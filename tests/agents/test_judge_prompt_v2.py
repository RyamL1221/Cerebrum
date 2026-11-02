"""Tests for the condition-neutral judge prompt (version 2), its
recorded hash, and re-judging stored responses."""

import json
from string import Template
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import judge, models, rejudge
from benchmarks.shared_memory.conditions import CONDITION_ALIASES, CONDITIONS
from benchmarks.shared_memory.judge import (
    JUDGE_PROMPT_VERSION,
    HybridJudge,
    LLMJudge,
    judge_prompt_sha256,
)
from benchmarks.shared_memory.models import (
    ConditionResults,
    ExperimentMetadata,
    ExperimentResults,
    JudgeScores,
    SyntheticProfile,
    SyntheticTaskContext,
    TrialResult,
)
from benchmarks.shared_memory.results import ResultsWriter

PROFILE = SyntheticProfile(
    user_name="Ana Li",
    preferred_tools=["vim", "git"],
    preferred_language="Go",
    response_style="terse",
)
TASK = SyntheticTaskContext(
    current_project="web server",
    active_experiment="load test",
    goals=["handle 10k connections"],
    blockers=["tail latency"],
    next_steps=["add pooling"],
)
FORBIDDEN = (
    "kernel", "injected", "injection", "shared memor",
    *CONDITIONS, *CONDITION_ALIASES,
)


def prompt_text():
    messages = LLMJudge()._build_judge_prompt(
        "How do I speed it up?", "Use pooling.", PROFILE, TASK
    )
    assert [m["role"] for m in messages] == ["system", "user"]
    return " ".join(m["content"] for m in messages).lower()


def test_prompt_names_no_mechanism_or_condition():
    text = prompt_text()
    for word in FORBIDDEN:
        assert word.lower() not in text, word


def test_prompt_keeps_the_rubric():
    text = prompt_text()
    for section in ("profile usage (1-5)", "task usage (1-5)",
                    "integration (1-5)"):
        assert section in text
    assert "ana li" in text and "web server" in text


def test_sha_changes_with_the_system_prompt(monkeypatch):
    before = judge_prompt_sha256()
    monkeypatch.setattr(judge, "SYSTEM_PROMPT", judge.SYSTEM_PROMPT + " ")
    assert judge_prompt_sha256() != before


def test_sha_changes_with_the_user_template(monkeypatch):
    before = judge_prompt_sha256()
    monkeypatch.setattr(
        judge, "USER_PROMPT_TEMPLATE",
        Template(judge.USER_PROMPT_TEMPLATE.template.replace("5 =", "5:")),
    )
    assert judge_prompt_sha256() != before


def test_sha_is_stable():
    assert judge_prompt_sha256() == judge_prompt_sha256()
    assert len(judge_prompt_sha256()) == 64


def trial(index, failed=False):
    return TrialResult(
        trial_index=index,
        condition=next(iter(CONDITION_ALIASES)),
        method=next(iter(CONDITION_ALIASES)),
        profile_usage_score=None if failed else 1,
        task_usage_score=None if failed else 1,
        integration_score=None if failed else 1,
        follow_up_query="q",
        assistant_response="Use vim and Go for the web server.",
        synthetic_profile=PROFILE,
        synthetic_task_context=TASK,
        failed=failed,
    )


def experiment(trials):
    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        metadata = ExperimentMetadata(
            trials_per_condition=len(trials),
            timestamp="t",
            kernel_url="u",
            conditions_run=[trials[0].condition],
            methods_run=[trials[0].method],
        )
    summary = ResultsWriter(".").compute_summary_statistics(trials)
    return ExperimentResults(
        experiment_metadata=metadata,
        conditions=[ConditionResults(
            condition=trials[0].condition, trials=trials, summary=summary,
        )],
    )


def llm_scores(value):
    return JudgeScores(
        profile_usage_score=value,
        task_usage_score=value,
        integration_score=value,
    )


def test_rejudge_rescores_and_records_the_prompt():
    source = experiment([trial(3), trial(5), trial(8, failed=True)])
    hybrid = HybridJudge()
    with patch.object(hybrid.llm_judge, "evaluate",
                      return_value=llm_scores(5)) as evaluate:
        result = rejudge.rejudge_experiment(source, hybrid, "src.json", "j")
    assert evaluate.call_count == 2  # the failed trial is not judged
    trials = result.conditions[0].trials
    assert [t.trial_index for t in trials] == [3, 5, 8]
    expected = HybridJudge.combine(
        trials[0].assistant_response, PROFILE, TASK, llm_scores(5)
    )
    assert trials[0].profile_usage_score == expected.profile_usage_score
    assert trials[0].profile_usage_score > 1
    assert trials[2].failed and trials[2].profile_usage_score is None
    assert {t.method for t in trials} == {"kernel_private"}
    assert result.conditions[0].condition == "kernel_private"
    meta = result.experiment_metadata
    assert meta.judge_prompt_version == JUDGE_PROMPT_VERSION == 2
    assert meta.judge_prompt_sha256 == judge_prompt_sha256()
    assert meta.methods_run == ["kernel_private"]
    assert meta.rejudge["source_judge_prompt_version"] == 1
    assert meta.git_commit == source.experiment_metadata.git_commit


def test_rejudge_fails_a_trial_instead_of_keyword_fallback():
    source = experiment([trial(0)])
    hybrid = HybridJudge()
    with patch.object(hybrid.llm_judge, "evaluate",
                      return_value=JudgeScores()) as evaluate:
        result = rejudge.rejudge_experiment(source, hybrid, "src.json", "j")
    assert evaluate.call_count == rejudge.RETRIES
    only = result.conditions[0].trials[0]
    assert only.failed and only.integration_score is None


def test_rejudge_main_writes_under_the_new_name(tmp_path):
    old_name = next(iter(CONDITION_ALIASES))
    cell = tmp_path / "in" / f"qwen_{old_name}"
    cell.mkdir(parents=True)
    source = cell / f"results_{old_name}.json"
    source.write_text(experiment([trial(0)]).model_dump_json())
    argv = ["rejudge", str(source), "--output", str(tmp_path / "out"),
            "--judge-model", "gpt-5.4:azure", "--workers", "1"]
    with patch("sys.argv", argv), patch.object(
        LLMJudge, "evaluate", return_value=llm_scores(4)
    ):
        rejudge.main()
    out = tmp_path / "out" / "qwen_kernel_private" / \
        "results_kernel_private.json"
    data = json.loads(out.read_text())
    assert data["experiment_metadata"]["judge_prompt_sha256"] == \
        judge_prompt_sha256()
    assert rejudge.complete(out, 1)


def test_new_results_record_the_prompt(tmp_path):
    from benchmarks.shared_memory.pipeline import PipelineResult
    from benchmarks.shared_memory.run_evaluation import EvaluationOrchestrator

    trial_data = models.SyntheticTrialData(
        profile=PROFILE, task_context=TASK, follow_up_query="q",
        plausible_actions=["a"], user_id="u",
    )
    with patch(
        "benchmarks.shared_memory.run_evaluation.SyntheticDataGenerator"
    ) as generator, patch(
        "benchmarks.shared_memory.run_evaluation.MethodPipeline"
    ) as pipeline, patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        generator.return_value.generate_trial_data.return_value = trial_data
        pipeline.return_value.run_trial.return_value = PipelineResult(
            profile_result={}, task_result={}, assistant_result={},
            assistant_response="r", latency_seconds=1.0,
        )
        orchestrator = EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path), write_csv=False,
            condition=None, method="kernel_private",
        )
        with patch.object(orchestrator.judge, "evaluate",
                          return_value=llm_scores(3)):
            orchestrator.run()
    data = json.loads((tmp_path / "results_kernel_private.json").read_text())
    meta = data["experiment_metadata"]
    assert meta["judge_prompt_version"] == 2
    assert meta["judge_prompt_sha256"] == judge_prompt_sha256()
    assert data["conditions"][0]["trials"][0]["plausible_actions"] == ["a"]


def test_old_results_load_without_prompt_fields():
    meta = ExperimentMetadata.model_validate({
        "trials_per_condition": 1, "timestamp": "t", "kernel_url": "u",
        "conditions_run": [], "config_snapshot": {}, "git_commit": None,
        "kernel_git_commit": None,
    })
    assert meta.judge_prompt_version is None
    assert meta.judge_prompt_sha256 is None


@pytest.mark.parametrize("value", [1, 5])
def test_hybrid_evaluate_matches_combine(value):
    hybrid = HybridJudge()
    with patch.object(hybrid.llm_judge, "evaluate",
                      return_value=llm_scores(value)):
        scores = hybrid.evaluate("q", "Use vim.", PROFILE, TASK)
    expected = HybridJudge.combine("Use vim.", PROFILE, TASK,
                                   llm_scores(value))
    assert scores == expected
