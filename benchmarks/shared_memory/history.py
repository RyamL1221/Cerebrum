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

The negative controls (``no_memory``, ``no_delete``, ``no_visibility``,
``writer_scoped``, ``no_supersession``) switch one property off so a
probe shows it can fail.

Since Amendment 2, any failure (a ``LocusFailure`` or any exception)
fails the user and keeps what ran. A probe whose diagnostics report a
failed retrieval or injection is a consumer error, and ``score_turns``
records a probe with an error unscored. Each write event's stored rows
and ids come from the listing after its session, by
``provenance_event``; a row that a forget or a sweep deleted later in
that session is not among them (the ids its reply named that the
session removed are the event's ``forgotten_ids``).
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
CONTROLS = ("no_memory", "no_delete", "no_visibility", "writer_scoped",
            "no_supersession")
# Controls of the library's deletion and supersession (Amendment 4):
# kernel and replicated only. writer_scoped makes the writers revoke by
# their own list and delete; no_supersession needs the kernel's
# memory.supersession off, which the replicated agents copy.
LIBRARY_CONTROLS = ("writer_scoped", "no_supersession")
WRITE_EVENTS = ("base", "add", "update", "contradict", "private")
# The events that state a fact's value (a base event states none).
STATEMENT_EVENTS = ("add", "update", "contradict", "private")
# The loci whose listings are the raw store (Amendment 4, "The audit
# reads the store"): their owner-only listings leave out a row that
# carries a forgotten value. Native's own listings have no guard.
STORE_AUDIT_LOCI = ("kernel", "replicated")
# Diagnostics keys that say a block cannot be trusted: the library's
# fetch failed, or the kernel's injector raised. Either looks like an
# empty store, which would pass deletion and privacy (Amendment 2).
BLOCK_ERRORS = (("retrieval_error", "retrieval failed"),
                ("injection_error", "injection failed"))


def forget_scope(control: Optional[str]) -> str:
    """A writer's ``forget_scope`` under ``control``: ``"writer"`` (its
    own list and delete) under ``writer_scoped``, else ``"user"`` (the
    user's forget, where the locus has one; Amendment 4)."""
    return "writer" if control == "writer_scoped" else "user"


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
    selects and formats, and writes the consumer's conversation when
    its ``auto_extract`` is on (never in v2, Amendment 3)."""

    locus = "kernel"
    # Creates are captured as they are sent (``capture``).
    writes_from_results = False

    def __init__(self, assistant_llms: Optional[list] = None,
                 kernel_config: Optional[dict] = None,
                 kernel_url: Optional[str] = None):
        self.assistant_llms = assistant_llms
        self.kernel_config = kernel_config or {}
        self.kernel_url = kernel_url
        self._writers: Dict[str, Any] = {}

    def audit_rows(self, user_id: str) -> List[dict]:
        """Every row the kernel's store holds for ``user_id``, of every
        agent, unfiltered (``GET /memory/audit``: no visibility rule, no
        tombstone guard; Amendment 4). A listing at its limit fails the
        user (it may be cut)."""
        import requests
        from cerebrum.config.config_manager import config

        url = (self.kernel_url or config.get_kernel_url()).rstrip("/")
        response = requests.get(f"{url}/memory/audit",
                                params={"user_id": user_id}, timeout=120)
        response.raise_for_status()
        body = response.json()
        if body.get("at_limit"):
            raise LocusFailure(f"listing_at_limit: audit of {user_id}")
        return _audit_rows(body.get("rows") or [])

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
            agent.forget_scope = forget_scope(control)
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
        if control in LIBRARY_CONTROLS and self.locus == "native":
            raise ValueError(
                f"{control} applies to the kernel and replicated loci "
                "only: native revokes by its owner and retires nothing")
        for name, agent in self.agents.items():
            agent.user_id = user_id
            agent.llms = self.assistant_llms
            agent.extra_metadata = provenance(name, user_id)
            if name in WRITERS:
                agent.share_memory = True
                agent.delete_on_revoke = control != "no_delete"
                agent.forget_scope = forget_scope(control)
        consumer = self.agents[CONSUMER]
        consumer.session, consumer.probe_id = None, None
        consumer.store_conversation = True
        if control == "no_visibility":
            if self.locus != "native":
                raise ValueError("no_visibility applies to the native locus"
                                 " only: the library enforces visibility")
            self._saved_visibility = consumer.check_visibility
            consumer.check_visibility = False

    def writer(self, name: str) -> Any:
        return self.agents[name]

    def consumer(self, user_id: str, probe_id: str) -> Any:
        """The consumer for one probe turn, which writes nothing
        (Amendment 3: ``store_conversation`` False)."""
        agent = self.agents[CONSUMER]
        agent.session = PROBE_SESSION
        agent.probe_id = probe_id
        agent.store_conversation = False
        return agent

    def lister(self, name: str) -> Any:
        return self.agents[name]

    def audit_rows(self, user_id: str) -> Optional[List[dict]]:
        """Replicated: every row the store holds for ``user_id``, of
        every agent, through the provider's own ``list`` (no visibility
        rule, no tombstone guard; Amendment 4). The agents share one
        store, so any agent's provider lists it. Native: None (its
        listings stay its own agents' backend calls, which have no
        guard)."""
        if self.locus != "replicated":
            return None
        provider = self.agents[CONSUMER].memory.provider
        found = provider.list(user_id, LIST_LIMIT)
        if len(found) >= LIST_LIMIT:
            raise LocusFailure(f"listing_at_limit: audit of {user_id}")
        return _audit_rows([candidate.to_row() for candidate in found])

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
        consumer.store_conversation = True
        if self._saved_visibility is not None:
            consumer.check_visibility = self._saved_visibility
            self._saved_visibility = None


# -- the history -------------------------------------------------------------

def _audit_rows(rows: List[dict]) -> List[dict]:
    """Listing rows as ``{memory_id, content, metadata}``."""
    return [{"memory_id": row.get("memory_id"),
             "content": row.get("content", ""),
             "metadata": dict(row.get("metadata") or {})}
            for row in rows]


def _listing(locus, after: str, ids: Dict[str, set]) -> Dict[str, Any]:
    """The rows each agent owns, under every user id the agents used. A
    listing that reaches the limit fails the user (it may be cut).

    Since Amendment 4 the kernel and replicated loci list the raw store
    (``audit_rows``): every row of each partition, of every agent, with
    no visibility rule and no tombstone guard, grouped by
    ``owner_agent``. The audits that read the listings
    (``revoked_value_rows``, ``reappeared_ids``, ``_probe_writes``,
    ``extraction_failure``, ``retired_rows``) therefore see a row the
    guard hides from the agents, text included. Native lists each
    agent's own rows through its backend, which has no guard
    (``source``: ``"store"`` or ``"owner"``)."""
    rows: Dict[str, List[dict]] = {name: [] for name in AGENTS}
    if getattr(locus, "locus", None) in STORE_AUDIT_LOCI:
        seen: set = set()
        for uid in sorted(set().union(*ids.values())):
            for row in locus.audit_rows(uid):
                memory_id = str(row.get("memory_id"))
                if memory_id in seen:
                    continue
                seen.add(memory_id)
                owner = (row.get("metadata") or {}).get("owner_agent", "")
                rows.setdefault(owner, []).append(row)
        return {"after": after, "rows": rows, "source": "store"}
    for name in AGENTS:
        seen_rows: Dict[str, dict] = {}
        for uid in sorted(ids[name]):
            listed = locus.lister(name).list_own_rows(uid)
            if len(listed) >= LIST_LIMIT:
                raise LocusFailure(
                    f"listing_at_limit: {name} after {after}")
            for row in listed:
                seen_rows.setdefault(str(row.get("memory_id")), row)
        rows[name] = list(seen_rows.values())
    return {"after": after, "rows": rows, "source": "owner"}


def _consumer_rows(locus, ids: Dict[str, set]) -> List[dict]:
    """The consumer's own rows, under each user id it used."""
    seen: Dict[str, dict] = {}
    for uid in sorted(ids[CONSUMER]):
        for row in locus.lister(CONSUMER).list_own_rows(uid):
            seen.setdefault(str(row.get("memory_id")), row)
    return list(seen.values())


def _probe_writes(history: Dict[str, Any],
                  probes: Dict[str, Any]) -> Dict[str, int]:
    """The rows each agent holds after the probes and did not before
    them, by agent (none when the probes stored nothing, as Amendment 3
    requires)."""
    stored = {}
    for name, rows in probes["rows"].items():
        before = {str(r.get("memory_id"))
                  for r in history["rows"].get(name, [])}
        new = [r for r in rows if str(r.get("memory_id")) not in before]
        if new:
            stored[name] = len(new)
    return stored


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
            stored = _probe_writes(*outcome.listings[-2:])
            if stored:
                agents = ", ".join(f"{n} {name}"
                                   for name, n in stored.items())
                raise LocusFailure(
                    f"probe_writes: probe turns stored "
                    f"{sum(stored.values())} rows ({agents})")
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
    to ``reported_ids``. Its ``memory_ids``, ``stored_rows`` and
    ``forgotten_ids`` are None until the listing after the session
    gives them (``_listed_rows``): the kernel's Mem0 add names only its
    first fact. The event's type is the script's (the record's own, for
    an event not in it)."""
    kinds = {event.get("event_id"): event.get("type") for event in events}
    out = []
    for record in records:
        record = dict(record)
        kind = kinds.get(record.get("event_id"), record.get("type"))
        if kind in WRITE_EVENTS:
            record["reported_ids"] = [
                str(i) for i in record.get("memory_ids") or []]
            record["memory_ids"] = record["stored_rows"] = None
            record["forgotten_ids"] = None
        out.append(record)
    return out


def _removed_in_session(record: SessionRecord) -> set:
    """The ids the session's own events removed: every row its revokes
    deleted (``deleted_ids``) and every row its writes swept."""
    removed = {str(i) for i in record.deleted_ids}
    for event in record.events:
        removed.update(str(i) for i in event.get("swept_ids") or [])
    return removed


def _listed_rows(record: SessionRecord, rows: List[dict]) -> None:
    """Fill each write event's ``memory_ids`` and ``stored_rows`` from
    ``rows``, the writer's rows in the listing after the session: those
    whose ``metadata.provenance_event`` is the event's id (Mem0 copies
    a write's metadata onto every fact it extracts). A row that a forget
    or a sweep deleted later in the session is in no listing: the
    event's ``forgotten_ids`` are the ids its reply named
    (``reported_ids``) that the session removed (Amendment 4: a Mem0
    fold of a value the session forgot). The session's ``stored_rows``
    is the listed rows' sum. A revoke's record is left as it is."""
    by_event: Dict[str, List[str]] = {}
    for row in rows:
        event = (row.get("metadata") or {}).get("provenance_event")
        if event is not None:
            by_event.setdefault(str(event), []).append(
                str(row.get("memory_id")))
    removed = _removed_in_session(record)
    stored = 0
    for event in record.events:
        if "reported_ids" not in event:  # not a write event
            continue
        found = by_event.get(str(event.get("event_id")), [])
        event["memory_ids"], event["stored_rows"] = found, len(found)
        event["forgotten_ids"] = [i for i in event["reported_ids"]
                                  if i in removed and i not in found]
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
    a write that stored nothing is a backend that failed silently. Two
    writes left no listed row and are no failure (Amendment 4): one the
    library suppressed (its rows carried a forgotten value and were
    swept), and one whose reply named rows that its own session then
    removed, every one (a forget took a Mem0 fold of the value it
    forgot, or a sweep). Any other write whose reply named no row (a
    suppressed write's names none) is never excused; neither is one
    whose named rows a later session removed, or one with a named row
    that nothing removed."""
    if backend_extraction is not True:
        return None
    after = {listing["after"]: listing for listing in outcome.listings}
    records: Dict[str, tuple] = {}
    for session in outcome.sessions:
        removed = _removed_in_session(session)
        for e in session.events:
            records[str(e.get("event_id"))] = (e, removed)
    empty = []
    for event in write_events(user):
        record, removed = records.get(event["event_id"], ({}, set()))
        if record.get("suppressed"):
            continue
        listing = after.get(f"session {event['session']}")
        if listing is None:
            continue
        rows = listing["rows"].get(event["writer"], [])
        if any((r.get("metadata") or {}).get("provenance_event")
               == event["event_id"] for r in rows):
            continue
        named = {str(i) for i in record.get("reported_ids") or []}
        if named and named <= removed:
            continue  # stored; its own session removed every row
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
    the listings after the history and after the probes: a value of any
    statement of the revoked slot (its add, updates, contradictions or
    private statement), or an alias, under the scorer's matcher. Since
    Amendment 4 the kernel and replicated listings are the raw store
    (``_listing``), so a carrier the tombstone guard hides from the
    agents still shows here, with its text."""
    revoked = [e for s in user.sessions for e in s["events"]
               if e["type"] == "revoke"]
    if not revoked:
        return []
    targets: Dict[str, List[dict]] = {}
    for s in user.sessions:
        for event in s["events"]:
            for r in revoked:
                if (event["type"] in STATEMENT_EVENTS
                        and event["fact_key"] == r["fact_key"]
                        and event.get("value")):
                    targets.setdefault(r["event_id"], []).append(event)
    out, seen = [], set()
    for listing in outcome.listings:
        if listing["after"] not in ("history", "probes"):
            continue
        for owner, rows in listing["rows"].items():
            for row in rows:
                for revoke_id, events in targets.items():
                    target = next((event for event in events
                                   if match_entry(row.get("content"),
                                                  event)), None)
                    if target is None:
                        continue
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
                        # The carrier's text, as the store holds it.
                        "content": row.get("content"),
                    })
    return out


def retired_events(user: V2UserData) -> List[str]:
    """The user's statements that a later statement of the same fact
    retires (Amendment 4), from the dataset's order: per ``fact_key``,
    every statement (add, update, contradict, private) but the last.
    The probes come after every session, so this holds for all of
    them."""
    by_fact: Dict[str, List[str]] = {}
    for s in sorted(user.sessions, key=lambda s: s["session"]):
        for event in s["events"]:
            if event["type"] in STATEMENT_EVENTS:
                by_fact.setdefault(event["fact_key"], []).append(
                    event["event_id"])
    return [event_id for events in by_fact.values()
            for event_id in events[:-1]]


def retired_rows(user: V2UserData,
                 outcome: HistoryOutcome) -> List[Dict[str, Any]]:
    """The rows of earlier statements (``retired_events``) in the
    listing after the history, of every agent, with the mark each
    carries (``superseded_by``, None when unmarked): with supersession
    on, every one should be marked (Amendment 4)."""
    retired = set(retired_events(user))
    history = next((listing for listing in outcome.listings
                    if listing["after"] == "history"), None)
    if not retired or history is None:
        return []
    out = []
    for owner, rows in history["rows"].items():
        for row in rows:
            metadata = row.get("metadata") or {}
            if str(metadata.get("provenance_event")) in retired:
                out.append({
                    "memory_id": str(row.get("memory_id")),
                    "owner_agent": owner,
                    "provenance_event": metadata.get("provenance_event"),
                    "fact_key": metadata.get("fact_key"),
                    "superseded_by": metadata.get("superseded_by"),
                })
    return out


def backend_invalidated_rows(
        outcome: HistoryOutcome) -> List[Dict[str, Any]]:
    """The rows in the listing after the history that the backend itself
    marked invalid: Graphiti's own supersession (``graphiti_invalid_at``
    or ``graphiti_expired_at``; Subtask 16, AIOS GRAPHITI_BACKEND.md),
    of every agent, with owner, event and slot. Recorded apart from the
    kernel's marks (``retired_rows``) and credited to no locus; empty
    for the other backends."""
    history = next((listing for listing in outcome.listings
                    if listing["after"] == "history"), None)
    if history is None:
        return []
    out = []
    for owner, rows in history["rows"].items():
        for row in rows:
            metadata = row.get("metadata") or {}
            if (metadata.get("graphiti_invalid_at")
                    or metadata.get("graphiti_expired_at")):
                out.append({
                    "memory_id": str(row.get("memory_id")),
                    "owner_agent": owner,
                    "provenance_event": metadata.get("provenance_event"),
                    "fact_key": metadata.get("fact_key"),
                    "invalid_at": metadata.get("graphiti_invalid_at"),
                    "expired_at": metadata.get("graphiti_expired_at"),
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
    """The rows the native consumer could see at a probe, by its own
    rules (``native/sharing.py``): the writers' rows after the history in
    the partition it searched (its ``resolved_user_id``; a V2 consumer's
    is rewritten), only the shared ones unless it reported not checking
    visibility (a V3 consumer, ``no_visibility``), plus its own rows when
    the probe began."""
    diagnostics = turn.diagnostics or {}
    partition = diagnostics.get("resolved_user_id") or user.user_id
    checks_visibility = diagnostics.get("visibility_checked") is not False
    history = next(l for l in outcome.listings if l["after"] == "history")
    writers = 0
    for name in WRITERS:
        for row in history["rows"].get(name, []):
            metadata = row.get("metadata") or {}
            if metadata.get("user_id") != partition:
                continue
            if (checks_visibility
                    and metadata.get("sharing_policy") != "shared"):
                continue
            writers += 1
    return writers + turn.consumer_rows_before


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
    retired = retired_events(user)
    invalidated = [row["memory_id"]
                   for row in backend_invalidated_rows(outcome)]
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
            visible_stored_rows=visible, k=k, retired_events=retired,
            invalidated_ids=invalidated,
        )
        fields = {key: value for key, value in score.items()
                  if key in ProbeResult.model_fields}
        out.append(ProbeResult(**{**fields, **recorded,
                                  "visible_stored_rows": visible}))
    return out
