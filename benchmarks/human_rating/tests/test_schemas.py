"""Schema validation tests for the human-rating evaluation workflow.

Tests cover:
- SourceTrial validation (invalid methods, models, empty fields, score range)
- RatingQueueItem schema constraints (no leaked fields)
- AnswerKeyItem referential integrity
- RatingRecord validation (invalid ratings, duplicate IDs)
- Rating queue JSON structure validation
- Answer key JSON structure validation
- Ratings session validation (immutability, forbidden fields)
- CompiledRecord field computation

Run:
    python benchmarks/human_rating/tests/test_schemas.py
"""

import os
import sys

# Ensure the project root is on sys.path when running as a script
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.schemas import (
    AnswerKeyItem,
    CompiledRecord,
    RatingQueueItem,
    RatingRecord,
    SourceTrial,
    VALID_RATINGS,
    VALID_SOURCE_METHODS,
    VALID_QUESTION_TYPES,
)
from benchmarks.human_rating.validation import (
    validate_answer_key,
    validate_rating_queue,
    validate_rating_record,
    validate_ratings_session,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_source_trial(**overrides) -> SourceTrial:
    """Create a valid SourceTrial with defaults, applying overrides."""
    defaults = dict(
        source_method="kernel_shared",
        model="gpt-4o",
        question_type="profile",
        original_trial_id="trial-001",
        profile_context="User prefers Python and VS Code",
        question="What should I prioritize?",
        response="Based on your profile, I recommend focusing on...",
        judge_score=4,
        source_file=None,
    )
    defaults.update(overrides)
    return SourceTrial(**defaults)


def _valid_queue_json(items=None, **overrides) -> dict:
    """Create a valid rating queue JSON structure."""
    if items is None:
        items = [
            {
                "blinded_id": f"R{i:02d}",
                "profile_context": "Some context" if i % 2 == 0 else None,
                "question": f"Question {i}",
                "response": f"Response {i}",
            }
            for i in range(1, 31)
        ]
    defaults = dict(
        schema_version=1,
        benchmark_name="test_benchmark",
        created_at="2026-07-14T10:00:00Z",
        total_items=len(items),
        items=items,
    )
    defaults.update(overrides)
    return defaults


def _valid_answer_key_json(items=None, **overrides) -> dict:
    """Create a valid answer key JSON structure with 30 items (6 duplicates)."""
    if items is None:
        items = []
        # 24 unique items
        for i in range(1, 25):
            items.append({
                "blinded_id": f"R{i:02d}",
                "source_method": list(VALID_SOURCE_METHODS)[i % len(VALID_SOURCE_METHODS)],
                "model": "gpt-4o",
                "question_type": "profile" if i % 2 == 0 else "task",
                "original_trial_id": f"trial-{i:03d}",
                "judge_score": (i % 5) + 1,
                "duplicate_of": None,
            })
        # 6 duplicates of the first 6
        for i in range(6):
            original = items[i]
            items.append({
                "blinded_id": f"R{25 + i:02d}",
                "source_method": original["source_method"],
                "model": original["model"],
                "question_type": original["question_type"],
                "original_trial_id": original["original_trial_id"],
                "judge_score": original["judge_score"],
                "duplicate_of": original["blinded_id"],
            })

    defaults = dict(
        schema_version=1,
        benchmark_name="test_benchmark",
        sampling_seed=12345,
        duplicate_seed=23456,
        id_assignment_seed=34567,
        presentation_seed=45678,
        created_at="2026-07-14T10:00:00Z",
        items=items,
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# SourceTrial tests
# ---------------------------------------------------------------------------

def test_source_trial_valid():
    """Valid SourceTrial should construct without error."""
    trial = _valid_source_trial()
    assert trial.source_method == "kernel_shared"
    assert trial.model == "gpt-4o"
    assert trial.question_type == "profile"
    print("  PASS: test_source_trial_valid")


def test_source_trial_invalid_method():
    """Invalid source_method should raise ValueError."""
    try:
        _valid_source_trial(source_method="invalid_method")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "source_method" in str(e)
    print("  PASS: test_source_trial_invalid_method")


def test_source_trial_invalid_model():
    """Model not 'gpt-4o' should raise ValueError."""
    try:
        _valid_source_trial(model="gpt-3.5-turbo")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "model" in str(e)
    print("  PASS: test_source_trial_invalid_model")


def test_source_trial_invalid_question_type():
    """Invalid question_type should raise ValueError."""
    try:
        _valid_source_trial(question_type="integration")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "question_type" in str(e)
    print("  PASS: test_source_trial_invalid_question_type")


def test_source_trial_empty_trial_id():
    """Empty original_trial_id should raise ValueError."""
    try:
        _valid_source_trial(original_trial_id="")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "original_trial_id" in str(e)
    print("  PASS: test_source_trial_empty_trial_id")


def test_source_trial_whitespace_trial_id():
    """Whitespace-only original_trial_id should raise ValueError."""
    try:
        _valid_source_trial(original_trial_id="   ")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "original_trial_id" in str(e)
    print("  PASS: test_source_trial_whitespace_trial_id")


def test_source_trial_empty_question():
    """Empty question should raise ValueError."""
    try:
        _valid_source_trial(question="")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "question" in str(e)
    print("  PASS: test_source_trial_empty_question")


def test_source_trial_empty_response():
    """Empty response should raise ValueError."""
    try:
        _valid_source_trial(response="")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "response" in str(e)
    print("  PASS: test_source_trial_empty_response")


def test_source_trial_score_out_of_range_low():
    """judge_score below 1 should raise ValueError."""
    try:
        _valid_source_trial(judge_score=0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "judge_score" in str(e)
    print("  PASS: test_source_trial_score_out_of_range_low")


def test_source_trial_score_out_of_range_high():
    """judge_score above 5 should raise ValueError."""
    try:
        _valid_source_trial(judge_score=6)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "judge_score" in str(e)
    print("  PASS: test_source_trial_score_out_of_range_high")


def test_source_trial_float_score():
    """Non-integer judge_score should raise ValueError."""
    try:
        _valid_source_trial(judge_score=3.5)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "judge_score" in str(e)
    print("  PASS: test_source_trial_float_score")


def test_source_trial_all_valid_methods():
    """All four valid source methods should construct successfully."""
    for method in VALID_SOURCE_METHODS:
        trial = _valid_source_trial(source_method=method)
        assert trial.source_method == method
    print("  PASS: test_source_trial_all_valid_methods")


def test_source_trial_null_profile_context():
    """profile_context=None should be valid."""
    trial = _valid_source_trial(profile_context=None)
    assert trial.profile_context is None
    print("  PASS: test_source_trial_null_profile_context")


# ---------------------------------------------------------------------------
# RatingQueueItem tests
# ---------------------------------------------------------------------------

def test_rating_queue_item_no_forbidden_fields():
    """RatingQueueItem should only have blinded_id, profile_context, question, response."""
    item = RatingQueueItem(
        blinded_id="R01",
        profile_context="Some context",
        question="What should I do?",
        response="Here is my recommendation.",
    )
    fields = {f.name for f in item.__dataclass_fields__.values()}
    assert fields == {"blinded_id", "profile_context", "question", "response"}
    print("  PASS: test_rating_queue_item_no_forbidden_fields")


def test_rating_queue_item_cannot_hold_method():
    """RatingQueueItem has no slot for source_method."""
    try:
        RatingQueueItem(
            blinded_id="R01",
            profile_context=None,
            question="Q",
            response="R",
            source_method="kernel_shared",  # type: ignore
        )
        assert False, "Should have raised TypeError"
    except TypeError:
        pass
    print("  PASS: test_rating_queue_item_cannot_hold_method")


# ---------------------------------------------------------------------------
# RatingRecord tests
# ---------------------------------------------------------------------------

def test_rating_record_valid():
    """Valid RatingRecord should construct without error."""
    record = RatingRecord(
        blinded_id="R07",
        rating=4,
        note="Good personalization",
        flagged=False,
        rated_at="2026-07-14T10:00:00Z",
    )
    assert record.rating == 4
    print("  PASS: test_rating_record_valid")


def test_rating_record_invalid_rating_zero():
    """rating=0 should raise ValueError."""
    try:
        RatingRecord(blinded_id="R01", rating=0, note=None, flagged=False, rated_at="2026-07-14T10:00:00Z")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "rating" in str(e)
    print("  PASS: test_rating_record_invalid_rating_zero")


def test_rating_record_invalid_rating_six():
    """rating=6 should raise ValueError."""
    try:
        RatingRecord(blinded_id="R01", rating=6, note=None, flagged=False, rated_at="2026-07-14T10:00:00Z")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "rating" in str(e)
    print("  PASS: test_rating_record_invalid_rating_six")


def test_rating_record_empty_blinded_id():
    """Empty blinded_id should raise ValueError."""
    try:
        RatingRecord(blinded_id="", rating=3, note=None, flagged=False, rated_at="2026-07-14T10:00:00Z")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "blinded_id" in str(e)
    print("  PASS: test_rating_record_empty_blinded_id")


def test_rating_record_empty_rated_at():
    """Empty rated_at should raise ValueError."""
    try:
        RatingRecord(blinded_id="R01", rating=3, note=None, flagged=False, rated_at="")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "rated_at" in str(e)
    print("  PASS: test_rating_record_empty_rated_at")


def test_rating_record_null_note_valid():
    """note=None should be valid."""
    record = RatingRecord(blinded_id="R01", rating=5, note=None, flagged=True, rated_at="2026-07-14T10:00:00Z")
    assert record.note is None
    print("  PASS: test_rating_record_null_note_valid")


# ---------------------------------------------------------------------------
# Rating queue JSON validation tests
# ---------------------------------------------------------------------------

def test_validate_queue_valid():
    """Valid queue JSON should produce no errors."""
    data = _valid_queue_json()
    errors = validate_rating_queue(data)
    assert errors == [], f"Unexpected errors: {errors}"
    print("  PASS: test_validate_queue_valid")


def test_validate_queue_missing_top_keys():
    """Missing top-level keys should report errors."""
    data = {"items": []}
    errors = validate_rating_queue(data)
    assert any("Missing top-level" in e for e in errors)
    print("  PASS: test_validate_queue_missing_top_keys")


def test_validate_queue_count_mismatch():
    """total_items != actual count should report error."""
    data = _valid_queue_json()
    data["total_items"] = 99
    errors = validate_rating_queue(data)
    assert any("total_items" in e for e in errors)
    print("  PASS: test_validate_queue_count_mismatch")


def test_validate_queue_leaked_method():
    """Item with source_method should report forbidden key."""
    items = [
        {
            "blinded_id": "R01",
            "profile_context": None,
            "question": "Q",
            "response": "R",
            "source_method": "kernel_shared",
        }
    ]
    data = _valid_queue_json(items=items)
    errors = validate_rating_queue(data)
    assert any("forbidden" in e for e in errors)
    print("  PASS: test_validate_queue_leaked_method")


def test_validate_queue_leaked_judge_score():
    """Item with judge_score should report forbidden key."""
    items = [
        {
            "blinded_id": "R01",
            "profile_context": None,
            "question": "Q",
            "response": "R",
            "judge_score": 4,
        }
    ]
    data = _valid_queue_json(items=items)
    errors = validate_rating_queue(data)
    assert any("forbidden" in e for e in errors)
    print("  PASS: test_validate_queue_leaked_judge_score")


def test_validate_queue_duplicate_blinded_id():
    """Duplicate blinded_id should report error."""
    items = [
        {"blinded_id": "R01", "profile_context": None, "question": "Q1", "response": "R1"},
        {"blinded_id": "R01", "profile_context": None, "question": "Q2", "response": "R2"},
    ]
    data = _valid_queue_json(items=items)
    errors = validate_rating_queue(data)
    assert any("duplicate blinded_id" in e for e in errors)
    print("  PASS: test_validate_queue_duplicate_blinded_id")


def test_validate_queue_empty_question():
    """Item with empty question should report error."""
    items = [
        {"blinded_id": "R01", "profile_context": None, "question": "", "response": "R1"},
    ]
    data = _valid_queue_json(items=items)
    errors = validate_rating_queue(data)
    assert any("empty question" in e for e in errors)
    print("  PASS: test_validate_queue_empty_question")


def test_validate_queue_empty_response():
    """Item with empty response should report error."""
    items = [
        {"blinded_id": "R01", "profile_context": None, "question": "Q", "response": "  "},
    ]
    data = _valid_queue_json(items=items)
    errors = validate_rating_queue(data)
    assert any("empty response" in e for e in errors)
    print("  PASS: test_validate_queue_empty_response")


# ---------------------------------------------------------------------------
# Answer key JSON validation tests
# ---------------------------------------------------------------------------

def test_validate_answer_key_valid():
    """Valid answer key should produce no errors."""
    data = _valid_answer_key_json()
    errors = validate_answer_key(data)
    assert errors == [], f"Unexpected errors: {errors}"
    print("  PASS: test_validate_answer_key_valid")


def test_validate_answer_key_wrong_count():
    """Wrong item count should report error."""
    data = _valid_answer_key_json()
    data["items"] = data["items"][:10]
    errors = validate_answer_key(data, expected_count=30)
    assert any("Expected 30" in e for e in errors)
    print("  PASS: test_validate_answer_key_wrong_count")


def test_validate_answer_key_broken_duplicate_ref():
    """Duplicate pointing to nonexistent target should report error."""
    data = _valid_answer_key_json()
    # Point last duplicate to a nonexistent ID
    data["items"][-1]["duplicate_of"] = "R99"
    errors = validate_answer_key(data)
    assert any("does not exist" in e for e in errors)
    print("  PASS: test_validate_answer_key_broken_duplicate_ref")


def test_validate_answer_key_self_reference():
    """Duplicate pointing to itself should report error."""
    data = _valid_answer_key_json()
    data["items"][-1]["duplicate_of"] = data["items"][-1]["blinded_id"]
    errors = validate_answer_key(data)
    assert any("points to itself" in e for e in errors)
    print("  PASS: test_validate_answer_key_self_reference")


def test_validate_answer_key_duplicate_mismatch():
    """Duplicate with mismatched source_method should report error."""
    data = _valid_answer_key_json()
    # Change the duplicate's source_method to differ from original
    dup = data["items"][-1]
    original_id = dup["duplicate_of"]
    original = next(it for it in data["items"] if it["blinded_id"] == original_id)
    # Force mismatch
    different_method = next(m for m in VALID_SOURCE_METHODS if m != original["source_method"])
    dup["source_method"] = different_method
    errors = validate_answer_key(data)
    assert any("source_method" in e and "mismatch" in e for e in errors)
    print("  PASS: test_validate_answer_key_duplicate_mismatch")


def test_validate_answer_key_wrong_duplicate_count():
    """Wrong number of duplicates should report error."""
    data = _valid_answer_key_json()
    # Remove all duplicates
    for item in data["items"]:
        item["duplicate_of"] = None
    errors = validate_answer_key(data)
    assert any("duplicate items" in e for e in errors)
    print("  PASS: test_validate_answer_key_wrong_duplicate_count")


def test_validate_answer_key_invalid_source_method():
    """Invalid source_method should report error."""
    data = _valid_answer_key_json()
    data["items"][0]["source_method"] = "bogus_method"
    errors = validate_answer_key(data)
    assert any("invalid source_method" in e for e in errors)
    print("  PASS: test_validate_answer_key_invalid_source_method")


# ---------------------------------------------------------------------------
# Ratings session validation tests
# ---------------------------------------------------------------------------

def test_validate_rating_record_valid():
    """Valid rating record should produce no errors."""
    record = {
        "blinded_id": "R07",
        "rating": 4,
        "note": "Good response",
        "flagged": False,
        "rated_at": "2026-07-14T10:00:00Z",
    }
    errors = validate_rating_record(record)
    assert errors == [], f"Unexpected errors: {errors}"
    print("  PASS: test_validate_rating_record_valid")


def test_validate_rating_record_invalid_rating():
    """Invalid rating should report error."""
    record = {
        "blinded_id": "R07",
        "rating": 7,
        "note": None,
        "flagged": False,
        "rated_at": "2026-07-14T10:00:00Z",
    }
    errors = validate_rating_record(record)
    assert any("Invalid rating" in e for e in errors)
    print("  PASS: test_validate_rating_record_invalid_rating")


def test_validate_rating_record_forbidden_key():
    """Rating record with source_method should report error."""
    record = {
        "blinded_id": "R07",
        "rating": 3,
        "note": None,
        "flagged": False,
        "rated_at": "2026-07-14T10:00:00Z",
        "source_method": "kernel_shared",
    }
    errors = validate_rating_record(record)
    assert any("forbidden" in e for e in errors)
    print("  PASS: test_validate_rating_record_forbidden_key")


def test_validate_ratings_session_duplicate_ids():
    """Session with duplicate blinded_id should report immutability error."""
    records = [
        {"blinded_id": "R01", "rating": 3, "note": None, "flagged": False, "rated_at": "2026-07-14T10:00:00Z"},
        {"blinded_id": "R01", "rating": 4, "note": None, "flagged": False, "rated_at": "2026-07-14T10:01:00Z"},
    ]
    errors = validate_ratings_session(records)
    assert any("duplicate blinded_id" in e and "immutable" in e for e in errors)
    print("  PASS: test_validate_ratings_session_duplicate_ids")


def test_validate_ratings_session_valid():
    """Valid session should produce no errors."""
    records = [
        {"blinded_id": f"R{i:02d}", "rating": (i % 5) + 1, "note": None, "flagged": False, "rated_at": "2026-07-14T10:00:00Z"}
        for i in range(1, 11)
    ]
    errors = validate_ratings_session(records)
    assert errors == [], f"Unexpected errors: {errors}"
    print("  PASS: test_validate_ratings_session_valid")


# ---------------------------------------------------------------------------
# CompiledRecord tests
# ---------------------------------------------------------------------------

def test_compiled_record_fields():
    """CompiledRecord should compute agreement metrics correctly."""
    record = CompiledRecord(
        blinded_id="R01",
        rating=4,
        note=None,
        flagged=False,
        rated_at="2026-07-14T10:00:00Z",
        source_method="kernel_shared",
        model="gpt-4o",
        question_type="profile",
        original_trial_id="trial-001",
        judge_score=4,
        duplicate_of=None,
        is_duplicate=False,
        human_judge_difference=0,
        exact_human_judge_match=True,
        within_one_human_judge=True,
    )
    assert record.exact_human_judge_match is True
    assert record.human_judge_difference == 0
    print("  PASS: test_compiled_record_fields")


def test_compiled_record_disagreement():
    """CompiledRecord with rating != judge_score should show difference."""
    record = CompiledRecord(
        blinded_id="R02",
        rating=2,
        note="Seemed generic",
        flagged=True,
        rated_at="2026-07-14T10:05:00Z",
        source_method="naive_concat",
        model="gpt-4o",
        question_type="task",
        original_trial_id="trial-005",
        judge_score=5,
        duplicate_of=None,
        is_duplicate=False,
        human_judge_difference=-3,
        exact_human_judge_match=False,
        within_one_human_judge=False,
    )
    assert record.human_judge_difference == -3
    assert record.exact_human_judge_match is False
    assert record.within_one_human_judge is False
    print("  PASS: test_compiled_record_disagreement")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

def main():
    print("=== Human Rating Schema Validation Tests ===\n")

    print("SourceTrial tests:")
    test_source_trial_valid()
    test_source_trial_invalid_method()
    test_source_trial_invalid_model()
    test_source_trial_invalid_question_type()
    test_source_trial_empty_trial_id()
    test_source_trial_whitespace_trial_id()
    test_source_trial_empty_question()
    test_source_trial_empty_response()
    test_source_trial_score_out_of_range_low()
    test_source_trial_score_out_of_range_high()
    test_source_trial_float_score()
    test_source_trial_all_valid_methods()
    test_source_trial_null_profile_context()

    print("\nRatingQueueItem tests:")
    test_rating_queue_item_no_forbidden_fields()
    test_rating_queue_item_cannot_hold_method()

    print("\nRatingRecord tests:")
    test_rating_record_valid()
    test_rating_record_invalid_rating_zero()
    test_rating_record_invalid_rating_six()
    test_rating_record_empty_blinded_id()
    test_rating_record_empty_rated_at()
    test_rating_record_null_note_valid()

    print("\nRating queue JSON validation tests:")
    test_validate_queue_valid()
    test_validate_queue_missing_top_keys()
    test_validate_queue_count_mismatch()
    test_validate_queue_leaked_method()
    test_validate_queue_leaked_judge_score()
    test_validate_queue_duplicate_blinded_id()
    test_validate_queue_empty_question()
    test_validate_queue_empty_response()

    print("\nAnswer key JSON validation tests:")
    test_validate_answer_key_valid()
    test_validate_answer_key_wrong_count()
    test_validate_answer_key_broken_duplicate_ref()
    test_validate_answer_key_self_reference()
    test_validate_answer_key_duplicate_mismatch()
    test_validate_answer_key_wrong_duplicate_count()
    test_validate_answer_key_invalid_source_method()

    print("\nRatings session validation tests:")
    test_validate_rating_record_valid()
    test_validate_rating_record_invalid_rating()
    test_validate_rating_record_forbidden_key()
    test_validate_ratings_session_duplicate_ids()
    test_validate_ratings_session_valid()

    print("\nCompiledRecord tests:")
    test_compiled_record_fields()
    test_compiled_record_disagreement()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
