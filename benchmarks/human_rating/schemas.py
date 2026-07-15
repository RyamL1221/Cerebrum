"""Data contracts for the human-rating evaluation workflow.

Defines typed schemas for:
- Normalized source trials (internal representation)
- Blinded rating queue items (rater-visible only)
- Answer-key items (preprocessing/compilation only)
- Rating records (append-only session file)
- Compiled item-level records (flat export)

Design invariants:
- The blinded queue schema CANNOT represent method, judge score, question
  type, trial ID, or duplicate status.
- Ratings are immutable one-record-per-ID submissions (single 1–5 score).
- The answer key is never exposed to the rating CLI.

Judge score selection rule:
    The comparison judge score is selected based on question_type:
    - profile questions → profile_usage_score
    - task questions → task_usage_score
    This matches the semantic intent: a profile question tests whether the
    model used profile knowledge, so the human rates the same dimension.
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

VALID_QUESTION_TYPES = frozenset({"profile", "task"})

VALID_RATINGS = frozenset({1, 2, 3, 4, 5})


# ---------------------------------------------------------------------------
# Judge score selection rule
# ---------------------------------------------------------------------------

def select_judge_score(
    question_type: str,
    profile_usage_score: int,
    task_usage_score: int,
    integration_score: int,
) -> int:
    """Select the comparison judge score based on question type.

    Rule:
    - "profile" questions → profile_usage_score
    - "task" questions → task_usage_score

    Args:
        question_type: "profile" or "task".
        profile_usage_score: GPT-5.4 judge's profile usage score (1–5).
        task_usage_score: GPT-5.4 judge's task usage score (1–5).
        integration_score: GPT-5.4 judge's integration score (1–5).

    Returns:
        The single integer score used for human-judge comparison.

    Raises:
        ValueError: If question_type is not valid.
    """
    if question_type == "profile":
        return profile_usage_score
    elif question_type == "task":
        return task_usage_score
    else:
        raise ValueError(
            f"Cannot select judge score for question_type={question_type!r}. "
            f"Must be 'profile' or 'task'."
        )


# ---------------------------------------------------------------------------
# Source trial schema (internal, never exposed to rater)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceTrial:
    """Typed internal representation of a source benchmark trial.

    Validation requirements:
    - source_method must be one of VALID_SOURCE_METHODS.
    - model must normalize to "gpt-4o".
    - question_type must be "profile" or "task".
    - original_trial_id must be nonempty.
    - question and response must be nonempty.
    - judge_score must be in the 1–5 range (selected by question_type rule).
    - inference_context is the exact context supplied to GPT-4o (may be
      empty for methods where retrieval failed or no context was injected).
    - source_file is optional diagnostic metadata (not exposed to rater).
    """

    source_method: str
    model: str
    question_type: Literal["profile", "task"]
    original_trial_id: str
    inference_context: str | None
    question: str
    response: str
    judge_score: int
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
        if self.question_type not in VALID_QUESTION_TYPES:
            raise ValueError(
                f"question_type must be 'profile' or 'task', "
                f"got {self.question_type!r}"
            )
        if not self.original_trial_id or not self.original_trial_id.strip():
            raise ValueError("original_trial_id must be nonempty")
        if not self.question or not self.question.strip():
            raise ValueError("question must be nonempty")
        if not self.response or not self.response.strip():
            raise ValueError("response must be nonempty")
        if not isinstance(self.judge_score, int) or self.judge_score < 1 or self.judge_score > 5:
            raise ValueError(
                f"judge_score must be an integer 1–5, got {self.judge_score!r}"
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
    - question_type
    - original_trial_id
    - judge_score
    - duplicate status
    - sampling cell
    - shuffle seed
    - source path
    """

    blinded_id: str
    inference_context: str | None
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
    """

    blinded_id: str
    source_method: str
    model: str
    question_type: Literal["profile", "task"]
    original_trial_id: str
    judge_score: int
    duplicate_of: str | None


# ---------------------------------------------------------------------------
# Rating record (append-only session file)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RatingRecord:
    """A single human rating submission.

    One 1–5 score per item. The rubric dimension matches the question type:
    - Profile items are rated on profile-usage quality.
    - Task items are rated on task-usage quality.

    Validation requirements:
    - rating must be an integer 1–5.
    - Each blinded_id may appear at most once in the session.
    - rated_at must be a timezone-aware ISO-8601 string.
    - No source method, judge score, question type, or duplicate metadata.

    Ratings are immutable: once submitted, they cannot be overwritten.
    """

    blinded_id: str
    rating: int
    note: str | None
    flagged: bool
    rated_at: str

    def __post_init__(self) -> None:
        if not self.blinded_id or not self.blinded_id.strip():
            raise ValueError("blinded_id must be nonempty")
        if not isinstance(self.rating, int) or self.rating not in VALID_RATINGS:
            raise ValueError(
                f"rating must be an integer 1–5, got {self.rating!r}"
            )
        if not self.rated_at or not self.rated_at.strip():
            raise ValueError("rated_at must be nonempty")


# ---------------------------------------------------------------------------
# Compiled item-level record (flat export)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompiledRecord:
    """One flat row per rating instance in the compiled export.

    Joins the rating record with the answer-key metadata and computes
    human-vs-judge agreement metrics.
    """

    blinded_id: str
    rating: int
    note: str | None
    flagged: bool
    rated_at: str
    source_method: str
    model: str
    question_type: Literal["profile", "task"]
    original_trial_id: str
    judge_score: int
    duplicate_of: str | None
    is_duplicate: bool
    human_judge_difference: int
    exact_human_judge_match: bool
    within_one_human_judge: bool
