"""Benchmark v2's harness (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Harness"): session ordering, the probes after
the history, the failure rules, the controls, what a revoke leaves
behind, and the probe_results schema, over an in-memory fake locus.

Amendment 2's harness changes are tested over the same fakes, the real
``KernelLocus`` with the kernel's replies faked (``FakeKernel``) and the
real ``AgentManagedLocus`` with fake agents: failed retrievals and
injections, errored probes recorded unscored, any exception failing the
user with what ran kept, rows per event from the listings, and the
agent-managed backend usage over every user id."""
import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.shared_memory import dataset, history, run_evaluation, synth_v2
from benchmarks.shared_memory.models import (
    InjectionDiagnostics,
    ProbeResult,
    TrialResult,
    V2UserData,
)
from benchmarks.shared_memory.pipeline import AgentPipeline, VariantRunner
from benchmarks.shared_memory.probes import score_probe
from cerebrum.example.agents.native.sharing import in_partition, visible
from cerebrum.example.agents.shared_memory_utils import WriterError
from cerebrum.utils import usage

BASE = dataset.load("users_v1")
USER_ID = "jordan_r1_t0__kernel_shared"
RETRIEVAL_ERROR = ("own: ConnectionError: refused; "
                   "shared: ConnectionError: refused")


def v2_user(index=0):
    record = synth_v2.build_user(index, BASE.users[index])
    return V2UserData(
        index=index, user_id=USER_ID,
        profile=record["final"]["profile"],
        task_context=record["final"]["task_context"],
        follow_up_query=record["base"]["follow_up_query"],
        plausible_actions=record["base"]["plausible_actions"],
        sessions=record["sessions"], probes=record["probes"],
    )


class Store:
    """Rows of every agent, as the loci keep them."""

    def __init__(self):
        self.rows, self.next = {}, 0

    def add(self, owner, content, metadata):
        mid = f"m{self.next}"
        self.next += 1
        self.rows[mid] = {"memory_id": mid, "content": content,
                          "metadata": dict(metadata, owner_agent=owner)}
        return mid

    def own(self, owner, uid):
        return [dict(r) for r in self.rows.values()
                if r["metadata"]["owner_agent"] == owner
                and r["metadata"].get("user_id") == uid]


def block_diagnostics(rows, session, user_id):
    """Injection diagnostics of a block that holds ``rows``, built at
    ``session`` in the session unit."""
    return {
        "injected_count": len(rows), "session": session,
        "block_recency_unit": "session",
        "resolved_user_id": user_id,
        "block_text": "Known about this user:\n" + "\n".join(
            f"- {r['content']}" for r in rows),
        "injected_memories": [
            {"memory_id": r["memory_id"], "content": r["content"],
             "owner_agent": r["metadata"]["owner_agent"],
             "memory_type": "profile",
             "provenance_event": r["metadata"].get("provenance_event"),
             "fact_key": r["metadata"].get("fact_key"),
             "session": r["metadata"].get("session")} for r in rows],
        "own_fetched": len(rows), "after_threshold": len(rows),
        "after_cap": min(len(rows), 10),
        "after_budget": min(len(rows), 10),
    }


class FakeWriter:
    """A v2 writer over the store. ``facts`` rows are stored per write,
    each with the write's metadata, as Mem0's extraction stores sibling
    facts, and the reply names the first only, as the kernel's and the
    library's Mem0 add do."""

    def __init__(self, name, store, log):
        self.name, self.store, self.log = name, store, log
        self.user_id = None
        self.delete_on_revoke = True
        self.fail_on = None
        self.facts = 1
        self.facts_of = {}  # event id -> rows stored (overrides facts)

    def run(self, task_input):
        session = json.loads(task_input)["v2_session"]
        self.log.append(("session", session["session"], self.name))
        events, deleted, stored = [], [], 0
        for event in session["events"]:
            if self.fail_on == event["event_id"]:
                return {"agent_name": self.name, "user_id": self.user_id,
                        "events": events, "writer_failed": True,
                        "error": "create: Memory not found",
                        "deleted_ids": deleted, "stored_rows": stored}
            if event["type"] == "revoke":
                found = [r["memory_id"] for r in
                         self.store.own(self.name, self.user_id)
                         if r["metadata"].get("fact_key")
                         == event["fact_key"]]
                if self.delete_on_revoke:
                    for mid in found:
                        del self.store.rows[mid]
                    deleted += found
                events.append({"event_id": event["event_id"],
                               "found_ids": found,
                               "deleted_ids": found
                               if self.delete_on_revoke else []})
                continue
            metadata = {
                "user_id": self.user_id, "fact_key": event["fact_key"],
                "session": session["session"],
                "provenance_event": event["event_id"],
                "sharing_policy": "private" if event["type"] == "private"
                else "shared"}
            ids = [self.store.add(self.name, event["utterance"] if n == 0
                                  else f"{event['utterance']} ({n + 1})",
                                  metadata) for n in range(
                                      self.facts_of.get(event["event_id"],
                                                        self.facts))]
            stored += 1
            events.append({"event_id": event["event_id"],
                           "memory_ids": ids[:1]})
        return {"agent_name": self.name, "user_id": self.user_id,
                "events": events, "stored_rows": stored,
                "deleted_ids": deleted, "writer_failed": False,
                "error": None, "written": []}

    def list_own_rows(self, user_id=None):
        return self.store.own(self.name, user_id or self.user_id)


class FakeConsumer:
    """The assistant: every row of its user in the block, ``extra``
    added to its diagnostics, its conversation stored."""

    def __init__(self, store, log, answer=None, diagnostics=None,
                 extra=None):
        self.store, self.log = store, log
        self.user_id, self.session, self.probe_id = None, None, None
        self.answer = answer or (lambda q: f"An answer to: {q}")
        self.diagnostics = diagnostics
        self.extra = extra or {}

    def run(self, question):
        self.log.append(("probe", self.session, self.probe_id))
        rows = [r for r in self.store.rows.values()
                if r["metadata"].get("user_id") == self.user_id]
        diagnostics = dict(self.diagnostics or block_diagnostics(
            rows, self.session, self.user_id), **self.extra)
        answer = self.answer(question)
        self.store.add("assistant_agent", f"User: {question}\nAssistant: "
                       f"{answer}", {"user_id": self.user_id,
                                     "session": self.session,
                                     "provenance_event": self.probe_id})
        return {"result": answer, "injection_diagnostics": diagnostics,
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                "total_tokens": 15}}

    def list_own_rows(self, user_id=None):
        return self.store.own("assistant_agent", user_id or self.user_id)


class FakeLocus:
    locus = "kernel"
    writes_from_results = True

    def __init__(self, **consumer):
        self.store, self.log = Store(), []
        self.writers = {n: FakeWriter(n, self.store, self.log)
                        for n in history.WRITERS}
        self.assistant = FakeConsumer(self.store, self.log, **consumer)

    def start_user(self, user_id, control):
        for agent in (*self.writers.values(), self.assistant):
            agent.user_id = user_id
        for agent in self.writers.values():
            agent.delete_on_revoke = control != "no_delete"

    def writer(self, name):
        return self.writers[name]

    def consumer(self, user_id, probe_id):
        self.assistant.session, self.assistant.probe_id = 7, probe_id
        return self.assistant

    def lister(self, name):
        return self.assistant if name == "assistant_agent" \
            else self.writers[name]

    def capture(self, written):
        from contextlib import ExitStack
        return ExitStack()

    def backend_usage(self, turns, user_ids=()):
        return None, None

    def finish_user(self):
        pass


def run(locus, user=None, control=None, variants=None):
    user = user or v2_user()
    outcome = history.run_history(user, locus,
                                  VariantRunner(variants, locus.locus),
                                  control=control)
    return user, outcome


def managed(kind, writer=None, consumer=None, **options):
    """The real ``AgentManagedLocus`` (``native`` or ``replicated``) over
    fake agents sharing one store; ``options`` go to the consumer."""
    store, log = Store(), []
    make_writer = writer or FakeWriter
    make_consumer = consumer or FakeConsumer
    agents = {n: make_writer(n, store, log) for n in history.WRITERS}
    agents[history.CONSUMER] = make_consumer(store, log, **options)
    return history.AgentManagedLocus(kind, agents)


class FakeKernel:
    """The kernel's replies to the kernel agents' SDK calls (create,
    list, delete and chat), over one store, for the real
    ``KernelLocus``. A create stores ``facts`` rows with its metadata
    and names the first, as the kernel's Mem0 add does; a chat reply's
    diagnostics hold every row of the user plus ``extra``, and the
    kernel stores the turn, as auto_extract does."""

    def __init__(self, facts=1, extra=None):
        self.store, self.facts, self.extra = Store(), facts, extra or {}

    def create_memory(self, agent_name, content=None, metadata=None,
                      base_url=None, **kwargs):
        owner = (metadata or {}).get("owner_agent", agent_name)
        ids = [self.store.add(owner, content if n == 0
                              else f"{content} ({n + 1})", metadata or {})
               for n in range(self.facts)]
        return {"response": {"success": True, "memory_id": ids[0]}}

    def list_memories(self, agent_name, user_id=None, base_url=None,
                      k=None, **kwargs):
        return {"response": {"success": True,
                             "search_results": self.store.own(agent_name,
                                                              user_id)}}

    def delete_memory(self, agent_name, memory_id, base_url=None,
                      user_id=None, **kwargs):
        if memory_id not in self.store.rows:
            return {"response": {"success": False,
                                 "error": "Memory not found"}}
        del self.store.rows[memory_id]
        return {"response": {"success": True, "memory_id": memory_id}}

    def llm_chat(self, agent_name, messages, base_url=None, llms=None,
                 user_id=None, session=None, **kwargs):
        question = messages[-1]["content"]
        rows = [r for r in self.store.rows.values()
                if r["metadata"].get("user_id") == user_id]
        diagnostics = dict(block_diagnostics(rows, session, user_id),
                           **self.extra)
        answer = f"An answer to: {question}"
        self.store.add(agent_name, f"User: {question}\nAssistant: {answer}",
                       {"user_id": user_id, "session": session,
                        "memory_type": "conversation",
                        "provenance_event": kwargs.get("provenance_event")})
        return {"response": {"response_message": answer},
                "injection_diagnostics": diagnostics,
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                "total_tokens": 15}}

    def patched(self) -> ExitStack:
        """The kernel agents' module-level SDK calls, answered here."""
        from cerebrum.example.agents.assistant_agent import (
            agent as assistant,
        )
        from cerebrum.example.agents.calendar_agent import agent as calendar
        from cerebrum.example.agents.profile_agent import agent as profile
        from cerebrum.example.agents.task_agent import agent as task

        stack = ExitStack()
        for module in (profile, task, calendar):
            for name in ("create_memory", "list_memories", "delete_memory"):
                stack.enter_context(
                    patch.object(module, name, getattr(self, name)))
        stack.enter_context(patch.object(assistant, "llm_chat",
                                         self.llm_chat))
        stack.enter_context(patch.object(assistant, "list_memories",
                                         self.list_memories))
        return stack


def record_usage(tag):
    """One backend LLM call and one embedding call tagged ``tag``."""
    usage.ACCUMULATOR.record(tag, usage.BACKEND_EXTRACTION, "azure/gpt-4o",
                             100, 20)
    usage.ACCUMULATOR.record(tag, usage.EMBEDDING,
                             "ollama/nomic-embed-text", 8, 0)


class UsageWriter(FakeWriter):
    """A writer whose backend makes one LLM and one embedding call per
    write, tagged with the user id it writes under (a V2 variant's
    rewritten one), as the native and replicated writers' calls are."""

    def run(self, task_input):
        result = super().run(task_input)
        for event in result["events"]:
            if "memory_ids" in event:
                record_usage(self.user_id)
        return result


class UsageConsumer(FakeConsumer):
    """An assistant that, as the native and replicated ones do, makes
    its own backend calls and then takes everything tagged with its
    own user id, reported as its ``backend_usage``."""

    def run(self, question):
        result = super().run(question)
        record_usage(self.user_id)
        records = usage.ACCUMULATOR.take(self.user_id)
        result["backend_usage"] = {
            "backend_llm_tokens": usage.summarize(
                records, usage.BACKEND_EXTRACTION),
            "embedding_tokens": usage.summarize(records, usage.EMBEDDING),
            "records": records,
        }
        return result


# -- ordering ---------------------------------------------------------------

def test_sessions_run_in_order_then_the_probes_at_session_7():
    locus = FakeLocus()
    user, outcome = run(locus)
    sessions = [entry for entry in locus.log if entry[0] == "session"]
    assert [s[1] for s in sessions] == [1, 2, 3, 4, 5, 6]
    assert [s[2] for s in sessions] == [s["writer"] for s in user.sessions]
    probes = [entry for entry in locus.log if entry[0] == "probe"]
    assert [p[2] for p in probes] == [p["probe_id"] for p in user.probes]
    assert all(p[1] == 7 for p in probes)
    # Every session came before every probe.
    assert locus.log.index(probes[0]) == len(sessions)
    # Listings after each session, after the history, after the probes.
    assert [l["after"] for l in outcome.listings] == [
        f"session {i}" for i in range(1, 7)] + ["history", "probes"]
    assert outcome.failure is None
    assert [s.session for s in outcome.sessions] == [1, 2, 3, 4, 5, 6]
    assert all(set(s.listing_counts) == set(history.AGENTS)
               for s in outcome.sessions)


def test_the_no_memory_control_skips_the_sessions():
    locus = FakeLocus()
    _, outcome = run(locus, control="no_memory")
    assert not [e for e in locus.log if e[0] == "session"]
    assert len([e for e in locus.log if e[0] == "probe"]) == 6
    assert outcome.sessions == []


def test_the_no_delete_control_reaches_the_writers():
    locus = FakeLocus()
    user, outcome = run(locus, control="no_delete")
    assert history.deleted_ids(outcome) == []
    revoked = history.revoked_value_rows(user, outcome)
    assert {r["listing"] for r in revoked} == {"history", "probes"}


# -- failures ---------------------------------------------------------------

def test_a_writer_error_stops_the_history():
    locus = FakeLocus()
    user = v2_user()
    locus.writers["task_agent"].fail_on = user.sessions[1]["events"][1][
        "event_id"]
    _, outcome = run(locus, user)
    assert outcome.failure.startswith("writer_failed: task_agent in session 2")
    assert not [e for e in locus.log if e[0] == "probe"]


@pytest.mark.parametrize("answer", ["", "   ", "Error: boom"])
def test_a_consumer_error_fails_instead_of_passing(answer):
    locus = FakeLocus(answer=lambda q: answer)
    _, outcome = run(locus)
    assert "consumer" in outcome.failure
    # It stopped at the first probe: deletion, a hard constraint.
    assert len(outcome.turns) == 1


def test_a_block_not_built_at_session_7_fails():
    locus = FakeLocus(diagnostics={"injected_count": 2, "session": None,
                                   "block_recency_unit": "time"})
    _, outcome = run(locus)
    assert "session None" in outcome.failure


def test_a_listing_at_its_limit_fails(monkeypatch):
    monkeypatch.setattr(history, "LIST_LIMIT", 3)
    _, outcome = run(FakeLocus())
    assert outcome.failure.startswith("listing_at_limit")


# -- what a revoke leaves --------------------------------------------------

def test_deleted_ids_reappearing_and_residue_are_recorded():
    locus = FakeLocus()
    user, outcome = run(locus, v2_user(0))  # user 0 has an echo
    deleted = history.deleted_ids(outcome)
    assert deleted
    assert history.reappeared_ids(outcome) == []
    # Put a deleted row back, as a backend that resurrects one would.
    final = outcome.listings[-1]["rows"]["profile_agent"]
    final.append({"memory_id": deleted[0], "content": "x",
                  "metadata": {}})
    assert history.reappeared_ids(outcome) == [deleted[0]]
    residue = history.revoked_value_rows(user, outcome)
    echo = next(e for s in user.sessions for e in s["events"]
                if e.get("echo_of"))
    assert {r["provenance_event"] for r in residue} >= {echo["event_id"]}
    assert all(r["owner_agent"] != "profile_agent" or
               r["provenance_event"] is None for r in residue)


def test_the_extraction_guard_counts_rows_by_event():
    locus = FakeLocus()
    user, outcome = run(locus)
    assert history.extraction_failure(user, outcome, True) is None
    assert history.extraction_failure(user, outcome, False) is None
    # A write that stored nothing: drop its row from its listing.
    event = user.sessions[2]["events"][0]
    listing = outcome.listings[2]["rows"][user.sessions[2]["writer"]]
    listing[:] = [r for r in listing if r["metadata"]["provenance_event"]
                  != event["event_id"]]
    assert event["event_id"] in history.extraction_failure(
        user, outcome, True)


# -- probe_results schema ----------------------------------------------------

def test_probe_results_have_the_spec_fields():
    locus = FakeLocus()
    user, outcome = run(locus)
    results = history.score_turns(user, outcome, "kernel")
    assert [r.type for r in results] == [
        "deletion", "privacy", "recall", "recency", "contradiction",
        "integration"]
    for r, probe in zip(results, user.probes):
        assert isinstance(r, ProbeResult)
        assert r.probe_id == probe["probe_id"]
        assert r.question == probe["question"]
        assert r.expected == probe["expected"]
        assert r.forbidden == probe["forbidden"]
        assert r.observed.startswith("An answer to")
        assert r.diagnostics is not None and r.diagnostics.session == 7
        assert r.token_usage["total_tokens"] == 15
        assert r.cap_bound is not None
    assert results[-1].passed is None  # integration is judged
    # The fake's block holds every row: the revoked value is in it.
    assert results[0].forbidden_in_block is True
    assert results[0].passed is False
    trial = TrialResult(trial_index=0, condition="kernel_shared",
                        probe_results=results, sessions=outcome.sessions)
    again = TrialResult.model_validate_json(trial.model_dump_json())
    assert again.probe_results[2].expected == results[2].expected
    assert len(again.sessions) == 6


# -- the orchestrator ----------------------------------------------------------

def orchestrator(**kwargs):
    with patch.object(run_evaluation, "SyntheticDataGenerator"), \
            patch.object(run_evaluation, "HybridJudge"):
        return run_evaluation.EvaluationOrchestrator(
            trials=1, output_dir="out", write_csv=False, condition=None,
            method=kwargs.pop("method", "kernel_shared"),
            dataset=kwargs.pop("dataset", "users_v1"), **kwargs)


def test_controls_need_v2_and_no_judge(tmp_path):
    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=2)
    with pytest.raises(ValueError):
        orchestrator(control="no_delete")  # v1 dataset
    with pytest.raises(ValueError):
        orchestrator(dataset=str(path), control="no_delete")  # judged
    with pytest.raises(ValueError):
        orchestrator(dataset=str(path), method="naive_concat", judge=False)
    o = orchestrator(dataset=str(path), control="no_delete", judge=False)
    assert o.v2 and o._run_settings()["control"] == "no_delete"


def test_a_v2_trial_mirrors_the_integration_probe_and_judges_it(tmp_path):
    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=1)
    o = orchestrator(dataset=str(path))
    o.generator.run_id = "r1"
    o._embed = False
    o.judge = MagicMock()
    o.judge.evaluate.return_value = SimpleNamespace(
        profile_usage_score=4, task_usage_score=3, integration_score=5,
        judge_attempts=1)
    locus = FakeLocus()

    def run_history_trial(user, variants=None, *, control=None,
                          recency_session=True):
        user = user.model_copy(update={"user_id": USER_ID})
        outcome = history.run_history(
            user, locus, VariantRunner(None, "kernel"), control=control)
        outcome.backend_extraction = False
        return user, outcome, "kernel"

    pipeline = SimpleNamespace(run_history_trial=run_history_trial)
    with patch.object(run_evaluation, "read_backend_usage",
                      return_value={"backend_llm_tokens": None,
                                    "embedding_tokens": None}):
        trial = o.run_single_trial(0, "kernel_shared", pipeline,
                                   method="kernel_shared")
    assert trial.failed is False, trial.error_message
    assert len(trial.probe_results) == 6 and len(trial.sessions) == 6
    integration = trial.probe_results[-1]
    assert trial.assistant_response == integration.observed
    assert trial.integration_score == integration.integration_score == 5
    kwargs = o.judge.evaluate.call_args.kwargs
    assert kwargs["query"] == trial.follow_up_query
    assert kwargs["profile"] == trial.synthetic_profile
    assert trial.input_sha256 and trial.user_id == USER_ID
    assert trial.token_usage.total_tokens == 6 * 15


def test_base_events_reach_the_writers_with_their_fields():
    """The harness hands a base event the fields it states (as a v1
    writer got them), so V5's raw payload has facts in it."""
    sent = []
    locus = FakeLocus()
    real = FakeWriter.run

    def recording(self, task_input):
        sent.append(json.loads(task_input)["v2_session"])
        return real(self, task_input)
    user = v2_user()
    with patch.object(FakeWriter, "run", recording):
        run(locus, user)
    bases = [e for s in sent for e in s["events"] if e["type"] == "base"]
    assert [b["fact_key"] for b in bases] == ["base_profile", "base_task"]
    assert bases[0]["fields"] == user.profile.model_dump()
    assert bases[1]["fields"] == user.task_context.model_dump()
    # The dataset's own events are left as they were.
    assert all("fields" not in e for s in user.sessions
               for e in s["events"])


# -- Amendment 2: the models ------------------------------------------------

def test_diagnostics_and_probe_results_carry_the_error_fields():
    reader = AgentPipeline(share_memory=True)
    diagnostics = reader._extract_injection_diagnostics(
        {"injection_diagnostics": {
            "injected_count": 0, "block_text": "",
            "retrieval_error": RETRIEVAL_ERROR,
            "injection_error": "RuntimeError: provider down"}})
    assert diagnostics.retrieval_error == RETRIEVAL_ERROR
    assert diagnostics.injection_error == "RuntimeError: provider down"
    result = ProbeResult(probe_id="p", type="recall", question="q",
                         semantic_error="ConnectionError: refused")
    assert result.semantic_error == "ConnectionError: refused"
    # A falsy error is no error; any other value is kept as its text,
    # so a producer's odd value cannot make the results file unloadable.
    assert InjectionDiagnostics(retrieval_error="").retrieval_error is None
    assert InjectionDiagnostics(
        injection_error=ValueError("bad row")).injection_error == "bad row"


def test_a_results_file_from_before_amendment_2_still_loads():
    old = {
        "trial_index": 0, "condition": "kernel_shared",
        "method": "kernel_shared",
        "injection_diagnostics": {"injected_count": 1, "block_text": "- x"},
        "sessions": [{
            "session": 1, "writer": "profile_agent", "stored_rows": 3,
            "events": [{"event_id": "u000-e00", "type": "base",
                        "memory_ids": ["m0"], "stored_rows": 1}],
            "listing_counts": {"profile_agent": 6}}],
        "probe_results": [{
            "probe_id": "u000-p3-recall", "type": "recall",
            "question": "q", "passed": True, "semantic_best": 0.4,
            "diagnostics": {"injected_count": 1, "block_text": "- x"}}],
    }
    trial = TrialResult.model_validate(old)
    assert trial.sessions[0].stored_rows == 3
    assert trial.sessions[0].events[0]["memory_ids"] == ["m0"]
    probe = trial.probe_results[0]
    assert probe.passed is True and probe.semantic_error is None
    assert probe.diagnostics.retrieval_error is None
    assert trial.injection_diagnostics.injection_error is None
    assert TrialResult.model_validate_json(trial.model_dump_json()) == trial


# -- Amendment 2: failed retrievals and injections --------------------------

def failing_block(kind, key, error):
    """A locus of ``kind`` whose consumer's diagnostics report ``key``
    as ``error``, and the patches it runs under."""
    if kind == "kernel":
        kernel = FakeKernel(extra={key: error})
        return history.KernelLocus(), kernel.patched()
    if kind == "fake":
        return FakeLocus(extra={key: error}), ExitStack()
    return managed(kind, extra={key: error}), ExitStack()


@pytest.mark.parametrize("kind", ["fake", "kernel", "replicated", "native"])
@pytest.mark.parametrize("key,what", [
    ("retrieval_error", "retrieval failed"),
    ("injection_error", "injection failed")])
def test_a_failed_retrieval_or_injection_fails_the_user(kind, key, what):
    """Before, a failed fetch looked like an empty store, so the
    deletion probe passed; now it is a consumer error in every locus."""
    error = RETRIEVAL_ERROR if key == "retrieval_error" else \
        "RuntimeError: provider down"
    locus, patches = failing_block(kind, key, error)
    with patches:
        user, outcome = run(locus)
    [turn] = outcome.turns  # it stopped at the first probe: deletion
    assert turn.error == f"consumer {what}: {error}"
    assert outcome.failure == f"{user.probes[0]['probe_id']}: {turn.error}"
    assert turn.answer.startswith("An answer to")  # the answer was fine
    assert len(outcome.sessions) == 6


@pytest.mark.parametrize("value", [None, ""])
def test_an_empty_error_field_is_no_error(value):
    locus = FakeLocus(extra={"retrieval_error": value,
                             "injection_error": value})
    _, outcome = run(locus)
    assert outcome.failure is None
    assert len(outcome.turns) == 6


def test_both_block_errors_are_named():
    locus = FakeLocus(extra={"retrieval_error": RETRIEVAL_ERROR,
                             "injection_error": "KeyError: 'x'"})
    _, outcome = run(locus)
    assert outcome.turns[0].error == (
        f"consumer retrieval failed: {RETRIEVAL_ERROR}; "
        "consumer injection failed: KeyError: 'x'")


# -- Amendment 2: errored probes are recorded unscored ----------------------

def with_session(session):
    """A consumer's diagnostics as built at ``session``."""
    def diagnostics(locus):
        real = locus.assistant.run

        def run_at(question):
            result = real(question)
            result["injection_diagnostics"]["session"] = session
            return result
        locus.assistant.run = run_at
    return diagnostics


ERRORED = {
    "empty answer": (dict(answer=lambda q: ""), None,
                     "consumer returned an empty answer"),
    "error text": (dict(answer=lambda q: "Error: model timed out"), None,
                   "consumer error: Error: model timed out"),
    "failed retrieval": (dict(extra={"retrieval_error": RETRIEVAL_ERROR}),
                         None, f"consumer retrieval failed: "
                         f"{RETRIEVAL_ERROR}"),
    "block at session 6": ({}, with_session(6),
                           "block built at session 6, not 7"),
}
SCORE_FIELDS_NONE = (
    "passed", "expected_present", "stale_present", "forbidden_in_answer",
    "forbidden_in_block", "transition_marked", "expected_in_block",
    "stale_in_block", "newest_target_row_has_stale", "cap_bound",
    "budget_bound", "answer_words", "semantic_best", "semantic_only",
    "semantic_error", "contaminated", "visible_stored_rows",
    "judge_scores", "integration_score")
SCORE_FIELDS_EMPTY = (
    "matched_expected", "matched_forbidden", "rows_with_expected",
    "rows_with_stale", "rows_with_forbidden", "other_values_in_answer",
    "deleted_ids_in_block")


@pytest.mark.parametrize("how", ERRORED)
def test_an_errored_probe_is_recorded_unscored(how):
    """pilot_v2 user 1's deletion probe (forbidden 'Kittiwake', no
    echo): scored, an errored turn over a clean block passed the hard
    constraint. It is recorded with its ground truth and the error."""
    options, setup, error = ERRORED[how]
    user = v2_user(1)
    locus = FakeLocus(**options)
    if setup:
        setup(locus)
    _, outcome = run(locus, user)
    [turn] = outcome.turns
    assert turn.error == error
    assert outcome.failure == f"u001-p1-deletion: {error}"
    # Scored, this turn would pass deletion: the block lacks the value.
    assert score_probe(turn.probe, turn.answer, turn.diagnostics,
                       user_values=[], locus="kernel")["passed"] is True
    # Native, so even the native-only visible_stored_rows is not set.
    [result] = history.score_turns(user, outcome, "native")
    probe = user.probes[0]
    assert (result.probe_id, result.type) == ("u001-p1-deletion",
                                              "deletion")
    assert result.question == probe["question"]
    assert result.expected == probe["expected"] == []
    assert result.forbidden == probe["forbidden"]
    assert result.target_event == probe["target_event"]
    assert result.observed == turn.answer and result.error == error
    assert result.diagnostics.block_text == turn.diagnostics["block_text"]
    assert result.token_usage["total_tokens"] == 15
    for name in SCORE_FIELDS_NONE:
        assert getattr(result, name) is None, name
    for name in SCORE_FIELDS_EMPTY:
        assert getattr(result, name) == [], name


def test_turns_before_an_error_are_still_scored():
    user = v2_user(1)
    failing = user.probes[2]["probe_id"]  # recall
    locus = FakeLocus()
    real = locus.assistant.run

    def run_probe(question):
        result = real(question)
        if locus.assistant.probe_id == failing:
            result["result"] = ""
        return result
    locus.assistant.run = run_probe
    _, outcome = run(locus, user)
    results = history.score_turns(user, outcome, "kernel")
    assert [r.type for r in results] == ["deletion", "privacy", "recall"]
    assert [r.error is None for r in results] == [True, True, False]
    assert results[0].passed is not None and results[1].passed is not None
    assert results[2].passed is None and results[2].matched_expected == []


# -- Amendment 2: any exception fails the user, what ran is kept ------------

@pytest.mark.parametrize("at,listings,turns", [(3, 2, 0), (8, 7, 6)])
def test_a_listing_error_fails_the_user_and_keeps_what_ran(at, listings,
                                                           turns):
    """A list reply that is an error raises WriterError, which escaped
    run_history; the trial then kept nothing. The calendar writer is
    listed once per listing: the 3rd follows session 3, the 8th the
    probes."""
    locus = FakeLocus()
    writer = locus.writers["calendar_agent"]
    calls = []

    def listing(user_id=None):
        calls.append(user_id)
        if len(calls) == at:
            raise WriterError("list: success is false")
        return FakeWriter.list_own_rows(writer, user_id)
    writer.list_own_rows = listing
    _, outcome = run(locus)
    assert outcome.failure == "WriterError: list: success is false"
    assert [s.session for s in outcome.sessions] == list(
        range(1, min(at, 6) + 1))
    assert len(outcome.listings) == listings
    assert len(outcome.turns) == turns
    assert all(t.error is None for t in outcome.turns)  # the probes ran


def test_a_consumer_that_raises_fails_the_user_and_keeps_its_turn():
    """A native or replicated consumer whose search raises: the user
    fails with the exception, and the probe is recorded unscored."""
    user = v2_user()
    locus = FakeLocus()
    real = locus.assistant.run

    def run_probe(question):
        if locus.assistant.probe_id == user.probes[1]["probe_id"]:
            raise RuntimeError("search failed")
        return real(question)
    locus.assistant.run = run_probe
    _, outcome = run(locus, user)
    assert outcome.failure == "RuntimeError: search failed"
    assert len(outcome.sessions) == 6 and len(outcome.listings) == 7
    first, raised = outcome.turns
    assert first.error is None
    assert raised.error == "consumer raised RuntimeError: search failed"
    assert raised.answer == "" and raised.diagnostics is None
    results = history.score_turns(user, outcome, "native")
    assert results[1].error == raised.error and results[1].passed is None
    assert results[1].forbidden == user.probes[1]["forbidden"]


def test_a_writer_that_raises_fails_the_user_and_records_its_session():
    locus = FakeLocus()

    def broken(task_input):
        raise KeyError("events")
    locus.writers["task_agent"].run = broken  # session 2's writer
    _, outcome = run(locus)
    assert outcome.failure == "KeyError: 'events'"
    first, failed = outcome.sessions
    assert first.session == 1 and not first.writer_failed
    assert (failed.session, failed.writer) == (2, "task_agent")
    assert failed.writer_failed and failed.error == "KeyError: 'events'"
    assert failed.events == [] and failed.stored_rows is None
    assert not [e for e in locus.log if e[0] == "probe"]


def test_a_harness_misuse_still_raises():
    """A control the locus cannot run is the caller's error, not the
    user's: it is raised before the history starts."""
    with pytest.raises(ValueError):
        run(history.KernelLocus(), control="no_visibility")


# -- Amendment 2: rows per event from the listings --------------------------

def check_rows_per_event(user, outcome):
    """Each write event holds both facts the store kept for it, from
    the listing; the reply named the first; revokes are untouched."""
    kinds = {e["event_id"]: e["type"]
             for s in user.sessions for e in s["events"]}
    for record in outcome.sessions:
        writes = 0
        for event in record.events:
            if kinds[event["event_id"]] == "revoke":
                assert "reported_ids" not in event
                assert event["deleted_ids"] == event["found_ids"] != []
                continue
            writes += 1
            [first] = event["reported_ids"]
            assert event["memory_ids"][0] == first
            assert event["stored_rows"] == len(event["memory_ids"]) == 2
        assert record.stored_rows == 2 * writes


def test_each_write_event_records_every_row_its_listing_shows():
    """A write Mem0 split into two facts (one reply id): before, the
    event recorded 1 row and the session the reply count."""
    locus = FakeLocus()
    for writer in locus.writers.values():
        writer.facts = 2
    user, outcome = run(locus)
    assert outcome.failure is None
    check_rows_per_event(user, outcome)
    # The fake writer's own reply-based record, kept as it was sent.
    revoke = next(e for s in outcome.sessions for e in s.events
                  if "reported_ids" not in e)
    assert set(revoke) == {"event_id", "found_ids", "deleted_ids"}
    # Each id is a row of the session's writer, in the listing after the
    # session, that carries the event (a later revoke may delete it).
    for record, listing in zip(outcome.sessions, outcome.listings):
        rows = {r["memory_id"]: r for r in listing["rows"][record.writer]}
        for event in record.events:
            for memory_id in event.get("memory_ids") or []:
                assert rows[memory_id]["metadata"][
                    "provenance_event"] == event["event_id"]


def test_kernel_events_record_every_fact_the_kernel_stored():
    """The kernel locus (the real kernel writers, the kernel's replies
    faked): the kernel's Mem0 add names only the first fact."""
    kernel = FakeKernel(facts=2)
    with kernel.patched():
        user, outcome = run(history.KernelLocus())
    assert outcome.failure is None
    check_rows_per_event(user, outcome)
    # These are run_v2_session's records (its keys), not a fake's.
    event = outcome.sessions[0].events[0]
    assert event["type"] == "base" and event["error"] is None


def test_a_failed_session_keeps_its_reported_ids_and_lists_no_rows():
    locus = FakeLocus()
    user = v2_user()
    locus.writers["task_agent"].fail_on = user.sessions[1]["events"][1][
        "event_id"]
    _, outcome = run(locus, user)
    listed, failed = outcome.sessions
    assert listed.stored_rows == 3
    assert [e["stored_rows"] for e in listed.events] == [1, 1, 1]
    # No listing followed the failed session: its rows are unknown.
    assert failed.writer_failed and failed.stored_rows is None
    [base] = failed.events  # the base event ran before the failed add
    assert len(base["reported_ids"]) == 1
    assert base["memory_ids"] is None and base["stored_rows"] is None


def test_a_write_that_stored_nothing_records_zero_rows():
    """A listed session whose write left no row (Mem0 extracting nothing)
    records [] and 0, not None: only a session with no listing has
    unknown rows."""
    locus = FakeLocus()
    user = v2_user()
    session = user.sessions[0]
    empty = session["events"][1]["event_id"]
    locus.writers[session["writer"]].facts_of[empty] = 0
    _, outcome = run(locus, user)
    record = outcome.sessions[0]
    event = next(e for e in record.events if e["event_id"] == empty)
    assert event["memory_ids"] == [] and event["stored_rows"] == 0
    assert event["reported_ids"] == []
    others = [e for e in record.events if e["event_id"] != empty]
    assert record.stored_rows == sum(e["stored_rows"] for e in others) > 0


def test_the_kernel_capture_records_only_creates_the_kernel_accepted():
    """A create the kernel refused fails the writer and is not counted
    as written, as in the agent-managed loci (before, the capture
    recorded it as it was sent)."""
    class RefusingKernel(FakeKernel):
        def create_memory(self, agent_name, content=None, metadata=None,
                          base_url=None, **kwargs):
            if (metadata or {}).get("provenance_event") == self.refused:
                return {"response": {"success": False,
                                     "error": "provider down"}}
            return super().create_memory(agent_name, content, metadata,
                                         base_url, **kwargs)

    kernel = RefusingKernel()
    user = v2_user()
    kernel.refused = user.sessions[0]["events"][1]["event_id"]
    with kernel.patched():
        _, outcome = run(history.KernelLocus(), user)
    assert outcome.failure and "provider down" in outcome.failure
    # Only the base event's create, the one before the refused one.
    assert len(outcome.written) == 1


# -- Amendment 2: agent-managed backend usage -------------------------------

@pytest.mark.parametrize("variants", [
    None, {"profile_agent": "V2"}, {"assistant_agent": "V2"}])
def test_agent_managed_backend_usage_counts_every_user_id_once(variants):
    """Each assistant run takes only its own id's calls. A V2 writer's
    calls (its rewritten id) or, under a V2 consumer, every writer's
    (the base id) were never taken."""
    locus = managed("native", writer=UsageWriter, consumer=UsageConsumer)
    code = "-".join(sorted(variants or {})) or "none"
    user = v2_user().model_copy(update={"user_id": f"usage_{code}_t0"})
    _, outcome = run(locus, user, variants=variants)
    assert outcome.failure is None
    calls = len(history.write_events(user)) + len(user.probes)  # 19 + 6
    assert outcome.backend_llm_tokens.calls == calls
    assert outcome.backend_llm_tokens.total_tokens == 120 * calls
    assert outcome.backend_llm_tokens.models == ["azure/gpt-4o"]
    assert outcome.embedding_tokens.calls == calls
    # Nothing is left under any id the trial used.
    for uid in (user.user_id, f"{user.user_id}@users.example"):
        assert usage.ACCUMULATOR.take(uid, wait=0) == []


# -- Amendment 2: a failed v2 trial's record --------------------------------

def test_a_failed_v2_trial_records_what_ran(tmp_path):
    """run_single_trial_v2: a consumer that raises fails the trial with
    the exception, and the record keeps the user id, the sessions and
    the probes that ran (the errored one unscored); no judge call."""
    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=1)
    o = orchestrator(dataset=str(path))
    o.generator.run_id = "r1"
    o._embed = False
    o.judge = MagicMock()
    locus = FakeLocus()
    real = locus.assistant.run

    def run_probe(question):
        if locus.assistant.probe_id.endswith("p2-privacy"):
            raise RuntimeError("search failed")
        return real(question)
    locus.assistant.run = run_probe

    def run_history_trial(user, variants=None, *, control=None,
                          recency_session=True):
        user = user.model_copy(update={"user_id": USER_ID})
        outcome = history.run_history(
            user, locus, VariantRunner(None, "kernel"), control=control)
        return user, outcome, "kernel"

    trial = o.run_single_trial(
        0, "kernel_shared", SimpleNamespace(
            run_history_trial=run_history_trial), method="kernel_shared")
    assert trial.failed is True
    assert trial.error_message == "RuntimeError: search failed"
    assert trial.user_id == USER_ID and len(trial.sessions) == 6
    deletion, privacy = trial.probe_results
    assert deletion.error is None and deletion.passed is not None
    assert privacy.passed is None
    assert privacy.error == "consumer raised RuntimeError: search failed"
    assert trial.deleted_memory_ids  # the revoke's deletes are recorded
    o.judge.evaluate.assert_not_called()
    again = TrialResult.model_validate_json(trial.model_dump_json())
    assert again.probe_results[1].error == privacy.error


# -- the native consumer's visible stored rows (native cap_bound) ------------

class NativeRulesConsumer(FakeConsumer):
    """The native consumer's own rules over the store
    (``native/sharing.py``): the rows of the partition it serves, only
    the visible ones unless ``check_visibility`` is off, and
    ``visibility_checked`` in its diagnostics. It writes its
    conversation through ``memory.write``, where V3 strips metadata."""

    def __init__(self, store, log, **options):
        super().__init__(store, log, **options)
        self.check_visibility = True
        self.memory = SimpleNamespace(write=self._write)

    def _write(self, messages, text, agent_name, metadata):
        return self.store.add(agent_name, text, metadata)

    def run(self, question):
        self.log.append(("probe", self.session, self.probe_id))
        rows = [r for r in self.store.rows.values()
                if in_partition(self.user_id, r["metadata"])
                and (not self.check_visibility
                     or visible(history.CONSUMER, r["metadata"]))]
        diagnostics = dict(block_diagnostics(rows, self.session,
                                             self.user_id),
                           visibility_checked=self.check_visibility)
        answer = self.answer(question)
        self.memory.write(
            [{"role": "user", "content": question}],
            f"User: {question}\nAssistant: {answer}", history.CONSUMER,
            {"user_id": self.user_id, "session": self.session,
             "provenance_event": self.probe_id,
             "owner_agent": history.CONSUMER, "sharing_policy": "private"})
        return {"result": answer, "injection_diagnostics": diagnostics,
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                "total_tokens": 15}}


@pytest.mark.parametrize("variants, control, partition, all_policies", [
    (None, None, "base", False),
    ({"assistant_agent": "V2"}, None, "alias", False),
    ({"assistant_agent": "V3"}, None, "base", True),
    (None, "no_visibility", "base", True),
])
def test_native_visible_rows_follow_the_consumers_partition_and_visibility(
        variants, control, partition, all_policies):
    """visible_stored_rows counts what the native consumer could fetch:
    the writers' rows in the partition it searched (a V2 consumer's is
    its rewritten id, which holds none of them) and, when it does not
    check visibility (V3, no_visibility), the private ones too; plus
    its own rows when the probe began. It used to count the writers'
    shared rows under the base id for every consumer."""
    locus = managed("native", consumer=NativeRulesConsumer)
    user = v2_user()
    _, outcome = run(locus, user, control=control, variants=variants)
    assert outcome.failure is None
    uid = user.user_id if partition == "base" else \
        f"{user.user_id}@users.example"
    listed = next(l for l in outcome.listings
                  if l["after"] == "history")["rows"]
    metadata = [r["metadata"] for name in history.WRITERS
                for r in listed.get(name, [])]
    expected = sum(1 for m in metadata if m.get("user_id") == uid and (
        all_policies or m.get("sharing_policy") == "shared"))
    shared_base = sum(1 for m in metadata if m.get("user_id") ==
                      user.user_id and m.get("sharing_policy") == "shared")
    if variants is None and control is None:
        assert expected == shared_base  # the reference count is unchanged
    elif all_policies:
        assert expected > shared_base  # the user's private fact
    else:
        assert expected == 0 < shared_base  # the V2 alias holds none
    results = history.score_turns(user, outcome, "native")
    for turn, result in zip(outcome.turns, results):
        assert result.diagnostics.visibility_checked is (not all_policies)
        assert result.visible_stored_rows == (
            expected + turn.consumer_rows_before)
        # The fake injects every row it can see, so its own count checks
        # both halves, its own rows (a V2 consumer's, under its alias)
        # included.
        assert result.visible_stored_rows == (
            result.diagnostics.injected_count)
