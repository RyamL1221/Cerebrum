"""Compare a re-validation run against the workshop results.

Applies the rule pre-registered in AIOS docs/REVALIDATION.md and reports
what the injection diagnostics show. Reads each cell's results JSON from
``<dir>/<model>_<method>/results_<method>.json``.

    python -m benchmarks.shared_memory.revalidate \\
        --new results/revalidation --workshop results \\
        --csv results/revalidation/summary.csv
"""
import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from scipy import stats

MODELS = ("gpt4o", "llama", "qwen")
METHODS = ("kernel_shared", "mem0_default")
DIMENSIONS = {
    "profile": "profile_usage_score",
    "task": "task_usage_score",
    "integration": "integration_score",
}
CONFIDENCE = 0.95
ALPHA = 0.05
TOST_MARGIN = 0.25
MAX_SHIFT = 0.5
MIN_CELLS_PASSED = 7


def load_trials(directory: Path, model: str, method: str) -> list:
    """Load one cell's trials."""
    path = directory / f"{model}_{method}" / f"results_{method}.json"
    with open(path) as handle:
        return json.load(handle)["conditions"][0]["trials"]


def welch_df(a: list, b: list) -> float:
    """Return the Welch-Satterthwaite degrees of freedom."""
    va = statistics.variance(a) / len(a)
    vb = statistics.variance(b) / len(b)
    return (va + vb) ** 2 / (
        va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1)
    )


def tost_p(new: list, workshop: list, margin: float = TOST_MARGIN) -> float:
    """Return the two one-sided Welch tests' larger p-value.

    Equivalence holds when it is below ``ALPHA``. If both groups are
    constant the difference is exact, so the result is 0 or 1.
    """
    diff = statistics.mean(new) - statistics.mean(workshop)
    se = math.sqrt(
        statistics.variance(new) / len(new)
        + statistics.variance(workshop) / len(workshop)
    )
    if se == 0:
        return 0.0 if abs(diff) < margin else 1.0
    df = welch_df(new, workshop)
    lower = stats.t.sf((diff + margin) / se, df)
    upper = stats.t.cdf((diff - margin) / se, df)
    return float(max(lower, upper))


def workshop_ci(scores: list) -> tuple:
    """Return the two-sided t confidence interval of a workshop mean."""
    half = (
        stats.t.ppf(1 - (1 - CONFIDENCE) / 2, len(scores) - 1)
        * statistics.stdev(scores)
        / math.sqrt(len(scores))
    )
    mean = statistics.mean(scores)
    return mean - half, mean + half


def compare_cell(new: list, workshop: list) -> dict:
    """Apply the pre-registered cell rule to one model and dimension."""
    new_mean = statistics.mean(new)
    workshop_mean = statistics.mean(workshop)
    low, high = workshop_ci(workshop)
    p_tost = tost_p(new, workshop)
    in_ci = low <= new_mean <= high
    equivalent = p_tost < ALPHA
    if statistics.pstdev(new) == 0 and statistics.pstdev(workshop) == 0:
        p_welch = 1.0 if new_mean == workshop_mean else 0.0
    else:
        p_welch = float(
            stats.ttest_ind(new, workshop, equal_var=False).pvalue
        )
    return {
        "new_mean": new_mean,
        "new_sd": statistics.stdev(new),
        "workshop_mean": workshop_mean,
        "workshop_sd": statistics.stdev(workshop),
        "ci_low": low,
        "ci_high": high,
        "diff": new_mean - workshop_mean,
        "welch_p": p_welch,
        "tost_p": p_tost,
        "in_ci": in_ci,
        "equivalent": equivalent,
        "passed": in_ci or equivalent,
    }


def condition_verdict(cells: list) -> dict:
    """Apply the pre-registered condition rule to all cells."""
    passed = sum(cell["passed"] for cell in cells)
    max_shift = max(abs(cell["diff"]) for cell in cells)
    return {
        "cells_passed": passed,
        "max_shift": max_shift,
        "reproduces": (
            passed >= MIN_CELLS_PASSED and max_shift <= MAX_SHIFT
        ),
    }


def diagnostics_report(trials: list) -> dict:
    """Summarize a cell's injection diagnostics."""
    diagnostics = [t.get("injection_diagnostics") for t in trials]
    present = [d for d in diagnostics if d]
    return {
        "trials": len(trials),
        "failed": sum(1 for t in trials if t.get("failed")),
        "with_diagnostics": len(present),
        "confirmed": sum(
            1 for t in trials
            if (t.get("retrieval_log") or {}).get("injection_status")
            == "confirmed"
        ),
        "scores_present": sum(d["scores_present"] for d in present),
        "after_visibility_nonzero": sum(
            1 for d in present if d["after_visibility"] > 0
        ),
        "injected_nonzero": sum(
            1 for d in present if d["injected_count"] > 0
        ),
        "cap_bound": sum(
            1 for d in present if d["after_threshold"] > d["after_cap"]
        ),
        "budget_bound": sum(
            1 for d in present if d["after_cap"] > d["after_budget"]
        ),
        "after_cap": dict(sorted(
            Counter(d["after_cap"] for d in present).items()
        )),
        "after_budget": dict(sorted(
            Counter(d["after_budget"] for d in present).items()
        )),
    }


def mean_latency(trials: list) -> float:
    """Return a cell's mean assistant latency."""
    return statistics.mean(t["latency_seconds"] for t in trials)


def scores(trials: list, field: str) -> list:
    """Return one judge dimension of the completed trials."""
    return [t[field] for t in trials if not t.get("failed")]


def analyze(new_dir: Path, workshop_dir: Path, method: str) -> list:
    """Compare every model and dimension of one method."""
    rows = []
    for model in MODELS:
        new = load_trials(new_dir, model, method)
        workshop = load_trials(workshop_dir, model, method)
        for name, field in DIMENSIONS.items():
            rows.append({
                "method": method,
                "model": model,
                "dimension": name,
                **compare_cell(scores(new, field), scores(workshop, field)),
            })
    return rows


def main() -> None:
    """Print the comparison and write the summary CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--workshop", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()

    all_rows = []
    for method in METHODS:
        rows = analyze(args.new, args.workshop, method)
        all_rows.extend(rows)
        print(f"\n## {method}")
        for row in rows:
            print(
                f"{row['model']:6} {row['dimension']:11} "
                f"new {row['new_mean']:.3f}±{row['new_sd']:.3f}  "
                f"workshop {row['workshop_mean']:.3f}"
                f"±{row['workshop_sd']:.3f}  "
                f"diff {row['diff']:+.3f}  "
                f"Welch p={row['welch_p']:.4f}  "
                f"TOST p={row['tost_p']:.4f}  "
                f"{'pass' if row['passed'] else 'FAIL'}"
            )
        print("verdict:", condition_verdict(rows))

    print("\n## diagnostics and latency")
    for method in METHODS:
        for model in MODELS:
            trials = load_trials(args.new, model, method)
            workshop = load_trials(args.workshop, model, method)
            print(
                f"{model} {method}: latency "
                f"{mean_latency(trials):.2f}s "
                f"(workshop {mean_latency(workshop):.2f}s) "
                f"{diagnostics_report(trials)}"
            )

    if args.csv:
        with open(args.csv, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
            writer.writeheader()
            writer.writerows(all_rows)


if __name__ == "__main__":
    main()
