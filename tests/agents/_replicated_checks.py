"""Replicated-logic agents (AIOS docs/REPLICATED_LOGIC.md).

Not collected by the suite: ``test_replicated_agents.py`` runs this file
in a fresh interpreter, because the replicated agents import the
kernel's ``aios`` package, which this checkout's ``aios/`` stub (imported
by other test modules) would shadow.
"""
import json
import sys
import threading
import time
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from cerebrum.example.agents.replicated import agents as replicated
from cerebrum.example.agents.replicated import library

pipeline_lib = library.load()

from aios.memory.providers import factory  # noqa: E402
from aios.memory.providers.in_house import InHouseProvider  # noqa: E402

from benchmarks.shared_memory.models import SyntheticProfile  # noqa: E402
from benchmarks.shared_memory.models import (  # noqa: E402
    SyntheticTaskContext,
    SyntheticTrialData,
)
from benchmarks.shared_memory.pipeline import (  # noqa: E402
    AgentPipeline,
    MethodPipeline,
)
from cerebrum.example.agents.profile_agent import agent as profile_module  # noqa: E402
from cerebrum.example.agents.task_agent import agent as task_module  # noqa: E402


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
KERNEL_USAGE = {"prompt_tokens": 900, "completion_tokens": 100,
                "total_tokens": 1000}


class SlowProvider(InHouseProvider):
    """A backend whose writes become durable only when ``commit`` is
    set, after ``add`` was called (like Mem0's asynchronous commit)."""

    synchronous_commit = False

    def __init__(self):
        super().__init__()
        self.initialize({})
        self.adding = threading.Event()
        self.commit = threading.Event()

    def add(self, memory_note):
        self.adding.set()
        self.commit.wait(5)
        return super().add(memory_note)


@pytest.fixture
def harness():
    """The replicated pipeline with one shared in-memory backend, the
    kernel's LLM calls mocked, and every kernel memory call recorded."""
    store = InHouseProvider()
    store.initialize({})
    memory_calls = MagicMock()
    chat = MagicMock(return_value={
        "response": {"response_message": "Add connection pooling."},
        "token_usage": KERNEL_USAGE,
        "llm_timing": {"llm_ms": 700.0, "schedule_wait_ms": 90.0},
    })
    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch.object(AgentPipeline, "_kernel_memory_config",
                           staticmethod(lambda: KERNEL_CONFIG)))
        enter(patch.object(factory.ProviderFactory, "create",
                           classmethod(lambda cls, kind, config: store)))
        enter(patch.object(replicated, "llm_chat", chat))
        enter(patch.object(profile_module, "llm_chat_with_json_output",
              return_value={"response": {"response_message": json.dumps(PROFILE)},
                            "token_usage": KERNEL_USAGE}))
        enter(patch.object(task_module, "llm_chat_with_json_output",
              return_value={"response": {"response_message": json.dumps(TASK)},
                            "token_usage": KERNEL_USAGE}))
        enter(patch("cerebrum.memory.apis.send_request", memory_calls))
        for module in (profile_module, task_module):
            for name in ("create_memory", "update_memory", "search_memories"):
                enter(patch.object(module, name, memory_calls))
        yield store, memory_calls, chat


@pytest.mark.parametrize("method", ["replicated_mem0", "replicated_inhouse"])
def test_replicated_trial_makes_no_kernel_memory_calls(harness, method):
    store, memory_calls, chat = harness
    result = MethodPipeline(method=method).run_trial(TRIAL)
    assert memory_calls.call_count == 0
    user = TRIAL.user_id + "__" + method
    # Everything went to the backend through the agents' own pipelines.
    types = sorted(
        row.metadata["memory_type"] for row in store.list(user, 100)
    )
    assert types == ["conversation", "profile", "task_context"]
    # The assistant sent the kernel's block, built by the library: the
    # compact format by default (Subtask 9d).
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert block.startswith("Known about this user:\n- My name is")
    assert "MEMORY CONTEXT" not in block
    assert result.injection_diagnostics.block_format == "compact"
    # The writers store the shared rendering (Subtask 9), profile first.
    assert block.index("My name is") < block.index("I'm working on")
    diagnostics = result.injection_diagnostics
    assert diagnostics.injected_count == 2
    assert result.retrieval_log.injection_status == "agent_reported"
    assert result.pipeline_version == pipeline_lib.PIPELINE_VERSION
    assert result.token_usage.total_tokens == 1000
    assert result.writer_tokens.calls == 2
    latency = result.latency_breakdown
    assert latency.llm_ms == 700.0
    assert latency.kernel_overhead_ms == pytest.approx(
        latency.barrier_wait_ms + latency.search_ms + latency.select_ms
        + latency.format_ms + latency.schedule_wait_ms
    )
    # The library runs without the kernel's manager, syscalls or server.
    assert "aios.memory.manager" not in sys.modules
    assert not any(m.startswith("aios.syscall") for m in sys.modules)
    assert "runtime.launch" not in sys.modules


def test_writers_update_their_memory_on_a_second_trial(harness):
    store, _, _ = harness
    pipeline = MethodPipeline(method="replicated_inhouse")
    pipeline.run_trial(TRIAL)
    pipeline.run_trial(TRIAL)
    user = TRIAL.user_id + "__replicated_inhouse"
    types = sorted(r.metadata["memory_type"] for r in store.list(user, 100))
    # One profile and one task context, updated in place; a conversation
    # per trial.
    assert types == ["conversation", "conversation", "profile",
                     "task_context"]


def test_each_agent_holds_its_own_pipeline_barrier_and_resolver(harness):
    pipeline = MethodPipeline(method="replicated_inhouse")
    agents = pipeline._replicated("inhouse")
    pipelines = [agent.memory.pipeline for agent in agents]
    assert len({id(p) for p in pipelines}) == 3
    assert len({id(p.barrier) for p in pipelines}) == 3
    assert len({id(p.resolver) for p in pipelines}) == 3
    # Difference 2: no shared registry. A user the profile agent wrote
    # for is unknown to the others.
    profile, task, assistant = agents
    profile.user_id = "only_profile"
    profile.run(json.dumps(PROFILE))
    assert "only_profile" in profile.memory.pipeline.resolver.known_user_ids
    assert "only_profile" not in assistant.memory.pipeline.resolver.known_user_ids
    assert "only_profile" not in task.memory.pipeline.resolver.known_user_ids


def profile_note(user):
    return pipeline_lib.note_from_request({
        "content": json.dumps(PROFILE),
        "metadata": {"owner_agent": "profile_agent", "user_id": user,
                     "memory_type": "profile", "sharing_policy": "shared"},
    })


def read_during_write(writer, reader, store, release_after=None):
    """The writer writes in a thread; once its write has been accepted
    (the provider's add was called) but is not durable, the reader
    retrieves. ``release_after`` seconds later the write commits."""
    thread = threading.Thread(
        target=writer.write, args=("profile_agent", "u", profile_note("u"))
    )
    thread.start()
    assert store.adding.wait(5)
    if release_after is not None:
        threading.Timer(release_after, store.commit.set).start()
    rows, diagnostics = reader.retrieve(
        "assistant_agent", "u", "profile", request_user_id="u"
    )
    store.commit.set()
    thread.join(5)
    return rows, diagnostics


def test_difference_1_a_local_barrier_cannot_order_another_agents_write():
    settings = pipeline_lib.PipelineSettings.from_memory_config(
        KERNEL_CONFIG["pipeline"]
    )
    # Replicated: ProfileAgent and AssistantAgent each with its own
    # barrier. The read does not wait and misses the accepted write.
    store = SlowProvider()
    profile = pipeline_lib.MemoryPipeline(store, settings)
    assistant = pipeline_lib.MemoryPipeline(store, settings)
    rows, diagnostics = read_during_write(profile, assistant, store)
    assert rows == []
    assert diagnostics["barrier_waits"] == []
    assert len(store.list("u", 10)) == 1  # it was written, too late

    # Kernel placement: one barrier for both. The same read waits for
    # the write and sees it.
    store = SlowProvider()
    shared = pipeline_lib.WriteBarrier(config=settings.write_barrier)
    profile = pipeline_lib.MemoryPipeline(store, settings, barrier=shared)
    assistant = pipeline_lib.MemoryPipeline(store, settings, barrier=shared)
    started = time.monotonic()
    rows, diagnostics = read_during_write(
        profile, assistant, store, release_after=0.3
    )
    assert [r["metadata"]["memory_type"] for r in rows] == ["profile"]
    assert diagnostics["barrier_waits"] == [
        {"user_id": "u", "outcome": "DRAINED"}
    ]
    assert time.monotonic() - started >= 0.25


def test_replicated_mem0_follows_the_kernels_extraction_and_counts_it():
    """With the kernel's backend_extraction, the replicated Mem0 store
    extracts with the pinned backend LLM, as the kernel's Mem0 does, and
    its LiteLLM calls are counted per trial (Subtask 9)."""
    import litellm

    from cerebrum.utils import usage

    config = {**KERNEL_CONFIG, "backend_extraction": True,
              "backend_llm": {"provider": "azure_openai", "model": "gpt-4o"}}
    seen = {}

    def create(cls, kind, provider_config):
        seen.update(kind=kind, config=provider_config)
        store = InHouseProvider()
        store.initialize({})
        store.backend_extraction = provider_config.get("infer", False)
        return store

    before = [c for c in litellm.callbacks
              if getattr(c, "accumulator", None) is usage.ACCUMULATOR]
    for c in before:
        litellm.callbacks.remove(c)
    with patch.object(factory.ProviderFactory, "create",
                      classmethod(create)):
        memory = replicated.ReplicatedMemory("mem0", config)
    assert seen["kind"] == "mem0"
    assert seen["config"]["infer"] is True
    assert seen["config"]["llm"] == usage.mem0_llm_config(
        config["backend_llm"]
    )
    assert memory.backend_extraction is True
    assert any(getattr(c, "accumulator", None) is usage.ACCUMULATOR
               for c in litellm.callbacks)
    # In-house: no extraction.
    with patch.object(factory.ProviderFactory, "create",
                      classmethod(create)):
        assert not replicated.ReplicatedMemory(
            "inhouse", config
        ).backend_extraction


def test_replicated_follows_the_kernels_block_format(harness):
    """A replicated agent formats its block as the kernel reports it at
    /memory/config: here the legacy format behind memory.block_format."""
    _, _, chat = harness
    legacy = dict(KERNEL_CONFIG, pipeline=dict(
        KERNEL_CONFIG["pipeline"], block_format="legacy",
    ))
    with patch.object(AgentPipeline, "_kernel_memory_config",
                      staticmethod(lambda: legacy)):
        MethodPipeline(method="replicated_inhouse").run_trial(TRIAL)
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert block.startswith("===== MEMORY CONTEXT =====")
