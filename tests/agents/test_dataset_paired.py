"""Subtask 9: the fixed dataset and the paired comparison."""
import json
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import compare, dataset, models
from benchmarks.shared_memory.pipeline import PipelineResult


def test_users_v1_is_committed_with_its_generation_record():
    users = dataset.load("users_v1")
    assert len(users) == 150
    header = users.header
    assert header["seed"] == 20261104
    assert header["model"] == "azure/gpt-4o"
    assert header["date"] and header["generator_sha256"]
    assert len({u["profile"]["user_name"] for u in users.users}) == 150


def test_pilot_v1_is_the_first_30_users():
    pilot, full = dataset.load("pilot_v1"), dataset.load("users_v1")
    assert len(pilot) == 30
    assert pilot.users == full.users[:30]
    assert pilot.sha256 == full.sha256  # one file


def test_random_is_no_dataset():
    assert dataset.load("random") is None


def orchestrator(tmp_path, spec, run_id, trials=None):
    from benchmarks.shared_memory.run_evaluation import (
        EvaluationOrchestrator,
    )

    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        return EvaluationOrchestrator(
            trials=trials, output_dir=str(tmp_path), write_csv=False,
            condition=None, method="kernel_shared", run_id=run_id,
            dataset=spec,
        )


def run_cell(tmp_path, run_id):
    """Run one cell on pilot_v1 with the pipeline and judge mocked, and
    return what the pipeline received and the results file."""
    received = []

    def run_trial(trial_data):
        received.append(trial_data)
        return PipelineResult(
            profile_result={}, task_result={}, assistant_result={},
            assistant_response="r", latency_seconds=1.0,
        )

    out = tmp_path / run_id
    orch = orchestrator(out, "pilot_v1", run_id)
    from tests.agents.test_judge_prompt_v2 import llm_scores

    with patch("benchmarks.shared_memory.run_evaluation.MethodPipeline") \
            as pipeline, patch.object(models.requests, "get") as get, \
            patch.object(orch.judge, "evaluate",
                         return_value=llm_scores(4)):
        get.return_value.json.return_value = {}
        pipeline.return_value.run_trial.side_effect = run_trial
        orch.run()
    data = json.loads((out / "results_kernel_shared.json").read_text())
    return received, data


def test_two_runs_of_a_cell_see_identical_users_and_inputs(tmp_path):
    first, data_a = run_cell(tmp_path, "run-a")
    second, data_b = run_cell(tmp_path, "run-b")
    assert len(first) == len(second) == 30
    for i, (a, b) in enumerate(zip(first, second)):
        assert a.profile == b.profile
        assert a.task_context == b.task_context
        assert a.follow_up_query == b.follow_up_query
        assert a.user_id.endswith(f"_run-a_t{i}")
        assert b.user_id.endswith(f"_run-b_t{i}")
    trials_a = data_a["conditions"][0]["trials"]
    trials_b = data_b["conditions"][0]["trials"]
    assert [t["trial_index"] for t in trials_a] == list(range(30))
    assert [t["input_sha256"] for t in trials_a] == \
        [t["input_sha256"] for t in trials_b]
    assert len({t["input_sha256"] for t in trials_a}) == 30
    assert {t["dataset"] for t in trials_a} == {"pilot_v1"}
    meta = data_a["experiment_metadata"]["dataset"]
    assert meta["name"] == "pilot_v1" and meta["seed"] == 20261104


def test_trials_default_to_the_dataset_and_cannot_exceed_it(tmp_path):
    assert orchestrator(tmp_path, "pilot_v1", "r").trials == 30
    assert orchestrator(tmp_path, "random", "r").trials == 10
    with pytest.raises(ValueError):
        orchestrator(tmp_path, "pilot_v1", "r", trials=31)


def test_random_still_generates_per_trial(tmp_path):
    orch = orchestrator(tmp_path, "random", "r")
    with patch.object(orch.generator, "generate_trial_data",
                      return_value="generated") as generate:
        assert orch.trial_data(3) == "generated"
    generate.assert_called_once_with(3)


# --- paired comparison -------------------------------------------------

def trial(index, score, failed=False, sha="h", writer_failed=()):
    return {"trial_index": index, "profile_usage_score": score,
            "task_usage_score": score, "integration_score": score,
            "failed": failed, "input_sha256": f"{sha}{index}",
            "writer_failed": list(writer_failed),
            "error_message": "writer_failed: task_agent"
            if writer_failed else None}


def write_cell(path, trials, sha="d1"):
    path.write_text(json.dumps({
        "experiment_metadata": {"dataset": {"name": "pilot_v1",
                                            "sha256": sha}},
        "conditions": [{"trials": trials}],
    }))
    return path


def test_paired_stats_match_known_values():
    a = [3, 4, 4, 5, 3, 4]
    b = [4, 4, 5, 5, 4, 5]
    cell = compare.paired_stats(a, b)
    assert cell["n"] == 6
    assert cell["diff"] == pytest.approx(4 / 6)
    from scipy import stats

    assert cell["t_p"] == pytest.approx(stats.ttest_rel(b, a).pvalue)
    assert cell["n_nonzero"] == 4
    assert cell["ci_low"] < cell["diff"] < cell["ci_high"]


def test_identical_cells_are_a_tie():
    cell = compare.paired_stats([4, 5, 3], [4, 5, 3])
    assert cell["diff"] == 0 and cell["t_p"] == 1.0
    assert cell["wilcoxon_p"] == 1.0 and cell["tost_p"] == 0.0


def test_pairs_drop_users_failed_in_either_cell(tmp_path):
    a = write_cell(tmp_path / "a.json",
                   [trial(0, 4), trial(1, 3), trial(2, 5), trial(3, 4)])
    b = write_cell(tmp_path / "b.json", [
        trial(0, 5), trial(1, 3, failed=True, writer_failed=["task_agent"]),
        trial(2, 4), trial(3, 4),
    ])
    result = compare.compare(a, b)
    assert result["pairs"] == 3
    assert result["excluded"] == {"writer_failed": 1}
    assert result["dimensions"]["profile"]["diff"] == pytest.approx(0)


def test_mismatched_inputs_or_datasets_are_errors(tmp_path):
    a = write_cell(tmp_path / "a.json", [trial(0, 4), trial(1, 4)])
    b = write_cell(tmp_path / "b.json",
                   [trial(0, 4, sha="x"), trial(1, 4, sha="x")])
    with pytest.raises(ValueError, match="inputs differ"):
        compare.compare(a, b)
    c = write_cell(tmp_path / "c.json", [trial(0, 4), trial(1, 4)],
                   sha="d2")
    with pytest.raises(ValueError, match="different datasets"):
        compare.compare(a, c)
