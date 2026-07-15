"""Tests for the interactive rating CLI — session integrity and protocol enforcement.

All tests use 30-item queues matching the production requirement.
Output is captured (not printed to terminal).

Run:
    python benchmarks/human_rating/tests/test_rate.py
"""

import ast
import json
import os
import stat
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
    _run_rating_session, _sanitize_display,
)


# ---------------------------------------------------------------------------
# Fixtures (always 30 items)
# ---------------------------------------------------------------------------

def _make_queue(run_id="test-run"):
    items = [
        {"blinded_id": f"HR-{i:04d}", "reference_context": f"Ctx {i}",
         "question": f"Q{i}", "response": f"R{i}"}
        for i in range(30)
    ]
    return {"schema_version": 1, "run_id": run_id, "item_count": 30, "items": items}


def _mock_input(responses):
    it = iter(responses)
    def _input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            return None
    return _input


def _capture():
    lines = []
    def _print(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))
    return _print, lines


def _write_queue_file(tmpdir, queue_data):
    p = Path(tmpdir) / "rater" / "rating_queue.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(queue_data))
    return p


# ---------------------------------------------------------------------------
# 1. Require exactly 30 queue items
# ---------------------------------------------------------------------------

def test_queue_with_29_items_rejected():
    """CLI rejects queues with fewer than 30 items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q = _make_queue()
        q["items"] = q["items"][:29]
        q["item_count"] = 29
        qp = _write_queue_file(tmpdir, q)
        result = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.rate", "--queue", str(qp)],
            capture_output=True, text=True, cwd=_project_root,
        )
        assert result.returncode != 0
        assert "30" in result.stderr
    print("  PASS: test_queue_with_29_items_rejected")


def test_queue_with_31_items_rejected():
    """CLI rejects queues with more than 30 items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q = _make_queue()
        q["items"].append({"blinded_id": "HR-EXTRA", "reference_context": "c", "question": "q", "response": "r"})
        q["item_count"] = 31
        qp = _write_queue_file(tmpdir, q)
        result = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.rate", "--queue", str(qp)],
            capture_output=True, text=True, cwd=_project_root,
        )
        assert result.returncode != 0
        assert "30" in result.stderr
    print("  PASS: test_queue_with_31_items_rejected")


def test_item_count_mismatch_rejected():
    """CLI rejects queue where item_count != len(items)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q = _make_queue()
        q["item_count"] = 25  # Mismatch
        qp = _write_queue_file(tmpdir, q)
        result = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.rate", "--queue", str(qp)],
            capture_output=True, text=True, cwd=_project_root,
        )
        assert result.returncode != 0
    print("  PASS: test_item_count_mismatch_rejected")


# ---------------------------------------------------------------------------
# 2. Unknown blinded ID in ratings rejected
# ---------------------------------------------------------------------------

def test_unknown_blinded_id_in_ratings_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        rec = {"schema_version": 1, "run_id": "test-run", "rater_id": "rater-01",
               "blinded_id": "HR-UNKNOWN", "rating": 3, "note": None, "flagged": False, "rated_at": "t"}
        ratings_path.write_text(json.dumps(rec) + "\n")
        queue_ids = {it["blinded_id"] for it in queue["items"]}
        try:
            _load_existing_ratings(ratings_path, queue_ids, "test-run", "rater-01")
            assert False
        except ValueError as e:
            assert "Unknown" in str(e) or "unknown" in str(e)
            assert "HR-UNKNOWN" in str(e)
    print("  PASS: test_unknown_blinded_id_in_ratings_rejected")


# ---------------------------------------------------------------------------
# 3. Mismatched run ID in ratings
# ---------------------------------------------------------------------------

def test_mismatched_run_id_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        rec = {"schema_version": 1, "run_id": "wrong-run", "rater_id": "rater-01",
               "blinded_id": "HR-0000", "rating": 3, "note": None, "flagged": False, "rated_at": "t"}
        ratings_path.write_text(json.dumps(rec) + "\n")
        queue_ids = {it["blinded_id"] for it in queue["items"]}
        try:
            _load_existing_ratings(ratings_path, queue_ids, "test-run", "rater-01")
            assert False
        except ValueError as e:
            assert "Run ID" in str(e)
    print("  PASS: test_mismatched_run_id_rejected")


# ---------------------------------------------------------------------------
# 4. Malformed JSONL
# ---------------------------------------------------------------------------

def test_malformed_jsonl_line_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        ratings_path.write_text('{"blinded_id":"HR-0000","rating":4\n')  # invalid JSON
        queue_ids = {it["blinded_id"] for it in queue["items"]}
        try:
            _load_existing_ratings(ratings_path, queue_ids, "test-run", "rater-01")
            assert False
        except ValueError as e:
            assert "line 1" in str(e).lower() or "Malformed" in str(e)
    print("  PASS: test_malformed_jsonl_line_rejected")


def test_malformed_trailing_jsonl_line_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        valid = json.dumps({"schema_version": 1, "run_id": "test-run", "rater_id": "rater-01",
                           "blinded_id": "HR-0000", "rating": 3, "note": None, "flagged": False, "rated_at": "t"})
        ratings_path.write_text(valid + "\n" + "truncated{garbage\n")
        queue_ids = {it["blinded_id"] for it in queue["items"]}
        try:
            _load_existing_ratings(ratings_path, queue_ids, "test-run", "rater-01")
            assert False
        except ValueError as e:
            assert "2" in str(e)  # line 2
    print("  PASS: test_malformed_trailing_jsonl_line_rejected")


def test_non_object_jsonl_record_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        ratings_path.write_text('["not", "an", "object"]\n')
        queue_ids = {it["blinded_id"] for it in queue["items"]}
        try:
            _load_existing_ratings(ratings_path, queue_ids, "test-run", "rater-01")
            assert False
        except ValueError as e:
            assert "line 1" in str(e).lower() or "object" in str(e).lower()
    print("  PASS: test_non_object_jsonl_record_rejected")


# ---------------------------------------------------------------------------
# 5. KeyboardInterrupt preserves progress
# ---------------------------------------------------------------------------

def test_keyboard_interrupt_preserves_progress():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture()

        call_count = [0]
        def interrupt_input(prompt=""):
            call_count[0] += 1
            if call_count[0] == 1:
                return "4"  # First rating
            raise KeyboardInterrupt()

        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=interrupt_input, output_fn=out_fn,
        )
        # First rating saved
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n") if l.strip()]
        assert len(records) == 1
        assert records[0]["rating"] == 4
        assert records[0]["blinded_id"] == "HR-0000"
    print("  PASS: test_keyboard_interrupt_preserves_progress")


# ---------------------------------------------------------------------------
# 6. Append-only behavior
# ---------------------------------------------------------------------------

def test_existing_jsonl_bytes_unchanged_after_append():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture()

        # Rate 2 items
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["3", "4", "q"]), output_fn=out_fn,
        )
        original_bytes = ratings_path.read_bytes()

        # Rate 1 more item (resume)
        out_fn2, _ = _capture()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["5", "q"]), output_fn=out_fn2,
        )
        new_bytes = ratings_path.read_bytes()

        # Original bytes are prefix of new bytes
        assert new_bytes.startswith(original_bytes)
        # Exactly one new line appended
        new_part = new_bytes[len(original_bytes):]
        new_lines = [l for l in new_part.decode().split("\n") if l.strip()]
        assert len(new_lines) == 1
    print("  PASS: test_existing_jsonl_bytes_unchanged_after_append")


# ---------------------------------------------------------------------------
# 7. Flush and fsync
# ---------------------------------------------------------------------------

def test_rating_append_calls_fsync():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture()

        fsync_calls = []
        original_fsync = os.fsync

        def tracking_fsync(fd):
            fsync_calls.append(fd)
            return original_fsync(fd)

        with patch("benchmarks.human_rating.rate.os.fsync", side_effect=tracking_fsync):
            _run_rating_session(
                queue, ratings_path, session_path, "test-run", "rater-01",
                input_fn=_mock_input(["4", "0", "5", "q"]),  # 4=valid, 0=invalid, 5=valid
                output_fn=out_fn,
            )

        # fsync called twice (once per valid rating), not for invalid
        assert len(fsync_calls) == 2
    print("  PASS: test_rating_append_calls_fsync")


# ---------------------------------------------------------------------------
# 8. Lock behavior
# ---------------------------------------------------------------------------

def test_lock_prevents_concurrent_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        qp = _write_queue_file(tmpdir, queue)
        lock_path = str(Path(tmpdir) / "rater" / "ratings.jsonl.lock")

        # Acquire lock manually
        import fcntl
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Try to start CLI — should fail
        result = subprocess.run(
            [sys.executable, "-m", "benchmarks.human_rating.rate",
             "--queue", str(qp), "--ratings", str(Path(tmpdir) / "rater" / "ratings.jsonl")],
            capture_output=True, text=True, cwd=_project_root, timeout=10,
        )
        assert result.returncode != 0
        assert "Another rating session" in result.stderr

        # Release
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()
    print("  PASS: test_lock_prevents_concurrent_session")


# ---------------------------------------------------------------------------
# 9. Permissions (POSIX)
# ---------------------------------------------------------------------------

def test_session_file_permissions_posix():
    if os.name != "posix":
        print("  SKIP: test_session_file_permissions_posix")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        fp = _queue_fingerprint(queue)
        _load_or_create_session(session_path, "test-run", "rater-01", fp, 30)
        mode = stat.S_IMODE(os.stat(session_path).st_mode)
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"
    print("  PASS: test_session_file_permissions_posix")


# ---------------------------------------------------------------------------
# 10. Session metadata consistency
# ---------------------------------------------------------------------------

def test_session_rater_id_mismatch_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        session_path = Path(tmpdir) / "session.json"
        fp = _queue_fingerprint(queue)
        _load_or_create_session(session_path, "test-run", "rater-01", fp, 30)
        try:
            _load_or_create_session(session_path, "test-run", "rater-02", fp, 30)
            assert False
        except ValueError as e:
            assert "Rater ID" in str(e)
    print("  PASS: test_session_rater_id_mismatch_rejected")


def test_session_run_id_mismatch_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        session_path = Path(tmpdir) / "session.json"
        fp = _queue_fingerprint(queue)
        _load_or_create_session(session_path, "test-run", "rater-01", fp, 30)
        try:
            _load_or_create_session(session_path, "other-run", "rater-01", fp, 30)
            assert False
        except ValueError as e:
            assert "Run ID" in str(e)
    print("  PASS: test_session_run_id_mismatch_rejected")


# ---------------------------------------------------------------------------
# 11. Completed sessions immutable
# ---------------------------------------------------------------------------

def test_completed_session_immutable():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture()

        # Rate all 30
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["3"] * 30), output_fn=out_fn,
        )
        size_after = ratings_path.stat().st_size
        bytes_after = ratings_path.read_bytes()

        # Try to resume
        out_fn2, lines2 = _capture()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input([]), output_fn=out_fn2,
        )

        # File unchanged
        assert ratings_path.stat().st_size == size_after
        assert ratings_path.read_bytes() == bytes_after
        assert any("complete" in l.lower() for l in lines2)
    print("  PASS: test_completed_session_immutable")


# ---------------------------------------------------------------------------
# Core behavior (30-item queue)
# ---------------------------------------------------------------------------

def test_first_rating_saved():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["4", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert len(records) == 1
        assert records[0]["rating"] == 4
        assert records[0]["blinded_id"] == "HR-0000"
    print("  PASS: test_first_rating_saved")


def test_resume_continues_from_next():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["3", "4", "q"]), output_fn=out_fn,
        )
        out_fn2, _ = _capture()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["5", "q"]), output_fn=out_fn2,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert len(records) == 3
        assert records[2]["blinded_id"] == "HR-0002"
    print("  PASS: test_resume_continues_from_next")


def test_note_and_flag():
    with tempfile.TemporaryDirectory() as tmpdir:
        queue = _make_queue()
        ratings_path = Path(tmpdir) / "ratings.jsonl"
        session_path = Path(tmpdir) / "session.json"
        out_fn, _ = _capture()
        _run_rating_session(
            queue, ratings_path, session_path, "test-run", "rater-01",
            input_fn=_mock_input(["n", "My note", "f", "4", "q"]), output_fn=out_fn,
        )
        records = [json.loads(l) for l in ratings_path.read_text().strip().split("\n")]
        assert records[0]["note"] == "My note"
        assert records[0]["flagged"] is True
    print("  PASS: test_note_and_flag")


def test_ansi_stripped():
    assert "\x1b" not in _sanitize_display("\x1b[31mred\x1b[0m")
    print("  PASS: test_ansi_stripped")


def test_cli_no_forbidden_options():
    result = subprocess.run(
        [sys.executable, "-m", "benchmarks.human_rating.rate", "--help"],
        capture_output=True, text=True, cwd=_project_root,
    )
    for forbidden in ("answer-key", "answer_key", "private", "manifest"):
        assert forbidden not in result.stdout.lower()
    print("  PASS: test_cli_no_forbidden_options")


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
    print("  PASS: test_source_no_private_access")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def main():
    print("=== Rating CLI Tests ===\n")

    print("30-item enforcement:")
    test_queue_with_29_items_rejected()
    test_queue_with_31_items_rejected()
    test_item_count_mismatch_rejected()

    print("\nUnknown/invalid IDs:")
    test_unknown_blinded_id_in_ratings_rejected()
    test_mismatched_run_id_rejected()

    print("\nMalformed JSONL:")
    test_malformed_jsonl_line_rejected()
    test_malformed_trailing_jsonl_line_rejected()
    test_non_object_jsonl_record_rejected()

    print("\nInterrupt handling:")
    test_keyboard_interrupt_preserves_progress()

    print("\nAppend-only:")
    test_existing_jsonl_bytes_unchanged_after_append()

    print("\nFlush/fsync:")
    test_rating_append_calls_fsync()

    print("\nLocking:")
    test_lock_prevents_concurrent_session()

    print("\nPermissions:")
    test_session_file_permissions_posix()

    print("\nSession metadata:")
    test_session_rater_id_mismatch_rejected()
    test_session_run_id_mismatch_rejected()

    print("\nImmutability:")
    test_completed_session_immutable()

    print("\nCore behavior:")
    test_first_rating_saved()
    test_resume_continues_from_next()
    test_note_and_flag()
    test_ansi_stripped()
    test_cli_no_forbidden_options()
    test_source_no_private_access()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
