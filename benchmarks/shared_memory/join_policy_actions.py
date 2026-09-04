#!/usr/bin/env python3
"""Standalone post-hoc join of adaptive-policy reward records onto trial results.

Enriches the per-trial output written by
``benchmarks/shared_memory/run_evaluation.py`` (``results.json`` or a
``results_*.json`` variant) with the kernel's adaptive-policy reward records
from ``policy_trials.jsonl``, populating ``TrialResult.policy_action``.

This runs AFTER a benchmark run — it is not part of the live trial loop and
touches neither the SDK nor the AIOS kernel. It only reads two existing
artifacts and writes an enriched copy of the results file.

Scope (decided in docs/policy-trials-jsonl-findings.md, Subtask 7 — GO gate):

* **Reward events only.** Only ``event == "reward"`` records carry a usable
  per-trial ``trial_id``. ``select`` records always have ``trial_id: null``
  (the harness never threads ``trial_index`` into add/retrieve metadata), so
  the decision-side signal (which arm was chosen, its gate/value/context)
  cannot be attributed to a trial and is intentionally NOT joined. This is a
  structural limitation, not a bug — see the findings doc.
* **Integer ``trial_id`` only.** Records whose ``trial_id`` is ``null`` or a
  string (manual markers like ``"probe"`` / ``"trial-subtask3-verify"``) are
  non-benchmark noise and are dropped.
* **Single-run-scoped, caller-supplied.** ``trial_id`` integers restart at 0
  every run and neither artifact carries a run id / user_id, so a naive join
  over a multi-run ``policy_trials.jsonl`` would silently collide across runs.
  The caller MUST scope input to one run, either by pointing ``--policy-log``
  at a single-run slice of the file, or by passing an explicit ``--since`` /
  ``--until`` epoch-second ``ts`` window. The script never auto-detects run
  boundaries.

Join: ``reward.trial_id == TrialResult.trial_index``. One trial maps to MANY
reward records (one per bandit rewarded), so ``policy_action`` is a list.

Stdlib only — no new dependencies. Compatible with Python 3.10+.

Example::

    python benchmarks/shared_memory/join_policy_actions.py \\
        --results results/run_a/results_kernel_shared.json \\
        --policy-log logs/policy_trials.jsonl \\
        --since 1788467100 --until 1788468300 \\
        --output results/run_a/results_kernel_shared.enriched.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

REWARD_EVENT = "reward"


def _is_int_trial_id(value: Any) -> bool:
    """True only for a genuine integer ``trial_id``.

    Excludes ``None`` (unjoinable ``select`` records) and strings (manual
    markers). Booleans are rejected too, since ``bool`` is an ``int`` subclass
    in Python and a boolean ``trial_id`` would be nonsensical here.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def load_reward_records(
    policy_log_path: str,
    since: Optional[float] = None,
    until: Optional[float] = None,
) -> Tuple[Dict[int, List[dict]], Dict[str, int]]:
    """Load and group reward records from a policy_trials.jsonl slice.

    Args:
        policy_log_path: Path to a ``policy_trials.jsonl`` file. Per Subtask 7,
            the caller is responsible for scoping this to a single run (either
            a per-run file or via the ``since``/``until`` window).
        since: Optional inclusive lower bound on the record ``ts`` (epoch s).
        until: Optional inclusive upper bound on the record ``ts`` (epoch s).

    Returns:
        Tuple ``(by_trial, stats)`` where ``by_trial`` maps an integer
        ``trial_id`` to the list of its reward records (in file order), and
        ``stats`` is a histogram of what was seen/dropped for reporting.
    """
    by_trial: Dict[int, List[dict]] = defaultdict(list)
    stats: Dict[str, int] = {
        "total_lines": 0,
        "not_reward_event": 0,
        "outside_ts_window": 0,
        "trial_id_null": 0,
        "trial_id_string": 0,
        "reward_joined": 0,
        "malformed": 0,
    }

    with open(policy_log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            stats["total_lines"] += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                stats["malformed"] += 1
                continue

            if rec.get("event") != REWARD_EVENT:
                stats["not_reward_event"] += 1
                continue

            # ts window filter (single-run scoping per Subtask 7).
            ts = rec.get("ts")
            if since is not None and (ts is None or ts < since):
                stats["outside_ts_window"] += 1
                continue
            if until is not None and (ts is None or ts > until):
                stats["outside_ts_window"] += 1
                continue

            tid = rec.get("trial_id")
            if tid is None:
                stats["trial_id_null"] += 1
                continue
            if isinstance(tid, str):
                stats["trial_id_string"] += 1
                continue
            if not _is_int_trial_id(tid):
                # Any other non-int type (float, etc.) — treat as noise.
                stats["malformed"] += 1
                continue

            by_trial[int(tid)].append(rec)
            stats["reward_joined"] += 1

    return by_trial, stats


def _policy_action_from_records(records: List[dict]) -> List[dict]:
    """Project raw reward records into PolicyActionEntry-shaped dicts.

    Only the fields Subtask 7 scoped are carried: ``bandit``, ``arm_index``,
    ``reward``, ``memory_id``. Order preserves the policy-log file order.
    """
    entries: List[dict] = []
    for rec in records:
        entries.append(
            {
                "bandit": rec.get("bandit"),
                "arm_index": rec.get("arm_index"),
                "reward": rec.get("reward"),
                "memory_id": rec.get("memory_id"),
            }
        )
    return entries


def enrich_results(
    results_payload: dict,
    by_trial: Dict[int, List[dict]],
) -> Dict[str, int]:
    """Populate ``policy_action`` on every trial in a results payload in place.

    Every non-failed trial gets ``policy_action`` set to a (possibly empty)
    list, so a present-but-empty list means "joined, no reward records for this
    trial_index" while ``None`` (untouched) would mean "never joined". Failed
    trials are left untouched (they have no meaningful outcome to attribute).

    Args:
        results_payload: Parsed ``ExperimentResults`` document (mutated).
        by_trial: Reward records grouped by integer trial_id.

    Returns:
        Histogram of the enrichment for reporting.
    """
    stats: Dict[str, int] = {
        "trials_total": 0,
        "trials_failed_skipped": 0,
        "trials_enriched_nonempty": 0,
        "trials_enriched_empty": 0,
    }
    for cond in results_payload.get("conditions") or []:
        for trial in cond.get("trials") or []:
            stats["trials_total"] += 1
            if trial.get("failed"):
                stats["trials_failed_skipped"] += 1
                continue
            idx = trial.get("trial_index")
            records = by_trial.get(idx, [])
            trial["policy_action"] = _policy_action_from_records(records)
            if records:
                stats["trials_enriched_nonempty"] += 1
            else:
                stats["trials_enriched_empty"] += 1
    return stats


def join(
    results_path: str,
    policy_log_path: str,
    output_path: str,
    since: Optional[float] = None,
    until: Optional[float] = None,
) -> int:
    """Run the join and write the enriched results file.

    Args:
        results_path: Path to the harness ``results*.json`` document.
        policy_log_path: Path to a single-run ``policy_trials.jsonl`` slice.
        output_path: Where to write the enriched copy.
        since: Optional inclusive ``ts`` lower bound (epoch seconds).
        until: Optional inclusive ``ts`` upper bound (epoch seconds).

    Returns:
        Process exit code (0 on success).
    """
    with open(results_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    by_trial, load_stats = load_reward_records(
        policy_log_path, since=since, until=until
    )
    enrich_stats = enrich_results(payload, by_trial)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"[join_policy_actions] results:    {results_path}")
    print(f"[join_policy_actions] policy log: {policy_log_path}")
    if since is not None or until is not None:
        print(
            f"[join_policy_actions] ts window:  "
            f"since={since} until={until}"
        )
    else:
        print(
            "[join_policy_actions] ts window:  (none — caller asserts the "
            "policy log is already a single-run slice)"
        )
    print("[join_policy_actions] policy-log scan:")
    print(f"    total lines            : {load_stats['total_lines']}")
    print(f"    non-reward events      : {load_stats['not_reward_event']}")
    print(f"    outside ts window      : {load_stats['outside_ts_window']}")
    print(f"    dropped trial_id=null  : {load_stats['trial_id_null']}")
    print(f"    dropped trial_id=str   : {load_stats['trial_id_string']}")
    print(f"    malformed              : {load_stats['malformed']}")
    print(f"    reward records joined  : {load_stats['reward_joined']}")
    print(
        f"    distinct trial_ids     : {len(by_trial)}"
    )
    print("[join_policy_actions] enrichment:")
    print(f"    trials total           : {enrich_stats['trials_total']}")
    print(
        f"    failed (skipped)       : "
        f"{enrich_stats['trials_failed_skipped']}"
    )
    print(
        f"    enriched (>=1 action)  : "
        f"{enrich_stats['trials_enriched_nonempty']}"
    )
    print(
        f"    enriched (0 actions)   : "
        f"{enrich_stats['trials_enriched_empty']}"
    )
    print(f"[join_policy_actions] wrote enriched results -> {output_path}")
    print(
        "[join_policy_actions] note: select-event (decision-side) records are "
        "NOT joined — their trial_id is always null and cannot be attributed "
        "to a trial. See docs/policy-trials-jsonl-findings.md."
    )
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="join_policy_actions.py",
        description=(
            "Post-hoc join of adaptive-policy reward records "
            "(policy_trials.jsonl) onto TrialResult.policy_action. Reward "
            "events only; integer trial_id only; single-run-scoped input."
        ),
    )
    parser.add_argument(
        "--results",
        required=True,
        type=str,
        help="Path to results*.json written by run_evaluation.py.",
    )
    parser.add_argument(
        "--policy-log",
        required=True,
        type=str,
        help=(
            "Path to a SINGLE-RUN slice of policy_trials.jsonl. If the file "
            "holds multiple runs, scope it with --since/--until."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        type=str,
        help="Path to write the enriched results JSON.",
    )
    parser.add_argument(
        "--since",
        type=float,
        default=None,
        help=(
            "Optional inclusive lower bound on record ts (epoch seconds) to "
            "scope the join to one run."
        ),
    )
    parser.add_argument(
        "--until",
        type=float,
        default=None,
        help=(
            "Optional inclusive upper bound on record ts (epoch seconds) to "
            "scope the join to one run."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if (
        args.since is not None
        and args.until is not None
        and args.since > args.until
    ):
        parser.error("--since must be <= --until")
    try:
        return join(
            results_path=args.results,
            policy_log_path=args.policy_log,
            output_path=args.output,
            since=args.since,
            until=args.until,
        )
    except FileNotFoundError as exc:
        print(f"[join_policy_actions] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
