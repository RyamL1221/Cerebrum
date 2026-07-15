"""Trial discovery, normalization, and eligibility validation.

Loads finalized GPT-4o benchmark result files for all four methods and
converts their heterogeneous raw records into validated SourceTrial objects
suitable for stratified sampling.

Public functions:
- discover_result_files() — find result JSONs by method
- load_result_file() — parse a single result file into SourceTrial objects
- load_eligible_trials() — load all methods and validate pool eligibility
- summarize_trial_pool() — produce a developer-facing method summary

Design decisions:
- original_trial_id is the method-independent trial_index (as a string).
  Cross-method uniqueness is enforced via (source_method, original_trial_id).
  Since the existing gpt4o result files were generated independently per
  method, trial_index=N in different methods represents different scenarios.
  Cross-method alignment only exists when results are produced with
  ``--method all`` (shared trial data cache).
- Model name is not stored in result files; the caller supplies the expected
  model (default "gpt-4o") and the file's directory naming is the authority.
- The benchmark generates a single query archetype (vague prioritization
  questions depending on BOTH profile and task context). There is no
  profile-only or task-only question variant. All three judge dimensions
  (profile_usage, task_usage, integration) are preserved per trial.
- Profile context is reconstructed from synthetic_profile and
  synthetic_task_context using the naive_concat format. This is the
  canonical representation of what was available during inference:
  - naive_concat: passed this exact block to the model
  - vanilla_rag: TF-IDF selected chunks from this data (exact chunks
    not recorded in results)
  - kernel_shared/mem0_default: this data was written to memory; the
    kernel may have injected it (exact injected text not recorded)
  Since exact per-method inference context is NOT stored in the result
  files, showing the source data (what was available) is more honest than
  fabricating method-specific context.
- Exclusion reasons are collected into a structured ExclusionReport.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from benchmarks.human_rating.schemas import (
    SourceTrial,
    VALID_SOURCE_METHODS,
)

logger = logging.getLogger(__name__)

# Methods eligible for human rating (all four standard methods)
ALLOWED_METHODS: list[str] = sorted(VALID_SOURCE_METHODS)

# Minimum trials per method required for eligibility
MIN_TRIALS_PER_METHOD = 3


# ---------------------------------------------------------------------------
# Exclusion reporting
# ---------------------------------------------------------------------------

@dataclass
class ExclusionEntry:
    """One excluded trial with structured reason."""
    method: str
    trial_index: int
    reason: str
    source_file: str


@dataclass
class ExclusionReport:
    """Structured report of all excluded trials."""
    entries: list[ExclusionEntry] = field(default_factory=list)

    @property
    def total_excluded(self) -> int:
        return len(self.entries)

    def by_reason(self) -> dict[str, int]:
        """Count exclusions by reason category."""
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e.reason] = counts.get(e.reason, 0) + 1
        return counts

    def by_method(self) -> dict[str, int]:
        """Count exclusions by method."""
        counts: dict[str, int] = {}
        for e in self.entries:
            counts[e.method] = counts.get(e.method, 0) + 1
        return counts

    def format_summary(self) -> str:
        """Format as a readable summary string."""
        if not self.entries:
            return "No trials excluded."
        lines = [f"Excluded {self.total_excluded} trial(s):"]
        for reason, count in sorted(self.by_reason().items()):
            lines.append(f"  {reason}: {count}")
        lines.append("By method:")
        for method, count in sorted(self.by_method().items()):
            lines.append(f"  {method}: {count}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile context reconstruction
# ---------------------------------------------------------------------------

def _build_profile_context(trial_data: dict) -> str | None:
    """Reconstruct the profile context available during inference.

    Uses the synthetic_profile and synthetic_task_context fields to build
    the same structured text that was available to the model. This matches
    the naive_concat format from pipeline.py, which is the canonical
    representation of what was available during inference across all methods.

    For naive_concat, this IS the exact context block passed to the model.
    For vanilla_rag, the model received a TF-IDF-selected subset of this.
    For kernel_shared/mem0_default, this data was written to memory and
    potentially injected by the kernel (exact injected text not recorded).

    Args:
        trial_data: A raw trial dict from the result JSON.

    Returns:
        The reconstructed context string, or None if profile data is missing.
    """
    profile = trial_data.get("synthetic_profile")
    task_ctx = trial_data.get("synthetic_task_context")

    if not profile or not task_ctx:
        return None

    # Build the same format as pipeline.py _run_naive_concat
    context = (
        f"--- USER PROFILE ---\n"
        f"Name: {profile.get('user_name', '')}\n"
        f"Preferred Tools: {', '.join(profile.get('preferred_tools', []))}\n"
        f"Preferred Language: {profile.get('preferred_language', '')}\n"
        f"Response Style: {profile.get('response_style', '')}\n"
        f"\n"
        f"--- TASK CONTEXT ---\n"
        f"Current Project: {task_ctx.get('current_project', '')}\n"
        f"Active Experiment: {task_ctx.get('active_experiment', '')}\n"
        f"Goals: {', '.join(task_ctx.get('goals', []))}\n"
        f"Blockers: {', '.join(task_ctx.get('blockers', []))}\n"
        f"Next Steps: {', '.join(task_ctx.get('next_steps', []))}"
    )

    return context


# ---------------------------------------------------------------------------
# Model name normalization
# ---------------------------------------------------------------------------

def normalize_model_name(raw: str) -> str:
    """Normalize a model name string to the canonical form.

    Args:
        raw: The raw model name (may include provider suffix).

    Returns:
        Normalized model name (e.g. "gpt-4o").

    Raises:
        ValueError: If the model name is not a recognized GPT-4o variant.
    """
    # Strip provider suffix for comparison
    base = raw.split(":")[0].strip().lower()
    if base == "gpt-4o":
        return "gpt-4o"
    raise ValueError(
        f"Model name '{raw}' is not a recognized GPT-4o variant. "
        f"Cannot normalize to 'gpt-4o'."
    )


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_result_files(
    results_root: Path | str,
    methods: Sequence[str] | None = None,
) -> dict[str, Path]:
    """Discover finalized result JSON files by method.

    Searches for files named ``results_{method}.json`` within
    directories matching the pattern ``gpt4o_{method}/`` or directly
    under the results root.

    Args:
        results_root: Root directory to search for results.
        methods: Methods to discover (default: all four).

    Returns:
        Dict mapping method name to its result file path.

    Raises:
        FileNotFoundError: If a required method's result file is not found.
        ValueError: If multiple result files exist for one method.
    """
    results_root = Path(results_root)
    if methods is None:
        methods = ALLOWED_METHODS

    discovered: dict[str, Path] = {}

    for method in sorted(methods):
        candidates: list[Path] = []

        # Pattern 1: gpt4o_{method}/results_{method}.json
        dir_path = results_root / f"gpt4o_{method}"
        file_path = dir_path / f"results_{method}.json"
        if file_path.exists():
            candidates.append(file_path)

        # Pattern 2: results_{method}.json directly under root
        direct_path = results_root / f"results_{method}.json"
        if direct_path.exists() and direct_path not in candidates:
            candidates.append(direct_path)

        if len(candidates) == 0:
            raise FileNotFoundError(
                f"No result file found for method '{method}' under "
                f"'{results_root}'. Expected at: {file_path} or {direct_path}"
            )
        if len(candidates) > 1:
            raise ValueError(
                f"Multiple result files found for method '{method}': "
                f"{[str(c) for c in candidates]}. Provide explicit paths."
            )

        discovered[method] = candidates[0]

    return discovered


# ---------------------------------------------------------------------------
# Single-file loading
# ---------------------------------------------------------------------------

def load_result_file(
    path: Path | str,
    expected_method: str,
    expected_model: str = "gpt-4o",
    exclusion_report: ExclusionReport | None = None,
) -> list[SourceTrial]:
    """Load and normalize trials from a single result JSON file.

    Args:
        path: Path to the result JSON file.
        expected_method: The method this file should contain.
        expected_model: Expected model name (default "gpt-4o").
        exclusion_report: If provided, excluded trials are appended here
            instead of only being logged.

    Returns:
        List of validated SourceTrial objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: On schema violations or method mismatches.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Result file not found: {path}")

    if exclusion_report is None:
        exclusion_report = ExclusionReport()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate top-level structure
    if "conditions" not in data:
        raise ValueError(f"Result file {path} is missing 'conditions' key")

    conditions = data["conditions"]
    if not isinstance(conditions, list) or len(conditions) == 0:
        raise ValueError(f"Result file {path} has empty or invalid 'conditions'")

    # Find the condition matching the expected method
    target_condition = None
    for cond in conditions:
        if cond.get("condition") == expected_method:
            target_condition = cond
            break

    if target_condition is None:
        available = [c.get("condition") for c in conditions]
        raise ValueError(
            f"Result file {path} does not contain method '{expected_method}'. "
            f"Available conditions: {available}"
        )

    trials_raw = target_condition.get("trials", [])
    if not trials_raw:
        raise ValueError(
            f"Result file {path} has no trials for method '{expected_method}'"
        )

    # Normalize model name
    model = normalize_model_name(expected_model)

    source_trials: list[SourceTrial] = []
    seen_ids: set[str] = set()

    for trial in trials_raw:
        trial_index = trial.get("trial_index")
        if trial_index is None:
            raise ValueError(
                f"Trial in {path} is missing 'trial_index'"
            )

        # Skip failed trials
        if trial.get("failed", False):
            exclusion_report.entries.append(ExclusionEntry(
                method=expected_method,
                trial_index=trial_index,
                reason="failed_trial",
                source_file=str(path),
            ))
            continue

        # Validate method consistency
        trial_method = trial.get("method", trial.get("condition", ""))
        if trial_method != expected_method:
            raise ValueError(
                f"Trial {trial_index} in {path} has method '{trial_method}' "
                f"but expected '{expected_method}'"
            )

        # Method-independent original_trial_id (just the index)
        original_trial_id = str(trial_index)

        # Enforce uniqueness within method
        uniqueness_key = (expected_method, original_trial_id)
        if uniqueness_key in seen_ids:
            raise ValueError(
                f"Duplicate trial (method={expected_method}, "
                f"trial_id={original_trial_id}) in {path}"
            )
        seen_ids.add(uniqueness_key)

        # Extract fields
        question = trial.get("follow_up_query", "")
        response = trial.get("assistant_response", "")

        # Validate nonempty question
        if not question or not question.strip():
            exclusion_report.entries.append(ExclusionEntry(
                method=expected_method,
                trial_index=trial_index,
                reason="empty_question",
                source_file=str(path),
            ))
            continue

        # Validate nonempty response
        if not response or not response.strip():
            exclusion_report.entries.append(ExclusionEntry(
                method=expected_method,
                trial_index=trial_index,
                reason="empty_response",
                source_file=str(path),
            ))
            continue

        # Extract all three judge scores
        profile_usage_score = trial.get("profile_usage_score")
        task_usage_score = trial.get("task_usage_score")
        integration_score = trial.get("integration_score")

        # Validate all scores present and in range
        scores_valid = True
        for score_name, score_val in [
            ("profile_usage_score", profile_usage_score),
            ("task_usage_score", task_usage_score),
            ("integration_score", integration_score),
        ]:
            if score_val is None:
                exclusion_report.entries.append(ExclusionEntry(
                    method=expected_method,
                    trial_index=trial_index,
                    reason=f"missing_{score_name}",
                    source_file=str(path),
                ))
                scores_valid = False
                break
            if not isinstance(score_val, int) or score_val < 1 or score_val > 5:
                exclusion_report.entries.append(ExclusionEntry(
                    method=expected_method,
                    trial_index=trial_index,
                    reason=f"invalid_{score_name}",
                    source_file=str(path),
                ))
                scores_valid = False
                break

        if not scores_valid:
            continue

        # Build profile context
        profile_context = _build_profile_context(trial)

        # Create validated SourceTrial
        source_trial = SourceTrial(
            source_method=expected_method,
            model=model,
            original_trial_id=original_trial_id,
            profile_context=profile_context,
            question=question,
            response=response,
            profile_usage_score=profile_usage_score,
            task_usage_score=task_usage_score,
            integration_score=integration_score,
            source_file=str(path),
        )
        source_trials.append(source_trial)

    return source_trials


# ---------------------------------------------------------------------------
# Multi-file loading with eligibility checks
# ---------------------------------------------------------------------------

def load_eligible_trials(
    method_paths: dict[str, str | Path] | None = None,
    results_root: str | Path | None = None,
    methods: Sequence[str] | None = None,
    expected_model: str = "gpt-4o",
    min_per_method: int = MIN_TRIALS_PER_METHOD,
) -> tuple[list[SourceTrial], ExclusionReport]:
    """Load all methods and validate pool eligibility.

    Either `method_paths` (explicit per-method paths) or `results_root`
    (auto-discovery) must be provided.

    Args:
        method_paths: Dict mapping method name to result file path.
        results_root: Root directory for auto-discovery.
        methods: Methods to load (default: all four).
        expected_model: Expected model name.
        min_per_method: Minimum trials required per method.

    Returns:
        Tuple of (validated SourceTrial list, ExclusionReport).

    Raises:
        ValueError: If eligibility checks fail.
        FileNotFoundError: If result files are not found.
    """
    if methods is None:
        methods = ALLOWED_METHODS

    # Resolve file paths
    if method_paths is not None:
        resolved: dict[str, Path] = {
            m: Path(p) for m, p in method_paths.items()
        }
        # Validate all requested methods are provided
        missing = set(methods) - set(resolved.keys())
        if missing:
            raise ValueError(
                f"Missing method paths for: {sorted(missing)}"
            )
    elif results_root is not None:
        resolved = discover_result_files(results_root, methods)
    else:
        raise ValueError(
            "Either 'method_paths' or 'results_root' must be provided"
        )

    exclusion_report = ExclusionReport()

    # Load trials from each method in deterministic order
    all_trials: list[SourceTrial] = []
    for method in sorted(methods):
        path = resolved[method]
        trials = load_result_file(
            path=path,
            expected_method=method,
            expected_model=expected_model,
            exclusion_report=exclusion_report,
        )
        logger.info(
            "Loaded %d trials from %s (%s)", len(trials), path, method
        )
        all_trials.extend(trials)

    # --- Pool eligibility checks ---

    # Check: all four methods represented
    methods_present = {t.source_method for t in all_trials}
    missing_methods = set(methods) - methods_present
    if missing_methods:
        raise ValueError(
            f"Missing methods in eligible pool: {sorted(missing_methods)}"
        )

    # Check: only expected model
    models_present = {t.model for t in all_trials}
    if models_present != {expected_model}:
        unexpected = models_present - {expected_model}
        raise ValueError(
            f"Unexpected models in pool: {unexpected}. "
            f"Only '{expected_model}' trials are eligible."
        )

    # Check: minimum per method
    for method in sorted(methods):
        method_count = sum(
            1 for t in all_trials if t.source_method == method
        )
        if method_count < min_per_method:
            raise ValueError(
                f"Insufficient eligible trials for method={method}: "
                f"required {min_per_method}, found {method_count}."
            )

    return all_trials, exclusion_report


# ---------------------------------------------------------------------------
# Pool summary
# ---------------------------------------------------------------------------

@dataclass
class MethodCount:
    """Trial count for a single method."""
    method: str
    count: int
    avg_profile_usage: float
    avg_task_usage: float
    avg_integration: float


@dataclass
class TrialPoolSummary:
    """Developer-facing summary of the eligible trial pool."""

    total_trials: int
    methods: list[str]
    method_counts: list[MethodCount]
    score_distribution: dict[str, dict[int, int]]  # dimension -> score -> count

    def format_table(self) -> str:
        """Format as an aligned text table.

        Returns:
            Multi-line string with method counts and average scores.
        """
        lines = []
        header = (
            f"{'Method':<20} {'Count':>6} "
            f"{'AvgProfile':>11} {'AvgTask':>8} {'AvgInteg':>9}"
        )
        lines.append(header)
        lines.append("-" * len(header))

        for mc in self.method_counts:
            lines.append(
                f"{mc.method:<20} {mc.count:>6} "
                f"{mc.avg_profile_usage:>11.2f} "
                f"{mc.avg_task_usage:>8.2f} "
                f"{mc.avg_integration:>9.2f}"
            )

        lines.append("-" * len(header))
        lines.append(f"{'TOTAL':<20} {self.total_trials:>6}")
        return "\n".join(lines)


def summarize_trial_pool(trials: Sequence[SourceTrial]) -> TrialPoolSummary:
    """Produce a developer-facing summary of the eligible trial pool.

    Args:
        trials: Sequence of validated SourceTrial objects.

    Returns:
        TrialPoolSummary with counts and averages by method.
    """
    methods = sorted({t.source_method for t in trials})

    method_counts: list[MethodCount] = []
    for method in methods:
        method_trials = [t for t in trials if t.source_method == method]
        count = len(method_trials)
        avg_pu = sum(t.profile_usage_score for t in method_trials) / count if count else 0
        avg_tu = sum(t.task_usage_score for t in method_trials) / count if count else 0
        avg_ig = sum(t.integration_score for t in method_trials) / count if count else 0
        method_counts.append(MethodCount(
            method=method,
            count=count,
            avg_profile_usage=avg_pu,
            avg_task_usage=avg_tu,
            avg_integration=avg_ig,
        ))

    # Score distribution per dimension
    score_dist: dict[str, dict[int, int]] = {
        "profile_usage": {},
        "task_usage": {},
        "integration": {},
    }
    for t in trials:
        score_dist["profile_usage"][t.profile_usage_score] = (
            score_dist["profile_usage"].get(t.profile_usage_score, 0) + 1
        )
        score_dist["task_usage"][t.task_usage_score] = (
            score_dist["task_usage"].get(t.task_usage_score, 0) + 1
        )
        score_dist["integration"][t.integration_score] = (
            score_dist["integration"].get(t.integration_score, 0) + 1
        )

    return TrialPoolSummary(
        total_trials=len(trials),
        methods=methods,
        method_counts=method_counts,
        score_distribution=score_dist,
    )
