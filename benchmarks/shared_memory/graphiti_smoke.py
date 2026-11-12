"""The pilot_v1 smoke on Graphiti (NeurIPS Subtask 16, AIOS
docs/GRAPHITI_BACKEND.md): the Subtask 11 pilot's locus contrasts on a
third backend, for one model at H = 0 and 2 on pilot_v1's 30 users, as
AIOS ``scripts/run_pilot_v1_graphiti.sh`` writes them.

It reads the cells with ``pilot_analysis``'s statistics and reports:

- per cell: scores, judge-free rates, failures, the backend's calls and
  cost, latency;
- paired kernel - replicated and kernel - native per H, with 95%
  t-intervals over users, and the H2 - H0 difference;
- two readings, reported, not required: the H = 0 tie (the interval of
  each primary gap holds 0) and the direction of the H = 2 gap against
  the pilot's own gaps for the same model (``--reference``, the pilot's
  ``gaps.csv``: pooled, Mem0 and in-house).

It gives no verdict: PILOT.md's rule is the pilot's, over two models,
two backends and H = 0 to 2.

    python -m benchmarks.shared_memory.graphiti_smoke \\
        results/pilot_v1_graphiti \\
        --reference results/pilot_v1_hetero/gaps.csv \\
        --markdown results/pilot_v1_graphiti/analysis.md \\
        --json results/pilot_v1_graphiti/analysis.json \\
        --csv-dir results/pilot_v1_graphiti
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from benchmarks.shared_memory import pilot_analysis as pa
from benchmarks.shared_memory.cost import cell_summary, load_prices
from benchmarks.shared_memory.pilot_schedule import PATH, Schedule

MODELS = ("qwen",)
LEVELS = (0, 2)
BACKEND = "graphiti"
# locus -> (phase, method)
CELLS = {
    "kernel": ("kgra", "kernel_shared"),
    "replicated": ("agent_gra", "replicated_graphiti"),
    "native": ("agent_gra", "native_graphiti"),
}
OTHERS = ("replicated", "native")


def cell_file(root: Path, model: str, locus: str, level: int) -> Path:
    phase, method = CELLS[locus]
    return (root / model / phase / f"h{level}_{method}"
            / f"results_{method}.json")


def load(root: Path) -> Tuple[dict, dict]:
    """As ``pilot_analysis.load``: ``cells[(model, locus, "graphiti",
    H)]`` is the trials by index, ``metadata`` the experiment metadata."""
    cells, metadata = {}, {}
    for model in MODELS:
        for locus in CELLS:
            for level in LEVELS:
                path = cell_file(root, model, locus, level)
                if not path.exists():
                    continue
                data = json.loads(path.read_text())
                key = (model, locus, BACKEND, level)
                cells[key] = {t["trial_index"]: t
                              for t in data["conditions"][0]["trials"]}
                metadata[key] = data["experiment_metadata"]
    return cells, metadata


def cost_rows(cells: dict, prices: dict) -> List[dict]:
    """Per cell: the backend's calls and USD per user, the total USD per
    user, and the trial latency."""
    rows = []
    for (model, locus, backend, level), trials in sorted(cells.items()):
        summary = cell_summary(list(trials.values()), prices)
        rows.append({
            "model": model, "locus": locus, "level": level,
            "n": summary["n"],
            "backend_calls": summary.get("backend_calls"),
            "backend_usd": summary.get("backend_usd"),
            "total_usd": summary.get("total_usd"),
            "latency_s": (None if summary.get("latency_ms") is None
                          else summary["latency_ms"] / 1000),
        })
    return rows


def gap_rows(cells: dict) -> List[dict]:
    rows = []
    for model in MODELS:
        for other in OTHERS:
            for dimension in pa.DIMENSIONS:
                base = {"model": model, "vs": other, "scope": BACKEND,
                        "dimension": dimension}
                for level in LEVELS:
                    rows.append({**base, "contrast": f"H{level}",
                                 **pa.gap(cells, model, other, level,
                                          dimension, (BACKEND,))})
                rows.append({**base, "contrast": "H2-H0",
                             **pa.did(cells, model, other, 2, 0, dimension,
                                      (BACKEND,))})
    return rows


def read_reference(path: str) -> List[dict]:
    """The pilot's gaps (``pilot_analysis --csv-dir``'s ``gaps.csv``)."""
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in ("mean", "ci_low", "ci_high"):
            row[key] = float(row[key]) if row.get(key) else None
    return rows


def _sign(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return (value > 0) - (value < 0)


def readings(gaps: List[dict],
             reference: Optional[List[dict]] = None) -> List[dict]:
    """Per model, other locus and primary dimension: whether the H = 0
    interval holds 0 (``h0_tie``), the sign of the H = 2 mean, the
    pilot's H = 2 means per scope, and whether the sign is the pilot's
    in every scope (``same_direction``; None without a reference)."""
    out = []
    for model in MODELS:
        for other in OTHERS:
            for dimension in pa.PRIMARY:
                pick = {r["contrast"]: r for r in gaps
                        if r["model"] == model and r["vs"] == other
                        and r["dimension"] == dimension}
                h0, h2 = pick["H0"], pick["H2"]
                pilot = {r["scope"]: r["mean"] for r in reference or []
                         if r["model"] == model and r["vs"] == other
                         and r["dimension"] == dimension
                         and r["contrast"] == "H2"
                         and r["mean"] is not None}
                sign = _sign(h2["mean"])
                out.append({
                    "model": model, "vs": other, "dimension": dimension,
                    "h0": h0, "h2": h2,
                    "h0_tie": (h0["mean"] is not None
                               and h0["ci_low"] <= 0 <= h0["ci_high"]),
                    "h2_sign": sign,
                    "pilot_h2": pilot,
                    "same_direction": (
                        None if not pilot or sign is None
                        else sign != 0 and all(
                            _sign(m) == sign for m in pilot.values())),
                })
    return out


def markdown(problems, cell_table, costs, gaps, reads) -> str:
    expected = len(MODELS) * len(CELLS) * len(LEVELS) * pa.USERS
    out = ["## Pairing and completeness", ""]
    out += ([f"- {p}" for p in problems] if problems
            else [f"- {expected} trials expected; every cell complete, "
                  "paired (same inputs and variants per user), on the "
                  "schedule, at one clean commit pair."])
    out += ["", "## Cells", "",
            pa.table(cell_table, ["model", "locus", "backend", "level", "n",
                                  "failed", "profile", "task",
                                  "integration", "leak_rate",
                                  "missing_rate", "facts_in_block"]),
            "", "## Cost and latency (per user)", "",
            pa.table(costs, ["model", "locus", "level", "n",
                             "backend_calls", "backend_usd", "total_usd",
                             "latency_s"],
                     {k: (lambda v: "" if v is None else f"{v:.4f}")
                      for k in ("backend_usd", "total_usd")}),
            "", "## Kernel − replicated and kernel − native "
            "(mean [95% CI])", ""]
    for model in MODELS:
        for other in OTHERS:
            out += [f"### {model}: kernel − {other}", "",
                    "| dimension | H0 | H2 | H2−H0 |", "|---|---|---|---|"]
            for dimension in pa.DIMENSIONS:
                pick = {r["contrast"]: r for r in gaps
                        if r["model"] == model and r["vs"] == other
                        and r["dimension"] == dimension}
                out.append(f"| {dimension} | " + " | ".join(
                    pa.ci(pick[c]) for c in ("H0", "H2", "H2-H0")) + " |")
            out.append("")
    out += ["## Readings (reported, not required)", "",
            "`h0_tie`: the H = 0 interval holds 0. `same_direction`: the "
            "H = 2 mean has the sign of the pilot's H = 2 mean in every "
            "scope (pooled, Mem0, in-house; Subtask 11).", "",
            "| model | vs | dimension | H0 | h0_tie | H2 | pilot H2 | "
            "same_direction |", "|---|---|---|---|---|---|---|---|"]
    for r in reads:
        pilot = ", ".join(f"{s} {m:+.2f}" for s, m in
                          sorted(r["pilot_h2"].items()))
        same = "" if r["same_direction"] is None else r["same_direction"]
        out.append(f"| {r['model']} | {r['vs']} | {r['dimension']} | "
                   f"{pa.ci(r['h0'])} | {r['h0_tie']} | {pa.ci(r['h2'])} | "
                   f"{pilot} | {same} |")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--schedule", default=str(PATH))
    parser.add_argument("--reference",
                        help="the pilot's gaps.csv (Subtask 11)")
    parser.add_argument("--markdown")
    parser.add_argument("--json")
    parser.add_argument("--csv-dir")
    args = parser.parse_args(argv)
    cells, metadata = load(Path(args.root))
    problems = pa.check_pairing(cells, metadata, Schedule(args.schedule))
    expected = len(MODELS) * len(CELLS) * len(LEVELS)
    if len(cells) < expected:
        problems.insert(0, f"{len(cells)} of {expected} cells present")
    prices = load_prices()
    cell_table = pa.cell_rows(cells, prices)
    costs = cost_rows(cells, prices)
    gaps = gap_rows(cells)
    reads = readings(gaps, read_reference(args.reference)
                     if args.reference else None)
    text = markdown(problems, cell_table, costs, gaps, reads)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text)
    if args.json:
        Path(args.json).write_text(json.dumps({
            "problems": problems, "readings": reads, "gaps": gaps,
            "cells": cell_table, "cost": costs,
        }, indent=1, default=str))
    if args.csv_dir:
        out = Path(args.csv_dir)
        pa.write_csv(out / "cells.csv", cell_table)
        pa.write_csv(out / "cost.csv", costs)
        pa.write_csv(out / "gaps.csv", gaps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
