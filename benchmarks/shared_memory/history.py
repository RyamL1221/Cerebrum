"""Benchmark v2's trial: one user's scripted history through a locus,
then the six probes (NeurIPS Subtask 14, AIOS docs/BENCHMARK_V2.md,
"Harness").

``run_history`` runs the user's sessions in order, each as one writer
turn (``writer.run`` on the session's events, under the trial's
variants), lists every agent's own rows after each session, then asks
the probes as consumer turns at session 7 and lists again. It returns
a ``HistoryOutcome`` with the raw probe turns; ``run_evaluation``
scores them and builds the trial result. A ``Locus`` gives the agents
and the listing calls of one condition:

- ``KernelLocus``: the kernel agents, fresh per user (a fresh assistant
  per probe, since its message list grows), every create captured;
- ``AgentManagedLocus``: the native or replicated agents, built once per
  cell like deployed agents and re-pointed at each user.

The negative controls (``no_memory``, ``no_delete``, ``no_visibility``)
switch one property off so a probe shows it can fail.

Since Amendment 2, any failure (a ``LocusFailure`` or any exception)
fails the user and keeps what ran. A probe whose diagnostics report a
failed retrieval or injection is a consumer error, and ``score_turns``
records a probe with an error unscored. Each write event's stored rows
and ids come from the listing after its session, by
``provenance_event``.
"""
import json
import logging
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
from unittest.mock import patch

from benchmarks.shared_memory.models import (
    SessionRecord,
    TokenUsage,
    V2UserData,
    WrittenMemoryRecord,
)
from benchmarks.shared_memory.probes import match_entry
from cerebrum.utils import usage

logger = logging.getLogger(__name__)

WRITERS = ("profile_agent", "task_agent", "calendar_agent")
CONSUMER = "assistant_agent"
AGENTS = WRITERS + (CONSUMER,)
PROBE_SESSION = 7
LIST_LIMIT = 10_000
CONTROLS = ("no_memory", "no_delete", "no_visibility")
WRITE_EVENTS = ("base", "add", "update", "contradict", "private")
# Diagnostics keys that say a block cannot be trusted: the library's
# fetch failed, or the kernel's injector raised. Either looks like an
# empty store, which would pass deletion and privacy (Amendment 2).
BLOCK_ERRORS = (("retrieval_error", "retrieval failed"),
                ("injection_error", "injection failed"))


def provenance(agent_name: str, user_id: str) -> Dict[str, str]:
    """The harness's provenance on every write (as in v1)."""
    return {"provenance_agent": agent_name, "provenance_user": user_id}


@dataclass
class ProbeTurn:
    """One probe as it ran: the dataset probe, the consumer's raw
    result, its answer and injection diagnostics, the rows the
    consumer owned before it, and any error (the reason the probe
    failed the user; ``score_turns`` does not score such a turn)."""

    probe: Dict[str, Any]
    result: Dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    diagnostics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_seconds: float = 0.0
    consumer_rows_before: int = 0


@dataclass
class HistoryOutcome:
    """What one user's history and probes produced, before scoring."""

    sessions: List[SessionRecord] = field(default_factory=list)
    turns: List[ProbeTurn] = field(default_factory=list)
    # [{"after": "session N" | "history" | "probes", "rows": {agent:
    # [rows]}}], in order.
    listings: List[Dict[str, Any]] = field(default_factory=list)
    written: List[WrittenMemoryRecord] = field(default_factory=list)
    failure: Optional[str] = None
    variants_applied: Dict[str, str] = field(default_factory=dict)
    variants_not_applied: Dict[str, str] = field(default_factory=dict)
    backend_extraction: Optional[bool] = None
    pipeline_version: Optional[str] = None
    # Agent-managed loci report their backend usage; the kernel's is
    # read from /memory/cost afterwards (None here).
    backend_llm_tokens: Optional[TokenUsage] = None
    embedding_tokens: Optional[TokenUsage] = None


class LocusFailure(RuntimeError):
    """A history that cannot go on: the user fails (the spec's
    "Failures")."""


# -- loci ------------------------------------------------------------------

class KernelLocus:
    """``kernel_shared``: the kernel agents over HTTP; the kernel stores,
    selects, formats and writes the consumer's conversation."""

    locus = "kernel"
    # Creates are captured as they are sent (``capture``).
    writes_from_results = False

    def __init__(self, assistant_llms: Optional[list] = None,
                 kernel_config: Optional[dict] = None):
        self.assistant_llms = assistant_llms
        self.kernel_config = kernel_config or {}
        self._writers: Dict[str, Any] = {}

    def start_user(self, user_id: str, control: Optional[str]) -> None:
        if control == "no_visibility":
            raise ValueError("no_visibility applies to the native locus only:"
                             " the kernel enforces visibility itself")
        from cerebrum.example.agents.calendar_agent.agent import (
            CalendarAgent,
        )
        from cerebrum.example.agents.profile_agent.agent import ProfileAgent
        from cerebrum.example.agents.task_agent.agent import TaskAgent

        self._writers = {}
        for name, cls in zip(WRITERS,
                             (ProfileAgent, TaskAgent, CalendarAgent)):
            agent = cls(name)
            agent.share_memory = True
            agent.user_id = user_id
            agent.llms = self.assistant_llms
            agent.extra_metadata = provenance(name, user_id)
            agent.delete_on_revoke = control != "no_delete"
            self._writers[name] = agent

    def writer(self, name: str) -> Any:
        return self._writers[name]

    def consumer(self, user_id: str, probe_id: str) -> Any:
        from cerebrum.example.agents.assistant_agent.agent import (
            AssistantAgent,
        )

        agent = AssistantAgent(CONSUMER)  # fresh: its messages grow
        agent.user_id = user_id
        agent.llms = self.assistant_llms
        agent.session = PROBE_SESSION
        agent.probe_id = probe_id
        return agent

    def lister(self, name: str) -> Any:
        if name == CONSUMER:
            return self.consumer(None, None)
        return self._writers[name]

    def capture(self, written: List[WrittenMemoryRecord]):
        """Patch every kernel agent module's ``create_memory`` so each
        create the kernel accepted is recorded with the metadata it was
        sent with (after any variant). A refused or raising create is
        not recorded, as in the agent-managed loci."""
        from cerebrum.example.agents.calendar_agent import (
            agent as calendar_module,
        )
        from cerebrum.example.agents.profile_agent import (
            agent as profile_module,
        )
        from cerebrum.example.agents.shared_memory_utils import reply_error
        from cerebrum.example.agents.task_agent import agent as task_module

        stack = ExitStack()
        for module in (profile_module, task_module, calendar_module):
            real = module.create_memory

            def capturing(agent_name, content=None, metadata=None,
                          base_url=None, _real=real, **kwargs):
                reply = _real(agent_name, content=content,
                              metadata=metadata, base_url=base_url,
                              **kwargs)
                if metadata and reply_error(reply) is None:
                    written.append(WrittenMemoryRecord(
                        agent_name=metadata.get("owner_agent", agent_name),
                        memory_type=metadata.get("memory_type", ""),
                        sharing_policy=metadata.get("sharing_policy",
                                                    "private"),
                        user_id=metadata.get("user_id", ""),
                    ))
                return reply
            stack.enter_context(patch.object(module, "create_memory",
                                             capturing))
        return stack

    def backend_usage(self, turns: List[ProbeTurn],
                      user_ids: Iterable[str] = ()) -> tuple:
        """None, None: the kernel's usage is read from ``/memory/cost``
        after the trial, under its canonical user ids."""
        return None, None

    def finish_user(self) -> None:
        self._writers = {}


class AgentManagedLocus:
    """``native_*`` / ``replicated_*``: each agent manages memory itself;
    the kernel serves the LLM calls only. The four agents live for the
    whole cell."""

    # The writers return what each write stored (no SDK to capture).
    writes_from_results = True

    def __init__(self, locus: str, agents: Dict[str, Any],
                 assistant_llms: Optional[list] = None):
        if locus not in ("native", "replicated"):
            raise ValueError(f"unknown agent-managed locus {locus!r}")
        self.locus = locus
        self.agents = agents
        self.assistant_llms = assistant_llms
        self._saved_visibility = None

    def start_user(self, user_id: str, control: Optional[str]) -> None:
        for name, agent in self.agents.items():
            agent.user_id = user_id
            agent.llms = self.assistant_llms
            agent.extra_metadata = provenance(name, user_id)
            if name in WRITERS:
                agent.share_memory = True
                agent.delete_on_revoke = control != "no_delete"
        consumer = self.agents[CONSUMER]
        consumer.session, consumer.probe_id = None, None
        if control == "no_visibility":
            if self.locus != "native":
                raise ValueError("no_visibility applies to the native locus"
                                 " only: the library enforces visibility")
            self._saved_visibility = consumer.check_visibility
            consumer.check_visibility = False

    def writer(self, name: str) -> Any:
        return self.agents[name]

    def consumer(self, user_id: str, probe_id: str) -> Any:
        agent = self.agents[CONSUMER]
        agent.session = PROBE_SESSION
        agent.probe_id = probe_id
        return agent

    def lister(self, name: str) -> Any:
        return self.agents[name]

    def capture(self, written: List[WrittenMemoryRecord]):
        return ExitStack()  # writes are recorded from the writers' results

    def backend_usage(self, turns: List[ProbeTurn],
                      user_ids: Iterable[str] = ()) -> tuple:
        """The backend's LLM and embedding usage over the trial. Each
        assistant run took everything tagged with its own user id since
        the last take, the history's writes included. Calls tagged with
        another id the trial used (``user_ids``, taken here, after the
        probes) are added: a V2 writer's rewritten id, or the writers'
        base id when a V2 consumer's was rewritten. A take removes what
        it returns, so no call is counted twice."""
        parts = [(turn.result or {}).get("backend_usage") or {}
                 for turn in turns]
        records: List[dict] = []
        for user_id in dict.fromkeys(user_ids):  # each id once, in order
            records += usage.ACCUMULATOR.take(user_id)
        if records:
            parts.append({
                "backend_llm_tokens": usage.summarize(
                    records, usage.BACKEND_EXTRACTION),
                "embedding_tokens": usage.summarize(
                    records, usage.EMBEDDING),
            })
        llm, embedding = TokenUsage(), TokenUsage()
        for part_usage in parts:
            for total, key in ((llm, "backend_llm_tokens"),
                               (embedding, "embedding_tokens")):
                part = part_usage.get(key) or {}
                total.calls += part.get("calls", 0) or 0
                total.prompt_tokens += part.get("prompt_tokens", 0) or 0
                total.completion_tokens += (
                    part.get("completion_tokens", 0) or 0)
                total.total_tokens += part.get("total_tokens", 0) or 0
                for model in part.get("models", []) or []:
                    if model not in total.models:
                        total.models.append(model)
        return llm, embedding

    def finish_user(self) -> None:
        consumer = self.agents[CONSUMER]
        consumer.session, consumer.probe_id = None, None
        if self._saved_visibility is not None:
            consumer.check_visibility = self._saved_visibility
            self._saved_visibility = None


# -- the history -------------------------------------------------------------

def _listing(locus, after: str, ids: Dict[str, set]) -> Dict[str, Any]:
    """Every agent's own rows, under each user id it used; a listing
    that reaches the limit fails the user (it may be cut)."""
    rows: Dict[str, List[dict]] = {}
    for name in AGENTS:
        seen: Dict[str, dict] = {}
        for uid in sorted(ids[name]):
            listed = locus.lister(name).list_own_rows(uid)
            if len(listed) >= LIST_LIMIT:
                raise LocusFailure(
                    f"listing_at_limit: {name} after {after}")
            for row in listed:
                seen.setdefault(str(row.get("memory_id")), row)
        rows[name] = list(seen.values())
    return {"after": after, "rows": rows}


def _consumer_rows(locus, ids: Dict[str, set]) -> List[dict]:
    """The consumer's own rows, under each user id it used."""
    seen: Dict[str, dict] = {}
    for uid in sorted(ids[CONSUMER]):
        for row in locus.lister(CONSUMER).list_own_rows(uid):
            seen.setdefault(str(row.get("memory_id")), row)
    return list(seen.values())


def _counts(listing: Dict[str, Any]) -> Dict[str, int]:
    return {name: len(rows) for name, rows in listing["rows"].items()}


def _writes_of(result: dict, written: List[WrittenMemoryRecord]) -> None:
    """Agent-managed writers return each write's metadata."""
    for metadata in result.get("written") or []:
        written.append(WrittenMemoryRecord(
            agent_name=metadata.get("owner_agent")
            or result.get("agent_name", ""),
            memory_type=metadata.get("memory_type", ""),
            sharing_policy=metadata.get("sharing_policy", ""),
            user_id=metadata.get("user_id", ""),
        ))


def _block_error(diagnostics: Any) -> Optional[str]:
    """Why the consumer's block cannot be trusted, from its injection
    diagnostics (a truthy ``retrieval_error`` or ``injection_error``),
    or None."""
    if not isinstance(diagnostics, dict):
        return None
    problems = [f"consumer {what}: {diagnostics[key]}"
                for key, what in BLOCK_ERRORS if diagnostics.get(key)]
    return "; ".join(problems) or None


def _answer_error(result: Any) -> Optional[str]:
    """Why a consumer reply is not an answer (an error must never pass
    a hard constraint), or None: no result, an error, a failed
    retrieval or injection (the block may lack rows the store holds),
    an empty answer or an "Error:" text."""
    if not isinstance(result, dict):
        return "consumer returned no result"
    answer = result.get("result")
    if result.get("error"):
        return f"consumer error: {result['error']}"
    failed = _block_error(result.get("injection_diagnostics"))
    if failed:
        return failed
    if not isinstance(answer, str) or not answer.strip():
        return "consumer returned an empty answer"
    if answer.startswith("Error:"):
        return f"consumer error: {answer[:200]}"
    return None


def _described(error: Exception) -> str:
    """An exception as a failure: ``"<ExceptionType>: <message>"``."""
    return f"{type(error).__name__}: {error}"


def run_history(user: V2UserData, locus, runner, *,
                control: Optional[str] = None,
                recency_session: bool = True) -> HistoryOutcome:
    """Run ``user``'s sessions and probes through ``locus``.

    ``runner`` is the trial's ``VariantRunner`` (``runner.run(name,
    agent, task_input)``). Any failure the spec lists, and any
    exception (a ``WriterError`` from a listing, a consumer that
    raises), stops the history and sets ``failure`` (an exception's as
    ``"<ExceptionType>: <message>"``); the outcome keeps what ran: the
    sessions, the probe turns and the listings.
    """
    if control is not None and control not in CONTROLS:
        raise ValueError(f"control must be one of {CONTROLS}")
    outcome = HistoryOutcome()
    uid = user.user_id
    ids = {name: {uid} for name in AGENTS}
    locus.start_user(uid, control)
    try:
        with locus.capture(outcome.written):
            if control != "no_memory":
                _sessions(user, locus, runner, outcome, ids)
            outcome.listings.append(_listing(locus, "history", ids))
            _probes(user, locus, runner, outcome, ids, recency_session)
            outcome.listings.append(_listing(locus, "probes", ids))
    except LocusFailure as failure:
        outcome.failure = str(failure)
    except Exception as error:  # every failure fails the user, not the run
        logger.warning("History of %s failed", uid, exc_info=True)
        outcome.failure = _described(error)
    finally:
        outcome.variants_applied = dict(runner.codes)
        outcome.variants_not_applied = dict(runner.not_applied)
        locus.finish_user()
    if outcome.failure is None:
        used = set().union(*ids.values())  # every id, every agent
        outcome.backend_llm_tokens, outcome.embedding_tokens = (
            locus.backend_usage(outcome.turns, sorted(used)))
    return outcome


def _with_base_fields(user: V2UserData, events: List[dict]) -> List[dict]:
    """The session's events, a base event with the fields it states
    (the base profile or task context), as a v1 writer received them;
    the dataset's events are not changed."""
    fields = {"base_profile": user.profile.model_dump(),
              "base_task": user.task_context.model_dump()}
    return [dict(e, fields=fields[e["fact_key"]])
            if e["type"] == "base" and e.get("fact_key") in fields else e
            for e in events]


def _reported(records: List[dict], events: List[dict]) -> List[dict]:
    """The writer's event records, each write event's reply ids moved
    to ``reported_ids``. Its ``memory_ids`` and ``stored_rows`` are None
    until the listing after the session gives them (``_listed_rows``):
    the kernel's Mem0 add names only its first fact. The event's type
    is the script's (the record's own, for an event not in it)."""
    kinds = {event.get("event_id"): event.get("type") for event in events}
    out = []
    for record in records:
        record = dict(record)
        kind = kinds.get(record.get("event_id"), record.get("type"))
        if kind in WRITE_EVENTS:
            record["reported_ids"] = [
                str(i) for i in record.get("memory_ids") or []]
            record["memory_ids"] = record["stored_rows"] = None
        out.append(record)
    return out


def _listed_rows(record: SessionRecord, rows: List[dict]) -> None:
    """Fill each write event's ``memory_ids`` and ``stored_rows`` from
    ``rows``, the writer's rows in the listing after the session: those
    whose ``metadata.provenance_event`` is the event's id (Mem0 copies
    a write's metadata onto every fact it extracts). The session's
    ``stored_rows`` is their sum. A revoke's record is left as it is."""
    by_event: Dict[str, List[str]] = {}
    for row in rows:
        event = (row.get("metadata") or {}).get("provenance_event")
        if event is not None:
            by_event.setdefault(str(event), []).append(
                str(row.get("memory_id")))
    stored = 0
    for event in record.events:
        if "reported_ids" not in event:  # not a write event
            continue
        found = by_event.get(str(event.get("event_id")), [])
        event["memory_ids"], event["stored_rows"] = found, len(found)
        stored += len(found)
    record.stored_rows = stored


def _sessions(user, locus, runner, outcome, ids) -> None:
    for session in user.sessions:
        name = session["writer"]
        payload = json.dumps({"v2_session": {
            "session": session["session"],
            "events": _with_base_fields(user, session["events"])}})
        try:
            result = runner.run(name, locus.writer(name), payload)
        except Exception as error:
            # A writer that raised: its session is recorded as failed,
            # then run_history fails the user with the exception.
            outcome.sessions.append(SessionRecord(
                session=session["session"], writer=name,
                writer_failed=True, error=_described(error)))
            raise
        if result.get("user_id"):
            ids[name].add(result["user_id"])
        if locus.writes_from_results:
            _writes_of(result, outcome.written)
        record = SessionRecord(
            session=session["session"], writer=name,
            user_id=result.get("user_id"),
            events=_reported(result.get("events") or [],
                             session["events"]),
            deleted_ids=[str(i) for i in result.get("deleted_ids") or []],
            writer_failed=bool(result.get("writer_failed")),
            error=result.get("error"),
        )
        outcome.sessions.append(record)
        if record.writer_failed:
            raise LocusFailure(
                f"writer_failed: {name} in session {record.session}: "
                f"{record.error}")
        listing = _listing(locus, f"session {record.session}", ids)
        record.listing_counts = _counts(listing)
        _listed_rows(record, listing["rows"].get(name, []))
        outcome.listings.append(listing)


def _answer_text(answer: Any) -> str:
    """A reply's answer as the record's text ("" for none)."""
    if answer is None:
        return ""
    return answer if isinstance(answer, str) else str(answer)


def _probes(user, locus, runner, outcome, ids, recency_session) -> None:
    for probe in user.probes:
        before = len(outcome.listings[-1]["rows"][CONSUMER])
        if outcome.turns:  # the consumer's rows as this probe starts
            before = len(_consumer_rows(locus, ids))
        agent = locus.consumer(user.user_id, probe["probe_id"])
        turn = ProbeTurn(probe=probe, consumer_rows_before=before)
        started = time.perf_counter()
        try:
            result = runner.run(CONSUMER, agent, probe["question"])
        except Exception as error:
            # A consumer that raised: the turn is recorded (unscored),
            # then run_history fails the user with the exception.
            turn.latency_seconds = time.perf_counter() - started
            turn.error = f"consumer raised {_described(error)}"
            outcome.turns.append(turn)
            raise
        turn.latency_seconds = time.perf_counter() - started
        if isinstance(result, dict):
            turn.result = result
            turn.answer = _answer_text(result.get("result"))
            diagnostics = result.get("injection_diagnostics")
            turn.diagnostics = (diagnostics if isinstance(diagnostics, dict)
                                else None)
        turn.error = _answer_error(result)
        if not turn.error:
            resolved = (turn.diagnostics or {}).get("resolved_user_id")
            if resolved:
                ids[CONSUMER].add(resolved)
            if recency_session:
                # Its block's ages are wrong, so it is not scored either.
                turn.error = _session_problem(turn.diagnostics)
        outcome.turns.append(turn)
        if turn.error:
            raise LocusFailure(f"{probe['probe_id']}: {turn.error}")


def _session_problem(diagnostics: Optional[dict]) -> Optional[str]:
    """In a v2 run with session ages, a block with rows must say it was
    built at session 7 in the session unit."""
    if not isinstance(diagnostics, dict):
        return "no injection diagnostics"
    if not diagnostics.get("injected_count"):
        return None  # an empty block has nothing to age
    if diagnostics.get("session") != PROBE_SESSION:
        return (f"block built at session {diagnostics.get('session')!r}, "
                f"not {PROBE_SESSION}")
    if diagnostics.get("block_recency_unit") != "session":
        return (f"block ages in {diagnostics.get('block_recency_unit')!r}, "
                "not sessions")
    return None


# -- what the history left behind -----------------------------------------

def write_events(user: V2UserData) -> List[dict]:
    """Every event that writes a row, with its session."""
    return [dict(event, session=s["session"], writer=s["writer"])
            for s in user.sessions for event in s["events"]
            if event["type"] in WRITE_EVENTS]


def extraction_failure(user: V2UserData, outcome: HistoryOutcome,
                       backend_extraction: Optional[bool]) -> Optional[str]:
    """With backend extraction, every write event must have left a row
    (counted in the listing after its session, by ``provenance_event``);
    a write that stored nothing is a backend that failed silently."""
    if backend_extraction is not True:
        return None
    after = {listing["after"]: listing for listing in outcome.listings}
    empty = []
    for event in write_events(user):
        listing = after.get(f"session {event['session']}")
        if listing is None:
            continue
        rows = listing["rows"].get(event["writer"], [])
        if not any((r.get("metadata") or {}).get("provenance_event")
                   == event["event_id"] for r in rows):
            empty.append(event["event_id"])
    if empty:
        return ("backend_extraction_failed: stored no rows: "
                + ", ".join(empty))
    return None


def deleted_ids(outcome: HistoryOutcome) -> List[str]:
    return [i for s in outcome.sessions for i in s.deleted_ids]


def reappeared_ids(outcome: HistoryOutcome) -> List[str]:
    """Deleted ids seen again in any later listing or in any probe's
    injected rows."""
    deleted, seen = [], []
    by_session = {s.session: s.deleted_ids for s in outcome.sessions}
    for listing in outcome.listings:
        after = listing["after"]
        if after.startswith("session "):
            # The listing right after a revoke must lack what it deleted.
            deleted += by_session.get(int(after.split()[1]), [])
        listed = {str(r.get("memory_id"))
                  for rows in listing["rows"].values() for r in rows}
        seen += [i for i in deleted if i in listed and i not in seen]
    for turn in outcome.turns:
        for row in (turn.diagnostics or {}).get("injected_memories") or []:
            mid = str(row.get("memory_id"))
            if mid in deleted and mid not in seen:
                seen.append(mid)
    return seen


def revoked_value_rows(user: V2UserData,
                       outcome: HistoryOutcome) -> List[Dict[str, Any]]:
    """Every row, of any agent, that still carries a revoked value in
    the listings after the history and after the probes."""
    revoked = [e for s in user.sessions for e in s["events"]
               if e["type"] == "revoke"]
    if not revoked:
        return []
    targets = {}
    for s in user.sessions:
        for event in s["events"]:
            for r in revoked:
                if (event["type"] in ("add", "private")
                        and event["fact_key"] == r["fact_key"]
                        and event.get("value")):
                    targets[r["event_id"]] = event
    out, seen = [], set()
    for listing in outcome.listings:
        if listing["after"] not in ("history", "probes"):
            continue
        for owner, rows in listing["rows"].items():
            for row in rows:
                for revoke_id, target in targets.items():
                    if match_entry(row.get("content"), target):
                        key = (listing["after"], str(row.get("memory_id")))
                        if key in seen:
                            continue
                        seen.add(key)
                        metadata = row.get("metadata") or {}
                        out.append({
                            "listing": listing["after"],
                            "memory_id": str(row.get("memory_id")),
                            "owner_agent": owner,
                            "provenance_event":
                                metadata.get("provenance_event"),
                            "fact_key": metadata.get("fact_key"),
                            "revoke_event": revoke_id,
                            "value": target["value"],
                        })
    return out


def user_values(user: V2UserData) -> List[Dict[str, Any]]:
    """Each fact's value with its aliases, event and slot (the scorer's
    ``user_values``)."""
    out = []
    for s in user.sessions:
        for event in s["events"]:
            if event.get("value"):
                out.append({"value": event["value"],
                            "aliases": list(event.get("aliases") or []),
                            "event_id": event["event_id"],
                            "slot": event.get("slot")})
    return out


def visible_rows(user: V2UserData, outcome: HistoryOutcome,
                 turn: ProbeTurn) -> int:
    """The rows the consumer could see at a probe: the writers' shared
    rows in its partition after the history, plus its own rows when the
    probe began."""
    history = next(l for l in outcome.listings if l["after"] == "history")
    shared = sum(
        1 for name in WRITERS for row in history["rows"].get(name, [])
        if (row.get("metadata") or {}).get("sharing_policy") == "shared"
        and (row.get("metadata") or {}).get("user_id") == user.user_id)
    return shared + turn.consumer_rows_before


def iter_turns(outcome: HistoryOutcome) -> Iterable[ProbeTurn]:
    return iter(outcome.turns)


# -- scoring -------------------------------------------------------------------

def score_turns(user: V2UserData, outcome: HistoryOutcome, locus: str,
                embed=None, k: int = 10) -> list:
    """Each probe turn as a ``ProbeResult``: the dataset's ground truth,
    the answer, the consumer's diagnostics and ``probes.score_probe``'s
    judge-free fields (judge scores are added by the caller).

    A turn with an error (it failed the user) is recorded but never
    scored: it keeps its probe's identity and ground truth, the answer,
    the diagnostics, tokens, latency and the error, and its ``passed``
    and every match and block field keep their defaults (None or
    empty), so an error cannot pass a hard constraint, even in a
    failed trial's record."""
    from benchmarks.shared_memory.models import ProbeResult
    from benchmarks.shared_memory.pipeline import AgentPipeline
    from benchmarks.shared_memory.probes import score_probe

    reader = AgentPipeline(share_memory=True)
    values = user_values(user)
    deleted = deleted_ids(outcome)
    out = []
    for turn in outcome.turns:
        probe = turn.probe
        recorded = {
            "probe_id": probe["probe_id"],
            "type": probe["type"],
            "slot": probe.get("slot"),
            "question": probe["question"],
            "expected": probe.get("expected") or [],
            "forbidden": probe.get("forbidden") or [],
            "target_event": probe.get("target_event"),
            "target_writer": probe.get("target_writer"),
            "target_session": probe.get("target_session"),
            "echo_event": probe.get("echo_event"),
            "observed": turn.answer,
            "error": turn.error,
            "diagnostics": reader._extract_injection_diagnostics(
                {"injection_diagnostics": turn.diagnostics}),
            "token_usage": (turn.result or {}).get("token_usage"),
            "latency_seconds": turn.latency_seconds,
        }
        if turn.error:
            out.append(ProbeResult(**recorded))
            continue
        native = locus == "native"
        visible = visible_rows(user, outcome, turn) if native else None
        score = score_probe(
            probe, turn.answer, turn.diagnostics, user_values=values,
            deleted_ids=deleted, embed=embed, locus=locus,
            visible_stored_rows=visible, k=k,
        )
        fields = {key: value for key, value in score.items()
                  if key in ProbeResult.model_fields}
        out.append(ProbeResult(**{**fields, **recorded,
                                  "visible_stored_rows": visible}))
    return out
