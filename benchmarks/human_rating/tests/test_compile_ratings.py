"""Comprehensive compiler tests with known expected metrics.

Run:
    python benchmarks/human_rating/tests/test_compile_ratings.py
"""

import csv
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.compile_ratings import (
    compile_rating_run, write_compilation_outputs,
)
from benchmarks.human_rating.rate import _queue_fingerprint

METHODS = ["kernel_shared", "mem0_default", "naive_concat", "vanilla_rag"]


def _build_run(tmpdir, human_ratings=None, judge_scores=None, **overrides):
    """Build a complete valid 30-item run. Ratings/judge default to 3."""
    if human_ratings is None:
        human_ratings = [3] * 30
    if judge_scores is None:
        judge_scores = [3] * 30

    q_items = []
    for i in range(24):
        q_items.append({"blinded_id": f"HR-{i:04d}", "reference_context": f"Ctx {i}",
                        "question": f"Q{i}", "response": f"R{i}"})
    # Duplicates must have identical content to their originals
    for i in range(6):
        orig = q_items[i]
        q_items.append({"blinded_id": f"HR-{24+i:04d}",
                        "reference_context": orig["reference_context"],
                        "question": orig["question"], "response": orig["response"]})
    queue = {"schema_version": 1, "run_id": "test-run", "item_count": 30, "items": q_items}

    k_items = []
    for i in range(24):
        k_items.append({
            "blinded_id": f"HR-{i:04d}", "queue_position": i + 1,
            "source_method": METHODS[i % 4], "model": "gpt-4o",
            "original_trial_id": str(i), "evaluation_dimension": "integration",
            "judge_score": judge_scores[i], "profile_usage_score": judge_scores[i],
            "task_usage_score": judge_scores[i], "integration_score": judge_scores[i],
            "reference_context_provenance": "synthetic_source_context",
            "is_exact_model_visible_context": False, "duplicate_of_blinded_id": None,
        })
    for i in range(6):
        orig = k_items[i]
        k_items.append({
            "blinded_id": f"HR-{24+i:04d}", "queue_position": 25 + i,
            "source_method": orig["source_method"], "model": "gpt-4o",
            "original_trial_id": orig["original_trial_id"],
            "evaluation_dimension": "integration",
            "judge_score": orig["judge_score"], "profile_usage_score": orig["profile_usage_score"],
            "task_usage_score": orig["task_usage_score"], "integration_score": orig["integration_score"],
            "reference_context_provenance": "synthetic_source_context",
            "is_exact_model_visible_context": False,
            "duplicate_of_blinded_id": orig["blinded_id"],
        })

    answer_key = {"schema_version": 1, "run_id": "test-run", "protocol_name": "test",
                  "sampling_seed": 1, "blinding_seed": 2,
                  "item_count": 30, "unique_source_count": 24, "duplicate_count": 6,
                  "items": k_items}

    ratings = []
    for i in range(30):
        ratings.append({"schema_version": 1, "run_id": "test-run", "rater_id": "rater-01",
                        "blinded_id": f"HR-{i:04d}", "rating": human_ratings[i],
                        "note": overrides.get(f"note_{i}"), "flagged": overrides.get(f"flag_{i}", False),
                        "rated_at": "2026-07-15T10:00:00Z"})

    session = {"schema_version": 1, "run_id": "test-run", "rater_id": "rater-01",
               "queue_fingerprint": _queue_fingerprint(queue),
               "queue_item_count": 30, "ratings_file": "ratings.jsonl",
               "started_at": "2026-07-15T10:00:00Z"}

    rater_dir = Path(tmpdir) / "rater"
    private_dir = Path(tmpdir) / "private"
    rater_dir.mkdir(parents=True); private_dir.mkdir(parents=True)

    qp = rater_dir / "rating_queue.json"; qp.write_text(json.dumps(queue))
    sp = rater_dir / "rating_session.json"; sp.write_text(json.dumps(session))
    kp = private_dir / "answer_key.json"; kp.write_text(json.dumps(answer_key))
    rp = rater_dir / "ratings.jsonl"
    with open(rp, "w") as f:
        for r in ratings:
            f.write(json.dumps(r) + "\n")
    return qp, rp, sp, kp


def _compile(tmpdir, **kw):
    paths = _build_run(tmpdir, **kw)
    return compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                              session_path=paths[2], answer_key_path=paths[3])


# === Ratings validation ===

def test_extra_rating_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        # Append an extra line
        with open(paths[1], "a") as f:
            f.write(json.dumps({"schema_version":1,"run_id":"test-run","rater_id":"rater-01",
                    "blinded_id":"HR-0000","rating":5,"note":None,"flagged":False,"rated_at":"t"}) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "31" in str(e) or "Extra" in str(e) or "Duplicate" in str(e)
    print("  PASS: test_extra_rating_rejected")


def test_duplicate_rating_id_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        lines = paths[1].read_text().strip().split("\n")
        lines[1] = lines[0]  # Duplicate first ID
        paths[1].write_text("\n".join(lines) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "Duplicate" in str(e) or "order" in str(e).lower()
    print("  PASS: test_duplicate_rating_id_rejected")


def test_unknown_rating_id_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        lines = paths[1].read_text().strip().split("\n")
        rec = json.loads(lines[0]); rec["blinded_id"] = "HR-UNKNOWN"
        lines[0] = json.dumps(rec)
        paths[1].write_text("\n".join(lines) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "Unknown" in str(e) or "order" in str(e).lower()
    print("  PASS: test_unknown_rating_id_rejected")


def test_rater_id_mismatch_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        lines = paths[1].read_text().strip().split("\n")
        rec = json.loads(lines[5]); rec["rater_id"] = "wrong"
        lines[5] = json.dumps(rec)
        paths[1].write_text("\n".join(lines) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "Rater ID" in str(e)
    print("  PASS: test_rater_id_mismatch_rejected")


def test_rating_order_mismatch_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        lines = paths[1].read_text().strip().split("\n")
        lines[0], lines[1] = lines[1], lines[0]  # Swap order
        paths[1].write_text("\n".join(lines) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "order" in str(e).lower()
    print("  PASS: test_rating_order_mismatch_rejected")


# === Session validation ===

def test_queue_fingerprint_mismatch_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        sess = json.loads(paths[2].read_text())
        sess["queue_fingerprint"] = "sha256:wrong"
        paths[2].write_text(json.dumps(sess))
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "fingerprint" in str(e).lower()
    print("  PASS: test_queue_fingerprint_mismatch_rejected")


# === Answer-key validation ===

def test_wrong_model_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        key = json.loads(paths[3].read_text())
        key["items"][0]["model"] = "gpt-5"
        paths[3].write_text(json.dumps(key))
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "model" in str(e).lower()
    print("  PASS: test_wrong_model_rejected")


def test_judge_integration_mismatch_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        key = json.loads(paths[3].read_text())
        key["items"][0]["judge_score"] = 5  # != integration_score (3)
        paths[3].write_text(json.dumps(key))
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "integration" in str(e).lower()
    print("  PASS: test_judge_integration_mismatch_rejected")


# === Metrics with known values ===

def test_overall_summary_known_values():
    """Mixed ratings: known exact metrics."""
    # 24 primary items: ratings cycle [1,2,3,4,5,1,2,3...], judge all 3
    h = [(i % 5) + 1 for i in range(24)] + [3] * 6
    j = [3] * 30
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d, human_ratings=h, judge_scores=j)
    s = result.overall_summary
    assert s.item_count == 24
    # Mean human: (1+2+3+4+5)*4 + (1+2+3+4) = 15*4+10=70? No: 24 items cycling 1-5
    # Actually [1,2,3,4,5,1,2,3,4,5,1,2,3,4,5,1,2,3,4,5,1,2,3,4] = 5 full cycles - 1 item
    # Sum = 4*(1+2+3+4+5) + (1+2+3+4) = 60+10 = 70, mean = 70/24 ≈ 2.917
    assert abs(s.mean_human_rating - 70/24) < 0.001
    assert s.mean_judge_score == 3.0
    # Exact agreement: only where human==3 (positions 2,7,12,17,22 → indices 2,7,12,17,22)
    # That's items where (i%5)+1==3, i.e. i%5==2, i in {2,7,12,17,22} → 5 items
    assert s.exact_agreement_count == 5
    assert abs(s.exact_agreement_rate - 5/24) < 0.001
    # Within-one: |h-3|<=1 → h in {2,3,4}. i%5 in {1,2,3} → 3 out of 5 per cycle
    # 4 full cycles: 12, plus partial [1,2,3,4]: 3 match → 15 total? Wait:
    # indices 0-23: i%5: 0,1,2,3,4,0,1,2,3,4,...,0,1,2,3 → positions with val in{2,3,4}:
    # val=(i%5)+1: 1,2,3,4,5,1,2,3,4,5,...1,2,3,4 → values 2,3,4 at i%5 in {1,2,3}
    # Count: in 24 items, i%5==1: 5 times, i%5==2: 5 times, i%5==3: 5 times → 15
    assert s.within_one_count == 15
    print("  PASS: test_overall_summary_known_values")


def test_primary_excludes_duplicates():
    """Duplicates don't contaminate primary metrics."""
    h = [3] * 24 + [1] * 6  # Primary match perfectly, dups differ
    j = [3] * 30
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d, human_ratings=h, judge_scores=j)
    assert result.overall_summary.exact_agreement_rate == 1.0
    assert result.appearance_sensitivity_summary.exact_agreement_rate < 1.0
    print("  PASS: test_primary_excludes_duplicates")


def test_sensitivity_uses_all_30():
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
    assert result.appearance_sensitivity_summary.item_count == 30
    print("  PASS: test_sensitivity_uses_all_30")


def test_confusion_matrix_known_cells():
    """All human=3, judge=3 → cell [3][3]=24, all others 0."""
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
    assert result.confusion_matrix[3][3] == 24
    assert result.confusion_matrix[1][1] == 0
    total = sum(result.confusion_matrix[h][j] for h in range(1,6) for j in range(1,6))
    assert total == 24
    print("  PASS: test_confusion_matrix_known_cells")


def test_duplicate_consistency_known():
    """All same rating → 100% exact."""
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
    ds = result.duplicate_summary
    assert ds.pair_count == 6
    assert ds.exact_match_rate == 1.0
    assert ds.mean_absolute_difference == 0.0
    print("  PASS: test_duplicate_consistency_known")


def test_duplicate_consistency_mixed():
    """Originals=3, duplicates=5 → diff=2 each."""
    h = [3]*24 + [5]*6
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d, human_ratings=h)
    ds = result.duplicate_summary
    assert ds.exact_match_rate == 0.0
    assert ds.mean_absolute_difference == 2.0
    assert ds.max_absolute_difference == 2
    print("  PASS: test_duplicate_consistency_mixed")


def test_method_summaries_six_each():
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
    assert len(result.method_summaries) == 4
    for ms in result.method_summaries:
        assert ms.item_count == 6
    print("  PASS: test_method_summaries_six_each")


def test_notes_and_flags_preserved():
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d, note_0="My note", flag_0=True)
    item = next(i for i in result.all_appearances if i.blinded_id == "HR-0000")
    assert item.note == "My note"
    assert item.flagged is True
    print("  PASS: test_notes_and_flags_preserved")


# === Output files ===

def test_output_row_counts():
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
        out = Path(d) / "compiled"
        write_compilation_outputs(result, output_dir=out, run_id="t", rater_id="r", protocol_name="p")
        # primary_items.csv: header + 24 rows
        with open(out / "primary_items.csv") as f:
            lines = list(csv.reader(f))
        assert len(lines) == 25  # 1 header + 24
        # all_appearances.csv: header + 30
        with open(out / "all_appearances.csv") as f:
            lines = list(csv.reader(f))
        assert len(lines) == 31
        # method_summary.csv: header + 4
        with open(out / "method_summary.csv") as f:
            lines = list(csv.reader(f))
        assert len(lines) == 5
        # duplicate_consistency.csv: header + 6
        with open(out / "duplicate_consistency.csv") as f:
            lines = list(csv.reader(f))
        assert len(lines) == 7
        # confusion_matrix.csv: header + 5
        with open(out / "confusion_matrix.csv") as f:
            lines = list(csv.reader(f))
        assert len(lines) == 6
    print("  PASS: test_output_row_counts")


def test_summary_protocol_limitations():
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
        out = Path(d) / "compiled"
        write_compilation_outputs(result, output_dir=out, run_id="t", rater_id="r", protocol_name="p")
        with open(out / "summary.json") as f:
            s = json.load(f)
        lim = s["limitations"]
        assert lim["question_stratification"] is None
        assert lim["display_context_provenance"] == "synthetic_source_context"
        assert lim["is_exact_model_visible_context"] is False
        assert lim["primary_judge_dimension"] == "integration"
    print("  PASS: test_summary_protocol_limitations")


def test_overwrite_protection():
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
        out = Path(d) / "compiled"
        write_compilation_outputs(result, output_dir=out, run_id="t", rater_id="r", protocol_name="p")
        try:
            write_compilation_outputs(result, output_dir=out, run_id="t", rater_id="r", protocol_name="p")
            assert False
        except FileExistsError:
            pass
    print("  PASS: test_overwrite_protection")


def test_compiled_output_permissions_posix():
    if os.name != "posix":
        print("  SKIP: test_compiled_output_permissions_posix")
        return
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
        out = Path(d) / "compiled"
        write_compilation_outputs(result, output_dir=out, run_id="t", rater_id="r", protocol_name="p")
        for f in out.iterdir():
            mode = stat.S_IMODE(os.stat(f).st_mode)
            assert mode == 0o600, f"{f.name}: {oct(mode)}"
    print("  PASS: test_compiled_output_permissions_posix")


def test_incomplete_ratings_rejected():
    with tempfile.TemporaryDirectory() as d:
        paths = _build_run(d)
        lines = paths[1].read_text().strip().split("\n")[:29]
        paths[1].write_text("\n".join(lines) + "\n")
        try:
            compile_rating_run(queue_path=paths[0], ratings_path=paths[1],
                               session_path=paths[2], answer_key_path=paths[3])
            assert False
        except ValueError as e:
            assert "29" in str(e)
    print("  PASS: test_incomplete_ratings_rejected")


def test_deterministic_json_output():
    with tempfile.TemporaryDirectory() as d:
        result = _compile(d)
        out1 = Path(d) / "c1"; out2 = Path(d) / "c2"
        write_compilation_outputs(result, output_dir=out1, run_id="t", rater_id="r", protocol_name="p")
        write_compilation_outputs(result, output_dir=out2, run_id="t", rater_id="r", protocol_name="p")
        assert (out1/"summary.json").read_text() == (out2/"summary.json").read_text()
    print("  PASS: test_deterministic_json_output")


# ---------------------------------------------------------------------------

def main():
    print("=== Compile Ratings Tests ===\n")

    print("Ratings validation:")
    test_extra_rating_rejected()
    test_duplicate_rating_id_rejected()
    test_unknown_rating_id_rejected()
    test_rater_id_mismatch_rejected()
    test_rating_order_mismatch_rejected()

    print("\nSession/key validation:")
    test_queue_fingerprint_mismatch_rejected()
    test_wrong_model_rejected()
    test_judge_integration_mismatch_rejected()

    print("\nMetrics:")
    test_overall_summary_known_values()
    test_primary_excludes_duplicates()
    test_sensitivity_uses_all_30()
    test_confusion_matrix_known_cells()
    test_duplicate_consistency_known()
    test_duplicate_consistency_mixed()
    test_method_summaries_six_each()
    test_notes_and_flags_preserved()

    print("\nOutputs:")
    test_output_row_counts()
    test_summary_protocol_limitations()
    test_overwrite_protection()
    test_compiled_output_permissions_posix()
    test_incomplete_ratings_rejected()
    test_deterministic_json_output()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
