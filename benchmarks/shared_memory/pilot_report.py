"""Report the pilot_v1 re-baseline (Subtask 9).

Reads ``<root>/{kmem0,kinh,agent}/<model>_<method>/results_<method>.json``
as ``scripts/run_pilot_baseline.sh`` (AIOS) writes them, and prints, per
model, every cell's means, writer failures, backend extraction and
cost (``cost.py``), and the paired locus comparisons per backend:
replicated − kernel_shared and native − kernel_shared (``compare.py``).

    python -m benchmarks.shared_memory.pilot_report results/pilot_v1 \\
        --csv results/pilot_v1/paired.csv --cells-csv results/pilot_v1/cells.csv
"""
import argparse
import csv
import json
from pathlib import Path

from benchmarks.shared_memory import compare
from benchmarks.shared_memory.cost import cell_summary, load_prices

MODELS = ("gpt4o", "qwen", "llama")
CELLS = {
    # (phase, method): (backend, label)
    ("kmem0", "kernel_shared"): ("mem0", "kernel_shared"),
    ("kmem0", "kernel_private"): ("mem0", "kernel_private"),
    ("agent", "replicated_mem0"): ("mem0", "replicated"),
    ("agent", "native_mem0"): ("mem0", "native"),
    ("kinh", "kernel_shared"): ("inhouse", "kernel_shared"),
    ("kinh", "kernel_private"): ("inhouse", "kernel_private"),
    ("agent", "replicated_inhouse"): ("inhouse", "replicated"),
    ("agent", "native_inhouse"): ("inhouse", "native"),
    ("agent", "naive_concat"): ("none", "naive_concat"),
    ("agent", "vanilla_rag"): ("none", "vanilla_rag"),
}
COMPARISONS = [
    (backend, other)
    for backend in ("mem0", "inhouse")
    for other in ("replicated", "native")
]


def cell_path(root: Path, phase: str, method: str, model: str) -> Path:
    return root / phase / f"{model}_{method}" / f"results_{method}.json"


def cells(root: Path, model: str) -> dict:
    """``(backend, label) -> results path`` for the cells present."""
    found = {}
    for (phase, method), key in CELLS.items():
        path = cell_path(root, phase, method, model)
        if path.exists():
            found[key] = path
    return found


def cell_rows(root: Path, prices: dict) -> list:
    rows = []
    for model in MODELS:
        for (backend, label), path in cells(root, model).items():
            trials = json.loads(path.read_text())["conditions"][0]["trials"]
            writer_failed = [t for t in trials if t.get("writer_failed")]
            retried = sum(
                1 for t in trials
                if any((t.get("writer_retries") or {}).values())
            )
            extraction = sorted(
                {str(t.get("backend_extraction")) for t in trials}
            )
            summary = cell_summary(trials, prices)
            rows.append({
                "model": model, "backend": backend, "cell": label,
                "trials": len(trials),
                "writer_failed": len(writer_failed),
                "writer_failed_agents": json.dumps(sorted({
                    a for t in writer_failed for a in t["writer_failed"]
                })),
                "trials_with_writer_retries": retried,
                "other_failed": sum(
                    1 for t in trials
                    if t.get("failed") and not t.get("writer_failed")
                ),
                "backend_extraction": "/".join(extraction),
                **summary,
            })
    return rows


def paired_rows(root: Path) -> list:
    rows = []
    for model in MODELS:
        found = cells(root, model)
        for backend, other in COMPARISONS:
            base = found.get((backend, "kernel_shared"))
            path = found.get((backend, other))
            if not base or not path:
                continue
            label = f"{model} {backend}: {other} - kernel_shared"
            rows += compare.rows(label, compare.compare(base, path))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--cells-csv", type=Path)
    args = parser.parse_args()
    prices = load_prices()
    cells_out = cell_rows(args.root, prices)
    for row in cells_out:
        print(
            f"{row['model']:6} {row['backend']:8} {row['cell']:15} "
            f"n={row['n']:2} writer_failed={row['writer_failed']} "
            f"retried={row['trials_with_writer_retries']} "
            f"bx={row['backend_extraction']} "
            f"P/T/I {row['profile_usage_mean'] or 0:.2f}/"
            f"{row['task_usage_mean'] or 0:.2f}/"
            f"{row['integration_mean'] or 0:.2f} "
            f"tokens {row['total_tokens'] or 0:,.0f} "
            f"usd {row['total_usd'] or 0:.4f} "
            f"latency {row['latency_ms'] or 0:,.0f} ms"
        )
    paired = paired_rows(args.root)
    for row in paired:
        print(
            f"{row['comparison']:42} {row['dimension']:11} "
            f"n={row['pairs']} diff {row['diff']:+.2f} "
            f"[{row['ci_low']:+.2f}, {row['ci_high']:+.2f}] "
            f"t p={row['t_p']:.3f} W p={row['wilcoxon_p']:.3f} "
            f"TOST p={row['tost_p']:.3f} excluded {row['excluded']}"
        )
    for path, out in ((args.cells_csv, cells_out), (args.csv, paired)):
        if path and out:
            with open(path, "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(out[0]))
                writer.writeheader()
                writer.writerows(out)


if __name__ == "__main__":
    main()
