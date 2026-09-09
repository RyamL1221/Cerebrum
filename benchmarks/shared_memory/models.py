"""Pydantic data models for the shared memory evaluation harness.

Defines all structured data shapes used across the harness: synthetic data
generation inputs, judge scores, per-trial results, and experiment-level
aggregation output. No business logic — just data and validation.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


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
    """All generated data for one trial (== one interaction under sessions)."""

    profile: SyntheticProfile
    task_context: SyntheticTaskContext
    follow_up_query: str
    plausible_actions: List[str] = []
    user_id: str = ""
    # Accumulating-session fields (design doc §3.4). Descriptive/grouping only —
    # NOT the reward-attribution key (that stays the global monotonic
    # ``trial_index`` on TrialResult). Defaults preserve one-shot mode:
    # session_id="" and interaction_index=0.
    #
    # session_id: stable across all interactions of one simulated user; equals
    #   the per-session user_id (no interaction index baked in) so all of a
    #   session's writes accumulate in one kernel collection.
    # interaction_index: 0-based position of this interaction WITHIN its session
    #   (0..interactions_per_user-1). Distinct from trial_index, which is the
    #   run-global per-interaction counter and must NOT be reset per session.
    session_id: str = ""
    interaction_index: int = 0


class SyntheticSession(BaseModel):
    """One simulated user across an ordered list of evolving interactions.

    A session shares a single stable ``user_id`` (== ``session_id``) and a
    single ``profile`` across all its interactions, so memory accumulates in
    one kernel collection. Each entry in ``interactions`` is a
    ``SyntheticTrialData`` with its own evolved ``task_context`` /
    ``follow_up_query`` / ``plausible_actions``, its ``interaction_index`` set
    to its position, and ``session_id``/``user_id`` set to the shared session
    id. The run-global ``trial_index`` is assigned by the runner (not here), so
    it stays monotonic across sessions.
    """

    session_id: str
    user_id: str
    profile: SyntheticProfile
    interactions: List[SyntheticTrialData]


# ---------------------------------------------------------------------------
# Retrieval log models
# ---------------------------------------------------------------------------

class RetrievalLogEntry(BaseModel):
    """Single retrieved memory entry with ownership metadata."""

    owner_agent: str
    memory_type: str
    memory_id: Optional[str] = None
    """Stable ID of this memory, when available from the source (kernel
    diagnostics or audit query). Defaults to None for backward compatibility
    and for sources that do not expose an ID."""


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

    injected_memory_ids: List[str] = []
    """IDs of the memories actually injected into this trial's prompt.

    Pure bookkeeping for downstream reward attribution (Subtask 4). Populated
    from kernel injection diagnostics when available, or from the harness-side
    audit query otherwise. Order matches ``retrieved_memories``. Empty when no
    IDs are available (e.g. a source that does not expose memory IDs). This
    field is observational only and does not affect injection behavior."""


# ---------------------------------------------------------------------------
# Metric and result models
# ---------------------------------------------------------------------------

class JudgeScores(BaseModel):
    """LLM judge output — 3-score rubric."""

    profile_usage_score: Optional[int] = None
    task_usage_score: Optional[int] = None
    integration_score: Optional[int] = None
    # Which scoring rubric produced these scores. Defaults to "v1" so older
    # persisted result files (written before this field existed) still parse
    # unchanged. Enforces the "never pool v1 and v2 scores" invariant in
    # aggregation, CSV output, and reward calculation. Flipped to "v2" only via
    # the v2 prompt path (subtask 3), never guessed at read time.
    rubric_version: str = "v1"
    # v2-only per-criterion detail. Shape:
    # {"profile_usage": {"criteria": {"1": 0|1, ..., "5": 0|1},
    #                    "justification": {"<idx>": "<one sentence>", ...}},
    #  "task_usage": {...}, "integration": {...}}
    # Populated by LLMJudge._parse_v2_scores for rubric_version == "v2"; stays
    # None for v1 (holistic scoring has no criteria to report). Persisted so the
    # 0/1 breakdown and zero-score justifications survive to results JSON for
    # later analysis (human-rating pipeline, re-judge script).
    criteria_breakdown: Optional[Dict] = None
    generic_penalty: Optional[bool] = None
    profile_usage_reasoning: Optional[str] = None
    task_usage_reasoning: Optional[str] = None
    integration_reasoning: Optional[str] = None
    # Per-call token usage from the judge LLM's /query response (the kernel's
    # top-level sibling key), captured by LLMJudge.evaluate() and propagated
    # through HybridJudge.evaluate(). Shape mirrors the assistant path:
    # {"prompt_tokens", "completion_tokens", "total_tokens"} with each value an
    # int or None, or the whole dict None when the response omitted it / the
    # judge call failed. Distinct from the assistant's token_usage.
    token_usage: Optional[Dict[str, Optional[int]]] = None


class MemoryCounts(BaseModel):
    """Memory creation counts for a trial."""

    total: int = 0
    shared: int = 0
    private: int = 0


class InjectedMemoryEntry(BaseModel):
    """Single injected memory with source attribution."""

    owner_agent: str
    memory_type: str
    match_score: Optional[float] = None
    memory_id: Optional[str] = None
    """Stable ID of the injected memory, when the kernel provides it. Used to
    populate RetrievalLog.injected_memory_ids for reward attribution."""


class InjectionDiagnostics(BaseModel):
    """Kernel injection audit for a single trial."""

    injected_count: int = 0
    injected_memories: List[InjectedMemoryEntry] = []


class WrittenMemoryRecord(BaseModel):
    """Record of metadata written by an agent during a trial."""

    agent_name: str
    memory_type: str
    sharing_policy: str
    user_id: str


class PolicyActionEntry(BaseModel):
    """One adaptive-policy reward record attributed to a trial.

    Mirrors a single ``event == "reward"`` record from the kernel's
    ``policy_trials.jsonl`` (see docs/policy-trials-jsonl-findings.md). A trial
    typically has several of these — one per bandit rewarded — so
    ``TrialResult.policy_action`` is a list, not a single entry. This is the
    outcome-side signal only (which bandit/arm was credited and with what
    reward); the decision-side ``select`` records are NOT joinable per trial
    (their ``trial_id`` is always null), so they are intentionally absent."""

    bandit: str
    arm_index: int
    reward: float
    memory_id: Optional[str] = None


class TrialResult(BaseModel):
    """Complete result for one trial."""

    trial_index: int
    condition: str
    method: str = ""
    # Accumulating-session grouping fields (design doc §3.4). ``trial_index``
    # above remains the run-global, monotonic per-interaction reward-attribution
    # key (join: policy_reward.trial_id == trial_index) and is NOT reset per
    # session. These two are descriptive only, for grouping per-interaction rows
    # into sessions and locating a turn within a session; defaults ("" / 0)
    # preserve one-shot result files unchanged.
    session_id: str = ""
    interaction_index: int = 0
    profile_usage_score: Optional[int] = None
    task_usage_score: Optional[int] = None
    integration_score: Optional[int] = None
    # Copied from the JudgeScores that produced the three scores above. Defaults
    # to "v1" so older persisted TrialResult records parse unchanged. Used to
    # partition aggregation/CSV/reward so v1 and v2 scores never silently pool.
    rubric_version: str = "v1"
    # Copied from JudgeScores.criteria_breakdown. Per-criterion 0/1 breakdown +
    # zero-score justifications for v2; None for v1. Same shape documented on
    # JudgeScores. Persisted to results JSON for downstream analysis.
    criteria_breakdown: Optional[Dict] = None
    memory_counts: MemoryCounts = MemoryCounts()
    retrieved_context_count: Optional[int] = None
    latency_seconds: Optional[float] = None
    follow_up_query: str = ""
    assistant_response: str = ""
    synthetic_profile: Optional[SyntheticProfile] = None
    synthetic_task_context: Optional[SyntheticTaskContext] = None
    retrieval_log: Optional[RetrievalLog] = None
    injection_diagnostics: Optional[InjectionDiagnostics] = None
    written_memories: List[WrittenMemoryRecord] = []
    failed: bool = False
    error_message: Optional[str] = None
    # Per-call token usage from the kernel's /query response, threaded through
    # AssistantAgent.run() → PipelineResult → here. Shape:
    # {"prompt_tokens", "completion_tokens", "total_tokens"} with each value an
    # int or None, or the whole dict None (error paths, or a response that
    # omitted it). Populated only on the success path where a PipelineResult
    # is available.
    token_usage: Optional[Dict[str, Optional[int]]] = None
    # Per-call token usage from the JUDGE LLM's /query response (GPT-5.4 in the
    # threshold search), captured in LLMJudge.evaluate() and propagated through
    # HybridJudge → JudgeScores.token_usage → here. Distinct from the
    # assistant-only ``token_usage`` field above; do not overload/merge them.
    # Same shape ({"prompt_tokens", "completion_tokens", "total_tokens"} / int
    # or None values / whole dict None). Populated only on the success path
    # where judging occurred; None on failure/early-return paths.
    judge_token_usage: Optional[Dict[str, Optional[int]]] = None
    # Adaptive-policy reward records attributed to this trial by the standalone
    # post-hoc join (benchmarks/shared_memory/join_policy_actions.py). NOT
    # threaded through the live path (AssistantAgent/PipelineResult are
    # untouched) — populated after the run by joining the kernel's
    # policy_trials.jsonl reward events on reward.trial_id == trial_index.
    # None = not yet joined; [] = joined but no reward records for this trial.
    policy_action: Optional[List[PolicyActionEntry]] = None


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


class ExperimentMetadata(BaseModel):
    """Top-level experiment configuration."""

    trials_per_condition: int
    timestamp: str
    kernel_url: str
    conditions_run: List[str]
    methods_run: List[str] = []
    # Pre-flight provenance: the live kernel memory-gating state captured by
    # EvaluationOrchestrator._verify_gating_status() BEFORE any trial ran, keyed
    # by method name. Records what was actually configured server-side when the
    # run executed (the raw GET /memory/gating_status response — e.g.
    # {"adaptive_policy_enabled", "static_thresholds_enabled",
    # "static_thresholds_config"}). Stored as a raw dict passthrough rather than
    # a typed sub-model because it mirrors a server-owned contract (notably the
    # opaque static_thresholds_config) that the client must not pin a schema to
    # — same reasoning as TrialResult.token_usage.
    #
    # DISTINCT from TrialResult.policy_action, and deliberately NOT merged with
    # it: this is DECISION-SIDE / PRE-FLIGHT provenance (what gating tier/config
    # was live before trials ran), whereas policy_action is OUTCOME-SIDE /
    # POST-HOC (which bandit/arm was rewarded, joined after the run from
    # policy_trials.jsonl). See docs/harness-aios-gating-dependency-scope.md.
    #
    # Only populated for the kernel_shared* tiers that undergo the pre-flight
    # check; None (whole field) when no gating-verified method ran, and any
    # non-verified method (naive_concat/vanilla_rag/mem0_default) is simply
    # absent from the dict.
    gating_status_by_method: Optional[Dict[str, Dict]] = None


class ConditionResults(BaseModel):
    """All trials and summary for one condition."""

    condition: str
    trials: List[TrialResult]
    summary: ConditionSummary


class ExperimentResults(BaseModel):
    """Top-level output structure for the Results_File."""

    experiment_metadata: ExperimentMetadata
    conditions: List[ConditionResults]
