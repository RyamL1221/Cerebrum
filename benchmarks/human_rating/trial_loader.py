"""Trial discovery, normalization, and eligibility validation.

Loads finalized GPT-4o benchmark result files for all four methods and
converts their heterogeneous raw records into validated SourceTrial objects
suitable for stratified sampling.

Public functions:
- discover_result_files() — find result JSONs by method
- load_result_file() — parse a single result file into SourceTrial objects
- load_eligible_trials() — load all methods and validate pool eligibility
- summarize_trial_pool() — produce a developer-facing method × type summary

Design decisions:
- Trial IDs are synthesized as ``{method}_{trial_index}`` since the source
  benchmark only stores a 0-based trial_index.
- Model name is not stored in result files; the caller supplies the expected
  model (default "gpt-4o") and it is validated against the file's directory
  naming convention.
- Question type is assigned via an external deterministic mapping file
  (question_types.json). All trials within a mapping must resolve to the
  same type regardless of method.
- Profile context is reconstructed from the synthetic_profile and
  synthetic_task_context fields using the same format as naive_concat's
  context block, since this represents what was available for inference.
- Judge score uses `integration_score` as the single overall score for
  human comparison, as it captures the holistic quality of personalization
  (combining both profile and task usage into a grounded recommendation).
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from benchmarks.human_rating.schemas import (
    SourceTrial,
    VALID_SOURCE_METHODS,
    VALID_QUESTION_TYPES,
)

logger = logging.getLogger(__name__)

# Methods eligible for human rating (all four standard methods)
ALLOWED_METHODS: list[str] = sorted(VALID_SOURCE_METHODS)

# Minimum trials per method/type cell required for eligibility
MIN_TRIALS_PER_CELL = 3


# ---------------------------------------------------------------------------
# Question-type mapping
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QuestionTypeMapping:
    """Deterministic question-type assignment for trials.

    Maps trial identifiers (method_trialIndex) to "profile" or "task".
    The same underlying trial index must resolve to the same question type
    regardless of method.
    """

    mapping: dict[int, str]  # trial_index -> question_type

    def get_type(self, trial_index: int) -> str:
        """Look up the question type for a trial index.

        Args:
            trial_index: The 0-based trial index.

        Returns:
            Either "profile" or "task".

        Raises:
            KeyError: If trial_index is not in the mapping.
            ValueError: If the mapped value is invalid.
        """
        if trial_index not in self.mapping:
            raise KeyError(
                f"Trial index {trial_index} not found in question_type mapping. "
                f"Available indices: {sorted(self.mapping.keys())[:10]}..."
            )
        qtype = self.mapping[trial_index]
        if qtype not in VALID_QUESTION_TYPES:
            raise ValueError(
                f"Invalid question_type '{qtype}' for trial_index {trial_index}. "
                f"Must be one of {sorted(VALID_QUESTION_TYPES)}"
            )
        return qtype


def load_question_type_mapping(path: str | Path) -> QuestionTypeMapping:
    """Load a question_types.json mapping file.

    Expected format:
    {
      "schema_version": 1,
      "description": "...",
      "assignment_rule": "...",
      "trials": {
        "0": "profile",
        "1": "task",
        ...
      }
    }

    Args:
        path: Path to the JSON mapping file.

    Returns:
        A validated QuestionTypeMapping.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is malformed or contains invalid types.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Question type mapping not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "trials" not in data:
        raise ValueError(
            f"Question type mapping at {path} is missing 'trials' key"
        )

    trials_raw = data["trials"]
    if not isinstance(trials_raw, dict):
        raise ValueError(
            f"'trials' must be a dict mapping index -> type, got {type(trials_raw).__name__}"
        )

    mapping: dict[int, str] = {}
    for key, value in trials_raw.items():
        try:
            idx = int(key)
        except (ValueError, TypeError):
            raise ValueError(
                f"Trial key '{key}' is not a valid integer index"
            )
        if value not in VALID_QUESTION_TYPES:
            raise ValueError(
                f"Trial index {idx} has invalid question_type '{value}'. "
                f"Must be one of {sorted(VALID_QUESTION_TYPES)}"
            )
        mapping[idx] = value

    return QuestionTypeMapping(mapping=mapping)


def generate_default_question_type_mapping(
    max_trial_index: int,
) -> QuestionTypeMapping:
    """Generate a default alternating question-type mapping.

    Since the existing benchmark does not have a native question_type field,
    this provides a deterministic assignment: even trial indices are "profile",
    odd indices are "task". This ensures equal distribution across types.

    Args:
        max_trial_index: The highest trial_index (inclusive) to map.

    Returns:
        A QuestionTypeMapping with alternating assignment.
    """
    mapping = {}
    for i in range(max_trial_index + 1):
        mapping[i] = "profile" if i % 2 == 0 else "task"
    return QuestionTypeMapping(mapping=mapping)


# ---------------------------------------------------------------------------
# Profile context reconstruction
# ---------------------------------------------------------------------------

def _build_profile_context(trial_data: dict) -> str | None:
    """Reconstruct the profile context available during inference.

    Uses the synthetic_profile and synthetic_task_context fields to build
    the same structured text that was available to the model. This matches
    the naive_concat format, which is the canonical representation of what
    was available during inference across all methods.

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

# Known equivalent representations that all normalize to "gpt-4o"
_GPT4O_VARIANTS = frozenset({
    "gpt-4o",
    "gpt-4o:azure",
    "gpt-4o:openai",
    "GPT-4o",
    "GPT-4O",
})


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
    question_type_map: QuestionTypeMapping | None = None,
) -> list[SourceTrial]:
    """Load and normalize trials from a single result JSON file.

    Args:
        path: Path to the result JSON file.
        expected_method: The method this file should contain.
        expected_model: Expected model name (default "gpt-4o").
        question_type_map: Mapping of trial_index -> question_type.
            If None, uses default alternating assignment.

    Returns:
        List of validated SourceTrial objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: On schema violations, method mismatches, or invalid data.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Result file not found: {path}")

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

    # Determine max trial index for default mapping
    max_idx = max(t.get("trial_index", 0) for t in trials_raw)
    if question_type_map is None:
        question_type_map = generate_default_question_type_mapping(max_idx)

    # Normalize model name
    model = normalize_model_name(expected_model)

    source_trials: list[SourceTrial] = []
    seen_ids: set[str] = set()

    for trial in trials_raw:
        # Skip failed trials
        if trial.get("failed", False):
            continue

        trial_index = trial.get("trial_index")
        if trial_index is None:
            raise ValueError(
                f"Trial in {path} is missing 'trial_index'"
            )

        # Validate method consistency
        trial_method = trial.get("method", trial.get("condition", ""))
        if trial_method != expected_method:
            raise ValueError(
                f"Trial {trial_index} in {path} has method '{trial_method}' "
                f"but expected '{expected_method}'"
            )

        # Construct unique trial ID
        original_trial_id = f"{expected_method}_{trial_index}"
        if original_trial_id in seen_ids:
            raise ValueError(
                f"Duplicate trial ID '{original_trial_id}' in {path}"
            )
        seen_ids.add(original_trial_id)

        # Extract fields
        question = trial.get("follow_up_query", "")
        response = trial.get("assistant_response", "")

        # Validate nonempty
        if not question or not question.strip():
            logger.warning(
                "Skipping trial %d in %s: empty question", trial_index, path
            )
            continue
        if not response or not response.strip():
            logger.warning(
                "Skipping trial %d in %s: empty response", trial_index, path
            )
            continue

        # Extract judge score (integration_score as the holistic measure)
        judge_score = trial.get("integration_score")
        if judge_score is None:
            logger.warning(
                "Skipping trial %d in %s: missing integration_score",
                trial_index, path
            )
            continue
        if not isinstance(judge_score, int) or judge_score < 1 or judge_score > 5:
            logger.warning(
                "Skipping trial %d in %s: invalid judge_score %r",
                trial_index, path, judge_score
            )
            continue

        # Get question type from mapping
        try:
            question_type = question_type_map.get_type(trial_index)
        except KeyError as e:
            raise ValueError(
                f"Trial {trial_index} in {path}: {e}"
            ) from e

        # Build profile context
        profile_context = _build_profile_context(trial)

        # Create validated SourceTrial
        source_trial = SourceTrial(
            source_method=expected_method,
            model=model,
            question_type=question_type,
            original_trial_id=original_trial_id,
            profile_context=profile_context,
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
    question_type_map: QuestionTypeMapping | None = None,
    min_per_cell: int = MIN_TRIALS_PER_CELL,
) -> list[SourceTrial]:
    """Load all methods and validate pool eligibility.

    Either `method_paths` (explicit per-method paths) or `results_root`
    (auto-discovery) must be provided.

    Args:
        method_paths: Dict mapping method name to result file path.
        results_root: Root directory for auto-discovery.
        methods: Methods to load (default: all four).
        expected_model: Expected model name.
        question_type_map: Question type mapping. If None, uses default.
        min_per_cell: Minimum trials required per method/type cell.

    Returns:
        Validated list of all eligible SourceTrial objects.

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

    # Load trials from each method in deterministic order
    all_trials: list[SourceTrial] = []
    for method in sorted(methods):
        path = resolved[method]
        trials = load_result_file(
            path=path,
            expected_method=method,
            expected_model=expected_model,
            question_type_map=question_type_map,
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

    # Check: both question types exist for every method
    # Check: minimum per cell
    for method in sorted(methods):
        for qtype in sorted(VALID_QUESTION_TYPES):
            cell_count = sum(
                1 for t in all_trials
                if t.source_method == method and t.question_type == qtype
            )
            if cell_count == 0:
                raise ValueError(
                    f"No eligible trials for method={method}, "
                    f"question_type={qtype}"
                )
            if cell_count < min_per_cell:
                raise ValueError(
                    f"Insufficient eligible trials for method={method}, "
                    f"question_type={qtype}: required {min_per_cell}, "
                    f"found {cell_count}."
                )

    # Check: nonempty question and response (already filtered during load)
    # Check: valid judge scores (already filtered during load)

    return all_trials


# ---------------------------------------------------------------------------
# Pool summary
# ---------------------------------------------------------------------------

@dataclass
class CellCount:
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
    cells: list[CellCount]
    score_distribution: dict[int, int]  # score -> count

    def format_table(self) -> str:
        """Format as an aligned text table.

        Returns:
            Multi-line string with method × type counts.
        """
        lines = []
        # Header
        header = f"{'Method':<20} {'Profile':>8} {'Task':>8} {'Total':>8}"
        lines.append(header)
        lines.append("-" * len(header))

        for method in self.methods:
            profile_count = next(
                (c.count for c in self.cells
                 if c.method == method and c.question_type == "profile"),
                0
            )
            task_count = next(
                (c.count for c in self.cells
                 if c.method == method and c.question_type == "task"),
                0
            )
            total = profile_count + task_count
            lines.append(
                f"{method:<20} {profile_count:>8} {task_count:>8} {total:>8}"
            )

        lines.append("-" * len(header))
        lines.append(f"{'TOTAL':<20} {'':<8} {'':<8} {self.total_trials:>8}")
        return "\n".join(lines)


def summarize_trial_pool(trials: Sequence[SourceTrial]) -> TrialPoolSummary:
    """Produce a developer-facing summary of the eligible trial pool.

    Args:
        trials: Sequence of validated SourceTrial objects.

    Returns:
        TrialPoolSummary with counts by method and question type.
    """
    methods = sorted({t.source_method for t in trials})
    question_types = sorted({t.question_type for t in trials})

    cells: list[CellCount] = []
    for method in methods:
        for qtype in question_types:
            count = sum(
                1 for t in trials
                if t.source_method == method and t.question_type == qtype
            )
            cells.append(CellCount(method=method, question_type=qtype, count=count))

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
