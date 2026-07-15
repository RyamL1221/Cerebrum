"""Trial loader tests for the human-rating evaluation workflow.

Tests cover:
- Successful loading for each method with all three judge dimensions
- Model-name normalization
- Rejection of non-GPT-4o trials
- Missing response / missing question
- Missing or out-of-range judge scores (any dimension)
- Duplicate (method, trial_id) pairs
- Insufficient trials per method
- Deterministic file processing order
- Exclusion of unrelated JSON artifacts
- Exact preservation of inference-time profile context
- Correct per-method summary counts
- Method-independent original_trial_id
- Structured exclusion reporting

Run:
    python benchmarks/human_rating/tests/test_trial_loader.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure the project root is on sys.path when running as a script
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.trial_loader import (
    ALLOWED_METHODS,
    ExclusionReport,
    discover_result_files,
    load_eligible_trials,
    load_result_file,
    normalize_model_name,
    summarize_trial_pool,
    _build_profile_context,
)
from benchmarks.human_rating.schemas import SourceTrial


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_trial(trial_index: int, method: str, **overrides) -> dict:
    """Create a synthetic trial dict matching the benchmark result format."""
    defaults = {
        "trial_index": trial_index,
        "condition": method,
        "method": method,
        "profile_usage_score": 3,
        "task_usage_score": 4,
        "integration_score": 4,
        "memory_counts": {"total": 0, "shared": 0, "private": 0},
        "retrieved_context_count": 0,
        "latency_seconds": 5.0,
        "follow_up_query": f"What should I focus on next? (trial {trial_index})",
        "assistant_response": f"Based on your profile and task context, I recommend... (trial {trial_index})",
        "synthetic_profile": {
            "user_name": f"User {trial_index}",
            "preferred_tools": ["VS Code", "Git"],
            "preferred_language": "Python",
            "response_style": "concise",
        },
        "synthetic_task_context": {
            "current_project": f"Project {trial_index}",
            "active_experiment": f"Experiment {trial_index}",
            "goals": [f"Goal A for trial {trial_index}"],
            "blockers": [f"Blocker for trial {trial_index}"],
            "next_steps": [f"Next step for trial {trial_index}"],
        },
        "retrieval_log": None,
        "injection_diagnostics": None,
        "written_memories": [],
        "failed": False,
        "error_message": None,
    }
    defaults.update(overrides)
    return defaults


def _make_result_file(method: str, num_trials: int = 10, **trial_overrides) -> dict:
    """Create a full result file structure for one method."""
    trials = [_make_trial(i, method, **trial_overrides) for i in range(num_trials)]
    return {
        "experiment_metadata": {
            "trials_per_condition": num_trials,
            "timestamp": "2026-07-14T10:00:00.000000",
            "kernel_url": "http://localhost:8000",
            "conditions_run": [method],
            "methods_run": [method],
        },
        "conditions": [
            {
                "condition": method,
                "trials": trials,
                "summary": {},
            }
        ],
    }


def _write_result_file(tmpdir: str, method: str, data: dict) -> str:
    """Write a result JSON file in the expected directory structure."""
    dir_path = os.path.join(tmpdir, f"gpt4o_{method}")
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"results_{method}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return file_path


def _write_all_methods(tmpdir: str, num_trials: int = 10) -> dict:
    """Write result files for all four methods, return method->path mapping."""
    paths = {}
    for method in ALLOWED_METHODS:
        data = _make_result_file(method, num_trials)
        path = _write_result_file(tmpdir, method, data)
        paths[method] = path
    return paths


# ---------------------------------------------------------------------------
# Model name normalization tests
# ---------------------------------------------------------------------------

def test_normalize_model_gpt4o():
    """Standard 'gpt-4o' should normalize correctly."""
    assert normalize_model_name("gpt-4o") == "gpt-4o"
    print("  PASS: test_normalize_model_gpt4o")


def test_normalize_model_with_provider():
    """'gpt-4o:azure' should normalize to 'gpt-4o'."""
    assert normalize_model_name("gpt-4o:azure") == "gpt-4o"
    assert normalize_model_name("gpt-4o:openai") == "gpt-4o"
    print("  PASS: test_normalize_model_with_provider")


def test_normalize_model_rejects_other():
    """Non-GPT-4o models should be rejected."""
    for bad in ("gpt-4o-mini", "gpt-5.4", "claude-3", "qwen2.5:7b"):
        try:
            normalize_model_name(bad)
            assert False, f"Should have raised ValueError for {bad}"
        except ValueError:
            pass
    print("  PASS: test_normalize_model_rejects_other")


# ---------------------------------------------------------------------------
# File discovery tests
# ---------------------------------------------------------------------------

def test_discover_result_files_success():
    """Auto-discovery should find all four method files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_all_methods(tmpdir)
        discovered = discover_result_files(tmpdir)
        assert set(discovered.keys()) == set(ALLOWED_METHODS)
        for method, path in discovered.items():
            assert path.exists()
    print("  PASS: test_discover_result_files_success")


def test_discover_result_files_missing_method():
    """Missing method file should raise FileNotFoundError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for method in ["kernel_shared", "mem0_default", "naive_concat"]:
            data = _make_result_file(method)
            _write_result_file(tmpdir, method, data)
        try:
            discover_result_files(tmpdir)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError as e:
            assert "vanilla_rag" in str(e)
    print("  PASS: test_discover_result_files_missing_method")


def test_discover_excludes_unrelated_json():
    """Unrelated JSON files should not be picked up."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_all_methods(tmpdir)
        unrelated = os.path.join(tmpdir, "summary.json")
        with open(unrelated, "w") as f:
            json.dump({"unrelated": True}, f)
        discovered = discover_result_files(tmpdir)
        assert len(discovered) == 4
        assert unrelated not in [str(p) for p in discovered.values()]
    print("  PASS: test_discover_excludes_unrelated_json")


def test_discover_deterministic_order():
    """Discovery should process files in deterministic sorted order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_all_methods(tmpdir)
        discovered = discover_result_files(tmpdir)
        keys = list(discovered.keys())
        assert keys == sorted(keys)
    print("  PASS: test_discover_deterministic_order")


# ---------------------------------------------------------------------------
# Single-file loading tests
# ---------------------------------------------------------------------------

def test_load_result_file_success():
    """Loading a valid result file should produce SourceTrial objects with three scores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=10)
        path = _write_result_file(tmpdir, "kernel_shared", data)
        trials = load_result_file(path, expected_method="kernel_shared")
        assert len(trials) == 10
        assert all(t.source_method == "kernel_shared" for t in trials)
        assert all(t.model == "gpt-4o" for t in trials)
        # All three scores preserved
        assert all(t.profile_usage_score == 3 for t in trials)
        assert all(t.task_usage_score == 4 for t in trials)
        assert all(t.integration_score == 4 for t in trials)
    print("  PASS: test_load_result_file_success")


def test_load_result_file_method_independent_trial_id():
    """original_trial_id should be just the trial index (method-independent)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        path = _write_result_file(tmpdir, "kernel_shared", data)
        trials = load_result_file(path, expected_method="kernel_shared")
        # IDs should be "0", "1", "2", "3", "4" — not "kernel_shared_0" etc.
        ids = [t.original_trial_id for t in trials]
        assert ids == ["0", "1", "2", "3", "4"]
    print("  PASS: test_load_result_file_method_independent_trial_id")


def test_load_result_file_missing_response():
    """Trials with empty response should be excluded with reason."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        data["conditions"][0]["trials"][2]["assistant_response"] = ""
        path = _write_result_file(tmpdir, "kernel_shared", data)
        report = ExclusionReport()
        trials = load_result_file(path, expected_method="kernel_shared", exclusion_report=report)
        assert len(trials) == 4
        assert report.total_excluded == 1
        assert report.entries[0].reason == "empty_response"
        assert report.entries[0].trial_index == 2
    print("  PASS: test_load_result_file_missing_response")


def test_load_result_file_missing_question():
    """Trials with empty question should be excluded with reason."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("naive_concat", num_trials=5)
        data["conditions"][0]["trials"][1]["follow_up_query"] = "   "
        path = _write_result_file(tmpdir, "naive_concat", data)
        report = ExclusionReport()
        trials = load_result_file(path, expected_method="naive_concat", exclusion_report=report)
        assert len(trials) == 4
        assert report.entries[0].reason == "empty_question"
    print("  PASS: test_load_result_file_missing_question")


def test_load_result_file_invalid_judge_score():
    """Trials with out-of-range judge score should be excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("vanilla_rag", num_trials=5)
        data["conditions"][0]["trials"][0]["integration_score"] = 0
        data["conditions"][0]["trials"][3]["profile_usage_score"] = 6
        path = _write_result_file(tmpdir, "vanilla_rag", data)
        report = ExclusionReport()
        trials = load_result_file(path, expected_method="vanilla_rag", exclusion_report=report)
        assert len(trials) == 3
        assert report.total_excluded == 2
    print("  PASS: test_load_result_file_invalid_judge_score")


def test_load_result_file_missing_judge_score():
    """Trials with null judge score should be excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("mem0_default", num_trials=5)
        data["conditions"][0]["trials"][2]["task_usage_score"] = None
        path = _write_result_file(tmpdir, "mem0_default", data)
        report = ExclusionReport()
        trials = load_result_file(path, expected_method="mem0_default", exclusion_report=report)
        assert len(trials) == 4
        assert "missing_task_usage_score" in report.entries[0].reason
    print("  PASS: test_load_result_file_missing_judge_score")


def test_load_result_file_failed_trials_excluded():
    """Failed trials should be excluded with 'failed_trial' reason."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        data["conditions"][0]["trials"][4]["failed"] = True
        path = _write_result_file(tmpdir, "kernel_shared", data)
        report = ExclusionReport()
        trials = load_result_file(path, expected_method="kernel_shared", exclusion_report=report)
        assert len(trials) == 4
        assert report.entries[0].reason == "failed_trial"
    print("  PASS: test_load_result_file_failed_trials_excluded")


def test_load_result_file_method_mismatch():
    """Method mismatch between file content and expectation should raise."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        path = _write_result_file(tmpdir, "kernel_shared", data)
        try:
            load_result_file(path, expected_method="naive_concat")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "does not contain method" in str(e)
    print("  PASS: test_load_result_file_method_mismatch")


def test_load_result_file_preserves_profile_context():
    """Profile context should be reconstructed from synthetic data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=1)
        path = _write_result_file(tmpdir, "kernel_shared", data)
        trials = load_result_file(path, expected_method="kernel_shared")
        ctx = trials[0].profile_context
        assert ctx is not None
        assert "User 0" in ctx
        assert "VS Code" in ctx
        assert "Python" in ctx
        assert "Project 0" in ctx
        assert "--- USER PROFILE ---" in ctx
        assert "--- TASK CONTEXT ---" in ctx
    print("  PASS: test_load_result_file_preserves_profile_context")


def test_load_result_file_duplicate_trial_index():
    """Duplicate (method, trial_index) should raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=3)
        data["conditions"][0]["trials"].append(_make_trial(1, "kernel_shared"))
        path = _write_result_file(tmpdir, "kernel_shared", data)
        try:
            load_result_file(path, expected_method="kernel_shared")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Duplicate trial" in str(e)
    print("  PASS: test_load_result_file_duplicate_trial_index")


# ---------------------------------------------------------------------------
# Multi-file loading and eligibility tests
# ---------------------------------------------------------------------------

def test_load_eligible_trials_success():
    """Loading all four methods should produce a valid pool with exclusion report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, report = load_eligible_trials(method_paths=paths, min_per_method=3)
        assert len(trials) == 40
        assert report.total_excluded == 0
        methods = {t.source_method for t in trials}
        assert methods == set(ALLOWED_METHODS)
    print("  PASS: test_load_eligible_trials_success")


def test_load_eligible_trials_auto_discovery():
    """Auto-discovery mode should work from results root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_all_methods(tmpdir, num_trials=10)
        trials, report = load_eligible_trials(results_root=tmpdir, min_per_method=3)
        assert len(trials) == 40
    print("  PASS: test_load_eligible_trials_auto_discovery")


def test_load_eligible_trials_insufficient_method():
    """Insufficient trials in a method should raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {}
        for method in ALLOWED_METHODS:
            n = 1 if method == "kernel_shared" else 10
            data = _make_result_file(method, num_trials=n)
            path = _write_result_file(tmpdir, method, data)
            paths[method] = path
        try:
            load_eligible_trials(method_paths=paths, min_per_method=3)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Insufficient" in str(e)
            assert "kernel_shared" in str(e)
    print("  PASS: test_load_eligible_trials_insufficient_method")


def test_load_eligible_trials_exclusion_report():
    """Exclusion report should track all excluded trials."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {}
        for method in ALLOWED_METHODS:
            data = _make_result_file(method, num_trials=10)
            # Add one failed trial to each method
            data["conditions"][0]["trials"][5]["failed"] = True
            path = _write_result_file(tmpdir, method, data)
            paths[method] = path
        trials, report = load_eligible_trials(method_paths=paths, min_per_method=3)
        assert len(trials) == 36  # 4 methods * 9 valid
        assert report.total_excluded == 4
        assert report.by_reason() == {"failed_trial": 4}
    print("  PASS: test_load_eligible_trials_exclusion_report")


# ---------------------------------------------------------------------------
# Pool summary tests
# ---------------------------------------------------------------------------

def test_summarize_trial_pool():
    """Summary should report correct per-method counts and averages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, _ = load_eligible_trials(method_paths=paths, min_per_method=3)
        summary = summarize_trial_pool(trials)
        assert summary.total_trials == 40
        assert set(summary.methods) == set(ALLOWED_METHODS)
        # Each method has 10 trials
        for mc in summary.method_counts:
            assert mc.count == 10
            assert mc.avg_profile_usage == 3.0
            assert mc.avg_task_usage == 4.0
            assert mc.avg_integration == 4.0
    print("  PASS: test_summarize_trial_pool")


def test_summarize_score_distribution():
    """Summary should include per-dimension score distribution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, _ = load_eligible_trials(method_paths=paths, min_per_method=3)
        summary = summarize_trial_pool(trials)
        # All fixtures: profile=3, task=4, integration=4
        assert summary.score_distribution["profile_usage"] == {3: 40}
        assert summary.score_distribution["task_usage"] == {4: 40}
        assert summary.score_distribution["integration"] == {4: 40}
    print("  PASS: test_summarize_score_distribution")


def test_summarize_table_format():
    """Summary table should be formatted correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, _ = load_eligible_trials(method_paths=paths, min_per_method=3)
        summary = summarize_trial_pool(trials)
        table = summary.format_table()
        assert "Method" in table
        assert "Count" in table
        for method in ALLOWED_METHODS:
            assert method in table
    print("  PASS: test_summarize_table_format")


# ---------------------------------------------------------------------------
# Profile context reconstruction tests
# ---------------------------------------------------------------------------

def test_build_profile_context_full():
    """Full profile context should include all fields."""
    trial = _make_trial(0, "kernel_shared")
    ctx = _build_profile_context(trial)
    assert ctx is not None
    assert "--- USER PROFILE ---" in ctx
    assert "Name: User 0" in ctx
    assert "Preferred Tools: VS Code, Git" in ctx
    assert "Preferred Language: Python" in ctx
    assert "Response Style: concise" in ctx
    assert "--- TASK CONTEXT ---" in ctx
    assert "Current Project: Project 0" in ctx
    print("  PASS: test_build_profile_context_full")


def test_build_profile_context_missing_profile():
    """Missing synthetic_profile should return None."""
    trial = _make_trial(0, "kernel_shared")
    trial["synthetic_profile"] = None
    ctx = _build_profile_context(trial)
    assert ctx is None
    print("  PASS: test_build_profile_context_missing_profile")


# ---------------------------------------------------------------------------
# Exclusion report tests
# ---------------------------------------------------------------------------

def test_exclusion_report_by_reason():
    """ExclusionReport should count by reason."""
    report = ExclusionReport()
    report.entries.append(
        __import__("benchmarks.human_rating.trial_loader", fromlist=["ExclusionEntry"]).ExclusionEntry(
            method="kernel_shared", trial_index=0, reason="empty_response", source_file="x"
        )
    )
    report.entries.append(
        __import__("benchmarks.human_rating.trial_loader", fromlist=["ExclusionEntry"]).ExclusionEntry(
            method="naive_concat", trial_index=1, reason="empty_response", source_file="y"
        )
    )
    report.entries.append(
        __import__("benchmarks.human_rating.trial_loader", fromlist=["ExclusionEntry"]).ExclusionEntry(
            method="kernel_shared", trial_index=2, reason="failed_trial", source_file="x"
        )
    )
    assert report.total_excluded == 3
    assert report.by_reason() == {"empty_response": 2, "failed_trial": 1}
    assert report.by_method() == {"kernel_shared": 2, "naive_concat": 1}
    print("  PASS: test_exclusion_report_by_reason")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

def main():
    print("=== Human Rating Trial Loader Tests ===\n")

    print("Model name normalization:")
    test_normalize_model_gpt4o()
    test_normalize_model_with_provider()
    test_normalize_model_rejects_other()

    print("\nFile discovery:")
    test_discover_result_files_success()
    test_discover_result_files_missing_method()
    test_discover_excludes_unrelated_json()
    test_discover_deterministic_order()

    print("\nSingle-file loading:")
    test_load_result_file_success()
    test_load_result_file_method_independent_trial_id()
    test_load_result_file_missing_response()
    test_load_result_file_missing_question()
    test_load_result_file_invalid_judge_score()
    test_load_result_file_missing_judge_score()
    test_load_result_file_failed_trials_excluded()
    test_load_result_file_method_mismatch()
    test_load_result_file_preserves_profile_context()
    test_load_result_file_duplicate_trial_index()

    print("\nMulti-file loading and eligibility:")
    test_load_eligible_trials_success()
    test_load_eligible_trials_auto_discovery()
    test_load_eligible_trials_insufficient_method()
    test_load_eligible_trials_exclusion_report()

    print("\nPool summary:")
    test_summarize_trial_pool()
    test_summarize_score_distribution()
    test_summarize_table_format()

    print("\nProfile context reconstruction:")
    test_build_profile_context_full()
    test_build_profile_context_missing_profile()

    print("\nExclusion report:")
    test_exclusion_report_by_reason()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
