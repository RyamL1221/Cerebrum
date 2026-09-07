"""Re-judge already-collected trial responses under the v2 rubric.

The v1 (holistic 1-5) and v2 (decomposed 0-5) judges are different
instruments; for an apples-to-apples v1-vs-v2 comparison on data that was
already collected (e.g. the paper's ``kernel_shared`` / ``kernel_shared_adaptive``
runs), the assistant responses do NOT need to be regenerated — only re-scored.
This script re-runs ONLY the judge over an existing finalized results JSON,
reusing the exact judge logic in ``judge.py`` (no prompt duplication), and
writes a NEW results file so the v1 original and the v2 re-judge coexist (per
the "never merge v1 and v2 scores" rule).

What it needs from each trial (all present in finalized results files —
verified against ``results/gpt4o_kernel_shared`` and
``results/adaptive_report/gpt4o``): ``follow_up_query``, ``assistant_response``,
``synthetic_profile``, ``synthetic_task_context``. ``plausible_actions`` is not
stored in those files and was not used when the originals were scored; the v2
prompt simply omits that section when it is absent, so re-judging is faithful.

Scoring method: the original runs were scored by ``HybridJudge`` (the
orchestrator constructs ``HybridJudge`` — see ``run_evaluation.py``). To keep
the comparison apples-to-apples in METHOD (only the rubric changes, not the
keyword+LLM hybrid vs. LLM-only choice), this script defaults to
``HybridJudge``. ``--llm-only`` opts into raw ``LLMJudge`` if desired.

Cost note: each non-skipped trial issues one judge-model call (e.g. GPT-5.4).
Use ``--dry-run`` to see the trial/call count and estimated cost first, and
``--limit N`` to re-judge only the first N re-judgeable trials for a cheap
smoke check before committing to a full run.

This module is the SCRIPT + smoke test only. Running it end-to-end against real
``kernel_shared`` / ``kernel_shared_adaptive`` data (real judge-model calls) is
follow-up EXPERIMENTAL work, intentionally NOT performed here.

Usage::

    # See what a full run would cost — no API calls:
    python benchmarks/shared_memory/rejudge.py \
        --input results/gpt4o_kernel_shared/results_kernel_shared.json --dry-run

    # Cheap smoke run over 5 trials with a real judge model:
    python benchmarks/shared_memory/rejudge.py \
        --input results/gpt4o_kernel_shared/results_kernel_shared.json \
        --judge-model "gpt-5.4:azure" --limit 5

    # Full re-judge (follow-up experimental work — not run in dev planning):
    python benchmarks/shared_memory/rejudge.py \
        --input results/gpt4o_kernel_shared/results_kernel_shared.json \
        --judge-model "gpt-5.4:azure"
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Ensure the project root is on sys.path when running as a script
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.shared_memory.judge import HybridJudge, LLMJudge
from benchmarks.shared_memory.models import (
    ConditionResults,
    ExperimentMetadata,
    ExperimentResults,
    SyntheticProfile,
    SyntheticTaskContext,
    TrialResult,
)
from benchmarks.shared_memory.results import ResultsWriter

logger = logging.getLogger(__name__)

RUBRIC_V2 = "v2"


def default_output_path(input_path: str) -> str:
    """Derive a v2 output path that never collides with the v1 original.

    ``.../results_kernel_shared.json`` → ``.../results_kernel_shared_v2.json``.
    A non-``.json`` path just gets a ``_v2`` suffix before any extension.
    """
    root, ext = os.path.splitext(input_path)
    if root.endswith("_v2"):
        # Already a v2 name — still avoid overwriting by re-suffixing.
        root = root + "_rejudged"
    return f"{root}_v2{ext or '.json'}"


def _reconstruct_context(
    trial: Dict[str, Any],
) -> Optional[Tuple[SyntheticProfile, SyntheticTaskContext]]:
    """Rebuild the judge inputs from a stored trial dict.

    Returns None when the trial lacks the synthetic profile/task needed to
    re-judge (mirrors the harness/human-rating convention of skipping rather
    than fabricating context).
    """
    prof = trial.get("synthetic_profile")
    task = trial.get("synthetic_task_context")
    if not prof or not task:
        return None
    try:
        return SyntheticProfile(**prof), SyntheticTaskContext(**task)
    except (TypeError, ValueError) as e:
        logger.warning(
            "trial %s: cannot reconstruct synthetic context: %s",
            trial.get("trial_index"), e,
        )
        return None


def _is_rejudgeable(trial: Dict[str, Any]) -> bool:
    """A trial can be re-judged iff it wasn't a failure and has a response +
    reconstructable profile/task context."""
    if trial.get("failed") is True:
        return False
    if not (trial.get("assistant_response") or "").strip():
        return False
    return _reconstruct_context(trial) is not None


def iter_trials(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten all trials across all conditions in a results payload."""
    trials: List[Dict[str, Any]] = []
    for cond in payload.get("conditions", []) or []:
        trials.extend(cond.get("trials", []) or [])
    return trials


def plan(payload: Dict[str, Any], limit: Optional[int] = None) -> Dict[str, int]:
    """Compute the re-judge plan counts without calling the judge.

    Returns a dict with total trials, how many are re-judgeable, how many would
    be skipped, and how many judge calls a run (respecting ``limit``) would make.
    """
    trials = iter_trials(payload)
    rejudgeable = [t for t in trials if _is_rejudgeable(t)]
    n_calls = len(rejudgeable)
    if limit is not None:
        n_calls = min(n_calls, limit)
    return {
        "total_trials": len(trials),
        "rejudgeable": len(rejudgeable),
        "skipped": len(trials) - len(rejudgeable),
        "judge_calls": n_calls,
    }


def rejudge_payload(
    payload: Dict[str, Any],
    judge,
    limit: Optional[int] = None,
) -> ExperimentResults:
    """Re-judge every re-judgeable trial in ``payload`` with ``judge``.

    Preserves each trial's non-score fields; replaces the three scores +
    rubric_version + criteria_breakdown with the judge's v2 output. Skipped
    trials (failed / no response / no context) are carried through unchanged
    except their rubric_version is left as-is (they were never re-scored).

    ``judge`` must expose ``.evaluate(query, response, profile, task_context,
    plausible_actions)`` returning a ``JudgeScores`` — i.e. HybridJudge or
    LLMJudge. This function never builds a prompt itself; it delegates entirely.
    """
    writer = ResultsWriter(output_dir=".")  # only used for summary computation
    called = 0
    new_conditions: List[ConditionResults] = []

    for cond in payload.get("conditions", []) or []:
        rebuilt: List[TrialResult] = []
        for raw in cond.get("trials", []) or []:
            trial = TrialResult(**raw)  # parse (fills rubric_version="v1" default)
            reconstructed = _reconstruct_context(raw)
            can_rejudge = (
                _is_rejudgeable(raw)
                and (limit is None or called < limit)
            )
            if can_rejudge and reconstructed is not None:
                profile, task_context = reconstructed
                scores = judge.evaluate(
                    query=raw.get("follow_up_query", ""),
                    response=raw.get("assistant_response", ""),
                    profile=profile,
                    task_context=task_context,
                    plausible_actions=raw.get("plausible_actions") or None,
                )
                called += 1
                trial = trial.model_copy(update={
                    "profile_usage_score": scores.profile_usage_score,
                    "task_usage_score": scores.task_usage_score,
                    "integration_score": scores.integration_score,
                    "rubric_version": scores.rubric_version,
                    "criteria_breakdown": scores.criteria_breakdown,
                    "judge_token_usage": scores.token_usage,
                })
            else:
                # Not re-judged (failed / no response / no context, or beyond
                # --limit). The output must stay a SINGLE-rubric (v2) artifact —
                # leaving these as "v1" would trip the never-pool guard the
                # instant anyone summarizes the file. Represent them as v2
                # trials with no score (failed=True), so they're preserved in
                # the record but excluded from v2 summary stats. Their original
                # v1 scores are intentionally dropped: a v2 file must not carry
                # v1 scores that could be mistaken for v2 ones.
                trial = trial.model_copy(update={
                    "rubric_version": RUBRIC_V2,
                    "profile_usage_score": None,
                    "task_usage_score": None,
                    "integration_score": None,
                    "criteria_breakdown": None,
                    "failed": True,
                    "error_message": trial.error_message or "not re-judged under v2 (skipped)",
                })
            rebuilt.append(trial)

        summary = writer.compute_summary_statistics(rebuilt)
        new_conditions.append(
            ConditionResults(condition=cond.get("condition", ""), trials=rebuilt, summary=summary)
        )

    old_meta = payload.get("experiment_metadata", {}) or {}
    meta = ExperimentMetadata(
        trials_per_condition=old_meta.get("trials_per_condition", 0),
        timestamp=datetime.utcnow().isoformat(),
        kernel_url=old_meta.get("kernel_url", ""),
        conditions_run=old_meta.get("conditions_run", []) or [],
        methods_run=old_meta.get("methods_run", []) or [],
    )
    return ExperimentResults(experiment_metadata=meta, conditions=new_conditions)


def _parse_model_arg(value: Optional[str]) -> Optional[list]:
    """Parse a ``name:backend`` model arg into the llms list judge.py expects."""
    if not value:
        return None
    name, _, backend = value.partition(":")
    return [{"name": name, "backend": backend or "openai"}]


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rejudge.py",
        description="Re-score an existing results JSON under the v2 rubric.",
    )
    p.add_argument("--input", required=True, help="Path to a finalized results_*.json (v1).")
    p.add_argument(
        "--output", default=None,
        help="Output path. Defaults to <input>_v2.json; never overwrites --input.",
    )
    p.add_argument(
        "--judge-model", default=None,
        help="Judge model as 'name:backend' (e.g. 'gpt-5.4:azure'). Defaults to kernel's model.",
    )
    p.add_argument(
        "--llm-only", action="store_true",
        help="Use raw LLMJudge instead of HybridJudge (default: HybridJudge, matching the originals).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Report trial/call counts and estimated cost; make NO judge calls.",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Re-judge only the first N re-judgeable trials (for cheap smoke checks).",
    )
    p.add_argument(
        "--cost-per-call", type=float, default=None,
        help="Optional $ per judge call, to print an estimated total in --dry-run.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if not os.path.exists(args.input):
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 2

    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    out_path = args.output or default_output_path(args.input)
    if os.path.abspath(out_path) == os.path.abspath(args.input):
        print("ERROR: refusing to overwrite the input (v1) file.", file=sys.stderr)
        return 2

    counts = plan(payload, limit=args.limit)
    print("Re-judge plan (rubric v2):")
    print(f"  input          : {args.input}")
    print(f"  output         : {out_path}")
    print(f"  total trials   : {counts['total_trials']}")
    print(f"  re-judgeable   : {counts['rejudgeable']}")
    print(f"  skipped        : {counts['skipped']} (failed / empty response / no context)")
    print(f"  judge calls    : {counts['judge_calls']}"
          + (f" (limited to {args.limit})" if args.limit is not None else ""))
    if args.cost_per_call is not None:
        print(f"  est. cost      : ${counts['judge_calls'] * args.cost_per_call:.2f}")

    if args.dry_run:
        print("\n[dry-run] No judge calls made, no output written.")
        return 0

    llms = _parse_model_arg(args.judge_model)
    judge = (
        LLMJudge(llms=llms, rubric_version=RUBRIC_V2)
        if args.llm_only
        else HybridJudge(llms=llms, rubric_version=RUBRIC_V2)
    )

    experiment = rejudge_payload(payload, judge, limit=args.limit)

    writer = ResultsWriter(output_dir=os.path.dirname(out_path) or ".")
    written = writer.write_json(experiment, os.path.basename(out_path))
    print(f"\nWrote v2 re-judged results to: {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
