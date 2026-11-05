"""Shared constants and utilities for the multi-agent personalization system.

This module provides memory metadata field names, sharing policy values,
memory type values, and helper functions used by the Assistant Agent,
Profile Agent, and Task Agent.
"""

from typing import Any, Optional, List, Dict

# --- Memory metadata field names ---
FIELD_OWNER_AGENT = "owner_agent"
FIELD_USER_ID = "user_id"
FIELD_MEMORY_TYPE = "memory_type"
FIELD_SHARING_POLICY = "sharing_policy"

# --- Sharing policy values ---
POLICY_PRIVATE = "private"
POLICY_SHARED = "shared"

# --- Memory type values ---
MEMORY_TYPE_CONVERSATION = "conversation"
MEMORY_TYPE_PROFILE = "profile"
MEMORY_TYPE_TASK_CONTEXT = "task_context"


_VALID_SHARING_POLICIES = {POLICY_PRIVATE, POLICY_SHARED}
_VALID_MEMORY_TYPES = {MEMORY_TYPE_PROFILE, MEMORY_TYPE_TASK_CONTEXT, MEMORY_TYPE_CONVERSATION}


def build_memory_metadata(
    owner_agent: str,
    user_id: str,
    memory_type: str,
    sharing_policy: str = POLICY_PRIVATE,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a validated metadata dict for kernel memory operations.

    Args:
        owner_agent: The agent_name of the creating agent. Must be non-empty.
        user_id: Identifier for the user. Must be non-empty.
        memory_type: One of "profile", "task_context", "conversation".
        sharing_policy: "private" (default) or "shared".
        **extra: Additional provider-specific keys.

    Returns:
        A metadata dictionary with exactly the four standard fields
        plus any extra kwargs.

    Raises:
        ValueError: If sharing_policy, memory_type, owner_agent, or
            user_id is invalid.
    """
    if sharing_policy not in _VALID_SHARING_POLICIES:
        raise ValueError(
            f"Invalid sharing_policy: {sharing_policy!r}. "
            f"Must be one of {sorted(_VALID_SHARING_POLICIES)}."
        )
    if memory_type not in _VALID_MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory_type: {memory_type!r}. "
            f"Must be one of {sorted(_VALID_MEMORY_TYPES)}."
        )
    if not isinstance(owner_agent, str) or not owner_agent:
        raise ValueError(
            f"Invalid owner_agent: {owner_agent!r}. "
            "owner_agent must be a non-empty string."
        )
    if not isinstance(user_id, str) or not user_id:
        raise ValueError(
            f"Invalid user_id: {user_id!r}. "
            "user_id must be a non-empty string."
        )

    metadata: Dict[str, Any] = {
        FIELD_OWNER_AGENT: owner_agent,
        FIELD_USER_ID: user_id,
        FIELD_MEMORY_TYPE: memory_type,
        FIELD_SHARING_POLICY: sharing_policy,
    }
    metadata.update(extra)
    return metadata


def filter_shared_memories(
    search_results: List[Dict[str, Any]],
    memory_type: Optional[str] = None,
    exclude_owner: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter search results to only shared memories, optionally by type.

    Args:
        search_results: Raw list from search_memories response.
        memory_type: If provided, only include memories of this type.
        exclude_owner: If provided, exclude memories owned by this agent.

    Returns:
        Filtered list of memory result dicts.
    """
    filtered: List[Dict[str, Any]] = []
    for mem in search_results:
        meta = mem.get("metadata", {})
        if meta.get(FIELD_SHARING_POLICY) != POLICY_SHARED:
            continue
        if memory_type and meta.get(FIELD_MEMORY_TYPE) != memory_type:
            continue
        if exclude_owner and meta.get(FIELD_OWNER_AGENT) == exclude_owner:
            continue
        filtered.append(mem)
    return filtered


# ---------------------------------------------------------------------------
# Writer output: validation and the one shared rendering (Subtask 9)
# ---------------------------------------------------------------------------
#
# Every writer (kernel, replicated and native) validates its extraction
# against the schema below, retries up to WRITER_RETRIES times, and on
# success stores ``render(memory_type, fields)`` as the memory text with
# the fields themselves as JSON in ``metadata["structured"]``. A writer
# whose extraction never validates stores nothing and reports
# ``writer_failed``.

import json as _json
from dataclasses import dataclass as _dataclass, field as _field

WRITER_RETRIES = 2
FIELD_STRUCTURED = "structured"

# Canonical field -> (accepted keys, kind). "list" fields take a list of
# non-empty strings (a non-empty string is one item); "list0" may be
# empty. Aliases cover keys real extractions use (Subtask 6).
SCHEMA = {
    MEMORY_TYPE_PROFILE: {
        "user_name": (("user_name", "username", "name"), "str"),
        "preferred_tools": (("preferred_tools", "tools"), "list"),
        "preferred_language": (
            ("preferred_language", "language"), "str"),
        "response_style": (
            ("response_style", "response_type", "style"), "str"),
    },
    MEMORY_TYPE_TASK_CONTEXT: {
        "current_project": (
            ("current_project", "project_name", "project"), "str"),
        "active_experiment": (
            ("active_experiment", "experiment_name", "experiment"), "str"),
        "goals": (("goals",), "list"),
        "blockers": (("blockers",), "list0"),
        "next_steps": (("next_steps", "next_actions"), "list"),
    },
}

TEMPLATES = {
    MEMORY_TYPE_PROFILE: [
        ("user_name", "My name is {}."),
        ("preferred_tools", "I prefer to use {}."),
        ("preferred_language", "My preferred programming language is {}."),
        ("response_style", "I like {} responses."),
    ],
    MEMORY_TYPE_TASK_CONTEXT: [
        ("current_project", "I'm working on {}."),
        ("active_experiment", "My current experiment is {}."),
        ("goals", "My goals are: {}."),
        ("blockers", "My blockers are: {}."),
        ("next_steps", "My next steps are: {}."),
    ],
}


def _coerce(value: Any, kind: str) -> Any:
    """The value as its kind, or None if it does not fit."""
    if kind == "str":
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
        return None
    if isinstance(value, str):
        value = [value] if value.strip() else []
    if not isinstance(value, list):
        return None
    items = [str(v).strip() for v in value
             if isinstance(v, (str, int, float))]
    if len(items) != len(value) or any(not i for i in items):
        return None
    if kind == "list" and not items:
        return None
    return items


def validate_extraction(memory_type: str, data: Any) -> tuple:
    """``(fields, problems)``: the schema's fields from a writer's
    extraction, or ``None`` and what is wrong. A single key holding an
    object is unwrapped first; aliases are mapped; other keys are
    ignored."""
    if not isinstance(data, dict):
        return None, [f"not a JSON object: {type(data).__name__}"]
    if len(data) == 1 and isinstance(next(iter(data.values())), dict):
        data = next(iter(data.values()))
    fields, problems = {}, []
    for name, (keys, kind) in SCHEMA[memory_type].items():
        key = next((k for k in keys if k in data), None)
        if key is None:
            problems.append(f"missing {name}")
            continue
        value = _coerce(data[key], kind)
        if value is None:
            problems.append(f"bad {name}: {data[key]!r}"[:120])
        else:
            fields[name] = value
    return (None, problems) if problems else (fields, [])


def render(memory_type: str, fields: Dict[str, Any]) -> str:
    """The memory text every writer stores for validated ``fields``."""
    def text(value):
        return "; ".join(value) if isinstance(value, list) else value
    return " ".join(
        template.format(text(fields[name]))
        for name, template in TEMPLATES[memory_type]
        if fields.get(name) not in (None, [])
    )


def structured(fields: Dict[str, Any]) -> str:
    """The fields as the JSON string kept in the memory's metadata."""
    return _json.dumps(fields, sort_keys=True)


@_dataclass
class Extraction:
    """A writer's validated extraction, after its retries."""

    memory_type: str
    fields: Optional[Dict[str, Any]] = None
    retries: int = 0
    problems: List[str] = _field(default_factory=list)
    token_usages: List[Optional[dict]] = _field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.fields is None

    @property
    def text(self) -> str:
        return render(self.memory_type, self.fields) if self.fields else ""

    def report(self) -> Dict[str, Any]:
        """The keys a writer's result carries about its extraction."""
        return {
            "writer_failed": self.failed,
            "writer_retries": self.retries,
            "writer_problems": self.problems,
            "token_usages": self.token_usages,
        }


def extract_validated(
    memory_type: str, extract_once, usage_of=lambda: None,
    retries: int = WRITER_RETRIES,
) -> Extraction:
    """Call ``extract_once()`` until its result validates, at most
    ``1 + retries`` times. ``usage_of()`` returns the last call's token
    usage. An exception counts as an invalid attempt."""
    result = Extraction(memory_type)
    for attempt in range(retries + 1):
        result.retries = attempt
        try:
            data = extract_once()
            fields, problems = validate_extraction(memory_type, data)
        except Exception as e:  # unparseable reply, transport error
            fields, problems = None, [f"{type(e).__name__}: {e}"[:200]]
        result.token_usages.append(usage_of())
        if fields is not None:
            result.fields, result.problems = fields, []
            return result
        result.problems = problems
    return result
