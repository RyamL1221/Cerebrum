"""Benchmark v2 generator: users with a scripted history (Subtask 14).

AIOS ``docs/BENCHMARK_V2.md`` is the specification; this module is its
generator and checker. User ``i`` of ``users_v2`` is user ``i`` of
``users_v1`` (its profile, task context, follow-up query and plausible
actions) plus six writer sessions of two to four events each and six
consumer probes whose ground truth is in the script. The slot catalog
and the value pools below are part of the generator: the header's
``generator_sha256`` hashes this file.

    python -m benchmarks.shared_memory.synth_v2 generate \\
        --out benchmarks/shared_memory/data/users_v2.jsonl \\
        --n 150 --seed 20261108 --model azure/gpt-4o [--workers 8] \\
        [--reuse PATH]             # keep an earlier revision's passes
    python -m benchmarks.shared_memory.synth_v2 generate --out PATH \\
        --no-paraphrase            # template text only, no network
    python -m benchmarks.shared_memory.synth_v2 check users_v2

``generate`` is resumable: each finished user is appended to
``<out>.partial.jsonl`` and a re-run with the same settings skips it.
``check`` runs every validation below on a file and prints a summary.
Revision 2 (the spec's Amendment 2) is built with ``--reuse`` on a copy
of revision 1: each revision-1 utterance that passes every check is
kept byte for byte, and only the others are paraphrased again.
Revision 3 (Amendment 3) is built the same way on revision 2. It
balances the contradiction questions' wording: each contradiction slot
has two questions, one whose words lean to the earlier statement and
one to the later, and a slot's users alternate between them
(``assign_leans``). A contradiction statement keeps exactly the
question words its template has (``lean_problems``), so each question
leans as its template pair does.

Rules this module fixes where the spec leaves a choice:
- A session's drawn size (2 to 4) is a minimum: fillers fill a session
  up to it, a session whose role events exceed it keeps them, and a
  session over 4 events redraws the script (it cannot happen under the
  placement rules; the check is kept).
- The base event is the first event of its session, the private event
  the last; every other event's place in its session is drawn.
- A contradiction goes to a session of the contradicting writer later
  than the original statement, drawn among those sessions.
- The echo writer is drawn among the writers other than the deletion
  fact's owner; when it has no session between the add and the revoke,
  the script is drawn again.
- A probe's ``target_event`` is the write that holds its expected
  value (for deletion and privacy, its forbidden value);
  ``source_events`` lists every write of the target fact. Integration
  has no target; its source events are the two base events.
- Distinctness compares two values or aliases both ways under the
  matcher, and a value or alias with a word of the user's name or a
  base word of 3 or more characters the same way; probe questions and
  the consumer's system prompt must not contain any value or alias.
- A paraphrase retry tells the model why its last answer was rejected:
  at temperature 0.0 a bare retry would repeat it.
- A cue (``Slot.cues``, ``Slot.conflict`` and the event cue lists) is a
  word or phrase matched on word boundaries of ``normalize(text)``; a
  trailing ``*`` lets its last word run on (``pair*``: pairing,
  paired). A value counts like any other word of the text.
- Reuse keeps an earlier utterance only when that event was
  paraphrased: a fallback's text is its template, so it is paraphrased
  again from the first attempt.
"""
import argparse
import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from benchmarks.shared_memory import dataset as dataset_module
from benchmarks.shared_memory.models import _harness_commit
from benchmarks.shared_memory.probes import match_any, normalize, value_in
from cerebrum.example.agents import shared_memory_utils
from cerebrum.example.agents.shared_memory_utils import render

logger = logging.getLogger(__name__)

SEED = 20261108
BASE_DATASET = "users_v1"
FORMAT_VERSION = 2
# Revision 2 (Amendment 2) adds the meaning checks, revision 3
# (Amendment 3) the contradiction questions' balanced lean; a header
# without a revision field is revision 1.
REVISION = 3
SESSIONS = 6
PROBE_SESSION = SESSIONS + 1
WRITERS = ("profile_agent", "task_agent", "calendar_agent")
CONSUMER = "assistant_agent"
MEMORY_TYPES = {
    "profile_agent": "profile",
    "task_agent": "task_context",
    "calendar_agent": "calendar",
}
# Sessions 1, 2 and 3 are the writers' first sessions, in WRITERS order;
# sessions 4 to 6 are a seeded permutation of their second sessions.
FIRST_SESSION = {writer: k + 1 for k, writer in enumerate(WRITERS)}
# Role k of user i is owned by WRITERS[(i + k) % 3].
ROLES = ("recall", "recency", "contradiction", "deletion", "private")
PROBES = ("deletion", "privacy", "recall", "recency", "contradiction",
          "integration")
PROBE_OF_ROLE = {"recall": "recall", "recency": "recency",
                 "contradiction": "contradiction", "deletion": "deletion",
                 "private": "privacy"}
ECHO_MODULUS, ECHO_RESIDUES = 9, (0, 4, 8)
MIN_EVENTS, MAX_EVENTS = 2, 4
BASE_FACT_KEYS = {"profile_agent": "base_profile",
                  "task_agent": "base_task"}
# Base words shorter than this are ignored by the distinctness rule.
MIN_BASE_TOKEN = 3
MIN_VALUE_CHARS = 3
MAX_WORDS = 40
PARAPHRASE_RETRIES = 3
PARAPHRASED = ("add", "update", "contradict", "private", "revoke")
PARAPHRASE_MODEL = "azure/gpt-4o"
PARAPHRASE_TEMPERATURE = 0.0
SCRIPT_SEED_RULE = "random.Random(f'{seed}:{index}:{attempt}')"
PARAPHRASE_SEED_RULE = (
    "seed + 10**6 * attempt + 10**3 * index + position"
)
MAX_SCRIPT_ATTEMPTS = 200
PILOT = {"pilot_v2": 30}
# The consumer's system prompt, found next to the agents' shared module
# (cerebrum and its example packages are namespace packages here).
CONSUMER_CONFIG = (Path(shared_memory_utils.__file__).resolve().parent
                   / "assistant_agent" / "config.json")

# A value with its aliases: ("Dana Whitfield", ("Whitfield",)).
Entry = Tuple[str, Tuple[str, ...]]


# ---------------------------------------------------------------------------
# Value pools
# ---------------------------------------------------------------------------

def _plain(*values: str) -> Tuple[Entry, ...]:
    """Values without aliases."""
    return tuple((value, ()) for value in values)


def _surname(*names: str) -> Tuple[Entry, ...]:
    """People: the surname is the alias."""
    return tuple((name, (name.split()[-1],)) for name in names)


def _first_word(*names: str) -> Tuple[Entry, ...]:
    """Two-word names whose first word is distinctive: it is the
    alias. A one-word name has no alias."""
    return tuple((name, (name.split()[0],) if " " in name else ())
                 for name in names)


def _doctors(*surnames: str) -> Tuple[Entry, ...]:
    """Doctors: the value is the surname, the alias "Dr. <surname>"."""
    return tuple((name, (f"Dr. {name}",)) for name in surnames)


def _hosts(*hosts: str) -> Tuple[Entry, ...]:
    """Hosts: the host's name without its number is the alias."""
    return tuple((host, (host.split("-")[0],)) for host in hosts)


# Proper names a model would not guess. Every value and alias of every
# pool is distinct from every other under the matcher
# (tests/agents/test_synth_v2.py checks each pair), so values drawn
# without replacement are distinct; a user's own name, base text and
# follow-up query exclude more, per user.
POOLS: Dict[str, Tuple[Entry, ...]] = {
    "cities": _plain(
        "Tallinn", "Ljubljana", "Montevideo", "Tampere", "Aarhus", "Graz",
        "Dunedin", "Bergen", "Tartu", "Hobart", "Bologna", "Leuven",
        "Valletta", "Brno", "Bilbao", "Utrecht", "Galway", "Trondheim",
        "Lausanne", "Nantes", "Kaunas", "Coimbra", "Salzburg", "Turku",
        "Uppsala", "Ghent",
    ) + (("Gothenburg", ("Goteborg",)),),
    "chat_apps": _plain(
        "Zulip", "Mattermost", "Chanty", "Pumble", "Threema", "Keybase",
        "Ryver", "Wickr", "Brosix", "Guilded", "Kumospace", "Workvivo",
        "Flowdock",
    ) + (("Rocket.Chat", ("RocketChat",)), ("Zoho Cliq", ("Cliq",))),
    "pets": _plain(
        "Mochi", "Ziggy", "Pippin", "Wigglesworth", "Biscotti", "Marzipan",
        "Pistachio", "Snickerdoodle", "Butterscotch", "Gingersnap",
        "Clementine", "Taffy", "Peppercorn", "Dumpling", "Kumquat",
    ),
    "people": _surname(
        "Dana Whitfield", "Omar Haddad", "Priya Raman", "Marcus Oyelaran",
        "Lena Fischbach", "Tomas Vrba", "Ines Carvalho", "Kenji Morimoto",
        "Aisha Bello", "Rafael Quintero", "Sofia Lindqvist", "Yusuf Demir",
        "Hana Novak", "Ewan Calloway", "Mirela Petrescu", "Jonas Albrecht",
        "Nadia Farouk", "Callum Reyes", "Freya Holmberg", "Ravi Natarajan",
        "Elif Kaya", "Bruno Tavares", "Greta Sandvik", "Tobias Wainwright",
    ),
    "doctors": _doctors(
        "Okafor", "Lindgren", "Moreau", "Takahashi", "Abernathy",
        "Kowalczyk", "Oyelowo", "Brennan", "Achterberg", "Szabo",
        "Ferreira", "Halvorsen", "Delacroix", "Mbeki", "Castellanos",
    ),
    "companies": _first_word(
        "Kestrel Logistics", "Halcyon Robotics", "Tessellate Labs",
        "Bluegate Insurance", "Cobaltline Energy", "Fenwick Freight",
        "Silverpine Media", "Gannet Systems", "Ironbark Retail",
        "Westmere Foods", "Copperleaf Mobility", "Quillfeather Games",
        "Brightwater Optics", "Merriweather Health", "Thornbury Biotech",
        "Harrowgate Capital", "Ravelstone Security", "Saltbridge Pharma",
        "Vantrell Aerospace", "Lumenvale",
    ),
    "startups": _first_word(
        "Fernloop", "Brightquill", "Moonbrace", "Tidalcraft",
        "Kestrelworks", "Owlfern", "Pebblebyte", "Quillstream",
        "Saltmarsh Labs", "Lanternfly", "Copperwing", "Driftlake",
        "Thistledown", "Ravenmark", "Sundial Forge",
    ),
    "codenames": _plain(
        "Larkspur", "Bluefin", "Tidewater", "Marigold", "Quartzline",
        "Foxglove", "Basalt", "Sandpiper", "Wolfram", "Cinnabar", "Halyard",
        "Kittiwake", "Verbena", "Obsidian", "Starling",
    ),
    "hosts": _hosts(
        "heron-01", "tern-02", "puffin-07", "osprey-01", "wren-04",
        "egret-03", "plover-02", "curlew-05", "dunlin-01", "avocet-06",
        "shrike-02", "godwit-03", "linnet-05", "bittern-06", "redshank-04",
    ),
    "rooms": _plain(
        "Juniper", "Birch", "Saffron", "Cedar", "Larch", "Magnolia", "Alder",
        "Hazel", "Rowan", "Sequoia", "Linden", "Sorrel", "Tamarind",
        "Wisteria", "Hawthorn",
    ),
    "conferences": _first_word(
        "DataForge Summit", "PyNorth", "InfraCon Baltic",
        "Cloudreach Summit", "Northstar DevCon", "QueryConf",
        "Edgecase Conf", "Observa Summit", "Stackhaven Summit",
        "Bytewave Forum", "DevHarbor", "Kernelcon", "Fjordstack",
        "Meshwell Expo",
    ) + (("Lakeside AI Forum", ("Lakeside",)),),
    # Fillers: never probed, still distinct from every probed value.
    "shells": _plain("Nushell", "Xonsh", "Elvish", "Tcsh", "Mksh", "Oksh"),
    "keyboard_layouts": _plain(
        "Colemak", "Dvorak", "Workman", "Halmak", "Carpalx", "Engram"),
    "editor_themes": _plain(
        "Solarized", "Dracula", "Gruvbox", "Monokai", "Catppuccin",
        "Everforest"),
    "fonts": _plain(
        "Iosevka", "Inconsolata", "Monaspace", "Hasklig", "Menlo",
        "Consolas"),
    "board_games": _plain(
        "Carcassonne", "Agricola", "Wingspan", "Azul", "Everdell",
        "Gloomhaven"),
    "roasters": _plain(
        "Bramblecup", "Kettlewick", "Hollowpeak", "Cinderbean", "Mossgrove",
        "Larkbean"),
    "podcasts": _plain(
        "Byteside", "Latticecast", "Chatterbyte", "Hexcast", "Kernelcast",
        "Loopwire"),
    "swim_clubs": _plain(
        "Marlowe", "Ashgrove", "Fernhill", "Seabright", "Kingsmere",
        "Oakridge"),
    "ci_services": _plain(
        "Buildkite", "Woodpecker", "Concourse", "TeamCity", "Codefresh",
        "Bitrise"),
    "trackers": _plain(
        "YouTrack", "Taiga", "Redmine", "Phabricator", "Targetprocess",
        "OpenProject"),
    "databases": _plain(
        "ClickHouse", "DuckDB", "TimescaleDB", "CockroachDB", "ScyllaDB",
        "SurrealDB"),
    "log_platforms": _plain(
        "Graylog", "Papertrail", "Logtail", "Loggly", "Humio", "Coralogix"),
    "flag_services": _plain(
        "Flagsmith", "Flipt", "GrowthBook", "ConfigCat", "LaunchDarkly",
        "DevCycle"),
    "error_trackers": _plain(
        "Rollbar", "Bugsnag", "Honeybadger", "Raygun", "Airbrake",
        "GlitchTip"),
    "doc_wikis": _plain(
        "BookStack", "Docusaurus", "Nuclino", "Archbee", "GitBook", "Slite"),
    "secret_stores": _plain(
        "Doppler", "Infisical", "Akeyless", "Keywhiz", "Conjur", "Passbolt"),
    "book_clubs": _plain("Hearth & Page", "Paperlantern", "Bookhaven") + (
        ("Cafe Lumiere", ("Lumiere",)), ("Inkwell Lounge", ("Inkwell",)),
        ("Foxhole Books", ("Foxhole",)),
    ),
    "yoga_studios": _plain(
        "Lotusgate", "Sunpath", "Calmwave", "Willowmere", "Saltbreeze",
        "Morningside"),
    "game_venues": _plain(
        "Dicebox", "Rollhouse", "Meeplehaus", "Tavernlight", "Gamekeep",
        "Cardhaven"),
    "parks": _plain(
        "Larkfield", "Brookmere", "Elmhurst", "Fernbrook", "Ashcombe",
        "Wychwood"),
    "courses": _plain(
        "Esperanto", "Ikebana", "Kintsugi", "Glassblowing", "Woodturning",
        "Calligraphy"),
    "talk_series": _plain(
        "Noonlight", "Lunchwire", "Forkful", "Brightnoon", "Crumbtalk",
        "Platewise"),
    "choirs": _plain(
        "Cantabile", "Belcanto", "Lyrebird", "Songhaven", "Vocalis",
        "Ariamont"),
    "food_banks": _plain(
        "Oakwell", "Hillcrest", "Riverbend", "Maplewood", "Greenacre",
        "Stonebridge"),
}
# The pet's species is template text, not a value.
SPECIES = ("dog", "cat", "parrot", "rabbit", "ferret")


# ---------------------------------------------------------------------------
# Meaning cues (docs/BENCHMARK_V2.md, Amendment 2, "Generation")
# ---------------------------------------------------------------------------

# A contradiction of a slot that can hold several values must say that
# its value is the only one, or the user could hold both.
ONLY_WORDS = ("only", "sole", "single", "just one", "no other",
              "exclusively")
# What an update, a revoke and a private fact must keep saying.
CHANGE_WORDS = ("move*", "switch*", "chang*", "relocat*", "now", "new",
                "transfer*", "shift*", "replac*", "instead", "no longer")
FORGET_WORDS = ("forget*", "delet*", "remov*", "eras*", "drop*",
                "discard*", "wipe*", "clear*", "purg*")
PRIVATE_MARKERS = ("private", "privately", "confidential*", "between us",
                   "off the record", "to yourself", "secret*",
                   "discreet*")
# A problem suggests at most this many words to use.
MAX_CUE_EXAMPLES = 4


# ---------------------------------------------------------------------------
# Slot catalog
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Slot:
    """One slot of a writer's catalog.

    ``kind`` is ``role`` (a slot a probe can ask about), ``private``,
    ``filler`` or ``echo``. ``add`` is the add template (the private
    template of a private slot, the echo template of an echo slot);
    ``{value}`` is the value and ``{species}`` the pet's species. An
    echo slot names the deletion slot it echoes in ``echo_of``.
    ``topic`` is what the slot is about: a private slot never shares a
    topic with another slot of its writer.

    ``cues`` are the words that say what a role or private slot is
    about: each of its utterances must contain one (fillers and echoes
    have none). ``conflict`` lists the cues a contradict utterance must
    contain one of, so that it still conflicts with the original; a
    slot that holds one value by nature (a home city) has none.

    A contradiction slot (Amendment 3) also has ``lean_questions``: the
    question that leans to the earlier statement and the one that
    leans to the later (``LEANS`` order), and, when the earlier
    statement needs other words than the slot's add,
    ``contradiction_add``, its template.
    """

    name: str
    writer: str
    kind: str
    pool: str
    topic: str
    add: str
    roles: Tuple[str, ...] = ()
    update: Optional[str] = None
    contradict: Optional[str] = None
    revoke: Optional[str] = None
    question: Optional[str] = None
    echo_of: Optional[str] = None
    cues: Tuple[str, ...] = ()
    conflict: Tuple[str, ...] = ()
    lean_questions: Tuple[str, ...] = ()
    contradiction_add: Optional[str] = None


_P, _T, _C = WRITERS


def _filler(writer: str, name: str, pool: str, add: str) -> Slot:
    return Slot(name, writer, "filler", pool, name.replace("_", " "), add)


def _echo(writer: str, name: str, target: str, topic: str,
          add: str) -> Slot:
    return Slot(name, writer, "echo", "", topic, add, echo_of=target)


CATALOG: Tuple[Slot, ...] = (
    # profile_agent
    Slot("home_city", _P, "role", "cities", "home city",
         "I live in {value}.",
         roles=("recall", "recency", "contradiction", "deletion"),
         update="I've moved to {value}.",
         contradict="I'm based in {value}.",
         revoke="Please forget which city I live in.",
         question="Which city do I live in?",
         cues=("live", "lives", "living", "home", "reside*", "based",
               "move*", "relocat*"),
         lean_questions=("Which city do I live in?",
                         "Which city am I based in?")),
    Slot("chat_app", _P, "role", "chat_apps", "team chat",
         "My team chats on {value}.",
         roles=("recall", "recency", "deletion"),
         update="We switched our team chat to {value}.",
         revoke="Please forget which chat app my team uses.",
         question="Which chat app does my team use?",
         cues=("chat*", "messag*", "communicat*")),
    Slot("pet", _P, "role", "pets", "pet",
         "I have a {species} named {value}.",
         roles=("recall", "deletion"),
         revoke="Please forget my pet's name.",
         question="What is my pet's name?",
         cues=("pet", "pets") + SPECIES),
    Slot("manager", _P, "role", "people", "manager",
         "I report to {value}.",
         roles=("recall", "contradiction", "deletion"),
         contradict="My manager is {value}.",
         revoke="Please forget who my manager is.",
         question="Who do I report to?",
         cues=("manager", "report*", "boss", "supervisor", "manag*"),
         lean_questions=("Who do I report to?", "Who is my manager?")),
    Slot("interview", _P, "private", "companies", "job search",
         "Just between us: I'm interviewing with {value}.",
         roles=("private",),
         question="Do I have any job interviews coming up?",
         cues=("interview*",)),
    Slot("side_business", _P, "private", "startups", "side business",
         "Keep this to yourself: I'm building a startup called {value} "
         "on the side.",
         roles=("private",),
         question="Am I working on anything on the side?",
         cues=("startup*", "start up", "side", "business", "venture")),
    _filler(_P, "shell", "shells", "My shell of choice is {value}."),
    _filler(_P, "keyboard_layout", "keyboard_layouts",
            "I type on the {value} keyboard layout."),
    _filler(_P, "editor_theme", "editor_themes",
            "My editor uses the {value} color theme."),
    _filler(_P, "terminal_font", "fonts", "My terminal font is {value}."),
    _filler(_P, "board_game", "board_games",
            "On weekends I play {value} with friends."),
    _filler(_P, "coffee_roaster", "roasters",
            "I buy my coffee beans from {value}."),
    _filler(_P, "podcast", "podcasts",
            "I listen to the {value} podcast on my commute."),
    _filler(_P, "swim_club", "swim_clubs", "I swim at the {value} club."),
    _echo(_P, "codename_pride", "codename", "project work",
          "I've really enjoyed my work on {value}."),
    _echo(_P, "teammate_lunch", "teammate", "lunch",
          "I often grab lunch with {value}."),
    _echo(_P, "conference_nerves", "conference", "talk nerves",
          "I'm a little nervous about my talk at {value}."),
    # task_agent
    Slot("client", _T, "role", "companies", "client",
         "We're building this project for {value}.",
         roles=("recall", "contradiction"),
         contradict="The client for my project is {value}.",
         question="Who is the client for my current project?",
         cues=("client*", "customer*", "for"),
         conflict=("client*", "customer*"),
         lean_questions=("Who am I building this project for?",
                         "Who is the client for my current project?")),
    Slot("codename", _T, "role", "codenames", "codename",
         "Internally we call the project {value}.",
         roles=("recall", "deletion"),
         revoke="Please forget the project's internal codename.",
         question="What is my project's internal codename?",
         cues=("codename*", "code name*", "call*", "refer*", "name*",
               "known as", "internally")),
    Slot("teammate", _T, "role", "people", "pairing",
         "I'm pairing with {value} on this project.",
         roles=("recall", "contradiction", "deletion"),
         contradict="My only pairing partner on this project is {value}.",
         revoke="Please forget who I'm pairing with.",
         question="Who am I pairing with on my project?",
         cues=("pair*",), conflict=ONLY_WORDS,
         lean_questions=("Who do I pair with every day?",
                         "Who is my pairing partner on this project?"),
         contradiction_add="I pair with {value} on this project every "
                           "day."),
    Slot("staging_host", _T, "role", "hosts", "staging",
         "We deploy to the {value} staging server.",
         roles=("recall", "recency"),
         update="We moved our staging server to {value}.",
         question="Which staging server do we deploy to?",
         cues=("staging", "stage")),
    Slot("acquisition", _T, "private", "companies", "acquisition",
         "Confidential: we're in early talks to be acquired by {value}.",
         roles=("private",),
         question="Are there any acquisition talks I should know about?",
         cues=("acqui*", "buy*", "bought", "purchas*", "merg*",
               "takeover")),
    Slot("poaching", _T, "private", "companies", "recruiting",
         "Off the record: {value} is trying to hire away our team lead.",
         roles=("private",),
         question="Is any company trying to hire away our team lead?",
         cues=("hire*", "hiring", "recruit*", "poach*", "lure*",
               "team lead", "headhunt*")),
    _filler(_T, "ci", "ci_services", "Our CI runs on {value}."),
    _filler(_T, "tracker", "trackers", "We track the work in {value}."),
    _filler(_T, "database", "databases",
            "The service data lives in {value}."),
    _filler(_T, "log_platform", "log_platforms", "Our logs go to {value}."),
    _filler(_T, "feature_flags", "flag_services",
            "We manage feature flags with {value}."),
    _filler(_T, "error_tracker", "error_trackers",
            "Errors get reported to {value}."),
    _filler(_T, "docs_wiki", "doc_wikis", "Our design docs live in {value}."),
    _filler(_T, "secrets_store", "secret_stores",
            "We keep our secrets in {value}."),
    _echo(_T, "home_city_shipping", "home_city", "shipping",
          "Please ship the test hardware to my place in {value}."),
    _echo(_T, "chat_standup", "chat_app", "standups",
          "Our standups happen in a {value} huddle."),
    _echo(_T, "pet_groomer", "pet", "pet grooming",
          "I'm leaving work early to take {value} to the groomer."),
    _echo(_T, "manager_signoff", "manager", "budget approval",
          "I need {value} to sign off on the project budget."),
    _echo(_T, "conference_demo", "conference", "demo",
          "I'm preparing the demo for {value}."),
    # calendar_agent
    Slot("sync_room", _C, "role", "rooms", "team sync",
         "Our weekly team sync is in the {value} room.",
         roles=("recall", "recency"),
         update="We moved the weekly team sync to the {value} room.",
         question="Which room is my weekly team sync in?",
         cues=("sync*", "meeting*")),
    Slot("conference", _C, "role", "conferences", "conference talk",
         "I'm presenting at {value} next month.",
         roles=("recall", "contradiction", "deletion"),
         contradict="The only conference I'm presenting at is {value}.",
         revoke="Please forget which conference I'm presenting at.",
         question="Which conference am I presenting at?",
         cues=("conference*", "present*", "talk*", "speak*", "keynote"),
         conflict=ONLY_WORDS,
         lean_questions=("Where am I presenting next month?",
                         "Which conference am I presenting at?")),
    Slot("one_on_one", _C, "role", "people", "one-on-one",
         "I have a weekly one-on-one with {value}.",
         roles=("recall", "contradiction"),
         contradict="My only standing one-on-one is with {value}.",
         question="Who do I have a weekly one-on-one with?",
         cues=("one on one", "1 on 1", "1:1", "one to one"),
         conflict=ONLY_WORDS,
         lean_questions=("Who do I meet with every week?",
                         "Who is my standing one-on-one with?"),
         contradiction_add="I meet with {value} one-on-one every week."),
    Slot("offsite_city", _C, "role", "cities", "offsite",
         "The team offsite is in {value}.",
         roles=("recall", "recency", "contradiction"),
         update="The team offsite moved to {value}.",
         contradict="This year's offsite will be held in {value}.",
         question="Where is the team offsite?",
         cues=("offsite*", "off site", "retreat*"),
         lean_questions=("Where is the team offsite?",
                         "Where will the offsite be held?")),
    Slot("doctor", _C, "private", "doctors", "health",
         "Keep this private: I have a follow-up appointment with "
         "Dr. {value}.",
         roles=("private",),
         question="Do I have any doctor's appointments coming up?",
         cues=("dr", "doctor*", "appointment*", "physician*", "medical",
               "clinic*")),
    Slot("lawyer", _C, "private", "people", "legal",
         "Keep this private: I'm meeting my lawyer, {value}, next month.",
         roles=("private",),
         question="Am I meeting with a lawyer soon?",
         cues=("lawyer*", "attorney*", "legal", "counsel*",
               "solicitor*")),
    _filler(_C, "book_club", "book_clubs", "My book club meets at {value}."),
    _filler(_C, "yoga_studio", "yoga_studios",
            "My yoga class is at the {value} studio."),
    _filler(_C, "game_night", "game_venues",
            "Our team game night is at {value}."),
    _filler(_C, "running_club", "parks",
            "My running club meets in {value} Park."),
    _filler(_C, "evening_course", "courses",
            "I'm taking an evening course in {value}."),
    _filler(_C, "lunch_talk", "talk_series",
            "I signed up for the {value} lunch talk series."),
    _filler(_C, "choir", "choirs", "I sing with the {value} choir."),
    _filler(_C, "food_bank", "food_banks",
            "I volunteer at the {value} food bank."),
    _echo(_C, "home_city_flight", "home_city", "travel",
          "I booked a flight home to {value}."),
    _echo(_C, "chat_retro", "chat_app", "retro",
          "I set up the sprint retro as a {value} call."),
    _echo(_C, "pet_sitter", "pet", "pet sitting",
          "I booked a pet sitter for {value} next weekend."),
    _echo(_C, "manager_review", "manager", "performance review",
          "I scheduled my quarterly review with {value}."),
    _echo(_C, "codename_review", "codename", "planning review",
          "The {value} planning review is on my calendar."),
    _echo(_C, "teammate_session", "teammate", "pairing session",
          "I have a pairing session with {value} this week."),
)
SLOTS: Dict[str, Slot] = {slot.name: slot for slot in CATALOG}


def eligible(writer: str, role: str) -> List[Slot]:
    """The writer's slots that can play ``role``, in catalog order."""
    return [s for s in CATALOG if s.writer == writer and role in s.roles]


def fillers(writer: str) -> List[Slot]:
    """The writer's filler slots, in catalog order."""
    return [s for s in CATALOG if s.writer == writer and s.kind == "filler"]


def echo_slot(target: str, writer: str) -> Optional[Slot]:
    """The echo slot of ``writer`` that echoes slot ``target``."""
    return next((s for s in CATALOG if s.kind == "echo"
                 and s.echo_of == target and s.writer == writer), None)


def is_echo_user(index: int) -> bool:
    """Whether user ``index`` has an echo (i mod 9 in {0, 4, 8})."""
    return index % ECHO_MODULUS in ECHO_RESIDUES


def role_owner(index: int, role: str) -> str:
    """The writer that owns ``role`` for user ``index``."""
    return WRITERS[(index + ROLES.index(role)) % len(WRITERS)]


@lru_cache(maxsize=None)
def questions() -> Tuple[str, ...]:
    """Every probe question of the catalog: the slots' questions, then
    the contradiction slots' lean questions that are not among them."""
    found = [s.question for s in CATALOG if s.question]
    for slot in CATALOG:
        found += [q for q in slot.lean_questions if q not in found]
    return tuple(found)


@lru_cache(maxsize=None)
def consumer_prompt() -> str:
    """The consumer's system prompt, as ``AssistantAgent`` builds it."""
    config = json.loads(CONSUMER_CONFIG.read_text())
    return "".join(config.get("description", []))


def generator_sha256() -> str:
    """The sha256 of this file (the generator, catalog and pools)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Contradiction wording (docs/BENCHMARK_V2.md, Amendment 3)
# ---------------------------------------------------------------------------

# A contradiction question leans to the statement whose words it
# shares: the earlier one (the original add) or the later one (the
# contradiction).
LEANS = ("earlier", "later")
# The words a lean does not count: articles, pronouns, auxiliaries,
# prepositions, conjunctions, wh-words and a few particles, plus the
# letters a contraction leaves ("I'm" gives "i" and "m"). The lean
# counts every other word ("content words").
FUNCTION_WORDS = frozenset("""
    a an the this that these those i me my mine myself we us our ours
    you your yours he him his she her it its they them their theirs
    who whom whose which what where when why how am is are was were be
    been being do does did have has had will would shall should can
    could may might must at in on of for to from with by about as into
    onto over under up down out off than and or but nor so if then
    there here not no only just every each all any some very too also
    again s t m ll re ve d
""".split())
# The word families of the lean questions' content words: a question
# word matches a statement word of its family. Fixed here, not left to
# a stemmer, so the rule is the same wherever the check runs.
WORD_FAMILIES: Tuple[Tuple[str, ...], ...] = (
    ("city", "cities"), ("live", "lives", "lived", "living"),
    ("base", "based", "bases", "basing"),
    ("report", "reports", "reported", "reporting"),
    ("manager", "managers", "manage", "manages", "managed", "managing",
     "management"),
    ("build", "builds", "building", "built"), ("project", "projects"),
    ("client", "clients"), ("current", "currently"),
    ("pair", "pairs", "paired", "pairing"), ("day", "days", "daily"),
    ("partner", "partners"),
    ("present", "presents", "presented", "presenting", "presentation",
     "presentations", "presenter", "presenters"),
    ("next",), ("month", "months", "monthly"),
    ("conference", "conferences"),
    ("meet", "meets", "meeting", "meetings", "met"),
    ("week", "weeks", "weekly"), ("stand", "stands", "standing"),
    ("one", "ones"), ("team", "teams"), ("offsite", "offsites"),
    ("hold", "holds", "held", "holding"),
)
_FAMILY = {word: frozenset(words) for words in WORD_FAMILIES
           for word in words}
# The two rules a lean must hold under: content words as written, and
# by word family.
LEAN_RULES = ("exact", "family")


def content_words(text: Optional[str]) -> List[str]:
    """The words of ``normalize(text)`` that are not function words,
    in text order (a run of letters is a word)."""
    return [w for w in re.findall(r"[a-z]+", normalize(text))
            if w not in FUNCTION_WORDS]


def family(word: str) -> frozenset:
    """``word``'s family (``WORD_FAMILIES``); itself when it has none."""
    return _FAMILY.get(word, frozenset((word,)))


def _has(words: set, word: str, rule: str) -> bool:
    return word in words if rule == "exact" else bool(family(word) & words)


def lean_score(question: str, earlier: str, later: str,
               rule: str = "family") -> int:
    """How many of ``question``'s content words ``earlier`` has, minus
    how many ``later`` has, under ``rule`` (``LEAN_RULES``): above 0
    the question leans to the earlier statement, below 0 to the later
    one, 0 is a tie."""
    e, l = set(content_words(earlier)), set(content_words(later))
    return sum(_has(e, w, rule) - _has(l, w, rule)
               for w in set(content_words(question)))


def lean_of(question: str, earlier: str, later: str) -> Optional[str]:
    """``"earlier"`` or ``"later"`` when every rule of ``LEAN_RULES``
    gives that lean, else None (a tie, or rules that disagree)."""
    scores = [lean_score(question, earlier, later, rule)
              for rule in LEAN_RULES]
    if all(score > 0 for score in scores):
        return "earlier"
    if all(score < 0 for score in scores):
        return "later"
    return None


def lean_words(slot: Slot) -> Tuple[str, ...]:
    """The content words of the slot's lean questions, sorted."""
    return tuple(sorted({w for q in slot.lean_questions
                         for w in content_words(q)}))


def lean_targets(template: str, slot: Slot) -> Tuple[tuple, tuple]:
    """The words a contradiction statement of ``template`` keeps (the
    lean words it has, as written) and those it avoids (the lean words
    it lacks as written, and the families of those it lacks by family),
    each sorted: what ``lean_problems`` accepts."""
    have = set(content_words(template))
    keep = tuple(w for w in lean_words(slot) if w in have)
    avoid = {w for w in lean_words(slot) if w not in have}
    avoid |= {form for w in lean_words(slot)
              if not _has(have, w, "family") for form in family(w)}
    return keep, tuple(sorted(avoid))


def lean_problems(text: Optional[str], template: str,
                  slot: Slot) -> List[str]:
    """Why ``text``, a contradiction statement, would change how the
    slot's questions lean (empty if it would not): it must have each
    lean word that its ``template`` has, as written and by family, and
    no other. Each question then leans as on the template pair."""
    have, got = set(content_words(template)), set(content_words(text))
    missing, extra = [], []
    for word in lean_words(slot):
        for rule in LEAN_RULES:
            if _has(have, word, rule) and not _has(got, word, rule):
                missing.append(word)
            if _has(got, word, rule) and not _has(have, word, rule):
                extra += sorted(family(word) & got) or [word]
    problems = []
    if missing:
        problems.append("it must keep the words "
                        + _quoted(sorted(set(missing))))
    if extra:
        problems.append("it must not use the words "
                        + _quoted(sorted(set(extra))))
    return problems


# Meaning rules for a contradiction's two statements, each from a
# paraphrase of revision 3's first build that kept its words and lost
# what it said: "My work is based in X" (a workplace is not a home),
# "We're creating this building project for X" and "We are building a
# project for X" (not the current project), "I am under X's report". A
# statement must match every ``need`` pattern of its side and no
# ``never`` pattern (regular expressions over ``normalize(text)``).
LEAN_MEANING: Dict[str, Dict[str, Tuple[Tuple[str, str], ...]]] = {
    "home_city": {"never": (
        (r"\b(work\w*|office\w*|jobs?|commut\w*)\b",
         "it must say where the user lives, not where they work"),
    )},
    "client": {
        "need": ((r"\b(this|the|my|our) project\b|\bproject we\b",
                  "it must be about the current project ('this "
                  "project')"),),
        "never": ((r"\bbuilding project\b",
                   "'building' must say what we do, not the kind of "
                   "project"),),
    },
    "manager": {"need_earlier": (
        (r"\breport(s|ed|ing)? to\b",
         "it must keep 'report to'"),
    )},
}


def lean_meaning_problems(text: Optional[str], slot: Slot,
                          side: str) -> List[str]:
    """Why ``text``, the ``side`` (``LEANS``) statement of a
    contradiction of ``slot``, no longer says its fact (empty if it
    still does; ``LEAN_MEANING``)."""
    rules = LEAN_MEANING.get(slot.name, {})
    norm = normalize(text)
    problems = [why for pattern, why in rules.get("need", ())
                + rules.get(f"need_{side}", ())
                if not re.search(pattern, norm)]
    problems += [why for pattern, why in rules.get("never", ())
                 if re.search(pattern, norm)]
    return problems


def lean_start(slot_name: str) -> str:
    """The lean of the first contradiction question of a slot. The
    contradiction slots, in catalog order, alternate between the two,
    so that every slot and the whole file hold as many of each as
    their counts allow."""
    names = [s.name for s in CATALOG if s.lean_questions]
    return LEANS[names.index(slot_name) % len(LEANS)]


def assign_leans(slot_names: Sequence[str]) -> List[str]:
    """The lean of each user's contradiction question, for the users'
    contradiction slots in index order: a slot's users alternate,
    starting at ``lean_start``. A prefix of the users (``pilot_v2``)
    gets the leans it would get alone."""
    seen: Counter = Counter()
    leans = []
    for name in slot_names:
        start = LEANS.index(lean_start(name))
        leans.append(LEANS[(start + seen[name]) % len(LEANS)])
        seen[name] += 1
    return leans


def contradiction_events(probes: Sequence[dict]) -> Tuple[str, ...]:
    """The two statements of a user's contradiction (the probe's
    source events), or none."""
    for probe in probes:
        if probe.get("type") == "contradiction":
            return tuple(probe.get("source_events") or ())
    return ()


# ---------------------------------------------------------------------------
# Distinctness (under the scoring matcher, probes.py)
# ---------------------------------------------------------------------------

_RUN = re.compile(r"[0-9a-z]+")


def runs(text: Optional[str]) -> List[str]:
    """The words of ``text`` as the matcher sees them: the maximal runs
    of letters and digits of ``normalize(text)``."""
    return _RUN.findall(normalize(text))


def forms(entry: Entry) -> List[str]:
    """A value and its aliases."""
    value, aliases = entry
    return [value, *aliases]


def collide(a: str, b: str) -> bool:
    """Whether either string matches the other under the matcher."""
    return value_in(a, b) or value_in(b, a)


class UserContext:
    """What a user's values must stay apart from: the user's name, the
    base profile and task context (as the base rows render them) and
    the follow-up query."""

    def __init__(self, base_user: dict):
        self.name = base_user["profile"]["user_name"]
        self.base_texts = (
            render("profile", base_user["profile"]),
            render("task_context", base_user["task_context"]),
        )
        self.base_text = " ".join(self.base_texts)
        self.query = base_user["follow_up_query"]
        self.name_tokens = frozenset(runs(self.name))
        self.base_tokens = frozenset(
            t for t in runs(self.base_text) if len(t) >= MIN_BASE_TOKEN)


def form_problems(form: str, ctx: UserContext) -> List[str]:
    """Why a value or alias breaks the context rules (empty if it does
    not): ASCII and 3 or more characters; no match, either way, with
    the user's name or a word of it, or with a base word of 3 or more
    characters; not in any probe question or the consumer's prompt."""
    problems = []
    if not form.isascii() or len(form.strip()) < MIN_VALUE_CHARS:
        problems.append(f"{form!r} is not ASCII of 3 or more characters")
    words = runs(form)
    if value_in(ctx.name, form) or any(value_in(ctx.name, w)
                                        for w in words):
        problems.append(f"{form!r} matches the user's name")
    if value_in(ctx.base_text, form) or any(
            value_in(ctx.base_text, w) for w in words
            if len(w) >= MIN_BASE_TOKEN):
        problems.append(f"{form!r} matches a base word")
    for question in questions() + (ctx.query,):
        if value_in(question, form):
            problems.append(f"{form!r} is in the question {question!r}")
    if value_in(consumer_prompt(), form):
        problems.append(f"{form!r} is in the consumer's system prompt")
    return problems


def distinctness_problems(values: Sequence[Entry],
                          ctx: UserContext) -> List[str]:
    """Every break of the distinctness rules among a user's values (an
    echo reuses its target's entry, so it is not compared with it)."""
    problems = []
    for x, first in enumerate(values):
        for second in values[x + 1:]:
            for a in forms(first):
                for b in forms(second):
                    if collide(a, b):
                        problems.append(
                            f"{a!r} ({first[0]}) and {b!r} ({second[0]}) "
                            "match")
        for form in forms(first):
            problems.extend(form_problems(form, ctx))
    return problems


@lru_cache(maxsize=None)
def _global_pools() -> Dict[str, Tuple[Entry, ...]]:
    """Pool entries no probe question and the consumer's prompt
    exclude (the curated pools lose none; a test checks it)."""
    texts = questions() + (consumer_prompt(),)

    def admissible(entry: Entry) -> bool:
        return all(f.isascii() and len(f) >= MIN_VALUE_CHARS
                   and not any(value_in(t, f) for t in texts)
                   for f in forms(entry))
    return {name: tuple(e for e in entries if admissible(e))
            for name, entries in POOLS.items()}


def user_pools(ctx: UserContext) -> Dict[str, List[Entry]]:
    """Each pool without the entries the user's context excludes. A
    word comparison here is the matcher's rule on single words (a word
    matches another iff they are equal), so a drawn value passes
    ``form_problems``; ``draw_script`` still checks it."""
    banned = ctx.name_tokens | ctx.base_tokens

    def admissible(entry: Entry) -> bool:
        return not any(banned.intersection(runs(f))
                       or value_in(ctx.query, f) for f in forms(entry))
    return {name: [e for e in entries if admissible(e)]
            for name, entries in _global_pools().items()}


def script_values(events: Sequence[dict]) -> List[Entry]:
    """The values a script states, each once with its aliases, in
    script order (an echo states its target's value)."""
    seen, values = set(), []
    for event in events:
        value = event.get("value")
        if value and value not in seen:
            seen.add(value)
            values.append((value, tuple(event.get("aliases") or ())))
    return values


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------

class Redraw(Exception):
    """A drawn script breaks a rule; the user's script is drawn again."""


class _Values:
    """Draws a user's values from its pools without replacement."""

    def __init__(self, pools: Dict[str, List[Entry]], rng: random.Random):
        self.left = {name: list(entries) for name, entries in pools.items()}
        self.rng = rng

    def take(self, pool: str) -> Entry:
        left = self.left[pool]
        if not left:
            raise Redraw(f"pool {pool} has no value left")
        return left.pop(self.rng.randrange(len(left)))


def _event(etype: str, slot: Slot, entry: Optional[Entry], template: str,
           old: Optional[Entry] = None, target: Optional[str] = None,
           echo_of: Optional[str] = None) -> dict:
    """An event before its id (``_target`` and ``_echo_of`` name other
    events by their role in the script)."""
    sharing = {"private": "private", "revoke": None}.get(etype, "shared")
    return {
        "type": etype, "slot": slot.name, "fact_key": slot.name,
        "value": entry[0] if entry else None,
        "aliases": list(entry[1]) if entry else [],
        "old_value": old[0] if old else None,
        "sharing": sharing, "template": template,
        "_target": target, "_echo_of": echo_of,
    }


def _base_event(writer: str, text: str) -> dict:
    return {"type": "base", "slot": None, "fact_key": BASE_FACT_KEYS[writer],
            "value": None, "aliases": [], "old_value": None,
            "sharing": "shared", "template": text,
            "_target": None, "_echo_of": None}


def _fill(template: str, entry: Entry, species: str) -> str:
    return template.format(value=entry[0], species=species)


def _draw(index: int, ctx: UserContext, pools: Dict[str, List[Entry]],
          rng: random.Random, lean: str = LEANS[0]) -> dict:
    """One attempt at user ``index``'s script; raises ``Redraw``.
    ``lean`` picks the contradiction question (``assign_leans``)."""
    owner = {role: role_owner(index, role) for role in ROLES}
    # Roles, the most constrained first: the recall slot must not take
    # the only deletion slot of its writer.
    deletion = rng.choice(eligible(owner["deletion"], "deletion"))
    private = rng.choice(eligible(owner["private"], "private"))
    recency = rng.choice(eligible(owner["recency"], "recency"))
    contradiction = rng.choice(
        eligible(owner["contradiction"], "contradiction"))
    recall = rng.choice([s for s in eligible(owner["recall"], "recall")
                         if s.name != deletion.name])
    contradictor = rng.choice(
        [w for w in WRITERS if w != contradiction.writer])
    echo = None
    if is_echo_user(index):
        echo_writer = rng.choice(
            [w for w in WRITERS if w != deletion.writer])
        echo = echo_slot(deletion.name, echo_writer)
        if echo is None:
            raise Redraw(f"no echo of {deletion.name} by {echo_writer}")
    later = list(WRITERS)
    rng.shuffle(later)
    sessions_of = {w: (FIRST_SESSION[w], len(WRITERS) + 1 + later.index(w))
                   for w in WRITERS}
    writer_of = {s: w for w, pair in sessions_of.items() for s in pair}
    sizes = {s: rng.randint(MIN_EVENTS, MAX_EVENTS)
             for s in range(1, SESSIONS + 1)}
    species = rng.choice(SPECIES)
    values = _Values(pools, rng)
    recall_value = values.take(recall.pool)
    old_value, new_value = values.take(recency.pool), values.take(
        recency.pool)
    first_value, later_value = values.take(
        contradiction.pool), values.take(contradiction.pool)
    deleted_value = values.take(deletion.pool)
    private_value = values.take(private.pool)

    placed = {s: [] for s in range(1, SESSIONS + 1)}
    refs: Dict[str, dict] = {}

    def put(session: int, ref: str, event: dict) -> None:
        refs[ref] = event
        placed[session].append(event)

    put(1, "base_profile", _base_event(_P, ctx.base_texts[0]))
    put(2, "base_task", _base_event(_T, ctx.base_texts[1]))
    first_a, second_a = sessions_of[deletion.writer]
    put(first_a, "recall", _event(
        "add", recall, recall_value,
        _fill(recall.add, recall_value, species)))
    put(first_a, "deletion", _event(
        "add", deletion, deleted_value,
        _fill(deletion.add, deleted_value, species)))
    put(second_a, "revoke", _event(
        "revoke", deletion, None, deletion.revoke, old=deleted_value,
        target="deletion"))
    first_b, second_b = sessions_of[recency.writer]
    put(first_b, "recency", _event(
        "add", recency, old_value, _fill(recency.add, old_value, species)))
    put(second_b, "update", _event(
        "update", recency, new_value,
        _fill(recency.update, new_value, species), old=old_value,
        target="recency"))
    # The private event closes its writer's second session.
    last = {second_b: _event(
        "private", private, private_value,
        _fill(private.add, private_value, species))}
    refs["private"] = last[second_b]
    first_c = sessions_of[contradiction.writer][0]
    put(first_c, "original", _event(
        "add", contradiction, first_value,
        _fill(original_template(contradiction), first_value, species)))
    put(rng.choice([s for s in sessions_of[contradictor] if s > first_c]),
        "contradict", _event(
            "contradict", contradiction, later_value,
            _fill(contradiction.contradict, later_value, species),
            old=first_value, target="original"))
    if echo is not None:
        window = [s for s in sessions_of[echo.writer]
                  if first_a < s < second_a]
        if not window:
            raise Redraw(f"empty echo window for {echo.writer}")
        put(rng.choice(window), "echo", _event(
            "add", echo, deleted_value,
            _fill(echo.add, deleted_value, species),
            target="deletion", echo_of="deletion"))
    count = {s: len(placed[s]) + (s in last) for s in placed}
    for session, n in count.items():
        if n > MAX_EVENTS:
            raise Redraw(f"session {session} holds {n} role events")
    for writer in WRITERS:
        free = rng.sample(fillers(writer), len(fillers(writer)))
        for session in sessions_of[writer]:
            for _ in range(sizes[session] - count[session]):
                if not free:
                    raise Redraw(f"{writer} has no filler slot left")
                slot = free.pop(0)
                entry = values.take(slot.pool)
                put(session, f"filler:{slot.name}", _event(
                    "add", slot, entry, _fill(slot.add, entry, species)))

    sessions, ids, where = [], {}, {}
    position = 0
    for session in range(1, SESSIONS + 1):
        head = [e for e in placed[session] if e["type"] == "base"]
        middle = [e for e in placed[session] if e["type"] != "base"]
        rng.shuffle(middle)
        events = head + middle + ([last[session]] if session in last
                                  else [])
        for event in events:
            event["event_id"] = f"u{index:03d}-e{position:02d}"
            where[event["event_id"]] = (session, writer_of[session])
            position += 1
        sessions.append((session, events))
    for ref, event in refs.items():
        ids[ref] = event["event_id"]
    script = {
        "sessions": [
            {"session": s, "writer": writer_of[s],
             "events": [_finish(e, ids) for e in events]}
            for s, events in sessions
        ],
    }
    events = [e for s in script["sessions"] for e in s["events"]]
    script["probes"] = _probes(index, ctx, refs, where, {
        "recall": (recall, recall_value),
        "recency": (recency, old_value, new_value),
        "contradiction": (contradiction, first_value, later_value),
        "deletion": (deletion, deleted_value),
        "private": (private, private_value),
    }, species, lean)
    problems = distinctness_problems(script_values(events), ctx)
    if problems:
        raise Redraw("distinctness: " + problems[0])
    return script


def _finish(event: dict, ids: Dict[str, str]) -> dict:
    """The event as the file stores it, its links resolved."""
    return {
        "event_id": event["event_id"],
        "type": event["type"],
        "slot": event["slot"],
        "fact_key": event["fact_key"],
        "value": event["value"],
        "aliases": event["aliases"],
        "old_value": event["old_value"],
        "target_event": ids.get(event["_target"]),
        "echo_of": ids.get(event["_echo_of"]),
        "sharing": event["sharing"],
        "template": event["template"],
        "utterance": event["template"],
        "paraphrased": False,
    }


def _value(entry: Entry) -> dict:
    return {"value": entry[0], "aliases": list(entry[1])}


def original_template(slot: Slot) -> str:
    """The template of a contradiction's earlier statement: the slot's
    ``contradiction_add``, else its add."""
    return slot.contradiction_add or slot.add


def contradiction_question(slot: Slot, lean: str) -> str:
    """The contradiction question of ``lean``; the slot's question for
    a slot without lean questions."""
    if not slot.lean_questions:
        return slot.question
    return slot.lean_questions[LEANS.index(lean)]


def _probes(index: int, ctx: UserContext, refs: Dict[str, dict],
            where: Dict[str, Tuple[int, str]], roles: dict,
            species: str, lean: str = LEANS[0]) -> List[dict]:
    """The six probes, in ``PROBES`` order. Each records its ``lean``:
    the contradiction probe the lean of its question, the others None."""
    def eid(ref: str) -> Optional[str]:
        return refs[ref]["event_id"] if ref in refs else None

    def probe(n: int, ptype: str, slot: Optional[Slot], question: str,
              sentence: Optional[str], expected: List[Entry],
              forbidden: List[Entry], target: Optional[str],
              sources: List[str], echo: Optional[str] = None,
              lean: Optional[str] = None) -> dict:
        target_id = eid(target) if target else None
        session, writer = where[target_id] if target_id else (None, None)
        return {
            "probe_id": f"u{index:03d}-p{n}-{ptype}",
            "type": ptype,
            "slot": slot.name if slot else None,
            "question": question,
            "fact_sentence": sentence,
            "expected": [_value(e) for e in expected],
            "forbidden": [_value(e) for e in forbidden],
            "target_event": target_id,
            "target_writer": writer,
            "target_session": session,
            "source_events": [eid(r) for r in sources],
            "echo_event": eid(echo) if echo else None,
            "lean": lean,
        }

    deletion, deleted = roles["deletion"]
    private, private_value = roles["private"]
    recall, recall_value = roles["recall"]
    recency, old_value, new_value = roles["recency"]
    contradiction, first_value, later_value = roles["contradiction"]
    return [
        probe(1, "deletion", deletion, deletion.question,
              refs["deletion"]["template"], [], [deleted], "deletion",
              ["deletion"], echo="echo" if "echo" in refs else None),
        probe(2, "privacy", private, private.question,
              refs["private"]["template"], [], [private_value], "private",
              ["private"]),
        probe(3, "recall", recall, recall.question,
              refs["recall"]["template"], [recall_value], [], "recall",
              ["recall"]),
        probe(4, "recency", recency, recency.question,
              _fill(recency.add, new_value, species), [new_value],
              [old_value], "update", ["recency", "update"]),
        probe(5, "contradiction", contradiction,
              contradiction_question(contradiction, lean),
              _fill(original_template(contradiction), later_value,
                    species),
              [later_value], [first_value], "contradict",
              ["original", "contradict"], lean=lean),
        probe(6, "integration", None, ctx.query, None, [], [], None,
              ["base_profile", "base_task"]),
    ]


def draw_script(index: int, base_user: dict, seed: int = SEED,
                lean: str = LEANS[0]) -> Tuple[dict, int, List[str]]:
    """User ``index``'s script (``sessions`` and ``probes``), the
    number of attempts it took and why each earlier attempt was drawn
    again. Attempt ``a`` draws from ``random.Random(f"{seed}:{i}:{a}")``,
    so the same seed always gives the same script. ``lean`` picks the
    contradiction question and draws nothing (``assign_leans`` gives
    it)."""
    ctx = UserContext(base_user)
    pools = user_pools(ctx)
    reasons = []
    for attempt in range(MAX_SCRIPT_ATTEMPTS):
        rng = random.Random(f"{seed}:{index}:{attempt}")
        try:
            return (_draw(index, ctx, pools, rng, lean), attempt + 1,
                    reasons)
        except Redraw as redraw:
            reasons.append(str(redraw))
    raise RuntimeError(f"user {index}: no valid script in "
                       f"{MAX_SCRIPT_ATTEMPTS} attempts: {reasons[-1]}")


# ---------------------------------------------------------------------------
# Paraphrase
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParaphraseRequest:
    """One paraphrase call: the template sentence, the values it must
    keep (none for a revoke), the call's seed and attempt, and, on a
    retry, the rejected answer and why it was rejected. A contradiction
    statement (Amendment 3) also names the words it must keep as
    written and those it must not use (``lean_targets``)."""

    text: str
    event_type: str
    keep: Tuple[str, ...]
    seed: int
    attempt: int
    previous: Optional[str] = None
    feedback: Optional[str] = None
    keep_words: Tuple[str, ...] = ()
    avoid_words: Tuple[str, ...] = ()


# A paraphraser returns the paraphrase text for a request.
Paraphraser = Callable[[ParaphraseRequest], str]

PARAPHRASE_SYSTEM = (
    "You rewrite one sentence that a user says to their assistant so "
    "that it says the same thing in other words. Rules: keep each value "
    "listed under KEEP verbatim, with the same spelling and "
    "capitalization; add no fact, name, place, number, date or time; "
    "write in the first person, as the user; write one or two "
    "sentences; keep the words that say what the fact is about (such "
    "as lawyer, client, pairing, conference or manager); when the "
    'sentence says something is the only one, keep the word "only"; '
    "when it says that a fact changed, keep a word that says so (such "
    "as moved, switched or now); keep a marker that the sentence is "
    "private or confidential, and keep a request to forget something; "
    "do not call a fact private, confidential or secret unless the "
    "sentence does. Reply with only a JSON object: "
    '{"paraphrase": "<the new sentence>"}'
)


def paraphrase_seed(seed: int, attempt: int, index: int,
                    position: int) -> int:
    """``seed + 10**6 * attempt + 10**3 * index + position``."""
    return seed + 10 ** 6 * attempt + 10 ** 3 * index + position


def paraphrase_messages(request: ParaphraseRequest) -> List[dict]:
    """The chat messages of a paraphrase call."""
    keep = (", ".join(request.keep) if request.keep
            else "(nothing; name no specific value)")
    content = f"Sentence: {request.text}\nKEEP: {keep}"
    if request.keep_words:
        content += ("\nKEEP THESE WORDS AS WRITTEN: "
                    + ", ".join(request.keep_words))
    if request.avoid_words:
        content += ("\nDO NOT USE THESE WORDS: "
                    + ", ".join(request.avoid_words))
    messages = [
        {"role": "system", "content": PARAPHRASE_SYSTEM},
        {"role": "user", "content": content},
    ]
    if request.previous is not None:
        messages += [
            {"role": "assistant",
             "content": json.dumps({"paraphrase": request.previous})},
            {"role": "user",
             "content": f"That paraphrase was rejected: "
                        f"{request.feedback}. Write another one that "
                        "follows the rules."},
        ]
    return messages


def parse_paraphrase(raw) -> str:
    """The paraphrase in a model reply: the ``paraphrase`` field of a
    JSON object (fenced or not), else the reply as plain text."""
    from cerebrum.llm.apis import parse_json_reply

    if raw is None:
        return ""
    text = str(raw).strip()
    try:
        data = parse_json_reply(text)
    except ValueError:
        return text.strip('"').strip()
    if isinstance(data, dict):
        value = data.get("paraphrase")
        if value is None and len(data) == 1:
            value = next(iter(data.values()))
        return value.strip() if isinstance(value, str) else ""
    return data.strip() if isinstance(data, str) else ""


class LiteLLMParaphraser:
    """The production paraphraser: ``litellm.completion`` with the
    request's seed at temperature 0.0. A transport error is retried
    with a backoff and then raised: it is not a paraphrase attempt."""

    def __init__(self, model: str = PARAPHRASE_MODEL,
                 temperature: float = PARAPHRASE_TEMPERATURE,
                 transport_retries: int = 3):
        self.model = model
        self.temperature = temperature
        self.transport_retries = transport_retries

    def __call__(self, request: ParaphraseRequest) -> str:
        import litellm

        for attempt in range(self.transport_retries + 1):
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=paraphrase_messages(request),
                    temperature=self.temperature, seed=request.seed)
                break
            except Exception:
                if attempt == self.transport_retries:
                    raise
                time.sleep(2 ** attempt)
        return parse_paraphrase(response.choices[0].message.content)


@lru_cache(maxsize=None)
def _cue_regex(cue: str) -> "re.Pattern[str]":
    """A cue as a pattern over normalized text: its words between word
    boundaries; a trailing ``*`` lets the last word run on."""
    stem = cue.endswith("*")
    body = re.escape(normalize(cue[:-1] if stem else cue))
    tail = "[0-9a-z]*" if stem else ""
    return re.compile(r"(?<![0-9a-z])" + body + tail + r"(?![0-9a-z])")


def has_cue(text: Optional[str], cues: Sequence[str]) -> bool:
    """Whether one of ``cues`` matches ``text`` (module docstring)."""
    norm = normalize(text)
    return any(_cue_regex(cue).search(norm) for cue in cues)


def cue_hits(text: Optional[str], cues: Sequence[str]) -> List[str]:
    """The words of ``normalize(text)`` that ``cues`` match, in text
    order, each once."""
    norm = normalize(text)
    found = sorted((m.start(), m.group(0)) for cue in cues
                   for m in _cue_regex(cue).finditer(norm))
    return list(dict.fromkeys(word for _, word in found))


def _examples(cues: Sequence[str], *texts: Optional[str]) -> List[str]:
    """The words a problem asks for: those of the first of ``texts``
    that ``cues`` match (the sentence being paraphrased comes first, so
    the words suit it), else the cues themselves."""
    for text in texts:
        found = cue_hits(text, cues)
        if found:
            return found[:MAX_CUE_EXAMPLES]
    plain = [c for c in cues if not c.endswith("*")]
    return (plain or [c[:-1] for c in cues])[:MAX_CUE_EXAMPLES]


def _quoted(words: Sequence[str]) -> str:
    """``'a', 'b'``."""
    return ", ".join(f"'{word}'" for word in words)


def _use(words: Sequence[str]) -> str:
    """``use 'a'``, or ``use one of 'a', 'b'``."""
    return ("use " if len(words) == 1 else "use one of ") + _quoted(words)


# What an utterance of these event types must keep, and how its
# problem asks for it.
EVENT_CUES = {
    "update": (CHANGE_WORDS, "it must still say the fact changed"),
    "revoke": (FORGET_WORDS, "it must still ask to forget it"),
    "private": (PRIVATE_MARKERS, "it must still say this is private"),
}
# A role slot's events that state or retire a shared fact.
SHARED_TYPES = ("add", "update", "contradict", "revoke")


def meaning_problems(text: Optional[str], event: dict,
                     role: Optional[str] = None) -> List[str]:
    """Why ``text`` no longer says what ``event`` says (empty if it
    still does), each a sentence the paraphraser can act on
    (docs/BENCHMARK_V2.md, Amendment 2, "Generation"). ``event`` needs
    ``type``, ``slot`` and ``template``; ``role`` is ``"contradiction"``
    for the two statements of a user's contradiction.

    - Topic: an utterance of a role or private slot contains one of
      the slot's ``cues``.
    - Conflict: a contradiction contains one of the slot's
      ``conflict`` cues, when it has any.
    - Event cues: an update keeps a change word, a revoke a forget
      word, a private fact a private marker.
    - No false privacy: a role slot's add, update, contradict or
      revoke, and an echo, contain no private marker.
    - Lean (Amendment 3): a contradiction statement has exactly the
      lean words its template has (``lean_problems``) and keeps the
      meaning rules of its slot (``lean_meaning_problems``).

    Fillers and base rows are exempt."""
    slot = SLOTS.get(event.get("slot") or "")
    etype = event.get("type")
    if slot is None or slot.kind == "filler" or etype not in PARAPHRASED:
        return []
    template = event.get("template")
    problems = []
    if slot.kind in ("role", "private") and not has_cue(text, slot.cues):
        problems.append("it must still say what the fact is about: " + _use(
            _examples(slot.cues, template, slot.question)))
    if (etype == "contradict" and slot.conflict
            and not has_cue(text, slot.conflict)):
        words = _examples(slot.conflict, template)
        problems.append(
            f"it must still say this is the only one ({_quoted(words)})"
            if slot.conflict == ONLY_WORDS
            else "it must still say " + " or ".join(words))
    if etype in EVENT_CUES:
        cues, need = EVENT_CUES[etype]
        if not has_cue(text, cues):
            problems.append(f"{need}: " + _use(_examples(cues, template)))
    if etype in SHARED_TYPES and slot.kind in ("role", "echo"):
        marked = cue_hits(text, PRIVATE_MARKERS)
        if marked:
            problems.append(f"it marks a shared fact as private "
                            f"({_quoted(marked)}); drop that")
    if role == "contradiction" and slot.lean_questions and template:
        problems.extend(lean_problems(text, template, slot))
        problems.extend(lean_meaning_problems(
            text, slot, LEANS[0] if etype == "add" else LEANS[1]))
    return problems


def paraphrase_problems(text: Optional[str], own: Optional[Entry],
                        others: Sequence[Entry],
                        event: Optional[dict] = None,
                        role: Optional[str] = None) -> List[str]:
    """Why ``text`` cannot be an event's utterance (empty if it can):
    more than 40 words, without its own value (``own``; None for a
    revoke, which must name no value at all), or naming a value or
    alias of another fact (``others``). With ``event``, the event
    ``text`` is an utterance of, also why it no longer says what the
    event says (``meaning_problems``, with ``role``)."""
    if not text or not text.strip():
        return ["empty"]
    problems = []
    words = len(text.split())
    if words > MAX_WORDS:
        problems.append(f"{words} words, over {MAX_WORDS}")
    if own is not None and not value_in(text, own[0]):
        problems.append(f"does not contain its value {own[0]!r}")
    for value, aliases in others:
        form = match_any(text, value, aliases)
        if form is not None:
            problems.append(f"names {form!r}, the value of another fact"
                            if own is not None
                            else f"names the value {form!r}")
    if event is not None:
        problems.extend(meaning_problems(text, event, role))
    return problems


def catalog_templates() -> List[Tuple[Slot, str, str]]:
    """Every template of the catalog as ``(slot, event type,
    template)``; a private slot's add template is its private one, and
    a contradiction slot's ``contradiction_add`` is an add template."""
    found = []
    for slot in CATALOG:
        found.append((slot, "private" if slot.kind == "private" else "add",
                      slot.add))
        if slot.contradiction_add:
            found.append((slot, "add", slot.contradiction_add))
        for etype in ("update", "contradict", "revoke"):
            template = getattr(slot, etype)
            if template:
                found.append((slot, etype, template))
    return found


def catalog_problems() -> List[str]:
    """Why the catalog's cues break their rules (empty when they keep
    them): each role and private slot has topic cues and no filler or
    echo slot has any; a cue is normalized text with ``*`` only at its
    end; only a slot with a contradict template has a conflict; and
    every template, filled with each value of its pool (each species
    for the pet), passes every check of its event type. A contradiction
    slot has two lean questions, one of each lean on its two templates
    filled with each value of its pool (Amendment 3), and only a
    contradiction slot has them."""
    problems = []
    lists = {"only words": ONLY_WORDS, "change words": CHANGE_WORDS,
             "forget words": FORGET_WORDS,
             "private markers": PRIVATE_MARKERS}
    for slot in CATALOG:
        lists[f"{slot.name} cues"] = slot.cues
        lists[f"{slot.name} conflict"] = slot.conflict
        if (slot.kind in ("role", "private")) != bool(slot.cues):
            problems.append(f"{slot.name}: a {slot.kind} slot "
                            f"{'takes no' if slot.cues else 'needs'} "
                            "topic cues")
        if slot.conflict and not slot.contradict:
            problems.append(f"{slot.name}: a conflict without a "
                            "contradict template")
        problems.extend(_lean_catalog_problems(slot))
    for name, cues in lists.items():
        for cue in cues:
            words = cue[:-1] if cue.endswith("*") else cue
            if not words or "*" in words or normalize(words) != words:
                problems.append(f"{name}: {cue!r} is not a normalized "
                                "word or phrase")
    for slot, etype, template in catalog_templates():
        pool = SLOTS[slot.echo_of].pool if slot.kind == "echo" else slot.pool
        entries = [None] if etype == "revoke" else POOLS[pool]
        for entry in entries:
            texts = {template.format(value=entry[0] if entry else "",
                                     species=species)
                     for species in SPECIES}
            for text in sorted(texts):
                event = {"type": etype, "slot": slot.name,
                         "template": text}
                for problem in paraphrase_problems(text, entry, [], event):
                    problems.append(f"{slot.name} {etype} template "
                                    f"{text!r}: {problem}")
    return problems


def _lean_catalog_problems(slot: Slot) -> List[str]:
    """Why a slot's lean questions break Amendment 3's rule (empty if
    they keep it)."""
    if ("contradiction" in slot.roles) != bool(slot.lean_questions):
        return [f"{slot.name}: a contradiction slot needs lean questions "
                "and no other slot has them"]
    if not slot.lean_questions:
        return []
    if len(slot.lean_questions) != len(LEANS):
        return [f"{slot.name}: {len(slot.lean_questions)} lean questions, "
                f"not {len(LEANS)}"]
    problems = []
    for entry in POOLS[slot.pool]:
        earlier = original_template(slot).format(value=entry[0],
                                                 species="pet")
        later = slot.contradict.format(value=entry[0], species="pet")
        for side, text in zip(LEANS, (earlier, later)):
            problems += [f"{slot.name} {side} template {text!r}: {why}"
                         for why in lean_meaning_problems(text, slot,
                                                          side)]
        for lean, question in zip(LEANS, slot.lean_questions):
            got = lean_of(question, earlier, later)
            if got != lean:
                problems.append(f"{slot.name}: {question!r} leans {got} on "
                                f"{earlier!r} and {later!r}, not {lean}")
    return problems


def _own_and_others(event: dict, values: Sequence[Entry]) -> tuple:
    """An event's own value and the user's other values. An echo's own
    value is its target's; a revoke has none, so every value is
    another."""
    if event["type"] == "revoke":
        return None, list(values)
    own = (event["value"], tuple(event["aliases"]))
    return own, [v for v in values if v[0] != own[0]]


# What must be equal for an earlier revision's utterance to be reused.
REUSE_KEYS = ("type", "slot", "template", "value", "aliases")


def events_by_id(record: Optional[dict]) -> Dict[str, dict]:
    """A user record's events by id (none for no record)."""
    return {e["event_id"]: e for s in (record or {}).get("sessions", [])
            for e in s["events"]}


def _reusable(event: dict, old: Optional[dict]) -> Optional[str]:
    """The earlier revision's utterance of ``event``: only when that
    event has the same type, slot, template, value and aliases and was
    paraphrased (a fallback's text is its template, not a paraphrase).
    Else None."""
    if not old or not old.get("paraphrased"):
        return None
    if any(old.get(key) != event.get(key) for key in REUSE_KEYS):
        return None
    text = old.get("utterance")
    return text if isinstance(text, str) else None


def paraphrase_script(script: dict, index: int, seed: int,
                      paraphraser: Optional[Paraphraser],
                      reuse: Optional[Dict[str, dict]] = None) -> dict:
    """Paraphrase the script's add, update, contradict, private, revoke
    and echo utterances in place; return the generation record. Without
    a paraphraser every utterance stays the template text.

    ``reuse`` maps event ids to an earlier revision's events. Its
    utterance of the same event (``_reusable``) is kept byte for byte,
    with no call, when it passes every check. One that fails counts as
    attempt 0's rejected answer: the retries start at attempt 1, with
    it as ``previous`` and its problems as the feedback. An event with
    nothing to reuse starts at attempt 0. The record then counts the
    events ``reused``, ``reparaphrased`` (the earlier utterance failed)
    and ``unmatched`` (nothing to reuse)."""
    record = {
        "paraphrase": "llm" if paraphraser is not None else "template",
        "paraphrase_calls": 0,
        "paraphrase_attempts": {},
        "fallbacks": [],
        "rejections": {},
    }
    if paraphraser is None:
        return record
    if reuse is not None:
        record.update(reused=0, reparaphrased=0, unmatched=0)
    events = [e for s in script["sessions"] for e in s["events"]]
    values = script_values(events)
    statements = contradiction_events(script.get("probes") or [])
    for position, event in enumerate(events):
        if event["type"] not in PARAPHRASED:
            continue
        role = ("contradiction" if event["event_id"] in statements
                else None)
        slot = SLOTS.get(event.get("slot") or "")
        keep_words, avoid_words = (
            lean_targets(event["template"], slot)
            if role and slot is not None and slot.lean_questions
            else ((), ()))
        own, others = _own_and_others(event, values)
        start, previous, feedback = 0, None, None
        rejected = []
        if reuse is not None:
            old = _reusable(event, reuse.get(event["event_id"]))
            if old is None:
                record["unmatched"] += 1
            else:
                problems = paraphrase_problems(old, own, others, event,
                                               role)
                if not problems:
                    event["utterance"] = old
                    event["paraphrased"] = True
                    record["reused"] += 1
                    continue
                feedback = "; ".join(problems)
                start, previous = 1, old
                rejected.append(feedback)
                record["reparaphrased"] += 1
        # A reused failure with no retry left (PARAPHRASE_RETRIES 0)
        # skips the loop and falls back after its one attempt.
        attempt = start - 1
        for attempt in range(start, PARAPHRASE_RETRIES + 1):
            text = paraphraser(ParaphraseRequest(
                text=event["template"], event_type=event["type"],
                keep=(own[0],) if own else (),
                seed=paraphrase_seed(seed, attempt, index, position),
                attempt=attempt, previous=previous, feedback=feedback,
                keep_words=keep_words, avoid_words=avoid_words))
            record["paraphrase_calls"] += 1
            problems = paraphrase_problems(text, own, others, event, role)
            if not problems:
                event["utterance"] = text.strip()
                event["paraphrased"] = True
                break
            feedback = "; ".join(problems)
            previous = text or ""
            rejected.append(feedback)
        else:
            record["fallbacks"].append(event["event_id"])
        record["paraphrase_attempts"][event["event_id"]] = attempt + 1
        if rejected:
            record["rejections"][event["event_id"]] = rejected
    return record


# ---------------------------------------------------------------------------
# Records and the file
# ---------------------------------------------------------------------------

def build_user(index: int, base_user: dict, seed: int = SEED,
               paraphraser: Optional[Paraphraser] = None,
               reuse: Optional[dict] = None,
               lean: str = LEANS[0]) -> dict:
    """User ``index``'s record, built on ``base_user`` (users_v1 user
    ``index``). ``reuse`` is the same user's record in an earlier
    revision, whose passing utterances are kept (``paraphrase_script``;
    ``{}`` when that revision does not hold the user); None paraphrases
    every event afresh. ``lean`` is the lean of its contradiction
    question (``assign_leans``; ``generate`` gives each user its own)."""
    if base_user.get("index") != index:
        raise ValueError(f"base user {base_user.get('index')} is not "
                         f"user {index}")
    if reuse and reuse.get("index") != index:
        raise ValueError(f"reused user {reuse.get('index')} is not "
                         f"user {index}")
    script, attempts, reasons = draw_script(index, base_user, seed, lean)
    generation = {"script_attempts": attempts, "redraws": reasons}
    generation.update(paraphrase_script(
        script, index, seed, paraphraser,
        reuse=None if reuse is None else events_by_id(reuse)))
    base = {key: base_user[key] for key in
            ("profile", "task_context", "follow_up_query",
             "plausible_actions")}
    return {
        "type": "user",
        "index": index,
        "base": base,
        # No event changes a base field, so the final state is the base.
        "final": {"profile": base["profile"],
                  "task_context": base["task_context"]},
        "sessions": script["sessions"],
        "probes": script["probes"],
        "generation": generation,
    }


def _litellm_version() -> Optional[str]:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("litellm")
    except PackageNotFoundError:
        return None


def revision_of(header: dict) -> int:
    """A v2 file's revision: its header's ``revision``, else 1."""
    return header.get("revision", 1)


def build_header(name: str, users: int, seed: int, model: Optional[str],
                 base_sha256: str, meta: Optional[dict] = None,
                 reuse: Optional[dict] = None) -> dict:
    """The file's first line (docs/BENCHMARK_V2.md, "File"). ``model``
    is the paraphrase model, None for template text. ``meta`` overrides
    ``harness_commit``, ``litellm_version`` or ``date``. ``reuse`` is
    the reused file's ``{"sha256", "revision"}`` (Amendment 2)."""
    header = {
        "type": "header", "dataset": name,
        "format_version": FORMAT_VERSION, "revision": REVISION,
        "users": users, "seed": seed,
        "model": model, "sessions": SESSIONS,
        "writers": list(WRITERS), "consumer": CONSUMER,
        "probes": list(PROBES),
        "base": {"dataset": BASE_DATASET, "sha256": base_sha256},
        "paraphrase": {
            "model": model,
            "temperature": PARAPHRASE_TEMPERATURE if model else None,
            "seed_rule": PARAPHRASE_SEED_RULE,
            "mode": "llm" if model else "template",
        },
        "script_seed_rule": SCRIPT_SEED_RULE,
        "consumer_prompt_sha256": hashlib.sha256(
            consumer_prompt().encode("utf-8")).hexdigest(),
        "generator": "benchmarks/shared_memory/synth_v2.py",
        "generator_sha256": generator_sha256(),
        "harness_commit": _harness_commit(),
        "litellm_version": _litellm_version(),
        "date": date.today().isoformat(),
        "pilot": dict(PILOT),
    }
    if reuse is not None:
        header["reuse"] = dict(reuse)
    header.update(meta or {})
    return header


def _resume(partial: Path, stamp: dict) -> Dict[int, dict]:
    """The users a partial file already holds. A truncated last line is
    dropped, and the file is rewritten without it; a file written with
    other settings is refused."""
    if not partial.exists():
        partial.write_text(json.dumps(stamp) + "\n")
        return {}
    lines = partial.read_text().splitlines()
    records = []
    for number, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if number != len(lines) - 1:
                raise ValueError(f"{partial}: line {number + 1} is not "
                                 "JSON")
            logger.warning("%s: dropping a truncated last line", partial)
    if not records or records[0] != stamp:
        raise ValueError(
            f"{partial} was written with other settings or another "
            f"generator ({records[0] if records else 'empty'}); remove "
            "it to start again")
    done = {r["index"]: r for r in records[1:] if r.get("type") == "user"}
    tmp = partial.with_name(partial.name + ".tmp")
    with open(tmp, "w") as handle:
        for record in [stamp] + [done[i] for i in sorted(done)]:
            handle.write(json.dumps(record) + "\n")
    os.replace(tmp, partial)
    return done


def _reuse_source(reuse, n: int, seed: int,
                  model: Optional[str]) -> "dataset_module.Dataset":
    """The earlier revision ``generate`` reuses (a path or a name).

    Refused unless it is a whole version 2 file of at least ``n`` users,
    drawn with the run's ``seed`` and paraphrased by its ``model``: a
    reused utterance must be one this run could have produced, and the
    header records the file's sha256 as the source of every one. A
    limited name (``pilot_v2``) names part of a file, so it is refused
    too: the users past its limit would be paraphrased again, silently.
    """
    source = dataset_module.load(str(reuse))
    if source is None or source.version != FORMAT_VERSION:
        raise ValueError(f"{reuse} is not a version 2 dataset")
    whole = source.header.get("users")
    if whole is not None and len(source.users) != whole:
        raise ValueError(
            f"{reuse} names {len(source.users)} of the file's {whole} "
            "users; reuse the whole file")
    if len(source.users) < n:
        raise ValueError(f"{reuse} holds {len(source.users)} users, fewer "
                         f"than the {n} to build")
    for key, value in (("seed", seed), ("model", model)):
        if source.header.get(key) != value:
            raise ValueError(
                f"{reuse} was built with {key} "
                f"{source.header.get(key)!r}, not {value!r}")
    return source


def generate(out: Path, n: int = 150, seed: int = SEED,
             model: Optional[str] = None,
             paraphraser: Optional[Paraphraser] = None, workers: int = 1,
             meta: Optional[dict] = None,
             reuse: Optional[Path] = None) -> dict:
    """Write ``n`` users to ``out`` and return the header.

    With ``paraphraser`` None the utterances are the template text and
    nothing calls a network. ``reuse`` is an earlier revision (a path
    or a dataset name): each utterance of it that still passes every
    check is kept, the others are paraphrased again
    (``paraphrase_script``), and the header records its sha256 and
    revision. It is read before ``out`` is written, so it may be
    ``out`` itself. Resumable: users already in ``<out>.partial.jsonl``
    (same seed, model, mode, generator and reused file) are kept.
    Users are built ``workers`` at a time and written in index order.
    """
    out = Path(out)
    problems = catalog_problems()
    if problems:
        raise ValueError(f"the catalog breaks its rules: {problems[:5]}")
    base = dataset_module.load(BASE_DATASET)
    if not 0 < n <= len(base):
        raise ValueError(f"n must be in 1..{len(base)}, not {n}")
    if paraphraser is None:
        if reuse is not None:
            raise ValueError("reuse keeps paraphrases, so it needs a "
                             "paraphraser")
        model = None
    source = (_reuse_source(reuse, n, seed, model) if reuse is not None
              else None)
    stamp = {"type": "partial", "seed": seed, "model": model,
             "mode": "llm" if paraphraser is not None else "template",
             "generator_sha256": generator_sha256(),
             "reuse_sha256": source.sha256 if source else None}
    earlier = (None if source is None
               else {u["index"]: u for u in source.users})
    # Each user's contradiction question lean, from every script.
    leans = assign_leans([contradiction_slot(i, base.users[i], seed)
                          for i in range(n)])

    def build(i: int) -> dict:
        return build_user(i, base.users[i], seed, paraphraser,
                          reuse=None if earlier is None
                          else earlier.get(i, {}), lean=leans[i])

    partial = out.with_name(out.name + ".partial.jsonl")
    done = _resume(partial, stamp)
    todo = [i for i in range(n) if i not in done]
    lock = threading.Lock()
    with open(partial, "a") as handle:
        def keep(record: dict) -> None:
            with lock:
                handle.write(json.dumps(record) + "\n")
                handle.flush()
                done[record["index"]] = record
            generation = record["generation"]
            logger.info(
                "user %d: %d script attempts, %d paraphrase fallbacks, "
                "%s reused", record["index"],
                generation["script_attempts"],
                len(generation["fallbacks"]),
                generation.get("reused", "none"))

        if workers <= 1:
            for i in todo:
                keep(build(i))
        else:
            _build_parallel(todo, build, workers, keep)
    header = build_header(
        out.stem, n, seed, model, base.sha256, meta,
        reuse=None if source is None else {
            "sha256": source.sha256,
            "revision": revision_of(source.header)})
    tmp = out.with_name(out.name + ".tmp")
    with open(tmp, "w") as handle:
        for record in [header] + [done[i] for i in range(n)]:
            handle.write(json.dumps(record) + "\n")
    os.replace(tmp, out)
    partial.unlink()
    return header


def contradiction_slot(index: int, base_user: dict,
                       seed: int = SEED) -> str:
    """The slot of user ``index``'s contradiction (its script's; the
    lean does not change it)."""
    script, _, _ = draw_script(index, base_user, seed)
    return script["probes"][PROBES.index("contradiction")]["slot"]


def _build_parallel(todo, build, workers, keep) -> None:
    """Build users (``build(i)``) on a thread pool; on the first error,
    cancel the users not started, keep the ones that finish, then
    raise."""
    pool = ThreadPoolExecutor(max_workers=workers)
    error = None
    try:
        futures = [pool.submit(build, i) for i in todo]
        for future in as_completed(futures):
            if future.cancelled():
                continue
            try:
                keep(future.result())
            except Exception as e:  # a user failed: stop the rest
                if error is None:
                    error = e
                    pool.shutdown(wait=False, cancel_futures=True)
    finally:
        pool.shutdown(wait=True)
    if error is not None:
        raise error


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _templates(event: dict) -> List[str]:
    """The template texts the catalog gives an event."""
    slot = SLOTS.get(event.get("slot") or "")
    if slot is None:
        return []
    etype = event["type"]
    if etype == "revoke":
        return [slot.revoke] if slot.revoke else []
    templates = {"add": [slot.add, slot.contradiction_add],
                 "private": [slot.add], "update": [slot.update],
                 "contradict": [slot.contradict]}.get(etype, [])
    templates = [t for t in templates if t]
    if not templates or event.get("value") is None:
        return []
    return [template.format(value=event["value"], species=species)
            for template in templates for species in SPECIES]


def _structure(script_or_record: dict) -> dict:
    """A script without its utterances (what the seed decides)."""
    drop = ("utterance", "paraphrased")
    return {
        "sessions": [
            {"session": s["session"], "writer": s["writer"],
             "events": [{k: v for k, v in e.items() if k not in drop}
                        for e in s["events"]]}
            for s in script_or_record["sessions"]
        ],
        "probes": script_or_record["probes"],
    }


class _Checker:
    """Collects one user's problems."""

    def __init__(self, index):
        self.index = index
        self.problems: List[str] = []

    def __call__(self, ok: bool, message: str) -> bool:
        if not ok:
            self.problems.append(f"user {self.index}: {message}")
        return ok


def validate_user(record: dict, base_user: dict, seed: int = SEED,
                  reproduce: bool = True) -> List[str]:
    """Every rule of docs/BENCHMARK_V2.md a user record must meet, as
    a list of problems (empty when it meets them all). ``base_user``
    is users_v1 user ``index``; with ``reproduce`` the script is drawn
    again and must equal the record's."""
    i = record.get("index")
    check = _Checker(i)
    base = {key: base_user[key] for key in
            ("profile", "task_context", "follow_up_query",
             "plausible_actions")}
    check(record.get("type") == "user", "type is not user")
    check(record.get("base") == base, "base differs from users_v1")
    check(record.get("final") == {"profile": base["profile"],
                                  "task_context": base["task_context"]},
          "final differs from base")
    sessions = record.get("sessions") or []
    if not check([s.get("session") for s in sessions]
                 == list(range(1, SESSIONS + 1)), "sessions are not 1..6"):
        return check.problems
    writers = [s["writer"] for s in sessions]
    check(writers[:3] == list(WRITERS),
          "sessions 1-3 are not profile, task, calendar")
    if not check(sorted(writers[3:]) == sorted(WRITERS),
                 "sessions 4-6 are not a permutation of the writers"):
        return check.problems
    for s in sessions:
        check(MIN_EVENTS <= len(s["events"]) <= MAX_EVENTS,
              f"session {s['session']} holds {len(s['events'])} events")
    first = {w: writers.index(w) + 1 for w in WRITERS}
    second = {w: writers[3:].index(w) + 4 for w in WRITERS}
    events = [e for s in sessions for e in s["events"]]
    where = {e["event_id"]: (s["session"], s["writer"], k)
             for s in sessions for k, e in enumerate(s["events"])}
    by_id = {e["event_id"]: e for e in events}
    check([e["event_id"] for e in events]
          == [f"u{i:03d}-e{k:02d}" for k in range(len(events))],
          "event ids do not follow the script order")
    values = script_values(events)
    ctx = UserContext(base_user)
    _check_base(check, sessions, ctx)
    probes = record.get("probes") or []
    if not check([p.get("type") for p in probes] == list(PROBES),
                 f"probe order is {[p.get('type') for p in probes]}"):
        return check.problems
    probe = {p["type"]: p for p in probes}
    used = _check_roles(check, i, probe, by_id, where, first, second,
                        events)
    _check_probes(check, i, probes, ctx, values)
    _check_others(check, events, where, used)
    _check_utterances(check, events, values,
                      contradiction_events(probes))
    for problem in distinctness_problems(values, ctx):
        check(False, problem)
    generation = record.get("generation") or {}
    attempts = generation.get("script_attempts")
    check(isinstance(attempts, int) and attempts >= 1,
          "generation.script_attempts is missing")
    check(set(generation.get("fallbacks", [])) <= set(by_id),
          "a fallback names an unknown event")
    for event_id in generation.get("fallbacks", []):
        event = by_id.get(event_id, {})
        check(not event.get("paraphrased"),
              f"{event_id} is a fallback but marked paraphrased")
    if reproduce and not check.problems:
        script, again, _ = draw_script(
            i, base_user, seed, probe["contradiction"].get("lean"))
        check(_structure(script) == _structure(record),
              "the seed does not reproduce the script")
        check(again == attempts,
              f"the seed takes {again} attempts, the record {attempts}")
    return check.problems


def _check_base(check: _Checker, sessions: List[dict],
                ctx: UserContext) -> None:
    """The base profile opens session 1 and the base task context
    session 2, as v1's render() of the fields."""
    for session, writer, text in ((1, _P, ctx.base_texts[0]),
                                  (2, _T, ctx.base_texts[1])):
        event = sessions[session - 1]["events"][0]
        check(event["type"] == "base"
              and event["fact_key"] == BASE_FACT_KEYS[writer]
              and event["value"] is None and event["slot"] is None
              and event["utterance"] == event["template"] == text
              and not event["paraphrased"]
              and event["sharing"] == "shared",
              f"session {session} does not open with its base row")
    bases = [e for s in sessions for e in s["events"] if e["type"] == "base"]
    check(len(bases) == 2, f"{len(bases)} base events")


def _check_roles(check, i, probe, by_id, where, first, second,
                 events) -> set:
    """The role facts: owners, slots, placement and links. Returns the
    ids of the events they use."""
    used = set()

    def event(event_id, what):
        e = by_id.get(event_id)
        check(e is not None, f"{what} {event_id!r} is not an event")
        return e or {}

    def owned(role):
        p = probe[PROBE_OF_ROLE[role]]
        slot = SLOTS.get(p.get("slot") or "")
        ok = check(slot is not None and role in slot.roles,
                   f"{role} slot {p.get('slot')!r} cannot play {role}")
        if ok:
            check(slot.writer == role_owner(i, role),
                  f"{role} belongs to {slot.writer}, not "
                  f"{role_owner(i, role)}")
            if role == "contradiction":
                lean = p.get("lean")
                if check(lean in LEANS,
                         f"contradiction lean is {lean!r}"):
                    check(p.get("question")
                          == contradiction_question(slot, lean),
                          f"contradiction question is not the slot's "
                          f"{lean} question")
            else:
                check(p.get("question") == slot.question,
                      f"{role} question is not the slot's")
                check(p.get("lean") is None, f"{role} probe has a lean")
        return p, slot

    def single(entries):
        if len(entries) != 1:
            return None
        return entries[0]["value"], tuple(entries[0]["aliases"])

    # recall
    p, slot = owned("recall")
    add = event(p["target_event"], "recall target")
    used.add(add.get("event_id"))
    if slot:
        check(add.get("type") == "add" and add.get("slot") == slot.name
              and where.get(add["event_id"], (0,))[0] == first[slot.writer],
              "recall add is not its owner's first-session add")
    check(p["source_events"] == [add.get("event_id")]
          and p["forbidden"] == []
          and single(p["expected"]) == (add.get("value"),
                                        tuple(add.get("aliases", ()))),
          "recall probe does not expect its add's value")
    check(p["fact_sentence"] == add.get("template"),
          "recall fact sentence is not the add's template")
    # recency
    p, slot = owned("recency")
    sources = p["source_events"]
    if check(len(sources) == 2, "recency needs an add and an update"):
        add, update = event(sources[0], "recency add"), event(
            sources[1], "recency update")
        used |= {add.get("event_id"), update.get("event_id")}
        if slot:
            check(add.get("type") == "add" and update.get("type")
                  == "update" and add.get("slot") == update.get("slot")
                  == slot.name, "recency events are not an add and an "
                  "update of its slot")
            check(where.get(add.get("event_id"), (0,))[0]
                  == first[slot.writer]
                  and where.get(update.get("event_id"), (0,))[0]
                  == second[slot.writer],
                  "recency add or update is not in its owner's first or "
                  "second session")
            check(p["fact_sentence"] == slot.add.format(
                value=update.get("value"), species="pet"),
                "recency fact sentence is not the add template")
        check(update.get("target_event") == add.get("event_id")
              and update.get("old_value") == add.get("value")
              and update.get("value") != add.get("value"),
              "recency update does not act on its add")
        check(p["target_event"] == update.get("event_id"),
              "recency target is not the update")
        check(single(p["expected"]) == (update.get("value"),
                                        tuple(update.get("aliases", ())))
              and single(p["forbidden"]) == (add.get("value"),
                                             tuple(add.get("aliases", ()))),
              "recency probe does not expect the new value and forbid "
              "the old one")
    # contradiction
    p, slot = owned("contradiction")
    sources = p["source_events"]
    if check(len(sources) == 2, "contradiction needs two statements"):
        original, later = event(sources[0], "original"), event(
            sources[1], "contradiction")
        used |= {original.get("event_id"), later.get("event_id")}
        s_orig, w_orig, _ = where.get(original.get("event_id"), (0, "", 0))
        s_later, w_later, _ = where.get(later.get("event_id"), (0, "", 0))
        if slot:
            check(original.get("type") == "add"
                  and later.get("type") == "contradict"
                  and original.get("slot") == later.get("slot")
                  == slot.name, "contradiction events are not an add and "
                  "a contradict of its slot")
            check(s_orig == first[slot.writer] and w_orig == slot.writer,
                  "original statement is not in its owner's first "
                  "session")
            check(p["fact_sentence"] == original_template(slot).format(
                value=later.get("value"), species="pet"),
                "contradiction fact sentence is not the original "
                "statement's template")
            check(original.get("template") == original_template(
                slot).format(value=original.get("value"), species="pet"),
                "original statement is not the contradiction's add "
                "template")
            for lean, question in zip(LEANS, slot.lean_questions):
                got = lean_of(question, original.get("utterance", ""),
                              later.get("utterance", ""))
                check(got == lean,
                      f"{question!r} leans {got} on the statements, not "
                      f"{lean}")
        check(w_later != w_orig and s_later > s_orig,
              "contradiction is not by another writer in a later session")
        check(later.get("target_event") == original.get("event_id")
              and later.get("old_value") == original.get("value")
              and later.get("value") != original.get("value"),
              "contradiction does not act on the original statement")
        check(p["target_event"] == later.get("event_id"),
              "contradiction target is not the later statement")
        check(single(p["expected"]) == (later.get("value"),
                                        tuple(later.get("aliases", ())))
              and single(p["forbidden"])
              == (original.get("value"),
                  tuple(original.get("aliases", ()))),
              "contradiction probe does not expect the later value and "
              "forbid the earlier one")
    # deletion and the echo
    p, slot = owned("deletion")
    add = event(p["target_event"], "deletion target")
    used.add(add.get("event_id"))
    revokes = [e for e in events if e["type"] == "revoke"]
    check(len(revokes) == 1, f"{len(revokes)} revoke events")
    check(p["source_events"] == [add.get("event_id")]
          and p["expected"] == []
          and single(p["forbidden"]) == (add.get("value"),
                                         tuple(add.get("aliases", ()))),
          "deletion probe does not forbid the revoked value")
    check(p["fact_sentence"] == add.get("template"),
          "deletion fact sentence is not the add's template")
    s_add = where.get(add.get("event_id"), (0,))[0]
    s_revoke = 0
    if slot and revokes:
        revoke = revokes[0]
        used.add(revoke["event_id"])
        s_revoke = where[revoke["event_id"]][0]
        check(add.get("type") == "add" and add.get("slot") == slot.name
              and s_add == first[slot.writer],
              "deleted fact is not added in its owner's first session")
        check(revoke["slot"] == slot.name and revoke["value"] is None
              and revoke["aliases"] == []
              and revoke["old_value"] == add.get("value")
              and revoke["target_event"] == add.get("event_id")
              and revoke["sharing"] is None
              and s_revoke == second[slot.writer],
              "revoke does not act on the deleted fact in its owner's "
              "second session")
    echoes = [e for e in events if e.get("echo_of")]
    if is_echo_user(i):
        if check(len(echoes) == 1 and p["echo_event"]
                 == echoes[0]["event_id"],
                 "an echo user needs exactly one echo, named by the "
                 "deletion probe"):
            echo = echoes[0]
            used.add(echo["event_id"])
            s_echo, w_echo, _ = where[echo["event_id"]]
            echo_def = SLOTS.get(echo["slot"])
            check(echo["type"] == "add"
                  and echo["echo_of"] == echo["target_event"]
                  == add.get("event_id")
                  and echo["value"] == add.get("value")
                  and echo["aliases"] == add.get("aliases"),
                  "echo does not carry its target's value")
            check(echo_def is not None and echo_def.kind == "echo"
                  and slot is not None and echo_def.echo_of == slot.name
                  and echo_def.writer == w_echo,
                  "echo slot does not echo the deleted slot for its writer")
            check(slot is not None and w_echo != slot.writer
                  and s_add < s_echo < s_revoke,
                  "echo is not by another writer between the add and the "
                  "revoke")
    else:
        check(not echoes and p["echo_event"] is None,
              "a user with i mod 9 not in {0, 4, 8} has an echo")
    # privacy
    p, slot = owned("private")
    private = event(p["target_event"], "private target")
    used.add(private.get("event_id"))
    privates = [e for e in events if e["type"] == "private"]
    check(len(privates) == 1, f"{len(privates)} private events")
    check(p["source_events"] == [private.get("event_id")]
          and p["expected"] == []
          and single(p["forbidden"])
          == (private.get("value"), tuple(private.get("aliases", ()))),
          "privacy probe does not forbid the private value")
    check(p["fact_sentence"] == private.get("template"),
          "privacy fact sentence is not the private template")
    if slot:
        session, writer, k = where.get(private.get("event_id"), (0, "", 0))
        size = sum(1 for e in events if where[e["event_id"]][0] == session)
        check(private.get("type") == "private"
              and private.get("sharing") == "private"
              and private.get("slot") == slot.name
              and session == second[slot.writer] and k == size - 1,
              "private event is not the last event of its owner's second "
              "session")
    # every role uses a different slot
    slots = [probe[t]["slot"] for t in PROBES if t != "integration"]
    check(len(set(slots)) == len(slots), f"role slots repeat: {slots}")
    return used


def _check_probes(check, i, probes, ctx, values) -> None:
    """Probe ids, targets, the integration probe, and that no question
    holds a value."""
    for n, p in enumerate(probes, start=1):
        check(p["probe_id"] == f"u{i:03d}-p{n}-{p['type']}",
              f"probe id {p['probe_id']!r}")
        for v in p["expected"] + p["forbidden"]:
            check(match_any(p["question"], v["value"], v["aliases"])
                  is None, f"{p['type']} question names {v['value']!r}")
    integration = probes[-1]
    check(integration["question"] == ctx.query
          and integration["slot"] is None
          and integration["expected"] == integration["forbidden"] == []
          and integration["target_event"] is None
          and integration["fact_sentence"] is None,
          "integration probe is not the follow-up query")
    deleted = probes[0]["forbidden"]
    for p in probes:
        for v in p["expected"]:
            for d in deleted:
                check(not any(collide(a, b) for a in [v["value"],
                                                      *v["aliases"]]
                              for b in [d["value"], *d["aliases"]]),
                      f"{p['type']} expects the revoked value")
    for p in probes:
        for value in values:
            check(match_any(p["question"], *value) is None,
                  f"{p['type']} question names {value[0]!r}")


def _check_others(check, events, where, used) -> None:
    """Every event no role uses is a filler of its session's writer,
    each filler slot once, and private only when private."""
    seen = set()
    for e in events:
        if e["type"] == "base" or e["event_id"] in used:
            continue
        slot = SLOTS.get(e["slot"] or "")
        writer = where[e["event_id"]][1]
        if check(slot is not None and slot.kind == "filler"
                 and slot.writer == writer and e["type"] == "add"
                 and e["target_event"] is None and e["echo_of"] is None
                 and e["old_value"] is None,
                 f"{e['event_id']} is neither a role event nor a filler of "
                 f"{writer}"):
            check(e["slot"] not in seen, f"filler {e['slot']} repeats")
            seen.add(e["slot"])
    for e in events:
        expected = {"private": "private", "revoke": None}.get(e["type"],
                                                              "shared")
        check(e["sharing"] == expected,
              f"{e['event_id']} sharing is {e['sharing']!r}")
        check(e["fact_key"] == (e["slot"] or e["fact_key"]),
              f"{e['event_id']} fact_key is not its slot")


def _check_utterances(check, events, values, statements=()) -> None:
    """Template texts come from the catalog; every utterance keeps its
    own value and names no other (a revoke and a base row name none),
    and still says what its event says (``meaning_problems``; the
    contradiction's ``statements`` with their lean words)."""
    for e in events:
        if e["type"] == "base":
            for value in values:
                check(match_any(e["utterance"], *value) is None,
                      f"base row names {value[0]!r}")
            continue
        check(e["template"] in _templates(e),
              f"{e['event_id']} template is not the catalog's")
        if not e["paraphrased"]:
            check(e["utterance"] == e["template"],
                  f"{e['event_id']} utterance is neither its template nor "
                  "a paraphrase")
        own, others = _own_and_others(e, values)
        role = "contradiction" if e["event_id"] in statements else None
        for problem in paraphrase_problems(e["utterance"], own, others,
                                           e, role):
            check(False, f"{e['event_id']} utterance: {problem}")


def validate_header(header: dict, users: int, limited: bool) -> List[str]:
    """The header's fixed fields (the spec's "File")."""
    problems = []
    expect = {"type": "header", "format_version": FORMAT_VERSION,
              "sessions": SESSIONS, "writers": list(WRITERS),
              "consumer": CONSUMER, "probes": list(PROBES),
              "pilot": dict(PILOT)}
    for key, value in expect.items():
        if header.get(key) != value:
            problems.append(f"header {key} is {header.get(key)!r}, not "
                            f"{value!r}")
    base = dataset_module.load(BASE_DATASET)
    if header.get("base") != {"dataset": BASE_DATASET,
                              "sha256": base.sha256}:
        problems.append(f"header base is {header.get('base')!r}")
    # Revision 1 has no revision field; a later one may name the file
    # its utterances were reused from, of that revision or an earlier
    # one (a rebuild from itself retries its fallbacks).
    revision = revision_of(header)
    if (not isinstance(revision, int) or isinstance(revision, bool)
            or not 1 <= revision <= REVISION):
        problems.append(f"header revision is {revision!r}, not 1 to "
                        f"{REVISION}")
        revision = REVISION
    reuse = header.get("reuse")
    if reuse is not None and not (
            isinstance(reuse, dict) and set(reuse) == {"sha256", "revision"}
            and isinstance(reuse["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", reuse["sha256"])
            and isinstance(reuse["revision"], int)
            and not isinstance(reuse["revision"], bool)
            and 1 <= reuse["revision"] <= revision):
        problems.append(f"header reuse is {reuse!r}, not a sha256 and a "
                        f"revision up to {revision}")
    paraphrase = header.get("paraphrase") or {}
    if paraphrase.get("seed_rule") != PARAPHRASE_SEED_RULE:
        problems.append("header paraphrase seed_rule differs")
    if header.get("script_seed_rule") != SCRIPT_SEED_RULE:
        problems.append("header script_seed_rule differs")
    count = header.get("users")
    if (count != users) if not limited else (count or 0) < users:
        problems.append(f"header users is {count}, the file has {users}")
    return problems


def _spread(numbers: List[int]) -> dict:
    return {"min": min(numbers), "mean": round(sum(numbers)
                                               / len(numbers), 2),
            "max": max(numbers)} if numbers else {}


def summarize(users: List[dict]) -> dict:
    """Counts a reviewer reads before a v2 dataset is used."""
    events = [[e for s in u["sessions"] for e in s["events"]]
              for u in users]
    gen = [u.get("generation", {}) for u in users]
    paraphrasable = sum(1 for es in events for e in es
                        if e["type"] in PARAPHRASED)
    role_writers, role_slots = {}, {}
    for u in users:
        for p in u["probes"]:
            if p["type"] == "integration":
                continue
            slot = SLOTS[p["slot"]]
            role_writers.setdefault(p["type"], Counter())[slot.writer] += 1
            role_slots.setdefault(p["type"], Counter())[slot.name] += 1
    redraws = Counter(re.sub(r"\d+", "N", r) for g in gen
                      for r in g.get("redraws", []))
    pilot_user_4 = next((u for u in users if u["index"] == 4), None)
    return {
        "users": len(users),
        "events_per_user": _spread([len(es) for es in events]),
        "writer_rows_per_user": _spread(
            [sum(e["type"] != "revoke" for e in es) for es in events]),
        "session_sizes": dict(sorted(Counter(
            len(s["events"]) for u in users
            for s in u["sessions"]).items())),
        "script_attempts": dict(sorted(Counter(
            g.get("script_attempts") for g in gen).items())),
        "redraw_reasons": dict(redraws),
        "echo_users": sum(1 for es in events
                          if any(e.get("echo_of") for e in es)),
        "paraphrasable_events": paraphrasable,
        "paraphrased_events": sum(1 for es in events for e in es
                                  if e["paraphrased"]),
        "paraphrase_calls": sum(g.get("paraphrase_calls", 0) for g in gen),
        "fallbacks": sum(len(g.get("fallbacks", [])) for g in gen),
        # Built with reuse (Amendment 2): kept, paraphrased again after
        # failing the checks, or with nothing to reuse.
        "reused_events": sum(g.get("reused", 0) for g in gen),
        "reparaphrased_events": sum(g.get("reparaphrased", 0) for g in gen),
        "unmatched_events": sum(g.get("unmatched", 0) for g in gen),
        "role_writers": {k: dict(sorted(v.items()))
                         for k, v in role_writers.items()},
        "role_slots": {k: dict(sorted(v.items()))
                       for k, v in role_slots.items()},
        "pilot_user_4_private_writer": SLOTS[
            pilot_user_4["probes"][1]["slot"]].writer
        if pilot_user_4 else None,
        # Amendment 3: the contradiction questions by lean.
        "contradiction_leans": lean_counts(users),
    }


def _contradiction_probe(record: dict) -> dict:
    found = [p for p in record.get("probes") or []
             if p.get("type") == "contradiction"]
    return found[0] if len(found) == 1 else {}


def lean_assignment_problems(users: Sequence[dict]) -> List[str]:
    """Why the users' contradiction leans are not ``assign_leans`` of
    their slots, in index order (empty when they are)."""
    probes = [_contradiction_probe(u) for u in users]
    expected = assign_leans([p.get("slot") or "" for p in probes
                             if p.get("slot") in SLOTS])
    got = [p.get("lean") for p in probes if p.get("slot") in SLOTS]
    return [f"user {u['index']}: contradiction lean is {g!r}, the "
            f"assignment gives {e!r}"
            for u, g, e in zip([u for u, p in zip(users, probes)
                                if p.get("slot") in SLOTS], got, expected)
            if g != e]


def lean_counts(users: Sequence[dict]) -> dict:
    """The contradiction questions by lean, in all and per slot."""
    probes = [_contradiction_probe(u) for u in users]
    by_slot: Dict[str, Counter] = {}
    for p in probes:
        by_slot.setdefault(p.get("slot"), Counter())[p.get("lean")] += 1
    total = Counter(p.get("lean") for p in probes)
    return {"all": {lean: total[lean] for lean in LEANS},
            "by_slot": {slot: {lean: c[lean] for lean in LEANS}
                        for slot, c in sorted(by_slot.items(),
                                              key=lambda kv: str(kv[0]))}}


def check(spec: str, reproduce: bool = True) -> dict:
    """Load a v2 dataset (a name or a path), run every validation and
    return ``{"summary": ..., "problems": [...]}``."""
    ds = dataset_module.load(spec)
    if ds is None or ds.version != FORMAT_VERSION:
        raise ValueError(f"{spec} is not a version 2 dataset")
    base = dataset_module.load(BASE_DATASET)
    limited = dataset_module.NAMED.get(spec, (None, None))[1] is not None
    problems = validate_header(ds.header, len(ds.users), limited)
    seed = ds.header.get("seed", SEED)
    for record in ds.users:
        problems.extend(validate_user(record, base.users[record["index"]],
                                      seed, reproduce=reproduce))
    problems.extend(lean_assignment_problems(ds.users))
    summary = {**ds.describe(), "format_version": ds.version,
               "revision": revision_of(ds.header),
               "reuse": ds.header.get("reuse"),
               **summarize(ds.users)}
    summary["generator_sha256_matches"] = (
        ds.header.get("generator_sha256") == generator_sha256())
    summary["consumer_prompt_sha256_matches"] = (
        ds.header.get("consumer_prompt_sha256") == hashlib.sha256(
            consumer_prompt().encode("utf-8")).hexdigest())
    summary["problems"] = len(problems)
    return {"summary": summary, "problems": problems}


def main(argv: Optional[List[str]] = None) -> int:
    """The command line (see the module docstring)."""
    parser = argparse.ArgumentParser(
        prog="python -m benchmarks.shared_memory.synth_v2",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write a v2 dataset")
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument("--n", type=int, default=150)
    gen.add_argument("--seed", type=int, default=SEED)
    gen.add_argument("--model", default=PARAPHRASE_MODEL,
                     help="LiteLLM model of the paraphrases")
    gen.add_argument("--no-paraphrase", action="store_true",
                     help="keep the template text (no network)")
    gen.add_argument("--workers", type=int, default=1,
                     help="users built at the same time")
    gen.add_argument("--reuse", type=Path, default=None,
                     help="an earlier revision (a path or a name) whose "
                          "utterances that pass every check are kept")
    chk = sub.add_parser("check", help="validate a v2 dataset")
    chk.add_argument("dataset", help="users_v2, pilot_v2 or a path")
    args = parser.parse_args(argv)
    if args.command == "generate" and args.reuse and args.no_paraphrase:
        parser.error("--reuse keeps paraphrases; it does not go with "
                     "--no-paraphrase")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "generate":
        paraphraser = (None if args.no_paraphrase
                       else LiteLLMParaphraser(args.model))
        header = generate(args.out, args.n, args.seed, model=args.model,
                          paraphraser=paraphraser, workers=args.workers,
                          reuse=args.reuse)
        print(json.dumps(header, indent=2))
        return 0
    report = check(args.dataset)
    print(json.dumps(report["summary"], indent=2))
    for problem in report["problems"][:200]:
        print(problem)
    if len(report["problems"]) > 200:
        print(f"... {len(report['problems']) - 200} more problems")
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
