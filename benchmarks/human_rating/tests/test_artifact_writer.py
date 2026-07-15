"""Tests for artifact writing (queue + answer key generation).

Run:
    python benchmarks/human_rating/tests/test_artifact_writer.py
"""

import ast
import json
import os
import stat
import sys
import tempfile

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.artifact_writer import (
    ALLOWED_QUEUE_ITEM_KEYS, FORBIDDEN_QUEUE_KEYS,
    WrittenArtifacts, build_answer_key, build_rating_queue,
    validate_artifact_pair, validate_answer_key_document,
    validate_queue_document, write_rating_artifacts,
)
from benchmarks.human_rating.blinding import build_blinded_plan
from benchmarks.human_rating.paths import get_run_paths
from benchmarks.human_rating.schemas import SourceTrial, VALID_SOURCE_METHODS


def _make_trial(method, tid, score=3):
    return SourceTrial(
        source_method=method, original_trial_id=str(tid), model="gpt-4o",
        evaluation_dimension="integration",
        reference_context=f"Ctx {method}/{tid}",
        reference_context_provenance="synthetic_source_context",
        is_exact_model_visible_context=False,
        question=f"Q{tid}", response=f"R{tid}",
        judge_score=score, profile_usage_score=score,
        task_usage_score=score, integration_score=score,
    )


def _make_plan(seed=42):
    trials = []
    for method in sorted(VALID_SOURCE_METHODS):
        for i in range(6):
            trials.append(_make_trial(method, i))
    return build_blinded_plan(trials, seed=seed)


def _write_in_tmp(plan, run_id="test-run", overwrite=False):
    with tempfile.TemporaryDirectory() as tmpdir:
        run_paths = get_run_paths(run_id, base_dir=tmpdir)
        result = write_rating_artifacts(
            plan, run_paths=run_paths, run_id=run_id,
            protocol_name="test_protocol",
            sampling_seed=111, blinding_seed=222,
            overwrite=overwrite,
        )
        # Read back
        with open(result.rating_queue_path) as f:
            queue = json.load(f)
        with open(result.answer_key_path) as f:
            key = json.load(f)
        return result, queue, key, tmpdir, run_paths
    return None


# --- Tests ---

def test_queue_30_items():
    plan = _make_plan()
    queue = build_rating_queue(plan, run_id="t")
    assert len(queue["items"]) == 30
    assert queue["item_count"] == 30
    print("  PASS: test_queue_30_items")


def test_queue_item_exactly_four_fields():
    plan = _make_plan()
    queue = build_rating_queue(plan, run_id="t")
    for item in queue["items"]:
        assert set(item.keys()) == ALLOWED_QUEUE_ITEM_KEYS
    print("  PASS: test_queue_item_exactly_four_fields")


def test_queue_no_private_leakage():
    plan = _make_plan()
    queue = build_rating_queue(plan, run_id="t")
    errors = validate_queue_document(queue)
    assert errors == [], f"Leakage: {errors}"
    print("  PASS: test_queue_no_private_leakage")


def test_answer_key_30_entries():
    plan = _make_plan()
    key = build_answer_key(plan, run_id="t", protocol_name="p", sampling_seed=1, blinding_seed=2)
    assert len(key["items"]) == 30
    assert key["unique_source_count"] == 24
    assert key["duplicate_count"] == 6
    print("  PASS: test_answer_key_30_entries")


def test_answer_key_6_duplicates():
    plan = _make_plan()
    key = build_answer_key(plan, run_id="t", protocol_name="p", sampling_seed=1, blinding_seed=2)
    dups = [it for it in key["items"] if it["duplicate_of_blinded_id"] is not None]
    assert len(dups) == 6
    print("  PASS: test_answer_key_6_duplicates")


def test_queue_key_id_order_match():
    plan = _make_plan()
    queue = build_rating_queue(plan, run_id="t")
    key = build_answer_key(plan, run_id="t", protocol_name="p", sampling_seed=1, blinding_seed=2)
    q_ids = [it["blinded_id"] for it in queue["items"]]
    k_ids = [it["blinded_id"] for it in key["items"]]
    assert q_ids == k_ids
    print("  PASS: test_queue_key_id_order_match")


def test_duplicate_queue_content_identical():
    plan = _make_plan()
    queue = build_rating_queue(plan, run_id="t")
    key = build_answer_key(plan, run_id="t", protocol_name="p", sampling_seed=1, blinding_seed=2)
    id_to_q = {it["blinded_id"]: it for it in queue["items"]}
    for k_item in key["items"]:
        ref = k_item.get("duplicate_of_blinded_id")
        if ref:
            dup_q = id_to_q[k_item["blinded_id"]]
            orig_q = id_to_q[ref]
            assert dup_q["reference_context"] == orig_q["reference_context"]
            assert dup_q["question"] == orig_q["question"]
            assert dup_q["response"] == orig_q["response"]
    print("  PASS: test_duplicate_queue_content_identical")


def test_answer_key_metadata():
    plan = _make_plan()
    key = build_answer_key(plan, run_id="t", protocol_name="p", sampling_seed=1, blinding_seed=2)
    for item in key["items"]:
        assert item["evaluation_dimension"] == "integration"
        assert item["judge_score"] == item["integration_score"]
        assert item["model"] == "gpt-4o"
        assert item["is_exact_model_visible_context"] is False
    print("  PASS: test_answer_key_metadata")


def test_deterministic_documents():
    plan = _make_plan(seed=77)
    q1 = build_rating_queue(plan, run_id="t")
    q2 = build_rating_queue(plan, run_id="t")
    assert json.dumps(q1, sort_keys=True) == json.dumps(q2, sort_keys=True)
    print("  PASS: test_deterministic_documents")


def test_paths_are_separate():
    with tempfile.TemporaryDirectory() as tmpdir:
        rp = get_run_paths("test", base_dir=tmpdir)
        assert os.path.dirname(os.path.abspath(rp.rating_queue_path)) != \
               os.path.dirname(os.path.abspath(rp.answer_key_path))
    print("  PASS: test_paths_are_separate")


def test_overwrite_protection():
    plan = _make_plan()
    with tempfile.TemporaryDirectory() as tmpdir:
        rp = get_run_paths("test", base_dir=tmpdir)
        write_rating_artifacts(
            plan, run_paths=rp, run_id="test",
            protocol_name="p", sampling_seed=1, blinding_seed=2,
        )
        try:
            write_rating_artifacts(
                plan, run_paths=rp, run_id="test",
                protocol_name="p", sampling_seed=1, blinding_seed=2,
            )
            assert False, "Should raise FileExistsError"
        except FileExistsError:
            pass
    print("  PASS: test_overwrite_protection")


def test_successful_overwrite():
    plan = _make_plan()
    with tempfile.TemporaryDirectory() as tmpdir:
        rp = get_run_paths("test", base_dir=tmpdir)
        write_rating_artifacts(
            plan, run_paths=rp, run_id="test",
            protocol_name="p", sampling_seed=1, blinding_seed=2,
        )
        # Should succeed with overwrite=True
        result = write_rating_artifacts(
            plan, run_paths=rp, run_id="test",
            protocol_name="p", sampling_seed=1, blinding_seed=2,
            overwrite=True,
        )
        assert result.item_count == 30
    print("  PASS: test_successful_overwrite")


def test_answer_key_permissions_posix():
    """Answer key should have 0600 permissions on POSIX."""
    if os.name != "posix":
        print("  SKIP: test_answer_key_permissions_posix (not POSIX)")
        return
    plan = _make_plan()
    with tempfile.TemporaryDirectory() as tmpdir:
        rp = get_run_paths("test", base_dir=tmpdir)
        result = write_rating_artifacts(
            plan, run_paths=rp, run_id="test",
            protocol_name="p", sampling_seed=1, blinding_seed=2,
        )
        mode = stat.S_IMODE(os.stat(result.answer_key_path).st_mode)
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"
    print("  PASS: test_answer_key_permissions_posix")


def test_pair_validation():
    plan = _make_plan()
    queue = build_rating_queue(plan, run_id="t")
    key = build_answer_key(plan, run_id="t", protocol_name="p", sampling_seed=1, blinding_seed=2)
    errors = validate_artifact_pair(queue, key)
    assert errors == [], f"Pair errors: {errors}"
    print("  PASS: test_pair_validation")


def test_rate_cli_no_answer_key_imports():
    """rate.py must not import answer_key or private-directory code."""
    rate_path = os.path.join(_project_root, "benchmarks", "human_rating", "rate.py")
    with open(rate_path) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "answer_key" not in module.lower(), f"rate.py imports {module}"
            assert "private" not in module.lower(), f"rate.py imports {module}"
            assert "artifact_writer" not in module.lower(), f"rate.py imports {module}"
    assert "answer_key" not in source.replace("answer-key", ""), "rate.py references answer_key"
    print("  PASS: test_rate_cli_no_answer_key_imports")


def test_real_results_generate():
    """Real finalized results generate a valid queue/key pair."""
    results_dir = os.path.join(_project_root, "results")
    if not os.path.isdir(os.path.join(results_dir, "gpt4o_naive_concat")):
        print("  SKIP: test_real_results_generate (results not present)")
        return
    from benchmarks.human_rating.trial_loader import load_eligible_trials
    from benchmarks.human_rating.sampling import sample_unique_trials
    trials, _ = load_eligible_trials(results_root=results_dir, min_per_method=6)
    selected, _ = sample_unique_trials(trials, seed=20260715)
    plan = build_blinded_plan(selected, seed=20260716)
    with tempfile.TemporaryDirectory() as tmpdir:
        rp = get_run_paths("real-test", base_dir=tmpdir)
        result = write_rating_artifacts(
            plan, run_paths=rp, run_id="real-test",
            protocol_name="mixed_personalization_source_grounded_v1",
            sampling_seed=20260715, blinding_seed=20260716,
        )
        assert result.item_count == 30
        assert result.unique_source_count == 24
        assert result.duplicate_count == 6
        # Read and validate
        with open(result.rating_queue_path) as f:
            queue = json.load(f)
        assert validate_queue_document(queue) == []
    print("  PASS: test_real_results_generate")


def main():
    print("=== Artifact Writer Tests ===\n")
    test_queue_30_items()
    test_queue_item_exactly_four_fields()
    test_queue_no_private_leakage()
    test_answer_key_30_entries()
    test_answer_key_6_duplicates()
    test_queue_key_id_order_match()
    test_duplicate_queue_content_identical()
    test_answer_key_metadata()
    test_deterministic_documents()
    test_paths_are_separate()
    test_overwrite_protection()
    test_successful_overwrite()
    test_answer_key_permissions_posix()
    test_pair_validation()
    test_rate_cli_no_answer_key_imports()
    test_real_results_generate()
    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
