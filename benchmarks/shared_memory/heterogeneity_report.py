"""The heterogeneity functional check (NeurIPS Subtask 10, AIOS
docs/HETEROGENEITY.md, "Functional verification").

Reads the results files of an unscored sweep (every locus x backend x H),
pairs each deviating trial with the same user's H = 0 trial in the same
cell, and reports what changed, judge-free:

    python -m benchmarks.shared_memory.heterogeneity_report <root> \\
        [--csv trials.csv] [--markdown table.md]

It then evaluates the design's checks per variant and prints each as
PASS or FINDING. A finding is a result to write down, not a bug.
"""
import argparse
import csv
import glob
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

LOCUS_BACKEND = {
    "replicated_mem0": ("replicated", "mem0"),
    "replicated_inhouse": ("replicated", "inhouse"),
    "native_mem0": ("native", "mem0"),
    "native_inhouse": ("native", "inhouse"),
}
LEAKS = ("cross_user_rows", "private_rows_from_others")
DELTAS = ("memories_missing", "raw_payload_rows")
COLUMNS = (
    "locus", "backend", "level", "trial_index", "variants",
    "not_applied", "missing", "d_missing", "cross_user_rows",
    "private_rows_from_others", "facts", "d_facts", "raw_payload_rows",
    "d_raw", "after_threshold", "d_after_threshold", "after_cap",
    "d_after_cap", "tokens", "d_tokens", "block_format", "threshold_used",
    "top_k_own",
)


def cell_of(metadata: dict, method: str) -> Tuple[str, str]:
    if method in LOCUS_BACKEND:
        return LOCUS_BACKEND[method]
    provider = (metadata.get("config_snapshot") or {}).get("provider", "")
    return "kernel", "mem0" if provider == "mem0" else "inhouse"


def load(root: str) -> Dict[tuple, dict]:
    """``(locus, backend, level, trial_index) -> trial``."""
    trials = {}
    paths = glob.glob(os.path.join(root, "**", "results_*.json"),
                      recursive=True)
    for path in sorted(paths):
        with open(path) as handle:
            data = json.load(handle)
        metadata = data["experiment_metadata"]
        level = (metadata.get("heterogeneity") or {}).get("level", 0)
        for condition in data["conditions"]:
            for trial in condition["trials"]:
                locus, backend = cell_of(metadata, trial["method"])
                key = (locus, backend, level, trial["trial_index"])
                if key in trials:
                    raise SystemExit(f"duplicate trial {key} in {path}")
                trials[key] = trial
    return trials


def _measures(trial: dict) -> dict:
    return trial.get("judge_free") or {}


def _diag(trial: dict) -> dict:
    return trial.get("injection_diagnostics") or {}


def _delta(a, b) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(a - b, 4)


def rows(trials: Dict[tuple, dict]) -> List[dict]:
    out = []
    for (locus, backend, level, index), trial in sorted(trials.items()):
        reference = trials.get((locus, backend, 0, index))
        m, d = _measures(trial), _diag(trial)
        rm = _measures(reference) if reference else {}
        rd = _diag(reference) if reference else {}
        out.append({
            "locus": locus, "backend": backend, "level": level,
            "trial_index": index,
            "variants": ",".join(
                f"{agent}={code}" for agent, code
                in sorted((trial.get("variants_applied") or {}).items())
            ),
            "not_applied": " | ".join(
                f"{agent}: {reason}" for agent, reason
                in sorted((trial.get("variants_not_applied") or {}).items())
            ),
            "failed": trial.get("failed", False),
            "missing": m.get("memories_missing"),
            "d_missing": _delta(m.get("memories_missing"),
                                rm.get("memories_missing")),
            "cross_user_rows": m.get("cross_user_rows"),
            "private_rows_from_others": m.get("private_rows_from_others"),
            "facts": m.get("profile_facts_in_block"),
            "d_facts": _delta(m.get("profile_facts_in_block"),
                              rm.get("profile_facts_in_block")),
            "raw_payload_rows": m.get("raw_payload_rows"),
            "d_raw": _delta(m.get("raw_payload_rows"),
                            rm.get("raw_payload_rows")),
            "after_threshold": d.get("after_threshold"),
            "d_after_threshold": _delta(d.get("after_threshold"),
                                        rd.get("after_threshold")),
            "after_cap": d.get("after_cap"),
            "d_after_cap": _delta(d.get("after_cap"), rd.get("after_cap")),
            "tokens": d.get("tokens_estimated"),
            "d_tokens": _delta(d.get("tokens_estimated"),
                               rd.get("tokens_estimated")),
            "block_format": d.get("block_format"),
            "threshold_used": d.get("threshold_used"),
            "top_k_own": (d.get("top_k_used") or {}).get("own"),
            "has_reference": reference is not None,
        })
    return out


def with_variant(table: List[dict], code: str, agent: Optional[str] = None):
    """Rows whose trial ran ``code`` (on ``agent`` if given)."""
    for row in table:
        applied = dict(
            pair.split("=") for pair in row["variants"].split(",") if pair
        )
        if any(c == code and (agent is None or a == agent)
               for a, c in applied.items()):
            yield row, applied


def _changed(row: dict) -> bool:
    return any((row.get(key) or 0) != 0 for key in (
        "d_missing", "d_facts", "d_raw", "d_after_threshold", "d_after_cap",
        "d_tokens",
    )) or any((row.get(key) or 0) != 0 for key in LEAKS)


def checks(table: List[dict]) -> List[Tuple[str, bool, str]]:
    """The design's checks: (name, passed, evidence)."""
    results = []

    def leaks(row):
        return sum(row.get(key) or 0 for key in LEAKS)

    for code in ("V2", "V3"):
        kernel = [r for r, _ in with_variant(table, code)
                  if r["locus"] == "kernel"]
        others = [r for r, _ in with_variant(table, code)
                  if r["locus"] != "kernel"]
        kernel_leaks = sum(leaks(r) for r in kernel)
        hit = [r for r in others
               if (r["d_missing"] or 0) > 0 or leaks(r) > 0]
        results.append((
            f"{code}: zero leaks under the kernel",
            kernel_leaks == 0 and bool(kernel),
            f"{len(kernel)} kernel trials, {kernel_leaks} leaked rows",
        ))
        results.append((
            f"{code}: missing or leak under at least one other locus",
            bool(hit),
            f"{len(hit)} of {len(others)} replicated/native trials",
        ))

    # V4 on the consumer: the kernel keeps its own settings (threshold
    # 0.0, own k 10) and records the variant as not applied; replicated
    # applies the agent's (0.5, k 5), and its cap or block size moves.
    single = [(r, a) for r, a in with_variant(table, "V4", "assistant_agent")]
    kernel = [r for r, a in single if r["locus"] == "kernel"]
    own = [r for r in kernel
           if r["threshold_used"] in (0.0, None) and r["top_k_own"] == 10
           and "assistant_agent: V4" in r["not_applied"]]
    results.append((
        "V4 consumer: the kernel keeps its own settings",
        bool(kernel) and len(own) == len(kernel),
        f"{len(own)} of {len(kernel)} kernel trials at threshold 0.0, "
        "k 10, recorded not applied",
    ))
    replicated = [r for r, a in single if r["locus"] == "replicated"]
    moved = [r for r in replicated if r["threshold_used"] == 0.5 and (
        (r["d_after_cap"] or 0) != 0 or (r["d_tokens"] or 0) != 0)]
    results.append((
        "V4 consumer: after_cap or block size changes under replicated",
        bool(replicated) and len(moved) == len(replicated),
        f"{len(moved)} of {len(replicated)} replicated trials",
    ))

    for locus in ("kernel", "replicated", "native"):
        for backend in ("inhouse", "mem0"):
            v5 = [r for r, a in with_variant(table, "V5")
                  if r["locus"] == locus and r["backend"] == backend
                  and any(c == "V5" and ag != "assistant_agent"
                          for ag, c in a.items())]
            raised = [r for r in v5 if (r["d_raw"] or 0) > 0]
            results.append((
                f"V5 writer: raw_payload_rows rises under {locus} "
                f"{backend}",
                bool(v5) and len(raised) == len(v5),
                f"{len(raised)} of {len(v5)} trials; d_facts "
                + ", ".join(str(r["d_facts"]) for r in v5),
            ))
    return results


def markdown(table: List[dict]) -> str:
    keys = ("locus", "backend", "level", "trial_index", "variants",
            "d_missing", "cross_user_rows", "private_rows_from_others",
            "d_facts", "d_raw", "d_after_cap", "d_tokens", "block_format")
    lines = ["| " + " | ".join(keys) + " |",
             "|" + "---|" * len(keys)]
    for row in table:
        if row["level"] == 0:
            continue
        lines.append("| " + " | ".join(
            "" if row.get(k) is None else str(row.get(k)) for k in keys
        ) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--csv")
    parser.add_argument("--markdown")
    args = parser.parse_args(argv)
    table = rows(load(args.root))
    missing_ref = [r for r in table if r["level"] and not r["has_reference"]]
    if missing_ref:
        print(f"WARNING: {len(missing_ref)} trials without an H=0 pair")
    if args.csv:
        with open(args.csv, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(COLUMNS),
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(table)
    text = markdown(table)
    if args.markdown:
        with open(args.markdown, "w") as handle:
            handle.write(text + "\n")
    print(text)
    print()
    for name, passed, evidence in checks(table):
        print(f"{'PASS   ' if passed else 'FINDING'} {name}: {evidence}")
    leaks = sum((r.get(k) or 0) for r in table if r["level"] == 0
                for k in LEAKS)
    print(f"H=0 leaked rows (all cells): {leaks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
