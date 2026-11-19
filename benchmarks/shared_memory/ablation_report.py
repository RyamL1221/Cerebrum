"""The kernel ablations' report (NeurIPS Subtask 19, AIOS docs/ABLATION.md):
reads a run of AIOS ``scripts/run_ablation.sh`` and writes, per switch,
one row per measurement: the full kernel's value, the ablated kernel's,
the paired difference (ablated minus full, by trial index) with its 95%
t interval, and the measurement's name; the functional check's rules
and the smoke's, each confirmed or not; and the contribution figure.

    python -m benchmarks.shared_memory.ablation_report results/<run> \\
        --md results/<run>/analysis.md --json results/<run>/analysis.json \\
        --svg results/<run>/contribution.svg

The run's layout is ``<model>/<phase>/<condition>_<method>``: phase
``kinh`` / ``kmem0`` is the full kernel, ``kinh_<switch>`` the kernel
with that switch, ``agent`` the replicated reference of
``consumer_config``.
"""
import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from benchmarks.shared_memory.ablation import SWITCHES, trial_ablation
from benchmarks.shared_memory.bench_v2_analysis import CELLS
from benchmarks.shared_memory.probes import t_interval
from benchmarks.shared_memory.stress_report import (
    JUDGE_FREE,
    _block,
    _by_user,
    _judge_free,
    _probe,
    _stress,
    cross_user_rows,
    paired_outcomes,
)
from benchmarks.shared_memory.synth_v2 import is_echo_user

KERNEL_PHASES = {"kinh": "inhouse", "kmem0": "mem0"}


def load(root: Path) -> Dict[tuple, List[dict]]:
    """``{(model, backend, switch, condition, method): trials}``;
    ``switch`` is None for the full kernel and ``"replicated"`` for the
    agent phase."""
    cells = {}
    for path in sorted(root.glob("*/*/*/results_*.json")):
        model, phase, cell = path.parts[-4], path.parts[-3], path.parts[-2]
        method = next((m for m in CELLS if cell.endswith("_" + m)), None)
        if method is None:
            continue
        condition = cell[:-len(method) - 1]
        if phase == "agent":
            backend, switch = CELLS[method][1], "replicated"
        else:
            base, _, switch = phase.partition("_")
            if base not in KERNEL_PHASES or (switch and
                                             switch not in SWITCHES):
                continue
            backend, switch = KERNEL_PHASES[base], switch or None
        data = json.loads(path.read_text())
        cells[(model, backend, switch, condition, method)] = \
            data["conditions"][0]["trials"]
    return cells


# -- the measures, per trial ---------------------------------------------------

def _probe_stress(trial: dict) -> List[dict]:
    return list((_stress(trial).get("probes") or {}).values())


def _diagnostics(trial: dict) -> List[dict]:
    return [p.get("diagnostics") or {}
            for p in trial.get("probe_results") or []]


def _mean(values: List[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def _failed(kind: str) -> Callable[[dict], Optional[int]]:
    def value(trial):
        passed = (_probe(trial, kind) or {}).get("passed")
        return None if passed is None else int(not passed)
    return value


def covered_late_writes(t):
    return sum(len(p.get("late_covered") or []) for p in _probe_stress(t))


def stale_reads(t):
    return sum(1 for p in _probe_stress(t) if p.get("stale_read"))


def timing_misses(t):
    return sum(1 for p in _probe_stress(t) if p.get("timing_miss"))


def misfiled_rows(t):
    return _stress(t).get("misfiled_rows") or 0


def stale_in_block(t):
    """Recency and contradiction probes whose block held the earlier
    statement's value."""
    return sum(1 for kind in ("recency", "contradiction")
               if (_probe(t, kind) or {}).get("stale_in_block"))


def carriers_left(t):
    return len(t.get("revoked_value_rows") or [])


def flood_rows_per_probe(t):
    return _mean([p.get("flood_rows_in_block") or 0
                  for p in _probe_stress(t)])


def block_tokens(t):
    return _mean([d.get("tokens_estimated") for d in _diagnostics(t)])


def budget_bound(t):
    return sum(1 for p in t.get("probe_results") or []
               if p.get("budget_bound"))


def after_threshold(t):
    return _mean([d.get("after_threshold") for d in _diagnostics(t)])


def after_cap(t):
    return _mean([d.get("after_cap") for d in _diagnostics(t)])


def jf(key: str) -> Callable[[dict], Any]:
    return lambda t: _judge_free(t, key)


def flood_writes_accepted(t):
    return _stress(t).get("flood_writes_accepted") or 0


def deletion_failed_of(echo: bool) -> Callable[[dict], Optional[int]]:
    """The deletion outcome of echo users only (``echo``), or of the
    others: None for a user of the other kind, so it is not paired."""
    def value(trial):
        if is_echo_user(trial["trial_index"]) != echo:
            return None
        return _failed("deletion")(trial)
    return value


class Measure(NamedTuple):
    condition: str
    name: str
    value: Callable[[dict], Any]
    # +1: the ablation should raise it; -1: lower it; 0: reported.
    direction: int
    primary: bool = False


MEASURES: Dict[str, List[Measure]] = {
    "barrier": [
        Measure("n6conc", "covered late writes per user",
                covered_late_writes, +1, True),
        Measure("n6conc", "stale reads per user", stale_reads, +1),
        Measure("n6conc", "timing misses per user", timing_misses, +1),
        Measure("n6conc", "memories_missing", jf("memories_missing"), 0),
    ],
    "identity": [
        Measure("n6wrong_user", "misfiled rows per user", misfiled_rows,
                +1, True),
        Measure("n6wrong_user", "cross-user rows in the blocks",
                cross_user_rows, +1),
        Measure("n6wrong_user", "memories_missing",
                jf("memories_missing"), +1),
        Measure("n6v2", "profile facts in the block",
                jf("profile_facts_in_block"), -1, True),
        Measure("n6v2", "memories_missing", jf("memories_missing"), +1),
    ],
    "visibility": [
        Measure("n6v3", "privacy probe failed", _failed("privacy"), +1,
                True),
        Measure("n6v3", "private rows from others",
                jf("private_rows_from_others"), +1),
    ],
    "supersession": [
        Measure("n6h0", "stale value in the recency and contradiction "
                "blocks", stale_in_block, +1, True),
        Measure("n6h0", "recency failed", _failed("recency"), +1),
        Measure("n6h0", "contradiction failed", _failed("contradiction"),
                +1),
    ],
    "forget_scope": [
        Measure("n6h0", "carriers left per user", carriers_left, +1, True),
        Measure("n6h0", "deletion failed, echo users",
                deletion_failed_of(True), +1),
        Measure("n6h0", "deletion failed, other users",
                deletion_failed_of(False), 0),
    ],
    "quota": [
        Measure(level, name, value, direction, primary)
        for level in ("n6flood10", "n6flood50")
        for name, value, direction, primary in (
            ("flood rows in the block per probe", flood_rows_per_probe,
             +1, True),
            ("profile facts in the block",
             jf("profile_facts_in_block"), -1, True),
            ("memories_missing", jf("memories_missing"), +1, False),
            ("flood writes accepted", flood_writes_accepted, +1, False),
        )
    ],
    "block_format": [
        Measure("n6h0", "block tokens per probe", block_tokens, 0, True),
    ],
    "block_order": [
        Measure("n6h0", "block tokens per probe", block_tokens, 0, True),
    ],
    "budget": [
        Measure("n6h0", "block tokens per probe", block_tokens, +1, True),
        Measure("n6h0", "probes the budget bound", budget_bound, -1),
    ],
    "threshold": [
        Measure("n6h0", "candidates after the threshold per probe",
                after_threshold, -1, True),
        Measure("n6h0", "block tokens per probe", block_tokens, -1),
    ],
    "consumer_config": [
        Measure("n6v4", "candidates after the threshold per probe",
                after_threshold, -1, True),
        Measure("n6v4", "rows after the cap per probe", after_cap, -1),
        Measure("n6v4", "block tokens per probe", block_tokens, -1),
        Measure("n6v4", "profile facts in the block",
                jf("profile_facts_in_block"), -1),
        Measure("n6v4", "memories_missing", jf("memories_missing"), +1),
    ],
}


def paired(ablated: List[dict], full: List[dict], value) -> dict:
    """Both cells' means over the users both have, and the paired
    difference ablated minus full with its 95% t interval."""
    here, there = _by_user(ablated), _by_user(full)
    pairs = []
    for user in sorted(set(here) & set(there)):
        a, b = value(there[user]), value(here[user])
        if a is not None and b is not None:
            pairs.append((a, b))
    if not pairs:
        return {"n": 0, "full": None, "ablated": None, "diff": None,
                "ci": None}
    diffs = [b - a for a, b in pairs]
    low, high = t_interval(diffs)
    # Plain floats: scipy's are numpy scalars, which JSON would print as
    # strings.
    return {"n": len(pairs),
            "full": float(statistics.mean(a for a, _ in pairs)),
            "ablated": float(statistics.mean(b for _, b in pairs)),
            "diff": float(statistics.mean(diffs)),
            "ci": None if low is None else [float(low), float(high)]}


def confirmed(row: dict) -> Optional[bool]:
    """A predicted direction confirmed: the interval excludes 0 on its
    side (a constant difference over two or more users has a
    zero-width interval, so it counts by its sign). None for a reported
    measure, or fewer than two pairs, which test nothing."""
    if not row["direction"] or row["diff"] is None or row.get("n", 0) < 2:
        return None
    ci = row["ci"] or [row["diff"], row["diff"]]
    return bool(ci[0] > 0 if row["direction"] > 0 else ci[1] < 0)


def rows(cells: Dict[tuple, List[dict]]) -> List[dict]:
    """One row per switch, condition and measurement the run has both
    cells for."""
    out = []
    keys = sorted({(m, b) for m, b, *_ in cells})
    for model, backend in keys:
        for switch, measures in MEASURES.items():
            for measure in measures:
                full = cells.get((model, backend, None, measure.condition,
                                  "kernel_shared"))
                ablated = cells.get((model, backend, switch,
                                     measure.condition, "kernel_shared"))
                if not (full and ablated):
                    continue
                row = {"model": model, "backend": backend,
                       "switch": switch,
                       "value": SWITCHES[switch][2],
                       "condition": measure.condition,
                       "measure": measure.name,
                       "primary": measure.primary,
                       "direction": measure.direction,
                       **paired(ablated, full, measure.value)}
                row["confirmed"] = confirmed(row)
                out.append(row)
    return out


def outcome_rows(cells: Dict[tuple, List[dict]]) -> List[dict]:
    """Per switch and condition, each judge-free probe type's outcomes
    against the full kernel (lost, gained, exact McNemar p)."""
    out = []
    for (model, backend, switch, condition, method), trials in sorted(
            cells.items(), key=lambda kv: tuple(map(str, kv[0]))):
        if switch in (None, "replicated") or method != "kernel_shared":
            continue
        full = cells.get((model, backend, None, condition, method))
        if not full:
            continue
        out.append({"model": model, "backend": backend, "switch": switch,
                    "condition": condition,
                    **{kind: paired_outcomes(trials, full, kind)
                       for kind in JUDGE_FREE}})
    return out


def _cell(cells, model, backend, switch, condition,
          method="kernel_shared") -> List[dict]:
    return [t for t in cells.get((model, backend, switch, condition,
                                  method)) or [] if not t.get("failed")]


def _blocks(trials: List[dict]) -> Dict[tuple, Optional[str]]:
    return {(t["trial_index"], p.get("probe_id")): _block(p)
            for t in trials for p in t.get("probe_results") or []}


def _per_probe(trials: List[dict], key: str) -> Dict[tuple, Any]:
    return {(t["trial_index"], p.get("probe_id")):
            (p.get("diagnostics") or {}).get(key)
            for t in trials for p in t.get("probe_results") or []}


def record_checks(cells: Dict[tuple, List[dict]]) -> List[dict]:
    """Every trial records the ablation its cell ran (``trial_ablation``):
    ``{}`` in a full-kernel or replicated cell, its switch in an
    ablated one; and a cell with no successful trial is reported, not
    skipped."""
    out = []
    for (model, backend, switch, condition, method), trials in sorted(
            cells.items(), key=lambda kv: tuple(map(str, kv[0]))):
        want = ({} if switch in (None, "replicated")
                else {switch: SWITCHES[switch][2]})
        wrong = [t["trial_index"] for t in trials
                 if trial_ablation(t) != want]
        ok = [t for t in trials if not t.get("failed")]
        out.append({"model": model, "backend": backend,
                    "switch": switch or "full", "condition": condition,
                    "method": method, "trials": len(trials),
                    "succeeded": len(ok), "wrong_record": wrong,
                    "held": bool(ok) and not wrong})
    return out


def functional_checks(cells: Dict[tuple, List[dict]]) -> List[dict]:
    """ABLATION.md's functional-check rules, per switch the run has
    both cells for: whether each held, and what it saw."""
    out = []

    def check(model, backend, switch, rule, held, seen):
        out.append({"model": model, "backend": backend, "switch": switch,
                    "rule": rule, "held": bool(held), "seen": seen})

    for model, backend in sorted({(m, b) for m, b, *_ in cells}):
        def pair(switch, condition):
            return (_cell(cells, model, backend, switch, condition),
                    _cell(cells, model, backend, None, condition))

        abl, full = pair("barrier", "n6conc")
        if abl and full:
            a = sum(covered_late_writes(t) for t in abl)
            f = sum(covered_late_writes(t) for t in full)
            check(model, backend, "barrier",
                  "a covered late write; the full kernel none",
                  a >= 1 and f == 0, f"{a} ablated, {f} full")
        abl, full = pair("identity", "n6wrong_user")
        if abl and full:
            a = sum(misfiled_rows(t) for t in abl)
            c = sum(cross_user_rows(t) for t in abl)
            f = sum(misfiled_rows(t) + cross_user_rows(t) for t in full)
            check(model, backend, "identity",
                  "wrong_user: misfiled rows and a cross-user row; the "
                  "full kernel neither", a >= 1 and c >= 1 and f == 0,
                  f"{a} misfiled and {c} cross-user rows ablated, {f} full")
        abl, full = pair("identity", "n6v2")
        if abl and full:
            facts = [_judge_free(t, "profile_facts_in_block") for t in abl]
            check(model, backend, "identity",
                  "V2: profile facts in the block 0 for every user",
                  all(f == 0 for f in facts), f"{facts}")
        abl, full = pair("visibility", "n6v3")
        if abl and full:
            a = [t for t in abl if (_probe(t, "privacy") or {}).get(
                "passed") is False and (_probe(t, "privacy") or {}).get(
                "forbidden_in_block")]
            f = [t for t in full
                 if (_probe(t, "privacy") or {}).get("passed") is False]
            check(model, backend, "visibility",
                  "a privacy probe fails with its value in the block; the "
                  "full kernel's never", a and not f,
                  f"{len(a)} of {len(abl)} ablated, {len(f)} full")
        abl, full = pair("supersession", "n6h0")
        if abl:
            probes = [(_probe(t, k) or {}) for t in abl
                      for k in ("recency", "contradiction")]
            held = [p for p in probes if p.get("stale_in_block")]
            check(model, backend, "supersession",
                  "an earlier statement in every recency and "
                  "contradiction block", probes and len(held) == len(
                      probes), f"{len(held)} of {len(probes)} blocks")
        abl, full = pair("forget_scope", "n6h0")
        if abl:
            echo = [t for t in abl if is_echo_user(t["trial_index"])]
            other = [t for t in abl if not is_echo_user(t["trial_index"])]
            echo_ok = all(carriers_left(t) >= 1 and _failed("deletion")(t)
                          for t in echo)
            other_ok = all(_failed("deletion")(t) == 0 for t in other)
            check(model, backend, "forget_scope",
                  "echo users keep a carrier and fail deletion; the "
                  "others pass", echo and echo_ok and other_ok,
                  f"echo users {[t['trial_index'] for t in echo]}: "
                  f"carriers {[carriers_left(t) for t in echo]}, deletion "
                  f"failed {[_failed('deletion')(t) for t in echo]}; "
                  f"others failed {[_failed('deletion')(t) for t in other]}")
        for level in ("n6flood10", "n6flood50"):
            abl, full = pair("quota", level)
            if abl and full:
                rejected = sum(sum((_stress(t).get("quota_rejected")
                                    or {}).values()) for t in abl)
                a = sum(flood_rows_per_probe(t) or 0 for t in abl)
                f = sum(flood_rows_per_probe(t) or 0 for t in full)
                check(model, backend, "quota",
                      f"{level}: no quota rejection, more flood rows in "
                      "the blocks than the full kernel's",
                      rejected == 0 and a > f,
                      f"{rejected} rejected; {a:.1f} vs {f:.1f} flood "
                      "rows per probe, summed over users")
        for switch in ("block_format", "block_order"):
            abl, full = pair(switch, "n6h0")
            if abl and full:
                a, f = _blocks(abl), _blocks(full)
                differ = sum(1 for k in a if k in f and a[k] != f[k])
                check(model, backend, switch,
                      "the blocks differ from the full kernel's",
                      differ >= 1, f"{differ} of {len(a)} probes differ")
        abl, full = pair("budget", "n6h0")
        if abl:
            bound = sum(budget_bound(t) for t in abl)
            check(model, backend, "budget", "the budget binds in no probe",
                  bound == 0, f"{bound} probes bound")
        abl, full = pair("threshold", "n6h0")
        if abl and full:
            a = _per_probe(abl, "after_threshold")
            f = _per_probe(full, "after_threshold")
            over = sorted(k for k in a if k in f and (a[k] or 0)
                          > (f[k] or 0))
            check(model, backend, "threshold",
                  "after_threshold never above the full kernel's, probe "
                  "by probe", not over, f"probes above: {over}")
        abl = _cell(cells, model, backend, "consumer_config", "n6v4")
        replicated = _cell(cells, model, backend, "replicated", "n6v4",
                           f"replicated_{backend}")
        if abl and replicated:
            a, r = _blocks(abl), _blocks(replicated)
            same = sum(1 for k in a if k in r and a[k] == r[k])
            check(model, backend, "consumer_config",
                  "the kernel's V4 block equals the replicated V4 block "
                  "in every probe", same == len(a) == len(r),
                  f"{same} of {len(a)} probes equal")
        full_v4 = _cell(cells, model, backend, None, "n6v4")
        full_h0 = _cell(cells, model, backend, None, "n6h0")
        if full_v4 and full_h0:
            a, h = _blocks(full_v4), _blocks(full_h0)
            same = sum(1 for k in a if k in h and a[k] == h[k])
            check(model, backend, "consumer_config",
                  "on the full kernel the V4 consumer's block equals the "
                  "H = 0 block", same == len(a) and same > 0,
                  f"{same} of {len(a)} probes equal")
    return out


def smoke_checks(table: List[dict]) -> List[dict]:
    """The smoke's rule (ABLATION.md, "Smoke"): each primary measure's
    interval excludes 0 in the predicted direction."""
    return [{"model": r["model"], "backend": r["backend"],
             "switch": r["switch"], "condition": r["condition"],
             "measure": r["measure"], "held": bool(r["confirmed"]),
             "seen": _fmt_diff(r)}
            for r in table if r["primary"] and r["direction"]]


# -- output --------------------------------------------------------------------

def _num(value) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def _fmt_diff(row: dict) -> str:
    if row["diff"] is None:
        return "-"
    ci = row["ci"]
    interval = f" [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else ""
    return f"{row['diff']:+.2f}{interval}"


def markdown(table: List[dict], outcomes: List[dict],
             functional: List[dict], records: List[dict] = ()) -> str:
    lines = ["# Kernel ablations (AIOS docs/ABLATION.md)", "",
             "Paired by trial index: ablated minus the full kernel, with "
             "a 95% t interval. Direction: + the ablation should raise the "
             "measure, - lower it, 0 reported.", "",
             "| switch | condition | measure | full | ablated | difference"
             " | n | direction | confirmed |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in table:
        lines.append(
            f"| {r['switch']}: {r['value']} | {r['condition']} | "
            f"{r['measure']}{' (primary)' if r['primary'] else ''} | "
            f"{_num(r['full'])} | {_num(r['ablated'])} | {_fmt_diff(r)} | "
            f"{r['n']} | {'+-0'[[1, -1, 0].index(r['direction'])]} | "
            f"{'-' if r['confirmed'] is None else r['confirmed']} |")
    lines += ["", "## Outcomes against the full kernel", "",
              "| switch | condition | " + " | ".join(JUDGE_FREE) + " |",
              "|---|---|" + "---|" * len(JUDGE_FREE)]
    for r in outcomes:
        cells = [f"-{r[k]['lost']} +{r[k]['gained']} (p {r[k]['p']:.2f})"
                 for k in JUDGE_FREE]
        lines.append(f"| {r['switch']} | {r['condition']} | "
                     + " | ".join(cells) + " |")
    if functional:
        lines += ["", "## Functional check rules", "",
                  "| switch | rule | held | seen |", "|---|---|---|---|"]
        for r in functional:
            lines.append(f"| {r['switch']} | {r['rule']} | {r['held']} | "
                         f"{r['seen']} |")
    if records:
        lines += ["", "## Cells", "",
                  "Each trial's recorded ablation is its cell's.", "",
                  "| switch | condition | method | trials | succeeded | "
                  "wrong record | held |", "|---|---|---|---|---|---|---|"]
        for r in records:
            lines.append(f"| {r['switch']} | {r['condition']} | "
                         f"{r['method']} | {r['trials']} | {r['succeeded']}"
                         f" | {r['wrong_record'] or '-'} | {r['held']} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--md", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)
    cells = load(args.root)
    table = rows(cells)
    outcomes = outcome_rows(cells)
    functional = functional_checks(cells)
    records = record_checks(cells)
    report = {"rows": table, "outcomes": outcomes,
              "functional_checks": functional,
              "smoke_checks": smoke_checks(table),
              "record_checks": records}
    text = markdown(table, outcomes, functional, records)
    if args.md:
        args.md.write_text(text)
    else:
        print(text)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
    if args.svg:
        from benchmarks.shared_memory.ablation_figure import contribution_svg

        args.svg.write_text(contribution_svg(table))


if __name__ == "__main__":
    main()
