"""Local logging for ``report_reward`` calls in the shared-memory harness.

Every ``report_reward`` MemoryQuery that Cerebrum sends to the kernel is also
logged locally here, so pilot-run results can be cross-checked against the
kernel-side per-trial reward logs (master-prompt deliverable #4).

This module is purely observational:
- It does NOT send the request (Subtask 4 owns the call site).
- It does NOT retry, validate, filter, or score anything.
- A logging failure is swallowed so it can never affect the request itself.

It reuses the harness-wide logging pattern (module-level
``logging.getLogger(__name__)``, matching ``pipeline.py`` /
``run_evaluation.py``) rather than introducing a new mechanism.

Empty ``memory_ids_involved`` disambiguation
--------------------------------------------
An empty ``memory_ids_involved`` list can mean two genuinely different things,
which must not be conflated in the log:

- ``mem0_id_gap`` — memories WERE retrieved/injected for this trial, but the
  Mem0 provider's ``retrieve_memory`` payload omits a per-entry memory ID, so
  no IDs could be captured. This is the known upstream dependency documented in
  ``docs/mem0-search-results-memory-id-gap.md`` and warned about in
  ``pipeline.py`` (Subtask 2). The reward still applies to real memories; we
  just can't name them yet.
- ``no_memories_retrieved`` — genuinely nothing was retrieved for this trial
  (e.g. a private-memory baseline, or a Phase 1 isolation trial). There are no
  memories to attribute the reward to.

Callers pass ``retrieved_memory_count`` so this module can tell the two apart.
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Reason codes for an empty memory_ids_involved list. Kept as module constants
# so downstream log consumers / tests can match on stable strings.
REASON_HAS_IDS = "has_ids"
REASON_MEM0_ID_GAP = "mem0_id_gap"
REASON_NO_MEMORIES_RETRIEVED = "no_memories_retrieved"


def classify_memory_ids_state(
    memory_ids_involved: List[str],
    retrieved_memory_count: int,
) -> str:
    """Classify why ``memory_ids_involved`` is (or isn't) empty.

    Args:
        memory_ids_involved: The IDs being reported for this trial.
        retrieved_memory_count: How many memories were actually
            retrieved/injected for this trial (independent of whether their
            IDs were captured). Typically ``RetrievalLog.shared_memory_count``
            or ``len(RetrievalLog.retrieved_memories)``.

    Returns:
        One of ``REASON_HAS_IDS``, ``REASON_MEM0_ID_GAP``, or
        ``REASON_NO_MEMORIES_RETRIEVED``.
    """
    if memory_ids_involved:
        return REASON_HAS_IDS
    if retrieved_memory_count > 0:
        # Memories existed for the trial but no IDs came through — the Mem0 gap.
        return REASON_MEM0_ID_GAP
    return REASON_NO_MEMORIES_RETRIEVED


def log_report_reward(
    trial_id: Any,
    memory_ids_involved: List[str],
    reward_value: float,
    trial_metadata: Dict[str, Any],
    retrieved_memory_count: int = 0,
    timestamp: Optional[float] = None,
) -> None:
    """Log a single ``report_reward`` payload locally.

    Intended to be called alongside (before or after) the actual
    ``report_reward`` send in the trial loop. Logs the full payload plus a
    timestamp, and — when ``memory_ids_involved`` is empty — distinguishes the
    Mem0-ID-gap case from the genuinely-no-memories case at different log
    levels so pilot output is not misread.

    This function never raises: any logging error is caught and reported at
    debug level so the caller's ``report_reward`` request is unaffected.

    Args:
        trial_id: Identifier for the trial (e.g. ``trial_index``).
        memory_ids_involved: Memory IDs the reward is attributed to.
        reward_value: The scalar reward for this trial.
        trial_metadata: Arbitrary trial context sent with the reward.
        retrieved_memory_count: Number of memories retrieved/injected for the
            trial, used to disambiguate an empty ``memory_ids_involved``.
        timestamp: Epoch seconds; defaults to ``time.time()`` when omitted.
    """
    try:
        ts = timestamp if timestamp is not None else time.time()
        reason = classify_memory_ids_state(memory_ids_involved, retrieved_memory_count)

        payload = {
            "event": "report_reward",
            "trial_id": trial_id,
            "memory_ids_involved": list(memory_ids_involved),
            "reward_value": reward_value,
            "trial_metadata": trial_metadata,
            "timestamp": ts,
            "memory_ids_state": reason,
        }

        if reason == REASON_MEM0_ID_GAP:
            # Distinct WARNING level + explicit flag so an empty list here is
            # NOT read as "no memories were ever injected". Root cause is the
            # upstream Mem0 ID gap (see pipeline.py Subtask 2 warning and
            # docs/mem0-search-results-memory-id-gap.md).
            logger.warning(
                "report_reward trial_id=%s: memory_ids_involved EMPTY due to Mem0 ID gap "
                "(%d memories retrieved but no IDs in payload; see "
                "docs/mem0-search-results-memory-id-gap.md). reward_value=%s ts=%s "
                "payload=%s",
                trial_id, retrieved_memory_count, reward_value, ts, payload,
            )
        elif reason == REASON_NO_MEMORIES_RETRIEVED:
            # Genuinely nothing retrieved — a different situation from the gap.
            logger.info(
                "report_reward trial_id=%s: memory_ids_involved empty because no "
                "memories were retrieved for this trial. reward_value=%s ts=%s payload=%s",
                trial_id, reward_value, ts, payload,
            )
        else:
            logger.info(
                "report_reward trial_id=%s: reporting reward for %d memories. "
                "reward_value=%s ts=%s payload=%s",
                trial_id, len(memory_ids_involved), reward_value, ts, payload,
            )
    except Exception as e:  # pragma: no cover - logging must never break sending
        # Purely observational: swallow so the report_reward send is unaffected.
        logger.debug("log_report_reward failed (non-fatal): %s", e)
