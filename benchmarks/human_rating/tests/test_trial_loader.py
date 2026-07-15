"""Trial loader tests for the corrected human-rating semantics.

Verifies:
- profile trials use the profile question template
- task trials use the task question template
- question_type is required in result JSON
- exact inference context is preserved (not reconstructed)
- empty retrieval remains empty
- the selected judge score follows the documented type-based rule
- trials missing question_type are excluded with structured reasons
- method-independent original_trial_id

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
    discover_result_files,
    load_eligible_trials,
    load_result_file,
    normalize_model_name,
    summarize_trial_pool,
)
from benchmarks.human_rating.schemas import SourceTrial, VALID_QUESTION_TYPES
from benchmarks.shared_memory.synth import (
    PROFILE_QUESTION_TEMPLATE,
    TASK_QUESTION_TEMPLATE,
    get_question_type_for_trial,
    get_question_template,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_trial(trial_index: int, method: str, **overrides) -> dict:
    """Create a trial dict with question_type and inference_context_text."""
    qtype = "profile" if trial_index % 2 == 0 else "task"
    question = get_question_template(qtype)
    # Simulate method-specific inference context
    if method == "naive_concat":
        ctx = f"--- USER PROFILE ---\nName: User {trial_index}\n--- TASK CONTEXT ---\nProject: P{trial_index}"
    elif method == "vanilla_rag":
        ctx = f"Goal: Goal for trial {trial_index}"
    elif method == "kernel_shared":
        ctx = f"Injected: Profile for trial {trial_index}"
    else:  # mem0_default
        ctx = ""  # No shared context injected

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
        "follow_up_query": question,
        "assistant_response": f"Response for trial {trial_index}",
        "inference_context_text": ctx,
        "synthetic_profile": {
            "user_name": f"User {trial_index}",
            "preferred_tools": ["VS Code"],
            "preferred_language": "Python",
            "response_style": "concise",
        },
        "synthetic_task_context": {
            "current_project": f"Project {trial_index}",
            "active_experiment": f"Exp {trial_index}",
            "goals": [f"Goal {trial_index}"],
            "blockers": [],
            "next_steps": [f"Step {trial_index}"],
        },
        "failed": False, "error_message": None,
    }
    defaults.update(overrides)
    return defaults


def _make_result_file(method: str, num_trials: int = 10) -> dict:
    trials = [_make_trial(i, method) for i in range(num_trials)]
    return {
        "experiment_metadata": {
            "trials_per_condition": num_trials,
            "timestamp": "2026-07-14T10:00:00",
            "kernel_url": "http://localhost:8000",
            "conditions_run": [method], "methods_run": [method],
        },
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
# Question template tests
# ---------------------------------------------------------------------------

def test_question_type_schedule():
    """Even=profile, odd=task deterministic schedule."""
    assert get_question_type_for_trial(0) == "profile"
    assert get_question_type_for_trial(1) == "task"
    assert get_question_type_for_trial(2) == "profile"
    assert get_question_type_for_trial(99) == "task"
    print("  PASS: test_question_type_schedule")


def test_profile_task_templates_differ():
    """Profile and task templates are semantically distinct."""
    assert PROFILE_QUESTION_TEMPLATE != TASK_QUESTION_TEMPLATE
    assert "preferences" in PROFILE_QUESTION_TEMPLATE.lower() or "style" in PROFILE_QUESTION_TEMPLATE.lower()
    assert "project" in TASK_QUESTION_TEMPLATE.lower() or "blockers" in TASK_QUESTION_TEMPLATE.lower()
    print("  PASS: test_profile_task_templates_differ")


# ---------------------------------------------------------------------------
# Trial loader tests
# ---------------------------------------------------------------------------

def test_load_with_question_type():
    """Trials with question_type load correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, report = load_eligible_trials(method_paths=paths, min_per_method=3)
        assert len(trials) == 40
        profile_trials = [t for t in trials if t.question_type == "profile"]
        task_trials = [t for t in trials if t.question_type == "task"]
        assert len(profile_trials) == 20  # 4 methods * 5 even indices
        assert len(task_trials) == 20     # 4 methods * 5 odd indices
    print("  PASS: test_load_with_question_type")


def test_missing_question_type_excluded():
    """Trials without question_type are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=5)
        # Remove question_type from trial 2
        del data["conditions"][0]["trials"][2]["question_type"]
        path = _write_result_file(tmpdir, "kernel_shared", data)
        report = ExclusionReport()
        trials = load_result_file(path, "kernel_shared", exclusion_report=report)
        assert len(trials) == 4
        assert report.entries[0].reason == "missing_or_invalid_question_type"
    print("  PASS: test_missing_question_type_excluded")


def test_inference_context_preserved_per_method():
    """Each method's inference context is preserved exactly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=2)
        trials, _ = load_eligible_trials(method_paths=paths, min_per_method=1)

        for t in trials:
            if t.source_method == "naive_concat":
                assert "--- USER PROFILE ---" in t.inference_context
            elif t.source_method == "vanilla_rag":
                assert "Goal:" in t.inference_context
            elif t.source_method == "kernel_shared":
                assert "Injected:" in t.inference_context
            elif t.source_method == "mem0_default":
                assert t.inference_context == ""  # empty — no injection
    print("  PASS: test_inference_context_preserved_per_method")


def test_empty_retrieval_stays_empty():
    """mem0_default with empty context stays empty (not reconstructed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("mem0_default", num_trials=4)
        # Explicitly set empty inference context
        for trial in data["conditions"][0]["trials"]:
            trial["inference_context_text"] = ""
        path = _write_result_file(tmpdir, "mem0_default", data)
        trials = load_result_file(path, "mem0_default")
        for t in trials:
            assert t.inference_context == ""
    print("  PASS: test_empty_retrieval_stays_empty")


def test_judge_score_follows_type_rule():
    """Profile trials use profile_usage_score, task trials use task_usage_score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("kernel_shared", num_trials=4)
        # Set distinct scores to verify selection
        for trial in data["conditions"][0]["trials"]:
            trial["profile_usage_score"] = 5  # profile trials should get 5
            trial["task_usage_score"] = 2     # task trials should get 2
            trial["integration_score"] = 3
        path = _write_result_file(tmpdir, "kernel_shared", data)
        trials = load_result_file(path, "kernel_shared")
        for t in trials:
            if t.question_type == "profile":
                assert t.judge_score == 5  # profile_usage_score
            else:
                assert t.judge_score == 2  # task_usage_score
    print("  PASS: test_judge_score_follows_type_rule")


def test_method_independent_trial_id():
    """original_trial_id is just the index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data = _make_result_file("naive_concat", num_trials=3)
        path = _write_result_file(tmpdir, "naive_concat", data)
        trials = load_result_file(path, "naive_concat")
        assert [t.original_trial_id for t in trials] == ["0", "1", "2"]
    print("  PASS: test_method_independent_trial_id")


def test_pool_summary_by_method_and_type():
    """Summary shows counts per method × question_type cell."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _write_all_methods(tmpdir, num_trials=10)
        trials, _ = load_eligible_trials(method_paths=paths, min_per_method=3)
        summary = summarize_trial_pool(trials)
        assert summary.total_trials == 40
        assert set(summary.question_types) == {"profile", "task"}
        # Each method × type cell has 5 trials
        for mc in summary.method_counts:
            assert mc.count == 5
    print("  PASS: test_pool_summary_by_method_and_type")


def test_exclusion_report_structured():
    """Exclusion report provides method, index, and reason."""
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
    print("  PASS: test_exclusion_report_structured")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def main():
    print("=== Human Rating Trial Loader Tests ===\n")

    print("Question templates:")
    test_question_type_schedule()
    test_profile_task_templates_differ()

    print("\nTrial loading:")
    test_load_with_question_type()
    test_missing_question_type_excluded()
    test_inference_context_preserved_per_method()
    test_empty_retrieval_stays_empty()
    test_judge_score_follows_type_rule()
    test_method_independent_trial_id()

    print("\nPool summary:")
    test_pool_summary_by_method_and_type()

    print("\nExclusion report:")
    test_exclusion_report_structured()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
