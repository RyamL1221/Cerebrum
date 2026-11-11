"""Benchmark v2's generator (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Generation"): determinism, ground truth that
agrees with the script, and the paraphrase rules, including Amendment
2's meaning checks and the revision-2 build that reuses revision 1, and
Amendment 3's contradiction questions of balanced lean (revision 3).

The ground-truth checks re-derive each rule from the script itself
rather than calling the generator's own validator, then also run that
validator on every user. Every paraphraser here is a fake: nothing
calls a network.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from benchmarks.shared_memory import dataset, synth_v2
from benchmarks.shared_memory.probes import match_any, value_in

REPO = Path(__file__).resolve().parents[2]
BASE = dataset.load("users_v1")
WRITERS = ("profile_agent", "task_agent", "calendar_agent")
ROLES = ("recall", "recency", "contradiction", "deletion", "privacy")
# The contradict templates Amendment 2 rewrote, and revision 1's text.
OLD_CONTRADICT = {
    "conference": "The conference I'm presenting at is {value}.",
    "one_on_one": "My weekly one-on-one is with {value}.",
    "teammate": "My pairing partner is {value}.",
}


@pytest.fixture(scope="module")
def users():
    """All 150 users in template mode (no network)."""
    return [synth_v2.build_user(i, BASE.users[i]) for i in range(150)]


def events_of(user):
    return [e for s in user["sessions"] for e in s["events"]]


def session_of(user, event_id):
    for s in user["sessions"]:
        for e in s["events"]:
            if e["event_id"] == event_id:
                return s
    raise KeyError(event_id)


def probe(user, kind):
    (found,) = [p for p in user["probes"] if p["type"] == kind]
    return found


def values(entries):
    return [e["value"] for e in entries]


# -- determinism ----------------------------------------------------------

def test_the_same_seed_gives_the_same_scripts(users):
    again = [synth_v2.build_user(i, BASE.users[i]) for i in range(150)]
    assert again == users
    other = synth_v2.build_user(0, BASE.users[0], seed=synth_v2.SEED + 1)
    assert other["sessions"] != users[0]["sessions"]


def test_template_generation_is_byte_identical(tmp_path):
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    synth_v2.generate(first, n=6)
    synth_v2.generate(second, n=6)
    a = first.read_text().splitlines()
    b = second.read_text().splitlines()
    assert a[1:] == b[1:]  # the users; the header names its path
    assert json.loads(a[0])["users"] == 6


def test_scripts_do_not_depend_on_the_hash_seed():
    code = ("import json; from benchmarks.shared_memory import dataset, "
            "synth_v2; b = dataset.load('users_v1'); print(json.dumps("
            "[synth_v2.build_user(i, b.users[i]) for i in range(4)]))")
    outputs = []
    for hash_seed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed)
        done = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                              env=env, capture_output=True, text=True,
                              timeout=300)
        assert done.returncode == 0, done.stderr[-2000:]
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1]


# -- ground truth ---------------------------------------------------------

def test_every_user_passes_the_generators_own_validation(users):
    problems = [p for i, u in enumerate(users)
                for p in synth_v2.validate_user(u, BASE.users[i])]
    assert problems == []


def test_sessions_and_writers_follow_the_layout(users):
    for user in users:
        sessions = user["sessions"]
        assert [s["session"] for s in sessions] == [1, 2, 3, 4, 5, 6]
        assert [s["writer"] for s in sessions[:3]] == list(WRITERS)
        assert sorted(s["writer"] for s in sessions[3:]) == sorted(WRITERS)
        for s in sessions:
            assert 2 <= len(s["events"]) <= 4
        types = [e["type"] for e in events_of(user)]
        assert types.count("base") == 2
        assert [e["fact_key"] for e in sessions[0]["events"]][0] == \
            "base_profile"
        assert [e["fact_key"] for e in sessions[1]["events"]][0] == \
            "base_task"
        assert [p["type"] for p in user["probes"]] == [
            "deletion", "privacy", "recall", "recency", "contradiction",
            "integration"]


def test_roles_belong_to_the_rotating_writer(users):
    for i, user in enumerate(users):
        for k, role in enumerate(ROLES):
            p = probe(user, role)
            want = WRITERS[(i + k) % 3]
            if role == "contradiction":
                # The role's owner states it first; another contradicts.
                first = [e for e in events_of(user)
                         if e["fact_key"] == p["slot"]
                         and e["type"] == "add"]
                assert session_of(user, first[0]["event_id"])[
                    "writer"] == want
            else:
                assert p["target_writer"] == want, (i, role)
    assert probe(users[4], "privacy")["target_writer"] == "calendar_agent"


def test_a_revoked_value_is_never_expected(users):
    for user in users:
        deletion = probe(user, "deletion")
        revoked = set(values(deletion["forbidden"]))
        assert len(revoked) == 1
        for p in user["probes"]:
            assert not revoked & set(values(p["expected"]))
        revokes = [e for e in events_of(user) if e["type"] == "revoke"]
        assert len(revokes) == 1
        assert revokes[0]["fact_key"] == deletion["slot"]
        adds = [e for e in events_of(user)
                if e["fact_key"] == deletion["slot"] and e["type"] == "add"]
        assert values(deletion["forbidden"]) == [adds[0]["value"]]
        # The add is in the owner's first session, the revoke after it.
        add_s = session_of(user, adds[0]["event_id"])
        rev_s = session_of(user, revokes[0]["event_id"])
        assert add_s["writer"] == rev_s["writer"]
        assert add_s["session"] <= 3 < rev_s["session"]


def test_a_contradicted_value_is_forbidden_and_the_later_one_expected(users):
    for user in users:
        p = probe(user, "contradiction")
        stated = [e for e in events_of(user) if e["fact_key"] == p["slot"]
                  and e["type"] in ("add", "contradict")]
        first, later = stated[0], stated[-1]
        assert (first["type"], later["type"]) == ("add", "contradict")
        assert values(p["forbidden"]) == [first["value"]]
        assert values(p["expected"]) == [later["value"]]
        assert later["target_event"] == first["event_id"]
        s_first = session_of(user, first["event_id"])
        s_later = session_of(user, later["event_id"])
        assert s_first["writer"] != s_later["writer"]
        assert s_first["session"] < s_later["session"]


def test_an_updated_value_is_forbidden_and_the_new_one_expected(users):
    for user in users:
        p = probe(user, "recency")
        stated = [e for e in events_of(user) if e["fact_key"] == p["slot"]
                  and e["type"] in ("add", "update")]
        old, new = stated[0], stated[-1]
        assert (old["type"], new["type"]) == ("add", "update")
        assert values(p["forbidden"]) == [old["value"]]
        assert values(p["expected"]) == [new["value"]]
        assert new["old_value"] == old["value"]
        # The update states only the new value.
        assert not match_any(new["utterance"], old["value"], old["aliases"])
        assert session_of(user, old["event_id"])["writer"] == \
            session_of(user, new["event_id"])["writer"]


def test_a_private_fact_is_forbidden_and_written_last(users):
    for user in users:
        p = probe(user, "privacy")
        (private,) = [e for e in events_of(user) if e["type"] == "private"]
        assert private["sharing"] == "private"
        assert values(p["forbidden"]) == [private["value"]]
        session = session_of(user, private["event_id"])
        assert session["session"] >= 4
        assert session["events"][-1]["event_id"] == private["event_id"]


def test_the_recall_fact_is_never_changed(users):
    for user in users:
        p = probe(user, "recall")
        changes = [e for e in events_of(user) if e["fact_key"] == p["slot"]
                   and e["type"] in ("update", "contradict", "revoke")]
        assert changes == []
        assert values(p["expected"]) and not p["forbidden"]


def test_echoes_carry_the_revoked_value_between_add_and_revoke(users):
    for i, user in enumerate(users):
        echoes = [e for e in events_of(user) if e.get("echo_of")]
        deletion = probe(user, "deletion")
        assert bool(echoes) == (i % 9 in (0, 4, 8)), i
        if not echoes:
            assert deletion["echo_event"] is None
            continue
        (echo,) = echoes
        assert deletion["echo_event"] == echo["event_id"]
        assert echo["value"] == deletion["forbidden"][0]["value"]
        assert value_in(echo["utterance"], echo["value"])
        add = next(e for e in events_of(user)
                   if e["event_id"] == echo["echo_of"])
        revoke = next(e for e in events_of(user) if e["type"] == "revoke")
        s_echo = session_of(user, echo["event_id"])
        assert s_echo["writer"] != session_of(user, add["event_id"])[
            "writer"]
        order = [e["event_id"] for e in events_of(user)]
        assert order.index(add["event_id"]) < order.index(
            echo["event_id"]) < order.index(revoke["event_id"])


def test_questions_and_revokes_name_no_value(users):
    for user in users:
        entries = [(e["value"], e["aliases"]) for e in events_of(user)
                   if e.get("value")]
        for p in user["probes"]:
            for value, aliases in entries:
                assert not match_any(p["question"], value, aliases), (
                    p["question"], value)
        (revoke,) = [e for e in events_of(user) if e["type"] == "revoke"]
        for value, aliases in entries:
            assert not match_any(revoke["utterance"], value, aliases)


def test_values_are_distinct_under_the_matcher(users):
    for user in users:
        facts = {}
        for e in events_of(user):
            if e.get("value") and not e.get("echo_of"):
                facts.setdefault(e["value"], set(e["aliases"]))
        forms = [(v, f) for v, aliases in facts.items()
                 for f in [v, *aliases]]
        for value, form in forms:
            for other, other_form in forms:
                if other != value:
                    assert not value_in(other_form, form), (form, other)
        name_tokens = user["base"]["profile"]["user_name"].split()
        for _, form in forms:
            for token in name_tokens:
                assert not value_in(token, form)
                assert not value_in(form, token)


# -- paraphrase -----------------------------------------------------------

def scripted(answers):
    """A paraphraser that answers from ``answers(request)``."""
    calls = []

    def paraphrase(request):
        calls.append(request)
        return answers(request)
    paraphrase.calls = calls
    return paraphrase


def test_a_good_paraphrase_is_kept():
    para = scripted(lambda r: "Honestly, " + r.text)
    user = synth_v2.build_user(0, BASE.users[0], paraphraser=para)
    kept = [e for e in events_of(user) if e["type"] == "add"]
    assert all(e["paraphrased"] for e in kept)
    assert kept[0]["utterance"] == "Honestly, " + kept[0]["template"]
    bases = [e for e in events_of(user) if e["type"] == "base"]
    assert not any(e["paraphrased"] for e in bases)
    assert user["generation"]["fallbacks"] == []


def test_a_paraphrase_without_its_value_is_retried_then_falls_back():
    para = scripted(lambda r: "I mentioned something earlier.")
    user = synth_v2.build_user(0, BASE.users[0], paraphraser=para)
    adds = [e for e in events_of(user) if e["type"] == "add"]
    assert not any(e["paraphrased"] for e in adds)
    assert all(e["utterance"] == e["template"] for e in adds)
    assert adds[0]["event_id"] in user["generation"]["fallbacks"]
    attempts = user["generation"]["paraphrase_attempts"]
    assert attempts[adds[0]["event_id"]] == synth_v2.PARAPHRASE_RETRIES + 1
    # Each retry gets a fresh seed and the reason it was rejected.
    retries = [c for c in para.calls if c.text == adds[0]["template"]]
    assert len({c.seed for c in retries}) == len(retries)
    assert retries[1].feedback and "does not contain" in retries[1].feedback


def test_a_paraphrase_naming_another_fact_or_too_long_is_rejected():
    user0 = synth_v2.build_user(0, BASE.users[0])
    values_ = [(e["value"], tuple(e["aliases"])) for e in events_of(user0)
               if e.get("value")]
    own, other = values_[0], values_[1]
    assert synth_v2.paraphrase_problems(
        f"About {own[0]}.", own, [other]) == []
    assert synth_v2.paraphrase_problems(
        f"About {own[0]} and {other[0]}.", own, [other])
    long = " ".join(["word"] * 41) + f" {own[0]}"
    assert synth_v2.paraphrase_problems(long, own, [other])
    # A revoke must name no value at all.
    assert synth_v2.paraphrase_problems(
        f"Forget {own[0]}.", None, [own, other])
    assert synth_v2.paraphrase_problems(
        "Please forget my pet's name.", None, [own, other]) == []


def test_an_echo_paraphrase_must_keep_the_revoked_value():
    i = 0  # an echo user
    user = synth_v2.build_user(i, BASE.users[i])
    (echo,) = [e for e in events_of(user) if e.get("echo_of")]

    def answers(request):
        if request.text == echo["template"]:
            return "I booked something for my pet."  # drops the value
        return request.text
    para = scripted(answers)
    again = synth_v2.build_user(i, BASE.users[i], paraphraser=para)
    (echo2,) = [e for e in events_of(again) if e.get("echo_of")]
    assert echo2["paraphrased"] is False
    assert echo2["utterance"] == echo2["template"]
    assert echo2["event_id"] in again["generation"]["fallbacks"]


def test_the_header_records_the_seed_and_rules(tmp_path):
    out = tmp_path / "v2.jsonl"
    header = synth_v2.generate(out, n=3)
    for key in ("format_version", "seed", "sessions", "writers", "probes",
                "base", "paraphrase", "generator_sha256", "pilot"):
        assert key in header
    assert header["format_version"] == 2 and header["seed"] == 20261108
    assert header["pilot"] == {"pilot_v2": 30}
    assert header["base"]["sha256"] == BASE.sha256


# -- meaning checks (Amendment 2, "Generation") ---------------------------

def catalog_template(slot, etype):
    """The catalog's template of ``slot`` for an event type."""
    definition = synth_v2.SLOTS[slot]
    return definition.add if etype in ("add", "private") else getattr(
        definition, etype)


def problems_of(slot, etype, value, text, aliases=()):
    """``paraphrase_problems`` of ``text`` as an utterance of an event
    of ``slot`` (its template filled with ``value``)."""
    template = catalog_template(slot, etype).format(value=value or "",
                                                    species="dog")
    own = None if value is None else (value, tuple(aliases))
    event = {"type": etype, "slot": slot, "template": template}
    return synth_v2.paraphrase_problems(text, own, [], event)


TOPIC = "it must still say what the fact is about: "
ONLY = "it must still say this is the only one ('only')"
# Real revision-1 utterances (users_v2.jsonl, sha256 768a37ac...), the
# amendment's own example, and events of the types revision 1 never got
# wrong.
LOST_MEANING = {
    "conference contradict (Amendment 2)": (
        "conference", "contradict", "Fjordstack",
        "I'm giving a presentation at Fjordstack.", ONLY),
    "conference contradict (u003-e13)": (
        "conference", "contradict", "Fjordstack",
        "I'm giving a presentation at the Fjordstack conference.", ONLY),
    "one-on-one contradict (u000-e11)": (
        "one_on_one", "contradict", "Sofia Lindqvist",
        "I have a weekly one-on-one scheduled with Sofia Lindqvist.", ONLY),
    "teammate contradict (u005-e17)": (
        "teammate", "contradict", "Freya Holmberg",
        "The person I'm paired with is Freya Holmberg.", ONLY),
    "client contradict (u014-e08)": (
        "client", "contradict", "Ravelstone Security",
        "The company I'm working with on my project is Ravelstone "
        "Security.", "it must still say client"),
    "teammate add (u001-e05)": (
        "teammate", "add", "Jonas Albrecht",
        "I'm collaborating with Jonas Albrecht on this project.",
        TOPIC + "use 'pairing'"),
    "teammate revoke (u004-e20)": (
        "teammate", "revoke", None,
        "Kindly erase from memory the person I'm teaming up with.",
        TOPIC + "use 'pairing'"),
    "lawyer private (u004-e12)": (
        "lawyer", "private", "Ewan Calloway",
        "Keep this private: I'm scheduled to meet with Ewan Calloway next "
        "month.", TOPIC + "use 'lawyer'"),
    "codename add (u001-e07)": (
        "codename", "add", "Kittiwake",
        "Privately, we refer to the project as Kittiwake.",
        "it marks a shared fact as private ('privately'); drop that"),
    "update without a change word": (
        "sync_room", "update", "Larch",
        "Our weekly team sync is in the Larch room.",
        "it must still say the fact changed: use 'moved'"),
    "revoke without a forget word": (
        "pet", "revoke", None, "I'd rather you didn't keep my pet's name.",
        "it must still ask to forget it: use 'forget'"),
    "private fact without a marker": (
        "doctor", "private", "Okafor",
        "I have a follow-up appointment with Dr. Okafor.",
        "it must still say this is private: use 'private'"),
    "echo marked private": (
        "teammate_session", "add", "Greta Sandvik",
        "Confidentially, I have a pairing session with Greta Sandvik this "
        "week.",
        "it marks a shared fact as private ('confidentially'); drop that"),
    # No false privacy on any shared event type of a role slot.
    "update marked private": (
        "home_city", "update", "Ghent", "Privately, I've moved to Ghent.",
        "it marks a shared fact as private ('privately'); drop that"),
    "contradict marked private": (
        "manager", "contradict", "Dana Whitfield",
        "Confidentially, my manager is Dana Whitfield.",
        "it marks a shared fact as private ('confidentially'); drop that"),
    "revoke marked private": (
        "pet", "revoke", None, "Please secretly forget my pet's name.",
        "it marks a shared fact as private ('secretly'); drop that"),
}


@pytest.mark.parametrize("slot, etype, value, text, problem",
                         LOST_MEANING.values(), ids=LOST_MEANING.keys())
def test_a_paraphrase_that_no_longer_says_its_fact_is_rejected(
        slot, etype, value, text, problem):
    assert problem in problems_of(slot, etype, value, text)


KEPT_MEANING = {
    "conference contradict": (
        "conference", "contradict", "Fjordstack",
        "Fjordstack is the only conference where I'm giving a talk."),
    "one-on-one contradict": (
        "one_on_one", "contradict", "Sofia Lindqvist",
        "Sofia Lindqvist is the only person I have a weekly 1:1 with."),
    "teammate contradict": (
        "teammate", "contradict", "Freya Holmberg",
        "Freya Holmberg is my sole pairing partner on this project."),
    "client contradict": (
        "client", "contradict", "Ravelstone Security",
        "Ravelstone Security is the client for my project."),
    "teammate add": (
        "teammate", "add", "Jonas Albrecht",
        "Jonas Albrecht and I are paired up on this project."),
    "teammate revoke": (
        "teammate", "revoke", None,
        "Kindly erase from memory the person I'm pairing with."),
    "lawyer private": (
        "lawyer", "private", "Ewan Calloway",
        "Keep this private: I'm meeting my attorney, Ewan Calloway, next "
        "month."),
    "codename add": (
        "codename", "add", "Kittiwake",
        "We refer to the project as Kittiwake internally."),
    "update": (
        "sync_room", "update", "Larch",
        "Our weekly team sync is now in the Larch room."),
    "private doctor": (
        "doctor", "private", "Okafor",
        "Just between us, I'm seeing Dr. Okafor for a follow-up."),
    "echo": (
        "teammate_session", "add", "Greta Sandvik",
        "This week I've got a pairing session with Greta Sandvik."),
    # Fillers are exempt: the secrets store's own template says secrets.
    "filler": (
        "secrets_store", "add", "Doppler", "Our secrets are kept in Doppler."),
}


@pytest.mark.parametrize("slot, etype, value, text", KEPT_MEANING.values(),
                         ids=KEPT_MEANING.keys())
def test_a_paraphrase_that_keeps_its_meaning_is_accepted(slot, etype,
                                                         value, text):
    assert problems_of(slot, etype, value, text) == []


def test_without_an_event_paraphrase_problems_checks_what_it_did_before():
    text = "Privately, we refer to the project as Kittiwake."
    own = ("Kittiwake", ())
    assert synth_v2.paraphrase_problems(text, own, []) == []
    assert synth_v2.paraphrase_problems(
        text, own, [], {"type": "add", "slot": "codename",
                        "template": "Internally we call the project "
                                    "Kittiwake."}) == [
        "it marks a shared fact as private ('privately'); drop that"]


@pytest.mark.parametrize("cue, text, hit", [
    ("pair*", "We paired up last week.", True),
    ("pair*", "I'm pairing with Jonas.", True),
    ("pair*", "I repaired the laptop.", False),
    ("for", "We build it for Kestrel.", True),
    ("for", "Before the launch, the form was due.", False),
    ("one on one", "My weekly one-on-one is with Dana.", True),
    ("1:1", "My weekly 1:1 is with Dana.", True),
    ("dr", "I see Dr. Okafor on Monday.", True),
    ("dr", "I drive to the office.", False),
    ("code name*", "The project is code-named Basalt.", True),
    ("off the record", "Off the record: they're hiring.", True),
    ("only", "It's the one I'm presenting at.", False),
])
def test_a_cue_matches_whole_words_and_a_star_matches_any_ending(cue, text,
                                                                 hit):
    assert synth_v2.has_cue(text, (cue,)) is hit


def cues(text):
    return tuple(text.split(", "))


AMENDMENT_2_CUES = {
    "home_city": "live, lives, living, home, reside*, based, move*, "
                 "relocat*",
    "chat_app": "chat*, messag*, communicat*",
    "pet": "pet, pets, dog, cat, parrot, rabbit, ferret",
    "manager": "manager, report*, boss, supervisor, manag*",
    "interview": "interview*",
    "side_business": "startup*, start up, side, business, venture",
    "client": "client*, customer*, for",
    "codename": "codename*, code name*, call*, refer*, name*, known as, "
                "internally",
    "teammate": "pair*",
    "staging_host": "staging, stage",
    "acquisition": "acqui*, buy*, bought, purchas*, merg*, takeover",
    "poaching": "hire*, hiring, recruit*, poach*, lure*, team lead, "
                "headhunt*",
    "sync_room": "sync*, meeting*",
    "conference": "conference*, present*, talk*, speak*, keynote",
    "one_on_one": "one on one, 1 on 1, 1:1, one to one",
    "offsite_city": "offsite*, off site, retreat*",
    "doctor": "dr, doctor*, appointment*, physician*, medical, clinic*",
    "lawyer": "lawyer*, attorney*, legal, counsel*, solicitor*",
}


def test_the_catalog_carries_the_amendment_2_cues_and_templates():
    only = cues("only, sole, single, just one, no other, exclusively")
    # Exactly the role and private slots carry cues, these ones.
    assert {s.name: s.cues for s in synth_v2.CATALOG if s.cues} == {
        name: cues(text) for name, text in AMENDMENT_2_CUES.items()}
    assert {s.name for s in synth_v2.CATALOG if s.cues} == {
        s.name for s in synth_v2.CATALOG if s.kind in ("role", "private")}
    conflict = {s.name: s.conflict for s in synth_v2.CATALOG if s.conflict}
    assert conflict == {"conference": only, "one_on_one": only,
                        "teammate": only,
                        "client": ("client*", "customer*")}
    assert synth_v2.CHANGE_WORDS == cues(
        "move*, switch*, chang*, relocat*, now, new, transfer*, shift*, "
        "replac*, instead, no longer")
    assert synth_v2.FORGET_WORDS == cues(
        "forget*, delet*, remov*, eras*, drop*, discard*, wipe*, clear*, "
        "purg*")
    assert synth_v2.PRIVATE_MARKERS == cues(
        "private, privately, confidential*, between us, off the record, "
        "to yourself, secret*, discreet*")
    contradict = {s.name: s.contradict for s in synth_v2.CATALOG
                  if s.name in OLD_CONTRADICT}
    # Amendment 3 changed the one-on-one template again (its lean).
    assert contradict == {
        "conference": "The only conference I'm presenting at is {value}.",
        "one_on_one": "My only standing one-on-one is with {value}.",
        "teammate": "My only pairing partner on this project is {value}.",
    }


def test_every_catalog_template_passes_every_check_of_its_event_type():
    assert synth_v2.catalog_problems() == []
    for slot in synth_v2.CATALOG:
        if slot.kind == "private":
            templates = {"private": slot.add}
        else:
            templates = {"add": slot.add, "update": slot.update,
                         "contradict": slot.contradict,
                         "revoke": slot.revoke}
        pool = (synth_v2.SLOTS[slot.echo_of].pool if slot.kind == "echo"
                else slot.pool)
        for etype, template in templates.items():
            if template is None:
                continue
            for value, aliases in ([(None, ())] if etype == "revoke"
                                   else synth_v2.POOLS[pool]):
                for species in synth_v2.SPECIES:
                    text = template.format(value=value, species=species)
                    own = None if value is None else (value, aliases)
                    event = {"type": etype, "slot": slot.name,
                             "template": text}
                    assert synth_v2.paraphrase_problems(
                        text, own, [], event) == [], (slot.name, text)


def test_no_pool_value_states_a_cue_of_its_slot_by_itself():
    # Two forms name the topic by design: "Dr. <surname>" says doctor,
    # and Rocket.Chat's name says chat. Any other value that matched
    # would let a paraphrase pass a check on the value alone.
    allowed = {("chat_app", "Rocket.Chat")} | {
        ("doctor", f"Dr. {value}") for value, _ in synth_v2.POOLS["doctors"]}
    lists = (synth_v2.ONLY_WORDS, synth_v2.CHANGE_WORDS,
             synth_v2.FORGET_WORDS, synth_v2.PRIVATE_MARKERS)
    for slot in synth_v2.CATALOG:
        if slot.kind not in ("role", "private"):
            continue
        for value, aliases in synth_v2.POOLS[slot.pool]:
            for form in (value, *aliases):
                said = any(synth_v2.has_cue(form, c)
                           for c in (slot.cues, slot.conflict) + lists)
                assert not said or (slot.name, form) in allowed, (slot, form)


def test_a_paraphrase_that_drops_its_topic_is_retried_with_the_words_to_use():
    user = synth_v2.build_user(4, BASE.users[4])
    (add,) = [e for e in events_of(user)
              if e["slot"] == "teammate" and e["type"] == "add"]

    def answers(request):
        if request.text == add["template"] and request.attempt == 0:
            return request.text.replace("pairing", "collaborating")
        return request.text
    para = scripted(answers)
    again = synth_v2.build_user(4, BASE.users[4], paraphraser=para)
    calls = [c for c in para.calls if c.text == add["template"]]
    assert [c.attempt for c in calls] == [0, 1]
    assert calls[1].feedback == TOPIC + "use 'pairing'"
    (kept,) = [e for e in events_of(again) if e["event_id"] ==
               add["event_id"]]
    assert kept["utterance"] == add["template"] and kept["paraphrased"]


# Revision 1's utterances of user 4 (pilot user 4, the spec's H = 2
# privacy case) that lost what their fact is about.
REVISION_1_USER_4 = {
    "u004-e03": "I'm collaborating with Greta Sandvik for this project.",
    "u004-e12": "Keep this private: I'm scheduled to meet with Ewan "
                "Calloway next month.",
    "u004-e20": "Kindly erase from memory the person I'm teaming up with.",
}


def test_the_dataset_check_reports_utterances_that_no_longer_say_their_fact():
    user = synth_v2.build_user(4, BASE.users[4])
    for e in events_of(user):
        if e["event_id"] in REVISION_1_USER_4:
            e["utterance"] = REVISION_1_USER_4[e["event_id"]]
            e["paraphrased"] = True
    assert synth_v2.validate_user(user, BASE.users[4], reproduce=False) == [
        f"user 4: u004-e03 utterance: {TOPIC}use 'pairing'",
        f"user 4: u004-e12 utterance: {TOPIC}use 'lawyer'",
        f"user 4: u004-e20 utterance: {TOPIC}use 'pairing'",
    ]


def test_the_paraphrase_prompt_asks_to_keep_what_the_fact_says():
    request = synth_v2.ParaphraseRequest(
        text="I'm pairing with Jonas Albrecht on this project.",
        event_type="add", keep=("Jonas Albrecht",), seed=1, attempt=0)
    system = synth_v2.paraphrase_messages(request)[0]["content"]
    for rule in ("keep the words that say what the fact is about",
                 'keep the word "only"', "that a fact changed",
                 "keep a request to forget something",
                 "do not call a fact private, confidential or secret "
                 "unless the sentence does"):
        assert rule in system


def test_the_scripts_of_users_0_to_4_match_the_committed_users_v2():
    # Read only: every revision keeps revision 1's scripts (Amendments 2
    # and 3); the committed file is built by this generator, its
    # contradiction questions by their recorded lean.
    committed = dataset.load("users_v2")
    keys = ("event_id", "type", "slot", "fact_key", "value", "aliases",
            "old_value", "target_event", "echo_of", "sharing")

    def script(user):
        return [(s["session"], s["writer"],
                 [[e[k] for k in keys] for e in s["events"]])
                for s in user["sessions"]]
    for i in range(5):
        stored = committed.users[i]
        drawn = synth_v2.build_user(
            i, BASE.users[i], lean=probe(stored, "contradiction")["lean"])
        assert script(drawn) == script(stored), i
        assert drawn["probes"] == stored["probes"], i
        for new, old in zip(events_of(drawn), events_of(stored)):
            assert new["template"] == old["template"], new["event_id"]


# -- revision 2: reuse of an earlier revision -----------------------------

def read_jsonl(path):
    lines = [json.loads(x) for x in Path(path).read_text().splitlines()]
    return lines[0], lines[1:]


def write_jsonl(path, header, users):
    Path(path).write_text("".join(json.dumps(r) + "\n"
                                  for r in [header] + users))


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frankly(request):
    """A paraphraser whose answers pass every check."""
    return "Frankly, " + request.text


def paraphrasable(user):
    return [(k, e) for k, e in enumerate(events_of(user))
            if e["type"] in synth_v2.PARAPHRASED]


@pytest.fixture
def earlier(tmp_path):
    """A paraphrased two-user file shaped like revision 1: its header
    has no revision field."""
    path = tmp_path / "revision1.jsonl"
    synth_v2.generate(path, n=2, model="fake/model",
                      paraphraser=scripted(
                          lambda r: "Honestly, " + r.text))
    header, users = read_jsonl(path)
    del header["revision"]
    write_jsonl(path, header, users)
    return path


def rebuild(earlier, tmp_path, para, n=2):
    """Revision 2 built from ``earlier``; its users."""
    out = tmp_path / "revision2.jsonl"
    synth_v2.generate(out, n=n, model="fake/model", paraphraser=para,
                      reuse=earlier)
    return read_jsonl(out)[1]


def role_add(user):
    """The position and event of the user's first add of a role slot."""
    return next((k, e) for k, e in enumerate(events_of(user))
                if e["type"] == "add"
                and synth_v2.SLOTS[e["slot"]].kind == "role")


def test_reuse_keeps_a_passing_utterance_byte_for_byte_without_a_call(
        earlier, tmp_path):
    header, users = read_jsonl(earlier)
    # A fresh paraphrase is stripped, so trailing spaces show the text
    # is the stored one, byte for byte.
    paraphrasable(users[0])[0][1]["utterance"] += "  "
    write_jsonl(earlier, header, users)
    para = scripted(frankly)
    again = rebuild(earlier, tmp_path, para)
    assert para.calls == []
    for old, new in zip(users, again):
        assert [e["utterance"] for e in events_of(new)] == [
            e["utterance"] for e in events_of(old)]
        generation = new["generation"]
        assert generation["reused"] == len(paraphrasable(old))
        assert generation["reparaphrased"] == generation["unmatched"] == 0
        assert generation["paraphrase_calls"] == 0


def test_reuse_retries_a_failing_utterance_from_attempt_1_with_it_as_previous(
        earlier, tmp_path):
    header, users = read_jsonl(earlier)
    position, event = role_add(users[0])
    failing = "Privately, " + event["template"]
    event["utterance"] = failing
    write_jsonl(earlier, header, users)
    para = scripted(frankly)
    again = rebuild(earlier, tmp_path, para)
    (call,) = para.calls
    assert (call.text, call.attempt, call.previous) == (
        event["template"], 1, failing)
    assert call.feedback == ("it marks a shared fact as private "
                             "('privately'); drop that")
    assert call.seed == synth_v2.paraphrase_seed(synth_v2.SEED, 1, 0,
                                                 position)
    new = events_of(again[0])[position]
    assert new["utterance"] == "Frankly, " + event["template"]
    assert new["paraphrased"]
    generation = again[0]["generation"]
    assert generation["reparaphrased"] == 1
    assert generation["unmatched"] == 0
    assert generation["paraphrase_calls"] == 1
    assert generation["paraphrase_attempts"][event["event_id"]] == 2
    assert generation["rejections"][event["event_id"]] == [call.feedback]


def test_a_reused_failure_that_keeps_failing_falls_back_after_four_attempts(
        earlier, tmp_path):
    header, users = read_jsonl(earlier)
    position, event = role_add(users[0])
    event["utterance"] = "Privately, " + event["template"]
    write_jsonl(earlier, header, users)
    para = scripted(lambda r: "I mentioned something earlier.")
    again = rebuild(earlier, tmp_path, para)
    assert [c.attempt for c in para.calls] == [1, 2, 3]
    new = events_of(again[0])[position]
    assert new["utterance"] == new["template"] and not new["paraphrased"]
    generation = again[0]["generation"]
    assert generation["fallbacks"] == [event["event_id"]]
    assert generation["paraphrase_attempts"][event["event_id"]] == \
        synth_v2.PARAPHRASE_RETRIES + 1
    assert len(generation["rejections"][event["event_id"]]) == \
        synth_v2.PARAPHRASE_RETRIES + 1


def test_reuse_paraphrases_a_changed_template_from_attempt_0(earlier,
                                                             tmp_path):
    header, users = read_jsonl(earlier)
    # User 0 contradicts its weekly one-on-one; revision 1 had the old
    # template and an utterance that does not conflict.
    position, event = next((k, e) for k, e in enumerate(events_of(users[0]))
                           if e["type"] == "contradict")
    assert event["slot"] == "one_on_one"
    event["template"] = OLD_CONTRADICT["one_on_one"].format(
        value=event["value"])
    event["utterance"] = ("I have a weekly one-on-one scheduled with "
                          f"{event['value']}.")
    write_jsonl(earlier, header, users)
    para = scripted(frankly)
    again = rebuild(earlier, tmp_path, para)
    (call,) = para.calls
    assert call.text == synth_v2.SLOTS["one_on_one"].contradict.format(
        value=event["value"])
    assert (call.attempt, call.previous, call.feedback) == (0, None, None)
    assert call.seed == synth_v2.paraphrase_seed(synth_v2.SEED, 0, 0,
                                                 position)
    assert events_of(again[0])[position]["utterance"] == "Frankly, " + \
        call.text
    assert again[0]["generation"]["unmatched"] == 1


@pytest.mark.parametrize("key, change", [
    ("value", lambda e: "Otherplace"),
    ("aliases", lambda e: list(e["aliases"]) + ["Otherplace"]),
    ("type", lambda e: "update"),
    ("slot", lambda e: "pet"),
])
def test_reuse_needs_every_key_of_the_event_to_be_equal(
        earlier, tmp_path, key, change):
    """An earlier utterance is reused only for the same type, slot,
    template, value and aliases (``REUSE_KEYS``): one key changed and
    the event is paraphrased from attempt 0."""
    header, users = read_jsonl(earlier)
    position, event = role_add(users[0])
    event[key] = change(event)  # template and utterance kept
    write_jsonl(earlier, header, users)
    para = scripted(frankly)
    again = rebuild(earlier, tmp_path, para)
    (call,) = para.calls
    assert (call.attempt, call.previous, call.feedback) == (0, None, None)
    assert again[0]["generation"]["unmatched"] == 1
    assert set(synth_v2.REUSE_KEYS) == {"type", "slot", "template",
                                        "value", "aliases"}


@pytest.mark.parametrize("how, match", [
    ("fewer users", "fewer than the 3"),
    ("another seed", "seed"),
    ("another model", "model"),
    ("part of a file", "reuse the whole file"),
])
def test_reuse_refuses_a_source_this_run_could_not_have_produced(
        earlier, tmp_path, monkeypatch, how, match):
    """A reused utterance must be one this run could have produced, from
    a whole file: a limited name would leave the users past its limit
    to be paraphrased again, silently, under the file's sha256."""
    options = {"n": 2, "seed": synth_v2.SEED, "model": "fake/model",
               "reuse": earlier}
    if how == "fewer users":
        options["n"] = 3
    elif how == "another seed":
        options["seed"] = synth_v2.SEED + 1
    elif how == "another model":
        options["model"] = "other/model"
    else:
        # A name for the file's first user, as pilot_v2 is for
        # users_v2 (an absolute path joins past DATA_DIR).
        monkeypatch.setitem(synth_v2.dataset_module.NAMED, "part",
                            (str(earlier), 1))
        options.update(n=1, reuse="part")
    with pytest.raises(ValueError, match=match):
        synth_v2.generate(tmp_path / "out.jsonl",
                          paraphraser=scripted(frankly), **options)


def test_a_partial_file_from_another_reuse_source_is_refused(earlier,
                                                             tmp_path):
    """A resumed run cannot mix two reuse sources: the partial file's
    stamp names the one it was built from."""
    out = tmp_path / "out.jsonl"
    partial = out.with_name(out.name + ".partial.jsonl")
    stamp = {"type": "partial", "seed": synth_v2.SEED,
             "model": "fake/model", "mode": "llm",
             "generator_sha256": synth_v2.generator_sha256(),
             "reuse_sha256": "0" * 64}
    partial.write_text(json.dumps(stamp) + "\n")
    with pytest.raises(ValueError, match="other settings"):
        synth_v2.generate(out, n=2, model="fake/model",
                          paraphraser=scripted(frankly), reuse=earlier)


def test_generate_refuses_a_catalog_that_breaks_its_own_rules(
        tmp_path, monkeypatch):
    monkeypatch.setattr(synth_v2, "catalog_problems",
                        lambda: ["home_city add: a template problem"])
    with pytest.raises(ValueError, match="breaks its rules"):
        synth_v2.generate(tmp_path / "x.jsonl", n=1)


def test_build_user_refuses_another_users_record_to_reuse(earlier):
    _, users = read_jsonl(earlier)
    with pytest.raises(ValueError, match="reused user 1 is not user 0"):
        synth_v2.build_user(0, BASE.users[0], paraphraser=scripted(frankly),
                            reuse=users[1])


def test_parallel_workers_write_what_one_worker_writes(earlier, tmp_path):
    """``--workers`` builds users on a thread pool; the records it writes
    are the ones a single worker writes."""
    files = {}
    for workers in (1, 2):
        out = tmp_path / f"workers{workers}.jsonl"
        synth_v2.generate(out, n=2, model="fake/model",
                          paraphraser=scripted(frankly), reuse=earlier,
                          workers=workers)
        files[workers] = read_jsonl(out)[1]
    assert files[1] == files[2]
    assert [u["index"] for u in files[2]] == [0, 1]


def test_reuse_paraphrases_an_earlier_fallback_from_attempt_0(earlier,
                                                              tmp_path):
    header, users = read_jsonl(earlier)
    position, event = role_add(users[0])
    event["utterance"], event["paraphrased"] = event["template"], False
    write_jsonl(earlier, header, users)
    para = scripted(frankly)
    again = rebuild(earlier, tmp_path, para)
    (call,) = para.calls
    assert (call.text, call.attempt) == (event["template"], 0)
    assert events_of(again[0])[position]["paraphrased"]
    assert again[0]["generation"]["unmatched"] == 1


def test_reuse_needs_a_paraphraser(earlier, tmp_path):
    with pytest.raises(ValueError, match="needs a paraphraser"):
        synth_v2.generate(tmp_path / "x.jsonl", n=1, reuse=earlier)
    with pytest.raises(SystemExit):
        synth_v2.main(["generate", "--out", str(tmp_path / "y.jsonl"),
                       "--no-paraphrase", "--reuse", str(earlier)])


def test_the_cli_passes_reuse_to_generate(earlier, tmp_path, monkeypatch):
    para = scripted(frankly)
    monkeypatch.setattr(synth_v2, "LiteLLMParaphraser", lambda model: para)
    out = tmp_path / "cli.jsonl"
    assert synth_v2.main(["generate", "--out", str(out), "--n", "2",
                          "--model", "fake/model",
                          "--reuse", str(earlier)]) == 0
    header, _ = read_jsonl(out)
    assert header["reuse"] == {"sha256": sha256_of(earlier), "revision": 1}
    assert para.calls == []


def test_the_header_records_revision_3_and_the_file_it_reused(earlier,
                                                              tmp_path):
    fresh = synth_v2.generate(tmp_path / "fresh.jsonl", n=1)
    assert fresh["revision"] == synth_v2.REVISION == 3
    assert "reuse" not in fresh
    out = tmp_path / "revision3.jsonl"
    header = synth_v2.generate(out, n=2, model="fake/model",
                               paraphraser=scripted(frankly), reuse=earlier)
    assert header["revision"] == 3
    assert header["reuse"] == {"sha256": sha256_of(earlier), "revision": 1}
    assert synth_v2.validate_header(fresh, 1, limited=False) == []
    assert synth_v2.validate_header(header, 2, limited=False) == []
    # check reads both revisions; a rebuild from revision 2 is allowed.
    old, new = synth_v2.check(str(earlier)), synth_v2.check(str(out))
    assert old["problems"] == new["problems"] == []
    assert (old["summary"]["revision"], new["summary"]["revision"]) == (1, 3)
    assert new["summary"]["reuse"] == header["reuse"]
    assert new["summary"]["reused_events"] == sum(
        len(paraphrasable(u)) for u in read_jsonl(earlier)[1])
    again = synth_v2.generate(tmp_path / "again.jsonl", n=2,
                              model="fake/model",
                              paraphraser=scripted(frankly), reuse=out)
    assert again["reuse"] == {"sha256": sha256_of(out), "revision": 3}
    assert synth_v2.validate_header(again, 2, limited=False) == []


@pytest.mark.parametrize("change", [
    {"revision": 4}, {"revision": "2"}, {"revision": True},
    {"reuse": {"sha256": "abc", "revision": 1}},
    {"reuse": {"sha256": "0" * 64}},
    {"reuse": {"sha256": "0" * 64, "revision": 4}},
    {"revision": 1, "reuse": {"sha256": "0" * 64, "revision": 2}},
], ids=["future", "text", "bool", "short sha", "no revision", "newer",
        "newer than the file"])
def test_validate_header_rejects_a_malformed_revision_or_reuse(change,
                                                               tmp_path):
    header = synth_v2.generate(tmp_path / "v2.jsonl", n=1)
    assert synth_v2.validate_header(
        dict(header, reuse={"sha256": "0" * 64, "revision": 1}), 1,
        limited=False) == []
    assert synth_v2.validate_header(dict(header, **change), 1,
                                    limited=False)


# -- revision 3: the contradiction questions' lean (Amendment 3) ----------

CONTRADICTION_SLOTS = [s for s in synth_v2.CATALOG if s.lean_questions]
REVISION_2_SHA256 = ("35f68c78a8373a0354c549f4e4755266b889042b76d3735963"
                     "eaefbc922426de")


def test_the_lean_counts_content_words_as_written_and_by_family():
    assert synth_v2.content_words("I'm presenting at Kernelcon.") == [
        "presenting", "kernelcon"]
    question = "Which conference am I presenting at?"
    earlier = "Next month, I'll be giving a presentation at Kernelcon."
    later = "Fjordstack is the only conference where I'm presenting."
    # "presenting" is in the later statement only, as written; by
    # family ("presentation") it is in both.
    assert synth_v2.lean_score(question, earlier, later, "exact") == -2
    assert synth_v2.lean_score(question, earlier, later, "family") == -1
    assert synth_v2.lean_of(question, earlier, later) == "later"
    # A tie, and rules that disagree, give no lean.
    assert synth_v2.lean_of("Who do I report to?", "I report to Ana.",
                            "Bo is who I report to.") is None
    assert synth_v2.lean_of("Who do I meet every week?",
                            "I meet Ana weekly.", "Bo is who I meet.") is None


def test_each_contradiction_slot_has_a_question_of_each_lean():
    assert {s.name for s in CONTRADICTION_SLOTS} == {
        s.name for s in synth_v2.CATALOG if "contradiction" in s.roles}
    for slot in CONTRADICTION_SLOTS:
        earlier = synth_v2.original_template(slot).format(
            value="Ana Lind", species="pet")
        later = slot.contradict.format(value="Bo Vale", species="pet")
        assert [synth_v2.lean_of(q, earlier, later)
                for q in slot.lean_questions] == list(synth_v2.LEANS), \
            slot.name


def test_leans_alternate_within_each_slot_and_balance_both_files(users):
    slots = [probe(u, "contradiction")["slot"] for u in users]
    leans = synth_v2.assign_leans(slots)
    # pilot_v2 gets the leans it would get alone.
    assert synth_v2.assign_leans(slots[:30]) == leans[:30]
    for n in (150, 30):
        assert Counter(leans[:n]) == {"earlier": n // 2, "later": n // 2}
        for name in set(slots[:n]):
            mine = [lean for slot, lean in zip(slots[:n], leans[:n])
                    if slot == name]
            assert all(a != b for a, b in zip(mine, mine[1:])), name


@pytest.mark.parametrize("text, problems", [
    ("Leuven is where I live.", []),
    ("My home is in Leuven.", ["it must keep the words 'live'"]),
    ("I live in Leuven, the city I'm based in.",
     ["it must not use the words 'based', 'city'"]),
])
def test_a_contradiction_statement_keeps_exactly_its_templates_lean_words(
        text, problems):
    slot = synth_v2.SLOTS["home_city"]
    assert synth_v2.lean_problems(text, "I live in Leuven.", slot) == \
        problems
    event = {"type": "add", "slot": "home_city",
             "template": "I live in Leuven."}
    assert synth_v2.meaning_problems(text, event, "contradiction") == \
        problems
    # Other adds of the slot (recall, deletion) are not held to it.
    assert synth_v2.meaning_problems(text, event) == []


def test_the_paraphraser_hears_which_words_to_keep_and_avoid():
    user = synth_v2.build_user(0, BASE.users[0])
    para = scripted(lambda r: r.text)
    synth_v2.paraphrase_script(user, 0, synth_v2.SEED, para)
    statements = set(synth_v2.contradiction_events(user["probes"]))
    events = [e for e in events_of(user)
              if e["type"] in synth_v2.PARAPHRASED]
    assert len(para.calls) == len(events) and len(statements) == 2
    for event, call in zip(events, para.calls):
        if event["event_id"] in statements:
            slot = synth_v2.SLOTS[event["slot"]]
            assert (call.keep_words, call.avoid_words) == \
                synth_v2.lean_targets(event["template"], slot)
            assert call.keep_words and call.avoid_words
            content = synth_v2.paraphrase_messages(call)[1]["content"]
            assert ("KEEP THESE WORDS AS WRITTEN: "
                    + ", ".join(call.keep_words)) in content
            assert ("DO NOT USE THESE WORDS: "
                    + ", ".join(call.avoid_words)) in content
        else:
            assert (call.keep_words, call.avoid_words) == ((), ())
            assert synth_v2.paraphrase_messages(call)[1]["content"] == (
                f"Sentence: {call.text}\nKEEP: "
                + (", ".join(call.keep) if call.keep
                   else "(nothing; name no specific value)"))


def test_check_reports_a_statement_that_changes_a_questions_lean():
    user = synth_v2.build_user(0, BASE.users[0])
    assert synth_v2.validate_user(user, BASE.users[0]) == []
    broken = copy.deepcopy(user)
    original = next(e for e in events_of(broken) if e["event_id"]
                    == synth_v2.contradiction_events(broken["probes"])[0])
    assert original["slot"] == "one_on_one"
    original["utterance"] = (f"I meet {original['value']} for our standing "
                             "one-on-one every week.")
    original["paraphrased"] = True
    problems = synth_v2.validate_user(broken, BASE.users[0])
    assert any("must not use the words 'standing'" in p for p in problems)
    assert any("leans None on the statements, not later" in p
               for p in problems)


def test_check_reports_a_lean_off_the_assignment():
    slots = [synth_v2.contradiction_slot(i, BASE.users[i]) for i in range(6)]
    leans = synth_v2.assign_leans(slots)
    users = [synth_v2.build_user(i, BASE.users[i], lean=lean)
             for i, lean in enumerate(leans)]
    assert synth_v2.lean_assignment_problems(users) == []
    flipped = synth_v2.LEANS[1 - synth_v2.LEANS.index(leans[3])]
    users[3] = synth_v2.build_user(3, BASE.users[3], lean=flipped)
    # The user alone is valid: its question is its lean's.
    assert synth_v2.validate_user(users[3], BASE.users[3]) == []
    assert synth_v2.lean_assignment_problems(users) == [
        f"user 3: contradiction lean is {flipped!r}, the assignment gives "
        f"{leans[3]!r}"]


def test_the_committed_users_v2_is_revision_3_with_balanced_leans():
    committed = dataset.load("users_v2")
    assert committed.header["revision"] == 3
    assert committed.header["reuse"] == {"sha256": REVISION_2_SHA256,
                                         "revision": 2}
    counts = synth_v2.lean_counts(committed.users)
    assert counts["all"] == {"earlier": 75, "later": 75}
    assert synth_v2.lean_counts(committed.users[:30])["all"] == {
        "earlier": 15, "later": 15}
    for name, by_lean in counts["by_slot"].items():
        assert abs(by_lean["earlier"] - by_lean["later"]) <= 1, name
    for user in committed.users:
        p = probe(user, "contradiction")
        by_id = {e["event_id"]: e for e in events_of(user)}
        earlier, later = (by_id[x]["utterance"] for x in p["source_events"])
        slot = synth_v2.SLOTS[p["slot"]]
        assert [synth_v2.lean_of(q, earlier, later)
                for q in slot.lean_questions] == list(synth_v2.LEANS)
        assert p["question"] == slot.lean_questions[
            synth_v2.LEANS.index(p["lean"])]
    assert synth_v2.check("users_v2")["problems"] == []


def test_the_committed_users_v2_was_built_by_this_generator():
    """The header names the generator that built the file by its
    SHA-256 (``generator_sha256``: ``synth_v2.py``, catalog and pools
    included), so the rules revision 3 was built under, and the counts
    its build reports (calls, fallbacks, reused statements), are this
    file's. An edit to ``synth_v2.py`` needs a new revision."""
    committed = dataset.load("users_v2")
    assert committed.header["generator_sha256"] == (
        synth_v2.generator_sha256())


@pytest.mark.parametrize("slot, side, text, rejected", [
    # The paraphrases of revision 3's first build that kept their words
    # and lost what they said, and forms that keep it.
    ("home_city", "later", "My work is based in Bologna.", True),
    ("home_city", "later", "My location is based in Bologna.", False),
    ("client", "earlier",
     "We're creating this building project for Lumenvale.", True),
    ("client", "earlier", "We are building a project for Westmere Foods.",
     True),
    ("client", "earlier",
     "This project we're building is for Westmere Foods.", False),
    ("client", "later",
     "Fenwick Freight is the client for the project I'm working on.",
     False),
    ("manager", "earlier", "I am under Elif Kaya's report.", True),
    ("manager", "earlier", "Elif Kaya is the person I report to.", False),
    ("manager", "later", "Elif Kaya is the name of my manager.", False),
])
def test_a_contradiction_statement_keeps_its_slots_meaning(slot, side, text,
                                                           rejected):
    problems = synth_v2.lean_meaning_problems(text, synth_v2.SLOTS[slot],
                                              side)
    assert bool(problems) is rejected, problems
    template = (synth_v2.original_template(synth_v2.SLOTS[slot])
                if side == "earlier" else synth_v2.SLOTS[slot].contradict)
    event = {"type": "add" if side == "earlier" else "contradict",
             "slot": slot, "template": template.format(value="Elif Kaya")}
    # Through the paraphrase check, for a contradiction statement only.
    if rejected:
        assert set(problems) <= set(synth_v2.meaning_problems(
            text, event, "contradiction"))
        assert not set(problems) & set(synth_v2.meaning_problems(text,
                                                                 event))
