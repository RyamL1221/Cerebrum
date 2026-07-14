"""Trial loader tests for the human-rating evaluation workflow.

Tests cover:
- Successful loading for each method
- Model-name normalization
- Rejection of non-GPT-4o trials
- Missing question-type mapping
- Invalid question type
- Missing response / missing question
- Missing or out-of-range judge score
- Duplicate method/trial IDs
- Conflicting questions for the same trial across methods
- Insufficient trials in a method/type cell
- Deterministic file processing order
- Exclusion of unrelated JSON artifacts
- Exact preservation of inference-time profile context
- Correct per-cell summary counts
- Question type mapping loading and validation

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
    MIN_TRIALS_PER_CELL,
    QuestionTypeMapping,
    discover_result_files,
    generate_default_question_type_mapping,
    load_eligible_trials,
    load_question_type_mapping,
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


def _make_question_type_file(tmpdir: str, max_index: int = 9) -> str:
    """Create a question_types.json file."""
    mapping = {}
    for i in range(max_index + 1):
        mapping[str(i)] = "profile" if i % 2 == 0 else "task"
    data = {
        "schema_version": 1,
        "description": "Test mapping",
        "assignment_rule": "alternating",
        "trials": mapping,
    }
    path = os.path.join(tmpdir, "question_types.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


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


def test_normalize_model_case_insensitive():
    """Capitalized variants should normalize."""
    assert normalize_model_name("GPT-4o") == "gpt-4o"
    assert normalize_model_name("GPT-4O") == "gpt-4o"
    print("  PASS: test_normalize_model_case_insensitive")


def test_normalize_model_rejects_other():
    """Non-GPT-4o models should be rejected."""
    try:
        normalize_model_name("gpt-4o-mini")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not a recognized GPT-4o variant" in str(e)
    try:
        normalize_model_name("gpt-5.4")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not a recognized" in str(e)
    print("  PASS: test_normalize_model_rejects_other")


# ---------------------------------------------------------------------------
# Question type mapping tests
# ---------------------------------------------------------------------------

def test_load_question_type_mapping():
    """Loading a valid mapping file should work."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _make_question_type_file(tmpdir, max_index=9)
        mapping = load_question_type_mapping(path)
        assert mapping.get_type(0) == "profile"
        assert mapping.get_type(1) == "task"
        assert mapping.get_type(8) == "profile"
        assert mapping.get_type(9) == "task"
    print("  PASS: test_load_question_type_mapping")


def test_question_type_mapping_missing_index():
    """Looking up a missing index should raise KeyError."""
    mapping = QuestionTypeMapping(mapping={0: "profile", 1: "task"})
    try:
        mapping.get_type(99)
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "99" in str(e)
    print("  PASS: test_question_type_mapping_missing_index")


def test_question_type_mapping_invalid_type():
    """Mapping with invalid type value should raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = {"schema_version": 1, "trials": {"0": "invalid_type"}}
        path = os.path.join(tmpdir, "qt.json")
        with open(path, "w") as f:
            json.dump(data, f)
        try:
            load_question_type_mapping(path)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "invalid question_type" in str(e)
    print("  PASS: test_question_type_mapping_invalid_type")


def test_question_type_mapping_missing_file():
    """Non-existent file should raise FileNotFoundError."""
    try:
        load_question_type_mapping("/nonexistent/path.json")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass
    print("  PASS: test_question_type_mapping_missing_file")


def test_default_question_type_mapping():
    """Default alternating mapping should work."""
    mapping = generate_default_question_type_mapping(9)
    assert mapping.get_type(0) == "profile"
    assert mapping.get_type(1) == "task"
    assert mapping.get_type(2) == "profile"
    assert mapping.get_type(9) == "task"
    print("  PASS: test_default_question_type_mapping")


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
            assert method in str(path)
    print("  PASS: test_discover_result_files_success")


def test_discover_result_files_missing_method():
    """Missing method file should raise FileNotFoundError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Only write 3 of 4
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
        # Write an unrelated JSON file
        unrelated = os.path.join(tmpdir, "summary.json")
        with open(unrelated, "w") as f:
            json.dump({"unrelated": True}, f)
        discovered = discover_result_files(tmpdir)
        # Should still find exactly 4 methods
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
    """Loading a valid result file should produce SourceTrial objects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=10)
        path = _write_result_file(tmpdir, "kernel_shared", data)
        trials = load_result_file(path, expected_method="kernel_shared")
        assert len(trials) == 10
        assert all(t.source_method == "kernel_shared" for t in trials)
        assert all(t.model == "gpt-4o" for t in trials)
    print("  PASS: test_load_result_file_success")


def test_load_result_file_each_method():
    """All four methods should load successfully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for method in ALLOWED_METHODS:
            data = _make_result_file(method, num_trials=5)
            path = _write_result_file(tmpdir, method, data)
            trials = load_result_file(path, expected_method=method)
            assert len(trials) == 5
            assert all(t.source_method == method for t in trials)
    print("  PASS: test_load_result_file_each_method")


def test_load_result_file_missing_response():
    """Trials with empty response should be skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        # Make trial 2 have empty response
        data["conditions"][0]["trials"][2]["assistant_response"] = ""
        path = _write_result_file(tmpdir, "kernel_shared", data)
        trials = load_result_file(path, expected_method="kernel_shared")
        assert len(trials) == 4  # 5 - 1 skipped
        ids = [t.original_trial_id for t in trials]
        assert "kernel_shared_2" not in ids
    print("  PASS: test_load_result_file_missing_response")


def test_load_result_file_missing_question():
    """Trials with empty question should be skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("naive_concat", num_trials=5)
        data["conditions"][0]["trials"][1]["follow_up_query"] = "   "
        path = _write_result_file(tmpdir, "naive_concat", data)
        trials = load_result_file(path, expected_method="naive_concat")
        assert len(trials) == 4
    print("  PASS: test_load_result_file_missing_question")


def test_load_result_file_invalid_judge_score():
    """Trials with out-of-range judge score should be skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("vanilla_rag", num_trials=5)
        data["conditions"][0]["trials"][0]["integration_score"] = 0  # invalid
        data["conditions"][0]["trials"][3]["integration_score"] = 6  # invalid
        path = _write_result_file(tmpdir, "vanilla_rag", data)
        trials = load_result_file(path, expected_method="vanilla_rag")
        assert len(trials) == 3  # 5 - 2 skipped
    print("  PASS: test_load_result_file_invalid_judge_score")


def test_load_result_file_missing_judge_score():
    """Trials with null judge score should be skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("mem0_default", num_trials=5)
        data["conditions"][0]["trials"][2]["integration_score"] = None
        path = _write_result_file(tmpdir, "mem0_default", data)
        trials = load_result_file(path, expected_method="mem0_default")
        assert len(trials) == 4
    print("  PASS: test_load_result_file_missing_judge_score")


def test_load_result_file_failed_trials_skipped():
    """Failed trials should be excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        data["conditions"][0]["trials"][4]["failed"] = True
        path = _write_result_file(tmpdir, "kernel_shared", data)
        trials = load_result_file(path, expected_method="kernel_shared")
        assert len(trials) == 4
    print("  PASS: test_load_result_file_failed_trials_skipped")


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
        assert len(trials) == 1
        ctx = trials[0].profile_context
        assert ctx is not None
        assert "User 0" in ctx
        assert "VS Code" in ctx
        assert "Python" in ctx
        assert "Project 0" in ctx
        assert "--- USER PROFILE ---" in ctx
        assert "--- TASK CONTEXT ---" in ctx
    print("  PASS: test_load_result_file_preserves_profile_context")


def test_load_result_file_question_type_assignment():
    """Question types should be assigned from the mapping."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=6)
        path = _write_result_file(tmpdir, "kernel_shared", data)
        mapping = generate_default_question_type_mapping(5)
        trials = load_result_file(
            path, expected_method="kernel_shared", question_type_map=mapping
        )
        assert len(trials) == 6
        assert trials[0].question_type == "profile"  # index 0
        assert trials[1].question_type == "task"     # index 1
        assert trials[2].question_type == "profile"  # index 2
    print("  PASS: test_load_result_file_question_type_assignment")


def test_load_result_file_duplicate_trial_index():
    """Duplicate trial_index should raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=3)
        # Duplicate trial_index 1
        data["conditions"][0]["trials"].append(
            _make_trial(1, "kernel_shared")
        )
        path = _write_result_file(tmpdir, "kernel_shared", data)
        try:
            load_result_file(path, expected_method="kernel_shared")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Duplicate trial ID" in str(e)
    print("  PASS: test_load_result_file_duplicate_trial_index")


# ---------------------------------------------------------------------------
# Multi-file loading and eligibility tests
# ---------------------------------------------------------------------------

def test_load_eligible_trials_success():
    """Loading all four methods should produce a valid pool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials = load_eligible_trials(
            method_paths=paths,
            min_per_cell=3,
        )
        # 4 methods * 10 trials = 40 total
        assert len(trials) == 40
        methods = {t.source_method for t in trials}
        assert methods == set(ALLOWED_METHODS)
    print("  PASS: test_load_eligible_trials_success")


def test_load_eligible_trials_auto_discovery():
    """Auto-discovery mode should work from results root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_all_methods(tmpdir, num_trials=10)
        trials = load_eligible_trials(
            results_root=tmpdir,
            min_per_cell=3,
        )
        assert len(trials) == 40
    print("  PASS: test_load_eligible_trials_auto_discovery")


def test_load_eligible_trials_insufficient_cell():
    """Insufficient trials in a cell should raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write kernel_shared with only 1 trial (not enough for min_per_cell=3)
        paths = {}
        for method in ALLOWED_METHODS:
            if method == "kernel_shared":
                data = _make_result_file(method, num_trials=1)
            else:
                data = _make_result_file(method, num_trials=10)
            path = _write_result_file(tmpdir, method, data)
            paths[method] = path

        try:
            load_eligible_trials(method_paths=paths, min_per_cell=3)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Insufficient eligible trials" in str(e)
            assert "kernel_shared" in str(e)
    print("  PASS: test_load_eligible_trials_insufficient_cell")


def test_load_eligible_trials_no_source_provided():
    """No paths and no results_root should raise ValueError."""
    try:
        load_eligible_trials()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be provided" in str(e)
    print("  PASS: test_load_eligible_trials_no_source_provided")


def test_load_eligible_trials_missing_method_path():
    """Missing method in explicit paths should raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {}
        for method in ["kernel_shared", "naive_concat", "mem0_default"]:
            data = _make_result_file(method, num_trials=10)
            path = _write_result_file(tmpdir, method, data)
            paths[method] = path
        try:
            load_eligible_trials(method_paths=paths)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "vanilla_rag" in str(e)
    print("  PASS: test_load_eligible_trials_missing_method_path")


# ---------------------------------------------------------------------------
# Pool summary tests
# ---------------------------------------------------------------------------

def test_summarize_trial_pool():
    """Summary should report correct counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials = load_eligible_trials(method_paths=paths, min_per_cell=3)
        summary = summarize_trial_pool(trials)
        assert summary.total_trials == 40
        assert set(summary.methods) == set(ALLOWED_METHODS)
        assert set(summary.question_types) == {"profile", "task"}
        # Each method should have 5 profile + 5 task (alternating)
        for cell in summary.cells:
            assert cell.count == 5
    print("  PASS: test_summarize_trial_pool")


def test_summarize_trial_pool_table_format():
    """Summary table should be formatted correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials = load_eligible_trials(method_paths=paths, min_per_cell=3)
        summary = summarize_trial_pool(trials)
        table = summary.format_table()
        assert "Method" in table
        assert "Profile" in table
        assert "Task" in table
        for method in ALLOWED_METHODS:
            assert method in table
    print("  PASS: test_summarize_trial_pool_table_format")


def test_summarize_score_distribution():
    """Summary should include score distribution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials = load_eligible_trials(method_paths=paths, min_per_cell=3)
        summary = summarize_trial_pool(trials)
        # All fixtures have integration_score=4
        assert 4 in summary.score_distribution
        assert summary.score_distribution[4] == 40
    print("  PASS: test_summarize_score_distribution")


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
    assert "Active Experiment: Experiment 0" in ctx
    assert "Goals: Goal A for trial 0" in ctx
    assert "Blockers: Blocker for trial 0" in ctx
    assert "Next Steps: Next step for trial 0" in ctx
    print("  PASS: test_build_profile_context_full")


def test_build_profile_context_missing_profile():
    """Missing synthetic_profile should return None."""
    trial = _make_trial(0, "kernel_shared")
    trial["synthetic_profile"] = None
    ctx = _build_profile_context(trial)
    assert ctx is None
    print("  PASS: test_build_profile_context_missing_profile")


def test_build_profile_context_missing_task():
    """Missing synthetic_task_context should return None."""
    trial = _make_trial(0, "kernel_shared")
    trial["synthetic_task_context"] = None
    ctx = _build_profile_context(trial)
    assert ctx is None
    print("  PASS: test_build_profile_context_missing_task")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

def main():
    print("=== Human Rating Trial Loader Tests ===\n")

    print("Model name normalization:")
    test_normalize_model_gpt4o()
    test_normalize_model_with_provider()
    test_normalize_model_case_insensitive()
    test_normalize_model_rejects_other()

    print("\nQuestion type mapping:")
    test_load_question_type_mapping()
    test_question_type_mapping_missing_index()
    test_question_type_mapping_invalid_type()
    test_question_type_mapping_missing_file()
    test_default_question_type_mapping()

    print("\nFile discovery:")
    test_discover_result_files_success()
    test_discover_result_files_missing_method()
    test_discover_excludes_unrelated_json()
    test_discover_deterministic_order()

    print("\nSingle-file loading:")
    test_load_result_file_success()
    test_load_result_file_each_method()
    test_load_result_file_missing_response()
    test_load_result_file_missing_question()
    test_load_result_file_invalid_judge_score()
    test_load_result_file_missing_judge_score()
    test_load_result_file_failed_trials_skipped()
    test_load_result_file_method_mismatch()
    test_load_result_file_preserves_profile_context()
    test_load_result_file_question_type_assignment()
    test_load_result_file_duplicate_trial_index()

    print("\nMulti-file loading and eligibility:")
    test_load_eligible_trials_success()
    test_load_eligible_trials_auto_discovery()
    test_load_eligible_trials_insufficient_cell()
    test_load_eligible_trials_no_source_provided()
    test_load_eligible_trials_missing_method_path()

    print("\nPool summary:")
    test_summarize_trial_pool()
    test_summarize_trial_pool_table_format()
    test_summarize_score_distribution()

    print("\nProfile context reconstruction:")
    test_build_profile_context_full()
    test_build_profile_context_missing_profile()
    test_build_profile_context_missing_task()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
