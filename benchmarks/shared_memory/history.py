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

logger = logging.getLogger(__name__)

WRITERS = ("profile_agent", "task_agent", "calendar_agent")
CONSUMER = "assistant_agent"
AGENTS = WRITERS + (CONSUMER,)
PROBE_SESSION = 7
LIST_LIMIT = 10_000
CONTROLS = ("no_memory", "no_delete", "no_visibility")
WRITE_EVENTS = ("base", "add", "update", "contradict", "private")


def provenance(agent_name: str, user_id: str) -> Dict[str, str]:
    """The harness's provenance on every write (as in v1)."""
    return {"provenance_agent": agent_name, "provenance_user": user_id}


@dataclass
class ProbeTurn:
    """One probe as it ran: the dataset probe, the consumer's raw
    result, its answer and injection diagnostics, the rows the
    consumer owned before it, and any error."""

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
        create is recorded as it is sent (after any variant)."""
        from cerebrum.example.agents.calendar_agent import (
            agent as calendar_module,
        )
        from cerebrum.example.agents.profile_agent import (
            agent as profile_module,
        )
        from cerebrum.example.agents.task_agent import agent as task_module

        stack = ExitStack()
        for module in (profile_module, task_module, calendar_module):
            real = module.create_memory

            def capturing(agent_name, content=None, metadata=None,
                          base_url=None, _real=real, **kwargs):
                if metadata:
                    written.append(WrittenMemoryRecord(
                        agent_name=metadata.get("owner_agent", agent_name),
                        memory_type=metadata.get("memory_type", ""),
                        sharing_policy=metadata.get("sharing_policy",
                                                    "private"),
                        user_id=metadata.get("user_id", ""),
                    ))
                return _real(agent_name, content=content, metadata=metadata,
                             base_url=base_url, **kwargs)
            stack.enter_context(patch.object(module, "create_memory",
                                             capturing))
        return stack

    def backend_usage(self, turns: List[ProbeTurn]) -> tuple:
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

    def backend_usage(self, turns: List[ProbeTurn]) -> tuple:
        """The backend's LLM and embedding usage, summed over the
        probes: each assistant run takes everything tagged with the user
        since the last take, the history's writes included."""
        llm, embedding = TokenUsage(), TokenUsage()
        for turn in turns:
            usage = (turn.result or {}).get("backend_usage") or {}
            for total, key in ((llm, "backend_llm_tokens"),
                               (embedding, "embedding_tokens")):
                part = usage.get(key) or {}
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


def _answer_error(result: Any) -> Optional[str]:
    """Why a consumer reply is not an answer (an error must never pass
    a hard constraint), or None."""
    if not isinstance(result, dict):
        return "consumer returned no result"
    answer = result.get("result")
    if result.get("error"):
        return f"consumer error: {result['error']}"
    if not isinstance(answer, str) or not answer.strip():
        return "consumer returned an empty answer"
    if answer.startswith("Error:"):
        return f"consumer error: {answer[:200]}"
    return None


def run_history(user: V2UserData, locus, runner, *,
                control: Optional[str] = None,
                recency_session: bool = True) -> HistoryOutcome:
    """Run ``user``'s sessions and probes through ``locus``.

    ``runner`` is the trial's ``VariantRunner`` (``runner.run(name,
    agent, task_input)``). Any failure the spec lists stops the history
    and sets ``failure``; the outcome keeps what ran.
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
    finally:
        outcome.variants_applied = dict(runner.codes)
        outcome.variants_not_applied = dict(runner.not_applied)
        locus.finish_user()
    if outcome.failure is None:
        outcome.backend_llm_tokens, outcome.embedding_tokens = (
            locus.backend_usage(outcome.turns))
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


def _sessions(user, locus, runner, outcome, ids) -> None:
    for session in user.sessions:
        name = session["writer"]
        payload = json.dumps({"v2_session": {
            "session": session["session"],
            "events": _with_base_fields(user, session["events"])}})
        result = runner.run(name, locus.writer(name), payload)
        if result.get("user_id"):
            ids[name].add(result["user_id"])
        if locus.writes_from_results:
            _writes_of(result, outcome.written)
        record = SessionRecord(
            session=session["session"], writer=name,
            user_id=result.get("user_id"),
            events=result.get("events") or [],
            stored_rows=result.get("stored_rows") or 0,
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
        outcome.listings.append(listing)


def _probes(user, locus, runner, outcome, ids, recency_session) -> None:
    for probe in user.probes:
        before = len(outcome.listings[-1]["rows"][CONSUMER])
        if outcome.turns:  # the consumer's rows as this probe starts
            before = len(_consumer_rows(locus, ids))
        agent = locus.consumer(user.user_id, probe["probe_id"])
        started = time.perf_counter()
        result = runner.run(CONSUMER, agent, probe["question"])
        turn = ProbeTurn(
            probe=probe, result=result if isinstance(result, dict) else {},
            answer=(result or {}).get("result") or ""
            if isinstance(result, dict) else "",
            diagnostics=(result or {}).get("injection_diagnostics")
            if isinstance(result, dict) else None,
            latency_seconds=time.perf_counter() - started,
            consumer_rows_before=before,
        )
        turn.error = _answer_error(result)
        outcome.turns.append(turn)
        if turn.error:
            raise LocusFailure(f"{probe['probe_id']}: {turn.error}")
        resolved = (turn.diagnostics or {}).get("resolved_user_id")
        if resolved:
            ids[CONSUMER].add(resolved)
        if recency_session:
            problem = _session_problem(turn.diagnostics)
            if problem:
                raise LocusFailure(f"{probe['probe_id']}: {problem}")


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
    judge-free fields (judge scores are added by the caller)."""
    from benchmarks.shared_memory.models import ProbeResult
    from benchmarks.shared_memory.pipeline import AgentPipeline
    from benchmarks.shared_memory.probes import score_probe

    reader = AgentPipeline(share_memory=True)
    values = user_values(user)
    deleted = deleted_ids(outcome)
    out = []
    for turn in outcome.turns:
        probe = turn.probe
        native = locus == "native"
        visible = visible_rows(user, outcome, turn) if native else None
        score = score_probe(
            probe, turn.answer, turn.diagnostics, user_values=values,
            deleted_ids=deleted, embed=embed, locus=locus,
            visible_stored_rows=visible, k=k,
        )
        fields = {key: value for key, value in score.items()
                  if key in ProbeResult.model_fields}
        diagnostics = reader._extract_injection_diagnostics(
            {"injection_diagnostics": turn.diagnostics})
        out.append(ProbeResult(
            **fields,
            slot=probe.get("slot"),
            question=probe["question"],
            expected=probe.get("expected") or [],
            forbidden=probe.get("forbidden") or [],
            target_event=probe.get("target_event"),
            target_writer=probe.get("target_writer"),
            target_session=probe.get("target_session"),
            echo_event=probe.get("echo_event"),
            observed=turn.answer,
            error=turn.error,
            visible_stored_rows=visible,
            diagnostics=diagnostics,
            token_usage=(turn.result or {}).get("token_usage"),
            latency_seconds=turn.latency_seconds,
        ))
    return out
