"""Subtask 4b: the judge retries, then fails the trial; it never scores
on keywords alone."""

from unittest.mock import patch

import pytest

from benchmarks.shared_memory import models
from benchmarks.shared_memory.judge import (
    JUDGE_RETRIES,
    SCORER,
    HybridJudge,
    JudgeFailed,
)
from benchmarks.shared_memory.models import JudgeScores, SyntheticTrialData
from benchmarks.shared_memory.pipeline import PipelineResult

from tests.agents.test_judge_prompt_v2 import PROFILE, TASK, llm_scores


def test_combine_refuses_missing_llm_scores():
    with pytest.raises(ValueError):
        HybridJudge.combine("Use vim.", PROFILE, TASK, JudgeScores())


def test_evaluate_retries_then_raises():
    hybrid = HybridJudge()
    with patch.object(hybrid.llm_judge, "evaluate",
                      return_value=JudgeScores()) as evaluate:
        with pytest.raises(JudgeFailed) as raised:
            hybrid.evaluate("q", "Use vim.", PROFILE, TASK)
    assert evaluate.call_count == JUDGE_RETRIES
    assert raised.value.attempts == JUDGE_RETRIES


def test_evaluate_counts_attempts():
    hybrid = HybridJudge()
    with patch.object(hybrid.llm_judge, "evaluate",
                      side_effect=[JudgeScores(), llm_scores(4)]):
        scores = hybrid.evaluate("q", "Use vim.", PROFILE, TASK)
    assert scores.judge_attempts == 2
    assert scores.profile_usage_score is not None


def _orchestrator(tmp_path):
    from benchmarks.shared_memory.run_evaluation import EvaluationOrchestrator

    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        return EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path), write_csv=False,
            condition=None, method="kernel_shared",
        )


def _trial(orchestrator, llm_side_effect):
    data = SyntheticTrialData(
        profile=PROFILE, task_context=TASK, follow_up_query="q",
        user_id="u",
    )
    pipeline = type("P", (), {})()
    pipeline.run_trial = lambda _data: PipelineResult(
        profile_result={}, task_result={}, assistant_result={},
        assistant_response="Use vim.", latency_seconds=1.0,
    )
    with patch.object(orchestrator.judge.llm_judge, "evaluate",
                      side_effect=llm_side_effect) as evaluate, \
            patch.object(models.requests, "get"):
        trial = orchestrator.run_single_trial(
            0, "kernel_shared", pipeline, method="kernel_shared",
            trial_data=data,
        )
    return trial, evaluate


def test_judge_failure_after_retries_fails_the_trial(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    trial, evaluate = _trial(
        orchestrator, [JudgeScores()] * JUDGE_RETRIES
    )
    assert evaluate.call_count == JUDGE_RETRIES
    assert trial.failed
    assert trial.judge_attempts == JUDGE_RETRIES
    assert trial.profile_usage_score is None
    assert trial.task_usage_score is None
    assert trial.integration_score is None
    assert trial.scorer is None
    # The response is kept, so the trial can be re-judged later.
    assert trial.assistant_response == "Use vim."


def test_scored_trial_records_scorer_and_attempts(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    trial, _ = _trial(orchestrator, [JudgeScores(), llm_scores(5)])
    assert not trial.failed
    assert trial.scorer == SCORER
    assert trial.judge_attempts == 2
