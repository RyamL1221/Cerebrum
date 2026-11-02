"""Pydantic data models for the shared memory evaluation harness.

Defines all structured data shapes used across the harness: synthetic data
generation inputs, judge scores, per-trial results, and experiment-level
aggregation output. No business logic — just data and validation.
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from cerebrum.config.config_manager import config


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


class InjectedMemoryEntry(BaseModel):
    """Single injected memory with source attribution."""

    owner_agent: str
    memory_type: str
    match_score: Optional[float] = None


class InjectionDiagnostics(BaseModel):
    """Kernel injection audit for a single trial."""

    injected_count: int = 0
    injected_memories: List[InjectedMemoryEntry] = []
    resolved_user_id: Optional[str] = None
    own_fetched: int = 0
    shared_fetched: int = 0
    after_partition: int = 0
    after_visibility: int = 0
    after_dedupe: int = 0
    scores_present: bool = False
    threshold_used: Optional[float] = None
    after_threshold: int = 0
    after_cap: int = 0
    top_k_used: Dict[str, int] = {}
    after_budget: int = 0
    tokens_estimated: int = 0


class WrittenMemoryRecord(BaseModel):
    """Record of metadata written by an agent during a trial."""

    agent_name: str
    memory_type: str
    sharing_policy: str
    user_id: str


class MemoryCounts(BaseModel):
    """Counts of the memories the profile and task agents created in a
    trial, derived from its ``written_memories``."""

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
    failed: bool = False
    error_message: Optional[str] = None


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
    git_commit: Optional[str] = Field(default_factory=_harness_commit)
    kernel_git_commit: Optional[str] = Field(default_factory=_kernel_commit)
    config_snapshot: dict = Field(default_factory=_config_snapshot)


class ConditionResults(BaseModel):
    """All trials and summary for one condition."""

    condition: str
    trials: List[TrialResult]
    summary: ConditionSummary


class ExperimentResults(BaseModel):
    """Top-level output structure for the Results_File."""

    experiment_metadata: ExperimentMetadata
    conditions: List[ConditionResults]
