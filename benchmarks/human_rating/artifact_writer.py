"""Serialize the blinded plan into rater-facing queue and private answer key.

Writes two physically isolated JSON artifacts:
- rating_queue.json (rater-visible, no private metadata)
- answer_key.json (private, complete unblinding data)

Both are validated and written atomically.
"""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from benchmarks.human_rating.blinding import BlindedPlan, PlannedRatingItem
from benchmarks.human_rating.paths import RunPaths


# ---------------------------------------------------------------------------
# Forbidden keys (must not appear anywhere in the queue)
# ---------------------------------------------------------------------------

FORBIDDEN_QUEUE_KEYS = frozenset({
    "source_method", "method", "model", "original_trial_id", "trial_index",
    "judge_score", "profile_usage_score", "task_usage_score",
    "integration_score", "evaluation_dimension",
    "duplicate_of", "duplicate_of_blinded_id", "appearance_index",
    "queue_position", "sampling_seed", "blinding_seed",
    "reference_context_provenance", "is_exact_model_visible_context",
})

ALLOWED_QUEUE_ITEM_KEYS = frozenset({
    "blinded_id", "reference_context", "question", "response",
})


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WrittenArtifacts:
    """Result of a successful artifact write."""
    rating_queue_path: Path
    answer_key_path: Path
    item_count: int
    unique_source_count: int
    duplicate_count: int


# ---------------------------------------------------------------------------
# Build documents
# ---------------------------------------------------------------------------

def build_rating_queue(plan: BlindedPlan, *, run_id: str) -> dict[str, Any]:
    """Build the rater-facing queue document from a blinded plan."""
    items = []
    for item in sorted(plan.items, key=lambda x: x.appearance_index):
        items.append({
            "blinded_id": item.blinded_id,
            "reference_context": item.source_trial.reference_context,
            "question": item.source_trial.question,
            "response": item.source_trial.response,
        })

    return {
        "schema_version": 1,
        "run_id": run_id,
        "item_count": len(items),
        "items": items,
    }


def build_answer_key(
    plan: BlindedPlan,
    *,
    run_id: str,
    protocol_name: str,
    sampling_seed: int,
    blinding_seed: int,
) -> dict[str, Any]:
    """Build the private answer key document from a blinded plan."""
    unique_count = sum(1 for i in plan.items if i.duplicate_of_blinded_id is None)
    dup_count = sum(1 for i in plan.items if i.duplicate_of_blinded_id is not None)

    items = []
    for item in sorted(plan.items, key=lambda x: x.appearance_index):
        items.append({
            "blinded_id": item.blinded_id,
            "queue_position": item.appearance_index + 1,
            "source_method": item.source_trial.source_method,
            "model": item.source_trial.model,
            "original_trial_id": item.source_trial.original_trial_id,
            "evaluation_dimension": item.source_trial.evaluation_dimension,
            "judge_score": item.source_trial.judge_score,
            "profile_usage_score": item.source_trial.profile_usage_score,
            "task_usage_score": item.source_trial.task_usage_score,
            "integration_score": item.source_trial.integration_score,
            "reference_context_provenance": item.source_trial.reference_context_provenance,
            "is_exact_model_visible_context": item.source_trial.is_exact_model_visible_context,
            "duplicate_of_blinded_id": item.duplicate_of_blinded_id,
        })

    return {
        "schema_version": 1,
        "run_id": run_id,
        "protocol_name": protocol_name,
        "sampling_seed": sampling_seed,
        "blinding_seed": blinding_seed,
        "item_count": len(items),
        "unique_source_count": unique_count,
        "duplicate_count": dup_count,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _check_forbidden_keys_recursive(obj: Any, path: str = "") -> list[str]:
    """Recursively check for forbidden keys in a data structure."""
    errors = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_QUEUE_KEYS:
                errors.append(f"Forbidden key '{key}' at {path or 'root'}")
            errors.extend(_check_forbidden_keys_recursive(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            errors.extend(_check_forbidden_keys_recursive(item, f"{path}[{i}]"))
    return errors


def validate_queue_document(queue: dict[str, Any]) -> list[str]:
    """Validate the queue document for private-data leakage."""
    errors = []

    # Check top-level structure
    if queue.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if "items" not in queue:
        errors.append("Missing 'items'")
        return errors

    items = queue["items"]
    if queue.get("item_count") != len(items):
        errors.append(f"item_count mismatch: {queue.get('item_count')} != {len(items)}")

    # Check each item has exactly allowed keys
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"Item {i} is not a dict")
            continue
        keys = set(item.keys())
        if keys != ALLOWED_QUEUE_ITEM_KEYS:
            extra = keys - ALLOWED_QUEUE_ITEM_KEYS
            missing = ALLOWED_QUEUE_ITEM_KEYS - keys
            if extra:
                errors.append(f"Item {i}: unexpected keys {sorted(extra)}")
            if missing:
                errors.append(f"Item {i}: missing keys {sorted(missing)}")

    # Recursive forbidden-key check on entire document
    forbidden_found = _check_forbidden_keys_recursive(queue)
    errors.extend(forbidden_found)

    return errors


def validate_answer_key_document(key: dict[str, Any]) -> list[str]:
    """Validate the answer key document."""
    errors = []

    if key.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    items = key.get("items", [])
    if key.get("item_count") != len(items):
        errors.append(f"item_count mismatch")
    if len(items) != 30:
        errors.append(f"Expected 30 items, got {len(items)}")

    # Check unique IDs
    ids = [it["blinded_id"] for it in items]
    if len(set(ids)) != len(ids):
        errors.append("Duplicate blinded_id in answer key")

    # Check duplicates
    dups = [it for it in items if it.get("duplicate_of_blinded_id") is not None]
    originals = [it for it in items if it.get("duplicate_of_blinded_id") is None]
    if len(originals) != 24:
        errors.append(f"Expected 24 originals, got {len(originals)}")
    if len(dups) != 6:
        errors.append(f"Expected 6 duplicates, got {len(dups)}")

    # Check duplicate references resolve to originals
    original_ids = {it["blinded_id"] for it in originals}
    dup_ids = {it["blinded_id"] for it in dups}
    for dup in dups:
        ref = dup["duplicate_of_blinded_id"]
        if ref not in original_ids:
            errors.append(f"Dup {dup['blinded_id']}: ref {ref} not an original")
        if ref in dup_ids:
            errors.append(f"Dup {dup['blinded_id']}: points to another dup")

    # Queue positions 1..30
    positions = sorted(it.get("queue_position", -1) for it in items)
    if positions != list(range(1, 31)):
        errors.append("queue_positions must be exactly 1..30")

    # judge_score == integration_score
    for it in items:
        if it.get("judge_score") != it.get("integration_score"):
            errors.append(f"{it['blinded_id']}: judge_score != integration_score")
            break

    # evaluation_dimension
    for it in items:
        if it.get("evaluation_dimension") != "integration":
            errors.append(f"{it['blinded_id']}: evaluation_dimension != integration")
            break

    return errors


def validate_artifact_pair(
    queue: Mapping[str, Any],
    answer_key: Mapping[str, Any],
) -> list[str]:
    """Validate cross-artifact consistency."""
    errors = []

    if queue.get("run_id") != answer_key.get("run_id"):
        errors.append("run_id mismatch between queue and answer key")

    q_items = queue.get("items", [])
    k_items = answer_key.get("items", [])

    if len(q_items) != len(k_items):
        errors.append(f"Item count mismatch: queue={len(q_items)}, key={len(k_items)}")
        return errors

    # Identical blinded-ID order
    q_ids = [it["blinded_id"] for it in q_items]
    k_ids = [it["blinded_id"] for it in k_items]
    if q_ids != k_ids:
        errors.append("Blinded ID order mismatch between queue and answer key")

    # Queue positions match actual positions
    for i, k_item in enumerate(k_items):
        expected_pos = i + 1
        if k_item.get("queue_position") != expected_pos:
            errors.append(
                f"Position mismatch for {k_item['blinded_id']}: "
                f"expected {expected_pos}, got {k_item.get('queue_position')}"
            )
            break

    # Duplicate queue content matches
    id_to_q_item = {it["blinded_id"]: it for it in q_items}
    for k_item in k_items:
        dup_ref = k_item.get("duplicate_of_blinded_id")
        if dup_ref:
            q_dup = id_to_q_item[k_item["blinded_id"]]
            q_orig = id_to_q_item.get(dup_ref)
            if q_orig and q_dup:
                for field in ("reference_context", "question", "response"):
                    if q_dup.get(field) != q_orig.get(field):
                        errors.append(
                            f"Dup {k_item['blinded_id']}: queue {field} "
                            f"differs from original {dup_ref}"
                        )
                        break

    return errors


# ---------------------------------------------------------------------------
# Atomic file writing
# ---------------------------------------------------------------------------

def write_rating_artifacts(
    plan: BlindedPlan,
    *,
    run_paths: RunPaths,
    run_id: str,
    protocol_name: str,
    sampling_seed: int,
    blinding_seed: int,
    overwrite: bool = False,
) -> WrittenArtifacts:
    """Build, validate, and atomically write both artifacts.

    Raises:
        FileExistsError: If artifacts exist and overwrite is False.
        ValueError: If validation fails.
    """
    queue_path = Path(run_paths.rating_queue_path)
    key_path = Path(run_paths.answer_key_path)

    # Validate path separation
    if queue_path.parent.resolve() == key_path.parent.resolve():
        raise ValueError("Queue and answer key must be in separate directories")

    # Check nesting
    q_resolved = queue_path.parent.resolve()
    k_resolved = key_path.parent.resolve()
    try:
        q_resolved.relative_to(k_resolved)
        raise ValueError("Queue directory must not be nested inside private directory")
    except ValueError as e:
        if "nested" in str(e):
            raise
    try:
        k_resolved.relative_to(q_resolved)
        raise ValueError("Private directory must not be nested inside queue directory")
    except ValueError as e:
        if "nested" in str(e):
            raise

    # Overwrite protection
    if not overwrite:
        if queue_path.exists():
            raise FileExistsError(
                f"Rating queue already exists: {queue_path}. "
                "Use --overwrite to regenerate."
            )
        if key_path.exists():
            raise FileExistsError(
                f"Answer key already exists: {key_path}. "
                "Use --overwrite to regenerate."
            )

    # Build documents
    queue_doc = build_rating_queue(plan, run_id=run_id)
    key_doc = build_answer_key(
        plan, run_id=run_id, protocol_name=protocol_name,
        sampling_seed=sampling_seed, blinding_seed=blinding_seed,
    )

    # Validate individually
    q_errors = validate_queue_document(queue_doc)
    if q_errors:
        raise ValueError(f"Queue validation failed: {q_errors}")

    k_errors = validate_answer_key_document(key_doc)
    if k_errors:
        raise ValueError(f"Answer key validation failed: {k_errors}")

    # Validate pair
    pair_errors = validate_artifact_pair(queue_doc, key_doc)
    if pair_errors:
        raise ValueError(f"Pair validation failed: {pair_errors}")

    # Create directories
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically via temp files
    tmp_queue = None
    tmp_key = None
    try:
        # Write queue
        tmp_queue = tempfile.NamedTemporaryFile(
            mode="w", dir=str(queue_path.parent),
            suffix=".tmp", delete=False, encoding="utf-8",
        )
        json.dump(queue_doc, tmp_queue, indent=2, sort_keys=True, ensure_ascii=False)
        tmp_queue.write("\n")
        tmp_queue.flush()
        os.fsync(tmp_queue.fileno())
        tmp_queue.close()

        # Write answer key
        tmp_key = tempfile.NamedTemporaryFile(
            mode="w", dir=str(key_path.parent),
            suffix=".tmp", delete=False, encoding="utf-8",
        )
        json.dump(key_doc, tmp_key, indent=2, sort_keys=True, ensure_ascii=False)
        tmp_key.write("\n")
        tmp_key.flush()
        os.fsync(tmp_key.fileno())
        tmp_key.close()

        # Atomic replace
        os.replace(tmp_queue.name, str(queue_path))
        os.replace(tmp_key.name, str(key_path))

        # Set permissions on answer key (POSIX only, best-effort)
        try:
            key_path.chmod(0o600)
        except (OSError, NotImplementedError):
            pass

        # Set queue permissions
        try:
            queue_path.chmod(0o644)
        except (OSError, NotImplementedError):
            pass

    except Exception:
        # Cleanup temp files on failure
        if tmp_queue and os.path.exists(tmp_queue.name):
            os.unlink(tmp_queue.name)
        if tmp_key and os.path.exists(tmp_key.name):
            os.unlink(tmp_key.name)
        raise

    unique_count = sum(1 for i in plan.items if i.duplicate_of_blinded_id is None)
    dup_count = sum(1 for i in plan.items if i.duplicate_of_blinded_id is not None)

    return WrittenArtifacts(
        rating_queue_path=queue_path,
        answer_key_path=key_path,
        item_count=len(plan.items),
        unique_source_count=unique_count,
        duplicate_count=dup_count,
    )
