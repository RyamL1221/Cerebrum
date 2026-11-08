"""Benchmark v2's harness (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Harness"): session ordering, the probes after
the history, the failure rules, the controls, what a revoke leaves
behind, and the probe_results schema, over an in-memory fake locus."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.shared_memory import dataset, history, run_evaluation, synth_v2
from benchmarks.shared_memory.models import (
    ProbeResult,
    TrialResult,
    V2UserData,
)
from benchmarks.shared_memory.pipeline import VariantRunner

BASE = dataset.load("users_v1")
USER_ID = "jordan_r1_t0__kernel_shared"


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


class FakeWriter:
    def __init__(self, name, store, log):
        self.name, self.store, self.log = name, store, log
        self.user_id = None
        self.delete_on_revoke = True
        self.fail_on = None

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
            mid = self.store.add(self.name, event["utterance"], {
                "user_id": self.user_id, "fact_key": event["fact_key"],
                "session": session["session"],
                "provenance_event": event["event_id"],
                "sharing_policy": "private" if event["type"] == "private"
                else "shared"})
            stored += 1
            events.append({"event_id": event["event_id"],
                           "memory_ids": [mid]})
        return {"agent_name": self.name, "user_id": self.user_id,
                "events": events, "stored_rows": stored,
                "deleted_ids": deleted, "writer_failed": False,
                "error": None, "written": []}

    def list_own_rows(self, user_id=None):
        return self.store.own(self.name, user_id or self.user_id)


class FakeConsumer:
    def __init__(self, store, log, answer=None, diagnostics=None):
        self.store, self.log = store, log
        self.user_id, self.session, self.probe_id = None, None, None
        self.answer = answer or (lambda q: f"An answer to: {q}")
        self.diagnostics = diagnostics

    def run(self, question):
        self.log.append(("probe", self.session, self.probe_id))
        rows = [r for r in self.store.rows.values()
                if r["metadata"].get("user_id") == self.user_id]
        diagnostics = self.diagnostics or {
            "injected_count": len(rows), "session": self.session,
            "block_recency_unit": "session",
            "resolved_user_id": self.user_id,
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

    def backend_usage(self, turns):
        return None, None

    def finish_user(self):
        pass


def run(locus, user=None, control=None):
    user = user or v2_user()
    outcome = history.run_history(user, locus, VariantRunner(None, "kernel"),
                                  control=control)
    return user, outcome


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
