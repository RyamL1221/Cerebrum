"""Compare two judgings of the same responses, trial by trial.

For each model, condition and dimension: both means, their difference,
Spearman's rho between the per-trial scores and the share of trials whose
score moved by more than one point. Trials are paired by ``trial_index``.

    python -m benchmarks.shared_memory.judge_compare \\
        --old results/revalidation --new results/revalidation_v2 \\
        --csv results/revalidation_v2/judge_comparison.csv
"""
import argparse
import csv
import math
import statistics
from pathlib import Path

from scipy import stats

from benchmarks.shared_memory.revalidate import (
    DIMENSIONS,
    METHODS,
    MODELS,
    load_trials,
)

MAX_SHIFT = 0.25


def paired(old: list, new: list, field: str) -> list:
    """Return (old, new) score pairs of trials completed in both."""
    by_index = {t["trial_index"]: t for t in new if not t.get("failed")}
    return [
        (t[field], by_index[t["trial_index"]][field])
        for t in old
        if not t.get("failed") and t["trial_index"] in by_index
    ]


def compare(pairs: list) -> dict:
    """Summarize one cell's score pairs. Rho is None when either side
    is constant."""
    old = [a for a, _ in pairs]
    new = [b for _, b in pairs]
    rho = None
    if len(set(old)) > 1 and len(set(new)) > 1:
        rho = float(stats.spearmanr(old, new).statistic)
    old_mean = statistics.mean(old)
    new_mean = statistics.mean(new)
    return {
        "n": len(pairs),
        "old_mean": old_mean,
        "new_mean": new_mean,
        "diff": new_mean - old_mean,
        "rho": rho,
        "changed_over_1": sum(abs(b - a) > 1 for a, b in pairs) / len(pairs),
        "exact_agreement": sum(a == b for a, b in pairs) / len(pairs),
    }


def main() -> None:
    """Print the comparison and optionally write it as CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()

    rows = []
    for method in METHODS:
        for model in MODELS:
            old = load_trials(args.old, model, method)
            new = load_trials(args.new, model, method)
            for name, field in DIMENSIONS.items():
                row = {"method": method, "model": model, "dimension": name,
                       **compare(paired(old, new, field))}
                rows.append(row)
                rho = "n/a" if row["rho"] is None else f"{row['rho']:.3f}"
                flag = " SHIFT>0.25" if abs(row["diff"]) > MAX_SHIFT else ""
                print(
                    f"{method:14} {model:6} {name:11} n={row['n']} "
                    f"old {row['old_mean']:.3f} new {row['new_mean']:.3f} "
                    f"diff {row['diff']:+.3f} rho {rho} "
                    f">1pt {row['changed_over_1']:.1%} "
                    f"same {row['exact_agreement']:.1%}{flag}"
                )
    if args.csv:
        with open(args.csv, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
