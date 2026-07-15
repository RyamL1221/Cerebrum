"""End-to-end lifecycle and regression tests for the human-rating workflow.

Run:
    python benchmarks/human_rating/tests/test_end_to_end.py
"""

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.rate import _queue_fingerprint


# ---------------------------------------------------------------------------
# Frozen expected values from the approved protocol
# ---------------------------------------------------------------------------

EXPECTED_SELECTED_TRIALS = {
    "kernel_shared": {"126", "15", "26", "52", "64", "96"},
    "mem0_default": {"106", "108", "121", "21", "42", "63"},
    "naive_concat": {"10", "119", "30", "41", "59", "98"},
    "vanilla_rag": {"133", "145", "26", "34", "55", "80"},
}

EXPECTED_FIRST_BLINDED_ID = "HR-63DE05"
EXPECTED_LAST_BLINDED_ID = "HR-A0CEC8"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_real_results():
    return os.path.isdir(os.path.join(_project_root, "results", "gpt4o_naive_concat"))


def _hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. Complete lifecycle integration
# ---------------------------------------------------------------------------

def test_complete_lifecycle():
    """Full lifecycle: generate → rate (partial + resume) → compile."""
    if not _has_real_results():
        print("  SKIP: test_complete_lifecycle (results not present)")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        runs_dir = os.path.join(tmpdir, "runs")

        # Generate
        r = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.sample_and_blind",
             "--generate", "--run-id", "e2e-test", "--runs-dir", runs_dir],
            capture_output=True, text=True, cwd=_project_root,
        )
        assert r.returncode == 0, f"Generate failed: {r.stderr}"

        queue_path = os.path.join(runs_dir, "e2e-test", "rater", "rating_queue.json")
        key_path = os.path.join(runs_dir, "e2e-test", "private", "answer_key.json")
        ratings_path = os.path.join(runs_dir, "e2e-test", "rater", "ratings.jsonl")
        session_path = os.path.join(runs_dir, "e2e-test", "rater", "rating_session.json")
        assert os.path.exists(queue_path)
        assert os.path.exists(key_path)

        # Rate: partial (15 ratings then quit)
        partial_input = "\n".join(["3"] * 15 + ["q"]) + "\n"
        r = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.rate",
             "--queue", queue_path, "--ratings", ratings_path, "--rater-id", "e2e-rater"],
            input=partial_input, capture_output=True, text=True, cwd=_project_root, timeout=30,
        )
        assert r.returncode == 0
        assert os.path.exists(ratings_path)
        with open(ratings_path) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 15

        # Resume and complete
        remaining_input = "\n".join(["4"] * 15) + "\n"
        r = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.rate",
             "--queue", queue_path, "--ratings", ratings_path, "--rater-id", "e2e-rater"],
            input=remaining_input, capture_output=True, text=True, cwd=_project_root, timeout=30,
        )
        assert r.returncode == 0
        with open(ratings_path) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 30

        # Compile
        compiled_dir = os.path.join(runs_dir, "e2e-test", "private", "compiled")
        r = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.compile_ratings",
             "--queue", queue_path, "--ratings", ratings_path,
             "--session", session_path, "--answer-key", key_path,
             "--output-dir", compiled_dir],
            capture_output=True, text=True, cwd=_project_root,
        )
        assert r.returncode == 0, f"Compile failed: {r.stderr}"
        assert os.path.exists(os.path.join(compiled_dir, "summary.json"))
        assert os.path.exists(os.path.join(compiled_dir, "primary_items.csv"))
        assert os.path.exists(os.path.join(compiled_dir, "all_appearances.csv"))
        assert os.path.exists(os.path.join(compiled_dir, "method_summary.csv"))
        assert os.path.exists(os.path.join(compiled_dir, "duplicate_consistency.csv"))
        assert os.path.exists(os.path.join(compiled_dir, "confusion_matrix.csv"))

    print("  PASS: test_complete_lifecycle")


# ---------------------------------------------------------------------------
# 2. Frozen selection regression
# ---------------------------------------------------------------------------

def test_frozen_selected_trial_identities():
    if not _has_real_results():
        print("  SKIP: test_frozen_selected_trial_identities")
        return

    from benchmarks.human_rating.trial_loader import load_eligible_trials
    from benchmarks.human_rating.sampling import sample_unique_trials

    trials, _ = load_eligible_trials(
        results_root=os.path.join(_project_root, "results"), min_per_method=6)
    selected, summary = sample_unique_trials(trials, seed=20260715)

    for method, expected_ids in EXPECTED_SELECTED_TRIALS.items():
        actual_ids = set(summary.selected_trial_ids_by_method[method])
        assert actual_ids == expected_ids, (
            f"{method}: expected {expected_ids}, got {actual_ids}"
        )
    print("  PASS: test_frozen_selected_trial_identities")


# ---------------------------------------------------------------------------
# 3. Frozen blinded plan regression
# ---------------------------------------------------------------------------

def test_frozen_blinded_plan():
    if not _has_real_results():
        print("  SKIP: test_frozen_blinded_plan")
        return

    from benchmarks.human_rating.trial_loader import load_eligible_trials
    from benchmarks.human_rating.sampling import sample_unique_trials
    from benchmarks.human_rating.blinding import build_blinded_plan, validate_blinded_plan

    trials, _ = load_eligible_trials(
        results_root=os.path.join(_project_root, "results"), min_per_method=6)
    selected, _ = sample_unique_trials(trials, seed=20260715)
    plan = build_blinded_plan(selected, seed=20260716)
    validate_blinded_plan(plan)

    ordered = sorted(plan.items, key=lambda x: x.appearance_index)
    assert ordered[0].blinded_id == EXPECTED_FIRST_BLINDED_ID
    assert ordered[-1].blinded_id == EXPECTED_LAST_BLINDED_ID
    assert len(ordered) == 30

    # Duplicate separation
    for item in ordered:
        if item.duplicate_of_blinded_id:
            orig = next(i for i in ordered if i.blinded_id == item.duplicate_of_blinded_id)
            assert abs(item.appearance_index - orig.appearance_index) >= 3

    print("  PASS: test_frozen_blinded_plan")


# ---------------------------------------------------------------------------
# 4. Deterministic regeneration
# ---------------------------------------------------------------------------

def test_deterministic_regeneration():
    if not _has_real_results():
        print("  SKIP: test_deterministic_regeneration")
        return

    from benchmarks.human_rating.trial_loader import load_eligible_trials
    from benchmarks.human_rating.sampling import sample_unique_trials
    from benchmarks.human_rating.blinding import build_blinded_plan
    from benchmarks.human_rating.artifact_writer import build_rating_queue, build_answer_key

    trials, _ = load_eligible_trials(
        results_root=os.path.join(_project_root, "results"), min_per_method=6)

    # Run 1
    s1, _ = sample_unique_trials(trials, seed=20260715)
    p1 = build_blinded_plan(s1, seed=20260716)
    q1 = build_rating_queue(p1, run_id="det-test")
    k1 = build_answer_key(p1, run_id="det-test", protocol_name="t",
                          sampling_seed=20260715, blinding_seed=20260716)

    # Run 2
    s2, _ = sample_unique_trials(trials, seed=20260715)
    p2 = build_blinded_plan(s2, seed=20260716)
    q2 = build_rating_queue(p2, run_id="det-test")
    k2 = build_answer_key(p2, run_id="det-test", protocol_name="t",
                          sampling_seed=20260715, blinding_seed=20260716)

    # Compare (exclude timestamps by comparing items only)
    assert q1["items"] == q2["items"]
    assert k1["items"] == k2["items"]
    assert [i.blinded_id for i in sorted(p1.items, key=lambda x: x.appearance_index)] == \
           [i.blinded_id for i in sorted(p2.items, key=lambda x: x.appearance_index)]

    print("  PASS: test_deterministic_regeneration")


# ---------------------------------------------------------------------------
# 5. Isolation regression
# ---------------------------------------------------------------------------

def test_rate_module_isolation():
    """rate.py does not import compiler, artifact_writer, or reference answer_key."""
    rate_path = os.path.join(_project_root, "benchmarks", "human_rating", "rate.py")
    with open(rate_path) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "compile" not in module.lower(), f"rate.py imports {module}"
            assert "artifact_writer" not in module.lower(), f"rate.py imports {module}"
            assert "answer_key" not in module.lower(), f"rate.py imports {module}"
    assert "answer_key" not in source.lower().replace("answer-key", "").replace("# answer", "")
    print("  PASS: test_rate_module_isolation")


def test_queue_contains_no_private_fields():
    """Queue JSON at no depth contains private metadata."""
    if not _has_real_results():
        print("  SKIP: test_queue_contains_no_private_fields")
        return

    from benchmarks.human_rating.trial_loader import load_eligible_trials
    from benchmarks.human_rating.sampling import sample_unique_trials
    from benchmarks.human_rating.blinding import build_blinded_plan
    from benchmarks.human_rating.artifact_writer import build_rating_queue, validate_queue_document

    trials, _ = load_eligible_trials(
        results_root=os.path.join(_project_root, "results"), min_per_method=6)
    selected, _ = sample_unique_trials(trials, seed=20260715)
    plan = build_blinded_plan(selected, seed=20260716)
    queue = build_rating_queue(plan, run_id="isolation-test")

    errors = validate_queue_document(queue)
    assert errors == [], f"Queue leakage: {errors}"

    # Deep string search
    queue_str = json.dumps(queue)
    for forbidden in ("source_method", "original_trial_id", "judge_score",
                      "integration_score", "duplicate_of_blinded_id",
                      "sampling_seed", "blinding_seed"):
        assert forbidden not in queue_str, f"Queue contains '{forbidden}'"

    print("  PASS: test_queue_contains_no_private_fields")


# ---------------------------------------------------------------------------
# 6. Source results unchanged
# ---------------------------------------------------------------------------

def test_workflow_does_not_modify_source_results():
    if not _has_real_results():
        print("  SKIP: test_workflow_does_not_modify_source_results")
        return

    results_dir = os.path.join(_project_root, "results")
    files_to_check = [
        "gpt4o_naive_concat/results_naive_concat.json",
        "gpt4o_vanilla_rag/results_vanilla_rag.json",
        "gpt4o_mem0_default/results_mem0_default.json",
        "gpt4o_kernel_shared/results_kernel_shared.json",
    ]
    hashes_before = {f: _hash_file(os.path.join(results_dir, f)) for f in files_to_check}

    # Run the full generation pipeline
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.sample_and_blind",
             "--generate", "--run-id", "hash-test", "--runs-dir", tmpdir],
            capture_output=True, text=True, cwd=_project_root,
        )

    hashes_after = {f: _hash_file(os.path.join(results_dir, f)) for f in files_to_check}
    assert hashes_before == hashes_after, "Source results modified!"
    print("  PASS: test_workflow_does_not_modify_source_results")


def test_generated_runs_are_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", "benchmarks/human_rating/runs/test/rater/queue.json"],
        capture_output=True, text=True, cwd=_project_root,
    )
    assert result.returncode == 0, "runs/ should be gitignored"
    print("  PASS: test_generated_runs_are_gitignored")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== End-to-End Tests ===\n")

    print("Lifecycle:")
    test_complete_lifecycle()

    print("\nFrozen protocol regression:")
    test_frozen_selected_trial_identities()
    test_frozen_blinded_plan()
    test_deterministic_regeneration()

    print("\nIsolation:")
    test_rate_module_isolation()
    test_queue_contains_no_private_fields()

    print("\nRepository boundary:")
    test_workflow_does_not_modify_source_results()
    test_generated_runs_are_gitignored()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
