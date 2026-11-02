"""The pipeline records the memories the agents write, and memory_counts
is derived from that record."""

from unittest.mock import patch

from benchmarks.shared_memory.models import (
    MemoryCounts,
    RetrievalLog,
    SyntheticProfile,
    SyntheticTaskContext,
    SyntheticTrialData,
    WrittenMemoryRecord,
)
from benchmarks.shared_memory.pipeline import AgentPipeline
from cerebrum.example.agents.assistant_agent.agent import AssistantAgent
from cerebrum.example.agents.profile_agent import agent as profile_module
from cerebrum.example.agents.task_agent import agent as task_module

TRIAL = SyntheticTrialData(
    profile=SyntheticProfile(
        user_name="Ana", preferred_tools=["vim"],
        preferred_language="Go", response_style="terse",
    ),
    task_context=SyntheticTaskContext(
        current_project="p", active_experiment="e",
        goals=["g"], blockers=["b"], next_steps=["n"],
    ),
    follow_up_query="q",
    user_id="ana__kernel_private",
)


def agent_run(module, memory_type):
    """Stand in for an agent's run: write one memory the way the agent
    does, through the name its module imported."""
    def run(self, content):
        module.create_memory(
            agent_name=self.agent_name,
            content=content,
            metadata={
                "owner_agent": self.agent_name,
                "memory_type": memory_type,
                "sharing_policy": "private",
                "user_id": self.user_id,
            },
        )
        return {}
    return run


def fake_sdk_create(agent_name, content, metadata=None, base_url=None):
    return {"response": {"memory_id": "m"}}


def test_pipeline_captures_writes_made_through_the_agents_imports():
    with patch("cerebrum.memory.apis.create_memory", fake_sdk_create), \
            patch.object(profile_module, "create_memory", fake_sdk_create), \
            patch.object(task_module, "create_memory", fake_sdk_create), \
            patch.object(profile_module.ProfileAgent, "run",
                         agent_run(profile_module, "profile")), \
            patch.object(task_module.TaskAgent, "run",
                         agent_run(task_module, "task_context")), \
            patch.object(AssistantAgent, "run",
                         lambda self, query: {"result": "ok"}), \
            patch.object(AgentPipeline, "_audit_shared_memories",
                         lambda self, user, query: RetrievalLog()):
        result = AgentPipeline(share_memory=False).run_trial(TRIAL)
    assert [w.memory_type for w in result.written_memories] == [
        "profile", "task_context",
    ]
    assert {w.user_id for w in result.written_memories} == {TRIAL.user_id}


def test_memory_counts_come_from_written_memories():
    def record(policy):
        return WrittenMemoryRecord(
            agent_name="a", memory_type="profile",
            sharing_policy=policy, user_id="u",
        )
    counts = MemoryCounts.of(
        [record("shared"), record("shared"), record("private")]
    )
    assert counts == MemoryCounts(total=3, shared=2, private=1)
    assert MemoryCounts.of([]) == MemoryCounts()
