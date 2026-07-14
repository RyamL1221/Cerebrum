"""Validation helpers for the human-rating workflow file formats.

Provides functions to validate:
- Rating queue JSON structure
- Answer key JSON structure and referential integrity
- Rating session JSONL records
"""

import json
from typing import Any

from benchmarks.human_rating.schemas import (
    VALID_RATINGS,
    VALID_SOURCE_METHODS,
    VALID_QUESTION_TYPES,
)


# ---------------------------------------------------------------------------
# Rating queue validation
# ---------------------------------------------------------------------------

_QUEUE_REQUIRED_TOP_KEYS = {"schema_version", "benchmark_name", "created_at", "total_items", "items"}
_QUEUE_ITEM_REQUIRED_KEYS = {"blinded_id", "profile_context", "question", "response"}
_QUEUE_FORBIDDEN_KEYS = {
    "source_method", "method", "model", "question_type", "original_trial_id",
    "judge_score", "duplicate_of", "duplicate_status", "is_duplicate",
    "sampling_seed", "shuffle_seed", "source_path", "source_file",
}


def validate_rating_queue(data: dict[str, Any]) -> list[str]:
    """Validate a rating queue JSON structure.

    Args:
        data: Parsed JSON dict of the rating queue file.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # Top-level keys
    missing_top = _QUEUE_REQUIRED_TOP_KEYS - set(data.keys())
    if missing_top:
        errors.append(f"Missing top-level keys: {sorted(missing_top)}")
        return errors

    if data["schema_version"] != 1:
        errors.append(f"Unsupported schema_version: {data['schema_version']}")

    items = data.get("items", [])
    if not isinstance(items, list):
        errors.append("'items' must be a list")
        return errors

    if data["total_items"] != len(items):
        errors.append(
            f"total_items ({data['total_items']}) != actual item count ({len(items)})"
        )

    seen_ids: set[str] = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"Item {i} is not a dict")
            continue

        # Check required keys
        missing_item = _QUEUE_ITEM_REQUIRED_KEYS - set(item.keys())
        if missing_item:
            errors.append(f"Item {i}: missing keys {sorted(missing_item)}")

        # Check for forbidden (leaked) keys
        leaked = _QUEUE_FORBIDDEN_KEYS & set(item.keys())
        if leaked:
            errors.append(f"Item {i}: contains forbidden keys {sorted(leaked)}")

        # Unique blinded_id
        bid = item.get("blinded_id", "")
        if bid in seen_ids:
            errors.append(f"Item {i}: duplicate blinded_id '{bid}'")
        seen_ids.add(bid)

        # Nonempty content
        if not item.get("question", "").strip():
            errors.append(f"Item {i} ('{bid}'): empty question")
        if not item.get("response", "").strip():
            errors.append(f"Item {i} ('{bid}'): empty response")

    return errors


# ---------------------------------------------------------------------------
# Answer key validation
# ---------------------------------------------------------------------------

_KEY_REQUIRED_TOP_KEYS = {
    "schema_version", "benchmark_name", "sampling_seed",
    "duplicate_seed", "id_assignment_seed", "presentation_seed",
    "created_at", "items",
}
_KEY_ITEM_REQUIRED_KEYS = {
    "blinded_id", "source_method", "model", "question_type",
    "original_trial_id", "judge_score", "duplicate_of",
}


def validate_answer_key(data: dict[str, Any], expected_count: int = 30) -> list[str]:
    """Validate an answer key JSON structure.

    Args:
        data: Parsed JSON dict of the answer key file.
        expected_count: Expected number of items (default 30).

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # Top-level keys
    missing_top = _KEY_REQUIRED_TOP_KEYS - set(data.keys())
    if missing_top:
        errors.append(f"Missing top-level keys: {sorted(missing_top)}")
        return errors

    if data["schema_version"] != 1:
        errors.append(f"Unsupported schema_version: {data['schema_version']}")

    items = data.get("items", [])
    if not isinstance(items, list):
        errors.append("'items' must be a list")
        return errors

    if len(items) != expected_count:
        errors.append(f"Expected {expected_count} items, got {len(items)}")

    seen_ids: set[str] = set()
    duplicates: list[dict] = []
    id_to_item: dict[str, dict] = {}

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"Item {i} is not a dict")
            continue

        # Check required keys
        missing_item = _KEY_ITEM_REQUIRED_KEYS - set(item.keys())
        if missing_item:
            errors.append(f"Item {i}: missing keys {sorted(missing_item)}")
            continue

        bid = item["blinded_id"]

        # Unique blinded_id
        if bid in seen_ids:
            errors.append(f"Item {i}: duplicate blinded_id '{bid}'")
        seen_ids.add(bid)
        id_to_item[bid] = item

        # Valid source_method
        if item["source_method"] not in VALID_SOURCE_METHODS:
            errors.append(f"Item {i} ('{bid}'): invalid source_method '{item['source_method']}'")

        # Valid question_type
        if item["question_type"] not in VALID_QUESTION_TYPES:
            errors.append(f"Item {i} ('{bid}'): invalid question_type '{item['question_type']}'")

        # Valid judge_score
        js = item["judge_score"]
        if not isinstance(js, int) or js < 1 or js > 5:
            errors.append(f"Item {i} ('{bid}'): invalid judge_score {js!r}")

        # Track duplicates
        if item["duplicate_of"] is not None:
            duplicates.append(item)

    # Validate duplicates
    dup_count = len(duplicates)
    if dup_count != 6:
        errors.append(f"Expected exactly 6 duplicate items, got {dup_count}")

    for dup in duplicates:
        target = dup["duplicate_of"]
        bid = dup["blinded_id"]

        # Target must exist
        if target not in id_to_item:
            errors.append(f"Duplicate '{bid}': target '{target}' does not exist")
            continue

        # No self-reference
        if target == bid:
            errors.append(f"Duplicate '{bid}': points to itself")
            continue

        # Source must match original
        original = id_to_item[target]
        for field in ("source_method", "model", "question_type", "original_trial_id", "judge_score"):
            if dup[field] != original[field]:
                errors.append(
                    f"Duplicate '{bid}': {field} mismatch with original '{target}' "
                    f"({dup[field]!r} != {original[field]!r})"
                )

    return errors


# ---------------------------------------------------------------------------
# Ratings session validation
# ---------------------------------------------------------------------------

_RATING_REQUIRED_KEYS = {"blinded_id", "rating", "note", "flagged", "rated_at"}
_RATING_FORBIDDEN_KEYS = {
    "source_method", "method", "model", "question_type",
    "original_trial_id", "judge_score", "duplicate_of",
}


def validate_rating_record(record: dict[str, Any]) -> list[str]:
    """Validate a single rating record (one JSONL line).

    Args:
        record: Parsed JSON dict from one line of the ratings file.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []

    missing = _RATING_REQUIRED_KEYS - set(record.keys())
    if missing:
        errors.append(f"Missing keys: {sorted(missing)}")
        return errors

    # Forbidden keys
    leaked = _RATING_FORBIDDEN_KEYS & set(record.keys())
    if leaked:
        errors.append(f"Contains forbidden keys: {sorted(leaked)}")

    # Valid rating
    rating = record["rating"]
    if not isinstance(rating, int) or rating not in VALID_RATINGS:
        errors.append(f"Invalid rating: {rating!r} (must be int 1–5)")

    # Nonempty blinded_id
    if not record["blinded_id"] or not str(record["blinded_id"]).strip():
        errors.append("blinded_id must be nonempty")

    # Rated_at present
    if not record["rated_at"] or not str(record["rated_at"]).strip():
        errors.append("rated_at must be nonempty")

    # Flagged must be boolean
    if not isinstance(record["flagged"], bool):
        errors.append(f"flagged must be bool, got {type(record['flagged']).__name__}")

    return errors


def validate_ratings_session(lines: list[dict[str, Any]]) -> list[str]:
    """Validate a complete ratings session (all JSONL records).

    Checks individual records plus cross-record constraints (no duplicate IDs).

    Args:
        lines: List of parsed dicts from the ratings JSONL file.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []
    seen_ids: set[str] = set()

    for i, record in enumerate(lines):
        record_errors = validate_rating_record(record)
        for err in record_errors:
            errors.append(f"Record {i}: {err}")

        bid = record.get("blinded_id", "")
        if bid in seen_ids:
            errors.append(f"Record {i}: duplicate blinded_id '{bid}' (ratings are immutable)")
        seen_ids.add(bid)

    return errors
