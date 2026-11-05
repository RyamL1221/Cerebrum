"""Paired comparison of two cells run on the same fixed dataset.

Two cells of the same dataset (``--dataset users_v1`` / ``pilot_v1``)
score the same users, trial ``i`` being user ``i``. For each judge
dimension this reports the per-user difference ``b - a``: its mean, a
95% t confidence interval, the paired t test, the Wilcoxon signed-rank
test (zero differences dropped; ``n_nonzero`` is how many remain), and
the paired TOST against the ±0.25 equivalence margin. A user is dropped
from the pairs when either cell failed it (counted per reason). Cells of
different datasets, or a user whose inputs differ between the cells,
are an error.

    python -m benchmarks.shared_memory.compare \\
        results/pilot/kernel_inhouse/llama_kernel_shared/results_kernel_shared.json \\
        results/pilot/replicated_inhouse/llama_replicated_inhouse/results_replicated_inhouse.json
"""
import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from scipy import stats

DIMENSIONS = {
    "profile": "profile_usage_score",
    "task": "task_usage_score",
    "integration": "integration_score",
}
CONFIDENCE = 0.95
MARGIN = 0.25


def load_cell(path: Path) -> tuple:
    """``(dataset, trials)`` of a results file, or of the one results
    file in a cell directory."""
    if path.is_dir():
        files = sorted(path.glob("results_*.json"))
        if len(files) != 1:
            raise ValueError(f"{path}: expected one results_*.json")
        path = files[0]
    data = json.loads(path.read_text())
    trials = [t for c in data["conditions"] for t in c["trials"]]
    return data["experiment_metadata"].get("dataset"), trials


def failure_reason(trial: dict) -> str:
    if trial.get("writer_failed"):
        return "writer_failed"
    message = trial.get("error_message") or ""
    return "judge_failed" if message.startswith("judge") else "failed"


def pair_trials(a: list, b: list) -> tuple:
    """``(pairs, excluded)``: the users both cells scored, as
    ``(trial_a, trial_b)`` by trial index, and a count of users dropped
    per reason."""
    by_a = {t["trial_index"]: t for t in a}
    by_b = {t["trial_index"]: t for t in b}
    pairs, excluded = [], Counter()
    for index in sorted(set(by_a) | set(by_b)):
        ta, tb = by_a.get(index), by_b.get(index)
        if ta is None or tb is None:
            excluded["missing"] += 1
            continue
        ha, hb = ta.get("input_sha256"), tb.get("input_sha256")
        if ha and hb and ha != hb:
            raise ValueError(f"user {index}: the two cells' inputs differ")
        failed = [t for t in (ta, tb) if t.get("failed")]
        if failed:
            for reason in {failure_reason(t) for t in failed}:
                excluded[reason] += 1
            continue
        pairs.append((ta, tb))
    return pairs, dict(excluded)


def paired_tost_p(diffs: list, margin: float = MARGIN) -> float:
    """The larger p-value of the two one-sided paired t tests that the
    mean difference lies within ±margin."""
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    if sd == 0:
        return 0.0 if abs(mean) < margin else 1.0
    se = sd / math.sqrt(len(diffs))
    df = len(diffs) - 1
    lower = stats.t.sf((mean + margin) / se, df)
    upper = stats.t.cdf((mean - margin) / se, df)
    return float(max(lower, upper))


def paired_stats(a: list, b: list) -> dict:
    """The paired statistics of ``b - a`` for two score lists."""
    diffs = [y - x for x, y in zip(a, b)]
    n = len(diffs)
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    if sd == 0:
        low = high = mean
        t_p = 1.0 if mean == 0 else 0.0
    else:
        half = (stats.t.ppf(1 - (1 - CONFIDENCE) / 2, n - 1)
                * sd / math.sqrt(n))
        low, high = mean - half, mean + half
        t_p = float(stats.ttest_rel(b, a).pvalue)
    nonzero = [d for d in diffs if d != 0]
    w_p = float(stats.wilcoxon(nonzero).pvalue) if nonzero else 1.0
    return {
        "n": n,
        "mean_a": statistics.mean(a),
        "mean_b": statistics.mean(b),
        "diff": mean,
        "sd_diff": sd,
        "ci_low": low,
        "ci_high": high,
        "t_p": t_p,
        "wilcoxon_p": w_p,
        "n_nonzero": len(nonzero),
        "tost_p": paired_tost_p(diffs) if n > 1 else 1.0,
    }


def compare(a_path: Path, b_path: Path) -> dict:
    """Paired statistics per dimension for cell ``b`` minus cell ``a``."""
    dataset_a, a = load_cell(a_path)
    dataset_b, b = load_cell(b_path)
    if not dataset_a or not dataset_b:
        raise ValueError("both cells must be run on a fixed dataset")
    if dataset_a["sha256"] != dataset_b["sha256"]:
        raise ValueError("the cells were run on different datasets")
    pairs, excluded = pair_trials(a, b)
    if len(pairs) < 2:
        raise ValueError(f"only {len(pairs)} paired users")
    return {
        "dataset": dataset_a["name"],
        "pairs": len(pairs),
        "excluded": excluded,
        "dimensions": {
            name: paired_stats([ta[field] for ta, _ in pairs],
                               [tb[field] for _, tb in pairs])
            for name, field in DIMENSIONS.items()
        },
    }


def rows(label: str, result: dict) -> list:
    """CSV rows of one comparison."""
    return [
        {"comparison": label, "dimension": name, "pairs": result["pairs"],
         "excluded": json.dumps(result["excluded"], sort_keys=True),
         **cell}
        for name, cell in result["dimensions"].items()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--label", default="b - a")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    result = compare(args.a, args.b)
    print(f"{args.label}: {result['pairs']} paired users of "
          f"{result['dataset']}, excluded {result['excluded']}")
    for name, cell in result["dimensions"].items():
        print(
            f"  {name:11} a {cell['mean_a']:.2f} b {cell['mean_b']:.2f} "
            f"diff {cell['diff']:+.2f} [{cell['ci_low']:+.2f}, "
            f"{cell['ci_high']:+.2f}] t p={cell['t_p']:.3f} "
            f"Wilcoxon p={cell['wilcoxon_p']:.3f} "
            f"(n≠0 {cell['n_nonzero']}) TOST p={cell['tost_p']:.3f}"
        )
    if args.csv:
        with open(args.csv, "w", newline="") as handle:
            out = rows(args.label, result)
            writer = csv.DictWriter(handle, fieldnames=list(out[0]))
            writer.writeheader()
            writer.writerows(out)


if __name__ == "__main__":
    main()
