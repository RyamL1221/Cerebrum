"""Tests for the interactive rating CLI.

Uses mocked input/output to avoid manual interaction.

Run:
    python benchmarks/human_rating/tests/test_rate.py
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.rate import (
    _load_existing_ratings, _load_or_create_session, _queue_fingerprint,
    _run_rating_session, _sanitize_display, validate_rating_queue,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_queue(n=5, run_id="test-run"):
    items = [
        {"blinded_id": f"HR-{i:04d}", "reference_context": f"Ctx {i}",
         "question": f"Q{i}", "response": f"R{i}"}
        for i in range(n)
    ]
    return {"schema_version": 1, "run_id": run_id, "item_count": n, "items": items}


def _write_queue(tmpdir, queue_data):
    p = Path(tmpdir) / "rater" / "rating_queue.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(queue_data))
    return p


def _mock_input(responses):
    """Create an input function that yields from a list."""
    it = iter(responses)
    def _input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            return None
    return _input


def _capture_output():
    """Create a list-capturing print function."""
    lines = []
    def _print(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))
    return _print, lines


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_valid_queue_loads():
    queue = _make_queue()
    errors = validate_rating_queue(queue)
    assert errors == []
    print("  PASS: test_valid_queue_loads")


def test_malformed_queue_rejected():
    queue = {"schema_version": 1}  # missing items
    errors = validate_rating_queue(queue)
    assert len(errors) > 0
    print("  PASS: test_malformed_queue_rejected")


def test_private_field_rejected():
    queue = _make_queue()
    queue["items"][0]["source_method"] = "naive_concat"
    errors = validate_rating_queue(queue)
    assert any("forbidden" in e for e in errors)
    print("  PASS: test_private_field_rejected")


def test_session_created_on_first_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        queue_path = _write_queue(tmpdir, queue)
        session_path = queue_path.parent / "rating_session.json"
        fp = _queue_fingerprint(queue)
        _load_or_create_session(session_path, "test-run", "rater-01", fp, 5)
        assert session_path.exists()
        data = json.loads(session_path.read_text())
        assert data["rater_id"] == "rater-01"
        assert data["queue_fingerprint"] == fp
    print("  PASS: test_session_created_on_first_run")


def test_queue_fingerprint_deterministic():
    queue = _make_queue()
    fp1 = _queue_fingerprint(queue)
    fp2 = _queue_fingerprint(queue)
    assert fp1 == fp2
    assert fp1.startswith("sha256:")
    print("  PASS: test_queue_fingerprint_deterministic")


def test_changed_queue_rejected_on_resume():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        queue_path = _write_queue(tmpdir, queue)
        session_path = queue_path.parent / "rating_session.json"
        fp = _queue_fingerprint(queue)
        _load_or_create_session(session_path, "test-run", "rater-01", fp, 5)
        # Now try with different fingerprint
        try:
            _load_or_create_session(session_path, "test-run", "rater-01", "sha256:different", 5)
            assert False
        except ValueError as e:
            assert "does not match" in str(e)
    print("  PASS: test_changed_queue_rejected_on_resume")


def test_one_rating_appends_one_line():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=3)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, lines = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["4", "q"]), output_fn=out_fn,
        )
        assert ratings_path.exists()
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n") if l.strip()]
        assert len(records) == 1
        assert records[0]["rating"] == 4
        assert records[0]["blinded_id"] == "HR-0000"
    print("  PASS: test_one_rating_appends_one_line")


def test_invalid_rating_does_not_advance():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=2)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, lines = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["0", "6", "abc", "3", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert len(records) == 1  # Only one valid rating saved
        assert records[0]["rating"] == 3
    print("  PASS: test_invalid_rating_does_not_advance")


def test_rating_1_and_5_accepted():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=2)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["1", "5", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert records[0]["rating"] == 1
        assert records[1]["rating"] == 5
    print("  PASS: test_rating_1_and_5_accepted")


def test_note_saved():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=2)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["n", "Good response", "4", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert records[0]["note"] == "Good response"
    print("  PASS: test_note_saved")


def test_note_cleared():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=2)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["n", "temp note", "n", "", "3", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert records[0]["note"] is None
    print("  PASS: test_note_cleared")


def test_flag_toggled():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=2)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, lines = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["f", "3", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert records[0]["flagged"] is True
    print("  PASS: test_flag_toggled")


def test_quit_preserves_progress():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=5)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["3", "4", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert len(records) == 2
    print("  PASS: test_quit_preserves_progress")


def test_eof_preserves_progress():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=5)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture_output()
        # Simulate EOF after 2 ratings by returning None
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["2", "3"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert len(records) == 2
    print("  PASS: test_eof_preserves_progress")


def test_resume_starts_at_first_unrated():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=5)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, lines = _capture_output()
        # Rate first 2
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["3", "4", "q"]), output_fn=out_fn,
        )
        # Resume — should start at item 3
        out_fn2, lines2 = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["5", "q"]), output_fn=out_fn2,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert len(records) == 3
        assert records[2]["blinded_id"] == "HR-0002"
        assert records[2]["rating"] == 5
    print("  PASS: test_resume_starts_at_first_unrated")


def test_completed_session_exits():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=3)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture_output()
        # Rate all 3
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["3", "4", "5"]), output_fn=out_fn,
        )
        # Try to resume — should say complete
        out_fn2, lines2 = _capture_output()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input([]), output_fn=out_fn2,
        )
        assert any("complete" in l.lower() for l in lines2)
    print("  PASS: test_completed_session_exits")


def test_duplicate_blinded_id_in_ratings_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=3)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        # Write a duplicate
        rec = {"schema_version": 1, "run_id": "test-run", "rater_id": "rater-01",
               "blinded_id": "HR-0000", "rating": 3, "note": None, "flagged": False, "rated_at": "t"}
        ratings_path.write_text(json.dumps(rec) + "\n" + json.dumps(rec) + "\n")
        queue_ids = {"HR-0000", "HR-0001", "HR-0002"}
        try:
            _load_existing_ratings(ratings_path, queue_ids, "test-run", "rater-01")
            assert False
        except ValueError as e:
            assert "Duplicate" in str(e)
    print("  PASS: test_duplicate_blinded_id_in_ratings_rejected")


def test_mismatched_rater_id_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=3)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        rec = {"schema_version": 1, "run_id": "test-run", "rater_id": "wrong-rater",
               "blinded_id": "HR-0000", "rating": 3, "note": None, "flagged": False, "rated_at": "t"}
        ratings_path.write_text(json.dumps(rec) + "\n")
        queue_ids = {"HR-0000", "HR-0001", "HR-0002"}
        try:
            _load_existing_ratings(ratings_path, queue_ids, "test-run", "rater-01")
            assert False
        except ValueError as e:
            assert "Rater ID" in str(e)
    print("  PASS: test_mismatched_rater_id_rejected")


def test_ansi_sequences_removed():
    text = "\x1b[31mRed text\x1b[0m normal"
    clean = _sanitize_display(text)
    assert "\x1b" not in clean
    assert "Red text" in clean
    print("  PASS: test_ansi_sequences_removed")


def test_rubric_help_uses_rubric_py():
    from benchmarks.human_rating.rubric import RATING_RUBRIC
    # Verify rate.py imports from rubric
    rate_path = os.path.join(_project_root, "benchmarks", "human_rating", "rate.py")
    with open(rate_path) as f:
        source = f.read()
    assert "from benchmarks.human_rating.rubric import" in source
    print("  PASS: test_rubric_help_uses_rubric_py")


def test_all_30_ratings_complete():
    """Integration test: rate a full 30-item queue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=30)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, lines = _capture_output()
        # Rate all 30 with score 3
        inputs = ["3"] * 30
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(inputs), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert len(records) == 30
        assert any("complete" in l.lower() for l in lines)
    print("  PASS: test_all_30_ratings_complete")


def test_cli_help_no_forbidden_options():
    result = subprocess.run(
        [sys.executable, "-m", "benchmarks.human_rating.rate", "--help"],
        capture_output=True, text=True, cwd=_project_root,
    )
    assert result.returncode == 0
    help_lower = result.stdout.lower()
    for forbidden in ("answer-key", "answer_key", "private", "manifest", "results-dir"):
        assert forbidden not in help_lower, f"--help contains '{forbidden}'"
    print("  PASS: test_cli_help_no_forbidden_options")


def test_source_no_private_access():
    rate_path = os.path.join(_project_root, "benchmarks", "human_rating", "rate.py")
    with open(rate_path) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "answer_key" not in module.lower()
            assert "artifact_writer" not in module.lower()
            assert "compile_ratings" not in module.lower()
    # No references to private paths
    assert "answer_key" not in source.lower().replace("answer-key", "")
    print("  PASS: test_source_no_private_access")


def test_note_length_enforced():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue(n=2)
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, lines = _capture_output()
        long_note = "x" * 2001
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["n", long_note, "3", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        # Long note rejected, rating still saved without note
        assert records[0]["note"] is None
        assert any("too long" in l.lower() for l in lines)
    print("  PASS: test_note_length_enforced")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def main():
    print("=== Rating CLI Tests ===\n")
    test_valid_queue_loads()
    test_malformed_queue_rejected()
    test_private_field_rejected()
    test_session_created_on_first_run()
    test_queue_fingerprint_deterministic()
    test_changed_queue_rejected_on_resume()
    test_one_rating_appends_one_line()
    test_invalid_rating_does_not_advance()
    test_rating_1_and_5_accepted()
    test_note_saved()
    test_note_cleared()
    test_flag_toggled()
    test_quit_preserves_progress()
    test_eof_preserves_progress()
    test_resume_starts_at_first_unrated()
    test_completed_session_exits()
    test_duplicate_blinded_id_in_ratings_rejected()
    test_mismatched_rater_id_rejected()
    test_ansi_sequences_removed()
    test_rubric_help_uses_rubric_py()
    test_all_30_ratings_complete()
    test_cli_help_no_forbidden_options()
    test_source_no_private_access()
    test_note_length_enforced()
    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
