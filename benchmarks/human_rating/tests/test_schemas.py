"""Schema validation tests for the human-rating evaluation workflow.

Tests verify semantic behavior of the corrected schemas:
- SourceTrial with question_type, inference_context, single judge_score
- RatingQueueItem cannot leak method/type/score information
- Single 1–5 rating per item (not three)
- Judge score selection rule (profile→profile_usage_score, task→task_usage_score)
- Answer key with question_type and duplicate validation

Run:
    python benchmarks/human_rating/tests/test_schemas.py
"""

import os
import sys

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.human_rating.schemas import (
    AnswerKeyItem,
    CompiledRecord,
    RatingQueueItem,
    RatingRecord,
    SourceTrial,
    select_judge_score,
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
# Judge score selection rule tests
# ---------------------------------------------------------------------------

def test_select_judge_score_profile():
    """Profile questions should use profile_usage_score."""
    assert select_judge_score("profile", 5, 2, 3) == 5
    print("  PASS: test_select_judge_score_profile")


def test_select_judge_score_task():
    """Task questions should use task_usage_score."""
    assert select_judge_score("task", 2, 5, 3) == 5
    print("  PASS: test_select_judge_score_task")


def test_select_judge_score_invalid_type():
    """Invalid question_type should raise ValueError."""
    try:
        select_judge_score("integration", 3, 3, 3)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("  PASS: test_select_judge_score_invalid_type")


# ---------------------------------------------------------------------------
# SourceTrial tests
# ---------------------------------------------------------------------------

def test_source_trial_valid():
    """Valid SourceTrial with question_type and inference_context."""
    trial = SourceTrial(
        source_method="kernel_shared", model="gpt-4o",
        question_type="profile", original_trial_id="42",
        inference_context="Name: Alice\nTools: VS Code",
        question="Based on what you know about my preferences...",
        response="I recommend...", judge_score=4,
    )
    assert trial.question_type == "profile"
    assert trial.inference_context == "Name: Alice\nTools: VS Code"
    print("  PASS: test_source_trial_valid")


def test_source_trial_invalid_question_type():
    """Invalid question_type should raise ValueError."""
    try:
        SourceTrial(
            source_method="kernel_shared", model="gpt-4o",
            question_type="integration", original_trial_id="1",
            inference_context="", question="Q", response="R", judge_score=3,
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "question_type" in str(e)
    print("  PASS: test_source_trial_invalid_question_type")


def test_source_trial_empty_inference_context_valid():
    """Empty inference_context is valid (retrieval failed)."""
    trial = SourceTrial(
        source_method="mem0_default", model="gpt-4o",
        question_type="task", original_trial_id="5",
        inference_context="",
        question="Q", response="R", judge_score=1,
    )
    assert trial.inference_context == ""
    print("  PASS: test_source_trial_empty_inference_context_valid")


def test_source_trial_none_inference_context_valid():
    """None inference_context is valid (field not recorded)."""
    trial = SourceTrial(
        source_method="vanilla_rag", model="gpt-4o",
        question_type="profile", original_trial_id="3",
        inference_context=None,
        question="Q", response="R", judge_score=2,
    )
    assert trial.inference_context is None
    print("  PASS: test_source_trial_none_inference_context_valid")


def test_source_trial_score_out_of_range():
    """judge_score outside 1–5 should raise ValueError."""
    try:
        SourceTrial(
            source_method="naive_concat", model="gpt-4o",
            question_type="profile", original_trial_id="1",
            inference_context="ctx", question="Q", response="R", judge_score=0,
        )
        assert False, "Should raise"
    except ValueError:
        pass
    print("  PASS: test_source_trial_score_out_of_range")


# ---------------------------------------------------------------------------
# RatingQueueItem tests
# ---------------------------------------------------------------------------

def test_queue_item_uses_inference_context():
    """Queue item shows inference_context (not profile_context)."""
    item = RatingQueueItem(
        blinded_id="R01",
        inference_context="Retrieved: Goal: Optimize model",
        question="Based on project history...",
        response="I suggest...",
    )
    assert item.inference_context == "Retrieved: Goal: Optimize model"
    print("  PASS: test_queue_item_uses_inference_context")


def test_queue_item_cannot_hold_question_type():
    """RatingQueueItem has no slot for question_type."""
    try:
        RatingQueueItem(
            blinded_id="R01", inference_context=None,
            question="Q", response="R", question_type="profile",  # type: ignore
        )
        assert False, "Should raise TypeError"
    except TypeError:
        pass
    print("  PASS: test_queue_item_cannot_hold_question_type")


# ---------------------------------------------------------------------------
# RatingRecord tests (single score per item)
# ---------------------------------------------------------------------------

def test_rating_record_single_score():
    """RatingRecord uses a single 'rating' field, not three."""
    record = RatingRecord(
        blinded_id="R07", rating=4, note="Good",
        flagged=False, rated_at="2026-07-14T10:00:00Z",
    )
    assert record.rating == 4
    # Should NOT have profile_usage_rating etc.
    assert not hasattr(record, "profile_usage_rating")
    print("  PASS: test_rating_record_single_score")


def test_rating_record_invalid():
    """Invalid rating should raise ValueError."""
    try:
        RatingRecord(blinded_id="R01", rating=6, note=None,
                     flagged=False, rated_at="2026-07-14T10:00:00Z")
        assert False, "Should raise"
    except ValueError:
        pass
    print("  PASS: test_rating_record_invalid")


# ---------------------------------------------------------------------------
# Rating queue validation tests
# ---------------------------------------------------------------------------

def test_validate_queue_leaked_question_type():
    """Queue item with question_type should report forbidden key."""
    items = [{"blinded_id": "R01", "inference_context": None,
              "question": "Q", "response": "R", "question_type": "profile"}]
    data = {"schema_version": 1, "benchmark_name": "t", "created_at": "t",
            "total_items": 1, "items": items}
    errors = validate_rating_queue(data)
    assert any("forbidden" in e for e in errors)
    print("  PASS: test_validate_queue_leaked_question_type")


# ---------------------------------------------------------------------------
# Answer key validation tests
# ---------------------------------------------------------------------------

def _valid_answer_key_json():
    items = []
    for i in range(1, 25):
        items.append({
            "blinded_id": f"R{i:02d}",
            "source_method": list(VALID_SOURCE_METHODS)[i % len(VALID_SOURCE_METHODS)],
            "model": "gpt-4o",
            "question_type": "profile" if i % 2 == 0 else "task",
            "original_trial_id": str(i),
            "judge_score": (i % 5) + 1,
            "duplicate_of": None,
        })
    for i in range(6):
        orig = items[i]
        items.append({
            "blinded_id": f"R{25 + i:02d}",
            "source_method": orig["source_method"],
            "model": orig["model"],
            "question_type": orig["question_type"],
            "original_trial_id": orig["original_trial_id"],
            "judge_score": orig["judge_score"],
            "duplicate_of": orig["blinded_id"],
        })
    return {
        "schema_version": 1, "benchmark_name": "t", "sampling_seed": 1,
        "duplicate_seed": 2, "id_assignment_seed": 3, "presentation_seed": 4,
        "created_at": "t", "items": items,
    }


def test_validate_answer_key_valid():
    """Valid answer key passes."""
    errors = validate_answer_key(_valid_answer_key_json())
    assert errors == [], f"Unexpected: {errors}"
    print("  PASS: test_validate_answer_key_valid")


def test_validate_answer_key_invalid_question_type():
    """Invalid question_type in answer key should error."""
    data = _valid_answer_key_json()
    data["items"][0]["question_type"] = "integration"
    errors = validate_answer_key(data)
    assert any("question_type" in e for e in errors)
    print("  PASS: test_validate_answer_key_invalid_question_type")


# ---------------------------------------------------------------------------
# Ratings session validation tests
# ---------------------------------------------------------------------------

def test_validate_rating_record_single_score():
    """Valid single-score rating record passes."""
    record = {"blinded_id": "R07", "rating": 4, "note": None,
              "flagged": False, "rated_at": "2026-07-14T10:00:00Z"}
    errors = validate_rating_record(record)
    assert errors == [], f"Unexpected: {errors}"
    print("  PASS: test_validate_rating_record_single_score")


def test_validate_rating_forbidden_judge_score():
    """Rating record with judge_score should be forbidden."""
    record = {"blinded_id": "R07", "rating": 4, "note": None,
              "flagged": False, "rated_at": "2026-07-14T10:00:00Z",
              "judge_score": 5}
    errors = validate_rating_record(record)
    assert any("forbidden" in e for e in errors)
    print("  PASS: test_validate_rating_forbidden_judge_score")


# ---------------------------------------------------------------------------
# CompiledRecord tests
# ---------------------------------------------------------------------------

def test_compiled_record():
    """CompiledRecord captures human-judge agreement."""
    record = CompiledRecord(
        blinded_id="R01", rating=4, note=None, flagged=False,
        rated_at="t", source_method="kernel_shared", model="gpt-4o",
        question_type="profile", original_trial_id="42",
        judge_score=5, duplicate_of=None, is_duplicate=False,
        human_judge_difference=-1, exact_human_judge_match=False,
        within_one_human_judge=True,
    )
    assert record.human_judge_difference == -1
    print("  PASS: test_compiled_record")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

def main():
    print("=== Human Rating Schema Tests ===\n")

    print("Judge score selection rule:")
    test_select_judge_score_profile()
    test_select_judge_score_task()
    test_select_judge_score_invalid_type()

    print("\nSourceTrial:")
    test_source_trial_valid()
    test_source_trial_invalid_question_type()
    test_source_trial_empty_inference_context_valid()
    test_source_trial_none_inference_context_valid()
    test_source_trial_score_out_of_range()

    print("\nRatingQueueItem:")
    test_queue_item_uses_inference_context()
    test_queue_item_cannot_hold_question_type()

    print("\nRatingRecord (single score):")
    test_rating_record_single_score()
    test_rating_record_invalid()

    print("\nQueue validation:")
    test_validate_queue_leaked_question_type()

    print("\nAnswer key validation:")
    test_validate_answer_key_valid()
    test_validate_answer_key_invalid_question_type()

    print("\nRating record validation:")
    test_validate_rating_record_single_score()
    test_validate_rating_forbidden_judge_score()

    print("\nCompiledRecord:")
    test_compiled_record()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
