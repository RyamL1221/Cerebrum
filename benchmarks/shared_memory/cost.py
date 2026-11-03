"""Estimated cost per trial and per cell, and the efficiency metric.

Turns a trial's token counts into USD with the dated price table in
``prices.yaml``, split assistant / writers / backend-internal LLM /
embedding (the design reports backend-internal cost separately from the
assistant's), and summarizes cells: means of every token and latency
field, the cost split, and ``tokens_per_quality`` (mean total tokens
divided by the mean of the three judge scores).

    python -m benchmarks.shared_memory.cost results/cost_check \\
        --csv results/cost_check/summary.csv
"""
import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Dict, List, Optional

import yaml

PRICES = Path(__file__).with_name("prices.yaml")

# TrialResult field -> cost column prefix.
TOKEN_FIELDS = {
    "token_usage": "assistant",
    "writer_tokens": "writers",
    "backend_llm_tokens": "backend",
    "embedding_tokens": "embedding",
}
LATENCY_FIELDS = (
    "barrier_wait_ms", "search_ms", "select_ms", "format_ms",
    "kernel_overhead_ms", "llm_ms", "schedule_wait_ms",
)
SCORES = ("profile_usage_score", "task_usage_score", "integration_score")


def load_prices(path: Path = PRICES) -> dict:
    """The price table: ``{"as_of", "source", "models": {name: {"input",
    "output"}}}``, prices in USD per 1M tokens."""
    with open(path) as handle:
        table = yaml.safe_load(handle)
    for name, entry in table["models"].items():
        for key in ("input", "output"):
            if not isinstance(entry.get(key), (int, float)):
                raise ValueError(f"prices: {name}.{key} must be a number")
    return table


def price_usage(usage: dict, prices: dict) -> Optional[float]:
    """USD of one TokenUsage. 0 when it made no calls; None when its
    model is not in the table, or several models share the counts."""
    if not usage or not usage.get("calls"):
        return 0.0
    models = usage.get("models") or []
    if len(models) != 1 or models[0] not in prices["models"]:
        return None
    entry = prices["models"][models[0]]
    return (
        usage.get("prompt_tokens", 0) * entry["input"]
        + usage.get("completion_tokens", 0) * entry["output"]
    ) / 1_000_000


def trial_cost(trial: dict, prices: dict) -> Dict[str, Optional[float]]:
    """One trial's estimated USD per part and in total (None when a
    part cannot be priced)."""
    parts = {
        f"{prefix}_usd": price_usage(trial.get(field) or {}, prices)
        for field, prefix in TOKEN_FIELDS.items()
    }
    known = list(parts.values())
    parts["total_usd"] = (
        None if None in known else sum(known)
    )
    return parts


def total_tokens(trial: dict) -> int:
    return sum(
        (trial.get(field) or {}).get("total_tokens", 0)
        for field in TOKEN_FIELDS
    )


def _mean(values: List[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return statistics.mean(present) if present else None


def cell_summary(trials: List[dict], prices: dict) -> dict:
    """Means over a cell's completed trials."""
    done = [t for t in trials if not t.get("failed")]
    row: Dict[str, Optional[float]] = {"n": len(done)}
    for field, prefix in TOKEN_FIELDS.items():
        for key in ("calls", "prompt_tokens", "completion_tokens",
                    "total_tokens"):
            row[f"{prefix}_{key}"] = _mean(
                [(t.get(field) or {}).get(key) for t in done]
            )
    row["total_tokens"] = _mean([total_tokens(t) for t in done])
    for key in LATENCY_FIELDS:
        row[key] = _mean(
            [(t.get("latency_breakdown") or {}).get(key) for t in done]
        )
    row["latency_ms"] = _mean([
        t["latency_seconds"] * 1000 for t in done
        if t.get("latency_seconds") is not None
    ])
    costs = [trial_cost(t, prices) for t in done]
    for key in ("assistant_usd", "writers_usd", "backend_usd",
                "embedding_usd", "total_usd"):
        values = [c[key] for c in costs]
        row[key] = None if None in values else _mean(values)
    score_means = [
        _mean([t.get(field) for t in done]) for field in SCORES
    ]
    row.update({
        f"{field.replace('_score', '')}_mean": mean
        for field, mean in zip(SCORES, score_means)
    })
    quality = (
        None if None in score_means else statistics.mean(score_means)
    )
    row["tokens_per_quality"] = (
        row["total_tokens"] / quality
        if quality and row["total_tokens"] is not None else None
    )
    row["prices_as_of"] = prices["as_of"]
    return row


def summarize_dir(directory: Path, prices: dict) -> List[dict]:
    """One row per results file (``<cell>/results_<method>.json``)."""
    rows = []
    for path in sorted(Path(directory).glob("**/results_*.json")):
        with open(path) as handle:
            data = json.load(handle)
        for condition in data["conditions"]:
            rows.append({
                "cell": path.parent.name,
                "method": condition["condition"],
                **cell_summary(condition["trials"], prices),
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--prices", type=Path, default=PRICES)
    args = parser.parse_args()
    rows = summarize_dir(args.directory, load_prices(args.prices))
    for row in rows:
        print(json.dumps(row))
    if args.csv and rows:
        with open(args.csv, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
