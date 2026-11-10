"""The agent-managed conditions native_mem0 and native_inhouse
(AIOS docs/NATIVE_USAGE.md): no kernel memory calls, the agents' own
sharing filter, kernel-comparable diagnostics, and the pre-flight."""

import hashlib
import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import chromadb
import pytest
from hypothesis import given, strategies as st

from benchmarks.shared_memory import run_evaluation
from benchmarks.shared_memory.models import (
    InjectionDiagnostics,
    SyntheticProfile,
    SyntheticTaskContext,
    SyntheticTrialData,
)
from benchmarks.shared_memory.pipeline import AgentPipeline, MethodPipeline
from cerebrum.example.agents.native import agents as native_agents
from cerebrum.example.agents.native import backends
from cerebrum.example.agents.shared_memory_utils import (
    render,
    validate_extraction,
)
from cerebrum.example.agents.native.sharing import (
    in_partition,
    memory_metadata,
    visible,
)
from cerebrum.example.agents.profile_agent import agent as profile_module
from cerebrum.example.agents.task_agent import agent as task_module

KERNEL_CONFIG = {
    "max_injected_memories": 10,
    "embedding": {"provider": "ollama", "model": "nomic-embed-text",
                  "dimension": 8, "ollama_base_url": "http://localhost:11434"},
    "backend_llm": {"provider": "ollama", "model": "qwen2.5:7b"},
    "auto_inject": False, "auto_extract": False,
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


class FakeMem0:
    """Shaped like mem0.Memory: one store shared by every client, as one
    Chroma collection is; search filters by user_id only."""

    store: list = []

    def __init__(self):
        self.add_calls = []

    def add(self, messages, user_id, agent_id, metadata, infer):
        self.add_calls.append({"infer": infer, "agent_id": agent_id})
        text = " ".join(m["content"] for m in messages)
        FakeMem0.store.append({
            "id": str(len(FakeMem0.store)), "memory": text,
            "user_id": user_id, "agent_id": agent_id,
            "metadata": {k: v for k, v in metadata.items() if k != "user_id"},
            "score": 1.0,
        })

    def search(self, query, filters, top_k):
        assert set(filters) == {"user_id"}, "native search is user_id only"
        return {"results": [
            dict(r) for r in FakeMem0.store
            if r["user_id"] == filters["user_id"]
        ][:top_k]}


def fake_embed(text):
    digest = hashlib.sha256(text.encode()).digest()
    return [b / 255 for b in digest[:8]]


@pytest.fixture
def harness():
    """Native pipeline with the kernel's LLM calls mocked and every kernel
    memory call recorded."""
    FakeMem0.store = []
    memory_calls = MagicMock()
    chat = MagicMock(return_value={"response": {"response_message": "ok"}})
    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch.object(AgentPipeline, "_kernel_memory_config",
                           staticmethod(lambda: KERNEL_CONFIG)))
        enter(patch.object(backends, "mem0_client", lambda s: FakeMem0()))
        ephemeral = chromadb.EphemeralClient()
        for name in [c.name for c in ephemeral.list_collections()]:
            ephemeral.delete_collection(name)
        enter(patch.object(backends, "chroma_client", lambda: ephemeral))
        enter(patch.object(backends, "Embedder", lambda e: fake_embed))
        enter(patch.object(native_agents, "llm_chat", chat))
        enter(patch.object(profile_module, "llm_chat_with_json_output",
              return_value={"response": {"response_message": json.dumps(PROFILE)}}))
        enter(patch.object(task_module, "llm_chat_with_json_output",
              return_value={"response": {"response_message": json.dumps(TASK)}}))
        enter(patch("cerebrum.memory.apis.send_request", memory_calls))
        for module in (profile_module, task_module):
            for name in ("create_memory", "update_memory", "search_memories"):
                enter(patch.object(module, name, memory_calls))
        yield memory_calls, chat


@pytest.mark.parametrize("method", ["native_mem0", "native_inhouse"])
def test_native_trial_makes_no_kernel_memory_calls(harness, method):
    memory_calls, chat = harness
    pipeline = MethodPipeline(method=method)
    result = pipeline.run_trial(TRIAL)
    assert memory_calls.call_count == 0
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert block.startswith("Relevant memories about this user:")
    assert "Ana Li" in block and "web server" in block
    assert result.injection_diagnostics.injected_count == 2
    assert {m.memory_type for m in result.injection_diagnostics.injected_memories} \
        == {"profile", "task_context"}
    assert [w.sharing_policy for w in result.written_memories] == ["shared", "shared"]
    assert result.retrieval_log.injection_status == "agent_reported"


def test_mem0_writers_ask_mem0_to_extract(harness):
    pipeline = MethodPipeline(method="native_mem0")
    pipeline.run_trial(TRIAL)
    profile, task, assistant = pipeline._native_agents
    for agent in (profile, task, assistant):
        assert all(c["infer"] for c in agent.memory.mem0.add_calls)
        assert {c["agent_id"] for c in agent.memory.mem0.add_calls} == {
            agent.agent_name
        }
    # Three agents, three clients.
    assert len({id(a.memory.mem0) for a in (profile, task, assistant)}) == 3


@pytest.mark.parametrize("method", ["native_mem0", "native_inhouse"])
def test_another_agents_private_memory_never_reaches_the_block(harness, method):
    _, chat = harness
    pipeline = MethodPipeline(method=method)
    profile, task, assistant = pipeline._native("mem0" if method == "native_mem0" else "inhouse")
    task.memory.write(
        [{"role": "user", "content": "secret plan"}], "secret plan",
        "task_agent", memory_metadata("task_agent", TRIAL.user_id + "__" + method,
                                      "task_context", "private"),
    )
    result = pipeline.run_trial(TRIAL)
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert "secret plan" not in block
    diagnostics = result.injection_diagnostics
    assert diagnostics.after_partition == 3
    assert diagnostics.after_visibility == 2


@pytest.mark.parametrize("checks", [True, False])
def test_the_native_consumer_reports_whether_it_checked_visibility(
        harness, checks):
    """The harness's visible_stored_rows reads it (history.visible_rows):
    a consumer that skips the rule (V3, no_visibility) sees another
    agent's private row, and the record says so."""
    _, chat = harness
    pipeline = MethodPipeline(method="native_inhouse")
    _, task, assistant = pipeline._native("inhouse")
    task.memory.write(
        [{"role": "user", "content": "secret plan"}], "secret plan",
        "task_agent", memory_metadata("task_agent",
                                      TRIAL.user_id + "__native_inhouse",
                                      "task_context", "private"),
    )
    assistant.check_visibility = checks
    result = pipeline.run_trial(TRIAL)
    raw = result.assistant_result["injection_diagnostics"]
    assert raw["visibility_checked"] is checks
    assert result.injection_diagnostics.visibility_checked is checks
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert ("secret plan" in block) is (not checks)


# The stages of the library's selection that native has no counterpart
# of (Amendment 4: supersession and the tombstone guard). Its consumer
# is unchanged by Amendment 4, so the record holds None for them.
LIBRARY_ONLY_KEYS = {"after_supersession", "superseded_rows",
                     "after_tombstone", "tombstoned_rows",
                     "tombstoned_forms"}


def test_native_diagnostics_have_the_kernel_keys(harness):
    """Native fills every kernel diagnostics key, except the library's
    Amendment 4 stages, which it does not run: those it leaves unset
    (None in the record), never a count that would claim a guard
    ran."""
    result = MethodPipeline(method="native_inhouse").run_trial(TRIAL)
    raw = result.assistant_result["injection_diagnostics"]
    assert LIBRARY_ONLY_KEYS <= set(InjectionDiagnostics.model_fields)
    assert set(InjectionDiagnostics.model_fields) - LIBRARY_ONLY_KEYS \
        <= set(raw)
    assert all(raw.get(key) is None for key in LIBRARY_ONLY_KEYS)
    recorded = result.injection_diagnostics
    assert all(getattr(recorded, key) is None for key in LIBRARY_ONLY_KEYS)
    assert raw["scores_present"] is True
    assert raw["threshold_used"] is None
    assert result.latency_seconds < sum(result.assistant_result["timing"].values()) + 1e-9


META = st.fixed_dictionaries({}, optional={
    "owner_agent": st.sampled_from(["assistant_agent", "task_agent", ""]),
    "sharing_policy": st.sampled_from(["shared", "private", "Shared", ""]),
    "user_id": st.sampled_from(["u", "v", ""]),
})


@given(META)
def test_filter_never_shows_another_agents_private_memory(metadata):
    if visible("assistant_agent", metadata) and in_partition("u", metadata):
        assert metadata.get("user_id") == "u"
        assert (metadata.get("owner_agent") == "assistant_agent"
                or metadata.get("sharing_policy") == "shared")


ROW_SCORES = st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0))


@given(st.lists(st.tuples(ROW_SCORES, st.booleans(), st.booleans()),
                max_size=15),
       st.integers(min_value=1, max_value=12))
def test_the_reference_consumer_keeps_the_backends_order(rows, k):
    """Mem0's documented use is its results in the order returned, cut
    at the limit, with no score threshold. The reference native
    consumer keeps the rows the sharing rule lets it see, in the
    backend's order, cut at k by position: none is dropped or moved for
    its score (Mem0's scores are distances; NATIVE_USAGE.md,
    "Evidence")."""
    assistant = native_agents.NativeAssistantAgent(
        "assistant_agent", MagicMock())
    given_rows = [
        {"memory_id": str(i), "content": f"row {i}", "score": score,
         "metadata": {"user_id": "u" if mine else "v",
                      "owner_agent": "task_agent",
                      "sharing_policy": "shared" if shared else "private"}}
        for i, (score, mine, shared) in enumerate(rows)
    ]
    kept, _ = assistant._select(given_rows, "u", k)
    assert kept == [
        r for r in given_rows
        if r["metadata"]["user_id"] == "u"
        and r["metadata"]["sharing_policy"] == "shared"
    ][:k]


def test_the_native_mem0_block_follows_mem0s_order(harness):
    """The block lists Mem0's results as Mem0 ordered them, and the
    diagnostics record each row's score as Mem0 returned it: recorded,
    never acted on."""
    _, chat = harness
    memory = native_agents.NativeMemory(
        "mem0", backends.NativeSettings.from_kernel_config(KERNEL_CONFIG))
    assistant = native_agents.NativeAssistantAgent("assistant_agent", memory)
    assistant.user_id = "u"
    scores = [1.0, 0.05, 0.6, 1.0, 0.3]
    FakeMem0.store = [
        {"id": str(i), "memory": f"fact {i}", "user_id": "u",
         "agent_id": "task_agent", "score": score,
         "metadata": {"owner_agent": "task_agent",
                      "sharing_policy": "shared",
                      "memory_type": "task_context"}}
        for i, score in enumerate(scores)
    ]
    result = assistant.run("question")
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert block.splitlines()[1:] == [f"- fact {i}" for i in range(5)]
    injected = result["injection_diagnostics"]["injected_memories"]
    assert [m["match_score"] for m in injected] == scores


def test_shared_renderer_handles_real_writer_variants():
    """Since Subtask 9 the native writers use the shared validator and
    renderer: aliases and one nested object are accepted, a partial
    extraction is not (it is retried, then the writer fails)."""
    fields, _ = validate_extraction("profile", {"user_attributes": {
        "name": "Ava", "tools": ["Git"], "language": "Go",
        "style": "concise", "mood": "calm",
    }})
    assert render("profile", fields) == (
        "My name is Ava. I prefer to use Git. My preferred programming "
        "language is Go. I like concise responses."
    )
    assert validate_extraction(
        "task_context", {"project_name": "P", "next_actions": ["a", "b"]}
    )[0] is None


def test_collection_names_are_valid_and_distinct():
    long_a, long_b = "x" * 80 + "a", "x" * 80 + "b"
    for user in ("ana@example.com", long_a):
        assert len(backends.collection_name(user)) <= 63
    assert backends.collection_name(long_a) != backends.collection_name(long_b)


def kernel_mode(**body):
    get = patch.object(run_evaluation.requests, "get").start()
    get.return_value.json.return_value = body
    return get


@pytest.fixture
def stop_patches():
    yield
    patch.stopall()


def test_preflight_refuses_native_with_injection_on(stop_patches):
    kernel_mode(auto_inject=True, auto_extract=False)
    with pytest.raises(SystemExit, match="native_mem0"):
        run_evaluation.check_kernel_mode("http://k", "native_mem0")


def test_preflight_refuses_native_with_extraction_on(stop_patches):
    kernel_mode(auto_inject=False, auto_extract=True)
    with pytest.raises(SystemExit, match="auto_extract=True"):
        run_evaluation.check_kernel_mode("http://k", "native_inhouse")


def test_preflight_refuses_kernel_condition_with_injection_off(stop_patches):
    kernel_mode(auto_inject=False, auto_extract=False)
    with pytest.raises(SystemExit, match="kernel_shared"):
        run_evaluation.check_kernel_mode("http://k", "kernel_shared")


def test_preflight_accepts_matching_modes(stop_patches):
    kernel_mode(auto_inject=False, auto_extract=False)
    run_evaluation.check_kernel_mode("http://k", "native_mem0")
    kernel_mode(auto_inject=True, auto_extract=True)
    run_evaluation.check_kernel_mode("http://k", "kernel_private")


def test_preflight_skips_conditions_without_memory(stop_patches):
    get = kernel_mode(auto_inject=True, auto_extract=True)
    run_evaluation.check_kernel_mode("http://k", "naive_concat")
    get.assert_not_called()


def test_preflight_refuses_an_old_kernel(stop_patches):
    kernel_mode(max_injected_memories=10)
    with pytest.raises(SystemExit, match="predates"):
        run_evaluation.check_kernel_mode("http://k", "native_mem0")
