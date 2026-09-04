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
    generic_penalty: Optional[bool] = None
    profile_usage_reasoning: Optional[str] = None
    task_usage_reasoning: Optional[str] = None
    integration_reasoning: Optional[str] = None


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
    profile_usage_score: Optional[int] = None
    task_usage_score: Optional[int] = None
    integration_score: Optional[int] = None
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


class ConditionResults(BaseModel):
    """All trials and summary for one condition."""

    condition: str
    trials: List[TrialResult]
    summary: ConditionSummary


class ExperimentResults(BaseModel):
    """Top-level output structure for the Results_File."""

    experiment_metadata: ExperimentMetadata
    conditions: List[ConditionResults]
