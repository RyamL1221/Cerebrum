"""Subtask 10: a backend that extracts facts but stored or called nothing
fails the trial.

Mem0 (infer=True) logs and swallows its extraction LLM's errors: from a
network Azure refused, a native Mem0 cell ran 5 trials with 0 backend
LLM calls and 0 injected rows, every trial "completed". Each writer now
reports the rows its write stored, and the orchestrator fails a trial
whose backend extracts when a successful writer stored no row or the
backend recorded no LLM call.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from benchmarks.shared_memory import models
from benchmarks.shared_memory.models import SyntheticTrialData, TokenUsage
from benchmarks.shared_memory.pipeline import (
    AgentPipeline,
    PipelineResult,
    extraction_failure,
    writer_stored,
    writes_without_fact,
)
from cerebrum.example.agents.native.agents import (
    NativeMemory,
    NativeProfileAgent,
)
from cerebrum.example.agents.profile_agent import agent as profile_module
from cerebrum.example.agents.replicated.agents import ReplicatedTaskAgent
from cerebrum.example.agents.task_agent import agent as task_module
from tests.agents.test_writer_parity import (
    PROFILE,
    TASK,
    replicated_memory,
    replies,
)

CALLED = TokenUsage(calls=2, prompt_tokens=10, total_tokens=10)


# --- the rule ------------------------------------------------------------

def test_no_extraction_backend_is_never_flagged():
    assert extraction_failure(False, {"profile_agent": 0}, TokenUsage()) \
        is None
    assert extraction_failure(None, {}, None) is None


def test_a_writer_that_stored_no_row_fails():
    reason = extraction_failure(
        True, {"profile_agent": 0, "task_agent": 1}, CALLED,
    )
    assert reason == ("backend_extraction_failed: stored no rows: "
                      "profile_agent")


def test_no_backend_llm_call_fails():
    """The Azure-blocked native Mem0 cell: rows unknown, 0 calls."""
    reason = extraction_failure(True, {}, TokenUsage())
    assert reason == ("backend_extraction_failed: no backend LLM calls "
                      "recorded")


def test_stored_rows_and_calls_pass():
    assert extraction_failure(
        True, {"profile_agent": 3, "task_agent": 1}, CALLED,
    ) is None


def test_a_graphiti_writer_that_stored_no_row_is_a_loss():
    """Amendment 5 (Subtask 16): Graphiti raises on an extraction error,
    so its empty write found no fact; it is recorded, not a failure.
    Mem0 swallows its errors: the same write still fails."""
    stored = {"profile_agent": 0, "task_agent": 1}
    assert extraction_failure(True, stored, CALLED, "graphiti") is None
    assert writes_without_fact(True, stored, "graphiti") == [
        "profile_agent"]
    assert writes_without_fact(False, stored, "graphiti") == []
    assert extraction_failure(True, stored, CALLED, "mem0") == (
        "backend_extraction_failed: stored no rows: profile_agent")
    assert writes_without_fact(True, stored, "mem0") == []


def test_a_graphiti_trial_with_no_backend_call_still_fails():
    assert extraction_failure(
        True, {"profile_agent": 0}, TokenUsage(), "graphiti",
    ) == "backend_extraction_failed: no backend LLM calls recorded"


def test_writer_stored_skips_writers_that_do_not_report():
    assert writer_stored(
        {"agent_name": "profile_agent", "stored_rows": 0},
        {"agent_name": "task_agent", "stored_rows": None},
        {"agent_name": "x"},
    ) == {"profile_agent": 0}


# --- every locus reports what it stored ------------------------------------

class SwallowingMem0:
    """Mem0's ``add`` when its extraction LLM call raised: logged, and
    an empty result."""

    def __init__(self, results):
        self.results = results

    def add(self, *args, **kwargs):
        return {"results": self.results}


def native_memory(results):
    memory = object.__new__(NativeMemory)
    memory.backend = "mem0"
    memory.backend_extraction = True
    memory.mem0 = SwallowingMem0(results)
    return memory


@pytest.mark.parametrize("results,stored", [
    ([], 0), ([{"id": "a"}, {"id": "b"}], 2),
])
def test_native_mem0_writer_reports_extracted_rows(results, stored):
    agent = NativeProfileAgent("profile_agent", native_memory(results))
    agent.user_id = "u1"
    with patch.object(profile_module, "llm_chat_with_json_output",
                      side_effect=replies(PROFILE)):
        result = agent.run("input")
    assert result["writer_failed"] is False
    assert result["stored_rows"] == stored


@pytest.mark.parametrize("memory_id,stored", [("", 0), ("r1", 1)])
def test_replicated_writer_reports_a_create_that_kept_nothing(
    memory_id, stored,
):
    memory = replicated_memory()
    memory.pipeline.write = lambda *a, **k: memory_id
    agent = ReplicatedTaskAgent("task_agent", memory)
    agent.user_id = "u1"
    with patch.object(task_module, "llm_chat_with_json_output",
                      side_effect=replies(TASK)):
        result = agent.run("input")
    assert result["stored_rows"] == stored


@pytest.mark.parametrize("memory_id,stored", [("", 0), ("k1", 1)])
def test_kernel_writer_reports_an_empty_memory_id(memory_id, stored):
    """The kernel answers an add whose extraction kept nothing with
    ``memory_id: ""``."""
    agent = task_module.TaskAgent("task_agent")
    agent.user_id, agent.share_memory = "u1", True
    with patch.object(task_module, "llm_chat_with_json_output",
                      side_effect=replies(TASK)), \
            patch.object(task_module, "search_memories", return_value={}), \
            patch.object(task_module, "create_memory", return_value={
                "response": {"memory_id": memory_id}}):
        result = agent.run("input")
    assert result["stored_rows"] == stored


# --- the orchestrator fails the trial --------------------------------------

def orchestrate(tmp_path, method, **fields):
    from benchmarks.shared_memory.run_evaluation import (
        EvaluationOrchestrator,
    )
    from tests.agents.test_judge_prompt_v2 import PROFILE as P, TASK as T

    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        orchestrator = EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path), write_csv=False,
            condition=None, method=method,
        )
    orchestrator.judged = False
    pipeline = SimpleNamespace(run_trial=lambda _d: PipelineResult(
        profile_result={}, task_result={}, assistant_result={},
        assistant_response="ok", latency_seconds=0.1, **fields,
    ))
    data = SyntheticTrialData(profile=P, task_context=T,
                              follow_up_query="q", user_id="u")
    with patch.object(models.requests, "get"):
        return orchestrator.run_single_trial(
            0, method, pipeline, method=method, trial_data=data,
        )


def test_native_trial_with_no_backend_call_is_failed(tmp_path):
    trial = orchestrate(
        tmp_path, "native_mem0", backend_extraction=True,
        writer_stored_rows={"profile_agent": 1, "task_agent": 1},
        backend_llm_tokens=TokenUsage(), embedding_tokens=TokenUsage(),
    )
    assert trial.failed
    assert trial.error_message.startswith("backend_extraction_failed")
    assert trial.writer_stored_rows == {"profile_agent": 1,
                                        "task_agent": 1}


def test_kernel_trial_with_an_empty_write_is_failed(tmp_path):
    with patch("benchmarks.shared_memory.run_evaluation."
               "read_backend_usage", return_value={
                   "backend_llm_tokens": CALLED,
                   "embedding_tokens": TokenUsage()}):
        trial = orchestrate(
            tmp_path, "kernel_shared", backend_extraction=True,
            writer_stored_rows={"profile_agent": 0, "task_agent": 1},
            backend_usage_user_id="u",
        )
    assert trial.failed
    assert trial.error_message == (
        "backend_extraction_failed: stored no rows: profile_agent")


def test_kernel_graphiti_trial_with_an_empty_write_is_scored(tmp_path):
    with patch("benchmarks.shared_memory.run_evaluation."
               "read_backend_usage", return_value={
                   "backend_llm_tokens": CALLED,
                   "embedding_tokens": TokenUsage()}):
        trial = orchestrate(
            tmp_path, "kernel_shared", backend_extraction=True,
            memory_backend="graphiti",
            writer_stored_rows={"profile_agent": 0, "task_agent": 1},
            backend_usage_user_id="u",
        )
    assert not trial.failed, trial.error_message
    assert trial.writes_without_fact == ["profile_agent"]


def test_the_kernel_memory_backend_is_its_provider():
    with patch.object(AgentPipeline, "_kernel_memory_config",
                      return_value={"provider": "graphiti"}):
        assert AgentPipeline._kernel_memory_backend() == "graphiti"
    with patch.object(AgentPipeline, "_kernel_memory_config",
                      side_effect=requests.ConnectionError("down")):
        assert AgentPipeline._kernel_memory_backend() is None


def test_healthy_and_non_extracting_trials_complete(tmp_path):
    healthy = orchestrate(
        tmp_path, "native_mem0", backend_extraction=True,
        writer_stored_rows={"profile_agent": 2, "task_agent": 1},
        backend_llm_tokens=CALLED, embedding_tokens=TokenUsage(),
    )
    inhouse = orchestrate(
        tmp_path, "native_inhouse", backend_extraction=False,
        writer_stored_rows={"profile_agent": 1, "task_agent": 1},
        backend_llm_tokens=TokenUsage(), embedding_tokens=TokenUsage(),
    )
    assert not healthy.failed and not inhouse.failed
