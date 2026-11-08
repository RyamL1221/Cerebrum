"""CLI entry point and orchestrator for the shared memory evaluation harness.

Runs a two-condition experiment comparing private-only memory (Phase 1)
against shared memory (Phase 2) across synthetic trials, collecting
profile-usage, task-usage, integration, memory-count, and latency metrics.

The kernel's ``memory.auto_inject`` is assumed to be enabled for both phases.
The only difference between phases is the ``share_memory`` flag on agents:
- Phase 1: agents write memories with sharing_policy="private" → kernel
  auto-inject finds nothing eligible to inject cross-agent.
- Phase 2: agents write memories with sharing_policy="shared" → kernel
  auto-inject retrieves and injects them into AssistantAgent's context.

Restart the kernel between phases to clear the memory store and prevent
rollover.

Usage::

    # Legacy --condition workflow (backward compatible)
    python benchmarks/shared_memory/run_evaluation.py --trials 10 --output results/ --condition phase1 --csv
    # restart kernel to clear memory
    python benchmarks/shared_memory/run_evaluation.py --trials 10 --output results/ --condition phase2 --csv

    # New --method workflow
    python benchmarks/shared_memory/run_evaluation.py --trials 10 --output results/ --method naive_concat
    python benchmarks/shared_memory/run_evaluation.py --trials 10 --output results/ --method all --csv
"""

import argparse
from typing import Optional
import logging
import os
import statistics
import sys
from datetime import datetime

import requests

# Ensure the project root is on sys.path when running as a script
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tqdm import tqdm

from benchmarks.shared_memory.models import (
    ConditionResults,
    ExperimentMetadata,
    ExperimentResults,
    MemoryCounts,
    TokenUsage,
    TrialResult,
)
from benchmarks.shared_memory.conditions import (
    CONDITIONS,
    KERNEL_INJECTION_CONDITIONS,
    AGENT_MANAGED_CONDITIONS,
    NATIVE_CONDITIONS,
    REPLICATED_CONDITIONS,
    canonical_condition,
    locus_of,
)
from benchmarks.shared_memory.judge import (
    JUDGE_PROMPT_VERSION,
    SCORER,
    HybridJudge,
    judge_prompt_sha256,
)
from benchmarks.shared_memory.dataset import (
    RANDOM,
    load as load_dataset,
    trial_input_sha256,
    v2_input_sha256,
)
from benchmarks.shared_memory import history
from benchmarks.shared_memory import judge_free as judge_free_measures
from benchmarks.shared_memory.pipeline import (
    AgentPipeline,
    MethodPipeline,
    extraction_failure,
    model_name,
)
from cerebrum.example.agents.variants import (
    CATALOG_VERSION as VARIANT_CATALOG_VERSION,
    schedule as variant_schedule,
)
from benchmarks.shared_memory.pilot_schedule import Schedule
from benchmarks.shared_memory.results import ResultsWriter
from benchmarks.shared_memory.synth import SyntheticDataGenerator
from cerebrum.config.config_manager import config

logger = logging.getLogger(__name__)

# All valid method names (excluding the meta-value "all")
_ALL_METHODS = list(CONDITIONS)


DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 20261105

# Heterogeneity (Subtask 10, AIOS docs/HETEROGENEITY.md). The default
# schedule seed was fixed before any heterogeneity trial ran.
HETEROGENEITY_LEVELS = (0, 1, 2)
DEFAULT_VARIANT_SEED = 20261106


class _Unjudged:
    """The scores of a trial run with --no-judge: none."""

    profile_usage_score = None
    task_usage_score = None
    integration_score = None
    judge_attempts = None


UNJUDGED = _Unjudged()


def with_decoding(llms: list | None, decoding: dict | None) -> list | None:
    """``llms`` with the decoding settings on every entry (Subtask 9d):
    the kernel applies an entry's ``temperature`` and ``seed`` to the
    call for that model. A ``None`` seed is left out."""
    if not llms or not decoding:
        return llms
    extra = {k: v for k, v in decoding.items() if v is not None}
    return [dict(entry, **extra) for entry in llms]


def _parse_model_arg(model_str: str | None) -> list | None:
    """Parse a 'name:backend' model string into an llms list.

    Accepts formats:
    - ``"qwen2.5:7b:ollama"``  → ``[{"name": "qwen2.5:7b", "backend": "ollama"}]``
    - ``"gpt-4.5:openai"``     → ``[{"name": "gpt-4.5", "backend": "openai"}]``
    - ``None``                 → ``None`` (use kernel default)

    The last colon-separated token is treated as the backend; everything
    before it is the model name.
    """
    if model_str is None:
        return None
    parts = model_str.rsplit(":", 1)
    if len(parts) == 2:
        name, backend = parts
        return [{"name": name, "backend": backend}]
    # No backend specified — pass name only
    return [{"name": model_str}]


def check_kernel_provider(kernel_url: str, expected: str) -> None:
    """Fail unless the live kernel serves memory from ``expected``.

    The provider is kernel configuration, so the harness cannot switch
    it; this only refuses to run against the wrong one.
    """
    response = requests.get(f"{kernel_url}/memory/config", timeout=10)
    response.raise_for_status()
    actual = response.json().get("provider")
    if actual != expected:
        raise SystemExit(
            f"--provider {expected}: the kernel at {kernel_url} serves "
            f"memory from {actual!r}"
        )


def read_backend_usage(kernel_url: str, user_id: str) -> dict:
    """The kernel's record of its memory backend's own LLM and embedding
    calls for one trial's user, as TokenUsage fields. Reading empties the
    record."""
    response = requests.get(
        f"{kernel_url}/memory/cost",
        params={"user_id": user_id}, timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    return {
        "backend_llm_tokens": TokenUsage(**body["backend_llm_tokens"]),
        "embedding_tokens": TokenUsage(**body["embedding_tokens"]),
    }


def check_kernel_mode(kernel_url: str, method: str) -> None:
    """Fail unless the kernel's memory mode fits the condition: a native
    or replicated condition (agent-managed memory) needs injection and
    extraction off, a kernel condition needs injection on. Other
    conditions are not checked."""
    methods = list(CONDITIONS) if method == "all" else [method]
    native = [m for m in methods if m in AGENT_MANAGED_CONDITIONS]
    kernel = [m for m in methods if m in KERNEL_INJECTION_CONDITIONS]
    if not native and not kernel:
        return
    response = requests.get(f"{kernel_url}/memory/config", timeout=10)
    response.raise_for_status()
    body = response.json()
    if "auto_inject" not in body or "auto_extract" not in body:
        raise SystemExit(
            f"the kernel at {kernel_url} does not report auto_inject / "
            "auto_extract; it predates the native conditions"
        )
    if native and (body["auto_inject"] or body["auto_extract"]):
        raise SystemExit(
            f"{native[0]} manages memory in the agents, but the kernel has "
            f"auto_inject={body['auto_inject']}, "
            f"auto_extract={body['auto_extract']}; set both false"
        )
    if kernel and not body["auto_inject"]:
        raise SystemExit(
            f"{kernel[0]} needs kernel injection, but the kernel has "
            "auto_inject=false"
        )


V2_SETTINGS = {"max_injected_memories": 10, "max_memory_tokens": 500,
               "relevance_threshold": 0.0, "block_format": "compact"}
V2_BARRIER_TIMEOUT_MS = 60_000


def check_v2_settings(kernel_url: str, method: str,
                      recency: bool = True) -> dict:
    """Fail unless the kernel's memory settings are benchmark v2's
    (AIOS docs/BENCHMARK_V2.md, "Pre-flight"); return what was checked,
    for the results file."""
    response = requests.get(f"{kernel_url}/memory/config", timeout=10)
    response.raise_for_status()
    body = response.json()
    pipeline = body.get("pipeline") or {}
    problems = []
    for key, want in V2_SETTINGS.items():
        if pipeline.get(key) != want:
            problems.append(f"{key} is {pipeline.get(key)!r}, not {want!r}")
    unit = pipeline.get("block_recency_unit", "time")
    if recency and (pipeline.get("block_recency") is not True
                    or unit != "session"):
        problems.append("session ages are off (block_recency "
                        f"{pipeline.get('block_recency')!r}, unit {unit!r})")
    if not recency and pipeline.get("block_recency") is not False:
        problems.append("--no-recency needs block_recency false")
    if canonical_condition(method) in KERNEL_INJECTION_CONDITIONS:
        timeout = (pipeline.get("write_barrier") or {}).get("timeout_ms")
        if not isinstance(timeout, (int, float)) or \
                timeout < V2_BARRIER_TIMEOUT_MS:
            problems.append(f"write_barrier.timeout_ms is {timeout!r}, not "
                            f">= {V2_BARRIER_TIMEOUT_MS}")
        if not (body.get("auto_inject") and body.get("auto_extract")):
            problems.append("a kernel method needs auto_inject and "
                            "auto_extract on")
    if problems:
        raise SystemExit("benchmark v2 pre-flight: " + "; ".join(problems))
    return {"pipeline": pipeline, "auto_inject": body.get("auto_inject"),
            "auto_extract": body.get("auto_extract"),
            "pipeline_version": body.get("pipeline_version")}


def build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Extracted as a standalone function so it can be imported and tested
    independently of the ``main()`` entry point.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Shared Memory Evaluation Harness — measures whether "
        "shared memory improves personalization quality.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help=(
            "Number of trials per condition (default: every user of "
            "--dataset; 10 with --dataset random)."
        ),
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=RANDOM,
        help=(
            "Fixed users: 'users_v1' (150), 'pilot_v1' (its first 30) or "
            "a dataset file. Trial i scores user i, so cells pair by "
            "trial index. 'random' (default) generates each trial's user "
            "with the assistant model; never use it for reported results."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/",
        help="Output directory for result files (default: results/).",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also write a CSV file alongside the JSON results.",
    )
    parser.add_argument(
        "--condition",
        choices=["both", "phase1", "phase2"],
        default=None,
        help=(
            "Legacy condition flag. When specified, maps phase1 → kernel_shared "
            "with share_memory=False and phase2 → kernel_shared with "
            "share_memory=True. Use --method for the new workflow."
        ),
    )
    parser.add_argument(
        "--method",
        type=canonical_condition,
        choices=[
            *CONDITIONS, *NATIVE_CONDITIONS, *REPLICATED_CONDITIONS, "all",
        ],
        default="kernel_shared",
        help=(
            "Personalization method to evaluate (default: kernel_shared). "
            "Use 'all' to run all four methods on the same trial data. "
            "Deprecated names are accepted with a warning."
        ),
    )
    parser.add_argument(
        "--kernel-url",
        type=str,
        default=None,
        help=(
            "AIOS kernel base URL (e.g. http://localhost:8001). "
            "Overrides the CEREBRUM_KERNEL_URL env var and config default."
        ),
    )
    parser.add_argument(
        "--assistant-model",
        type=str,
        default=None,
        help=(
            "LLM for the assistant and synthetic data generation, as "
            "'name:backend' (e.g. 'qwen2.5:7b:ollama' or 'gpt-4o-mini:openai'). "
            "Defaults to the kernel's currently selected model."
        ),
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help=(
            "LLM for the judge, as 'name:backend' "
            "(e.g. 'gpt-4.5:openai' or 'qwen2.5:7b:ollama'). "
            "Defaults to the same model as --assistant-model."
        ),
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help=(
            "Run-specific discriminator appended to user_id for namespace "
            "isolation. Prevents residual memories from prior runs from "
            "polluting current run results. When not specified, a random "
            "UUID suffix is generated automatically."
        ),
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help=(
            "Memory provider the kernel must be running (e.g. 'mem0', "
            "'in-house'). Checked against /memory/config before any "
            "trial; the run stops if it differs."
        ),
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=(
            "Temperature for every assistant and writer call (default "
            f"{DEFAULT_TEMPERATURE}). The judge keeps its own settings."
        ),
    )
    parser.add_argument(
        "--seed",
        type=str,
        default=str(DEFAULT_SEED),
        help=(
            "Seed for every assistant and writer call where the backend "
            f"accepts one (default {DEFAULT_SEED}; 'none' for no seed)."
        ),
    )
    parser.add_argument(
        "--sampled",
        action="store_true",
        help=(
            "Use the kernel's default sampling (temperature 1.0, no "
            "seed) instead of fixed decoding; for comparison with runs "
            "before Subtask 9d only."
        ),
    )
    parser.add_argument(
        "--heterogeneity",
        type=int,
        choices=list(HETEROGENEITY_LEVELS),
        default=0,
        help=(
            "Heterogeneity level H: how many of the three agents deviate "
            "from the reference, each with a catalog variant chosen by "
            "the seeded schedule (AIOS docs/HETEROGENEITY.md), or by "
            "--schedule. A scored run at H > 0 needs --schedule (the "
            "pre-registered pilot schedule); otherwise pass --no-judge."
        ),
    )
    parser.add_argument(
        "--variant-seed",
        type=int,
        default=DEFAULT_VARIANT_SEED,
        help=(
            "Seed of the heterogeneity schedule (default "
            f"{DEFAULT_VARIANT_SEED}); the same in every cell keeps "
            "cells paired."
        ),
    )
    parser.add_argument(
        "--schedule",
        type=str,
        default=None,
        help=(
            "A committed heterogeneity schedule file (e.g. "
            "benchmarks/shared_memory/data/pilot_v1_schedule.json, AIOS "
            "docs/PILOT.md): user i at level H gets the file's variants "
            "instead of the seeded cycle. Must name the --dataset."
        ),
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help=(
            "Do not judge: trials carry no scores, only the judge-free "
            "measures (functional checks)."
        ),
    )
    parser.add_argument(
        "--control",
        choices=history.CONTROLS,
        default=None,
        help=(
            "Benchmark v2 negative control (AIOS docs/BENCHMARK_V2.md, "
            "\"Functional check\"): no_memory skips the sessions, "
            "no_delete makes revokes delete nothing, no_visibility makes "
            "the native consumer ignore visibility. Needs --no-judge."
        ),
    )
    parser.add_argument(
        "--no-recency",
        action="store_true",
        help=(
            "Benchmark v2 without session ages (an ablation); the kernel "
            "must then report block_recency false."
        ),
    )
    parser.add_argument(
        "--kernel-logs",
        type=str,
        default=None,
        help=(
            "Path to captured AIOS kernel stdout file. When provided, the "
            "orchestrator parses injection log lines and cross-references "
            "them with harness-side audit results for ground truth verification."
        ),
    )
    return parser


class EvaluationOrchestrator:
    """Orchestrates the shared memory evaluation experiment.

    Args:
        trials: Number of trials to run per condition.
        output_dir: Directory path for writing result files.
        write_csv: If True, also write a CSV file alongside JSON.
        condition: Legacy condition flag — "both", "phase1", "phase2", or None.
            When set, the orchestrator uses the legacy AgentPipeline path for
            backward compatibility.
        method: Method to evaluate — one of "kernel_shared", "naive_concat",
            "vanilla_rag", "kernel_private", or "all". Ignored when ``condition``
            is set.
    """

    def __init__(
        self,
        trials: int,
        output_dir: str,
        write_csv: bool,
        condition: str,
        method: str = "kernel_shared",
        assistant_llms: list | None = None,
        judge_llms: list | None = None,
        kernel_url: str | None = None,
        run_id: str | None = None,
        kernel_logs_path: str | None = None,
        dataset: str = RANDOM,
        decoding: dict | None = None,
        heterogeneity: int = 0,
        variant_seed: int | None = None,
        judge: bool = True,
        schedule: str | None = None,
        control: str | None = None,
        recency: bool = True,
        preflight: dict | None = None,
    ):
        if heterogeneity not in HETEROGENEITY_LEVELS:
            raise ValueError(
                f"heterogeneity must be one of {HETEROGENEITY_LEVELS}"
            )
        if heterogeneity and judge and schedule is None:
            raise ValueError(
                "a scored heterogeneity run needs --schedule (the "
                "pre-registered schedule); otherwise pass --no-judge"
            )
        if heterogeneity and condition is not None:
            raise ValueError("heterogeneity needs --method, not --condition")
        self.heterogeneity = heterogeneity
        self.variant_seed = (
            DEFAULT_VARIANT_SEED if variant_seed is None else variant_seed
        )
        self.judged = judge
        self.dataset = load_dataset(dataset)
        self.dataset_name = self.dataset.name if self.dataset else RANDOM
        # Benchmark v2 (AIOS docs/BENCHMARK_V2.md): a scripted history
        # per user, then the probes.
        self.v2 = bool(self.dataset and self.dataset.version == 2)
        self.control = control
        self.recency = recency
        self.preflight = preflight
        if control is not None and not self.v2:
            raise ValueError("--control needs a benchmark v2 dataset")
        if control is not None and judge:
            raise ValueError("a negative control runs without the judge: "
                             "pass --no-judge")
        if self.v2 and condition is not None:
            raise ValueError("benchmark v2 needs --method, not --condition")
        if self.v2 and canonical_condition(method) not in \
                MethodPipeline.V2_METHODS:
            raise ValueError(f"benchmark v2 runs {MethodPipeline.V2_METHODS},"
                             f" not {method}")
        self._embed = None
        self.schedule = Schedule(schedule) if schedule else None
        if self.schedule and self.schedule.dataset != self.dataset_name:
            raise ValueError(
                f"--schedule {self.schedule.name} is for "
                f"{self.schedule.dataset}, not {self.dataset_name}"
            )
        if trials is None:
            trials = len(self.dataset) if self.dataset else 10
        if self.dataset and trials > len(self.dataset):
            raise ValueError(
                f"--trials {trials}: {self.dataset_name} has "
                f"{len(self.dataset)} users"
            )
        self.trials = trials
        self.output_dir = output_dir
        self.write_csv = write_csv
        self.condition = condition
        self.method = canonical_condition(method)
        # The judge falls back to the assistant model, without the
        # assistant's decoding: it keeps its own settings.
        self.judge_llms = judge_llms or assistant_llms
        # Fixed decoding for every assistant and writer call (Subtask
        # 9d) rides on the llms entries; the agents all take this list.
        if decoding and not assistant_llms:
            raise ValueError(
                "fixed decoding needs --assistant-model: the decoding "
                "rides on the model entry (or pass --sampled)"
            )
        self.decoding = decoding
        self.assistant_llms = with_decoding(assistant_llms, decoding)
        self.run_id = run_id  # None → SyntheticDataGenerator auto-generates UUID

        # Resolve kernel URL: CLI arg > config default
        resolved_url = kernel_url or config.get_kernel_url()
        self.kernel_url = resolved_url

        self.generator = SyntheticDataGenerator(llms=self.assistant_llms, run_id=self.run_id)
        self.generator.kernel_url = resolved_url

        self.judge = HybridJudge(llms=self.judge_llms)
        self.judge.llm_judge.kernel_url = resolved_url

        self.writer = ResultsWriter(output_dir=output_dir, write_csv=write_csv)

        # Kernel log cross-reference: deferred to after trials complete.
        # The log file is written by the kernel DURING the run, so we parse
        # it after all trials finish and retroactively update injection_status.
        self.kernel_logs_path = kernel_logs_path
        self.kernel_log_counts: dict[str, int] | None = None

    def _cross_reference_kernel_logs(self, trials: list[TrialResult]) -> None:
        """Parse kernel logs after trials complete and update injection_status.

        The kernel appends injection lines to the log file DURING the run,
        so this must be called AFTER all trials finish. It retroactively
        updates each trial's retrieval_log.injection_status based on the
        kernel's ground truth.
        """
        if not self.kernel_logs_path:
            return

        from benchmarks.shared_memory.kernel_log_parser import parse_injection_lines
        try:
            self.kernel_log_counts = parse_injection_lines(self.kernel_logs_path)
            logger.info(
                "Post-run kernel log cross-reference: %d user_ids with injection data from %s",
                len(self.kernel_log_counts), self.kernel_logs_path,
            )
        except (FileNotFoundError, OSError) as e:
            logger.warning(
                "Failed to load kernel logs from %s: %s. "
                "Skipping post-run cross-reference.",
                self.kernel_logs_path, e,
            )
            return

        for trial in trials:
            if trial.failed or not trial.retrieval_log:
                continue
            # Look up user_id from the trial's synthetic data
            user_id = getattr(trial, "_user_id", None)
            if not user_id and trial.synthetic_profile:
                # Reconstruct from profile — but we don't have run_id here.
                # Use retrieval_log metadata or fall back to scanning all keys.
                pass
            # Try matching by checking all kernel log user_ids against trial index
            # The most reliable approach: check if any kernel log user_id
            # is a substring match for this trial's profile name.
            profile_name = ""
            if trial.synthetic_profile:
                profile_name = trial.synthetic_profile.user_name.lower().replace(" ", "_")

            kernel_count = 0
            for uid, count in self.kernel_log_counts.items():
                if profile_name and profile_name in uid:
                    kernel_count = count
                    break

            audit_count = trial.retrieval_log.shared_memory_count
            if kernel_count > 0 and audit_count == 0:
                logger.info(
                    "Trial %d: Kernel log confirms %d injections for '%s' "
                    "but audit returned 0. Updating injection_status.",
                    trial.trial_index, kernel_count, profile_name,
                )
                trial.retrieval_log.injection_status = "kernel_confirmed_audit_missed"
            elif kernel_count > 0 and audit_count > 0:
                logger.info(
                    "Trial %d: Kernel log (%d) and audit (%d) agree for '%s'.",
                    trial.trial_index, kernel_count, audit_count, profile_name,
                )

    def trial_data(self, trial_index: int):
        """Trial ``trial_index``'s user: the dataset's user of that
        index, or a freshly generated one with ``--dataset random``."""
        if self.dataset is not None:
            return self.dataset.trial_data(trial_index, self.generator.run_id)
        return self.generator.generate_trial_data(trial_index)

    def _heterogeneity_metadata(self) -> dict:
        """``{level, variant_seed, catalog_version}`` for the results
        file (AIOS docs/HETEROGENEITY.md)."""
        out = {
            "level": getattr(self, "heterogeneity", 0),
            "variant_seed": getattr(
                self, "variant_seed", DEFAULT_VARIANT_SEED
            ),
            "catalog_version": VARIANT_CATALOG_VERSION,
        }
        if getattr(self, "schedule", None):
            out.update(self.schedule.metadata())
        return out

    def trial_variants(self, trial_index: int) -> dict:
        """``{agent: variant}`` for user ``trial_index``: from the
        schedule file when given, else the seeded cycle."""
        level = getattr(self, "heterogeneity", 0)
        if getattr(self, "schedule", None):
            return self.schedule.variants(level, trial_index)
        return variant_schedule(self.variant_seed, level, trial_index)

    def run_single_trial(
        self,
        trial_index: int,
        condition: str,
        pipeline: AgentPipeline,
        method: str = "",
        trial_data=None,
    ) -> TrialResult:
        """Execute one trial with log-and-continue error handling.

        Args:
            trial_index: Zero-based trial index.
            condition: Condition label for the trial result (e.g. "phase1",
                "kernel_shared", "naive_concat").
            pipeline: The AgentPipeline (or MethodPipeline) to run.
            method: Method name to record on the TrialResult. When empty,
                the condition string is used as the method label.
            trial_data: Pre-generated SyntheticTrialData to reuse. When None,
                the orchestrator generates fresh data for this trial.

        Returns:
            TrialResult with all fields populated.
        """
        effective_method = method if method else condition
        if getattr(self, "v2", False):
            return self.run_single_trial_v2(
                trial_index, condition, pipeline, effective_method)

        # Step 1: Generate (or reuse) synthetic data
        if trial_data is None:
            try:
                trial_data = self.trial_data(trial_index)
            except Exception as e:
                logger.error("Trial %d: synthetic data generation failed: %s", trial_index, e)
                return TrialResult(
                    trial_index=trial_index,
                    condition=condition,
                    method=effective_method,
                    failed=True,
                    error_message=str(e),
                )

        # Step 2: Run agent pipeline
        variants = self.trial_variants(trial_index)
        try:
            if variants:
                pipeline_result = pipeline.run_trial(
                    trial_data, variants=variants
                )
            else:
                pipeline_result = pipeline.run_trial(trial_data)
        except Exception as e:
            logger.error("Trial %d: agent pipeline failed: %s", trial_index, e)
            return TrialResult(
                trial_index=trial_index,
                condition=condition,
                method=effective_method,
                failed=True,
                error_message=str(e),
                synthetic_profile=trial_data.profile,
                synthetic_task_context=trial_data.task_context,
                follow_up_query=trial_data.follow_up_query,
            )

        common = {
            "writer_retries": pipeline_result.writer_retries,
            "writer_attempt_settings": pipeline_result.writer_attempt_settings,
            "backend_extraction": pipeline_result.backend_extraction,
            "writer_stored_rows": dict(getattr(
                pipeline_result, "writer_stored_rows", {}) or {}),
            "decoding": pipeline_result.decoding,
            "dataset": self.dataset_name,
            "input_sha256": trial_input_sha256(trial_data),
            "heterogeneity_level": getattr(self, "heterogeneity", 0),
            "variants_applied": getattr(
                pipeline_result, "variants_applied", {}) or {},
            "variants_not_applied": getattr(
                pipeline_result, "variants_not_applied", {}) or {},
            "judge_free": getattr(pipeline_result, "judge_free", None),
        }
        if pipeline_result.writer_failed:
            # A writer stored nothing (Subtask 9): counted, not scored.
            logger.warning(
                "Trial %d: writer failed: %s", trial_index,
                pipeline_result.writer_failed,
            )
            return TrialResult(
                trial_index=trial_index,
                condition=condition,
                method=effective_method,
                failed=True,
                error_message=(
                    "writer_failed: "
                    + ", ".join(pipeline_result.writer_failed)
                ),
                writer_failed=pipeline_result.writer_failed,
                follow_up_query=trial_data.follow_up_query,
                plausible_actions=trial_data.plausible_actions,
                synthetic_profile=trial_data.profile,
                synthetic_task_context=trial_data.task_context,
                written_memories=pipeline_result.written_memories,
                writer_tokens=pipeline_result.writer_tokens,
                pipeline_version=pipeline_result.pipeline_version,
                **common,
            )

        # Extract retrieval log from pipeline result
        retrieval_log = pipeline_result.retrieval_log

        # Phase 1 isolation verification
        if condition == "phase1" and retrieval_log:
            if not retrieval_log.cross_agent_found:
                logger.info("Trial %d: Phase 1 isolation verified — zero cross-agent memories.", trial_index)
            else:
                entries = [(e.owner_agent, e.memory_type) for e in retrieval_log.retrieved_memories]
                logger.warning(
                    "Trial %d: Cross-agent memory leakage detected! count=%d entries=%s",
                    trial_index, len([e for e in retrieval_log.retrieved_memories if e.owner_agent != "assistant_agent"]), entries,
                )

        # Phase 2 retrieval audit
        if condition == "phase2" and retrieval_log:
            entries = [(e.owner_agent, e.memory_type) for e in retrieval_log.retrieved_memories]
            logger.info(
                "Trial %d: Retrieved %d shared memories. Entries: %s",
                trial_index, retrieval_log.shared_memory_count, entries,
            )

        # Kernel log cross-reference is now handled post-run by
        # _cross_reference_kernel_logs() after all trials complete.

        # Step 3: Judge the assistant response (not with --no-judge)
        try:
            if not getattr(self, "judged", True):
                scores = UNJUDGED
            else:
                scores = self.judge.evaluate(
                    query=trial_data.follow_up_query,
                    response=pipeline_result.assistant_response,
                    profile=trial_data.profile,
                    task_context=trial_data.task_context,
                )
        except Exception as e:
            # No keyword-only fallback (Subtask 4b): the trial fails.
            logger.error("Trial %d: judge failed: %s", trial_index, e)
            return TrialResult(
                trial_index=trial_index,
                condition=condition,
                method=effective_method,
                failed=True,
                error_message=f"judge: {e}",
                judge_attempts=getattr(e, "attempts", None),
                follow_up_query=trial_data.follow_up_query,
                plausible_actions=trial_data.plausible_actions,
                assistant_response=pipeline_result.assistant_response or "",
                synthetic_profile=trial_data.profile,
                synthetic_task_context=trial_data.task_context,
                injection_diagnostics=pipeline_result.injection_diagnostics,
                written_memories=pipeline_result.written_memories,
                pipeline_version=pipeline_result.pipeline_version,
                **common,
            )
        attempts = getattr(scores, "judge_attempts", None)

        # Read after judging, so the kernel's background conversation
        # write (and its embedding call) has finished.
        backend_usage = {
            "backend_llm_tokens": pipeline_result.backend_llm_tokens,
            "embedding_tokens": pipeline_result.embedding_tokens,
        }
        if (pipeline_result.backend_llm_tokens is None
                and pipeline_result.backend_usage_user_id):
            try:
                backend_usage = read_backend_usage(
                    self.kernel_url, pipeline_result.backend_usage_user_id
                )
            except requests.RequestException as e:
                logger.warning(
                    "Trial %d: backend usage unavailable: %s", trial_index, e
                )
        backend_usage = {
            key: value or TokenUsage() for key, value in backend_usage.items()
        }
        # A backend that extracts but stored or called nothing failed
        # silently: the trial is failed, not completed (Subtask 10).
        silent = extraction_failure(
            pipeline_result.backend_extraction,
            common["writer_stored_rows"],
            backend_usage["backend_llm_tokens"],
        )
        if silent:
            logger.error("Trial %d: %s", trial_index, silent)
            return TrialResult(
                trial_index=trial_index,
                condition=condition,
                method=effective_method,
                failed=True,
                error_message=silent,
                follow_up_query=trial_data.follow_up_query,
                plausible_actions=trial_data.plausible_actions,
                assistant_response=pipeline_result.assistant_response or "",
                synthetic_profile=trial_data.profile,
                synthetic_task_context=trial_data.task_context,
                injection_diagnostics=pipeline_result.injection_diagnostics,
                written_memories=pipeline_result.written_memories,
                token_usage=pipeline_result.token_usage,
                writer_tokens=pipeline_result.writer_tokens,
                pipeline_version=pipeline_result.pipeline_version,
                **common,
                **backend_usage,
            )

        return TrialResult(
            trial_index=trial_index,
            condition=condition,
            method=effective_method,
            profile_usage_score=scores.profile_usage_score,
            task_usage_score=scores.task_usage_score,
            integration_score=scores.integration_score,
            memory_counts=MemoryCounts.of(pipeline_result.written_memories),
            retrieved_context_count=pipeline_result.retrieved_context_count,
            latency_seconds=pipeline_result.latency_seconds,
            follow_up_query=trial_data.follow_up_query,
            plausible_actions=trial_data.plausible_actions,
            assistant_response=pipeline_result.assistant_response or "",
            synthetic_profile=trial_data.profile,
            synthetic_task_context=trial_data.task_context,
            retrieval_log=retrieval_log,
            injection_diagnostics=pipeline_result.injection_diagnostics,
            written_memories=pipeline_result.written_memories,
            token_usage=pipeline_result.token_usage,
            writer_tokens=pipeline_result.writer_tokens,
            latency_breakdown=pipeline_result.latency_breakdown,
            pipeline_version=pipeline_result.pipeline_version,
            scorer=SCORER if scores is not UNJUDGED else None,
            judge_attempts=attempts if isinstance(attempts, int) else None,
            **common,
            **backend_usage,
        )

    # -- benchmark v2 (AIOS docs/BENCHMARK_V2.md, "Harness") -------------

    def _recorded_run_id(self) -> Optional[str]:
        """The run id the users' ids carry: ``--run-id``, else the one
        the generator drew."""
        run_id = getattr(self.generator, "run_id", None)
        return self.run_id or (run_id if isinstance(run_id, str) else None)

    def _run_settings(self) -> dict:
        """What a v2 results file records about the run's settings."""
        if not getattr(self, "v2", False):
            return {}
        return {"benchmark": "v2", "control": self.control,
                "recency": self.recency, "preflight": self.preflight}

    def _embedder(self):
        """The pinned embedding model as ``embed(texts)`` for the probes'
        semantic diagnostic; None when it cannot be reached (the
        semantic fields are then None; no pass depends on them)."""
        if self._embed is not None:
            return self._embed or None
        try:
            from cerebrum.example.agents.native.backends import Embedder

            embedding = AgentPipeline._kernel_memory_config()["embedding"]
            model = Embedder(embedding)
            self._embed = lambda texts: [model(t) for t in texts]
        except Exception as e:  # never fails a trial
            logger.warning("Semantic probe diagnostic off: %s", e)
            self._embed = False
        return self._embed or None

    def run_single_trial_v2(self, trial_index: int, condition: str,
                            pipeline, method: str) -> TrialResult:
        """One benchmark v2 user: the history and the probes through the
        method's locus, the probes scored, the integration probe judged;
        any failure the spec lists fails the user."""
        base = {
            "trial_index": trial_index, "condition": condition,
            "method": method, "dataset": self.dataset_name,
            "heterogeneity_level": getattr(self, "heterogeneity", 0),
            "control": self.control,
        }
        try:
            user = self.dataset.user_v2(trial_index, self.generator.run_id)
        except Exception as e:
            return TrialResult(**base, failed=True, error_message=str(e))
        base.update(
            input_sha256=v2_input_sha256(user),
            follow_up_query=user.follow_up_query,
            plausible_actions=user.plausible_actions,
            synthetic_profile=user.profile,
            synthetic_task_context=user.task_context,
        )
        variants = self.trial_variants(trial_index)
        try:
            user, outcome, locus = pipeline.run_history_trial(
                user, variants or None, control=self.control,
                recency_session=self.recency,
            )
        except Exception as e:
            logger.error("Trial %d: history failed: %s", trial_index, e)
            return TrialResult(**base, failed=True,
                               error_message=f"history: {e}")
        common = {
            "user_id": user.user_id,
            "sessions": outcome.sessions,
            "variants_applied": outcome.variants_applied,
            "variants_not_applied": outcome.variants_not_applied,
            "backend_extraction": outcome.backend_extraction,
            "pipeline_version": outcome.pipeline_version,
            "written_memories": outcome.written,
            "memory_counts": MemoryCounts.of(outcome.written),
            "deleted_memory_ids": history.deleted_ids(outcome),
        }
        results = history.score_turns(user, outcome, locus,
                                      embed=self._embedder())
        common["probe_results"] = results
        if outcome.failure:
            logger.error("Trial %d: %s", trial_index, outcome.failure)
            return TrialResult(**base, **common, failed=True,
                               error_message=outcome.failure)
        integration = next(r for r in results if r.type == "integration")
        scores = UNJUDGED
        if getattr(self, "judged", True):
            try:
                scores = self.judge.evaluate(
                    query=user.follow_up_query,
                    response=integration.observed,
                    profile=user.profile, task_context=user.task_context,
                )
            except Exception as e:
                logger.error("Trial %d: judge failed: %s", trial_index, e)
                return TrialResult(**base, **common, failed=True,
                                   error_message=f"judge: {e}",
                                   judge_attempts=getattr(e, "attempts",
                                                          None))
            integration.judge_scores = {
                "profile_usage_score": scores.profile_usage_score,
                "task_usage_score": scores.task_usage_score,
                "integration_score": scores.integration_score,
            }
            integration.integration_score = scores.integration_score
        # Read after the probes (and the judge), so the kernel's last
        # background conversation write is counted.
        backend = {"backend_llm_tokens": outcome.backend_llm_tokens,
                   "embedding_tokens": outcome.embedding_tokens}
        if outcome.backend_llm_tokens is None:
            try:
                backend = read_backend_usage(self.kernel_url, user.user_id)
            except requests.RequestException as e:
                logger.warning("Trial %d: backend usage unavailable: %s",
                               trial_index, e)
        backend = {k: v or TokenUsage() for k, v in backend.items()}
        silent = history.extraction_failure(
            user, outcome, outcome.backend_extraction)
        wrote = self.control != "no_memory" and history.write_events(user)
        if (silent is None and outcome.backend_extraction is True and wrote
                and backend["backend_llm_tokens"].calls == 0):
            silent = "backend_extraction_failed: no backend LLM calls recorded"
        attempts = getattr(scores, "judge_attempts", None)
        trial = TrialResult(
            **base, **common,
            reappeared_memory_ids=history.reappeared_ids(outcome),
            revoked_value_rows=history.revoked_value_rows(user, outcome),
            assistant_response=integration.observed,
            injection_diagnostics=integration.diagnostics,
            judge_free=judge_free_measures.measure(
                user.profile, user.user_id, integration.diagnostics,
                outcome.written,
            ),
            profile_usage_score=scores.profile_usage_score,
            task_usage_score=scores.task_usage_score,
            integration_score=scores.integration_score,
            token_usage=TokenUsage.of_calls(
                [r.token_usage for r in results],
                model_name(self.assistant_llms)),
            latency_seconds=sum(r.latency_seconds or 0.0 for r in results),
            decoding=(outcome.turns[0].result or {}).get("decoding")
            if outcome.turns else None,
            scorer=SCORER if scores is not UNJUDGED else None,
            judge_attempts=attempts if isinstance(attempts, int) else None,
            **backend,
        )
        if silent:
            logger.error("Trial %d: %s", trial_index, silent)
            trial.failed, trial.error_message = True, silent
        return trial

    def run(self) -> ExperimentResults:
        """Run the full experiment across all requested conditions/methods.

        When ``--condition`` is set (legacy path), the orchestrator uses
        ``AgentPipeline`` directly with the appropriate ``share_memory`` flag,
        preserving the original behavior exactly.

        When ``--method`` is used (new path), the orchestrator uses
        ``MethodPipeline`` for all methods. When ``--method all`` is specified,
        one ``SyntheticTrialData`` instance is generated per trial index and
        reused across all four method pipelines.
        """
        # ----------------------------------------------------------------
        # Legacy --condition path (backward compatible)
        # ----------------------------------------------------------------
        if self.condition is not None:
            return self._run_legacy_condition()

        # ----------------------------------------------------------------
        # New --method path
        # ----------------------------------------------------------------
        return self._run_method()

    def _run_legacy_condition(self) -> ExperimentResults:
        """Run the legacy --condition phase1/phase2 workflow unchanged."""
        if self.condition == "both":
            conditions = ["phase1", "phase2"]
        elif self.condition == "phase1":
            conditions = ["phase1"]
        else:
            conditions = ["phase2"]

        condition_results = []

        for cond in conditions:
            share_memory = cond == "phase2"
            pipeline = AgentPipeline(share_memory=share_memory, assistant_llms=self.assistant_llms)
            logger.info(
                "Running condition '%s' (share_memory=%s, kernel auto_inject assumed ON).",
                cond,
                share_memory,
            )

            trials: list[TrialResult] = []
            for i in tqdm(range(self.trials), desc=f"Condition: {cond}"):
                result = self.run_single_trial(i, cond, pipeline)
                trials.append(result)

            summary = self.writer.compute_summary_statistics(trials)
            condition_results.append(
                ConditionResults(condition=cond, trials=trials, summary=summary)
            )

        # Post-run kernel log cross-reference
        all_trials = [t for cr in condition_results for t in cr.trials]
        self._cross_reference_kernel_logs(all_trials)

        metadata = ExperimentMetadata(
            trials_per_condition=self.trials,
            timestamp=datetime.now().isoformat(),
            kernel_url=config.get_kernel_url(),
            judge_prompt_version=JUDGE_PROMPT_VERSION,
            judge_prompt_sha256=judge_prompt_sha256(),
            conditions_run=conditions,
            dataset=self.dataset.describe() if self.dataset else None,
            decoding=self.decoding,
            judge_temperature=self.judge.temperature,
            judge_seed=self.judge.seed,
            judged=getattr(self, "judged", True),
            heterogeneity=self._heterogeneity_metadata(),
            run_settings=self._run_settings(),
            run_id=self._recorded_run_id(),
        )

        experiment = ExperimentResults(
            experiment_metadata=metadata,
            conditions=condition_results,
        )

        json_path = self.writer.write_json(experiment)
        logger.info("Results written to %s", json_path)

        if self.write_csv:
            csv_path = self.writer.write_csv(experiment)
            logger.info("CSV written to %s", csv_path)

        return experiment

    def _run_method(self) -> ExperimentResults:
        """Run the new --method workflow using MethodPipeline."""
        # Determine which methods to run
        if self.method == "all":
            methods_to_run = list(_ALL_METHODS)
        else:
            methods_to_run = [self.method]

        condition_results = []

        for method_name in methods_to_run:
            pipeline = MethodPipeline(method=method_name, assistant_llms=self.assistant_llms)
            logger.info("Running method '%s'.", method_name)

            trials: list[TrialResult] = []

            if self.method == "all":
                # Generate one SyntheticTrialData per trial index and reuse
                # it across all methods so scores are directly comparable.
                # The trial data cache is built on the first method pass and
                # reused for subsequent methods.
                if not hasattr(self, "_trial_data_cache"):
                    self._trial_data_cache: dict = {}

                for i in tqdm(range(self.trials), desc=f"Method: {method_name}"):
                    if i not in self._trial_data_cache:
                        try:
                            self._trial_data_cache[i] = self.trial_data(i)
                        except Exception as e:
                            logger.error("Trial %d: synthetic data generation failed: %s", i, e)
                            trials.append(TrialResult(
                                trial_index=i,
                                condition=method_name,
                                method=method_name,
                                failed=True,
                                error_message=str(e),
                            ))
                            continue

                    cached_data = self._trial_data_cache[i]
                    result = self.run_single_trial(
                        i, method_name, pipeline,
                        method=method_name,
                        trial_data=cached_data,
                    )
                    trials.append(result)
            else:
                # Single method — generate fresh data per trial
                for i in tqdm(range(self.trials), desc=f"Method: {method_name}"):
                    result = self.run_single_trial(
                        i, method_name, pipeline,
                        method=method_name,
                    )
                    trials.append(result)

            summary = self.writer.compute_summary_statistics(trials)
            condition_results.append(
                ConditionResults(condition=method_name, trials=trials, summary=summary)
            )

        # Post-run kernel log cross-reference
        all_trials = [t for cr in condition_results for t in cr.trials]
        self._cross_reference_kernel_logs(all_trials)

        # Determine output filename
        if self.method == "all":
            output_filename = "results_all_methods.json"
        else:
            output_filename = f"results_{self.method}.json"

        metadata = ExperimentMetadata(
            trials_per_condition=self.trials,
            timestamp=datetime.now().isoformat(),
            kernel_url=config.get_kernel_url(),
            judge_prompt_version=JUDGE_PROMPT_VERSION,
            judge_prompt_sha256=judge_prompt_sha256(),
            conditions_run=methods_to_run,
            methods_run=methods_to_run,
            dataset=self.dataset.describe() if self.dataset else None,
            decoding=self.decoding,
            judge_temperature=self.judge.temperature,
            judge_seed=self.judge.seed,
            judged=getattr(self, "judged", True),
            heterogeneity=self._heterogeneity_metadata(),
            run_settings=self._run_settings(),
            run_id=self._recorded_run_id(),
        )

        experiment = ExperimentResults(
            experiment_metadata=metadata,
            conditions=condition_results,
        )

        json_path = self.writer.write_json(experiment, filename=output_filename)
        logger.info("Results written to %s", json_path)

        if self.write_csv:
            csv_path = self.writer.write_csv(experiment)
            logger.info("CSV written to %s", csv_path)

        # Print comparative summary after all methods complete
        self.writer.print_summary(experiment)

        return experiment


def decoding_from_args(args) -> dict | None:
    """``{"temperature", "seed"}`` from the CLI; None with --sampled."""
    if args.sampled:
        return None
    seed = None if str(args.seed).lower() == "none" else int(args.seed)
    return {"temperature": args.temperature, "seed": seed}


def main():
    """Parse CLI arguments and run the evaluation orchestrator."""
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    kernel_url = args.kernel_url or config.get_kernel_url()
    if args.provider:
        check_kernel_provider(kernel_url, args.provider)
    if args.condition is None:
        check_kernel_mode(kernel_url, canonical_condition(args.method))
    dataset_spec = (load_dataset(args.dataset)
                    if isinstance(args.dataset, str) else None)
    preflight = None
    if dataset_spec is not None and dataset_spec.version == 2:
        preflight = check_v2_settings(kernel_url, args.method,
                                      recency=not args.no_recency)

    orchestrator = EvaluationOrchestrator(
        trials=args.trials,
        output_dir=args.output,
        write_csv=args.csv,
        condition=args.condition,
        method=args.method,
        assistant_llms=_parse_model_arg(args.assistant_model),
        judge_llms=_parse_model_arg(args.judge_model),
        run_id=args.run_id,
        kernel_logs_path=args.kernel_logs,
        dataset=args.dataset,
        decoding=decoding_from_args(args),
        heterogeneity=args.heterogeneity,
        variant_seed=args.variant_seed,
        judge=not args.no_judge,
        schedule=args.schedule,
        control=args.control,
        recency=not args.no_recency,
        preflight=preflight,
    )

    experiment = orchestrator.run()

    # Legacy --condition path: print the original summary format
    if args.condition is not None:
        meta = experiment.experiment_metadata
        print(f"\n{'=' * 60}")
        print(f"Experiment complete — {meta.timestamp}")
        print(f"Conditions: {', '.join(meta.conditions_run)}")
        print(f"Trials per condition: {meta.trials_per_condition}")
        print(f"{'=' * 60}")

        for cond_result in experiment.conditions:
            s = cond_result.summary
            print(f"\n--- {cond_result.condition} ---")
            print(f"  Profile Usage:      mean={s.profile_usage.mean:.2f}  std={s.profile_usage.std:.2f}")
            print(f"  Task Usage:         mean={s.task_usage.mean:.2f}  std={s.task_usage.std:.2f}")
            print(f"  Integration:        mean={s.integration.mean:.2f}  std={s.integration.std:.2f}")
            print(f"  Latency (s):        mean={s.latency.mean:.2f}  std={s.latency.std:.2f}")
            print(f"  Memory total:       mean={s.memory_total.mean:.2f}")
            print(f"  Injected memories:  mean={s.injected_memories.mean:.2f}  std={s.injected_memories.std:.2f}")
            print(f"  Trials: {s.total_trials} total, {s.failed_trials} failed")

            non_failed = [t for t in cond_result.trials if not t.failed]
            mean_shared = statistics.mean([
                t.retrieval_log.shared_memory_count
                for t in non_failed if t.retrieval_log
            ]) if any(t.retrieval_log for t in non_failed) else 0.0
            cross_agent_count = sum(
                1 for t in non_failed if t.retrieval_log and t.retrieval_log.cross_agent_found
            )
            print(f"  Shared mem retrieved: mean={mean_shared:.2f}")
            print(f"  Cross-agent trials:  {cross_agent_count}/{len(non_failed)}")

        # Comparative analysis: Phase 1 vs Phase 2
        conditions_by_name = {c.condition: c.summary for c in experiment.conditions}
        if "phase1" in conditions_by_name and "phase2" in conditions_by_name:
            p1 = conditions_by_name["phase1"]
            p2 = conditions_by_name["phase2"]

            print(f"\n{'=' * 60}")
            print("Comparative Analysis: Phase 1 (private) vs Phase 2 (shared)")
            print(f"{'=' * 60}")
            header = f"  {'Metric':<22} {'Phase1':>12} {'Phase2':>12} {'Delta':>12}"
            print(header)
            print(f"  {'-' * 58}")

            rows = [
                ("Profile Usage mean", p1.profile_usage.mean, p2.profile_usage.mean),
                ("Profile Usage std", p1.profile_usage.std, p2.profile_usage.std),
                ("Task Usage mean", p1.task_usage.mean, p2.task_usage.mean),
                ("Task Usage std", p1.task_usage.std, p2.task_usage.std),
                ("Integration mean", p1.integration.mean, p2.integration.mean),
                ("Integration std", p1.integration.std, p2.integration.std),
                ("Injected mem mean", p1.injected_memories.mean, p2.injected_memories.mean),
            ]
            for label, v1, v2 in rows:
                delta = v2 - v1
                sign = "+" if delta >= 0 else ""
                print(f"  {label:<22} {v1:>12.2f} {v2:>12.2f} {sign + f'{delta:.2f}':>12}")

        print()


if __name__ == "__main__":
    main()
