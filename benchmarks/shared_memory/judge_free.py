"""Judge-free measures of what reached the consumer (NeurIPS Subtask 10,
AIOS docs/HETEROGENEITY.md, "Measurements").

Computed from a trial's injection diagnostics (the block text and each
injected row's stored ``user_id`` / ``sharing_policy`` / provenance) and
the writers' recorded writes. Never from the judge.
"""
import json
import re
from typing import Any, Iterable, List, Optional, Tuple

from benchmarks.shared_memory.models import (
    InjectionDiagnostics,
    JudgeFreeMeasures,
    SyntheticProfile,
    WrittenMemoryRecord,
)
from cerebrum.example.agents.shared_memory_utils import SCHEMA

CONSUMER = "assistant_agent"

# The writer-schema keys that mark a raw payload in a block row: the
# canonical field names with an underscore (plain words such as "goals"
# also occur in rendered sentences).
SCHEMA_KEYS = tuple(sorted(
    name for fields in SCHEMA.values() for name in fields if "_" in name
))

_LEGACY_TIMESTAMP = re.compile(r"^\[[^\]]*\] ")


def provenance_items(profile: SyntheticProfile) -> List[str]:
    """The profile items checked in the block: name, language, style
    and each preferred tool."""
    items = [profile.user_name, profile.preferred_language,
             profile.response_style, *profile.preferred_tools]
    return [item for item in items if item and item.strip()]


def contains(text: str, item: str) -> bool:
    """``item`` in ``text``, case-insensitive, not inside a longer word
    (so the language "Go" does not match "algorithm")."""
    pattern = r"(?<!\w)" + re.escape(item.strip()) + r"(?!\w)"
    return re.search(pattern, text or "", re.IGNORECASE) is not None


def block_rows(block_text: str) -> List[str]:
    """The bullet rows of a block in any format (compact, legacy,
    native), without bullet or legacy timestamp."""
    rows = []
    for line in (block_text or "").split("\n"):
        if line.startswith("- "):
            rows.append(_LEGACY_TIMESTAMP.sub("", line[2:]))
    return rows


def is_raw_payload(row: str) -> bool:
    """A JSON object, or a row carrying a writer-schema key."""
    text = row.strip()
    if text.startswith("{"):
        try:
            if isinstance(json.loads(text), dict):
                return True
        except ValueError:
            pass
    return any(key in text for key in SCHEMA_KEYS)


def _field(record: Any, name: str) -> Any:
    """``record.name`` for a model, ``record[name]`` for a stored dict."""
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


def split_missing(
    missing: Iterable[str], written: Iterable[Any],
) -> Tuple[List[str], List[str]]:
    """``(withheld, lost)``: the missing writers split by why their rows
    did not reach the consumer (Subtask 14).

    A writer is *withheld* when every row it stored was private, or
    carried no policy (the private default): the visibility rule kept it
    from the consumer, as it should. It is *lost* when it stored at least
    one shared row and none reached the block: stored under another user
    id, or dropped by the threshold, the dedupe, the cap or the budget.
    ``written`` holds ``WrittenMemoryRecord``\\ s or their stored dicts,
    so old result files can be split too.
    """
    shared = {
        _field(record, "agent_name") for record in written
        if (_field(record, "sharing_policy") or "private") == "shared"
    }
    missing = list(missing)
    withheld = [writer for writer in missing if writer not in shared]
    lost = [writer for writer in missing if writer in shared]
    return withheld, lost


def measure(
    profile: SyntheticProfile,
    trial_user_id: str,
    diagnostics: Optional[InjectionDiagnostics],
    written: Iterable[WrittenMemoryRecord],
    consumer: str = CONSUMER,
) -> JudgeFreeMeasures:
    """The trial's measures. ``trial_user_id`` is the reference id the
    trial's provenance names (the method-scoped user id)."""
    injected = list(diagnostics.injected_memories) if diagnostics else []
    block_text = diagnostics.block_text if diagnostics else None

    facts = None
    missing_facts: List[str] = []
    if block_text is not None:
        items = provenance_items(profile)
        missing_facts = [
            i for i in items if not contains(block_text, i)
        ]
        facts = (
            (len(items) - len(missing_facts)) / len(items) if items else None
        )

    def writer_of(row) -> str:
        return row.provenance_agent or row.owner_agent or ""

    def user_of(row) -> str:
        return row.provenance_user or row.user_id or ""

    cross_user = sum(1 for row in injected if user_of(row) != trial_user_id)
    private_from_others = sum(
        1 for row in injected
        if writer_of(row) != consumer
        and (row.sharing_policy or "private") != "shared"
    )
    seen = {
        writer_of(row) for row in injected if user_of(row) == trial_user_id
    }
    written = list(written)
    stored = sorted({
        record.agent_name for record in written
        if record.agent_name != consumer
    })
    missing = [agent for agent in stored if agent not in seen]
    withheld, lost = split_missing(missing, written)
    raw_rows = sum(1 for row in block_rows(block_text or "")
                   if is_raw_payload(row))
    return JudgeFreeMeasures(
        profile_facts_in_block=facts,
        profile_facts_missing=missing_facts,
        cross_user_rows=cross_user,
        private_rows_from_others=private_from_others,
        memories_missing=len(missing),
        memories_missing_writers=missing,
        memories_withheld=len(withheld),
        memories_withheld_writers=withheld,
        memories_lost=len(lost),
        memories_lost_writers=lost,
        raw_payload_rows=raw_rows,
    )
