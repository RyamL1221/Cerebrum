"""Heterogeneity variants in the replicated locus (AIOS
docs/HETEROGENEITY.md).

Not collected by the suite: ``test_heterogeneity.py`` runs this file in
a fresh interpreter, because the replicated agents import the kernel's
``aios`` package, which this checkout's ``aios/`` stub would shadow
(known issue 18).
"""
import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from cerebrum.example.agents.replicated import agents as replicated
from cerebrum.example.agents.replicated import library

pipeline_lib = library.load()

from aios.memory.providers import factory  # noqa: E402
from aios.memory.providers.in_house import InHouseProvider  # noqa: E402

from benchmarks.shared_memory.models import (  # noqa: E402
    SyntheticProfile,
    SyntheticTaskContext,
    SyntheticTrialData,
)
from benchmarks.shared_memory.pipeline import (  # noqa: E402
    AgentPipeline,
    MethodPipeline,
)
from cerebrum.example.agents import variants  # noqa: E402
from cerebrum.example.agents.profile_agent import agent as profile_module  # noqa: E402
from cerebrum.example.agents.task_agent import agent as task_module  # noqa: E402
from cerebrum.example.agents.variants import apply_variant  # noqa: E402


@pytest.fixture(autouse=True)
def _store_root(tmp_path, monkeypatch):
    """Every replicated store's root, and so its tombstone file (AIOS
    docs/DELETION_AND_SUPERSESSION.md), in a temporary directory:
    nothing persists in the checkout's .replicated_memory."""
    monkeypatch.setattr(replicated, "STORE_ROOT",
                        str(tmp_path / "replicated_memory"))


KERNEL_CONFIG = {
    "max_injected_memories": 10,
    "embedding": {"provider": "ollama", "model": "nomic-embed-text",
                  "dimension": 768,
                  "ollama_base_url": "http://localhost:11434"},
    "auto_inject": False, "auto_extract": False,
    "pipeline": {"relevance_threshold": 0.0, "max_injected_memories": 10,
                 "max_memory_tokens": 2000,
                 "write_barrier": {"enabled": True, "timeout_ms": 2000}},
    "pipeline_version": pipeline_lib.PIPELINE_VERSION,
}
PROFILE = {"user_name": "Ana Li", "preferred_tools": ["vim", "git"],
           "preferred_language": "Go", "response_style": "terse"}
TASK = {"current_project": "web server", "active_experiment": "load test",
        "goals": ["handle 10k connections"], "blockers": ["tail latency"],
        "next_steps": ["add pooling"]}
TRIAL = SyntheticTrialData(
    profile=SyntheticProfile(**PROFILE),
    task_context=SyntheticTaskContext(**TASK),
    follow_up_query="What should I do next on the web server?",
    user_id="ana_t0",
)
USAGE = {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10}
METHOD = "replicated_inhouse"
USER = f"{TRIAL.user_id}__{METHOD}"


@pytest.fixture
def run():
    """One replicated pipeline, kept across trials like the harness's,
    over an in-memory backend; returns (run, store, chat)."""
    store = InHouseProvider()
    store.initialize({})
    chat = MagicMock(return_value={
        "response": {"response_message": "Add connection pooling."},
        "token_usage": USAGE,
        "llm_timing": {"llm_ms": 7.0, "schedule_wait_ms": 1.0},
    })
    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch.object(AgentPipeline, "_kernel_memory_config",
                           staticmethod(lambda: KERNEL_CONFIG)))
        enter(patch.object(factory.ProviderFactory, "create",
                           classmethod(lambda cls, kind, config: store)))
        enter(patch.object(replicated, "llm_chat", chat))
        enter(patch.object(profile_module, "llm_chat_with_json_output",
              return_value={"response": {"response_message":
                                         json.dumps(PROFILE)},
                            "token_usage": USAGE}))
        enter(patch.object(task_module, "llm_chat_with_json_output",
              return_value={"response": {"response_message":
                                         json.dumps(TASK)},
                            "token_usage": USAGE}))
        pipeline = MethodPipeline(method=METHOD)

        def trial(variants_by_agent, user_suffix=""):
            data = TRIAL.model_copy(
                update={"user_id": TRIAL.user_id + user_suffix}
            )
            return pipeline.run_trial(data, variants=variants_by_agent)

        yield trial, store, chat, pipeline


def block_of(chat):
    return chat.call_args.kwargs["messages"][0]["content"]


def test_reference(run):
    trial, store, chat, _ = run
    result = trial(None)
    assert result.judge_free.memories_missing == 0
    assert result.judge_free.profile_facts_in_block == 1.0
    assert result.judge_free.raw_payload_rows == 0
    rows = result.injection_diagnostics.injected_memories
    assert {r.provenance_agent for r in rows} == {
        "profile_agent", "task_agent"}
    assert {r.provenance_user for r in rows} == {USER}


def test_v1_writer_private_and_consumer_legacy(run):
    trial, store, chat, pipeline = run
    result = trial({"task_agent": "V1"}, "_a")
    assert result.judge_free.memories_missing_writers == ["task_agent"]
    result = trial({"assistant_agent": "V1"}, "_b")
    assert block_of(chat).startswith("===== MEMORY CONTEXT =====")
    assert result.injection_diagnostics.block_format == "legacy"
    assert result.judge_free.profile_facts_in_block == 1.0
    # Restored: the next reference trial builds the compact block.
    trial(None, "_c")
    assert block_of(chat).startswith("Known about this user:")
    assert pipeline._replicated_agents[2].memory.pipeline.settings \
        .block_format == "compact"


def test_v2_resolves_independently_and_misses(run):
    """The library's default resolver keeps the alias: another user."""
    trial, store, chat, _ = run
    result = trial({"profile_agent": "V2"}, "_a")
    assert result.judge_free.memories_missing_writers == ["profile_agent"]
    alias = f"{TRIAL.user_id}_a__{METHOD}@users.example"
    assert [r.metadata["memory_type"] for r in store.list(alias, 10)] == [
        "profile"]
    result = trial({"assistant_agent": "V2"}, "_b")
    assert result.judge_free.memories_missing == 2
    assert result.judge_free.cross_user_rows == 0


def test_v3_writer_gets_the_librarys_private_default(run):
    trial, store, chat, _ = run
    result = trial({"profile_agent": "V3"}, "_a")
    user = f"{TRIAL.user_id}_a__{METHOD}"
    profile = [r for r in store.list(user, 10)
               if r.metadata["memory_type"] == "profile"][0]
    assert profile.metadata["owner_agent"] == "profile_agent"
    assert profile.metadata["sharing_policy"] == "private"
    assert result.judge_free.memories_missing_writers == ["profile_agent"]
    result = trial({"assistant_agent": "V3"}, "_b")
    assert result.judge_free.memories_missing == 0
    assert "library the agent links enforces" in (
        result.variants_not_applied["assistant_agent"]
    )


def test_v4_consumer_uses_its_own_settings(run):
    trial, store, chat, pipeline = run
    reference = trial(None, "_a").injection_diagnostics
    tuned = trial({"assistant_agent": "V4"}, "_b").injection_diagnostics
    assert reference.threshold_used == 0.0 and tuned.threshold_used == 0.5
    assert tuned.top_k_used["own"] == 5
    assert tuned.after_cap < reference.after_cap
    settings = pipeline._replicated_agents[2].memory.pipeline.settings
    assert settings.relevance_threshold == 0.0  # restored


def test_v5_writer_and_consumer_write_json(run):
    trial, store, chat, _ = run
    result = trial({"profile_agent": "V5"}, "_a")
    user = f"{TRIAL.user_id}_a__{METHOD}"
    profile = [r for r in store.list(user, 10)
               if r.metadata["memory_type"] == "profile"][0]
    assert json.loads(profile.content)["user_name"] == "Ana Li"
    # The library's formatter prints the unknown keys as "key: value".
    assert "user_name: Ana Li" in block_of(chat)
    assert result.judge_free.raw_payload_rows == 1
    assert result.judge_free.profile_facts_in_block == 1.0
    trial({"assistant_agent": "V5"}, "_b")
    user = f"{TRIAL.user_id}_b__{METHOD}"
    turn = [r for r in store.list(user, 10)
            if r.metadata["memory_type"] == "conversation"][0]
    assert json.loads(turn.content)["user"] == TRIAL.follow_up_query


def test_v4_writer_existence_check_uses_the_threshold():
    """Applied (not recorded as not applied) to a replicated writer."""
    store = InHouseProvider()
    store.initialize({})
    with patch.object(factory.ProviderFactory, "create",
                      classmethod(lambda cls, kind, config: store)):
        memory = replicated.ReplicatedMemory("inhouse", KERNEL_CONFIG)
    writer = replicated.ReplicatedTaskAgent("task_agent", memory)
    with apply_variant(variants.variant("V4"), writer, "task_agent",
                       "replicated") as skipped:
        assert skipped is None
        assert memory.pipeline.settings.relevance_threshold == 0.5
        assert memory.pipeline.barrier is not None
    assert memory.pipeline.settings.relevance_threshold == 0.0
