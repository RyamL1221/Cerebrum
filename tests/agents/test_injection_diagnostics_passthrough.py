"""Regression tests: kernel diagnostics reach TrialResult, and agent
upserts update in the owning user's collection.

Before these fixes AssistantAgent dropped injection_diagnostics, so every
stored trial had them null. No running kernel required.
"""

from unittest.mock import patch

from benchmarks.shared_memory.models import InjectionDiagnostics
from benchmarks.shared_memory.pipeline import AgentPipeline
from cerebrum.example.agents.assistant_agent.agent import AssistantAgent
from cerebrum.example.agents.profile_agent.agent import ProfileAgent
from cerebrum.example.agents.task_agent.agent import TaskAgent

DIAGNOSTICS = {
    "injected_count": 1,
    "injected_memories": [{
        "memory_id": "m1",
        "owner_agent": "profile_agent",
        "memory_type": "profile",
        "match_score": None,
    }],
    "resolved_user_id": "alice",
    "own_fetched": 2,
    "shared_fetched": 1,
    "after_partition": 3,
    "after_visibility": 2,
    "after_dedupe": 1,
    "scores_present": False,
    "after_threshold": 1,
    "after_cap": 1,
    "top_k_used": {"own": 10, "shared": 40},
    "after_budget": 1,
    "tokens_estimated": 12,
}


def test_assistant_forwards_kernel_diagnostics():
    agent = AssistantAgent("assistant_agent")
    response = {
        "response": {"response_message": "hi"},
        "injection_diagnostics": DIAGNOSTICS,
    }
    with patch(
        "cerebrum.example.agents.assistant_agent.agent.llm_chat",
        return_value=response,
    ):
        result = agent.run("hello")
    assert result["injection_diagnostics"] == DIAGNOSTICS


def test_pipeline_keeps_every_selection_field():
    pipeline = AgentPipeline(share_memory=True)
    diagnostics = pipeline._extract_injection_diagnostics({
        "injection_diagnostics": DIAGNOSTICS,
    })
    assert isinstance(diagnostics, InjectionDiagnostics)
    dumped = diagnostics.model_dump()
    for key, value in DIAGNOSTICS.items():
        if key != "injected_memories":
            assert dumped[key] == value


def _existing(memory_type):
    return {"response": {"search_results": [{
        "memory_id": "m1",
        "metadata": {"memory_type": memory_type},
    }]}}


def test_profile_upsert_updates_the_users_collection():
    module = "cerebrum.example.agents.profile_agent.agent"
    with patch(f"{module}.search_memories",
               return_value=_existing("profile")), \
            patch(f"{module}.update_memory") as update, \
            patch(f"{module}.create_memory") as create:
        ProfileAgent("profile_agent")._upsert_profile_memory(
            "alice", {"user_name": "Alice"}
        )
    create.assert_not_called()
    assert update.call_args.kwargs["memory_id"] == "m1"
    assert update.call_args.kwargs["metadata"]["user_id"] == "alice"


def test_task_upsert_updates_the_users_collection():
    module = "cerebrum.example.agents.task_agent.agent"
    with patch(f"{module}.search_memories",
               return_value=_existing("task_context")), \
            patch(f"{module}.update_memory") as update, \
            patch(f"{module}.create_memory") as create:
        TaskAgent("task_agent")._upsert_task_memory(
            "alice", {"project": "x"}
        )
    create.assert_not_called()
    assert update.call_args.kwargs["metadata"]["user_id"] == "alice"
