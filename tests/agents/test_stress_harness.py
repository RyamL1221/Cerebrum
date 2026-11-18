"""The stress dimensions' harness rules that Subtask 18's mutation run
found unpinned (NeurIPS Subtask 18, AIOS docs/STRESS_DIMENSIONS.md):
the writers' quota, binding and timing records, the flood rows, the
faulty agent's and the N-agent schedules, and the history's flood
records, concurrent probes, writer-turn listings, kernel writer types
and native listings. Each rule changes a number the stress report or a
v2 analysis gives. Small synthetic fixtures only (the committed
agent-count datasets for derived users); no kernel and no model is
reached, and no test reads ``results/``."""
import importlib
import threading
import time
from types import SimpleNamespace

import pytest

from benchmarks.shared_memory import (
    agents_v1,
    dataset,
    history,
    run_evaluation,
    stress,
)
from benchmarks.shared_memory.models import SessionRecord
from benchmarks.shared_memory.pipeline import VariantRunner
from cerebrum.example.agents import shared_memory_utils as smu
from cerebrum.example.agents.variants import faults
from tests.agents.test_history_v2 import (
    FakeConsumer,
    FakeKernel,
    FakeLocus,
    FakeWriter,
    Store,
    run,
    v2_user,
)

schedule_module = importlib.import_module(
    "cerebrum.example.agents.variants.schedule")
VARIANT_SEED = 20261106
FAULT_SEED = 20261116
QUOTA = {"enabled": True, "max_writes": 2, "dedupe": True}
REPORT = {"deleted": [], "values_count": 1, "forms_count": 1,
          "scrubbed": {}, "listed": 0, "not_found": []}


def writer(**attributes):
    """A v2 writer agent, as the loci configure one."""
    return SimpleNamespace(agent_name="docs_agent", user_id="u",
                           share_memory=True, extra_metadata={},
                           delete_on_revoke=True, forget_scope="user",
                           **attributes)


def event(i, kind, slot, text, memory_type="task_context"):
    return {"event_id": f"e{i}", "type": kind, "slot": slot,
            "fact_key": slot, "aliases": [], "utterance": text,
            "value": None if kind == "revoke" else f"Value{i}",
            "memory_type": memory_type, "sharing": "shared"}


def kernel_reply(memory_id, **outcome):
    """The kernel's reply to a create: ``metadata`` is the write's
    outcome."""
    return {"response": {"success": True, "memory_id": memory_id,
                         "metadata": dict({"suppressed": False},
                                          **outcome)}}


def derived_user(n, index=0):
    data = dataset.load(dataset.with_agents("pilot_v2", n))
    return data.user_v2(index, "r1").model_copy(
        update={"user_id": "jordan_r1_t0__kernel_shared"})


# -- the writers' records ------------------------------------------------

def test_a_quota_rejection_is_recorded_and_the_bound_counts_admitted():
    """SD 484-485: a rejected write's reply says why
    (``quota_rejected``); 527-529: it is measured by reason and writer;
    637-640: the bound counts each flooding turn's accepted flood writes
    against ``max_writes`` less its accepted write events. The writer
    records the reason on the event and on each flood write (``_timed``,
    a kernel reply's metadata)."""
    replies = iter([
        kernel_reply("m1", barrier_seq=1, committed_at=1.0),   # e0
        kernel_reply("", quota_rejected="duplicate"),           # e1
        kernel_reply("m2", barrier_seq=2, committed_at=2.0),   # flood 1
        kernel_reply("", quota_rejected="quota"),               # flood 2
        kernel_reply("", quota_rejected="quota"),               # flood 3
    ])
    session = [event(0, "add", "ci", "CI runs on Jenkins."),
               event(1, "add", "db", "CI runs on Jenkins!")]
    result = smu.run_v2_session(
        writer(flood_rows=3), {"session": 3, "events": session},
        "task_context", write=lambda content, metadata: next(replies),
        list_rows=None, delete=None)
    assert result["writer_failed"] is False
    assert [e.get("quota_rejected") for e in result["events"]] == [
        None, "duplicate"]
    assert [f.get("quota_rejected") for f in result["flood"]] == [
        None, "quota", "quota"]
    record = SessionRecord(session=3, writer="docs_agent",
                           events=result["events"], flood=result["flood"])
    outcome = SimpleNamespace(sessions=[record], turns=[], listings=[],
                              misfiled_rows=None)
    (turn,) = stress.flood_sessions(outcome, QUOTA)
    assert (turn["write_events"], turn["flood_accepted"], turn["bound"],
            turn["over"]) == (1, 1, 1, False)
    measured = stress.measures(SimpleNamespace(sessions=[]), outcome, [],
                               quota=QUOTA)
    assert measured["quota_rejected"] == {"duplicate": 1, "quota": 2}
    assert measured["flood_sessions_over_bound"] == 0


def test_the_claim_a_kernel_session_overrode_is_recorded_per_request():
    """SD 395-399: the kernel puts ``identity_overridden`` beside the
    response in its reply to a memory request; 635-636: every faulty
    kernel request records it. The writer records it on each write, each
    forget and each flood write, and the measures count them all."""
    overridden = {"claimed": "victim", "bound": "u"}
    session = [event(0, "add", "ci", "CI runs on Jenkins."),
               event(1, "revoke", "pet", "Forget my pet.")]
    result = smu.run_v2_session(
        writer(flood_rows=1), {"session": 6, "events": session},
        "task_context",
        write=lambda content, metadata: dict(kernel_reply("m1"),
                                             identity_overridden=overridden),
        list_rows=None, delete=None,
        forget=lambda user, key: {
            "response": {"success": True, "metadata": dict(REPORT)},
            "identity_overridden": overridden})
    assert result["writer_failed"] is False
    assert [e.get("identity_overridden") for e in result["events"]] == [
        overridden, overridden]
    assert result["flood"][0]["identity_overridden"] == overridden
    record = SessionRecord(session=6, writer="docs_agent",
                           events=result["events"], flood=result["flood"])
    outcome = SimpleNamespace(sessions=[record], turns=[], listings=[],
                              misfiled_rows=None)
    measured = stress.measures(SimpleNamespace(sessions=[]), outcome, [])
    assert measured["identity_overridden_requests"] == 3


def test_a_flood_near_duplicate_carries_its_source_events_metadata():
    """SD 461-463: a near-duplicate carries its source event's metadata
    (``fact_key``, ``session``, ``memory_type``, ``provenance_event``),
    as a retried write would: the source write's metadata exactly, plus
    ``flood``, whatever memory type the writer's own class has (an
    agent-count writer writes another v2 writer's facts)."""
    log = []

    def write(content, metadata):
        log.append(dict(metadata))
        return {"memory_id": f"m{len(log)}",
                "metadata": {"suppressed": False}}

    session = [event(0, "add", "ci", "CI runs on Jenkins."),
               event(1, "update", "db", "We moved to Postgres.")]
    result = smu.run_v2_session(
        writer(flood_rows=4), {"session": 3, "events": session},
        "calendar", write=write, list_rows=None, delete=None)
    own = {m["provenance_event"]: m for m in log[:2]}
    near = [(row, m) for row, m in zip(result["flood"], log[2:])
            if row["kind"] == "near_duplicate"]
    assert len(near) == 2
    for row, metadata in near:
        source = own[metadata["provenance_event"]]
        assert source["memory_type"] == "task_context"
        assert metadata == dict(source, flood=row["k"])


def test_a_flooding_writer_floods_a_turn_that_only_revokes():
    """SD 455-456: the faulty writer floods every session where it
    writes, and a revoke-only turn is flooded too (DEV_STATUS, Subtask
    18, review fix 8); without a write event every flood row is an
    irrelevant note (``flood_writes``). The writer does not fail."""
    contents = []

    def write(content, metadata):
        contents.append(content)
        return {"memory_id": f"m{len(contents)}",
                "metadata": {"suppressed": False}}

    result = smu.run_v2_session(
        writer(flood_rows=3),
        {"session": 6, "events": [event(0, "revoke", "pet",
                                         "Forget my pet.")]},
        "task_context", write=write, list_rows=None, delete=None,
        forget=lambda user, key: dict(REPORT))
    assert result["writer_failed"] is False and result["error"] is None
    assert [r["kind"] for r in result["flood"]] == ["irrelevant"] * 3
    assert all(r["memory_ids"] for r in result["flood"])
    assert [c.split(":")[0] for c in contents] == [
        "Note 1", "Note 2", "Note 3"]


def test_an_events_completion_is_when_its_last_call_returned():
    """SD 297-299: ``writes_in_flight`` are the writes issued before the
    probe that had not completed when it was issued, on the harness's
    clock: an event's ``completed_at`` is when its last call returned,
    after its ``issued_at``. A probe issued in between sees it in
    flight."""
    returned = []

    def write(content, metadata):
        time.sleep(0.05)
        returned.append(time.time())
        return {"memory_id": "m1", "metadata": {"suppressed": False}}

    result = smu.run_v2_session(
        writer(), {"session": 2, "events": [
            event(0, "add", "ci", "CI runs on Jenkins.")]},
        "task_context", write=write, list_rows=None, delete=None)
    record = result["events"][0]
    assert record["issued_at"] < returned[0] <= record["completed_at"]
    turn = SimpleNamespace(issued_at=(record["issued_at"] + returned[0]) / 2,
                           completed_at=None, latency_seconds=None)
    probe = SimpleNamespace(diagnostics=None, target_event=None,
                            type="recall")
    timing = stress.probe_timing(probe, turn,
                                 [dict(record, writer="w", session=2)], {},
                                 "native")
    assert timing["writes_in_flight"] == ["e0"]


# -- the schedules -------------------------------------------------------

def test_each_fault_rotates_its_candidates_by_an_offset_of_its_own():
    """SD 375-377: the candidates are rotated by a seeded offset per
    fault, user i taking candidate (i + offset) mod their count; a pure
    function of the fault seed, the fault, the trial index and the
    candidates, so a re-run reproduces each cell's faulty agents."""
    candidates = ["profile_agent", "task_agent", "docs_agent",
                  "calendar_agent"]
    picked = {fault: [faults.faulty_agent(FAULT_SEED, fault, i, candidates)
                      for i in range(4)]
              for fault in ("wrong_user", "missing_metadata", "flood10",
                            "flood50")}
    assert picked == {
        "wrong_user": ["profile_agent", "task_agent", "docs_agent",
                       "calendar_agent"],
        "missing_metadata": ["calendar_agent", "profile_agent",
                             "task_agent", "docs_agent"],
        "flood10": ["docs_agent", "calendar_agent", "profile_agent",
                    "task_agent"],
        "flood50": ["calendar_agent", "profile_agent", "task_agent",
                    "docs_agent"],
    }


def test_a_writer_fault_falls_on_a_writer_with_a_write_event():
    """SD 371-374: for ``wrong_user`` and the floods the faulty agent is
    a writer with at least one write event in the user's history; only
    ``missing_metadata`` may fall on the consumer
    (``EvaluationOrchestrator.trial_fault``)."""
    user = SimpleNamespace(
        writers=["profile_agent", "task_agent", "docs_agent",
                 "travel_agent"],
        sessions=[{"session": n, "writer": name,
                   "events": [{"type": "revoke" if name == "travel_agent"
                               else "add"}]}
                  for n, name in enumerate(["profile_agent", "task_agent",
                                            "docs_agent", "travel_agent"])])
    seen = {}
    for fault in ("wrong_user", "flood10", "flood50", "missing_metadata"):
        orchestrator = SimpleNamespace(
            fault=fault, fault_seed=FAULT_SEED, trials=12,
            dataset=SimpleNamespace(
                user_v2=lambda i, run_id: SimpleNamespace(user_id=f"u{i}")),
            generator=SimpleNamespace(run_id="r1"))
        seen[fault] = {
            run_evaluation.EvaluationOrchestrator.trial_fault(
                orchestrator, i, user)[0] for i in range(12)}
    writing = {"profile_agent", "task_agent", "docs_agent"}
    for fault in ("wrong_user", "flood10", "flood50"):
        assert seen[fault] == writing, fault
    assert seen["missing_metadata"] == writing | {history.CONSUMER}


N6 = tuple(agents_v1.WRITERS[6]) + (history.CONSUMER,)
SCHEDULE_N6 = {
    1: [{"task_agent": "V1", "docs_agent": "V1"},
        {"calendar_agent": "V2", "travel_agent": "V1"},
        {"profile_agent": "V5", "assistant_agent": "V1"},
        {"task_agent": "V3", "docs_agent": "V5"},
        {"calendar_agent": "V3", "travel_agent": "V2"}],
    2: [{"profile_agent": "V4", "assistant_agent": "V3",
         "task_agent": "V2", "docs_agent": "V4"},
        {"calendar_agent": "V4", "travel_agent": "V3",
         "profile_agent": "V3", "assistant_agent": "V4"},
        {"task_agent": "V4", "docs_agent": "V2", "calendar_agent": "V1",
         "travel_agent": "V5"},
        {"profile_agent": "V1", "assistant_agent": "V2",
         "task_agent": "V5", "docs_agent": "V3"},
        {"calendar_agent": "V5", "travel_agent": "V4",
         "profile_agent": "V2", "assistant_agent": "V5"}],
}


def test_the_n_agent_schedule_is_the_specs_construction():
    """SD 142-150: the 5N (agent, variant) pairs sit on a cycle whose
    position k belongs to agent ``order[k mod N]``, a seeded order of
    the agents; user i gets the d = round(H N / 3) consecutive positions
    starting at offset_H + d i, offset 0 at H = 1 and 5 d(N, 1) at
    H = 2. So, as HETEROGENEITY.md's schedule at N = 3 (its "Balance"),
    the first five users at H = 1 and at H = 2 together apply every pair
    exactly once; and the pilot's N = 6 schedule is this one."""
    for level, expected in SCHEDULE_N6.items():
        assert [schedule_module.schedule_for(VARIANT_SEED, level, i, N6)
                for i in range(5)] == expected
    for n in (6, 12):
        agents = tuple(agents_v1.WRITERS[n]) + (history.CONSUMER,)
        applied = [pair for level in (1, 2) for i in range(5)
                   for pair in schedule_module.schedule_for(
                       VARIANT_SEED, level, i, agents).items()]
        assert len(applied) == len(set(applied)) == 5 * n
        assert set(applied) == set(
            schedule_module.cycle_for(VARIANT_SEED, agents))
    # The agents' order on the cycle is seeded, not the dataset's.
    orders = {tuple(agent for agent, _ in
                    schedule_module.cycle_for(seed, N6)[:len(N6)])
              for seed in range(5)}
    assert len(orders) > 1


# -- the history ---------------------------------------------------------

class FloodingWriter(FakeWriter):
    """A writer whose every turn reports two flood writes, the second
    one turned away by the quota."""

    def run(self, task_input):
        result = super().run(task_input)
        result["flood"] = [
            {"k": 1, "kind": "near_duplicate", "memory_ids": ["f1"],
             "error": None},
            {"k": 2, "kind": "irrelevant", "memory_ids": [], "error": None,
             "quota_rejected": "quota"}]
        return result


def test_each_session_record_keeps_its_turns_flood_writes():
    """SD 527-529 and 637-640: the flood rows sent and written and the
    bound check count each flooding writer turn's flood writes, from its
    session record."""
    locus = FakeLocus()
    locus.writers["task_agent"] = FloodingWriter(
        "task_agent", locus.store, locus.log)
    user, outcome = run(locus)
    assert outcome.failure is None
    flooding = [s for s in outcome.sessions if s.writer == "task_agent"]
    assert flooding and all([f["k"] for f in s.flood] == [1, 2]
                            for s in flooding)
    assert all(s.flood == [] for s in outcome.sessions
               if s.writer != "task_agent")
    turns = stress.flood_sessions(outcome, QUOTA)
    assert [t["flood_accepted"] for t in turns] == [1] * len(flooding)


class HarnessLocus(FakeLocus):
    """``FakeLocus`` with a writer for every writer of ``writers``, the
    kernel session scope, and concurrent consumers. A writer fetched on
    a worker thread (a concurrent write task beginning) takes ``delay``
    seconds; ``begun`` holds when each such fetch returned."""

    delay = 0.0

    def __init__(self, writers=history.WRITERS, **consumer):
        super().__init__(**consumer)
        self.writers = {n: FakeWriter(n, self.store, self.log)
                        for n in writers}
        self.begun = []
        self._lock = threading.Lock()

    def start_user(self, user_id, control, writers=history.WRITERS):
        super().start_user(user_id, control)

    def writer(self, name):
        if threading.current_thread() is not threading.main_thread():
            time.sleep(self.delay)
            with self._lock:
                self.begun.append(time.time())
        return self.writers[name]

    def session_scope(self, user_id):
        import contextlib

        return contextlib.nullcontext("token")

    def open_session(self, user_id=None):
        return "token"

    def close_session(self, token):
        return None

    def concurrent_consumer(self, user_id, probe_id):
        agent = FakeConsumer(self.store, self.log)
        agent.user_id, agent.session, agent.probe_id = user_id, 7, probe_id
        agent.store_conversation = False
        return agent


def test_concurrent_probes_are_issued_once_every_write_has_begun():
    """SD 238-241: under ``concurrent`` the probes are issued once every
    write task of the last session has begun (its request may not have
    reached the store yet); SD 297-300: a probe's ``issued_at``, like a
    write's, is on the harness's wall clock, so writes issued before it
    compare."""
    locus = HarnessLocus()
    locus.delay = 0.2
    started = time.time()
    outcome = history.run_history(v2_user(), locus,
                                  VariantRunner(None, locus.locus),
                                  concurrency="concurrent")
    ended = time.time()
    assert outcome.failure is None and len(outcome.turns) == 6
    issued = [turn.issued_at for turn in outcome.turns]
    assert all(started <= t <= ended for t in issued)
    assert min(issued) >= max(locus.begun)


def test_every_writer_turn_of_a_session_gets_its_listed_rows():
    """SD 134-136: a session of a derived user is a list of writer
    turns; BENCHMARK_V2.md 548-551: each write event's rows and ids come
    from the listing after its session, for every turn of it (the late
    writes' rows, ``late_rows``, sum them)."""
    user = derived_user(6, index=1)  # sessions 2 to 5: two turns each
    locus = HarnessLocus(user.writers)
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus))
    assert outcome.failure is None
    groups = [turns for _, turns in history.session_groups(user)]
    assert any(len(turns) > 1 for turns in groups)
    writes = [e for s in outcome.sessions for e in s.events
              if "reported_ids" in e]
    assert writes and all(e["memory_ids"] == e["reported_ids"]
                          and e["stored_rows"] == 1 for e in writes)
    assert all(s.listing_counts for s in outcome.sessions)


def test_the_kernel_locus_writes_each_v2_writers_facts_with_its_type():
    """SD 124-127: memory types stay the v2 event's; a v2 event carries
    none, so the kernel locus writes each with its writer's: the v2
    writers are ProfileAgent, TaskAgent and CalendarAgent, and only an
    agent-count dataset's further writers take the calendar writer's
    class."""
    kernel = FakeKernel()
    with kernel.patched():
        _, outcome = run(history.KernelLocus())
    assert outcome.failure is None
    types = {}
    for row in kernel.store.rows.values():
        types.setdefault(row["metadata"]["owner_agent"], set()).add(
            row["metadata"].get("memory_type"))
    assert types == {"profile_agent": {"profile"},
                     "task_agent": {"task_context"},
                     "calendar_agent": {"calendar"}}


@pytest.mark.parametrize("n, index", ((3, 0), (6, 1)))
def test_native_listings_list_every_writer_of_an_agent_count_user(n, index):
    """BENCHMARK_V2.md 520-521: after each session the agents' rows are
    listed; at N agents the native listings list the dataset's writers,
    so every write is credited with its rows (the extraction check, the
    stored flood rows, the visible rows)."""
    user = derived_user(n, index)
    store, log = Store(), []
    agents = {name: FakeWriter(name, store, log) for name in user.writers}
    agents[history.CONSUMER] = FakeConsumer(store, log)
    locus = history.AgentManagedLocus("native", agents)
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus))
    assert outcome.failure is None
    after = next(l for l in outcome.listings if l["after"] == "history")
    writing = {turn["writer"] for turn in user.sessions
               if any(e["type"] in history.WRITE_EVENTS
                      for e in turn["events"])}
    if n > 3:  # a writer v2 does not have writes for this user
        assert writing - set(history.WRITERS)
    assert {name for name, rows in after["rows"].items() if rows} >= writing
    assert history.extraction_failure(user, outcome, True) is None


class Stamped:
    """The store, each row added through it stamped with ``fields``."""

    def __init__(self, store, **fields):
        self.store, self.fields, self.rows = store, fields, store.rows

    def add(self, owner, content, metadata):
        return self.store.add(owner, content, dict(metadata, **self.fields))

    def own(self, owner, uid):
        return self.store.own(owner, uid)


class MisfilingWriter(FakeWriter):
    """A ``wrong_user`` writer outside the kernel: it writes under the
    victim's id, its rows carrying the harness's provenance of the
    trial's user."""

    def run(self, task_input):
        user_id, self.user_id = self.user_id, "victim"
        self.store = Stamped(self.base, provenance_user=user_id)
        try:
            return super().run(task_input)
        finally:
            self.user_id = user_id


def test_native_misfiled_rows_are_found_whichever_writer_is_faulty():
    """SD 422-424: ``misfiled_rows`` are the rows whose
    ``provenance_user`` is user i stored under the victim's id: in the
    native locus each writer's own rows in the victim's partition,
    whichever writer is faulty (here the last), credited to the writes
    that stored them (SD 426-429)."""
    user = v2_user()
    store, log = Store(), []
    agents = {name: FakeWriter(name, store, log) for name in history.WRITERS}
    faulty = MisfilingWriter("calendar_agent", store, log)
    faulty.base = store
    agents["calendar_agent"] = faulty
    agents[history.CONSUMER] = FakeConsumer(store, log)
    locus = history.AgentManagedLocus("native", agents)
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, locus.locus),
                                  victim_id="victim")
    assert outcome.failure is None and outcome.misfiled_rows
    assert {r["metadata"]["owner_agent"]
            for r in outcome.misfiled_rows} == {"calendar_agent"}
    assert sum(s.stored_rows for s in outcome.sessions
               if s.writer == "calendar_agent") > 0
    assert history.extraction_failure(user, outcome, True) is None
