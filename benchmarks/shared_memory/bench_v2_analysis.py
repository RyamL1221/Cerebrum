"""Analyze benchmark v2 runs (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Functional check and smoke").

Reads ``<root>/<model>/<phase>/<condition>_<method>/results_<method>.json``
as AIOS ``scripts/run_bench_v2.sh`` writes them and reports:

- the per-probe pass matrix (locus x backend x condition x probe type),
  deletion split into echo and non-echo users, with 95% Wilson
  intervals, the lenient recency and contradiction rates, and how often
  the cap and the budget bound;
- the functional check's criteria, each with its evidence;
- for the smoke: the integration mean per cell with its 95%
  t-interval, kernel against replicated per probe type (paired over
  users, exact McNemar), and the share of identical in-house blocks.

    python -m benchmarks.shared_memory.bench_v2_analysis results/bench_v2_functional \\
        --markdown results/bench_v2_functional/analysis.md \\
        --json results/bench_v2_functional/analysis.json
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from benchmarks.shared_memory.probes import mcnemar_exact, t_interval, wilson

JUDGE_FREE = ("deletion", "privacy", "recall", "recency", "contradiction")
REAL_CONDITIONS = ("h0", "h2")
CONTROL_OF = {"recall": "no_memory", "recency": "no_memory",
              "contradiction": "no_memory", "deletion": "no_delete",
              "privacy": "no_visibility"}
# method -> (locus, backend)
CELLS = {
    "kernel_shared": None,  # the backend comes from the phase
    "replicated_mem0": ("replicated", "mem0"),
    "replicated_inhouse": ("replicated", "inhouse"),
    "native_mem0": ("native", "mem0"),
    "native_inhouse": ("native", "inhouse"),
}
PHASE_BACKEND = {"kmem0": "mem0", "kinh": "inhouse"}


def load(root: Path) -> Dict[tuple, dict]:
    """``{(model, locus, backend, condition): {"trials": [...],
    "metadata": {...}}}`` for every results file under ``root``."""
    cells = {}
    for path in sorted(root.glob("*/*/*/results_*.json")):
        model, phase, cell = path.parts[-4], path.parts[-3], path.parts[-2]
        # "<condition>_<method>"; conditions hold underscores themselves
        # (no_delete), so the method is matched as the suffix.
        method = next((m for m in CELLS if cell.endswith("_" + m)), None)
        if method is None:
            continue
        condition = cell[:-len(method) - 1]
        locus, backend = CELLS[method] or ("kernel", PHASE_BACKEND[phase])
        data = json.loads(path.read_text())
        cells[(model, locus, backend, condition)] = {
            "trials": data["conditions"][0]["trials"],
            "metadata": data["experiment_metadata"],
        }
    return cells


def _rate(passed: int, n: int) -> dict:
    if not n:
        return {"passed": passed, "n": n, "rate": None, "ci_low": None,
                "ci_high": None}
    low, high = wilson(passed, n)
    return {"passed": passed, "n": n, "rate": passed / n, "ci_low": low,
            "ci_high": high}


def _probes(trials: List[dict], kind: str, echo: Optional[bool] = None):
    out = []
    for trial in trials:
        if trial.get("failed"):
            continue
        for probe in trial.get("probe_results") or []:
            if probe["type"] != kind:
                continue
            if echo is not None and bool(probe.get("echo_event")) != echo:
                continue
            out.append(probe)
    return out


def cell_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """One row per cell and probe type (deletion also per echo split)."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        trials = cell["trials"]
        failed = sum(1 for t in trials if t.get("failed"))
        splits = [(kind, None) for kind in JUDGE_FREE]
        splits += [("deletion", True), ("deletion", False)]
        for kind, echo in splits:
            probes = _probes(trials, kind, echo)
            scored = [p for p in probes if p.get("passed") is not None]
            row = {
                "model": model, "locus": locus, "backend": backend,
                "condition": condition,
                "probe": kind if echo is None else
                f"deletion ({'echo' if echo else 'no echo'})",
                "trials": len(trials), "failed": failed,
                **_rate(sum(1 for p in scored if p["passed"]), len(scored)),
                "cap_bound": sum(1 for p in probes if p.get("cap_bound")),
                "budget_bound": (None if locus == "native" else sum(
                    1 for p in probes if p.get("budget_bound"))),
                "probes": len(probes),
                # A value reached the block only through the consumer's
                # own conversation rows (earlier probes' answers).
                "contaminated": sum(1 for p in probes
                                    if p.get("contaminated")),
            }
            if kind in ("recency", "contradiction"):
                lenient = [p for p in probes
                           if p.get("expected_present") is not None]
                row["lenient"] = _rate(
                    sum(1 for p in lenient if p["expected_present"]),
                    len(lenient))["rate"]
                both = [p for p in probes if p.get("expected_present")
                        and p.get("stale_present")]
                row["names_both"] = len(both)
                row["named_as_past"] = sum(
                    1 for p in both if p.get("transition_marked"))
            if kind in ("deletion", "privacy"):
                row["in_block"] = sum(1 for p in probes
                                      if p.get("forbidden_in_block"))
                row["in_answer"] = sum(1 for p in probes
                                       if p.get("forbidden_in_answer"))
            rows.append(row)
    return rows


def binding_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per cell: the share of probes whose cap / budget bound, and the
    block sizes."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        probes = [p for t in cell["trials"] if not t.get("failed")
                  for p in t.get("probe_results") or []]
        tokens = [((p.get("diagnostics") or {}).get("tokens_estimated")
                   or 0) for p in probes]
        rows.append({
            "model": model, "locus": locus, "backend": backend,
            "condition": condition, "probes": len(probes),
            "cap_bound": sum(1 for p in probes if p.get("cap_bound")),
            "budget_bound": None if locus == "native" else sum(
                1 for p in probes if p.get("budget_bound")),
            "tokens_median": statistics.median(tokens) if tokens else None,
            "tokens_max": max(tokens) if tokens else None,
        })
    return rows


def criteria(cells: Dict[tuple, dict]) -> List[dict]:
    """The functional check's pass conditions (docs/BENCHMARK_V2.md),
    each with its evidence."""
    out = []

    def probes_where(kind, pred, echo=None):
        return [p for key, cell in cells.items() if pred(*key)
                for p in _probes(cell["trials"], kind, echo)
                if p.get("passed") is not None]

    real = lambda m, l, b, c: c in REAL_CONDITIONS  # noqa: E731
    for kind in JUDGE_FREE:
        scored = probes_where(kind, real)
        passes = sum(1 for p in scored if p["passed"])
        fails = len(scored) - passes
        control = CONTROL_OF[kind]
        ctl = probes_where(kind, lambda m, l, b, c: c == control)
        ctl_fails = sum(1 for p in ctl if not p["passed"])
        out.append({
            "criterion": f"{kind} passes and fails in real conditions, "
                         f"and fails under {control}",
            "holds": passes > 0 and fails > 0 and ctl_fails > 0,
            "evidence": f"real: {passes} pass, {fails} fail; "
                        f"{control}: {ctl_fails} of {len(ctl)} fail",
        })
    inhouse_real = lambda m, l, b, c: (  # noqa: E731
        b == "inhouse" and c in REAL_CONDITIONS)
    non_echo = probes_where("deletion", inhouse_real, echo=False)
    nd = probes_where("deletion", lambda m, l, b, c: c == "no_delete")
    out.append({
        "criterion": "deletion passes among non-echo users in in-house "
                     "cells and fails under no_delete",
        "holds": bool(non_echo) and all(p["passed"] for p in non_echo)
        and any(not p["passed"] for p in nd),
        "evidence": f"non-echo in-house: "
                    f"{sum(p['passed'] for p in non_echo)} of "
                    f"{len(non_echo)} pass; no_delete: "
                    f"{sum(not p['passed'] for p in nd)} of {len(nd)} fail",
    })
    kernel_priv = [p for key, cell in cells.items() if key[1] == "kernel"
                   for p in _probes(cell["trials"], "privacy")]
    leaks = [p for p in kernel_priv if p.get("forbidden_in_block")
             or p.get("forbidden_in_answer")]
    out.append({
        "criterion": "the kernel's privacy probe never fails (block or "
                     "answer)",
        "holds": bool(kernel_priv) and not leaks,
        "evidence": f"{len(leaks)} of {len(kernel_priv)} kernel privacy "
                    "probes leaked",
    })
    # A cell is locus x backend (the spec's six cells), read over the
    # real conditions: no_memory skips the sessions, so its cap cannot
    # bind, and the controls are not what the check is about.
    bound: Dict[tuple, List[int]] = {}
    for (m, l, b, c), cell in cells.items():
        if l not in ("kernel", "replicated") or c not in REAL_CONDITIONS:
            continue
        counts = bound.setdefault((m, l, b), [0, 0, 0])
        for t in cell["trials"]:
            for p in t.get("probe_results") or []:
                counts[0] += 1
                counts[1] += bool(p.get("cap_bound"))
                counts[2] += bool(p.get("budget_bound"))
    no_cap = [key for key, (_, cap, _) in sorted(bound.items()) if not cap]
    out.append({
        "criterion": "the cap binds in some probe of every kernel and "
                     "replicated cell (H = 0 and H = 2)",
        "holds": bool(bound) and not no_cap,
        "evidence": "; ".join(f"{l} {b}: {cap} of {n}"
                              for (m, l, b), (n, cap, _)
                              in sorted(bound.items()))
        + (f"; cells without a binding cap: {no_cap}" if no_cap else ""),
    })
    budget = sum(budget for (m, l, b), (_, _, budget) in bound.items()
                 if b == "inhouse")
    out.append({
        "criterion": "the budget binds in some probe of a kernel or "
                     "replicated in-house cell (H = 0 and H = 2)",
        "holds": budget > 0,
        "evidence": f"{budget} probes with a binding budget",
    })
    return out


def contrast_rows(cells: Dict[tuple, dict], model: str,
                  condition: str = "h0") -> List[dict]:
    """Kernel against replicated per backend and probe type, paired by
    user: exact McNemar on the discordant pairs."""
    rows = []
    for backend in ("mem0", "inhouse"):
        k = cells.get((model, "kernel", backend, condition))
        r = cells.get((model, "replicated", backend, condition))
        if not k or not r:
            continue
        by_user = lambda cell: {t["trial_index"]: t  # noqa: E731
                                for t in cell["trials"]
                                if not t.get("failed")}
        ku, ru = by_user(k), by_user(r)
        for kind in JUDGE_FREE:
            b = c = both = 0
            for i in sorted(set(ku) & set(ru)):
                kp = next((p for p in ku[i]["probe_results"]
                           if p["type"] == kind), None)
                rp = next((p for p in ru[i]["probe_results"]
                           if p["type"] == kind), None)
                if not kp or not rp or kp.get("passed") is None \
                        or rp.get("passed") is None:
                    continue
                both += 1
                b += kp["passed"] and not rp["passed"]
                c += rp["passed"] and not kp["passed"]
            rows.append({"model": model, "backend": backend, "probe": kind,
                         "pairs": both, "kernel_only": b,
                         "replicated_only": c,
                         "p_mcnemar": mcnemar_exact(b, c) if both else None})
        if backend == "inhouse":
            same = total = 0
            for i in sorted(set(ku) & set(ru)):
                for kp, rp in zip(ku[i]["probe_results"],
                                  ru[i]["probe_results"]):
                    total += 1
                    same += ((kp.get("diagnostics") or {}).get("block_text")
                             == (rp.get("diagnostics") or {}).get(
                                 "block_text"))
            rows.append({"model": model, "backend": backend,
                         "probe": "identical blocks", "pairs": total,
                         "kernel_only": same, "replicated_only": None,
                         "p_mcnemar": None})
    return rows


def integration_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per cell with judged integration scores (failed trials left
    out): ``n``, the ``mean`` with its 95% t-interval (``ci_low`` /
    ``ci_high``), ``sd`` (both None for n < 2, where neither is
    defined) and the share of scores of 4 or more."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        scores = [t.get("integration_score") for t in cell["trials"]
                  if not t.get("failed")
                  and t.get("integration_score") is not None]
        if not scores:
            continue
        mean = statistics.mean(scores)
        sd = statistics.stdev(scores) if len(scores) > 1 else None
        low, high = t_interval(scores)
        rows.append({"model": model, "locus": locus, "backend": backend,
                     "condition": condition, "n": len(scores),
                     "mean": mean, "ci_low": low, "ci_high": high,
                     "sd": sd,
                     "share_ge_4": sum(s >= 4 for s in scores) / len(scores)})
    return rows


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def table(rows: List[dict], keys: List[str]) -> str:
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(k)) for k in keys)
                     + " |")
    return "\n".join(lines)


def markdown(cells, rows, binding, checks, contrasts, integration) -> str:
    """The report: the pass matrix and the cap and budget table, then
    the criteria, the contrasts and the integration rows when given."""
    out = ["# Benchmark v2 analysis", "",
           f"{len(cells)} cells, "
           f"{sum(len(c['trials']) for c in cells.values())} user-trials, "
           f"{sum(1 for c in cells.values() for t in c['trials'] if t.get('failed'))} failed.",
           "", "## Per-probe pass matrix", "",
           "Pass rates with 95% Wilson intervals; recency and "
           "contradiction also give the lenient rate (the new value "
           "named, stale or not), how many answers named both values "
           "and how many of those named the stale one as past. "
           "`contaminated`: a value reached the block only through the "
           "consumer's own conversation rows.", "",
           table(rows, ["model", "locus", "backend", "condition", "probe",
                        "passed", "n", "rate", "ci_low", "ci_high",
                        "lenient", "names_both", "named_as_past",
                        "in_block", "in_answer", "contaminated",
                        "cap_bound", "budget_bound", "probes"]), "",
           "## Cap and budget", "",
           table(binding, ["model", "locus", "backend", "condition",
                           "probes", "cap_bound", "budget_bound",
                           "tokens_median", "tokens_max"]), ""]
    if checks:
        out += ["## Functional check criteria", "",
                table(checks, ["criterion", "holds", "evidence"]), ""]
    if contrasts:
        out += ["## Kernel against replicated (paired over users)", "",
                table(contrasts, ["model", "backend", "probe", "pairs",
                                  "kernel_only", "replicated_only",
                                  "p_mcnemar"]), ""]
    if integration:
        out += ["## Integration (judge v2)", "",
                "The mean with its 95% t-interval (none for n < 2).", "",
                table(integration, ["model", "locus", "backend",
                                    "condition", "n", "mean", "ci_low",
                                    "ci_high", "sd", "share_ge_4"]), ""]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--markdown")
    parser.add_argument("--json")
    parser.add_argument("--no-criteria", action="store_true",
                        help="skip the functional check's criteria")
    args = parser.parse_args(argv)
    cells = load(Path(args.root))
    rows, binding = cell_rows(cells), binding_rows(cells)
    checks = [] if args.no_criteria else criteria(cells)
    models = sorted({key[0] for key in cells})
    contrasts = [r for m in models for r in contrast_rows(cells, m)]
    integration = integration_rows(cells)
    text = markdown(cells, rows, binding, checks, contrasts, integration)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text)
    if args.json:
        Path(args.json).write_text(json.dumps({
            "rows": rows, "binding": binding, "criteria": checks,
            "contrasts": contrasts, "integration": integration,
        }, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
