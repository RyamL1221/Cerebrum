"""Tests for the compilation module.

Uses synthetic fixtures with known expected metrics.

Run:
    python benchmarks/human_rating/tests/test_compile_ratings.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.compile_ratings import (
    compile_rating_run, write_compilation_outputs, CompilationResult,
)
from benchmarks.human_rating.rate import _queue_fingerprint


# ---------------------------------------------------------------------------
# Fixture: build a complete valid run with known scores
# ---------------------------------------------------------------------------

METHODS = ["kernel_shared", "mem0_default", "naive_concat", "vanilla_rag"]


def _build_run(tmpdir, human_ratings=None, judge_scores=None):
    """Build a complete valid run with 30 items (24 originals + 6 duplicates).

    Default: human=3, judge=3 for all (100% exact agreement).
    """
    if human_ratings is None:
        human_ratings = [3] * 30
    if judge_scores is None:
        judge_scores = [3] * 30

    # Build queue (30 items)
    q_items = []
    for i in range(30):
        q_items.append({
            "blinded_id": f"HR-{i:04d}",
            "reference_context": f"Ctx {i}",
            "question": f"Q{i}",
            "response": f"R{i}",
        })
    queue = {"schema_version": 1, "run_id": "test-run", "item_count": 30, "items": q_items}

    # Build answer key: first 24 are originals, last 6 are duplicates of first 6
    k_items = []
    method_idx = 0
    for i in range(24):
        m = METHODS[i % 4]
        k_items.append({
            "blinded_id": f"HR-{i:04d}",
            "queue_position": i + 1,
            "source_method": m,
            "model": "gpt-4o",
            "original_trial_id": str(i),
            "evaluation_dimension": "integration",
            "judge_score": judge_scores[i],
            "profile_usage_score": judge_scores[i],
            "task_usage_score": judge_scores[i],
            "integration_score": judge_scores[i],
            "reference_context_provenance": "synthetic_source_context",
            "is_exact_model_visible_context": False,
            "duplicate_of_blinded_id": None,
        })
    # 6 duplicates of items 0-5
    for i in range(6):
        orig = k_items[i]
        k_items.append({
            "blinded_id": f"HR-{24+i:04d}",
            "queue_position": 24 + i + 1,
            "source_method": orig["source_method"],
            "model": "gpt-4o",
            "original_trial_id": orig["original_trial_id"],
            "evaluation_dimension": "integration",
            "judge_score": orig["judge_score"],
            "profile_usage_score": orig["profile_usage_score"],
            "task_usage_score": orig["task_usage_score"],
            "integration_score": orig["integration_score"],
            "reference_context_provenance": "synthetic_source_context",
            "is_exact_model_visible_context": False,
            "duplicate_of_blinded_id": orig["blinded_id"],
        })

    answer_key = {
        "schema_version": 1, "run_id": "test-run", "protocol_name": "test",
        "sampling_seed": 1, "blinding_seed": 2,
        "item_count": 30, "unique_source_count": 24, "duplicate_count": 6,
        "items": k_items,
    }

    # Build ratings
    ratings = []
    for i in range(30):
        ratings.append({
            "schema_version": 1, "run_id": "test-run", "rater_id": "rater-01",
            "blinded_id": f"HR-{i:04d}", "rating": human_ratings[i],
            "note": None, "flagged": False, "rated_at": "2026-07-15T10:00:00Z",
        })

    # Build session
    session = {
        "schema_version": 1, "run_id": "test-run", "rater_id": "rater-01",
        "queue_fingerprint": _queue_fingerprint(queue),
        "queue_item_count": 30, "ratings_file": "ratings.jsonl",
        "started_at": "2026-07-15T10:00:00Z",
    }

    # Write files
    rater_dir = Path(tmpdir) / "rater"
    private_dir = Path(tmpdir) / "private"
    rater_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True)

    queue_path = rater_dir / "rating_queue.json"
    ratings_path = rater_dir / "ratings.jsonl"
    session_path = rater_dir / "rating_session.json"
    key_path = private_dir / "answer_key.json"

    queue_path.write_text(json.dumps(queue))
    session_path.write_text(json.dumps(session))
    key_path.write_text(json.dumps(answer_key))
    with open(ratings_path, "w") as f:
        for r in ratings:
            f.write(json.dumps(r) + "\n")

    return queue_path, ratings_path, session_path, key_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_complete_valid_run():
    """A complete valid run compiles without error."""
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        result = compile_rating_run(
            queue_path=paths[0], ratings_path=paths[1],
            session_path=paths[2], answer_key_path=paths[3],
        )
        assert len(result.primary_items) == 24
        assert len(result.all_appearances) == 30
        assert len(result.duplicate_pairs) == 6
        assert len(result.method_summaries) == 4
    print("  PASS: test_complete_valid_run")


def test_exactly_24_primary_rows():
    with tempfile.TemporaryDirectory() as d:
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d),
        )))
        assert len(result.primary_items) == 24
        assert all(not i.is_duplicate_appearance for i in result.primary_items)
    print("  PASS: test_exactly_24_primary_rows")


def test_exactly_6_duplicate_pairs():
    with tempfile.TemporaryDirectory() as d:
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d),
        )))
        assert len(result.duplicate_pairs) == 6
    print("  PASS: test_exactly_6_duplicate_pairs")


def test_six_primary_items_per_method():
    with tempfile.TemporaryDirectory() as d:
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d),
        )))
        for ms in result.method_summaries:
            assert ms.item_count == 6
    print("  PASS: test_six_primary_items_per_method")


def test_exact_agreement_100_percent():
    """All ratings == judge scores → 100% exact agreement."""
    with tempfile.TemporaryDirectory() as d:
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d, human_ratings=[3]*30, judge_scores=[3]*30),
        )))
        assert result.overall_summary.exact_agreement_rate == 1.0
        assert result.overall_summary.within_one_rate == 1.0
        assert result.overall_summary.mean_absolute_error == 0.0
    print("  PASS: test_exact_agreement_100_percent")


def test_score_difference_correctness():
    """Known diff: human=5, judge=3 → diff=+2, abs=2, not exact, within_one=False."""
    with tempfile.TemporaryDirectory() as d:
        h = [5] * 30
        j = [3] * 30
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d, human_ratings=h, judge_scores=j),
        )))
        assert result.overall_summary.mean_signed_difference == 2.0
        assert result.overall_summary.mean_absolute_error == 2.0
        assert result.overall_summary.exact_agreement_rate == 0.0
        assert result.overall_summary.within_one_rate == 0.0
    print("  PASS: test_score_difference_correctness")


def test_within_one_correctness():
    """human=4, judge=3 → within_one=True, exact=False."""
    with tempfile.TemporaryDirectory() as d:
        h = [4] * 30
        j = [3] * 30
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d, human_ratings=h, judge_scores=j),
        )))
        assert result.overall_summary.exact_agreement_rate == 0.0
        assert result.overall_summary.within_one_rate == 1.0
    print("  PASS: test_within_one_correctness")


def test_confusion_matrix_totals_24():
    with tempfile.TemporaryDirectory() as d:
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d),
        )))
        total = sum(result.confusion_matrix[h][j] for h in range(1, 6) for j in range(1, 6))
        assert total == 24
    print("  PASS: test_confusion_matrix_totals_24")


def test_duplicate_consistency_known():
    """Duplicates with same rating → 100% exact consistency."""
    with tempfile.TemporaryDirectory() as d:
        # All same rating → duplicates match perfectly
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d, human_ratings=[3]*30),
        )))
        assert result.duplicate_summary.exact_match_rate == 1.0
        assert result.duplicate_summary.within_one_rate == 1.0
        assert result.duplicate_summary.mean_absolute_difference == 0.0
    print("  PASS: test_duplicate_consistency_known")


def test_duplicate_consistency_mixed():
    """Duplicates with different ratings show correct metrics."""
    with tempfile.TemporaryDirectory() as d:
        h = [3] * 24 + [5, 5, 5, 5, 5, 5]  # Originals=3, duplicates=5
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d, human_ratings=h),
        )))
        # Original items 0-5 rated 3, duplicates (24-29) rated 5 → diff=2
        assert result.duplicate_summary.exact_match_rate == 0.0
        assert result.duplicate_summary.mean_absolute_difference == 2.0
    print("  PASS: test_duplicate_consistency_mixed")


def test_incomplete_ratings_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        # Remove last rating line
        rp = paths[1]
        lines = rp.read_text().strip().split("\n")
        rp.write_text("\n".join(lines[:29]) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "29" in str(e) and "30" in str(e)
    print("  PASS: test_incomplete_ratings_rejected")


def test_run_id_mismatch_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        # Modify a rating's run_id
        rp = paths[1]
        lines = rp.read_text().strip().split("\n")
        rec = json.loads(lines[0])
        rec["run_id"] = "wrong"
        lines[0] = json.dumps(rec)
        rp.write_text("\n".join(lines) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "mismatch" in str(e).lower()
    print("  PASS: test_run_id_mismatch_rejected")


def test_primary_excludes_duplicates():
    """Primary metrics use only 24 originals, not duplicates."""
    with tempfile.TemporaryDirectory() as d:
        # Give duplicates extreme ratings to detect contamination
        h = [3] * 24 + [1, 1, 1, 1, 1, 1]
        j = [3] * 30
        result = compile_rating_run(**dict(zip(
            ["queue_path", "ratings_path", "session_path", "answer_key_path"],
            _build_run(d, human_ratings=h, judge_scores=j),
        )))
        # Primary should show 100% exact (all 3==3)
        assert result.overall_summary.exact_agreement_rate == 1.0
        # Sensitivity includes duplicates (1 vs 3) → lower agreement
        assert result.appearance_sensitivity_summary.exact_agreement_rate < 1.0
    print("  PASS: test_primary_excludes_duplicates")


def test_write_outputs():
    """Compilation outputs are written correctly."""
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        result = compile_rating_run(
            queue_path=paths[0], ratings_path=paths[1],
            session_path=paths[2], answer_key_path=paths[3],
        )
        out_dir = Path(d) / "compiled"
        write_compilation_outputs(
            result, output_dir=out_dir, run_id="test-run",
            rater_id="rater-01", protocol_name="test",
        )
        assert (out_dir / "summary.json").exists()
        assert (out_dir / "primary_items.csv").exists()
        assert (out_dir / "all_appearances.csv").exists()
        assert (out_dir / "method_summary.csv").exists()
        assert (out_dir / "duplicate_consistency.csv").exists()
        assert (out_dir / "confusion_matrix.csv").exists()
        # summary.json has limitations
        with open(out_dir / "summary.json") as f:
            s = json.load(f)
        assert s["limitations"]["primary_judge_dimension"] == "integration"
        assert s["limitations"]["is_exact_model_visible_context"] is False
    print("  PASS: test_write_outputs")


def test_overwrite_protection():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        result = compile_rating_run(
            queue_path=paths[0], ratings_path=paths[1],
            session_path=paths[2], answer_key_path=paths[3],
        )
        out_dir = Path(d) / "compiled"
        write_compilation_outputs(result, output_dir=out_dir,
                                  run_id="t", rater_id="r", protocol_name="p")
        try:
            write_compilation_outputs(result, output_dir=out_dir,
                                      run_id="t", rater_id="r", protocol_name="p")
            assert False
        except FileExistsError:
            pass
    print("  PASS: test_overwrite_protection")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def main():
    print("=== Compile Ratings Tests ===\n")
    test_complete_valid_run()
    test_exactly_24_primary_rows()
    test_exactly_6_duplicate_pairs()
    test_six_primary_items_per_method()
    test_exact_agreement_100_percent()
    test_score_difference_correctness()
    test_within_one_correctness()
    test_confusion_matrix_totals_24()
    test_duplicate_consistency_known()
    test_duplicate_consistency_mixed()
    test_incomplete_ratings_rejected()
    test_run_id_mismatch_rejected()
    test_primary_excludes_duplicates()
    test_write_outputs()
    test_overwrite_protection()
    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
