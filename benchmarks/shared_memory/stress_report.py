"""The stress dimensions' report (NeurIPS Subtask 18, AIOS
docs/STRESS_DIMENSIONS.md): reads a run of ``scripts/run_stress_s18.sh``
and tabulates, per dimension, level, locus and backend, the judge-free
measures, each trial paired with its reference (the same user in the
same cell type at the dimension's base level).

    python -m benchmarks.shared_memory.stress_report results/<run> \\
        --md results/<run>/analysis.md --json results/<run>/analysis.json

Conditions are the driver's: ``nNhH`` (agent count), ``n6conc``
(concurrency), ``n6<fault>`` and ``n6loadM``. The reference of
``nNh2`` is ``nNh0``; of ``n6conc`` and the faults, ``n6h0``.
"""
import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from benchmarks.shared_memory.bench_v2_analysis import CELLS
from benchmarks.shared_memory.probes import mcnemar_exact, t_interval, wilson

JUDGE_FREE = ("deletion", "privacy", "recall", "recency", "contradiction")
PHASE_BACKEND = {"kinh": "inhouse", "kinh_q": "inhouse",
                 "kmem0": "mem0", "kmem0_q": "mem0"}
FAULTS = ("wrong_user", "missing_metadata", "flood10", "flood50")
WRITE_EVENTS = ("base", "add", "update", "contradict", "private")
EMPTY_WRITE = "backend_extraction_failed"
STAGES = ("barrier_wait_ms", "search_ms", "select_ms", "format_ms",
          "schedule_wait_ms", "llm_ms")


def load(root: Path) -> Dict[tuple, dict]:
    """``{(model, locus, backend, condition): trials}`` for every
    results file under ``root`` (``model/phase/<condition>_<method>``)."""
    cells = {}
    for path in sorted(root.glob("*/*/*/results_*.json")):
        model, phase, cell = path.parts[-4], path.parts[-3], path.parts[-2]
        method = next((m for m in CELLS if cell.endswith("_" + m)), None)
        if method is None:
            continue
        condition = cell[:-len(method) - 1]
        locus, backend = CELLS[method] or ("kernel", PHASE_BACKEND[phase])
        data = json.loads(path.read_text())
        cells[(model, locus, backend, condition)] = \
            data["conditions"][0]["trials"]
    return cells


def _rate(flags: Iterable[Optional[bool]]) -> dict:
    flags = [f for f in flags if f is not None]
    n, k = len(flags), sum(1 for f in flags if f)
    if not n:
        return {"k": 0, "n": 0, "rate": None, "ci": None}
    low, high = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n, "ci": [low, high]}


def _probe(trial: dict, kind: str) -> Optional[dict]:
    return next((p for p in trial.get("probe_results") or []
                 if p["type"] == kind), None)


def _by_user(trials: List[dict]) -> Dict[int, dict]:
    return {t["trial_index"]: t for t in trials if not t.get("failed")}


def _block(probe: Optional[dict]) -> Optional[str]:
    return ((probe or {}).get("diagnostics") or {}).get("block_text")


def paired_outcomes(trials: List[dict], reference: List[dict],
                    kind: str) -> dict:
    """Users whose ``kind`` outcome changed from the reference: ``lost``
    (passed there, failed here), ``gained``, and the exact McNemar p."""
    here, there = _by_user(trials), _by_user(reference)
    lost = gained = same = 0
    for user in sorted(set(here) & set(there)):
        a = (_probe(there[user], kind) or {}).get("passed")
        b = (_probe(here[user], kind) or {}).get("passed")
        if a is None or b is None:
            continue
        if a and not b:
            lost += 1
        elif b and not a:
            gained += 1
        else:
            same += 1
    return {"lost": lost, "gained": gained, "same": same,
            "p": mcnemar_exact(lost, gained)}


def _paired_mean(trials: List[dict], reference: List[dict], value) -> dict:
    """The paired difference ``value(trial) - value(reference trial)``
    over the users both have it for: mean and 95% t interval."""
    here, there = _by_user(trials), _by_user(reference)
    diffs = []
    for user in sorted(set(here) & set(there)):
        a, b = value(there[user]), value(here[user])
        if a is not None and b is not None:
            diffs.append(b - a)
    if not diffs:
        return {"n": 0, "mean": None, "ci": None}
    low, high = t_interval(diffs)
    return {"n": len(diffs), "mean": statistics.mean(diffs),
            "ci": [low, high]}


def cross_user_rows(trial: dict) -> int:
    """Injected rows, over every probe, written for another user (a
    leak), by the row's ``provenance_user``."""
    count = 0
    for probe in trial.get("probe_results") or []:
        for row in (probe.get("diagnostics") or {}).get(
                "injected_memories") or []:
            owner = row.get("provenance_user")
            if owner and owner != trial.get("user_id"):
                count += 1
    return count


def writes_without_row(trial: dict) -> List[str]:
    """The trial's write events whose reply named no row: neither
    suppressed (a forgotten value) nor turned away by the write quota.
    On a backend that extracts, a write it stored nothing for (Mem0:
    "extracted no facts", known issue 32)."""
    out = []
    for record in trial.get("sessions") or []:
        for event in record.get("events") or []:
            if (event.get("type") in WRITE_EVENTS
                    and "reported_ids" in event
                    and not event.get("reported_ids")
                    and not event.get("suppressed")
                    and not event.get("quota_rejected")):
                out.append(event.get("event_id"))
    return out


def _judge_free(trial: dict, key: str):
    return (trial.get("judge_free") or {}).get(key)


def _stress(trial: dict) -> dict:
    return trial.get("stress") or {}


def probe_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Every cell's judge-free pass rates."""
    rows = []
    for (model, locus, backend, condition), trials in sorted(cells.items()):
        ok = [t for t in trials if not t.get("failed")]
        row = {"model": model, "locus": locus, "backend": backend,
               "condition": condition, "trials": len(trials),
               "failed": len(trials) - len(ok)}
        for kind in JUDGE_FREE:
            rate = _rate((_probe(t, kind) or {}).get("passed") for t in ok)
            row[kind] = rate
        # Over every trial, the failed included.
        row["writes_without_row"] = sum(len(writes_without_row(t))
                                        for t in trials)
        rows.append(row)
    return rows


def agent_count_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per locus and backend: at H = 0, whether every user's judge-free
    outcomes and blocks are the same at N = 3, 6 and 12; at H = 2, the
    outcomes that changed from the same N's H = 0."""
    rows = []
    keys = sorted({k[:3] for k in cells})
    for model, locus, backend in keys:
        h0 = {n: cells.get((model, locus, backend, f"n{n}h0"))
              for n in (3, 6, 12)}
        if all(h0.values()):
            users = set.intersection(*(set(_by_user(t)) for t in
                                       h0.values()))
            same_outcomes = same_blocks = probes = 0
            for user in users:
                for kind in JUDGE_FREE + ("integration",):
                    found = [_probe(_by_user(h0[n])[user], kind)
                             for n in (3, 6, 12)]
                    probes += 1
                    if len({(p or {}).get("passed") for p in found}) == 1:
                        same_outcomes += 1
                    if len({_block(p) for p in found}) == 1:
                        same_blocks += 1
            rows.append({"model": model, "locus": locus, "backend": backend,
                         "level": "H0 across N", "users": len(users),
                         "probes": probes, "same_outcomes": same_outcomes,
                         "same_blocks": same_blocks})
        for n in (3, 6, 12):
            here = cells.get((model, locus, backend, f"n{n}h2"))
            there = cells.get((model, locus, backend, f"n{n}h0"))
            if not (here and there):
                continue
            row = {"model": model, "locus": locus, "backend": backend,
                   "level": f"N{n} H2 vs H0"}
            for kind in JUDGE_FREE:
                row[kind] = paired_outcomes(here, there, kind)
            row["cross_user_rows"] = sum(cross_user_rows(t) for t in here)
            row["memories_missing"] = _paired_mean(
                here, there, lambda t: _judge_free(t, "memories_missing"))
            rows.append(row)
    return rows


def _probe_stress(trials: List[dict]) -> List[dict]:
    return [p for t in trials if not t.get("failed")
            for p in (_stress(t).get("probes") or {}).values()]


def concurrency_rows(cells: Dict[tuple, dict]) -> List[dict]:
    rows = []
    for (model, locus, backend, condition), trials in sorted(cells.items()):
        if condition != "n6conc":
            continue
        probes = _probe_stress(trials)
        waits = [p["barrier_wait_ms"] for p in probes
                 if p.get("barrier_wait_ms") is not None]
        reference = cells.get((model, locus, backend, "n6h0")) or []
        row = {
            "model": model, "locus": locus, "backend": backend,
            "probes": len(probes),
            "with_writes_in_flight": sum(1 for p in probes
                                         if p["writes_in_flight"]),
            "with_late_writes": sum(1 for p in probes if p["late_writes"]),
            "late_writes": sum(len(p["late_writes"]) for p in probes),
            # The late writes the probe's barrier covered: none in the
            # kernel (STRESS_DIMENSIONS.md, the checks that must hold).
            "late_covered": sum(len(p["late_covered"]) for p in probes),
            "late_rows": sum(p["late_rows"] for p in probes),
            "uncovered_writes": sum(len(p["uncovered_writes"])
                                    for p in probes),
            "timing_misses": sum(1 for p in probes if p.get("timing_miss")),
            "stale_reads": sum(1 for p in probes if p.get("stale_read")),
            "late_forgets": sum(1 for p in probes if p.get("late_forget")),
            "barrier_wait_ms_median": (statistics.median(waits)
                                       if waits else None),
            "barrier_wait_ms_max": max(waits) if waits else None,
            "barrier_timeouts": sum(_stress(t).get("barrier_timeouts") or 0
                                    for t in trials),
            "memories_missing_timing": sum(
                len(_stress(t).get("memories_missing_timing") or [])
                for t in trials if not t.get("failed")),
            # Every missing memory, paired with the same user's
            # sequential trial; the timing part is the count above.
            "memories_missing": _paired_mean(
                trials, reference,
                lambda t: _judge_free(t, "memories_missing")),
        }
        for kind in JUDGE_FREE:
            row[kind] = paired_outcomes(trials, reference, kind)
        rows.append(row)
    return rows


def _quantile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    values = sorted(values)
    position = q * (len(values) - 1)
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def load_rows(cells: Dict[tuple, dict]) -> List[dict]:
    rows = []
    for (model, locus, backend, condition), trials in sorted(cells.items()):
        if not condition.startswith("n6load"):
            continue
        ok = [t for t in trials if not t.get("failed")]
        starts = [_stress(t).get("started_at") for t in ok]
        ends = [_stress(t).get("finished_at") for t in ok]
        span = (max(ends) - min(starts)) if ok and None not in starts + ends \
            else None
        probes = _probe_stress(ok)
        latencies = [p["latency_seconds"] for p in probes
                     if p.get("latency_seconds") is not None]
        row = {"model": model, "locus": locus, "backend": backend,
               "load": int(condition[len("n6load"):]), "users": len(ok),
               "failed": len(trials) - len(ok),
               "users_per_minute": (60 * len(ok) / span) if span else None,
               "latency_p50_s": _quantile(latencies, 0.5),
               "latency_p95_s": _quantile(latencies, 0.95),
               "barrier_timeouts": sum(_stress(t).get("barrier_timeouts")
                                       or 0 for t in ok)}
        for stage in STAGES:
            values = [p[stage] for p in probes if p.get(stage) is not None]
            row[f"{stage}_median"] = (statistics.median(values)
                                      if values else None)
            row[f"{stage}_p95"] = _quantile(values, 0.95)
        tokens = [((p.get("token_usage") or {}).get("completion_tokens"))
                  for t in ok for p in t.get("probe_results") or []]
        llm = [p.get("llm_ms") for p in probes]
        pairs = [(ms, tok) for ms, tok in zip(llm, tokens) if ms and tok]
        row["ms_per_completion_token"] = (
            sum(ms for ms, _ in pairs) / sum(tok for _, tok in pairs)
            if pairs else None)
        rows.append(row)
    return rows


def fault_rows(cells: Dict[tuple, dict]) -> List[dict]:
    rows = []
    for (model, locus, backend, condition), trials in sorted(cells.items()):
        fault = condition[2:] if condition.startswith("n6") else None
        if fault not in FAULTS:
            continue
        ok = [t for t in trials if not t.get("failed")]
        reference = cells.get((model, locus, backend, "n6h0")) or []
        stress = [_stress(t) for t in ok]
        rejected = Counter()
        for entry in stress:
            rejected.update(entry.get("quota_rejected") or {})
        probes = _probe_stress(ok)
        row = {
            "model": model, "locus": locus, "backend": backend,
            "fault": fault, "users": len(ok), "failed": len(trials) - len(ok),
            "faulty_agents": dict(Counter(t.get("faulty_agent")
                                          for t in ok)),
            "misfiled_rows": sum(s.get("misfiled_rows") or 0
                                 for s in stress),
            "identity_overridden": sum(
                (s.get("identity_overridden_requests") or 0)
                + (s.get("identity_overridden_chats") or 0)
                for s in stress),
            "cross_user_rows": sum(cross_user_rows(t) for t in ok),
            "private_rows_from_others": sum(
                _judge_free(t, "private_rows_from_others") or 0 for t in ok),
            "flood_rows_stored": sum(s.get("flood_rows_stored") or 0
                                     for s in stress),
            "flood_writes_accepted": sum(s.get("flood_writes_accepted") or 0
                                         for s in stress),
            # Flooding turns whose accepted flood writes exceed the
            # quota's bound (None when a trial ran without the quota).
            "flood_sessions_over_bound": (
                None if any(s.get("flood_sessions_over_bound") is None
                            for s in stress)
                else sum(s["flood_sessions_over_bound"] for s in stress)),
            "flood_rows_in_block_per_probe": (
                statistics.mean(p.get("flood_rows_in_block") or 0
                                for p in probes) if probes else None),
            "quota_rejected": dict(rejected),
            "memories_missing": _paired_mean(
                ok, reference, lambda t: _judge_free(t, "memories_missing")),
            "profile_facts_in_block": _paired_mean(
                ok, reference,
                lambda t: _judge_free(t, "profile_facts_in_block")),
        }
        for kind in JUDGE_FREE:
            row[kind] = paired_outcomes(ok, reference, kind)
        rows.append(row)
    return rows


def _faulty_requests(trial: dict) -> int:
    """The requests the faulty writer made: one per event (a write or a
    forget) and per flood write."""
    faulty = trial.get("faulty_agent")
    return sum(len(s.get("events") or []) + len(s.get("flood") or [])
               for s in trial.get("sessions") or []
               if s.get("writer") == faulty)


def checks(cells: Dict[tuple, dict]) -> List[dict]:
    """STRESS_DIMENSIONS.md's checks that must hold ("Functional check
    and smoke"), each with whether it held over the cells that bear on
    it and what it saw. A check no cell bears on is not reported."""
    rows: List[dict] = []

    def add(check: str, holds: bool, detail: str) -> None:
        rows.append({"check": check, "holds": holds, "detail": detail})

    failed = [(key, t) for key, trials in sorted(cells.items())
              for t in trials if t.get("failed")]
    other = [f"{key[1]} {key[2]} {key[3]} user {t['trial_index']}"
             for key, t in failed
             if not (t.get("error_message") or "").startswith(EMPTY_WRITE)]
    add("every failed trial is a write the backend stored nothing for",
        not other, f"{len(failed) - len(other)} such trials"
        + (f"; other failures: {', '.join(other)}" if other else ""))
    n12 = [key for key in cells if key[3].startswith("n12")]
    if n12:
        add("N = 12 runs end to end", not any(
            key[3].startswith("n12") for key, t in failed
            if not (t.get("error_message") or "").startswith(EMPTY_WRITE)),
            f"{len(n12)} cells, "
            f"{sum(len(cells[key]) for key in n12)} trials")
    for row in agent_count_rows(cells):
        if row["level"] != "H0 across N" or row["backend"] != "inhouse":
            continue
        blocks = row["locus"] != "native"
        holds = row["same_outcomes"] == row["probes"] and (
            not blocks or row["same_blocks"] == row["probes"])
        add(f"in-house H = 0, {row['locus']}: the same outcomes at N = 3, "
            "6 and 12" + (", byte-equal blocks" if blocks else ""), holds,
            f"{row['same_outcomes']}/{row['probes']} outcomes, "
            f"{row['same_blocks']}/{row['probes']} blocks")
    for (model, locus, backend, condition), trials in sorted(cells.items()):
        if locus != "kernel":
            continue
        ok = [t for t in trials if not t.get("failed")]
        name = f"{backend} {condition}"
        if condition == "n6conc":
            covered = sum(len(p.get("late_covered") or [])
                          for p in _probe_stress(ok))
            timeouts = sum(_stress(t).get("barrier_timeouts") or 0
                           for t in ok)
            add(f"kernel {name}: no probe reads a late write the kernel "
                "accepted before it, and no barrier wait times out",
                covered == 0 and timeouts == 0,
                f"{covered} covered late writes, {timeouts} timeouts")
        elif condition == "n6wrong_user":
            misfiled = [_stress(t).get("misfiled_rows") for t in ok]
            short = [t["trial_index"] for t in ok
                     if _stress(t).get("identity_overridden_requests")
                     != _faulty_requests(t)]
            add(f"kernel {name}: no row misfiled, and every faulty request "
                "records identity_overridden",
                all(m == 0 for m in misfiled) and not short,
                f"misfiled {misfiled}"
                + (f"; overrides short for users {short}" if short else ""))
        elif condition in ("n6flood10", "n6flood50"):
            over = [_stress(t).get("flood_sessions_over_bound") for t in ok]
            rejected = sorted({w for t in ok for w in (_stress(t).get(
                "quota_rejected_by_writer") or {})
                if w != t.get("faulty_agent")})
            add(f"kernel {name}: at most max_writes less its write events "
                "accepted per flooding turn, and no reference writer's "
                "write rejected",
                all(o == 0 for o in over) and not rejected,
                f"turns over the bound per user {over}"
                + (f"; rejected writers {rejected}" if rejected else ""))
    return rows


def report(root: Path) -> Dict[str, Any]:
    return report_cells(load(root))


def report_cells(cells: Dict[tuple, dict]) -> Dict[str, Any]:
    return {"checks": checks(cells),
            "probes": probe_rows(cells),
            "agent_count": agent_count_rows(cells),
            "concurrency": concurrency_rows(cells),
            "load": load_rows(cells),
            "faults": fault_rows(cells)}


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3g}"
    if isinstance(value, dict) and "rate" in value:
        if value["rate"] is None:
            return "-"
        low, high = value["ci"]  # Wilson, 95%
        return f"{value['k']}/{value['n']} [{low:.2f}, {high:.2f}]"
    if isinstance(value, dict) and "lost" in value:
        return f"-{value['lost']}/+{value['gained']} (p {value['p']:.2g})"
    if isinstance(value, dict) and "mean" in value:
        if value["mean"] is None:
            return "-"
        low, high = value["ci"]
        if low is None:
            return f"{value['mean']:+.2f} (n {value['n']})"
        return f"{value['mean']:+.2f} [{low:+.2f}, {high:+.2f}]"
    return str(value)


def table(rows: List[dict]) -> str:
    if not rows:
        return "(none)\n"
    keys = list(rows[0])
    lines = ["| " + " | ".join(keys) + " |",
             "|" + "---|" * len(keys)]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(k)) for k in keys)
                     + " |")
    return "\n".join(lines) + "\n"


def markdown(data: Dict[str, Any]) -> str:
    parts = ["# Stress dimensions: judge-free report\n"]
    across = [r for r in data["agent_count"]
              if r["level"] == "H0 across N"]
    mixed = [r for r in data["agent_count"]
             if r["level"] != "H0 across N"]
    # Each table takes its columns from its first row, so rows of
    # another shape get a table of their own.
    for title, rows in (("Checks that must hold", data.get("checks", [])),
                        ("Pass rates per cell", data["probes"]),
                        ("Agent count: H = 0 across N", across),
                        ("Agent count: H = 2 against H = 0", mixed),
                        ("Concurrency (n6conc against n6h0)",
                         data["concurrency"]),
                        ("Load", data["load"]),
                        ("Faults (against n6h0)", data["faults"])):
        parts.append(f"\n## {title}\n\n" + table(rows))
    return "".join(parts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--md", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    data = report(args.root)
    if args.json:
        args.json.write_text(json.dumps(data, indent=1, sort_keys=True))
    text = markdown(data)
    if args.md:
        args.md.write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
