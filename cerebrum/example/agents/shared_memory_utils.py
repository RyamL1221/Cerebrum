"""Shared constants and utilities for the multi-agent personalization system.

This module provides memory metadata field names, sharing policy values,
memory type values, and helper functions used by the Assistant Agent,
Profile Agent, Task Agent and Calendar Agent, and the event loop every
benchmark v2 writer runs (``run_v2_session``).
"""

from typing import Any, Callable, Optional, List, Dict

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
# The calendar writer's rows (benchmark v2, AIOS docs/BENCHMARK_V2.md).
MEMORY_TYPE_CALENDAR = "calendar"


_VALID_SHARING_POLICIES = {POLICY_PRIVATE, POLICY_SHARED}
_VALID_MEMORY_TYPES = {
    MEMORY_TYPE_PROFILE, MEMORY_TYPE_TASK_CONTEXT, MEMORY_TYPE_CALENDAR,
    MEMORY_TYPE_CONVERSATION,
}


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
        memory_type: One of "profile", "task_context", "calendar",
            "conversation".
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
# A retry under greedy decoding repeats the first answer, so retries
# sample (Subtask 9d follow-up): attempt n > 0 uses this temperature and
# the request's seed + n; the first attempt keeps the request's decoding.
RETRY_TEMPERATURE = 0.3
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
    attempt_settings: List[Optional[dict]] = _field(default_factory=list)

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
            "writer_attempt_settings": self.attempt_settings,
        }


def attempt_llms(llms: Optional[list], attempt: int) -> Optional[list]:
    """The ``llms`` entries for extraction attempt ``attempt``: attempt 0
    unchanged; a retry at ``RETRY_TEMPERATURE`` with the entry's seed +
    ``attempt`` (no seed when the entry has none). ``None`` stays
    ``None`` (the kernel's default decoding)."""
    if not llms or attempt == 0:
        return llms
    out = []
    for entry in llms:
        entry = dict(entry, temperature=RETRY_TEMPERATURE)
        if entry.get("seed") is not None:
            entry["seed"] = int(entry["seed"]) + attempt
        out.append(entry)
    return out


def attempt_setting(llms: Optional[list], attempt: int) -> Dict[str, Any]:
    """``{"attempt", "temperature", "seed"}`` an attempt requested (the
    first entry's; ``None`` for what the kernel's default decides)."""
    entry = (llms or [{}])[0]
    return {"attempt": attempt, "temperature": entry.get("temperature"),
            "seed": entry.get("seed")}


def extract_validated(
    memory_type: str, extract_once, usage_of=lambda: None,
    retries: int = WRITER_RETRIES, llms: Optional[list] = None,
) -> Extraction:
    """Call ``extract_once(attempt_llms)`` until its result validates, at
    most ``1 + retries`` times; attempt n gets ``attempt_llms(llms, n)``
    and its settings are recorded. ``usage_of()`` returns the last
    call's token usage. An exception counts as an invalid attempt."""
    result = Extraction(memory_type)
    for attempt in range(retries + 1):
        result.retries = attempt
        these = attempt_llms(llms, attempt)
        result.attempt_settings.append(attempt_setting(these, attempt))
        try:
            data = extract_once(these)
            fields, problems = validate_extraction(memory_type, data)
        except Exception as e:  # unparseable reply, transport error
            fields, problems = None, [f"{type(e).__name__}: {e}"[:200]]
        result.token_usages.append(usage_of())
        if fields is not None:
            result.fields, result.problems = fields, []
            return result
        result.problems = problems
    return result


# ---------------------------------------------------------------------------
# Benchmark v2 writers (Subtask 14, AIOS docs/BENCHMARK_V2.md)
# ---------------------------------------------------------------------------
#
# A v2 writer gets one session of scripted events and makes the writes
# and deletes they imply, with no LLM call: each event already says what
# to store. Its input is ``json.dumps({"v2_session": {"session": n,
# "events": [...]}})``; any other input keeps the writer's v1 behaviour.
# ``run_v2_session`` is the one event loop of every writer in every
# locus; each locus passes its own create, list and delete calls.

import logging as _logging

_logger = _logging.getLogger(__name__)

V2_SESSION_KEY = "v2_session"
# The event types that write one row; an echo is an ``add``.
V2_WRITE_EVENTS = ("base", "add", "update", "contradict", "private")
V2_REVOKE = "revoke"
V2_EVENT_TYPES = V2_WRITE_EVENTS + (V2_REVOKE,)
# A listing asks for this many rows (BENCHMARK_V2.md, "Listings reach
# every row"); one that comes back with as many may have cut some.
V2_LIST_LIMIT = 10_000

FIELD_FACT_KEY = "fact_key"
FIELD_EVENT_TYPE = "event_type"
FIELD_SESSION = "session"
FIELD_PROVENANCE_EVENT = "provenance_event"
# A statement's value aliases, as a JSON string (benchmark v2,
# Amendment 4): the forget matches carriers by every form of a value.
FIELD_VALUE_ALIASES = "value_aliases"
MEMORY_NOT_FOUND = "Memory not found"
# How a revoke deleted (Amendment 4): through the kernel's or the
# library's user-scoped forget, or by the owner's own list and delete
# (native, and the writer_scoped control).
REVOKE_FORGET = "forget"
REVOKE_OWNER = "owner"
# ``agent.forget_scope``: "user" revokes through ``forget`` when the
# locus gives one; "writer" (the writer_scoped control) never does.
FORGET_SCOPES = ("user", "writer")


class WriterError(RuntimeError):
    """A v2 writer's create, list or delete failed. The session stops
    there: a v2 writer never catches and continues."""


def parse_v2_session(task_input: Any) -> Optional[Dict[str, Any]]:
    """The v2 session in a writer's input (``{"session", "events"}``),
    or ``None`` when the input is not a v2 session, so the writer keeps
    its v1 behaviour. A ``v2_session`` that is not an object comes back
    empty, which ``run_v2_session`` refuses."""
    if not isinstance(task_input, str):
        return None
    try:
        data = _json.loads(task_input)
    except ValueError:
        return None
    if not isinstance(data, dict) or V2_SESSION_KEY not in data:
        return None
    payload = data[V2_SESSION_KEY]
    return payload if isinstance(payload, dict) else {}


def v2_structured(event: Dict[str, Any]) -> str:
    """The event as the JSON string a v2 write keeps in
    ``metadata.structured`` (its ``fact_key``, ``value`` and
    ``event_type``): what V5 writes as its raw payload. A base event
    carries the base profile or task context as ``fields`` (the harness
    adds them), and its payload is those fields, as v1's writers kept
    them (``structured``): a fact-less payload would leave Mem0 nothing
    to extract."""
    if event.get("type") == "base" and isinstance(event.get("fields"),
                                                    dict):
        return structured(event["fields"])
    return _json.dumps({
        FIELD_FACT_KEY: event.get(FIELD_FACT_KEY),
        "value": event.get("value"),
        FIELD_EVENT_TYPE: event.get("type"),
    }, sort_keys=True)


def v2_sharing_policy(agent: Any, event: Dict[str, Any]) -> str:
    """``private`` for a private event; any other event is ``shared``
    when the writer's ``share_memory`` is true, else ``private`` (V1).
    The kernel writers also have a ``share_memory`` method: a value that
    is not a bool (that bound method, when the harness set no attribute)
    counts as the default, True."""
    if event.get("type") == "private":
        return POLICY_PRIVATE
    share = getattr(agent, "share_memory", True)
    if not isinstance(share, bool):
        share = True
    return POLICY_SHARED if share else POLICY_PRIVATE


def v2_write_metadata(
    agent: Any, memory_type: str, session: int, event: Dict[str, Any],
) -> Dict[str, Any]:
    """The metadata of one v2 write: the four standard fields,
    ``fact_key``, ``event_type`` (the event's type: an echo is ``add``),
    ``session``, ``structured`` and, for an event with a value,
    ``value_aliases`` (its aliases as a JSON string, ``"[]"`` for none:
    Chroma refuses an empty list); then the deployment's
    ``extra_metadata`` (the harness's provenance); last
    ``provenance_event``, the event's id, which nothing overrides."""
    fields = {
        FIELD_FACT_KEY: event[FIELD_FACT_KEY],
        FIELD_EVENT_TYPE: event["type"],
        FIELD_SESSION: session,
        FIELD_STRUCTURED: v2_structured(event),
    }
    if isinstance(event.get("value"), str) and event["value"]:
        fields[FIELD_VALUE_ALIASES] = _json.dumps(
            [str(alias) for alias in event.get("aliases") or []]
        )
    metadata = build_memory_metadata(
        owner_agent=agent.agent_name,
        user_id=agent.user_id,
        memory_type=memory_type,
        sharing_policy=v2_sharing_policy(agent, event),
        **fields,
    )
    metadata.update(getattr(agent, "extra_metadata", None) or {})
    metadata[FIELD_PROVENANCE_EVENT] = event["event_id"]
    return metadata


def _unwrap(reply: Any) -> Any:
    """A reply without the kernel's ``{"response": ...}`` envelope; the
    library's and native calls return their value directly."""
    if isinstance(reply, dict) and "response" in reply:
        return reply["response"]
    return reply


def reply_error(reply: Any) -> Optional[str]:
    """Why a create, list or delete reply is a writer error, or ``None``
    when it is not (BENCHMARK_V2.md, "Failures"): no reply, ``False``
    (a library or native delete that found no row of the agent's),
    ``success`` false, or an error that says "Memory not found"."""
    response = _unwrap(reply)
    if response is None:
        return "no reply"
    if response is False:
        return f"{MEMORY_NOT_FOUND} (or not the agent's)"
    if isinstance(response, dict):
        error = response.get("error")
        if response.get("success") is False:
            return str(error) if error else "success is false"
        if error and MEMORY_NOT_FOUND in str(error):
            return str(error)
    return None


def _checked(operation: str, reply: Any) -> Any:
    """The unwrapped reply; raises ``WriterError`` for an error reply."""
    problem = reply_error(reply)
    if problem is not None:
        raise WriterError(f"{operation}: {problem}")
    return _unwrap(reply)


def reply_ids(reply: Any) -> List[str]:
    """The ids a create reply names: the kernel's ``memory_id`` (``""``
    when the backend's extraction kept nothing: no row), the library's
    id, or native's list of ids."""
    response = _checked("create", reply)
    if isinstance(response, dict):
        response = response.get("memory_id")
    if response is None or isinstance(response, str):
        return [response] if response else []
    if isinstance(response, (list, tuple)):
        return [str(memory_id) for memory_id in response if memory_id]
    raise WriterError(
        f"create: unexpected reply {type(response).__name__}"
    )


def write_outcome(reply: Any) -> Dict[str, Any]:
    """What a write did after storing (Amendment 4): the ids it
    ``swept`` (rows of any agent that carried a forgotten value), the
    ids it ``retired`` (earlier statements of its slot), the values it
    ``lifted`` (a restatement) and whether it was ``suppressed`` (its
    own rows carried a forgotten value). From the kernel's reply
    ``metadata`` or the library's outcome; empty for a reply without
    one (native, or a kernel before Amendment 4)."""
    response = _unwrap(reply)
    if isinstance(response, dict):
        outcome = response.get("metadata")
        if isinstance(outcome, dict) and "suppressed" in outcome:
            return outcome
    return {}


def forget_report(reply: Any) -> Dict[str, Any]:
    """The report of a forget reply: the kernel's reply ``metadata``,
    or the library's report itself. Raises ``WriterError`` for an error
    reply or one without a report."""
    response = _checked("forget", reply)
    if isinstance(response, dict) and "deleted" not in response:
        response = response.get("metadata")
    if not isinstance(response, dict) or not isinstance(
        response.get("deleted"), list
    ):
        raise WriterError("forget: the reply holds no report")
    return response


def listed_rows(reply: Any) -> List[Dict[str, Any]]:
    """The rows of a listing reply as ``{memory_id, content, metadata}``:
    the kernel's ``search_results``, or the library's or native list.
    Raises ``WriterError`` for an error reply or one without rows."""
    response = _checked("list", reply)
    if isinstance(response, dict):
        response = response.get("search_results")
    if not isinstance(response, list):
        raise WriterError("list: the reply holds no rows")
    return [
        {
            "memory_id": row.get("memory_id"),
            "content": row.get("content", ""),
            "metadata": dict(row.get("metadata") or {}),
        }
        for row in response
    ]


def require_user_id(user_id: Any) -> str:
    """``user_id`` if it names a user; raises ``WriterError``
    otherwise (a v2 call never falls back to the agent's own scope)."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise WriterError(f"no user_id: {user_id!r}")
    return user_id


def v2_failure(
    agent: Any, error: str, session: Optional[int] = None,
) -> Dict[str, Any]:
    """The result of a v2 writer turn that ran no event: the session
    result's keys, ``writer_failed`` and the reason."""
    _logger.warning("%s: v2 writer failed: %s",
                    getattr(agent, "agent_name", ""), error)
    return {
        "agent_name": getattr(agent, "agent_name", ""),
        "result": f"Writer failed: {error}",
        "session": session,
        "user_id": getattr(agent, "user_id", None),
        "events": [],
        "stored_rows": 0,
        "deleted_ids": [],
        "written": [],
        "writer_failed": True,
        "error": error,
        "token_usage": None,
    }


def _session_problem(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return "the session is not an object"
    session = payload.get("session")
    if not isinstance(session, int) or isinstance(session, bool):
        return f"session must be an integer, got {session!r}"
    events = payload.get("events")
    if not isinstance(events, list) or not all(
        isinstance(event, dict) for event in events
    ):
        return "events must be a list of objects"
    return None


def _event_problem(event: Dict[str, Any]) -> Optional[str]:
    kind = event.get("type")
    if kind not in V2_EVENT_TYPES:
        return f"unknown event type {kind!r}"
    for key in ("event_id", FIELD_FACT_KEY):
        if not isinstance(event.get(key), str) or not event[key]:
            return f"no {key}"
    utterance = event.get("utterance")
    if kind in V2_WRITE_EVENTS and not (
        isinstance(utterance, str) and utterance.strip()
    ):
        return "no utterance"
    return None


def _event_record(event: Dict[str, Any]) -> Dict[str, Any]:
    record = {
        "event_id": event.get("event_id"),
        "type": event.get("type"),
        "fact_key": event.get(FIELD_FACT_KEY),
        "memory_ids": [],
        "stored_rows": 0,
        "deleted_ids": [],
        "found_ids": [],
        "error": None,
    }
    if event.get("type") == V2_REVOKE:
        record.update({"revoke_path": None, "forget": None})
    else:
        record.update({
            "swept_ids": [], "retired_ids": [], "lifted": [],
            "suppressed": False,
        })
    return record


def _describe(error: Exception) -> str:
    if isinstance(error, WriterError):
        return str(error)
    return f"{type(error).__name__}: {error}"


def run_v2_session(
    agent: Any,
    payload: Any,
    memory_type: str,
    *,
    write: Callable[[str, Dict[str, Any]], Any],
    list_rows: Callable[[str], Any],
    delete: Callable[[str, str], Any],
    forget: Optional[Callable[[str, str], Any]] = None,
) -> Dict[str, Any]:
    """Run one benchmark v2 session (``parse_v2_session``) for
    ``agent``, a writer of ``memory_type``, through its locus's calls:

    - ``write(content, metadata)`` stores one row; its reply names the
      ids stored (the kernel's ``create_memory`` reply, the library's id,
      native's list of ids). A locus that stores other metadata than it
      was given (its defaults, a variant's changes) leaves what it
      stored in ``metadata``: the replicated and native writes do; a
      kernel create leaves it as sent, and the harness records the
      kernel's writes from its create capture instead;
    - ``list_rows(user_id)`` lists the agent's own rows for the user;
    - ``delete(user_id, memory_id)`` deletes one of them.

    - ``forget(user_id, fact_key)``, when the locus has one (kernel and
      replicated, Amendment 4), forgets a fact for the user.

    A write event (base, add, update, contradict or private; an echo is
    an add) stores its utterance with ``v2_write_metadata``, and its
    record keeps what the write did next (``write_outcome``: the ids it
    swept and retired, the values it lifted, ``suppressed``).

    A revoke goes through ``forget`` when the locus gives one and
    ``agent.forget_scope`` is ``"user"`` (the default): the user's
    forget deletes every row of the slot and every row, of any agent,
    that carries the fact's values, and the record keeps its report
    (``revoke_path`` ``"forget"``; ``found_ids`` are the slot's rows,
    ``deleted_ids`` every row deleted). Otherwise (native, or
    ``forget_scope`` ``"writer"``, the ``writer_scoped`` control) it
    lists the agent's own rows and deletes every one whose
    ``metadata.fact_key`` is the event's (``revoke_path`` ``"owner"``):
    Mem0 copies a write's metadata onto every fact it extracts, so this
    reaches a write's sibling facts. With ``agent.delete_on_revoke``
    False (the ``no_delete`` control) the revoke lists the agent's own
    rows, records the ones it found and deletes nothing.

    A reply that is an error (``reply_error``), a listing that returned
    its limit, a malformed event, or any exception fails the writer: the
    event records the error and the session stops there.

    Returns ``{agent_name, result, session, user_id`` (the id the writer
    used, which a V2 variant rewrites), ``events`` (one record per event
    run: ``event_id, type, fact_key, memory_ids, stored_rows,
    deleted_ids, found_ids, error``, and a revoke's ``revoke_path`` and
    ``forget`` report or a write's ``swept_ids, retired_ids, lifted,
    suppressed``), ``stored_rows`` (rows written),
    ``deleted_ids``, ``written`` (the metadata of each write that
    succeeded, as ``write`` left it: in the replicated and native loci
    what the row was stored with, for a kernel create the metadata as
    sent, since the harness records kernel writes from its create
    capture; a failed write is not in it), ``writer_failed, error,
    token_usage}`` (None: no LLM call).
    """
    problem = _session_problem(payload)
    if problem is not None:
        return v2_failure(agent, f"malformed v2 session: {problem}")
    session, events = payload["session"], payload["events"]
    try:
        user_id = require_user_id(getattr(agent, "user_id", None))
    except WriterError as e:
        return v2_failure(agent, str(e), session)
    deletes = getattr(agent, "delete_on_revoke", True) is not False
    scope = getattr(agent, "forget_scope", "user")
    if scope not in FORGET_SCOPES:
        return v2_failure(
            agent, f"forget_scope must be one of {FORGET_SCOPES}, "
            f"got {scope!r}", session,
        )
    forgets = deletes and forget is not None and scope == "user"
    records: List[Dict[str, Any]] = []
    written: List[Dict[str, Any]] = []
    error: Optional[str] = None
    for event in events:
        record = _event_record(event)
        records.append(record)
        try:
            problem = _event_problem(event)
            if problem is not None:
                raise WriterError(
                    f"event {event.get('event_id')!r}: {problem}"
                )
            if event["type"] == V2_REVOKE and forgets:
                report = forget_report(
                    forget(user_id, event[FIELD_FACT_KEY])
                )
                record["revoke_path"] = REVOKE_FORGET
                record["forget"] = {
                    key: report.get(key) for key in (
                        "deleted", "values_count", "forms_count",
                        "scrubbed", "listed", "not_found",
                    )
                }
                record["found_ids"] = [
                    entry["memory_id"] for entry in report["deleted"]
                    if entry.get("reason") == "fact_key"
                ]
                record["deleted_ids"] = [
                    entry["memory_id"] for entry in report["deleted"]
                ]
            elif event["type"] == V2_REVOKE:
                record["revoke_path"] = REVOKE_OWNER
                rows = listed_rows(list_rows(user_id))
                if len(rows) >= V2_LIST_LIMIT:
                    raise WriterError(
                        f"list: returned its limit of {V2_LIST_LIMIT} "
                        "rows, so some may be missing"
                    )
                record["found_ids"] = [
                    row["memory_id"] for row in rows
                    if row["metadata"].get(FIELD_FACT_KEY)
                    == event[FIELD_FACT_KEY]
                ]
                if deletes:
                    for memory_id in record["found_ids"]:
                        _checked("delete", delete(user_id, memory_id))
                        record["deleted_ids"].append(memory_id)
            else:
                metadata = v2_write_metadata(
                    agent, memory_type, session, event
                )
                reply = write(event["utterance"], metadata)
                ids = reply_ids(reply)
                # Only now, so a failed write is never recorded as
                # written; by now a replicated or native locus has left
                # in ``metadata`` what it stored (Amendment 2, "Stored
                # metadata"); a kernel create leaves it as sent.
                written.append(metadata)
                record["memory_ids"] = ids
                record["stored_rows"] = len(ids)
                outcome = write_outcome(reply)
                record["swept_ids"] = [
                    entry["memory_id"] if isinstance(entry, dict)
                    else str(entry)
                    for entry in outcome.get("swept") or []
                ]
                record["retired_ids"] = list(outcome.get("retired") or [])
                record["lifted"] = list(outcome.get("lifted") or [])
                record["suppressed"] = bool(outcome.get("suppressed"))
        except Exception as e:  # every failure fails the writer
            record["error"] = error = _describe(e)
            _logger.warning(
                "%s: v2 session %s stopped at event %s: %s",
                getattr(agent, "agent_name", ""), session,
                event.get("event_id"), error,
            )
            break
    return {
        "agent_name": getattr(agent, "agent_name", ""),
        "result": f"v2 session {session}: {len(events)} events",
        "session": session,
        "user_id": user_id,
        "events": records,
        "stored_rows": sum(r["stored_rows"] for r in records),
        "deleted_ids": [i for r in records for i in r["deleted_ids"]],
        "written": written,
        "writer_failed": error is not None,
        "error": error,
        "token_usage": None,
    }
