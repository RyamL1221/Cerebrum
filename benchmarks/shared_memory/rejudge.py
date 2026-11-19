"""Re-score stored assistant responses with the current judge prompt.

Reads results files, re-judges every completed trial's stored
``assistant_response`` (a v2 trial's is its integration probe's answer)
and writes a new results file per input. Makes judge calls only: no
assistant or memory calls.

Either judge (``--judge``; AIOS docs/METRICS.md, "The judges"), each
answer judged ``--repeats`` times, every repeat recorded in the trial's
``judges[<name>]`` (and a v2 integration probe's). The primary judge
(or a kernel judge named by ``--judge-model``) also rewrites the
trial's three hybrid scores, as before Subtask 20; a trial it cannot
judge after retries is marked failed instead of falling back to the
keyword score. The second judge adds its record only, and a judgment it
cannot make is recorded as failed without failing the trial. The second
judge's calls go in one Message Batch for all inputs.

    python -m benchmarks.shared_memory.rejudge \\
        results/pilot_v1_hetero/*/*/*/results_*.json \\
        --root results/pilot_v1_hetero --output results/s20_hetero_gpt \\
        --judge gpt-5.4 --repeats 3
"""
import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from benchmarks.shared_memory.conditions import canonical_condition
from benchmarks.shared_memory.judge import (
    JUDGE_PROMPT_VERSION,
    JUDGE_RETRIES,
    JUDGES,
    SCORER,
    SECOND_JUDGE,
    ClaudeJudge,
    HybridJudge,
    JudgeFailed,
    batch_evaluate,
    judge_prompt_sha256,
    make_judge,
)
from benchmarks.shared_memory.models import (
    ExperimentResults,
    JudgeScores,
    TrialResult,
    _harness_commit,
)
from benchmarks.shared_memory.results import ResultsWriter
from benchmarks.shared_memory.run_evaluation import _parse_model_arg

logger = logging.getLogger(__name__)

RETRIES = JUDGE_RETRIES
SCORE_FIELDS = ("profile_usage_score", "task_usage_score", "integration_score")


def rewrites_scores(judge: HybridJudge) -> bool:
    """Whether ``judge``'s hybrid is the trial's score: every judge but
    the second, which only adds its record."""
    return judge.name != SECOND_JUDGE


def _with_judges(judges: Optional[Dict[str, Any]], name: str,
                 record: Dict[str, Any]) -> Dict[str, Any]:
    return {**(judges or {}), name: record}


def apply_judgment(judge: HybridJudge, trial: TrialResult,
                   outcome: Any) -> TrialResult:
    """``trial`` with ``outcome`` (the judge's ``JudgeScores``, or the
    ``JudgeFailed`` it raised) applied."""
    integration = next((p for p in trial.probe_results
                        if p.type == "integration"), None)
    if isinstance(outcome, JudgeFailed):
        if not rewrites_scores(judge):
            failed = {"judge": judge.name, "failed": True,
                      "attempts": outcome.attempts}
            update: Dict[str, Any] = {
                "judges": _with_judges(trial.judges, judge.name, failed)}
            if integration is not None:
                probes = [p.model_copy(update={"judges": _with_judges(
                    p.judges, judge.name, failed)}) if p is integration
                    else p for p in trial.probe_results]
                update["probe_results"] = probes
            return trial.model_copy(update=update)
        return trial.model_copy(update={
            **{field: None for field in SCORE_FIELDS},
            "failed": True,
            "error_message": f"re-judge: {outcome}",
            "judge_attempts": outcome.attempts,
        })
    scores: JudgeScores = outcome
    update = {"judges": _with_judges(trial.judges, judge.name,
                                     scores.record)}
    if rewrites_scores(judge):
        update.update({field: getattr(scores, field)
                       for field in SCORE_FIELDS})
        update.update({"scorer": SCORER,
                       "judge_attempts": scores.judge_attempts})
    if integration is not None:
        probe_update: Dict[str, Any] = {"judges": _with_judges(
            integration.judges, judge.name, scores.record)}
        if rewrites_scores(judge):
            probe_update["judge_scores"] = {
                field: getattr(scores, field) for field in SCORE_FIELDS}
            probe_update["integration_score"] = scores.integration_score
        update["probe_results"] = [
            p.model_copy(update=probe_update) if p is integration else p
            for p in trial.probe_results]
    return trial.model_copy(update=update)


def judge_inputs(trial: TrialResult) -> Dict[str, Any]:
    """What the judge sees for a stored trial."""
    return {"query": trial.follow_up_query,
            "response": trial.assistant_response,
            "profile": trial.synthetic_profile,
            "task_context": trial.synthetic_task_context}


def rejudge_trial(judge: HybridJudge, trial: TrialResult) -> TrialResult:
    """Return a copy of ``trial`` judged by ``judge`` (one call per
    repeat)."""
    if trial.failed:
        return trial
    inputs = judge_inputs(trial)
    try:
        outcome = judge.evaluate(inputs["query"], inputs["response"],
                                 inputs["profile"], inputs["task_context"])
    except JudgeFailed as e:
        outcome = e
    return apply_judgment(judge, trial, outcome)


def rejudged_metadata(experiment: ExperimentResults, judge: HybridJudge,
                      source: str, judge_model: Optional[str]):
    old = experiment.experiment_metadata
    update: Dict[str, Any] = {
        "conditions_run": [canonical_condition(c) for c in old.conditions_run],
        "methods_run": [canonical_condition(m) for m in old.methods_run],
        "rejudge": {
            "source": source,
            "source_judge_prompt_version": old.judge_prompt_version or 1,
            # None: the source judge sampled (kernel default 1.0).
            "source_judge_temperature": old.judge_temperature,
            "source_judge_seed": old.judge_seed,
            "judge_model": judge_model,
            "judge": judge.describe(),
            "harness_commit": _harness_commit(),
            "timestamp": datetime.now().isoformat(),
        },
    }
    if rewrites_scores(judge):
        update.update({
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
            "judge_prompt_sha256": judge_prompt_sha256(),
            "judge_temperature": judge.temperature,
            "judge_seed": judge.seed,
            "judge": judge.describe(),
        })
    return old.model_copy(update=update)


def _rebuild(experiment: ExperimentResults, judge: HybridJudge, source: str,
             judge_model: Optional[str], judged) -> ExperimentResults:
    """The experiment with each condition's trials replaced by
    ``judged(condition_index, trial_index_in_list, trial)``."""
    writer = ResultsWriter(output_dir=".")
    conditions = []
    for ci, result in enumerate(experiment.conditions):
        name = canonical_condition(result.condition)
        trials = [
            judged(ci, ti, trial).model_copy(update={
                "condition": canonical_condition(trial.condition),
                "method": canonical_condition(trial.method),
            })
            for ti, trial in enumerate(result.trials)
        ]
        conditions.append(result.model_copy(update={
            "condition": name,
            "trials": trials,
            "summary": writer.compute_summary_statistics(trials),
        }))
    return ExperimentResults(
        experiment_metadata=rejudged_metadata(experiment, judge, source,
                                              judge_model),
        conditions=conditions)


def rejudge_experiment(
    experiment: ExperimentResults,
    judge: HybridJudge,
    source: str,
    judge_model: str | None,
    workers: int = 1,
) -> ExperimentResults:
    """Re-judge every condition of one experiment, one call per repeat
    (a kernel judge, or the second judge through the Messages API)."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        judged = {
            (ci, ti): future for ci, result in enumerate(
                experiment.conditions)
            for ti, future in enumerate(
                pool.submit(rejudge_trial, judge, t) for t in result.trials)
        }
        return _rebuild(experiment, judge, source, judge_model,
                        lambda ci, ti, _: judged[(ci, ti)].result())


def rejudge_in_batch(
    experiments: Dict[str, ExperimentResults],
    judge: HybridJudge,
    judge_model: Optional[str],
    evaluate=batch_evaluate,
) -> Dict[str, ExperimentResults]:
    """Re-judge many experiments (source -> experiment) with the second
    judge in one Message Batch."""
    items: Dict[str, Dict[str, Any]] = {}
    for source, experiment in experiments.items():
        for ci, result in enumerate(experiment.conditions):
            for ti, trial in enumerate(result.trials):
                if not trial.failed:
                    items[f"{len(items)}"] = {"key": (source, ci, ti),
                                              **judge_inputs(trial)}
    by_key = {item.pop("key"): item_id for item_id, item in items.items()}
    outcomes = evaluate(judge, items) if items else {}

    def judged(source):
        def one(ci, ti, trial):
            item_id = by_key.get((source, ci, ti))
            if item_id is None:
                return trial
            return apply_judgment(judge, trial, outcomes[item_id])
        return one

    return {source: _rebuild(experiment, judge, source, judge_model,
                             judged(source))
            for source, experiment in experiments.items()}


def output_path(source: Path, output_dir: Path, condition: str,
                root: Optional[Path] = None) -> Path:
    """Under ``root``, the input's own path below it; otherwise map
    ``<model>_<old>/results_<old>.json`` to the current name."""
    if root is not None:
        return output_dir / source.relative_to(root)
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


def main(argv=None) -> None:
    """Re-judge each input file; skip one whose output is complete."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=None,
                        help="write each input under --output at its "
                             "path below this directory")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--judge", choices=sorted(JUDGES))
    which.add_argument("--judge-model")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    judge = make_judge(args.judge, _parse_model_arg(args.judge_model),
                       args.repeats)
    label = args.judge or args.judge_model
    todo: Dict[str, ExperimentResults] = {}
    targets: Dict[str, Path] = {}
    for source in args.inputs:
        experiment = ExperimentResults.model_validate_json(source.read_text())
        condition = experiment.conditions[0].condition
        target = output_path(source, args.output, condition, args.root)
        trials = sum(len(c.trials) for c in experiment.conditions)
        if complete(target, trials):
            logger.info("skip %s: %s is complete", source, target)
            continue
        todo[str(source)], targets[str(source)] = experiment, target
    if isinstance(judge.llm_judge, ClaudeJudge):
        results = rejudge_in_batch(todo, judge, label)
    else:
        results = {}
        for source, experiment in todo.items():
            logger.info("re-judge %s -> %s", source, targets[source])
            results[source] = rejudge_experiment(
                experiment, judge, source, label, args.workers)
    failed = 0
    for source, result in results.items():
        target = targets[source]
        ResultsWriter(output_dir=str(target.parent)).write_json(
            result, filename=target.name
        )
        failed += sum(t.failed for c in result.conditions for t in c.trials)
    if failed:
        raise SystemExit(f"{failed} failed trials after re-judging")


if __name__ == "__main__":
    main()
