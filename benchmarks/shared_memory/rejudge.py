"""Re-score stored assistant responses with the current judge prompt.

Reads results files, re-judges every completed trial's stored
``assistant_response`` with ``HybridJudge`` and writes a new results file
per input, under the condition's current name. Makes judge calls only: no
assistant or memory calls. A trial whose LLM judge call fails after
retries is marked failed instead of falling back to the keyword score.

    python -m benchmarks.shared_memory.rejudge \\
        results/revalidation/*/results_*.json \\
        --output results/revalidation_v2 --judge-model gpt-5.4:azure
"""
import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from benchmarks.shared_memory.conditions import canonical_condition
from benchmarks.shared_memory.judge import (
    JUDGE_PROMPT_VERSION,
    JUDGE_RETRIES,
    SCORER,
    HybridJudge,
    JudgeFailed,
    judge_prompt_sha256,
)
from benchmarks.shared_memory.models import (
    ExperimentResults,
    TrialResult,
    _harness_commit,
)
from benchmarks.shared_memory.results import ResultsWriter
from benchmarks.shared_memory.run_evaluation import _parse_model_arg

logger = logging.getLogger(__name__)

RETRIES = JUDGE_RETRIES
SCORE_FIELDS = ("profile_usage_score", "task_usage_score", "integration_score")


def rejudge_trial(judge: HybridJudge, trial: TrialResult) -> TrialResult:
    """Return a copy of ``trial`` with its scores from ``judge``."""
    if trial.failed:
        return trial
    try:
        scores = judge.evaluate(
            trial.follow_up_query,
            trial.assistant_response,
            trial.synthetic_profile,
            trial.synthetic_task_context,
        )
    except JudgeFailed as e:
        return trial.model_copy(update={
            **{field: None for field in SCORE_FIELDS},
            "failed": True,
            "error_message": f"re-judge: {e}",
            "judge_attempts": e.attempts,
        })
    return trial.model_copy(update={
        **{field: getattr(scores, field) for field in SCORE_FIELDS},
        "scorer": SCORER,
        "judge_attempts": scores.judge_attempts,
    })


def rejudge_experiment(
    experiment: ExperimentResults,
    judge: HybridJudge,
    source: str,
    judge_model: str | None,
    workers: int = 1,
) -> ExperimentResults:
    """Re-judge every condition of one experiment."""
    writer = ResultsWriter(output_dir=".")
    conditions = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in experiment.conditions:
            name = canonical_condition(result.condition)
            trials = [
                trial.model_copy(update={
                    "condition": canonical_condition(trial.condition),
                    "method": canonical_condition(trial.method),
                })
                for trial in pool.map(
                    lambda t: rejudge_trial(judge, t), result.trials
                )
            ]
            conditions.append(result.model_copy(update={
                "condition": name,
                "trials": trials,
                "summary": writer.compute_summary_statistics(trials),
            }))
    old = experiment.experiment_metadata
    metadata = old.model_copy(update={
        "conditions_run": [canonical_condition(c) for c in old.conditions_run],
        "methods_run": [canonical_condition(m) for m in old.methods_run],
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": judge_prompt_sha256(),
        "judge_temperature": judge.temperature,
        "judge_seed": judge.seed,
        "rejudge": {
            "source": source,
            "source_judge_prompt_version": old.judge_prompt_version or 1,
            # None: the source judge sampled (kernel default 1.0).
            "source_judge_temperature": old.judge_temperature,
            "source_judge_seed": old.judge_seed,
            "judge_model": judge_model,
            "harness_commit": _harness_commit(),
            "timestamp": datetime.now().isoformat(),
        },
    })
    return ExperimentResults(experiment_metadata=metadata, conditions=conditions)


def output_path(source: Path, output_dir: Path, condition: str) -> Path:
    """Map ``<model>_<old>/results_<old>.json`` to the current name."""
    model = source.parent.name.removesuffix(f"_{condition}")
    name = canonical_condition(condition)
    return output_dir / f"{model}_{name}" / f"results_{name}.json"


def complete(path: Path, trials: int) -> bool:
    """Return whether a re-judged file has every trial and no failure."""
    if not path.exists():
        return False
    data = json.loads(path.read_text())
    every = [t for c in data["conditions"] for t in c["trials"]]
    return len(every) == trials and not any(t["failed"] for t in every)


def main() -> None:
    """Re-judge each input file; skip one whose output is complete."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    judge = HybridJudge(llms=_parse_model_arg(args.judge_model))
    failed = 0
    for source in args.inputs:
        experiment = ExperimentResults.model_validate_json(source.read_text())
        condition = experiment.conditions[0].condition
        target = output_path(source, args.output, condition)
        trials = sum(len(c.trials) for c in experiment.conditions)
        if complete(target, trials):
            logger.info("skip %s: %s is complete", source, target)
            continue
        logger.info("re-judge %s -> %s", source, target)
        result = rejudge_experiment(
            experiment, judge, str(source), args.judge_model, args.workers
        )
        ResultsWriter(output_dir=str(target.parent)).write_json(
            result, filename=target.name
        )
        failed += sum(t.failed for c in result.conditions for t in c.trials)
    if failed:
        raise SystemExit(f"{failed} failed trials after re-judging")


if __name__ == "__main__":
    main()
