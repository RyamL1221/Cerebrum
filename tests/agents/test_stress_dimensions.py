"""The stress dimensions' harness (NeurIPS Subtask 18, AIOS
docs/STRESS_DIMENSIONS.md): the agent-count datasets, the N-agent
heterogeneity schedule and the faulty agent's schedule, the writers'
flood rows and timing records, the history's writer turns, concurrent
sessions and kernel sessions, the thread-safe create capture, the
stress measures, the orchestrator's flags and the pre-flight's quota
check. No kernel and no model is reached."""
import importlib
import json
import threading
import time
from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.shared_memory import agents_v1, dataset, history, stress
from benchmarks.shared_memory import run_evaluation
from benchmarks.shared_memory.models import SessionRecord
from benchmarks.shared_memory.pipeline import VariantRunner
from cerebrum.example.agents import shared_memory_utils as smu
from cerebrum.example.agents.variants import base as variant_base
from cerebrum.example.agents.variants import faults
from cerebrum.utils import communication
from tests.agents.test_history_v2 import (
    FakeConsumer,
    FakeLocus,
    FakeWriter,
    Store,
    v2_user,
)
from tests.agents.test_v2_preflight import kernel_config

schedule_module = importlib.import_module(
    "cerebrum.example.agents.variants.schedule")
SEED = 20261106


# -- the agent-count datasets ---------------------------------------------

def test_the_committed_files_are_what_agents_v1_derives():
    assert agents_v1.check() == 0


@pytest.mark.parametrize("n", agents_v1.LEVELS)
def test_each_level_keeps_users_v2s_facts_over_its_writers(n):
    """The same events, utterances, sessions and probes as users_v2, a
    slot's own events with one writer, contradictions and echoes across
    writers, at most 4 events per writer and session; the private fact
    is its writer's last but for the N = 3 users the header names."""
    records = [json.loads(line) for line in
               agents_v1.output_path(n).read_text().splitlines()]
    _, source, sha = agents_v1.load_source()
    header, users = records[0], records[1:]
    assert agents_v1.problems(records, source) == []
    assert header["derived_from"]["sha256"] == sha
    assert header["generator_sha256"] == agents_v1.generator_sha256()
    assert header["writers"] == list(agents_v1.WRITERS[n])
    expected = {3: 32, 6: 0, 12: 0}[n]
    assert len(header["private_not_last"]) == expected
    writing = Counter(turn["writer"] for user in users
                      for turn in user["sessions"])
    assert set(writing) == set(header["writers"])  # every writer writes


@pytest.mark.parametrize("n", [6, 12])
def test_the_check_finds_a_private_fact_its_writer_writes_after(n):
    """At N = 6 and 12 a private fact is its writer's last; the check
    reads that from the file's own writer turns, not from its flag."""
    records = [json.loads(line) for line in
               agents_v1.output_path(n).read_text().splitlines()]
    _, source_users, _ = agents_v1.load_source()
    assert agents_v1.problems(records, source_users) == []
    for user in records[1:]:
        session, writer = next((s["session"], s["writer"])
                               for s in user["sessions"]
                               for e in s["events"]
                               if e["type"] == "private")
        later = [s for s in user["sessions"] if s["session"] > session]
        if later:
            later[0]["writer"] = writer  # the writer writes again
            break
    found = agents_v1.problems(records, source_users)
    assert any("private fact not its writer's last" in f for f in found)


def test_each_finer_writer_lies_inside_one_v2_writer():
    """So a contradiction or an echo, across v2 writers, stays across
    writers at N = 6 and N = 12: every N = 12 writer takes slots of one
    v2 writer only, and every N = 6 writer merges N = 12 writers of one
    v2 writer only."""
    v2_of = {}
    for v2, mapping in agents_v1.N12.items():
        for writer in mapping.values():
            assert v2_of.setdefault(writer, v2) == v2, writer
    assert set(v2_of) == set(agents_v1.WRITERS[12])
    merged = {}
    for writer, n6 in agents_v1.N6.items():
        assert merged.setdefault(n6, v2_of[writer]) == v2_of[writer], n6
    assert set(merged) == set(agents_v1.WRITERS[6])


def test_a_derived_user_runs_as_writer_turns():
    data = dataset.load(dataset.with_agents("pilot_v2", 12))
    user = data.user_v2(0, "r")
    assert user.writers == list(agents_v1.WRITERS[12])
    groups = history.session_groups(user)
    assert [number for number, _ in groups] == [1, 2, 3, 4, 5, 6]
    assert sum(len(turns) for _, turns in groups) == len(user.sessions)
    assert dataset.with_agents("users_v2", 4) == "users_v2"
    with pytest.raises(ValueError):
        dataset.with_agents("pilot_v1", 6)


def tiny_user(index):
    """A v2 user of four sessions: profile's base and its private fact
    (session 4), task's base, and one calendar slot written before the
    private event, which no contradiction, echo or private fact
    constrains: at N = 3 only the user's parity decides its writer."""
    def event(event_id, kind, key):
        return {"event_id": event_id, "type": kind, "fact_key": key,
                "slot": key, "echo_of": None}

    return {"index": index, "probes": [], "sessions": [
        {"session": 1, "writer": "profile_agent",
         "events": [event("e0", "base", "base_profile")]},
        {"session": 2, "writer": "task_agent",
         "events": [event("e1", "base", "base_task")]},
        {"session": 3, "writer": "calendar_agent",
         "events": [event("e2", "add", "yoga_studio")]},
        {"session": 4, "writer": "profile_agent",
         "events": [event("e3", "private", "side_business")]},
    ]}


def test_n3_gives_a_free_calendar_unit_to_the_users_parity_writer():
    """STRESS_DIMENSIONS.md, Agent count, N = 3 (lines 106-113): a v2
    calendar unit the constraints leave free goes "to profile_agent for
    even i and to task_agent for odd i"."""
    writer_of, _ = agents_v1.n3_writers(tiny_user(0))
    assert writer_of["e2"] == "profile_agent"
    writer_of, _ = agents_v1.n3_writers(tiny_user(1))
    assert writer_of["e2"] == "task_agent"


V2_MEMORY_TYPES = {"profile_agent": "profile", "task_agent": "task_context",
                   "calendar_agent": "calendar"}


@pytest.mark.parametrize("n", agents_v1.LEVELS)
def test_each_derived_event_keeps_its_v2_writers_memory_type(n):
    """STRESS_DIMENSIONS.md, Agent count (lines 124-127): "Memory types
    stay the v2 event's (profile, task_context, calendar), whoever
    writes it." Read from the derivation itself, so it holds whatever
    data files were generated."""
    _, source, _ = agents_v1.load_source()
    for user in source[:30]:
        v2_writer = {e["event_id"]: s["writer"] for s in user["sessions"]
                     for e in s["events"]}
        derived = agents_v1.derive_user(user, n)
        assert {e["event_id"]: (e["v2_writer"], e["memory_type"])
                for turn in derived["sessions"] for e in turn["events"]} \
            == {i: (w, V2_MEMORY_TYPES[w]) for i, w in v2_writer.items()}


@pytest.mark.parametrize("n", agents_v1.LEVELS)
def test_a_sessions_writer_turns_follow_each_writers_first_event(n):
    """STRESS_DIMENSIONS.md, Agent count, Datasets (lines 134-136): "A
    session of a derived user is a list of writer turns, one per writer
    active in it, in the order of each writer's first event there.\""""
    _, source, _ = agents_v1.load_source()
    for user in source[:30]:
        writer_of, _ = agents_v1.writers_of(user, n)
        expected = [(s["session"], w) for s in user["sessions"]
                    for w in dict.fromkeys(writer_of[e["event_id"]]
                                           for e in s["events"])]
        derived = agents_v1.derive_user(user, n)
        assert [(t["session"], t["writer"])
                for t in derived["sessions"]] == expected


# -- schedules -----------------------------------------------------------

def test_the_n_agent_schedule_is_the_heterogeneity_schedule_at_three():
    for level in (0, 1, 2):
        for i in range(45):
            assert schedule_module.schedule_for(
                SEED, level, i, variant_base.AGENTS
            ) == schedule_module.schedule(SEED, level, i)


@pytest.mark.parametrize("n", (6, 12))
def test_h_deviates_a_fraction_of_n_agents(n):
    agents = tuple(agents_v1.WRITERS[n]) + ("assistant_agent",)
    for level, share in ((1, 1 / 3), (2, 2 / 3)):
        seen = Counter()
        for i in range(5 * n):
            chosen = schedule_module.schedule_for(SEED, level, i, agents)
            assert len(chosen) == round(share * n)
            assert set(chosen) <= set(agents)
            assert schedule_module.schedule_for(SEED, level, i,
                                                agents) == chosen
            seen.update(chosen.keys())
        assert set(seen) == set(agents)  # every agent deviates somewhere
    assert schedule_module.schedule_for(SEED, 0, 3, agents) == {}


def test_the_faulty_agent_rotates_over_its_candidates():
    candidates = ["profile_agent", "task_agent", "docs_agent"]
    picked = [faults.faulty_agent(7, "flood10", i, candidates)
              for i in range(6)]
    assert picked[:3] == picked[3:] and set(picked) == set(candidates)
    assert faults.faulty_agent(7, "flood10", 0, candidates) == \
        faults.faulty_agent(7, "flood10", 0, list(candidates))
    assert faults.faulty_agent(7, "none", 0, candidates) is None
    with pytest.raises(ValueError):
        faults.faulty_agent(7, "wrong_user", 0, [])


def test_the_fault_variants():
    wrong = faults.fault_variant("wrong_user", "victim")
    assert wrong.user_id("me") == "victim" and wrong.has("identity", "writer")
    flood = faults.fault_variant("flood50")
    assert flood.flood_rows() == 50 and flood.code == "flood50"
    assert faults.fault_variant("missing_metadata").code == "V3"
    assert faults.fault_variant("none") is None
    with pytest.raises(ValueError):
        faults.fault_variant("wrong_user")  # needs a victim


def test_a_flooding_writer_runs_with_its_rows_and_no_quota_of_its_own():
    """In the replicated locus the flooder's pipeline is rebuilt without
    the quota (it does not enforce one on itself) over the same
    provider, barrier, resolver, tombstones and usage tag; every locus
    gets its flood_rows; all of it is undone after the run."""
    import dataclasses

    @dataclasses.dataclass(frozen=True)
    class Settings:
        write_quota: dict

    class Pipeline:
        def __init__(self, provider, settings, **kwargs):
            self.provider, self.settings = provider, settings
            self.quota = kwargs.pop("quota", "own")
            self.__dict__.update(kwargs)

    pipeline = Pipeline("provider", Settings({"enabled": True,
                                              "max_writes": 4}),
                        barrier="b", resolver="r", tombstones="t",
                        usage_tag="u")
    agent = SimpleNamespace(memory=SimpleNamespace(
        pipeline=pipeline, library=SimpleNamespace(MemoryPipeline=Pipeline)),
        user_id="u")
    with variant_base.apply_variant(faults.fault_variant("flood10"), agent,
                                    "travel_agent", "replicated"):
        unquoted = agent.memory.pipeline
        assert agent.flood_rows == 10 and unquoted.quota is None
        assert unquoted.settings.write_quota == {"enabled": False,
                                                 "max_writes": 4}
        assert (unquoted.provider, unquoted.barrier, unquoted.resolver,
                unquoted.tombstones, unquoted.usage_tag) == (
            "provider", "b", "r", "t", "u")
    assert agent.memory.pipeline is pipeline
    assert not hasattr(agent, "flood_rows")
    kernel_agent = SimpleNamespace(user_id="u")
    with variant_base.apply_variant(faults.fault_variant("flood50"),
                                    kernel_agent, "docs_agent", "kernel"):
        assert kernel_agent.flood_rows == 50


def test_the_new_writers_are_writers_to_the_variants():
    for name in agents_v1.WRITERS[12]:
        assert variant_base.role_of(name) == "writer"
    assert set(agents_v1.WRITERS[12]) <= set(variant_base.KNOWN_WRITERS)


# -- the writer's session: flood rows and timing --------------------------

class WriteLog:
    def __init__(self):
        self.writes = []

    def write(self, content, metadata):
        self.writes.append((content, dict(metadata)))
        return {"memory_id": f"m{len(self.writes)}",
                "metadata": {"barrier_seq": len(self.writes),
                             "committed_at": time.time(),
                             "suppressed": False}}


def writer_agent(**attributes):
    return SimpleNamespace(agent_name="travel_agent", user_id="u",
                           share_memory=True, extra_metadata={},
                           delete_on_revoke=True, forget_scope="user",
                           **attributes)


def events(*items):
    return [{"event_id": f"e{i}", "type": kind, "slot": slot,
             "fact_key": slot, "value": "Wizzair", "aliases": [],
             "utterance": text, "memory_type": "profile",
             "sharing": "shared"}
            for i, (kind, slot, text) in enumerate(items)]


def test_a_flooding_writer_stores_its_rows_after_its_events():
    log = WriteLog()
    session = events(("add", "airline", "I fly with Wizzair."),
                     ("add", "hotel", "I stay at Ibis."))
    result = smu.run_v2_session(
        writer_agent(flood_rows=6), {"session": 3, "events": session},
        "calendar", write=log.write, list_rows=None, delete=None)
    assert result["writer_failed"] is False
    own, flooded = log.writes[:2], log.writes[2:]
    assert [c for c, _ in own] == ["I fly with Wizzair.", "I stay at Ibis."]
    assert len(flooded) == 6 == len(result["flood"])
    kinds = [row["kind"] for row in result["flood"]]
    assert kinds == ["near_duplicate", "irrelevant"] * 3
    first, _ = flooded[0]
    assert first == "I FLY WITH WIZZAIR."  # normalizes to the original
    assert flooded[0][1]["provenance_event"] == "e0"  # a retried write
    assert flooded[0][1]["flood"] == 1 and flooded[0][1]["fact_key"] \
        == "airline"
    note, note_metadata = flooded[1]
    assert note.startswith("Note 2: ")
    assert note_metadata["provenance_event"] == "flood:3:2"
    assert "fact_key" not in note_metadata and note_metadata["flood"] == 2
    assert all(row["memory_ids"] for row in result["flood"])


def test_a_session_without_flood_rows_writes_none():
    log = WriteLog()
    result = smu.run_v2_session(
        writer_agent(), {"session": 1,
                         "events": events(("add", "a", "A."))},
        "profile", write=log.write, list_rows=None, delete=None)
    assert result["flood"] == [] and len(log.writes) == 1


def test_an_event_writes_with_its_own_memory_type_and_timing():
    log = WriteLog()
    session = events(("add", "airline", "I fly with Wizzair."))
    session[0]["memory_type"] = "calendar"
    before = time.time()
    result = smu.run_v2_session(
        writer_agent(), {"session": 2, "events": session}, "profile",
        write=log.write, list_rows=None, delete=None)
    assert log.writes[0][1]["memory_type"] == "calendar"
    record = result["events"][0]
    assert before <= record["issued_at"] <= record["completed_at"]
    assert record["barrier_seq"] == 1 and "committed_at" in record


def test_a_forget_that_missed_a_row_fails_unless_writes_run_at_once():
    report = {"deleted": [], "values_count": 1, "forms_count": 1,
              "scrubbed": {}, "listed": 2, "not_found": ["r1"]}
    session = events(("revoke", "airline", ""))
    session[0].update(value=None, utterance="Forget my airline.")

    def run(concurrent):
        return smu.run_v2_session(
            writer_agent(concurrent=concurrent),
            {"session": 6, "events": session}, "profile",
            write=None, list_rows=None, delete=None,
            forget=lambda user, key: dict(report))

    assert run(False)["writer_failed"] is True
    concurrent = run(True)
    assert concurrent["writer_failed"] is False
    assert concurrent["events"][0]["not_found"] == ["r1"]


def test_a_forget_records_its_commit_from_either_reply():
    report = {"deleted": [], "values_count": 1, "forms_count": 1,
              "scrubbed": {}, "listed": 0, "not_found": [],
              "barrier_seq": 7, "committed_at": 123.0}
    session = events(("revoke", "airline", ""))
    session[0].update(value=None, utterance="Forget my airline.")
    kernel_reply = {"response": {"success": True,
                                 "metadata": dict(report)}}
    for reply in (dict(report), kernel_reply):  # library, kernel
        result = smu.run_v2_session(
            writer_agent(), {"session": 6, "events": session}, "profile",
            write=None, list_rows=None, delete=None,
            forget=lambda user, key, reply=reply: reply)
        record = result["events"][0]
        assert result["writer_failed"] is False
        assert (record["barrier_seq"], record["committed_at"]) == (7, 123.0)


# -- the history ---------------------------------------------------------

class TurnLocus(FakeLocus):
    """``FakeLocus`` with a writer for every writer of the user, and
    the kernel session scope recorded."""

    def __init__(self, writers, **consumer):
        super().__init__(**consumer)
        self.writers = {n: FakeWriter(n, self.store, self.log)
                        for n in writers}
        self.scopes = []

    def start_user(self, user_id, control, writers=history.WRITERS):
        super().start_user(user_id, control)

    def session_scope(self, user_id):
        import contextlib

        @contextlib.contextmanager
        def scope():
            self.scopes.append(("open", user_id))
            yield "token"
            self.scopes.append(("close", user_id))
        return scope()

    def concurrent_consumer(self, user_id, probe_id):
        agent = FakeConsumer(self.store, self.log)
        agent.user_id, agent.session, agent.probe_id = user_id, 7, probe_id
        agent.store_conversation = False
        return agent

    def open_session(self, user_id=None):
        self.scopes.append(("open", user_id))
        return "token"

    def close_session(self, token):
        self.scopes.append(("close", token))


def derived_user(n=6, index=0):
    data = dataset.load(dataset.with_agents("pilot_v2", n))
    return data.user_v2(index, "r1").model_copy(
        update={"user_id": "jordan_r1_t0__kernel_shared"})


def test_an_agent_count_history_runs_writer_turns_and_lists_per_session():
    user = derived_user(12)
    locus = TurnLocus(user.writers)
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus))
    assert outcome.failure is None
    assert [(s.session, s.writer) for s in outcome.sessions] == [
        (t["session"], t["writer"]) for t in user.sessions]
    sessions = [l["after"] for l in outcome.listings
                if l["after"].startswith("session")]
    assert sessions == [f"session {n}" for n in range(1, 7)]
    # Each v2 session and the probes ran in a kernel session of their own.
    assert locus.scopes.count(("open", user.user_id)) == 7


class SlowWriter(FakeWriter):
    """A writer whose writes take ``delay`` seconds, recording when each
    call began and ended."""

    delay = 0.3
    calls = None

    def run(self, task_input):
        started = time.time()
        time.sleep(self.delay)
        result = super().run(task_input)
        self.calls.append((started, time.time()))
        return result


def test_concurrent_sessions_issue_the_probes_before_the_last_writes_end():
    user = derived_user(6)
    locus = TurnLocus(user.writers)
    calls = []
    for name in user.writers:
        writer = SlowWriter(name, locus.store, locus.log)
        writer.calls = calls
        locus.writers[name] = writer
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus),
                                  concurrency="concurrent")
    assert outcome.failure is None and outcome.concurrency == "concurrent"
    last_session = max(t["session"] for t in user.sessions)
    last_writes = sum(len(t["events"]) for t in user.sessions
                      if t["session"] == last_session)
    last_ended = max(end for _, end in calls[-last_writes:])
    issued = [turn.issued_at for turn in outcome.turns]
    assert len(issued) == 6 and max(issued) < last_ended
    # A session's writes ran at once: they overlapped in time.
    first = sorted(calls)[:2]
    assert first[1][0] < first[0][1]
    # Every write of the user still landed, and was recorded once.
    events_written = sum(1 for t in user.sessions for e in t["events"]
                         if e["type"] in history.WRITE_EVENTS)
    recorded = sum(1 for s in outcome.sessions for e in s.events
                   if "reported_ids" in e)  # a write event's record
    assert recorded == events_written
    assert not any(writer.__dict__.get("concurrent")
                   for writer in locus.writers.values())


class SlowProbeLocus(TurnLocus):
    """``TurnLocus`` whose concurrent consumer for ``slow`` probes takes
    ``delay`` seconds, counting the probe calls that returned."""

    delay = 0.3

    def __init__(self, writers, slow=(), **consumer):
        super().__init__(writers, **consumer)
        self.slow, self.returned = set(slow), []

    def concurrent_consumer(self, user_id, probe_id):
        agent = super().concurrent_consumer(user_id, probe_id)
        run = agent.run

        def timed(question):
            if probe_id in self.slow:
                time.sleep(self.delay)
            try:
                return run(question)
            finally:
                self.returned.append(probe_id)
        agent.run = timed
        return agent


def test_a_concurrent_probes_latency_is_its_own():
    """Concurrent probes are awaited in the dataset's order; each
    probe's latency and completion are when its own call returned."""
    user = derived_user(6)
    first = user.probes[0]["probe_id"]
    locus = SlowProbeLocus(user.writers, slow=[first])
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus),
                                  concurrency="concurrent")
    assert outcome.failure is None
    slow, *fast = outcome.turns
    assert slow.probe["probe_id"] == first
    assert slow.latency_seconds >= SlowProbeLocus.delay
    assert all(t.latency_seconds < SlowProbeLocus.delay for t in fast)
    assert all(t.completed_at < slow.completed_at for t in fast)


def test_probes_issued_before_a_writer_failed_finish_before_the_history():
    """A writer of the last session that fails after the probes were
    issued fails the user; the probes still finish, and their kernel
    session is closed, before ``run_history`` returns."""
    user = derived_user(6)
    locus = SlowProbeLocus(user.writers,
                           slow=[p["probe_id"] for p in user.probes])
    last = max(t["session"] for t in user.sessions)
    turn = next(t for t in user.sessions if t["session"] == last
                and any(e["type"] in history.WRITE_EVENTS
                        for e in t["events"]))
    calls = []
    for name in user.writers:
        writer = SlowWriter(name, locus.store, locus.log)
        writer.calls = calls
        locus.writers[name] = writer
    locus.writers[turn["writer"]].fail_on = next(
        e["event_id"] for e in turn["events"]
        if e["type"] in history.WRITE_EVENTS)
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus),
                                  concurrency="concurrent")
    assert outcome.failure.startswith("writer_failed")
    assert sorted(locus.returned) == sorted(p["probe_id"]
                                            for p in user.probes)
    probe_sessions = [s for s in locus.scopes if s == ("open", user.user_id)]
    assert locus.scopes.count(("close", "token")) == 1
    assert probe_sessions  # the probes' own session was opened


def test_the_kernel_locus_runs_a_session_in_a_kernel_session():
    """The SDK requests of a kernel writer carry the session's token,
    which the harness opened for the user and closes after."""
    locus = history.KernelLocus(sessions=True, kernel_url="http://k")
    locus.start_user("u1", None)
    seen = []
    with patch.object(communication, "open_kernel_session",
                      return_value="tok") as opened, \
            patch.object(communication, "close_kernel_session") as closed:
        with locus.session_scope("u1"):
            seen.append(communication.current_kernel_session())
    assert seen == ["tok"]
    opened.assert_called_once_with("u1", "http://k")
    closed.assert_called_once_with("tok", "http://k")
    assert communication.current_kernel_session() is None
    off = history.KernelLocus()
    with off.session_scope("u1"):
        assert communication.current_kernel_session() is None


def test_send_request_carries_the_kernel_session():
    query = SimpleNamespace(query_class="memory",
                            model_dump=lambda: {"params": {}})
    with patch.object(communication, "post",
                      return_value={"response": None}) as post:
        communication.send_request("a", query, base_url="http://k")
        with communication.kernel_session("tok"):
            communication.send_request("a", query, base_url="http://k")
    without, with_token = (call.args[2] for call in post.call_args_list)
    assert "session_token" not in without
    assert with_token["session_token"] == "tok"


def test_the_create_capture_keeps_concurrent_trials_apart():
    """Two trials capturing at once each record only their own creates
    (the load mode); the real create is restored after both."""
    from cerebrum.example.agents.task_agent import agent as task_module

    def fake_create(agent_name, content=None, metadata=None, base_url=None,
                    **kwargs):
        return {"response": {"success": True, "memory_id": "m"}}

    lists = {"a": [], "b": []}
    start = threading.Barrier(2)

    def trial(name):
        with history._capture_into(lists[name]):
            start.wait()
            for k in range(20):
                task_module.create_memory(
                    "task_agent", content="x",
                    metadata={"user_id": name, "owner_agent": "task_agent"})

    with patch.object(task_module, "create_memory", fake_create):
        threads = [threading.Thread(target=trial, args=(n,)) for n in "ab"]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert task_module.create_memory is fake_create
    assert [r.user_id for r in lists["a"]] == ["a"] * 20
    assert [r.user_id for r in lists["b"]] == ["b"] * 20


def test_the_create_capture_skips_a_create_the_quota_turned_away():
    """A create the write quota rejected stored nothing: the capture
    does not record it as written."""
    from cerebrum.example.agents.task_agent import agent as task_module

    replies = iter([
        {"response": {"success": True, "memory_id": "m",
                      "metadata": {"suppressed": False}}},
        {"response": {"success": True, "memory_id": "",
                      "metadata": {"suppressed": False,
                                   "quota_rejected": "quota"}}},
        {"response": {"success": True, "memory_id": "",
                      "metadata": {"suppressed": False,
                                   "quota_rejected": "duplicate"}}},
    ])

    def fake_create(agent_name, content=None, metadata=None, base_url=None,
                    **kwargs):
        return next(replies)

    written = []
    with patch.object(task_module, "create_memory", fake_create):
        with history._capture_into(written):
            for _ in range(3):
                task_module.create_memory(
                    "task_agent", content="x",
                    metadata={"user_id": "u", "owner_agent": "task_agent"})
    assert len(written) == 1


def test_the_flood_bound_counts_accepted_writes_against_write_events():
    """Per flooding turn: the quota admits ``max_writes`` writes, its
    own write events (not its revokes) first; accepted flood writes are
    those it admitted, whatever rows they left."""
    record = SessionRecord(session=3, writer="w", events=[
        {"event_id": "e1", "type": "add"},
        {"event_id": "e2", "type": "revoke"},
        {"event_id": "e3", "type": "update"},
    ], flood=[{"k": 1, "memory_ids": []},           # accepted, no row
              {"k": 2, "memory_ids": ["a", "b"]},   # accepted, two rows
              {"k": 3, "memory_ids": ["c"]},
              {"k": 4, "memory_ids": [], "quota_rejected": "quota"},
              {"k": 5, "memory_ids": [], "quota_rejected": "duplicate"}])
    outcome = SimpleNamespace(sessions=[record])
    quota = {"enabled": True, "max_writes": 4, "dedupe": True}
    (turn,) = stress.flood_sessions(outcome, quota)
    assert (turn["write_events"], turn["flood_accepted"], turn["bound"]) \
        == (2, 3, 2)
    assert turn["over"] is True
    record.flood = record.flood[:2]
    assert stress.flood_sessions(outcome, quota)[0]["over"] is False
    (off,) = stress.flood_sessions(outcome, {"enabled": False})
    assert off["bound"] is None and off["over"] is None


def test_misfiled_rows_are_the_users_rows_in_the_victims_partition():
    locus = FakeLocus()
    store = locus.store
    store.add("profile_agent", "mine", {"user_id": "victim",
                                        "provenance_user": "me"})
    store.add("profile_agent", "theirs", {"user_id": "victim",
                                          "provenance_user": "victim"})
    rows = history._misfiled(locus, "victim", "me", history.WRITERS)
    assert [row["content"] for row in rows] == ["mine"]


class Stamped:
    """The store, each row added through it stamped with ``fields``."""

    def __init__(self, store, **fields):
        self.store, self.fields, self.rows = store, fields, store.rows

    def add(self, owner, content, metadata):
        return self.store.add(owner, content, dict(metadata, **self.fields))

    def own(self, owner, uid):
        return self.store.own(owner, uid)


class MisfilingWriter(FakeWriter):
    """A writer that writes under the victim's id, as a ``wrong_user``
    writer outside the kernel does, its rows carrying the harness's
    provenance of the trial's user."""

    def run(self, task_input):
        user_id, self.user_id = self.user_id, "victim"
        self.store = Stamped(self.base, provenance_user=user_id)
        try:
            return super().run(task_input)
        finally:
            self.user_id = user_id


def test_a_wrong_user_writers_rows_are_credited_to_its_writes():
    """The faulty writer's rows are in the victim's partition: listed
    with each session's listing (``misfiled``), they are its writes'
    rows, so a backend that extracts does not read its writes as ones
    that stored nothing."""
    locus = FakeLocus()
    writer = MisfilingWriter("task_agent", locus.store, locus.log)
    writer.base = locus.store
    locus.writers["task_agent"] = writer
    user = v2_user()
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus),
                                  victim_id="victim")
    assert outcome.failure is None and outcome.misfiled_rows
    sessions = [s for s in outcome.sessions if s.writer == "task_agent"]
    assert sum(s.stored_rows for s in sessions) > 0
    first = next(listing for listing in outcome.listings
                 if listing["after"].startswith("session "))
    assert first["rows"].get("task_agent", []) == []  # not this user's
    assert history.extraction_failure(user, outcome, True) is None


def test_flood_rows_are_no_rows_of_their_source_event():
    record = SessionRecord(session=1, writer="w", events=[
        {"event_id": "e1", "type": "add", "reported_ids": ["a"]}])
    rows = [{"memory_id": "a", "metadata": {"provenance_event": "e1"}},
            {"memory_id": "f", "metadata": {"provenance_event": "e1",
                                            "flood": 1}}]
    history._listed_rows(record, rows)
    assert record.events[0]["memory_ids"] == ["a"]


def test_a_deleted_row_reappearing_is_found_whichever_writer_deleted_it():
    """An agent-count session has one record per writer turn; a row any
    of them deleted that a later listing shows has reappeared."""
    outcome = history.HistoryOutcome()
    outcome.sessions = [
        SessionRecord(session=2, writer="w1", deleted_ids=["a"]),
        SessionRecord(session=2, writer="w2", deleted_ids=["b"]),
    ]
    outcome.listings = [{"after": "session 2", "rows": {"w1": [
        {"memory_id": "a"}, {"memory_id": "b"}]}}]
    assert history.reappeared_ids(outcome) == ["a", "b"]


# -- the stress measures --------------------------------------------------

def probe(probe_id, kind, target, diagnostics, **fields):
    return SimpleNamespace(probe_id=probe_id, type=kind, target_event=target,
                           diagnostics=diagnostics, **fields)


def test_late_writes_are_those_committed_after_the_fetch_began():
    t0 = 1000.0
    sessions = [SessionRecord(session=6, writer="w", events=[
        {"event_id": "e1", "type": "update", "issued_at": t0,
         "completed_at": t0 + 0.5, "committed_at": t0 + 0.4,
         "barrier_seq": 5, "stored_rows": 1},
        {"event_id": "e2", "type": "revoke", "issued_at": t0,
         "completed_at": t0 + 0.05, "fact_key": "pet", "stored_rows": 0},
        {"event_id": "e3", "type": "add", "issued_at": t0,
         "completed_at": t0 + 0.02, "committed_at": t0 + 0.01,
         "barrier_seq": 7, "stored_rows": 1,
         "quota_rejected": "quota"},
    ], flood=[{"k": 1, "memory_ids": [], "quota_rejected": "duplicate"}])]
    outcome = SimpleNamespace(
        sessions=sessions, misfiled_rows=None,
        listings=[{"after": "history", "rows": {"w": [
            {"memory_id": "f1", "metadata": {"flood": 2}}]}}],
        turns=[SimpleNamespace(probe={"probe_id": "p4"}, issued_at=t0 + 0.001,
                               completed_at=t0 + 3, latency_seconds=3)])
    user = SimpleNamespace(sessions=[{"session": 6, "writer": "w",
                                      "events": [
                                          {"event_id": "e1", "sharing": "shared"},
                                          {"event_id": "e2", "fact_key": "pet"},
                                          {"event_id": "e3", "sharing": "shared"}]}])
    result = probe("p4", "recency", "e1", {
        "fetch_started_at": t0 + 0.03, "barrier_snapshot": 6,
        "barrier_waits": [{"outcome": "DRAINED"}],
        "injected_memories": [{"memory_id": "f1"}]},
        stale_in_block=True, expected_in_block=False)
    measured = stress.measures(user, outcome, [result], locus="kernel")
    p = measured["probes"]["p4"]
    assert p["writes_in_flight"] == ["e1", "e2", "e3"]
    assert p["late_writes"] == ["e1", "e2"]  # e3 committed before
    assert p["uncovered_writes"] == ["e3"]  # accepted after the snapshot
    assert p["stale_read"] is True and p["timing_miss"] is True
    assert p["flood_rows_in_block"] == 1
    assert measured["quota_rejected"] == {"quota": 1, "duplicate": 1}
    assert measured["barrier_drained"] == 1 and measured["barrier_timeouts"] \
        == 0
    assert measured["flood_rows_stored"] == 1
    # A replicated agent's barrier sequences are its own: none compared.
    replicated = stress.measures(user, outcome, [result], locus="replicated")
    assert replicated["probes"]["p4"]["uncovered_writes"] == []


def test_a_write_accepted_after_the_probe_is_uncovered_not_missed():
    """A late write whose barrier sequence is above the probe's
    snapshot was accepted after the probe: in the kernel it is
    uncovered, not a miss; outside the kernel every late write is."""
    t0 = 1000.0
    sessions = [SessionRecord(session=6, writer="w", events=[
        {"event_id": "e1", "type": "update", "issued_at": t0,
         "completed_at": t0 + 0.5, "committed_at": t0 + 0.4,
         "barrier_seq": 8, "stored_rows": 1}])]
    outcome = SimpleNamespace(
        sessions=sessions, misfiled_rows=None, listings=[],
        turns=[SimpleNamespace(probe={"probe_id": "p4"},
                               issued_at=t0 + 0.001, completed_at=t0 + 3,
                               latency_seconds=3),
               SimpleNamespace(probe={"probe_id": "p9"},
                               issued_at=t0 + 0.001, completed_at=t0 + 3,
                               latency_seconds=3)])
    user = SimpleNamespace(sessions=[{"session": 6, "writer": "w",
                                      "events": [{"event_id": "e1",
                                                  "sharing": "shared"}]}])
    diagnostics = {"fetch_started_at": t0 + 0.03, "barrier_snapshot": 6,
                   "injected_memories": []}
    results = [probe("p4", "recency", "e1", diagnostics,
                     stale_in_block=True, expected_in_block=False),
               probe("p9", "integration", None, diagnostics)]
    kernel = stress.measures(user, outcome, results, locus="kernel")
    p = kernel["probes"]["p4"]
    assert p["late_writes"] == ["e1"] and p["uncovered_writes"] == ["e1"]
    assert p["late_covered"] == [] and p["late_rows"] == 0
    assert p["timing_miss"] is False and p["stale_read"] is False
    assert kernel["memories_missing_timing"] == []
    replicated = stress.measures(user, outcome, results, locus="replicated")
    p = replicated["probes"]["p4"]
    assert p["late_covered"] == ["e1"] and p["late_rows"] == 1
    assert p["timing_miss"] is True and p["stale_read"] is True
    assert replicated["memories_missing_timing"] == ["w"]


def test_a_trials_flood_bound_is_the_kernels_quota(tmp_path):
    """The trial's stress measures take the write quota the pre-flight
    read from the kernel, so the flood bound is the run's own."""
    from benchmarks.shared_memory import synth_v2
    from tests.agents.test_history_v2 import USER_ID, orchestrator

    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=1)
    o = orchestrator(dataset=str(path))
    o.generator.run_id = "r1"
    o._embed = False
    o.judged = False
    quota = {"enabled": True, "max_writes": 5, "dedupe": True}
    o.preflight = {"pipeline": {"write_quota": quota}}
    locus = FakeLocus()

    def run_history_trial(user, variants=None, *, control=None,
                          recency_session=True, **stress_kwargs):
        user = user.model_copy(update={"user_id": USER_ID})
        return user, history.run_history(
            user, locus, VariantRunner(None, "kernel"),
            control=control), "kernel"

    seen = {}
    real = stress.measures

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    no_usage = {"backend_llm_tokens": None, "embedding_tokens": None}
    with patch.object(run_evaluation.stress, "measures", spy), \
            patch.object(run_evaluation, "read_backend_usage",
                         return_value=no_usage):
        o.run_single_trial(0, "kernel_shared", SimpleNamespace(
            run_history_trial=run_history_trial), method="kernel_shared")
    assert seen["quota"] == quota


T0 = 1000.0


def measured_probe(events, *, locus, kind="recall", target=None,
                   fetch=T0 + 0.03, snapshot=None, **fields):
    """The stress measures of one probe issued at ``T0 + 0.001`` whose
    fetch began at ``fetch``, over ``events`` (one writer, session 6;
    each event's ``sharing`` and ``fact_key`` are the user's)."""
    outcome = SimpleNamespace(
        sessions=[SessionRecord(session=6, writer="w", events=events)],
        misfiled_rows=None, listings=[],
        turns=[SimpleNamespace(probe={"probe_id": "p"}, issued_at=T0 + 0.001,
                               completed_at=T0 + 3, latency_seconds=3)])
    user = SimpleNamespace(sessions=[{"session": 6, "writer": "w", "events": [
        {"event_id": e["event_id"], "sharing": e.get("sharing", "shared"),
         "fact_key": e.get("fact_key")} for e in events]}])
    diagnostics = {"fetch_started_at": fetch, "barrier_snapshot": snapshot,
                   "injected_memories": []}
    result = probe("p", kind, target, diagnostics, **fields)
    return stress.measures(user, outcome, [result],
                           locus=locus)["probes"]["p"]


def timed_write(event_id, *, completed, committed=None, kind="add",
                **fields):
    record = {"event_id": event_id, "type": kind, "issued_at": T0,
              "completed_at": completed, **fields}
    if committed is not None:
        record["committed_at"] = committed
    return record


def test_a_writes_commit_time_is_the_stores_own_else_its_completion():
    """STRESS_DIMENSIONS.md, Concurrency, "What is measured" (lines
    299-305): a late write committed after the fetch began; "the commit
    time is the write's own (committed_at, kernel and replicated ...) or
    the harness's completion time (native, an upper bound)"."""
    events = [
        # Committed before the fetch began; its reply came after it.
        timed_write("e1", committed=T0 + 0.01, completed=T0 + 0.05),
        # No commit time of its own: completed before the fetch began.
        timed_write("e2", completed=T0 + 0.02),
        timed_write("e3", completed=T0 + 0.04),
    ]
    p = measured_probe(events, locus="replicated")
    assert p["late_writes"] == ["e3"]


def test_a_write_at_the_probes_snapshot_was_accepted_before_it():
    """STRESS_DIMENSIONS.md, Concurrency, "What is measured" (lines
    319-321): uncovered_writes are the kernel writes "whose barrier
    sequence is above the probe's snapshot (accepted after it)"; the
    write holding the snapshot's own sequence was accepted before."""
    events = [timed_write("e1", committed=T0 + 0.4, completed=T0 + 0.5,
                    barrier_seq=6),
              timed_write("e2", committed=T0 + 0.4, completed=T0 + 0.5,
                    barrier_seq=7)]
    p = measured_probe(events, locus="kernel", snapshot=6)
    assert p["uncovered_writes"] == ["e2"]
    assert p["late_covered"] == ["e1"]


@pytest.mark.parametrize("kind,measure,field,miss_when", [
    ("recall", "timing_miss", "expected_in_block", False),
    ("recency", "stale_read", "stale_in_block", True),
    ("contradiction", "stale_read", "stale_in_block", True),
    ("deletion", "late_forget", "forbidden_in_block", True),
])
@pytest.mark.parametrize("in_block", [True, False])
def test_a_covered_late_write_is_a_miss_only_as_the_block_shows(
        kind, measure, field, miss_when, in_block):
    """STRESS_DIMENSIONS.md, Concurrency, "What is measured" (lines
    312-318): timing_miss needs the target's value missing from the
    block; stale_read is a recency or contradiction probe "whose block
    held the stale value"; late_forget a deletion probe "whose block held
    the revoked value". The late write alone decides none of them."""
    if kind == "deletion":
        events = [timed_write("e0", committed=T0 - 5, completed=T0 - 5,
                        fact_key="pet"),
                  timed_write("e1", committed=T0 + 0.4, completed=T0 + 0.5,
                        kind="revoke", fact_key="pet")]
        target = "e0"
    else:
        events = [timed_write("e1", committed=T0 + 0.4, completed=T0 + 0.5,
                        kind="update")]
        target = "e1"
    p = measured_probe(events, locus="replicated", kind=kind,
                       target=target, **{field: in_block})
    assert "e1" in p["late_covered"]
    assert p[measure] is (in_block == miss_when)


def test_late_rows_are_the_rows_of_late_writes_the_consumer_may_see():
    """STRESS_DIMENSIONS.md, Concurrency, "What is measured" (lines
    309-311): "late_rows are their rows the consumer may see": rows, not
    writes (a revoke leaves none, a write may leave several), and not a
    private fact's."""
    events = [timed_write("e1", completed=T0 + 0.5, stored_rows=3),
              timed_write("e2", completed=T0 + 0.5, kind="revoke",
                    stored_rows=0),
              timed_write("e3", completed=T0 + 0.5, kind="private",
                    stored_rows=1, sharing="private")]
    p = measured_probe(events, locus="native")
    assert p["late_covered"] == ["e1", "e2", "e3"]
    assert p["late_rows"] == 3


def test_overrides_and_quota_rejections_are_counted_per_request_and_writer():
    """STRESS_DIMENSIONS.md, wrong_user "Measured" and the checks that
    must hold (lines 397-399, 430-431, 635-636): identity_overridden
    counts each request the kernel bound, a chat by its injection
    diagnostics; floods "Measured" (lines 527-529): quota_rejected "by
    reason and writer", so a reference writer's rejection shows."""
    overridden = {"claimed": "victim", "bound": "u"}
    sessions = [
        SessionRecord(session=2, writer="w1", events=[
            {"event_id": "e1", "type": "add",
             "identity_overridden": overridden},
            {"event_id": "e2", "type": "add", "quota_rejected": "quota"},
        ], flood=[{"k": 1, "memory_ids": ["m"],
                   "identity_overridden": overridden},
                  {"k": 2, "memory_ids": [], "quota_rejected": "duplicate"}]),
        SessionRecord(session=3, writer="w2", events=[
            {"event_id": "e3", "type": "add"}]),
    ]
    ids = ("p1", "p2", "p3")
    outcome = SimpleNamespace(
        sessions=sessions, misfiled_rows=[], listings=[],
        turns=[SimpleNamespace(probe={"probe_id": i}, issued_at=T0,
                               completed_at=T0 + 1, latency_seconds=1)
               for i in ids])
    results = [probe("p1", "recall", None,
                     {"identity_overridden": overridden}),
               probe("p2", "recency", None, {}),
               probe("p3", "privacy", None, {})]
    measured = stress.measures(SimpleNamespace(sessions=[]), outcome,
                               results, locus="kernel")
    assert measured["identity_overridden_requests"] == 2
    assert measured["identity_overridden_chats"] == 1
    assert measured["quota_rejected"] == {"quota": 1, "duplicate": 1}
    assert measured["quota_rejected_by_writer"] == {"w1": 2}


def test_memories_missing_timing_names_writers_whose_late_writes_left_no_row():
    """STRESS_DIMENSIONS.md, Concurrency, "What is measured" (lines
    323-327): "writers with a covered late write none of whose rows
    reached the integration probe's block": a revoke is no write, and
    another writer's row in the block does not excuse a writer."""
    sessions = [
        SessionRecord(session=1, writer="w3", events=[
            timed_write("e3", completed=T0 - 9, committed=T0 - 9)]),
        SessionRecord(session=6, writer="w1", events=[
            timed_write("e1", completed=T0 + 0.5, kind="update")]),
        SessionRecord(session=6, writer="w2", events=[
            timed_write("e2", completed=T0 + 0.5, kind="revoke",
                        fact_key="pet")]),
    ]
    outcome = SimpleNamespace(
        sessions=sessions, misfiled_rows=None, listings=[],
        turns=[SimpleNamespace(probe={"probe_id": "p9"}, issued_at=T0 + 0.001,
                               completed_at=T0 + 3, latency_seconds=3)])
    user = SimpleNamespace(sessions=[{"session": 6, "writer": "w", "events": [
        {"event_id": i, "sharing": "shared"} for i in ("e1", "e2", "e3")]}])
    integration = probe("p9", "integration", None, {
        "fetch_started_at": T0 + 0.03,
        "injected_memories": [{"memory_id": "m3",
                               "provenance_event": "e3"}]})
    measured = stress.measures(user, outcome, [integration],
                               locus="replicated")
    assert measured["probes"]["p9"]["late_covered"] == ["e1", "e2"]
    assert measured["memories_missing_timing"] == ["w1"]


# -- the orchestrator and the pre-flight ---------------------------------

def stressed(**kwargs):
    with patch.object(run_evaluation, "SyntheticDataGenerator"), \
            patch.object(run_evaluation, "HybridJudge"):
        return run_evaluation.EvaluationOrchestrator(
            trials=kwargs.pop("trials", 3), output_dir="out",
            write_csv=False, condition=None,
            method=kwargs.pop("method", "kernel_shared"),
            dataset=kwargs.pop("dataset", "pilot_v2"), **kwargs)


def test_an_agent_count_needs_a_v2_dataset():
    """``--agents N`` derives the v2 dataset's agent-count version; with
    any other dataset (or none) it refuses, instead of running that
    dataset recorded as N agents."""
    assert stressed(agents=6, judge=False).dataset.name == "pilot_agents_n6"
    assert stressed(agents=6, judge=False,
                    dataset="pilot_agents_n6").dataset.name \
        == "pilot_agents_n6"
    for dataset in ("pilot_v1", None, "pilot_agents_n12"):
        with pytest.raises(ValueError, match="--agents 6 needs"):
            stressed(agents=6, judge=False, dataset=dataset)
    # An agent-count dataset runs only at its own N.
    with pytest.raises(ValueError, match="written by 6 agents"):
        stressed(agents=4, judge=False, dataset="pilot_agents_n6")


def test_the_stress_levels_run_judge_free_and_uncrossed():
    with pytest.raises(ValueError):
        stressed(agents=6)  # judged
    with pytest.raises(ValueError):
        stressed(concurrency="concurrent", heterogeneity=2, judge=False)
    with pytest.raises(ValueError):
        stressed(load=4, fault="flood10", judge=False)
    with pytest.raises(ValueError):
        stressed(load=4, method="replicated_inhouse", judge=False)
    with pytest.raises(ValueError):
        stressed(fault="wrong_user", heterogeneity=1, judge=False)
    o = stressed(agents=12, judge=False, fault="flood10")
    assert o.dataset_name == "pilot_agents_n12"
    assert o._run_settings()["stress"]["fault"] == "flood10"


def test_the_faulty_agent_writes_and_the_victim_is_the_next_user():
    o = stressed(agents=6, judge=False, fault="wrong_user", trials=3)
    o.generator.run_id = "r1"
    user = o.dataset.user_v2(2, "r1")
    agent, victim = o.trial_fault(2, user)
    writing = {t["writer"] for t in user.sessions
               if any(e["type"] in history.WRITE_EVENTS
                      for e in t["events"])}
    assert agent in writing
    assert victim == o.dataset.user_v2(0, "r1").user_id  # wraps around
    meta = stressed(agents=6, judge=False, fault="missing_metadata")
    meta.generator.run_id = "r1"
    picked = {meta.trial_fault(i, meta.dataset.user_v2(i, "r1"))[0]
              for i in range(3)}
    assert picked <= set(agents_v1.WRITERS[6]) | {"assistant_agent"}


def preflight(fault, **quota):
    body = kernel_config(write_quota=dict(
        {"enabled": False, "max_writes": 4, "dedupe": True}, **quota),
        ablate={})  # the full kernel (Subtask 19)
    with patch.object(run_evaluation.requests, "get") as get:
        get.return_value.json.return_value = body
        return run_evaluation.check_v2_settings("http://k", "kernel_shared",
                                                fault=fault)


def test_the_preflight_wants_the_quota_on_only_under_a_flood():
    preflight("none")
    preflight("wrong_user")
    preflight("flood10", enabled=True)
    with pytest.raises(SystemExit):
        preflight("flood10")
    with pytest.raises(SystemExit):
        preflight("flood50", enabled=True, max_writes=3)
    with pytest.raises(SystemExit):
        preflight("none", enabled=True)


def test_the_load_mode_runs_users_at_once_in_order():
    o = stressed(load=4, judge=False, trials=8)
    running, peak = [0], [0]
    lock = threading.Lock()

    def trial(i, condition, pipeline, method=""):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        time.sleep(0.05)
        with lock:
            running[0] -= 1
        return i

    with patch.object(o, "run_single_trial", side_effect=trial):
        assert o._run_loaded(None, "kernel_shared") == list(range(8))
    assert peak[0] == 4


def test_both_flood_levels_run_with_the_quota_on():
    """STRESS_DIMENSIONS.md, flood10 and flood50, "The quota" (lines
    487-492): the write quota "is off by default and on under the flood
    levels", both of them; the pre-flight refuses either without it."""
    for fault in ("flood10", "flood50"):
        preflight(fault, enabled=True)
        with pytest.raises(SystemExit):
            preflight(fault)


def test_at_n_agents_h_deviates_its_share_of_the_writers_and_consumer():
    """STRESS_DIMENSIONS.md, Heterogeneity scales with N (lines 142-153,
    182-185): d = round(H*N/3) of the N agents deviate, the consumer one
    of them (it deviates at H = 2 as at every N)."""
    o = stressed(agents=6, judge=False, heterogeneity=2, trials=6)
    agents = tuple(agents_v1.WRITERS[6]) + ("assistant_agent",)
    chosen = [o.trial_variants(i) for i in range(6)]
    assert all(len(c) == round(2 * 6 / 3) for c in chosen)
    assert chosen == [schedule_module.schedule_for(SEED, 2, i, agents)
                      for i in range(6)]
    assert any("assistant_agent" in c for c in chosen)


@pytest.mark.parametrize("fault", ["wrong_user", "missing_metadata",
                                   "flood10", "flood50"])
def test_the_faulty_agent_is_taken_in_the_datasets_agent_order(fault):
    """STRESS_DIMENSIONS.md, A faulty agent (lines 370-376): the
    candidates are, for wrong_user and the floods, the writers with a
    write event, for missing_metadata those and the consumer, "taken in
    the dataset's agent order, rotated by a seeded offset per fault"."""
    o = stressed(agents=6, judge=False, fault=fault, trials=5)
    o.generator.run_id = "r1"
    for i in range(5):
        user = o.dataset.user_v2(i, "r1")
        writing = {t["writer"] for t in user.sessions
                   if any(e["type"] in history.WRITE_EVENTS
                          for e in t["events"])}
        candidates = [w for w in agents_v1.WRITERS[6] if w in writing]
        if fault == "missing_metadata":
            candidates.append("assistant_agent")
        assert o.trial_fault(i, user)[0] == faults.faulty_agent(
            o.fault_seed, fault, i, candidates)


def stress_trial(tmp_path, **levels):
    """One v2 trial through ``run_single_trial`` at the given stress
    levels, its history run on a FakeLocus after 0.05 s: the
    orchestrator, the TrialResult and the keywords the history got."""
    from benchmarks.shared_memory import synth_v2
    from tests.agents.test_history_v2 import USER_ID

    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=2)
    o = stressed(dataset=str(path), trials=2, judge=False, **levels)
    o.generator.run_id = "r1"
    o._embed = False
    o.preflight = {"pipeline": {"write_quota": {
        "enabled": False, "max_writes": 4, "dedupe": True}}}
    locus, seen = FakeLocus(), {}

    def run_history_trial(user, variants=None, *, control=None,
                          recency_session=True, **stress_kwargs):
        seen.update(stress_kwargs)
        time.sleep(0.05)
        user = user.model_copy(update={"user_id": USER_ID})
        return user, history.run_history(
            user, locus, VariantRunner(None, "kernel"),
            control=control), "kernel"

    no_usage = {"backend_llm_tokens": None, "embedding_tokens": None}
    pipeline = SimpleNamespace(run_history_trial=run_history_trial,
                               method="kernel_shared")
    with patch.object(run_evaluation, "read_backend_usage",
                      return_value=no_usage):
        result = o.run_single_trial(0, "kernel_shared", pipeline,
                                    method="kernel_shared")
    return o, result, seen


def test_a_faulty_trial_records_its_agent_victim_and_stress(tmp_path):
    """STRESS_DIMENSIONS.md, wrong_user (lines 379-385): the faulty
    writer tags the next user's id; Harness (lines 604-608): TrialResult
    records fault, faulty_agent, fault_victim and stress, the measures
    per probe and per trial; Load mode (lines 331-336): throughput comes
    from each trial's start and finish."""
    o, result, seen = stress_trial(tmp_path, fault="wrong_user")
    user = o.dataset.user_v2(0, "r1")
    agent, victim = o.trial_fault(0, user)
    assert agent and victim == o.dataset.user_v2(1, "r1").user_id
    assert seen == {"fault": "wrong_user", "faulty_agent": agent,
                    "victim_user_id": victim}
    assert not result.failed
    assert (result.fault, result.faulty_agent) == ("wrong_user", agent)
    assert result.fault_victim == f"{victim}__kernel_shared"
    measured = result.stress
    assert measured["faulty_agent"] == agent
    assert set(measured["probes"]) == {p["probe_id"] for p in user.probes}
    assert measured["finished_at"] - measured["started_at"] >= 0.05
    assert result.model_dump()["stress"] == measured


def test_a_concurrent_trial_runs_its_history_concurrently(tmp_path):
    """STRESS_DIMENSIONS.md, Concurrency (lines 228-250) and Harness
    (line 599): --concurrency concurrent reaches the history, which
    issues each write of a session as its own task."""
    _, result, seen = stress_trial(tmp_path, concurrency="concurrent")
    assert seen == {"concurrency": "concurrent"}
    assert result.concurrency == "concurrent" and result.stress is not None
