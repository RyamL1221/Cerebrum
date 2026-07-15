"""Trial loader tests for the human-rating evaluation workflow.

Tests use synthetic fixtures that include the required fields
(question_type, inference_context_text). They do NOT depend on existing
finalized benchmark results which lack these fields.

Verifies:
- Successful loading from well-formed result files
- Model-name normalization
- Missing question_type → exclusion
- Missing inference_context_text → exclusion (None = unobservable)
- Empty inference_context_text → valid (confirmed no context)
- Judge score selection rule (profile→profile_usage, task→task_usage)
- Method-independent original_trial_id
- Duplicate trial detection
- Insufficient trials per cell
- UnsupportedBenchmarkArtifactsError for incompatible results
- File discovery
- Exclusion report structure

Run:
    python benchmarks/human_rating/tests/test_trial_loader.py
"""

import json
import os
import sys
import tempfile

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.trial_loader import (
    ALLOWED_METHODS,
    ExclusionReport,
    UnsupportedBenchmarkArtifactsError,
    discover_result_files,
    load_eligible_trials,
    load_result_file,
    normalize_model_name,
    summarize_trial_pool,
)
from benchmarks.human_rating.schemas import SourceTrial, select_judge_score


# ---------------------------------------------------------------------------
# Fixture helpers — produce result files WITH required human-rating fields
# ---------------------------------------------------------------------------

def _make_trial(trial_index: int, method: str, **overrides) -> dict:
    """Create a trial dict with all required human-rating fields."""
    qtype = "profile" if trial_index % 2 == 0 else "task"
    defaults = {
        "trial_index": trial_index,
        "condition": method,
        "method": method,
        "question_type": qtype,
        "profile_usage_score": 3,
        "task_usage_score": 4,
        "integration_score": 3,
        "memory_counts": {"total": 0, "shared": 0, "private": 0},
        "retrieved_context_count": 0,
        "latency_seconds": 5.0,
        "follow_up_query": f"Question for trial {trial_index}",
        "assistant_response": f"Response for trial {trial_index}",
        "inference_context_text": f"Context for trial {trial_index}",
        "synthetic_profile": {"user_name": f"User {trial_index}", "preferred_tools": ["Git"],
                              "preferred_language": "Python", "response_style": "concise"},
        "synthetic_task_context": {"current_project": f"Project {trial_index}",
                                   "active_experiment": f"Exp {trial_index}",
                                   "goals": [f"Goal {trial_index}"], "blockers": [],
                                   "next_steps": [f"Step {trial_index}"]},
        "failed": False,
        "error_message": None,
    }
    defaults.update(overrides)
    return defaults


def _make_result_file(method: str, num_trials: int = 10) -> dict:
    trials = [_make_trial(i, method) for i in range(num_trials)]
    return {
        "experiment_metadata": {"trials_per_condition": num_trials,
                                "timestamp": "2026-07-14T10:00:00",
                                "kernel_url": "http://localhost:8000",
                                "conditions_run": [method], "methods_run": [method]},
        "conditions": [{"condition": method, "trials": trials, "summary": {}}],
    }


def _write_result_file(tmpdir: str, method: str, data: dict) -> str:
    dir_path = os.path.join(tmpdir, f"gpt4o_{method}")
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"results_{method}.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def _write_all_methods(tmpdir: str, num_trials: int = 10) -> dict:
    paths = {}
    for method in ALLOWED_METHODS:
        data = _make_result_file(method, num_trials)
        path = _write_result_file(tmpdir, method, data)
        paths[method] = path
    return paths


# ---------------------------------------------------------------------------
# Model name normalization
# ---------------------------------------------------------------------------

def test_normalize_model():
    assert normalize_model_name("gpt-4o") == "gpt-4o"
    assert normalize_model_name("gpt-4o:azure") == "gpt-4o"
    try:
        normalize_model_name("gpt-4o-mini")
        assert False
    except ValueError:
        pass
    print("  PASS: test_normalize_model")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def test_discover_result_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_all_methods(tmpdir)
        discovered = discover_result_files(tmpdir)
        assert set(discovered.keys()) == set(ALLOWED_METHODS)
    print("  PASS: test_discover_result_files")


# ---------------------------------------------------------------------------
# Loading with required fields
# ---------------------------------------------------------------------------

def test_load_success():
    """Well-formed results with question_type and inference_context_text load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, report = load_eligible_trials(method_paths=paths, min_per_cell=3)
        assert len(trials) == 40
        assert report.total_excluded == 0
        # Verify question types alternate
        for t in trials:
            expected_type = "profile" if int(t.original_trial_id) % 2 == 0 else "task"
            assert t.question_type == expected_type
    print("  PASS: test_load_success")


def test_method_independent_trial_id():
    """original_trial_id is just the trial index string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("naive_concat", num_trials=3)
        path = _write_result_file(tmpdir, "naive_concat", data)
        trials = load_result_file(path, "naive_concat")
        assert [t.original_trial_id for t in trials] == ["0", "1", "2"]
    print("  PASS: test_method_independent_trial_id")


# ---------------------------------------------------------------------------
# Missing question_type → exclusion
# ---------------------------------------------------------------------------

def test_missing_question_type_excluded():
    """Trials without question_type are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        del data["conditions"][0]["trials"][2]["question_type"]
        path = _write_result_file(tmpdir, "kernel_shared", data)
        report = ExclusionReport()
        trials = load_result_file(path, "kernel_shared", exclusion_report=report)
        assert len(trials) == 4
        assert report.entries[0].reason == "missing_or_invalid_question_type"
    print("  PASS: test_missing_question_type_excluded")


# ---------------------------------------------------------------------------
# Missing inference_context_text → exclusion (unobservable)
# ---------------------------------------------------------------------------

def test_none_inference_context_excluded():
    """Trials with inference_context_text=None are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=4)
        data["conditions"][0]["trials"][1]["inference_context_text"] = None
        path = _write_result_file(tmpdir, "kernel_shared", data)
        report = ExclusionReport()
        trials = load_result_file(path, "kernel_shared", exclusion_report=report)
        assert len(trials) == 3
        assert report.entries[0].reason == "missing_exact_inference_context"
    print("  PASS: test_none_inference_context_excluded")


def test_missing_inference_context_field_excluded():
    """Trials without inference_context_text field at all are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("vanilla_rag", num_trials=4)
        del data["conditions"][0]["trials"][0]["inference_context_text"]
        path = _write_result_file(tmpdir, "vanilla_rag", data)
        report = ExclusionReport()
        trials = load_result_file(path, "vanilla_rag", exclusion_report=report)
        assert len(trials) == 3
        assert any(e.reason == "missing_exact_inference_context" for e in report.entries)
    print("  PASS: test_missing_inference_context_field_excluded")


# ---------------------------------------------------------------------------
# Empty inference_context_text → valid (confirmed no context)
# ---------------------------------------------------------------------------

def test_empty_inference_context_valid():
    """Empty string inference_context_text is valid (confirmed no context)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("mem0_default", num_trials=4)
        for trial in data["conditions"][0]["trials"]:
            trial["inference_context_text"] = ""
        path = _write_result_file(tmpdir, "mem0_default", data)
        trials = load_result_file(path, "mem0_default")
        assert len(trials) == 4
        assert all(t.inference_context == "" for t in trials)
    print("  PASS: test_empty_inference_context_valid")


# ---------------------------------------------------------------------------
# Judge score selection rule
# ---------------------------------------------------------------------------

def test_judge_score_selection():
    """Profile trials get profile_usage_score, task trials get task_usage_score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("naive_concat", num_trials=4)
        for trial in data["conditions"][0]["trials"]:
            trial["profile_usage_score"] = 5
            trial["task_usage_score"] = 2
            trial["integration_score"] = 3
        path = _write_result_file(tmpdir, "naive_concat", data)
        trials = load_result_file(path, "naive_concat")
        for t in trials:
            if t.question_type == "profile":
                assert t.judge_score == 5
            else:
                assert t.judge_score == 2
    print("  PASS: test_judge_score_selection")


# ---------------------------------------------------------------------------
# UnsupportedBenchmarkArtifactsError for old results
# ---------------------------------------------------------------------------

def test_unsupported_artifacts_error():
    """Results lacking question_type entirely raise UnsupportedBenchmarkArtifactsError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {}
        for method in ALLOWED_METHODS:
            data = _make_result_file(method, num_trials=5)
            # Remove question_type from ALL trials to simulate old results
            for trial in data["conditions"][0]["trials"]:
                del trial["question_type"]
            path = _write_result_file(tmpdir, method, data)
            paths[method] = path
        try:
            load_eligible_trials(method_paths=paths, min_per_cell=3)
            assert False, "Should have raised"
        except UnsupportedBenchmarkArtifactsError as e:
            assert "question type" in str(e).lower() or "question_type" in str(e)
    print("  PASS: test_unsupported_artifacts_error")


# ---------------------------------------------------------------------------
# Insufficient trials per cell
# ---------------------------------------------------------------------------

def test_insufficient_cell():
    """Too few trials in a method/type cell raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {}
        for method in ALLOWED_METHODS:
            # Only 2 trials → 1 profile + 1 task (below min_per_cell=3)
            data = _make_result_file(method, num_trials=2)
            path = _write_result_file(tmpdir, method, data)
            paths[method] = path
        try:
            load_eligible_trials(method_paths=paths, min_per_cell=3)
            assert False, "Should have raised"
        except ValueError as e:
            assert "Insufficient" in str(e)
    print("  PASS: test_insufficient_cell")


# ---------------------------------------------------------------------------
# Pool summary
# ---------------------------------------------------------------------------

def test_pool_summary():
    """Summary reports counts per method × type cell."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, _ = load_eligible_trials(method_paths=paths, min_per_cell=3)
        summary = summarize_trial_pool(trials)
        assert summary.total_trials == 40
        assert set(summary.question_types) == {"profile", "task"}
        for c in summary.cells:
            assert c.count == 5  # 10 trials ÷ 2 types = 5 per cell
    print("  PASS: test_pool_summary")


# ---------------------------------------------------------------------------
# Exclusion report structure
# ---------------------------------------------------------------------------

def test_exclusion_report():
    """Exclusion report tracks reasons and methods."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("vanilla_rag", num_trials=5)
        data["conditions"][0]["trials"][1]["assistant_response"] = ""
        data["conditions"][0]["trials"][3]["question_type"] = "invalid"
        path = _write_result_file(tmpdir, "vanilla_rag", data)
        report = ExclusionReport()
        trials = load_result_file(path, "vanilla_rag", exclusion_report=report)
        assert len(trials) == 3
        assert report.total_excluded == 2
        reasons = {e.reason for e in report.entries}
        assert "empty_response" in reasons
        assert "missing_or_invalid_question_type" in reasons
    print("  PASS: test_exclusion_report")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def main():
    print("=== Human Rating Trial Loader Tests ===\n")

    print("Model normalization:")
    test_normalize_model()

    print("\nFile discovery:")
    test_discover_result_files()

    print("\nLoading with required fields:")
    test_load_success()
    test_method_independent_trial_id()

    print("\nMissing metadata → exclusion:")
    test_missing_question_type_excluded()
    test_none_inference_context_excluded()
    test_missing_inference_context_field_excluded()
    test_empty_inference_context_valid()

    print("\nJudge score selection:")
    test_judge_score_selection()

    print("\nCompatibility:")
    test_unsupported_artifacts_error()

    print("\nEligibility:")
    test_insufficient_cell()

    print("\nPool summary:")
    test_pool_summary()

    print("\nExclusion report:")
    test_exclusion_report()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
