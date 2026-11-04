"""Compare replicated-logic cells with kernel cells on the same backend.

For each backend and model, pairs ``replicated_<backend>`` with the
``kernel_shared`` cell run against the same backend, and reports per
judge dimension the means, the difference (replicated - kernel), Welch
and TOST p-values and the pre-registered cell rule (``revalidate``).
A replicated-over-kernel gap above ``GAP`` is flagged: the design
predicts a tie on this benchmark (AIOS docs/REPLICATED_LOGIC.md).
Also checks every trial's ``locus`` and that kernel and replicated
trials ran the same ``pipeline_version``.

    python -m benchmarks.shared_memory.locus_compare results/locus_smoke \\
        --csv results/locus_smoke/summary.csv
"""
import argparse
import csv
import statistics
from collections import Counter
from pathlib import Path

from benchmarks.shared_memory.revalidate import (
    DIMENSIONS,
    MODELS,
    compare_cell,
    load_trials,
    scores,
)

GAP = 0.25
PAIRS = {
    "mem0": ("kernel_mem0", "replicated_mem0"),
    "inhouse": ("kernel_inhouse", "replicated_inhouse"),
}


def cell_checks(trials: list, locus: str) -> dict:
    """Locus, version, failures and injected types of one cell."""
    done = [t for t in trials if not t.get("failed")]
    return {
        "failed": len(trials) - len(done),
        "locus_ok": all(t.get("locus") == locus for t in trials),
        "versions": sorted({t.get("pipeline_version") for t in trials},
                           key=str),
        "injected": dict(Counter(
            tuple(m["memory_type"] for m in
                  (t.get("injection_diagnostics") or {})
                  .get("injected_memories", []))
            for t in done
        )),
        "latency": statistics.mean(t["latency_seconds"] for t in done),
    }


def analyze(root: Path) -> tuple:
    rows, checks = [], {}
    for backend, (kernel_dir, replicated_dir) in PAIRS.items():
        for model in MODELS:
            kernel = load_trials(root / kernel_dir, model, "kernel_shared")
            method = f"replicated_{backend}"
            replicated = load_trials(root / replicated_dir, model, method)
            checks[(backend, model)] = {
                "kernel": cell_checks(kernel, "kernel"),
                "replicated": cell_checks(replicated, "replicated"),
            }
            for name, field in DIMENSIONS.items():
                cell = compare_cell(
                    scores(replicated, field), scores(kernel, field)
                )
                rows.append({
                    "backend": backend,
                    "model": model,
                    "dimension": name,
                    "replicated_mean": cell["new_mean"],
                    "replicated_sd": cell["new_sd"],
                    "kernel_mean": cell["workshop_mean"],
                    "kernel_sd": cell["workshop_sd"],
                    "diff": cell["diff"],
                    "welch_p": cell["welch_p"],
                    "tost_p": cell["tost_p"],
                    "passed": cell["passed"],
                    "flag_replicated_over_kernel": cell["diff"] > GAP,
                })
    return rows, checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()
    rows, checks = analyze(args.root)
    for row in rows:
        print(
            f"{row['backend']:7} {row['model']:6} {row['dimension']:11} "
            f"replicated {row['replicated_mean']:.3f} "
            f"kernel {row['kernel_mean']:.3f} diff {row['diff']:+.3f} "
            f"Welch p={row['welch_p']:.3f} TOST p={row['tost_p']:.3f} "
            f"{'pass' if row['passed'] else 'FAIL'}"
            f"{'  FLAG' if row['flag_replicated_over_kernel'] else ''}"
        )
    for key, value in checks.items():
        print(key, value)
    versions = {
        v for c in checks.values() for side in c.values()
        for v in side["versions"]
    }
    print("pipeline versions:", versions)
    if args.csv:
        with open(args.csv, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
