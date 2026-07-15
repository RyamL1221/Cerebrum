"""Data contracts for the human-rating evaluation workflow.

Defines typed schemas for:
- Normalized source trials (internal representation)
- Blinded rating queue items (rater-visible only)
- Answer-key items (preprocessing/compilation only)
- Rating records (append-only session file)
- Compiled item-level records (flat export)

Design invariants:
- The blinded queue schema CANNOT represent method, judge score, trial ID,
  or duplicate status.
- Ratings are immutable one-record-per-ID submissions.
- The answer key is never exposed to the rating CLI.

Question-type note:
    The existing benchmark generates a single query archetype — intentionally
    vague prioritization questions that require BOTH profile and task context
    to answer well. There is no native profile-only or task-only question
    variant. Consequently, the human rater evaluates each trial on all three
    judge dimensions (profile_usage, task_usage, integration) rather than a
    single dimension. The answer key records which judge dimension is used
    for the primary human-judge comparison.
"""

from dataclasses import dataclass
from typing_extensions import Literal

# ---------------------------------------------------------------------------
# Valid domain values
# ---------------------------------------------------------------------------

VALID_SOURCE_METHODS = frozenset({
    "naive_concat",
    "vanilla_rag",
    "mem0_default",
    "kernel_shared",
})

VALID_JUDGE_DIMENSIONS = frozenset({
    "profile_usage",
    "task_usage",
    "integration",
})

VALID_RATINGS = frozenset({1, 2, 3, 4, 5})


# ---------------------------------------------------------------------------
# Source trial schema (internal, never exposed to rater)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceTrial:
    """Typed internal representation of a source benchmark trial.

    Validation requirements:
    - source_method must be one of VALID_SOURCE_METHODS.
    - model must normalize to "gpt-4o".
    - original_trial_id must be nonempty (method-independent trial index).
    - question and response must be nonempty.
    - profile_usage_score, task_usage_score, integration_score must be 1–5.
    - profile_context may be None for trials where no profile context was
      supplied during inference.
    - source_file is optional diagnostic metadata (not exposed to rater).
    """

    source_method: str
    model: str
    original_trial_id: str
    profile_context: str | None
    question: str
    response: str
    profile_usage_score: int
    task_usage_score: int
    integration_score: int
    source_file: str | None = None

    def __post_init__(self) -> None:
        if self.source_method not in VALID_SOURCE_METHODS:
            raise ValueError(
                f"source_method must be one of {sorted(VALID_SOURCE_METHODS)}, "
                f"got {self.source_method!r}"
            )
        if self.model != "gpt-4o":
            raise ValueError(
                f"model must normalize to 'gpt-4o', got {self.model!r}"
            )
        if not self.original_trial_id or not self.original_trial_id.strip():
            raise ValueError("original_trial_id must be nonempty")
        if not self.question or not self.question.strip():
            raise ValueError("question must be nonempty")
        if not self.response or not self.response.strip():
            raise ValueError("response must be nonempty")
        for field_name, value in [
            ("profile_usage_score", self.profile_usage_score),
            ("task_usage_score", self.task_usage_score),
            ("integration_score", self.integration_score),
        ]:
            if not isinstance(value, int) or value < 1 or value > 5:
                raise ValueError(
                    f"{field_name} must be an integer 1–5, got {value!r}"
                )


# ---------------------------------------------------------------------------
# Blinded rating queue item (rater-visible ONLY)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RatingQueueItem:
    """A single blinded item presented to the rater.

    This schema intentionally CANNOT represent:
    - source_method
    - model
    - original_trial_id
    - judge scores
    - duplicate status
    - sampling cell
    - shuffle seed
    - source path
    """

    blinded_id: str
    profile_context: str | None
    question: str
    response: str


# ---------------------------------------------------------------------------
# Answer-key item (preprocessing + compilation ONLY)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnswerKeyItem:
    """Unblinded metadata for a single queue item.

    Used by sample_and_blind (writer) and compile_ratings (reader).
    Never imported or accessed by the rate command.

    The judge_dimension field specifies which automated judge score
    is used for the primary human-judge comparison for this item.
    """

    blinded_id: str
    source_method: str
    model: str
    original_trial_id: str
    judge_dimension: Literal["profile_usage", "task_usage", "integration"]
    judge_score: int
    profile_usage_score: int
    task_usage_score: int
    integration_score: int
    duplicate_of: str | None


# ---------------------------------------------------------------------------
# Rating record (append-only session file)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RatingRecord:
    """A single human rating submission.

    The human rater scores on the same three dimensions as the automated
    judge: profile_usage, task_usage, and integration.

    Validation requirements:
    - All three ratings must be integers 1–5.
    - Each blinded_id may appear at most once in the session.
    - rated_at must be a timezone-aware ISO-8601 string.
    - No source method, judge score, or duplicate metadata.

    Ratings are immutable: once submitted, they cannot be overwritten.
    """

    blinded_id: str
    profile_usage_rating: int
    task_usage_rating: int
    integration_rating: int
    note: str | None
    flagged: bool
    rated_at: str

    def __post_init__(self) -> None:
        if not self.blinded_id or not self.blinded_id.strip():
            raise ValueError("blinded_id must be nonempty")
        if not self.rated_at or not self.rated_at.strip():
            raise ValueError("rated_at must be nonempty")
        for field_name, value in [
            ("profile_usage_rating", self.profile_usage_rating),
            ("task_usage_rating", self.task_usage_rating),
            ("integration_rating", self.integration_rating),
        ]:
            if not isinstance(value, int) or value not in VALID_RATINGS:
                raise ValueError(
                    f"{field_name} must be an integer 1–5, got {value!r}"
                )


# ---------------------------------------------------------------------------
# Compiled item-level record (flat export)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompiledRecord:
    """One flat row per rating instance in the compiled export.

    Joins the rating record with the answer-key metadata and computes
    human-vs-judge agreement metrics for each dimension.
    """

    blinded_id: str
    profile_usage_rating: int
    task_usage_rating: int
    integration_rating: int
    note: str | None
    flagged: bool
    rated_at: str
    source_method: str
    model: str
    original_trial_id: str
    judge_dimension: str
    judge_score: int
    profile_usage_score: int
    task_usage_score: int
    integration_score: int
    duplicate_of: str | None
    is_duplicate: bool
    # Per-dimension agreement
    profile_usage_difference: int
    task_usage_difference: int
    integration_difference: int
    profile_usage_exact_match: bool
    task_usage_exact_match: bool
    integration_exact_match: bool
    profile_usage_within_one: bool
    task_usage_within_one: bool
    integration_within_one: bool
