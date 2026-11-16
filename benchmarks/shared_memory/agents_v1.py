"""Benchmark v2's agent-count datasets (NeurIPS Subtask 18, AIOS
docs/STRESS_DIMENSIONS.md, "Agent count").

User i of ``agents_n3``, ``agents_n6`` and ``agents_n12`` has exactly
the history of user i of ``users_v2``: the same events, utterances,
sessions and probes. Only the writer of each event changes, so the
store holds the same text at every N (N agents: N - 1 writers and the
consumer). Derived offline, with no LLM call; the paraphrases are
``users_v2``'s.

- **N = 12**: each v2 writer's slots are split among writers by topic
  (``N12``). Every slot's own events (its add, update, revoke or
  private statement) stay with one writer; a contradiction or an echo
  goes to a writer inside the v2 writer that made it, so it stays
  across writers.
- **N = 6** merges the N = 12 writers within each v2 writer (``N6``).
- **N = 3** merges the v2 writers, per user (``n3_writers``): v2
  profile to ``profile_agent``, v2 task to ``task_agent``, and each of
  v2 calendar's units to whichever keeps contradictions and echoes
  across writers; then, where that leaves a choice, away from the
  private fact's writer when the unit comes after the private event;
  then by the user's parity.
- **Memory types** stay the v2 event's.

``python -m benchmarks.shared_memory.agents_v1 generate`` writes the
three files; ``check`` validates them and that they are what this
module derives.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent / "data"
SOURCE = DATA_DIR / "users_v2.jsonl"
LEVELS = (3, 6, 12)
CONSUMER = "assistant_agent"
PILOT = 30
# The most events one writer has in one session, in users_v2 and so at
# every N (a v2 session has 2 to 4 events and one writer).
MAX_SESSION_EVENTS = 4

P, T, C = "profile_agent", "task_agent", "calendar_agent"
V2_WRITERS = (P, T, C)
MEMORY_TYPES = {P: "profile", T: "task_context", C: "calendar"}

# N = 12: per v2 writer, slot (or ("contradict", target slot)) -> writer.
_PROFILE = {
    "base_profile": "profile_agent", "home_city": "profile_agent",
    "pet": "profile_agent", "side_business": "profile_agent",
    "board_game": "profile_agent", "coffee_roaster": "profile_agent",
    "podcast": "profile_agent", "swim_club": "profile_agent",
    "conference_nerves": "profile_agent",
    ("contradict", "conference"): "profile_agent",
    ("contradict", "offsite_city"): "profile_agent",
    "manager": "people_agent", "interview": "people_agent",
    "teammate_lunch": "people_agent",
    ("contradict", "teammate"): "people_agent",
    ("contradict", "one_on_one"): "people_agent",
    "chat_app": "standup_agent", "codename_pride": "standup_agent",
    ("contradict", "client"): "standup_agent",
    "shell": "workstation_agent", "keyboard_layout": "workstation_agent",
    "editor_theme": "workstation_agent",
    "terminal_font": "workstation_agent",
}
_TASK = {
    "base_task": "task_agent", "staging_host": "task_agent",
    "poaching": "task_agent", "ci": "task_agent", "database": "task_agent",
    "secrets_store": "task_agent", "feature_flags": "task_agent",
    "log_platform": "task_agent", "home_city_shipping": "task_agent",
    "pet_groomer": "task_agent",
    ("contradict", "home_city"): "task_agent",
    "codename": "docs_agent", "docs_wiki": "docs_agent",
    "tracker": "docs_agent", "conference_demo": "docs_agent",
    ("contradict", "conference"): "docs_agent",
    "teammate": "code_review_agent", "error_tracker": "code_review_agent",
    "chat_standup": "code_review_agent",
    ("contradict", "one_on_one"): "code_review_agent",
    ("contradict", "offsite_city"): "code_review_agent",
    "client": "project_health_agent", "acquisition": "project_health_agent",
    "manager_signoff": "project_health_agent",
    ("contradict", "manager"): "project_health_agent",
}
_CALENDAR = {
    "sync_room": "calendar_agent", "one_on_one": "calendar_agent",
    "doctor": "calendar_agent", "yoga_studio": "calendar_agent",
    "running_club": "calendar_agent", "choir": "calendar_agent",
    "game_night": "calendar_agent", "chat_retro": "calendar_agent",
    "manager_review": "calendar_agent", "teammate_session": "calendar_agent",
    "codename_review": "calendar_agent",
    ("contradict", "client"): "calendar_agent",
    ("contradict", "teammate"): "calendar_agent",
    ("contradict", "manager"): "calendar_agent",
    "conference": "travel_agent", "offsite_city": "travel_agent",
    "home_city_flight": "travel_agent", "pet_sitter": "travel_agent",
    ("contradict", "home_city"): "travel_agent",
    "lawyer": "expenses_agent", "book_club": "expenses_agent",
    "evening_course": "expenses_agent", "lunch_talk": "expenses_agent",
    "food_bank": "expenses_agent",
}
N12 = {P: _PROFILE, T: _TASK, C: _CALENDAR}
WRITERS = {
    12: ("profile_agent", "people_agent", "standup_agent",
         "workstation_agent", "task_agent", "docs_agent",
         "code_review_agent", "project_health_agent", "calendar_agent",
         "travel_agent", "expenses_agent"),
    6: ("profile_agent", "task_agent", "docs_agent", "calendar_agent",
        "travel_agent"),
    3: ("profile_agent", "task_agent"),
}
# N = 6: the N = 12 writer -> its N = 6 writer.
N6 = {
    "profile_agent": "profile_agent", "people_agent": "profile_agent",
    "standup_agent": "profile_agent", "workstation_agent": "profile_agent",
    "task_agent": "task_agent", "code_review_agent": "task_agent",
    "project_health_agent": "task_agent", "docs_agent": "docs_agent",
    "calendar_agent": "calendar_agent", "expenses_agent": "calendar_agent",
    "travel_agent": "travel_agent",
}
OTHER3 = {"profile_agent": "task_agent", "task_agent": "profile_agent"}
N3_OF_V2 = {P: "profile_agent", T: "task_agent"}


def generator_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _events(user: dict) -> List[Tuple[int, str, int, dict]]:
    """``(session, v2 writer, position, event)`` in script order."""
    return [(s["session"], s["writer"], pos, e)
            for s in user["sessions"] for pos, e in enumerate(s["events"])]


def _key(event: dict) -> Any:
    """The N = 12 map's key for an event."""
    if event["type"] == "base":
        return event["fact_key"]
    if event["type"] == "contradict":
        return ("contradict", event["slot"])
    return event["slot"]


def n12_writer(v2_writer: str, event: dict) -> str:
    try:
        return N12[v2_writer][_key(event)]
    except KeyError:
        raise ValueError(
            f"no N = 12 writer for {event['event_id']} of {v2_writer} "
            f"({_key(event)!r})") from None


def owners(user: dict) -> Dict[str, str]:
    """fact_key -> the v2 writer of its first statement (echoes and
    contradictions are not first statements)."""
    out: Dict[str, str] = {}
    for _, writer, _, event in _events(user):
        if (event["type"] in ("base", "add", "private")
                and not event.get("echo_of")
                and event["fact_key"] not in out):
            out[event["fact_key"]] = writer
    return out


def _unit(event: dict, owner: Dict[str, str]) -> Tuple[str, str]:
    """A calendar event's unit at N = 3: one slot's own events stay
    together; a contradiction and an echo are units of their own."""
    if event["type"] == "contradict":
        return ("contradict", event["event_id"])
    if event.get("echo_of"):
        return ("echo", event["event_id"])
    return ("slot", event["fact_key"])


def n3_writers(user: dict) -> Tuple[Dict[str, str], bool]:
    """event_id -> writer at N = 3, and whether the private fact's
    writer writes again in a later session (``private_not_last``)."""
    events = _events(user)
    by_id = {e["event_id"]: (s, w, e) for s, w, _, e in events}
    owner = owners(user)
    second = {w: max(s for s, ww, _, _ in events if ww == w)
              for w in V2_WRITERS}
    hard: Dict[Tuple[str, str], str] = {}

    def force(unit, writer):
        if hard.get(unit, writer) != writer:
            raise ValueError(f"user {user['index']}: conflicting "
                             f"constraints on {unit}")
        hard[unit] = writer

    for session, writer, _, event in events:
        if event["type"] == "contradict":
            target = owner[event["fact_key"]]
            if writer == C and target != C:
                force(_unit(event, owner), OTHER3[N3_OF_V2[target]])
            if target == C and writer != C:
                force(("slot", event["fact_key"]),
                      OTHER3[N3_OF_V2[writer]])
        if event.get("echo_of"):
            _, _, target_event = by_id[event["echo_of"]]
            target = owner[target_event["fact_key"]]
            if writer == C and target != C:
                force(_unit(event, owner), OTHER3[N3_OF_V2[target]])
            if target == C and writer != C:
                force(("slot", target_event["fact_key"]),
                      OTHER3[N3_OF_V2[writer]])

    (private_session, private_v2, _, private), = [
        (s, w, p, e) for s, w, p, e in events if e["type"] == "private"]
    units: "OrderedDict[Tuple[str, str], List[Tuple[int, dict]]]" = (
        OrderedDict())
    for session, writer, _, event in events:
        if writer == C:
            units.setdefault(_unit(event, owner), []).append(
                (session, event))
    default = "profile_agent" if user["index"] % 2 == 0 else "task_agent"
    if private_v2 == C:
        # The private fact's unit: to a writer with no later session.
        early = [w3 for w3, v2 in (("profile_agent", P), ("task_agent", T))
                 if second[v2] < private_session]
        soft = {("slot", private["fact_key"]): early[0]} if early else {}
        holder = None
    else:
        holder = N3_OF_V2[private_v2]
        soft = {unit: OTHER3[holder] for unit, members in units.items()
                if any(s > private_session for s, _ in members)}
    chosen = {unit: hard.get(unit, soft.get(unit, default))
              for unit in units}
    out = {}
    for session, writer, _, event in events:
        out[event["event_id"]] = (N3_OF_V2[writer] if writer != C
                                  else chosen[_unit(event, owner)])
    return out, private_not_last(
        [(s, out[e["event_id"]], e) for s, _, _, e in events])


def private_not_last(events: List[Tuple[int, str, dict]]) -> bool:
    """Whether the writer of the private fact writes again in a later
    session, over ``(session, writer, event)``: at any N, from the
    writers the events were given."""
    private = [(s, w) for s, w, e in events if e["type"] == "private"]
    return any(later > session and other == writer
               for session, writer in private
               for later, other, _ in events)


def writers_of(user: dict, n: int) -> Tuple[Dict[str, str], bool]:
    """event_id -> its writer at N = ``n``, and ``private_not_last``."""
    if n == 3:
        return n3_writers(user)
    if n not in (6, 12):
        raise ValueError(f"agent count must be one of {LEVELS}")
    out = {}
    events = []
    for session, writer, _, event in _events(user):
        w12 = n12_writer(writer, event)
        out[event["event_id"]] = w12 if n == 12 else N6[w12]
        events.append((session, out[event["event_id"]], event))
    return out, private_not_last(events)


def derive_user(user: dict, n: int) -> dict:
    """User ``user`` of users_v2 at N = ``n``: the same record, with each
    session a list of writer turns (one per writer active in it, in the
    order of each one's first event there), each event's
    ``memory_type`` and ``v2_writer``, and the probes' ``target_writer``
    the target event's new writer."""
    writer_of, not_last = writers_of(user, n)
    sessions = []
    for session in user["sessions"]:
        turns: "OrderedDict[str, List[dict]]" = OrderedDict()
        for event in session["events"]:
            turns.setdefault(writer_of[event["event_id"]], []).append(dict(
                event, memory_type=MEMORY_TYPES[session["writer"]],
                v2_writer=session["writer"],
            ))
        for writer, events in turns.items():
            sessions.append({"session": session["session"],
                             "writer": writer, "events": events})
    probes = []
    for probe in user["probes"]:
        probe = dict(probe)
        if probe.get("target_event"):
            probe["target_writer"] = writer_of[probe["target_event"]]
        probes.append(probe)
    out = dict(user)
    out["sessions"] = sessions
    out["probes"] = probes
    out["agents"] = {"n": n, "private_not_last": not_last}
    return out


def load_source(path: Path = SOURCE) -> Tuple[dict, List[dict], str]:
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()
            if line.strip()]
    return rows[0], rows[1:], hashlib.sha256(raw).hexdigest()


def header_for(source_header: dict, source_sha: str, n: int,
               users: List[dict]) -> dict:
    header = dict(source_header)
    header.update({
        "dataset": f"agents_n{n}",
        "agents": n,
        "writers": list(WRITERS[n]),
        "consumer": CONSUMER,
        "derived_from": {"dataset": "users_v2", "sha256": source_sha,
                         "generator": source_header.get("generator"),
                         "generator_sha256": source_header.get(
                             "generator_sha256")},
        "generator": "benchmarks/shared_memory/agents_v1.py",
        "generator_sha256": generator_sha256(),
        "writer_map": ({"rule": "per user (agents_v1.n3_writers)"}
                       if n == 3 else
                       {v2: {"/".join(k) if isinstance(k, tuple) else k:
                             (w if n == 12 else N6[w])
                             for k, w in mapping.items()}
                        for v2, mapping in N12.items()}),
        "private_not_last": [u["index"] for u in users
                             if u["agents"]["private_not_last"]],
        "pilot": {f"pilot_agents_n{n}": PILOT},
    })
    header.pop("harness_commit", None)
    header.pop("date", None)
    return header


def derive(n: int, path: Path = SOURCE) -> List[dict]:
    """The records of ``agents_n{n}``: header first."""
    source_header, users, sha = load_source(path)
    derived = [derive_user(user, n) for user in users]
    return [header_for(source_header, sha, n, derived)] + derived


def render(records: List[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)


def output_path(n: int) -> Path:
    return DATA_DIR / f"agents_n{n}.jsonl"


def problems(records: List[dict], source_users: List[dict]) -> List[str]:
    """Why a derived file is not what the spec says (empty: none)."""
    header, users = records[0], records[1:]
    n = header["agents"]
    writers = set(header["writers"])
    found: List[str] = []
    if len(users) != len(source_users):
        found.append("user count differs from users_v2")
    for user, source in zip(users, source_users):
        i = user["index"]
        flat = [e for s in user["sessions"] for e in s["events"]]
        strip = ("memory_type", "v2_writer")
        # Each session's events, in script order (event ids follow it;
        # a session's writer turns group them by writer).
        derived = {}
        for s in user["sessions"]:
            derived.setdefault(s["session"], []).extend(
                {k: v for k, v in e.items() if k not in strip}
                for e in s["events"])
        derived = {n: sorted(es, key=lambda e: e["event_id"])
                   for n, es in derived.items()}
        if derived != {s["session"]: s["events"]
                       for s in source["sessions"]}:
            found.append(f"user {i}: events differ from users_v2")
        for s in user["sessions"]:
            ids = [e["event_id"] for e in s["events"]]
            if ids != sorted(ids):
                found.append(f"user {i}: a turn out of script order")
        if [{k: v for k, v in p.items() if k != "target_writer"}
                for p in user["probes"]] != [
                {k: v for k, v in p.items() if k != "target_writer"}
                for p in source["probes"]]:
            found.append(f"user {i}: probes differ from users_v2")
        writer_of = {e["event_id"]: s["writer"] for s in user["sessions"]
                     for e in s["events"]}
        if set(writer_of.values()) - writers:
            found.append(f"user {i}: a writer outside the header's")
        owner = owners(source)
        first_writer: Dict[str, str] = {}
        for s in user["sessions"]:
            per = Counter()
            for e in s["events"]:
                per[s["writer"]] += 1
                if e["type"] in ("base", "add", "update", "revoke",
                                 "private") and not e.get("echo_of"):
                    w = first_writer.setdefault(e["fact_key"], s["writer"])
                    if w != s["writer"]:
                        found.append(f"user {i}: slot {e['fact_key']} has "
                                     "two writers")
            if max(per.values()) > MAX_SESSION_EVENTS:
                found.append(f"user {i}: session {s['session']} gives a "
                             f"writer more than {MAX_SESSION_EVENTS} events")
        for e in flat:
            if e["type"] == "contradict" and (
                    writer_of[e["event_id"]]
                    == first_writer.get(e["fact_key"])):
                found.append(f"user {i}: {e['event_id']} contradicts its "
                             "own writer's fact")
            if e.get("echo_of"):
                target = next(x for x in flat
                              if x["event_id"] == e["echo_of"])
                if writer_of[e["event_id"]] == first_writer.get(
                        target["fact_key"]):
                    found.append(f"user {i}: {e['event_id']} echoes its "
                                 "own writer's fact")
            if e["type"] == "base":
                expected = {"base_profile": "profile_agent",
                            "base_task": "task_agent"}[e["fact_key"]]
                if writer_of[e["event_id"]] != expected:
                    found.append(f"user {i}: {e['fact_key']} moved")
        # Recomputed from the file's own writer turns, not read from
        # its flag.
        not_last = private_not_last([(s["session"], s["writer"], e)
                                     for s in user["sessions"]
                                     for e in s["events"]])
        if not_last != user["agents"]["private_not_last"]:
            found.append(f"user {i}: private_not_last flag is "
                         f"{user['agents']['private_not_last']}, not "
                         f"{not_last}")
        if n in (6, 12) and not_last:
            found.append(f"user {i}: private fact not its writer's last")
        del owner
    return found


def generate(levels=LEVELS) -> None:
    for n in levels:
        records = derive(n)
        output_path(n).write_text(render(records))
        print(f"wrote {output_path(n).name}: {len(records) - 1} users, "
              f"private_not_last {len(records[0]['private_not_last'])}")


def check(levels=LEVELS) -> int:
    _, source_users, _ = load_source()
    bad = 0
    for n in levels:
        path = output_path(n)
        text = path.read_text()
        records = [json.loads(line) for line in text.splitlines()]
        found = problems(records, source_users)
        if text != render(derive(n)):
            found.append("the file is not what agents_v1 derives")
        for problem in found:
            print(f"{path.name}: {problem}")
        bad += len(found)
        print(f"{path.name}: {'ok' if not found else 'PROBLEMS'}")
    return bad


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument("--agents", type=int, nargs="*", default=LEVELS)
    args = parser.parse_args(argv)
    if args.command == "generate":
        generate(args.agents)
        return 0
    return 1 if check(args.agents) else 0


if __name__ == "__main__":
    sys.exit(main())
