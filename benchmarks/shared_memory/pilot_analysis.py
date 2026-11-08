"""Analyze the pre-registered locus x heterogeneity pilot (NeurIPS
Subtask 11, AIOS docs/PILOT.md).

Reads ``<root>/<model>/<phase>/h<H>_<method>/results_<method>.json`` as
AIOS ``scripts/run_pilot_v1.sh`` writes them and reports:

- per cell: score means, judge-free rates, failures, cost;
- paired kernel - replicated (and kernel - native) per backend and
  pooled over backends, per H, with 95% t-intervals over users;
- the difference-in-differences across H (H2 - H0, H1 - H0);
- the H = 1 per-variant breakdown;
- the verdict, by PILOT.md's operational reading of the rule.

    python -m benchmarks.shared_memory.pilot_analysis results/pilot_v1_hetero \\
        --markdown results/pilot_v1_hetero/analysis.md \\
        --json results/pilot_v1_hetero/analysis.json \\
        --csv-dir results/pilot_v1_hetero
"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scipy import stats

from benchmarks.shared_memory.cost import cell_summary, load_prices
from benchmarks.shared_memory.pilot_schedule import Schedule, PATH

MODELS = ("qwen", "gpt4o")
LEVELS = (0, 1, 2)
BACKENDS = ("mem0", "inhouse")
LOCI = ("kernel", "replicated", "native")
DIMENSIONS = {"profile": "profile_usage_score",
              "task": "task_usage_score",
              "integration": "integration_score"}
PRIMARY = ("profile", "integration")
CONFIDENCE = 0.95
GO_MARGIN = 0.25
USERS = 30
# (locus, backend) -> (phase, method)
CELLS = {
    ("kernel", "mem0"): ("kmem0", "kernel_shared"),
    ("kernel", "inhouse"): ("kinh", "kernel_shared"),
    ("replicated", "mem0"): ("agent", "replicated_mem0"),
    ("replicated", "inhouse"): ("agent", "replicated_inhouse"),
    ("native", "mem0"): ("agent", "native_mem0"),
    ("native", "inhouse"): ("agent", "native_inhouse"),
}
LEAKS = ("cross_user_rows", "private_rows_from_others")


# -- loading ----------------------------------------------------------------

def cell_file(root: Path, model: str, locus: str, backend: str,
              level: int) -> Path:
    phase, method = CELLS[(locus, backend)]
    return root / model / phase / f"h{level}_{method}" / f"results_{method}.json"


def load(root: Path) -> Tuple[dict, dict]:
    """``(cells, metadata)``: ``cells[(model, locus, backend, H)]`` is the
    trials by index; ``metadata`` the same keys' experiment metadata."""
    cells, metadata = {}, {}
    for model in MODELS:
        for (locus, backend) in CELLS:
            for level in LEVELS:
                path = cell_file(root, model, locus, backend, level)
                if not path.exists():
                    continue
                data = json.loads(path.read_text())
                trials = data["conditions"][0]["trials"]
                key = (model, locus, backend, level)
                cells[key] = {t["trial_index"]: t for t in trials}
                metadata[key] = data["experiment_metadata"]
    return cells, metadata


def check_pairing(cells: dict, metadata: dict,
                  schedule: Optional[Schedule]) -> List[str]:
    """Problems with the pairing: inputs or variants that differ across
    cells for one user, a schedule other than the committed one, failed
    trials, dirty commits."""
    problems = []
    inputs = defaultdict(set)
    variants = defaultdict(set)
    commits = set()
    for key, trials in cells.items():
        meta = metadata[key]
        commits.add((meta.get("git_commit"), meta.get("kernel_git_commit")))
        het = meta.get("heterogeneity") or {}
        if schedule and het.get("schedule_sha256") != schedule.sha256:
            problems.append(f"{key}: schedule {het.get('schedule_sha256')}")
        for index, trial in trials.items():
            inputs[index].add(trial.get("input_sha256"))
            variants[(key[3], index)].add(
                json.dumps(trial.get("variants_applied") or {},
                           sort_keys=True))
            if trial.get("failed"):
                problems.append(f"{key} trial {index} failed: "
                                f"{trial.get('error_message')}")
        if len(trials) != USERS:
            problems.append(f"{key}: {len(trials)} trials")
    for index, found in inputs.items():
        if len(found) > 1:
            problems.append(f"user {index}: inputs differ across cells")
    for (level, index), found in variants.items():
        if len(found) > 1:
            problems.append(f"H{level} user {index}: variants differ")
        if schedule:
            want = json.dumps(schedule.variants(level, index),
                              sort_keys=True)
            if found != {want}:
                problems.append(f"H{level} user {index}: not the schedule")
    for harness, kernel in commits:
        for name, commit in (("harness", harness), ("kernel", kernel)):
            if not commit or commit.endswith("-dirty"):
                problems.append(f"{name} commit {commit}")
    if len(commits) > 1:
        problems.append(f"{len(commits)} different commit pairs")
    return problems


# -- statistics ---------------------------------------------------------------

def t_interval(values: List[float]) -> dict:
    """Mean and 95% t-interval of ``values``."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "ci_low": None, "ci_high": None}
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    if sd == 0:
        low = high = mean
    else:
        half = stats.t.ppf(1 - (1 - CONFIDENCE) / 2, n - 1) * sd / math.sqrt(n)
        low, high = mean - half, mean + half
    return {"n": n, "mean": mean, "ci_low": low, "ci_high": high}


def score(trial: Optional[dict], dimension: str) -> Optional[float]:
    if not trial or trial.get("failed"):
        return None
    return trial.get(DIMENSIONS[dimension])


def user_gaps(cells: dict, model: str, other: str, level: int,
              dimension: str, backends=BACKENDS) -> Dict[int, float]:
    """Per user: kernel - other, averaged over ``backends`` (a user
    missing in any is dropped)."""
    out = {}
    for index in range(USERS):
        diffs = []
        for backend in backends:
            k = score(cells.get((model, "kernel", backend, level), {})
                      .get(index), dimension)
            o = score(cells.get((model, other, backend, level), {})
                      .get(index), dimension)
            if k is None or o is None:
                break
            diffs.append(k - o)
        else:
            out[index] = statistics.mean(diffs)
    return out


def gap(cells, model, other, level, dimension, backends=BACKENDS) -> dict:
    return t_interval(list(
        user_gaps(cells, model, other, level, dimension, backends).values()
    ))


def did(cells, model, other, high, low, dimension,
        backends=BACKENDS) -> dict:
    """Per user (gap at ``high``) - (gap at ``low``)."""
    a = user_gaps(cells, model, other, high, dimension, backends)
    b = user_gaps(cells, model, other, low, dimension, backends)
    return t_interval([a[i] - b[i] for i in sorted(set(a) & set(b))])


def judge_free(trials: List[dict]) -> dict:
    done = [t for t in trials if not t.get("failed") and t.get("judge_free")]
    n = len(done)

    def rate(pred):
        return sum(1 for t in done if pred(t["judge_free"])) / n if n else None

    facts = [t["judge_free"].get("profile_facts_in_block") for t in done]
    facts = [f for f in facts if f is not None]
    return {
        "n": n,
        "leak_rate": rate(lambda m: sum(m.get(k) or 0 for k in LEAKS) > 0),
        "missing_rate": rate(lambda m: (m.get("memories_missing") or 0) > 0),
        "facts_in_block": statistics.mean(facts) if facts else None,
    }


def trials_of(cells, model, locus, backends=BACKENDS, levels=LEVELS):
    return [t for b in backends for h in levels
            for t in cells.get((model, locus, b, h), {}).values()]


# -- tables --------------------------------------------------------------------

def cell_rows(cells: dict, prices: dict) -> List[dict]:
    rows = []
    for (model, locus, backend, level), trials in sorted(cells.items()):
        values = list(trials.values())
        summary = cell_summary(values, prices)
        free = judge_free(values)
        rows.append({
            "model": model, "locus": locus, "backend": backend,
            "level": level, "n": summary["n"],
            "failed": sum(1 for t in values if t.get("failed")),
            "profile": summary.get("profile_usage_mean"),
            "task": summary.get("task_usage_mean"),
            "integration": summary.get("integration_mean"),
            "leak_rate": free["leak_rate"],
            "missing_rate": free["missing_rate"],
            "facts_in_block": free["facts_in_block"],
            "total_usd": summary.get("total_usd"),
            "total_tokens": summary.get("total_tokens"),
            "latency_ms": summary.get("latency_ms"),
        })
    return rows


def gap_rows(cells: dict) -> List[dict]:
    rows = []
    for model in MODELS:
        for other in ("replicated", "native"):
            for scope, backends in (("pooled", BACKENDS),
                                    ("mem0", ("mem0",)),
                                    ("inhouse", ("inhouse",))):
                for dimension in DIMENSIONS:
                    for level in LEVELS:
                        g = gap(cells, model, other, level, dimension,
                                backends)
                        rows.append({"model": model, "vs": other,
                                     "scope": scope, "dimension": dimension,
                                     "contrast": f"H{level}", **g})
                    for high in (1, 2):
                        d = did(cells, model, other, high, 0, dimension,
                                backends)
                        rows.append({"model": model, "vs": other,
                                     "scope": scope, "dimension": dimension,
                                     "contrast": f"H{high}-H0", **d})
    return rows


def variant_rows(cells: dict, schedule: Schedule) -> List[dict]:
    """H = 1, by (role, variant): the pooled kernel - other gap and each
    locus's missing and leak rate over the variant's 3 users."""
    groups = defaultdict(list)
    for index in range(USERS):
        ((agent, code),) = schedule.variants(1, index).items()
        groups[(schedule.stratum(1, index), code)].append(index)
    rows = []
    for model in MODELS:
        for (role, code), users in sorted(groups.items()):
            row = {"model": model, "role": role, "variant": code,
                   "users": len(users)}
            for other in ("replicated", "native"):
                for dimension in PRIMARY:
                    gaps = user_gaps(cells, model, other, 1, dimension)
                    values = [gaps[i] for i in users if i in gaps]
                    row[f"k-{other[:3]}_{dimension}"] = (
                        statistics.mean(values) if values else None)
            for locus in LOCI:
                picked = [cells.get((model, locus, b, 1), {}).get(i)
                          for b in BACKENDS for i in users]
                free = judge_free([t for t in picked if t])
                row[f"{locus}_missing"] = free["missing_rate"]
                row[f"{locus}_leak"] = free["leak_rate"]
            rows.append(row)
    return rows


# -- the rule -------------------------------------------------------------------

def condition_iii(cells: dict, model: str) -> dict:
    kernel_all = judge_free(trials_of(cells, model, "kernel"))
    kernel = judge_free(trials_of(cells, model, "kernel", levels=(1, 2)))
    replicated = judge_free(
        trials_of(cells, model, "replicated", levels=(1, 2)))
    per_h = {
        h: (judge_free(trials_of(cells, model, "kernel", levels=(h,)))
            ["missing_rate"],
            judge_free(trials_of(cells, model, "replicated", levels=(h,)))
            ["missing_rate"])
        for h in (1, 2)
    }
    holds = (kernel_all["n"] > 0 and kernel_all["leak_rate"] == 0
             and kernel["missing_rate"] is not None
             and replicated["missing_rate"] is not None
             and kernel["missing_rate"] < replicated["missing_rate"])
    return {"holds": holds,
            "kernel_leak_rate": kernel_all["leak_rate"],
            "kernel_leak_n": kernel_all["n"],
            "kernel_missing_h12": kernel["missing_rate"],
            "replicated_missing_h12": replicated["missing_rate"],
            "missing_by_h": per_h}


def verdict(cells: dict) -> dict:
    """PILOT.md's operational reading of the rule, per model, then the
    outcome."""
    per_model = {}
    for model in MODELS:
        h2 = {d: gap(cells, model, "replicated", 2, d) for d in PRIMARY}
        dd = {d: did(cells, model, "replicated", 2, 0, d) for d in PRIMARY}
        i_dims = [d for d in PRIMARY
                  if h2[d]["mean"] is not None
                  and h2[d]["mean"] >= GO_MARGIN and h2[d]["ci_low"] > 0]
        i_ii_dims = [d for d in i_dims
                     if dd[d]["mean"] is not None and dd[d]["mean"] > 0
                     and dd[d]["ci_low"] > 0]
        iii = condition_iii(cells, model)
        per_model[model] = {
            "h2_gap": h2, "did_h2_h0": dd,
            "i_dimensions": i_dims, "i_and_ii_dimensions": i_ii_dims,
            "iii": iii,
            "h2_positive": any(h2[d]["mean"] is not None and h2[d]["mean"] > 0
                               for d in PRIMARY),
            "h2_nonpositive_both": all(
                h2[d]["mean"] is not None and h2[d]["mean"] <= 0
                for d in PRIMARY),
            "h2_ci_includes_0": all(
                h2[d]["ci_low"] is not None and h2[d]["ci_low"] <= 0
                <= h2[d]["ci_high"] for d in PRIMARY if h2[d]["mean"]
                is not None and h2[d]["mean"] > 0),
        }
    present = [m for m in MODELS if per_model[m]["iii"]["kernel_leak_n"]]
    iii_both = bool(present) and len(present) == len(MODELS) and all(
        per_model[m]["iii"]["holds"] for m in MODELS)
    go = iii_both and any(per_model[m]["i_and_ii_dimensions"]
                          for m in MODELS)
    conditional = (iii_both and not go and all(
        per_model[m]["h2_positive"] and per_model[m]["h2_ci_includes_0"]
        for m in MODELS))
    no_go = (not iii_both) or all(per_model[m]["h2_nonpositive_both"]
                                  for m in MODELS)
    if len(present) < len(MODELS):
        outcome = "INCOMPLETE"
    elif go:
        outcome = "GO"
    elif no_go:
        outcome = "NO-GO"
    elif conditional:
        outcome = "CONDITIONAL GO"
    else:
        outcome = "NO RULE OUTCOME"
    return {"outcome": outcome, "iii_both_models": iii_both,
            "per_model": per_model}


# -- output ------------------------------------------------------------------

def fmt(value, digits=2) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:+.{digits}f}" if digits == 2 else f"{value:.{digits}f}"
    return str(value)


def ci(row: dict) -> str:
    if row["mean"] is None:
        return ""
    return (f"{row['mean']:+.2f} [{row['ci_low']:+.2f}, "
            f"{row['ci_high']:+.2f}]")


COUNT_KEYS = ("level", "n", "failed")


def table(rows: List[dict], keys: List[str], formats=None) -> str:
    formats = formats or {}
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    def default(key):
        # A mean of integer scores can come back as an int; every value
        # column prints with two decimals, the count columns as is.
        def show(v):
            if v is None:
                return ""
            if isinstance(v, (int, float)) and not isinstance(v, bool) \
                    and key not in COUNT_KEYS:
                return f"{v:.2f}"
            return str(v)
        return show
    for row in rows:
        lines.append("| " + " | ".join(
            formats.get(k, default(k))(row.get(k)) for k in keys) + " |")
    return "\n".join(lines)


def markdown(cells, problems, gaps, variants, verdict_, cell_table) -> str:
    out = ["## Pairing and completeness", ""]
    out += ([f"- {p}" for p in problems] if problems
            else ["- 1,080 trials expected; every cell complete, paired "
                  "(same inputs and variants per user), on the schedule, "
                  "at one clean commit pair."])
    out += ["", "## Cells", "",
            table(cell_table, ["model", "locus", "backend", "level", "n",
                               "failed", "profile", "task", "integration",
                               "leak_rate", "missing_rate",
                               "facts_in_block", "total_usd"],
                  {"total_usd": lambda v: "" if v is None else f"{v:.4f}"}),
            "", "## Kernel − replicated and kernel − native (mean [95% CI])",
            ""]
    for other in ("replicated", "native"):
        for model in MODELS:
            out += [f"### {model}: kernel − {other}", "",
                    "| scope | dimension | H0 | H1 | H2 | H1−H0 | H2−H0 |",
                    "|---|---|---|---|---|---|---|"]
            for scope in ("pooled", "mem0", "inhouse"):
                for dimension in DIMENSIONS:
                    pick = {r["contrast"]: r for r in gaps
                            if r["model"] == model and r["vs"] == other
                            and r["scope"] == scope
                            and r["dimension"] == dimension}
                    out.append(f"| {scope} | {dimension} | " + " | ".join(
                        ci(pick[c]) for c in
                        ("H0", "H1", "H2", "H1-H0", "H2-H0")) + " |")
            out.append("")
    out += ["## H = 1 by variant (3 users each; pooled gaps, missing and "
            "leak rates over both backends)", "",
            table(variants, ["model", "role", "variant",
                             "k-rep_profile", "k-rep_integration",
                             "k-nat_profile", "k-nat_integration",
                             "kernel_missing", "replicated_missing",
                             "native_missing", "kernel_leak",
                             "replicated_leak", "native_leak"]), ""]
    out += ["## Verdict", "", f"**{verdict_['outcome']}**", ""]
    for model in MODELS:
        m = verdict_["per_model"][model]
        iii = m["iii"]
        out += [f"- {model}:",
                "  - (i) H = 2 pooled kernel − replicated: " + "; ".join(
                    f"{d} {ci(m['h2_gap'][d])}" for d in PRIMARY)
                + f" → (i) met on {m['i_dimensions'] or 'none'}.",
                "  - (ii) H2 − H0 DiD: " + "; ".join(
                    f"{d} {ci(m['did_h2_h0'][d])}" for d in PRIMARY)
                + f" → (i) and (ii) met on "
                f"{m['i_and_ii_dimensions'] or 'none'}.",
                f"  - (iii) kernel leak rate {fmt(iii['kernel_leak_rate'], 3)}"
                f" over {iii['kernel_leak_n']} trials; memories_missing at "
                f"H ≥ 1 kernel {fmt(iii['kernel_missing_h12'], 3)} vs "
                f"replicated {fmt(iii['replicated_missing_h12'], 3)} "
                f"(H1 {fmt(iii['missing_by_h'][1][0], 3)} vs "
                f"{fmt(iii['missing_by_h'][1][1], 3)}, H2 "
                f"{fmt(iii['missing_by_h'][2][0], 3)} vs "
                f"{fmt(iii['missing_by_h'][2][1], 3)}) → "
                f"{'holds' if iii['holds'] else 'fails'}."]
    return "\n".join(out) + "\n"


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    keys = list(rows[0])
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--schedule", default=str(PATH))
    parser.add_argument("--markdown")
    parser.add_argument("--json")
    parser.add_argument("--csv-dir")
    args = parser.parse_args(argv)
    root = Path(args.root)
    schedule = Schedule(args.schedule)
    cells, metadata = load(root)
    problems = check_pairing(cells, metadata, schedule)
    expected = len(MODELS) * len(CELLS) * len(LEVELS)
    if len(cells) < expected:
        problems.insert(0, f"{len(cells)} of {expected} cells present")
    cell_table = cell_rows(cells, load_prices())
    gaps = gap_rows(cells)
    variants = variant_rows(cells, schedule)
    verdict_ = verdict(cells)
    text = markdown(cells, problems, gaps, variants, verdict_, cell_table)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text)
    if args.json:
        Path(args.json).write_text(json.dumps({
            "problems": problems, "verdict": verdict_, "gaps": gaps,
            "variants": variants, "cells": cell_table,
        }, indent=1, default=str))
    if args.csv_dir:
        out = Path(args.csv_dir)
        write_csv(out / "cells.csv", cell_table)
        write_csv(out / "gaps.csv", gaps)
        write_csv(out / "variants_h1.csv", variants)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
