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
from unittest.mock import patch

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


def test_misfiled_rows_are_the_users_rows_in_the_victims_partition():
    locus = FakeLocus()
    store = locus.store
    store.add("profile_agent", "mine", {"user_id": "victim",
                                        "provenance_user": "me"})
    store.add("profile_agent", "theirs", {"user_id": "victim",
                                          "provenance_user": "victim"})
    rows = history._misfiled(locus, "victim", "me", history.WRITERS)
    assert [row["content"] for row in rows] == ["mine"]


def test_flood_rows_are_no_rows_of_their_source_event():
    record = SessionRecord(session=1, writer="w", events=[
        {"event_id": "e1", "type": "add", "reported_ids": ["a"]}])
    rows = [{"memory_id": "a", "metadata": {"provenance_event": "e1"}},
            {"memory_id": "f", "metadata": {"provenance_event": "e1",
                                            "flood": 1}}]
    history._listed_rows(record, rows)
    assert record.events[0]["memory_ids"] == ["a"]


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


# -- the orchestrator and the pre-flight ---------------------------------

def stressed(**kwargs):
    with patch.object(run_evaluation, "SyntheticDataGenerator"), \
            patch.object(run_evaluation, "HybridJudge"):
        return run_evaluation.EvaluationOrchestrator(
            trials=kwargs.pop("trials", 3), output_dir="out",
            write_csv=False, condition=None,
            method=kwargs.pop("method", "kernel_shared"),
            dataset=kwargs.pop("dataset", "pilot_v2"), **kwargs)


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
        {"enabled": False, "max_writes": 4, "dedupe": True}, **quota))
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
