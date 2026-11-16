"""The stress dimensions' judge-free measures (NeurIPS Subtask 18, AIOS
docs/STRESS_DIMENSIONS.md): what a trial's records say about timing,
identity and flooding. Computed after the trial from the writers'
event records (each write's ``issued_at``, ``completed_at`` and, in the
kernel and replicated loci, the store's ``committed_at`` and the
kernel's ``barrier_seq``), the probes' diagnostics (``fetch_started_at``,
``barrier_snapshot``, the barrier waits and stage times), the listings
and the injected rows. ``measures`` returns a JSON-ready dict for
``TrialResult.stress``.
"""
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

WRITE_EVENTS = ("base", "add", "update", "contradict", "private")
REVOKE = "revoke"
TIMING_KEYS = ("barrier_wait_ms", "search_ms", "select_ms", "format_ms",
               "schedule_wait_ms", "kernel_overhead_ms", "llm_ms")


def _diag(result) -> Dict[str, Any]:
    diagnostics = getattr(result, "diagnostics", None)
    if diagnostics is None:
        return {}
    if hasattr(diagnostics, "model_dump"):
        return diagnostics.model_dump()
    return dict(diagnostics)


def write_records(outcome) -> List[Dict[str, Any]]:
    """Every event the writers ran, with its writer and session: one
    entry per write or revoke, in session order."""
    out = []
    for record in outcome.sessions:
        for event in record.events or []:
            out.append(dict(event, writer=record.writer,
                            session=record.session))
    return out


def _committed(event: Dict[str, Any]) -> Optional[float]:
    """When the store committed the event: its own commit time (kernel,
    replicated), else the time its call returned (an upper bound)."""
    return event.get("committed_at") or event.get("completed_at")


def probe_timing(result, turn, events: List[Dict[str, Any]],
                 user_events: Dict[str, dict],
                 locus: Optional[str] = None) -> Dict[str, Any]:
    """One probe's timing measures (STRESS_DIMENSIONS.md, Concurrency,
    "What is measured"). ``uncovered_writes`` is the kernel's only: its
    writes and reads share one barrier, whose sequences compare; a
    replicated agent's sequence is its own barrier's."""
    diagnostics = _diag(result)
    issued = getattr(turn, "issued_at", None)
    fetch = diagnostics.get("fetch_started_at")
    snapshot = diagnostics.get("barrier_snapshot")
    before = [e for e in events
              if issued is not None and e.get("issued_at") is not None
              and e["issued_at"] <= issued]
    in_flight = [e["event_id"] for e in before
                 if (e.get("completed_at") or float("inf")) > issued]
    late = []
    if fetch is not None:
        late = [e for e in before
                if (_committed(e) or float("inf")) > fetch]
    late_ids = [e["event_id"] for e in late]
    shared_late = [e for e in late
                   if (user_events.get(e["event_id"]) or {}).get("sharing")
                   != "private"]
    uncovered = []
    if snapshot is not None and locus == "kernel":
        uncovered = [e["event_id"] for e in before
                     if e.get("barrier_seq")
                     and e["barrier_seq"] > snapshot]
    target = getattr(result, "target_event", None)
    kind = getattr(result, "type", None)
    stale_read = None
    timing_miss = None
    late_forget = None
    if kind in ("recency", "contradiction") and target:
        stale_read = (target in late_ids
                      and bool(getattr(result, "stale_in_block", False)))
    if kind in ("recall", "recency", "contradiction") and target:
        timing_miss = (target in late_ids
                       and not getattr(result, "expected_in_block", None))
    if kind == "deletion" and target:
        fact_key = (user_events.get(target) or {}).get("fact_key")
        revokes = [e["event_id"] for e in late if e.get("type") == REVOKE
                   and e.get("fact_key") == fact_key]
        late_forget = bool(revokes) and bool(
            getattr(result, "forbidden_in_block", False))
    waits = diagnostics.get("barrier_waits") or []
    return {
        "issued_at": issued,
        "completed_at": getattr(turn, "completed_at", None),
        "latency_seconds": getattr(turn, "latency_seconds", None),
        "fetch_started_at": fetch,
        "barrier_snapshot": snapshot,
        "barrier_outcomes": [w.get("outcome") for w in waits],
        "writes_in_flight": in_flight,
        "late_writes": late_ids,
        "late_rows": sum(e.get("stored_rows") or 0 for e in shared_late),
        "uncovered_writes": uncovered,
        "timing_miss": timing_miss,
        "stale_read": stale_read,
        "late_forget": late_forget,
        **{key: diagnostics.get(key) for key in TIMING_KEYS},
    }


def flood_ids(outcome) -> set:
    """The ids of the rows flood writes left after the history (rows
    marked ``metadata.flood``)."""
    history = next((l for l in outcome.listings if l["after"] == "history"),
                   None)
    if history is None:
        return set()
    return {str(row.get("memory_id")) for rows in history["rows"].values()
            for row in rows
            if (row.get("metadata") or {}).get("flood") is not None}


def _injected_ids(result) -> List[str]:
    diagnostics = _diag(result)
    return [str(m.get("memory_id")) for m in
            diagnostics.get("injected_memories") or []
            if m.get("memory_id")]


def measures(user, outcome, results: Iterable, *,
             faulty_agent: Optional[str] = None,
             started_at: Optional[float] = None,
             finished_at: Optional[float] = None,
             locus: Optional[str] = None) -> Dict[str, Any]:
    """The trial's stress measures (``TrialResult.stress``)."""
    results = list(results)
    events = write_records(outcome)
    user_events = {e["event_id"]: e for turn in user.sessions
                   for e in turn["events"]}
    turns = {t.probe["probe_id"]: t for t in outcome.turns}
    probes = {}
    for result in results:
        turn = turns.get(result.probe_id)
        probes[result.probe_id] = probe_timing(result, turn, events,
                                               user_events, locus)
    floods = [f for record in outcome.sessions for f in record.flood or []]
    stored_flood = flood_ids(outcome)
    for result in results:
        probes[result.probe_id]["flood_rows_in_block"] = sum(
            1 for i in _injected_ids(result) if i in stored_flood)
    rejected = Counter()
    rejected_by_writer = Counter()
    overridden = 0
    for entry in events + [dict(f, writer=r.writer)
                           for r in outcome.sessions for f in r.flood or []]:
        if entry.get("quota_rejected"):
            rejected[entry["quota_rejected"]] += 1
            rejected_by_writer[entry["writer"]] += 1
        if entry.get("identity_overridden"):
            overridden += 1
    chat_overridden = sum(
        1 for result in results
        if _diag(result).get("identity_overridden"))
    integration = next((r for r in results if r.type == "integration"),
                       None)
    timing_missing = None
    if integration is not None:
        late = set(probes[integration.probe_id]["late_writes"])
        injected_events = {
            m.get("provenance_event") for m in
            _diag(integration).get("injected_memories") or []}
        writers = {e["writer"] for e in events
                   if e["event_id"] in late
                   and e.get("type") in WRITE_EVENTS}
        timing_missing = sorted(
            w for w in writers
            if not any(e["writer"] == w and e["event_id"] in injected_events
                       for e in events))
    outcomes = [o for p in probes.values() for o in p["barrier_outcomes"]]
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "faulty_agent": faulty_agent,
        "probes": probes,
        "memories_missing_timing": timing_missing,
        "barrier_timeouts": outcomes.count("TIMEOUT"),
        "barrier_drained": outcomes.count("DRAINED"),
        "identity_overridden_requests": overridden,
        "identity_overridden_chats": chat_overridden,
        "misfiled_rows": (None if outcome.misfiled_rows is None
                          else len(outcome.misfiled_rows)),
        "flood_rows_written": sum(1 for f in floods if f.get("memory_ids")),
        "flood_rows_sent": len(floods),
        "flood_rows_stored": len(stored_flood),
        "quota_rejected": dict(rejected),
        "quota_rejected_by_writer": dict(rejected_by_writer),
    }
