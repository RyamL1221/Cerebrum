"""Trial discovery, normalization, and eligibility validation.

Loads benchmark result files and converts their raw records into validated
SourceTrial objects suitable for stratified sampling.

Public functions:
- discover_result_files() — find result JSONs by method
- load_result_file() — parse a single result file into SourceTrial objects
- load_eligible_trials() — load all methods and validate pool eligibility
- summarize_trial_pool() — produce a developer-facing method × type summary

Compatibility:
    The human-rating pipeline requires result files that contain:
    - ``question_type``: "profile" or "task" (authoritative, not inferred)
    - ``inference_context_text``: exact context supplied to GPT-4o

    Existing finalized results (produced before these fields were added) do
    NOT contain this metadata and cannot be used directly. Attempting to load
    them will report exclusions with reason ``missing_or_invalid_question_type``
    or ``missing_exact_inference_context``.

    To produce compatible results, the Cerebrum benchmark must be updated to:
    1. Generate explicit profile/task question templates
    2. Record exact inference context per method
    3. Store ``question_type`` and ``inference_context_text`` in TrialResult
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
    VALID_QUESTION_TYPES,
    select_judge_score,
)

logger = logging.getLogger(__name__)

# Methods eligible for human rating (all four standard methods)
ALLOWED_METHODS: list[str] = sorted(VALID_SOURCE_METHODS)

# Minimum trials per method/type cell required for eligibility
MIN_TRIALS_PER_CELL = 3


# ---------------------------------------------------------------------------
# Compatibility error
# ---------------------------------------------------------------------------

class UnsupportedBenchmarkArtifactsError(RuntimeError):
    """Raised when existing result files lack required human-rating metadata.

    Existing finalized results do not contain an authoritative profile/task
    question type or exact inference context required by the requested
    sampling design.
    """
    pass


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

    Requires result files with ``question_type`` and ``inference_context_text``
    fields. Files without these fields will have all trials excluded.

    Args:
        path: Path to the result JSON file.
        expected_method: The method this file should contain.
        expected_model: Expected model name (default "gpt-4o").
        exclusion_report: If provided, excluded trials are appended here.

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
            raise ValueError(f"Trial in {path} is missing 'trial_index'")

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

        # Method-independent original_trial_id
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

        # Extract question_type (required)
        question_type = trial.get("question_type", "")
        if not question_type or question_type not in VALID_QUESTION_TYPES:
            exclusion_report.entries.append(ExclusionEntry(
                method=expected_method,
                trial_index=trial_index,
                reason="missing_or_invalid_question_type",
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

        # Select the comparison judge score based on question type
        judge_score = select_judge_score(
            question_type, profile_usage_score, task_usage_score, integration_score
        )

        # Extract exact inference context (required — None means unobservable)
        inference_context = trial.get("inference_context_text")
        if inference_context is None:
            exclusion_report.entries.append(ExclusionEntry(
                method=expected_method,
                trial_index=trial_index,
                reason="missing_exact_inference_context",
                source_file=str(path),
            ))
            continue
        # Empty string is valid (confirmed no context supplied)

        # Create validated SourceTrial
        source_trial = SourceTrial(
            source_method=expected_method,
            model=model,
            question_type=question_type,
            original_trial_id=original_trial_id,
            inference_context=inference_context,
            question=question,
            response=response,
            judge_score=judge_score,
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
    min_per_cell: int = MIN_TRIALS_PER_CELL,
) -> tuple[list[SourceTrial], ExclusionReport]:
    """Load all methods and validate pool eligibility.

    Either `method_paths` (explicit per-method paths) or `results_root`
    (auto-discovery) must be provided.

    Raises UnsupportedBenchmarkArtifactsError if the loaded results do not
    contain the required metadata fields (question_type, inference_context_text).

    Args:
        method_paths: Dict mapping method name to result file path.
        results_root: Root directory for auto-discovery.
        methods: Methods to load (default: all four).
        expected_model: Expected model name.
        min_per_cell: Minimum trials required per method/type cell.

    Returns:
        Tuple of (validated SourceTrial list, ExclusionReport).

    Raises:
        ValueError: If eligibility checks fail.
        FileNotFoundError: If result files are not found.
        UnsupportedBenchmarkArtifactsError: If results lack required metadata.
    """
    if methods is None:
        methods = ALLOWED_METHODS

    # Resolve file paths
    if method_paths is not None:
        resolved: dict[str, Path] = {
            m: Path(p) for m, p in method_paths.items()
        }
        missing = set(methods) - set(resolved.keys())
        if missing:
            raise ValueError(f"Missing method paths for: {sorted(missing)}")
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
        logger.info("Loaded %d trials from %s (%s)", len(trials), path, method)
        all_trials.extend(trials)

    # If ALL trials were excluded, this likely means the results lack metadata
    if not all_trials and exclusion_report.total_excluded > 0:
        reasons = exclusion_report.by_reason()
        if "missing_or_invalid_question_type" in reasons or "missing_exact_inference_context" in reasons:
            raise UnsupportedBenchmarkArtifactsError(
                "Existing finalized results do not contain an authoritative "
                "profile/task question type or exact inference context required "
                "by the requested sampling design. "
                f"Exclusion reasons: {reasons}"
            )

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

    # Check: minimum per method × question_type cell
    for method in sorted(methods):
        for qtype in sorted(VALID_QUESTION_TYPES):
            cell_count = sum(
                1 for t in all_trials
                if t.source_method == method and t.question_type == qtype
            )
            if cell_count < min_per_cell:
                raise ValueError(
                    f"Insufficient eligible trials for method={method}, "
                    f"question_type={qtype}: required {min_per_cell}, "
                    f"found {cell_count}."
                )

    return all_trials, exclusion_report


# ---------------------------------------------------------------------------
# Pool summary
# ---------------------------------------------------------------------------

@dataclass
class MethodTypeCount:
    """Trial count for a single method × question_type cell."""
    method: str
    question_type: str
    count: int


@dataclass
class TrialPoolSummary:
    """Developer-facing summary of the eligible trial pool."""

    total_trials: int
    methods: list[str]
    question_types: list[str]
    cells: list[MethodTypeCount]
    score_distribution: dict[int, int]  # judge_score -> count

    def format_table(self) -> str:
        """Format as an aligned text table."""
        lines = []
        header = f"{'Method':<20} {'Profile':>8} {'Task':>8} {'Total':>8}"
        lines.append(header)
        lines.append("-" * len(header))

        for method in self.methods:
            profile_count = next(
                (c.count for c in self.cells
                 if c.method == method and c.question_type == "profile"), 0
            )
            task_count = next(
                (c.count for c in self.cells
                 if c.method == method and c.question_type == "task"), 0
            )
            total = profile_count + task_count
            lines.append(
                f"{method:<20} {profile_count:>8} {task_count:>8} {total:>8}"
            )

        lines.append("-" * len(header))
        lines.append(f"{'TOTAL':<20} {'':<8} {'':<8} {self.total_trials:>8}")
        return "\n".join(lines)


def summarize_trial_pool(trials: Sequence[SourceTrial]) -> TrialPoolSummary:
    """Produce a developer-facing summary of the eligible trial pool."""
    methods = sorted({t.source_method for t in trials})
    question_types = sorted({t.question_type for t in trials})

    cells: list[MethodTypeCount] = []
    for method in methods:
        for qtype in question_types:
            count = sum(
                1 for t in trials
                if t.source_method == method and t.question_type == qtype
            )
            cells.append(MethodTypeCount(method=method, question_type=qtype, count=count))

    score_distribution: dict[int, int] = {}
    for t in trials:
        score_distribution[t.judge_score] = score_distribution.get(t.judge_score, 0) + 1

    return TrialPoolSummary(
        total_trials=len(trials),
        methods=methods,
        question_types=question_types,
        cells=cells,
        score_distribution=score_distribution,
    )
