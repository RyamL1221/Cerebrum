"""Pydantic data models for the shared memory evaluation harness.

Defines all structured data shapes used across the harness: synthetic data
generation inputs, judge scores, per-trial results, and experiment-level
aggregation output. No business logic — just data and validation.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field, field_validator, model_validator

from benchmarks.shared_memory.conditions import locus_of
from cerebrum.config.config_manager import config


def _error_text(value: Any) -> Optional[str]:
    """An error field's value as text: None (or any falsy value) for no
    error, a string as it is, anything else through ``str``, so a
    producer that sends an exception or a dict still leaves a record
    the results file can load."""
    if not value:
        return None
    return value if isinstance(value, str) else str(value)


# ---------------------------------------------------------------------------
# Synthetic data models
# ---------------------------------------------------------------------------

class SyntheticProfile(BaseModel):
    """Matches ProfileAgent extraction schema."""

    user_name: str
    preferred_tools: List[str]
    preferred_language: str
    response_style: str


class SyntheticTaskContext(BaseModel):
    """Matches TaskAgent extraction schema."""

    current_project: str
    active_experiment: str
    goals: List[str]
    blockers: List[str]
    next_steps: List[str]


class SyntheticTrialData(BaseModel):
    """All generated data for one trial."""

    profile: SyntheticProfile
    task_context: SyntheticTaskContext
    follow_up_query: str
    plausible_actions: List[str] = []
    user_id: str = ""


# ---------------------------------------------------------------------------
# Retrieval log models
# ---------------------------------------------------------------------------

class RetrievalLogEntry(BaseModel):
    """Single retrieved memory entry with ownership metadata."""

    owner_agent: str
    memory_type: str


class RetrievalLog(BaseModel):
    """Structured record of what memories the AssistantAgent retrieved."""

    shared_memory_count: int = 0
    retrieved_memories: List[RetrievalLogEntry] = []
    cross_agent_found: bool = False
    injection_status: str = "confirmed"
    """Source of truth for injection data.

    Valid values:
    - ``"confirmed"``: from kernel diagnostics (default for backward compat)
    - ``"audit_inferred"``: from audit query with count > 0
    - ``"unknown"``: neither source confirmed injection
    """


# ---------------------------------------------------------------------------
# Metric and result models
# ---------------------------------------------------------------------------

class JudgeScores(BaseModel):
    """LLM judge output — 3-score rubric."""

    profile_usage_score: Optional[int] = None
    task_usage_score: Optional[int] = None
    integration_score: Optional[int] = None
    generic_penalty: Optional[bool] = None
    profile_usage_reasoning: Optional[str] = None
    task_usage_reasoning: Optional[str] = None
    integration_reasoning: Optional[str] = None
    # LLM judge calls the scores took (HybridJudge.evaluate).
    judge_attempts: Optional[int] = None


class V2UserData(BaseModel):
    """A benchmark v2 user (AIOS docs/BENCHMARK_V2.md, "File") with its
    run-scoped user id: the final profile and task context (the judge's
    inputs, equal to the base in v2), the integration query, and the
    script's sessions and probes as the dataset holds them."""

    index: int
    user_id: str
    profile: SyntheticProfile
    task_context: SyntheticTaskContext
    follow_up_query: str
    plausible_actions: List[str] = []
    sessions: List[Dict[str, Any]] = []
    probes: List[Dict[str, Any]] = []


class InjectedMemoryEntry(BaseModel):
    """Single injected memory with source attribution."""

    owner_agent: str
    memory_type: str
    match_score: Optional[float] = None
    # Since Subtask 10 (docs/HETEROGENEITY.md in AIOS): the row's id,
    # stored user and sharing policy, and the provenance its writer
    # attached (None for a row written without it, such as the kernel's
    # own conversation write). None in older files.
    memory_id: Optional[str] = None
    user_id: Optional[str] = None
    sharing_policy: Optional[str] = None
    provenance_agent: Optional[str] = None
    provenance_user: Optional[str] = None
    # Benchmark v2: the row's text as printed (without its age), the
    # event that wrote it, and the fact and session it states.
    provenance_event: Optional[str] = None
    content: Optional[str] = None
    fact_key: Optional[str] = None
    session: Optional[int] = None


class InjectionDiagnostics(BaseModel):
    """Kernel injection audit for a single trial."""

    injected_count: int = 0
    injected_memories: List[InjectedMemoryEntry] = []
    resolved_user_id: Optional[str] = None
    own_fetched: int = 0
    shared_fetched: int = 0
    after_partition: int = 0
    after_visibility: int = 0
    # Whether the consumer applied the visibility rule: reported by the
    # native consumer, False for a V3 consumer and under no_visibility;
    # None where the kernel or the library enforces it.
    visibility_checked: Optional[bool] = None
    after_dedupe: int = 0
    scores_present: bool = False
    threshold_used: Optional[float] = None
    after_threshold: int = 0
    after_cap: int = 0
    top_k_used: Dict[str, int] = {}
    after_budget: int = 0
    tokens_estimated: int = 0
    # The block's format (Subtask 9d): the library's "compact" or
    # "legacy"; "native" for the native agents' own renderer.
    block_format: Optional[str] = None
    block_recency: Optional[bool] = None
    # Benchmark v2: the age unit and the current session the block was
    # built with, and the write-barrier waits that preceded it.
    block_recency_unit: Optional[str] = None
    session: Optional[int] = None
    barrier_waits: List[Dict[str, Any]] = []
    # The block as the consumer received it (Subtask 10); None in older
    # files, "" when nothing was injected.
    block_text: Optional[str] = None
    # Benchmark v2, Amendment 2: why the block cannot be trusted. The
    # library's own or shared fetch failed (``"own: ...; shared: ..."``),
    # or the kernel's injector raised; such a block looks like an empty
    # store, so the harness fails the user. None when nothing failed,
    # and in older files.
    retrieval_error: Optional[str] = None
    injection_error: Optional[str] = None

    @field_validator("retrieval_error", "injection_error", mode="before")
    @classmethod
    def _as_error_text(cls, value: Any) -> Optional[str]:
        return _error_text(value)


class JudgeFreeMeasures(BaseModel):
    """What reached the consumer, measured without the judge (Subtask
    10, docs/HETEROGENEITY.md in AIOS)."""

    # Fraction of the user's profile items (name, language, style, each
    # tool) present in the block; None without a block to check.
    profile_facts_in_block: Optional[float] = None
    profile_facts_missing: List[str] = []
    # Injected rows of another user (a leak).
    cross_user_rows: int = 0
    # Injected rows another agent wrote and did not share (a leak).
    private_rows_from_others: int = 0
    # Writers that stored a memory this trial of which no row reached
    # the block.
    memories_missing: int = 0
    memories_missing_writers: List[str] = []
    # The missing writers split by cause (Subtask 14; judge_free.
    # split_missing): withheld = every row the writer stored was private
    # (or had no policy, the private default), so visibility kept it from
    # the consumer; lost = it stored a shared row and none reached the
    # block. memories_missing == memories_withheld + memories_lost.
    memories_withheld: int = 0
    memories_withheld_writers: List[str] = []
    memories_lost: int = 0
    memories_lost_writers: List[str] = []
    # Block rows that are raw structured JSON or carry writer-schema
    # keys (the form measure for V5).
    raw_payload_rows: int = 0


class WrittenMemoryRecord(BaseModel):
    """Record of metadata written by an agent during a trial."""

    agent_name: str
    memory_type: str
    sharing_policy: str
    user_id: str


class MemoryCounts(BaseModel):
    """Counts of the memories the writers created in a trial (v1: the
    profile and task agents; v2: all three writers, one per write
    event), derived from its ``written_memories``."""

    total: int = 0
    shared: int = 0
    private: int = 0

    @classmethod
    def of(cls, written: List[WrittenMemoryRecord]) -> "MemoryCounts":
        """Count written memories by sharing policy."""
        return cls(
            total=len(written),
            shared=sum(1 for w in written if w.sharing_policy == "shared"),
            private=sum(
                1 for w in written if w.sharing_policy == "private"
            ),
        )


class TokenUsage(BaseModel):
    """Tokens of one group of LLM or embedding calls in a trial.

    ``models`` are LiteLLM-style names (``azure/gpt-4o``,
    ``ollama/nomic-embed-text``), the keys of ``prices.yaml``.
    """

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    models: List[str] = []

    @classmethod
    def of_calls(
        cls, usages: List[Optional[dict]], model: Optional[str] = None
    ) -> "TokenUsage":
        """Sum the kernel's per-call ``token_usage`` dicts. A call whose
        backend reported no usage (None) counts as a call with 0
        tokens."""
        prompt = sum((u or {}).get("prompt_tokens") or 0 for u in usages)
        completion = sum(
            (u or {}).get("completion_tokens") or 0 for u in usages
        )
        return cls(
            calls=len(usages),
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            models=[model] if model and usages else [],
        )


class LatencyBreakdown(BaseModel):
    """Where the assistant call's time went, in milliseconds.

    ``kernel_overhead_ms`` is the memory stages (barrier wait, provider
    search, selection, formatting; done by the kernel in the kernel
    conditions and by the agent in the native ones) plus
    ``schedule_wait_ms``, the kernel scheduler's wait before the model
    call. ``llm_ms`` is the model call itself; overhead + llm_ms is the
    assistant call's latency. None where nothing was measured.
    """

    barrier_wait_ms: Optional[float] = None
    search_ms: Optional[float] = None
    select_ms: Optional[float] = None
    format_ms: Optional[float] = None
    kernel_overhead_ms: Optional[float] = None
    llm_ms: Optional[float] = None
    schedule_wait_ms: Optional[float] = None


class SessionRecord(BaseModel):
    """One benchmark v2 writer session (AIOS docs/BENCHMARK_V2.md,
    "Harness"): the writer, the user id it wrote under, its events with
    the ids each stored, found or deleted, and the listings after it."""

    session: int
    writer: str
    user_id: Optional[str] = None
    # One record per event the writer ran. Since Amendment 2 a write
    # event's ``memory_ids`` and ``stored_rows`` are the writer's rows
    # in the listing after the session whose ``provenance_event`` is
    # the event (every fact Mem0 extracted from it), and
    # ``reported_ids`` the ids the writer's reply named (the kernel's
    # Mem0 add names only the first). Both are None when no listing
    # followed (the session or its listing failed). A revoke keeps its
    # ``found_ids`` and ``deleted_ids``.
    events: List[Dict[str, Any]] = []
    # The write events' ``stored_rows`` summed; None as above. Older
    # files hold the replies' count.
    stored_rows: Optional[int] = None
    deleted_ids: List[str] = []
    writer_failed: bool = False
    error: Optional[str] = None
    # Rows each agent owned for the user after the session.
    listing_counts: Dict[str, int] = {}


class ProbeResult(BaseModel):
    """One benchmark v2 probe turn: the question and its ground truth,
    the consumer's answer and diagnostics, and the judge-free score
    (``probes.score_probe``; judge scores for integration only)."""

    probe_id: str
    type: str
    slot: Optional[str] = None
    question: str
    expected: List[Dict[str, Any]] = []
    forbidden: List[Dict[str, Any]] = []
    target_event: Optional[str] = None
    target_writer: Optional[str] = None
    target_session: Optional[int] = None
    echo_event: Optional[str] = None
    observed: str = ""
    # Why the turn failed the user (a consumer error, a failed
    # retrieval or injection, a block not built at session 7). Such a
    # turn is recorded but never scored: ``passed`` is None and every
    # match and block field keeps its default (Amendment 2).
    error: Optional[str] = None
    # The pass rule's outcome; None for integration (judged) and for a
    # turn with an error.
    passed: Optional[bool] = None
    expected_present: Optional[bool] = None
    stale_present: Optional[bool] = None
    forbidden_in_answer: Optional[bool] = None
    forbidden_in_block: Optional[bool] = None
    matched_expected: List[str] = []
    matched_forbidden: List[str] = []
    transition_marked: Optional[bool] = None
    expected_in_block: Optional[bool] = None
    stale_in_block: Optional[bool] = None
    rows_with_expected: List[Dict[str, Any]] = []
    rows_with_stale: List[Dict[str, Any]] = []
    rows_with_forbidden: List[Dict[str, Any]] = []
    newest_target_row_has_stale: Optional[bool] = None
    cap_bound: Optional[bool] = None
    budget_bound: Optional[bool] = None
    answer_words: Optional[int] = None
    other_values_in_answer: List[str] = []
    semantic_best: Optional[float] = None
    semantic_only: Optional[bool] = None
    # The semantic diagnostic's embedding failure, recorded instead of
    # stopping the run (Amendment 2); it decides no pass. None when the
    # embedding worked or was not called, and in older files.
    semantic_error: Optional[str] = None
    deleted_ids_in_block: List[str] = []
    contaminated: Optional[bool] = None
    visible_stored_rows: Optional[int] = None
    diagnostics: Optional["InjectionDiagnostics"] = None
    judge_scores: Optional[Dict[str, Any]] = None
    integration_score: Optional[int] = None
    token_usage: Optional[Dict[str, Any]] = None
    latency_seconds: Optional[float] = None

    @field_validator("semantic_error", mode="before")
    @classmethod
    def _as_error_text(cls, value: Any) -> Optional[str]:
        return _error_text(value)


class TrialResult(BaseModel):
    """Complete result for one trial."""

    trial_index: int
    condition: str
    method: str = ""
    profile_usage_score: Optional[int] = None
    task_usage_score: Optional[int] = None
    integration_score: Optional[int] = None
    memory_counts: MemoryCounts = MemoryCounts()
    retrieved_context_count: Optional[int] = None
    latency_seconds: Optional[float] = None
    follow_up_query: str = ""
    plausible_actions: List[str] = []
    assistant_response: str = ""
    synthetic_profile: Optional[SyntheticProfile] = None
    synthetic_task_context: Optional[SyntheticTaskContext] = None
    retrieval_log: Optional[RetrievalLog] = None
    injection_diagnostics: Optional[InjectionDiagnostics] = None
    written_memories: List[WrittenMemoryRecord] = []
    # Cost (Subtask 7). The assistant's call, the writers' extraction
    # calls, and the memory backend's own LLM and embedding calls.
    token_usage: TokenUsage = TokenUsage()
    writer_tokens: TokenUsage = TokenUsage()
    backend_llm_tokens: TokenUsage = TokenUsage()
    embedding_tokens: TokenUsage = TokenUsage()
    latency_breakdown: LatencyBreakdown = LatencyBreakdown()
    # Where the memory logic ran (Subtask 8): "kernel", "replicated",
    # "native" or "none"; derived from the method when not given.
    locus: str = ""
    # The memory pipeline library's source hash for kernel and
    # replicated trials (aios.memory.pipeline.PIPELINE_VERSION).
    pipeline_version: Optional[str] = None
    # How the scores were produced (judge.SCORER) and how many LLM judge
    # calls they took; a trial whose judge failed every attempt is failed
    # with no scores (Subtask 4b). None in older files.
    scorer: Optional[str] = None
    judge_attempts: Optional[int] = None
    # Writers whose extraction never validated (Subtask 9): they stored
    # nothing, and the trial is failed and not scored. Each writer's
    # retries. Whether the memory backend extracted facts itself (Mem0
    # with infer=True); None without a memory backend.
    writer_failed: List[str] = []
    writer_retries: Dict[str, int] = {}
    # Each writer's extraction attempts, ``{attempt, temperature, seed}``
    # (Subtask 9d follow-up: retries sample at RETRY_TEMPERATURE, seed+n).
    writer_attempt_settings: Dict[str, List[dict]] = {}
    backend_extraction: Optional[bool] = None
    # The rows each writer's write stored ({agent: n}; Subtask 10). A
    # trial whose backend extracts and stored no row for a writer, or
    # recorded no backend LLM call, is failed: the backend failed
    # silently (``backend_extraction_failed``).
    writer_stored_rows: Dict[str, int] = {}
    # The temperature and seed the kernel applied to the assistant's
    # call (Subtask 9d); None in older files or without a kernel reply.
    decoding: Optional[Dict[str, Any]] = None
    # The dataset the trial's user came from (``users_v1``, ...;
    # ``random`` when generated per trial) and a hash of the trial's
    # inputs (writer inputs and query), equal across cells for one user.
    dataset: Optional[str] = None
    input_sha256: Optional[str] = None
    # Heterogeneity (Subtask 10): the level, the variant each deviating
    # agent ran ({agent: variant}), and the aspects of a variant the
    # locus gave the agent no way to apply ({agent: reason}).
    heterogeneity_level: int = 0
    variants_applied: Dict[str, str] = {}
    variants_not_applied: Dict[str, str] = {}
    judge_free: Optional[JudgeFreeMeasures] = None
    # Benchmark v2 (AIOS docs/BENCHMARK_V2.md, "Harness"): the user's
    # run-scoped id, the negative control the trial ran under, each
    # writer session, each probe, and what the revokes left behind.
    user_id: Optional[str] = None
    control: Optional[str] = None
    sessions: List[SessionRecord] = []
    probe_results: List[ProbeResult] = []
    deleted_memory_ids: List[str] = []
    reappeared_memory_ids: List[str] = []
    revoked_value_rows: List[Dict[str, Any]] = []
    failed: bool = False
    error_message: Optional[str] = None

    @model_validator(mode="after")
    def _fill_locus(self) -> "TrialResult":
        if not self.locus:
            self.locus = locus_of(self.method or self.condition)
        return self


# ---------------------------------------------------------------------------
# Experiment output models
# ---------------------------------------------------------------------------

class SummaryStatistics(BaseModel):
    """Aggregated stats for one metric."""

    mean: float
    std: float
    min: float
    max: float


class ConditionSummary(BaseModel):
    """Summary statistics for all metrics in one condition."""

    profile_usage: SummaryStatistics
    task_usage: SummaryStatistics
    integration: SummaryStatistics
    latency: SummaryStatistics
    memory_total: SummaryStatistics
    memory_shared: SummaryStatistics
    memory_private: SummaryStatistics
    injected_memories: SummaryStatistics
    total_trials: int
    failed_trials: int


def _git_commit(repo: Path) -> Optional[str]:
    """Return a repo's HEAD, marked ``-dirty`` when a tracked file
    differs from it, or None when it cannot be read."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        changes = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "-uno"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{commit}-dirty" if changes else commit


def _harness_commit() -> Optional[str]:
    """Return the Cerebrum commit this harness runs from."""
    return _git_commit(Path(__file__).resolve().parents[2])


def _kernel_commit() -> Optional[str]:
    """Return the sibling AIOS checkout's commit."""
    return _git_commit(Path(__file__).resolve().parents[3] / "AIOS")


def _config_snapshot() -> dict:
    """Return the live kernel's memory settings, or {} without one."""
    try:
        response = requests.get(
            f"{config.get_kernel_url()}/memory/config", timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {}


class ExperimentMetadata(BaseModel):
    """Top-level experiment configuration."""

    trials_per_condition: int
    timestamp: str
    kernel_url: str
    conditions_run: List[str]
    methods_run: List[str] = []
    # None in files written before version 2, whose prompt was version 1.
    judge_prompt_version: Optional[int] = None
    judge_prompt_sha256: Optional[str] = None
    # Set by rejudge.py: the source file and how it was re-scored.
    rejudge: Optional[dict] = None
    # The fixed dataset the users came from (dataset.Dataset.describe);
    # None when users were generated per trial.
    dataset: Optional[dict] = None
    # The decoding requested for every assistant and writer call
    # (``{"temperature": 0.0, "seed": ...}``, Subtask 9d); None when the
    # run used the kernel's default sampling.
    decoding: Optional[dict] = None
    # The judge's decoding (Subtask 9d follow-up); None in files judged
    # before it, which sampled at the kernel default 1.0 with no seed.
    judge_temperature: Optional[float] = None
    judge_seed: Optional[int] = None
    # False when the run was not judged (``--no-judge``, Subtask 10);
    # its trials carry no scores. None in older files (judged).
    judged: Optional[bool] = None
    # ``{level, variant_seed, catalog_version}`` (Subtask 10); None
    # before it (level 0).
    heterogeneity: Optional[dict] = None
    git_commit: Optional[str] = Field(default_factory=_harness_commit)
    kernel_git_commit: Optional[str] = Field(default_factory=_kernel_commit)
    # Looked up at call time, so the test suite can stub it (the
    # live-kernel guard, tests/conftest.py).
    # Benchmark v2: the run's recency, control and the kernel settings
    # the pre-flight checked (AIOS docs/BENCHMARK_V2.md, "Harness").
    run_settings: Dict[str, Any] = {}
    run_id: Optional[str] = None
    config_snapshot: dict = Field(
        default_factory=lambda: _config_snapshot()
    )


class ConditionResults(BaseModel):
    """All trials and summary for one condition."""

    condition: str
    trials: List[TrialResult]
    summary: ConditionSummary


class ExperimentResults(BaseModel):
    """Top-level output structure for the Results_File."""

    experiment_metadata: ExperimentMetadata
    conditions: List[ConditionResults]
