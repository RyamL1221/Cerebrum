"""Heterogeneity variants (NeurIPS Subtask 10, AIOS
docs/HETEROGENEITY.md): the schedule, each variant against the reference
agent in the kernel and native loci, the judge-free measures, and what
trials record. The replicated locus is checked in a fresh interpreter
(``_heterogeneity_checks.py``; known issue 18).
"""
import json
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.shared_memory import run_evaluation
from benchmarks.shared_memory.judge_free import (
    is_raw_payload, measure, split_missing,
)
from benchmarks.shared_memory.models import (
    InjectedMemoryEntry,
    InjectionDiagnostics,
    SyntheticProfile,
    SyntheticTaskContext,
    SyntheticTrialData,
    TrialResult,
    WrittenMemoryRecord,
)
from benchmarks.shared_memory.pipeline import (
    AgentPipeline,
    MethodPipeline,
)
from cerebrum.example.agents import variants
from cerebrum.example.agents.assistant_agent import agent as assistant_module
from cerebrum.example.agents.native import agents as native
from cerebrum.example.agents.profile_agent import agent as profile_module
from cerebrum.example.agents.task_agent import agent as task_module
from cerebrum.example.agents.variants import (
    AGENTS,
    VARIANT_CODES,
    apply_variant,
    cycle,
    schedule,
)

REPO = Path(__file__).resolve().parents[2]
CHECKS = Path(__file__).with_name("_heterogeneity_checks.py")
SEED = run_evaluation.DEFAULT_VARIANT_SEED
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
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


# -- the schedule -------------------------------------------------------------


@pytest.mark.parametrize("seed", [SEED, 1, 7, 12345])
def test_schedule_is_deterministic_and_a_pure_function(seed):
    first = [[schedule(seed, h, i) for i in range(40)] for h in (0, 1, 2)]
    again = [[schedule(seed, h, i) for i in range(40)] for h in (0, 1, 2)]
    assert first == again
    assert all(s == {} for s in first[0])
    for h in (1, 2):
        for chosen in first[h]:
            assert len(chosen) == h  # h distinct agents
            assert set(chosen) <= set(AGENTS)
            assert set(chosen.values()) <= set(VARIANT_CODES)


@pytest.mark.parametrize("seed", [SEED, 1, 7, 12345])
def test_first_five_users_of_h1_and_h2_cover_every_pair_once(seed):
    pairs = [
        pair for h in (1, 2) for i in range(5)
        for pair in schedule(seed, h, i).items()
    ]
    assert len(pairs) == 15
    assert set(pairs) == {(a, v) for a in AGENTS for v in VARIANT_CODES}


@pytest.mark.parametrize("seed", [SEED, 3])
def test_schedule_is_balanced_over_15_users(seed):
    for h, times in ((1, 1), (2, 2)):
        counts = {}
        for i in range(15):
            for pair in schedule(seed, h, i).items():
                counts[pair] = counts.get(pair, 0) + 1
        assert len(counts) == 15 and set(counts.values()) == {times}


def test_cycle_has_no_adjacent_agent_repeat_and_seeds_differ():
    for seed in range(20):
        pairs = cycle(seed)
        for k in range(15):
            assert pairs[k][0] != pairs[(k + 1) % 15][0]
    assert cycle(1) != cycle(2)
    with pytest.raises(ValueError):
        schedule(SEED, 3, 0)


class Recorder:
    """A pipeline that records the variants each trial got."""

    def __init__(self):
        self.seen = []

    def run_trial(self, trial_data, variants=None):
        self.seen.append(variants)
        raise RuntimeError("recorded")


def orchestrator(level, judge=False, method="kernel_shared"):
    with patch.object(run_evaluation, "load_dataset", return_value=None):
        return run_evaluation.EvaluationOrchestrator(
            trials=5, output_dir="/tmp", write_csv=False, condition=None,
            method=method, heterogeneity=level, variant_seed=SEED,
            judge=judge,
        )


def test_every_locus_gets_the_same_schedule():
    """The orchestrator passes schedule(seed, H, i), whatever the cell."""
    seen = {}
    for method in ("kernel_shared", "replicated_mem0", "native_inhouse"):
        runner = orchestrator(2, method=method)
        recorder = Recorder()
        for i in range(5):
            runner.run_single_trial(i, method, recorder, method=method,
                                    trial_data=TRIAL)
        seen[method] = recorder.seen
    assert seen["kernel_shared"] == seen["replicated_mem0"] == (
        seen["native_inhouse"]
    ) == [schedule(SEED, 2, i) for i in range(5)]


def test_heterogeneity_needs_no_judge_and_level_0_passes_nothing():
    with pytest.raises(ValueError, match="--schedule"):
        orchestrator(1, judge=True)
    runner = orchestrator(0, judge=True)
    recorder = MagicMock(side_effect=RuntimeError)
    recorder.run_trial.side_effect = RuntimeError("x")
    runner.run_single_trial(0, "kernel_shared", recorder,
                            trial_data=TRIAL)
    assert recorder.run_trial.call_args.kwargs == {}
    assert runner._heterogeneity_metadata() == {
        "level": 0, "variant_seed": SEED,
        "catalog_version": variants.CATALOG_VERSION,
    }


# -- the kernel locus: what each variant makes the agents send ------------


def kernel_reply(diagnostics=None):
    return {
        "response": {"response_message": "Add pooling."},
        "token_usage": USAGE,
        "llm_timing": {"llm_ms": 5.0},
        "injection_diagnostics": diagnostics or {
            "injected_count": 0, "injected_memories": [], "block_text": "",
        },
    }


@pytest.fixture
def kernel():
    """The kernel conditions' agents with the kernel mocked: the SDK
    memory calls and the model calls are recorded."""
    calls = {"create": [], "update": [], "search": [], "chat": []}

    def create(**kwargs):
        calls["create"].append(kwargs)
        return {"response": {"memory_id": f"m{len(calls['create'])}"}}

    def update(**kwargs):
        calls["update"].append(kwargs)
        return {"response": {}}

    def search(**kwargs):
        calls["search"].append(kwargs)
        return {"response": {"search_results": []}}

    def chat(**kwargs):
        calls["chat"].append(kwargs)
        return kernel_reply()

    def extraction(fields):
        return MagicMock(return_value={
            "response": {"response_message": json.dumps(fields)},
            "token_usage": USAGE,
        })

    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch.object(AgentPipeline, "_kernel_memory_config",
                           staticmethod(lambda: {})))
        enter(patch("benchmarks.shared_memory.pipeline.search_memories",
                    return_value=None))
        enter(patch(
            "cerebrum.memory.apis.create_memory",
            side_effect=lambda agent_name, content, metadata=None,
            base_url=None: create(agent_name=agent_name, content=content,
                                  metadata=metadata, base_url=base_url),
        ))
        for module in (profile_module, task_module):
            enter(patch.object(module, "create_memory", side_effect=create))
            enter(patch.object(module, "update_memory", side_effect=update))
            enter(patch.object(module, "search_memories",
                               side_effect=search))
        enter(patch.object(profile_module, "llm_chat_with_json_output",
                           extraction(PROFILE)))
        enter(patch.object(task_module, "llm_chat_with_json_output",
                           extraction(TASK)))
        enter(patch.object(assistant_module, "llm_chat", side_effect=chat))
        yield calls


def run_kernel(variants_by_agent):
    return MethodPipeline("kernel_shared").run_trial(
        TRIAL, variants=variants_by_agent
    )


USER = TRIAL.user_id + "__kernel_shared"


def test_kernel_reference_sends_shared_rendered_writes_with_provenance(
        kernel):
    result = run_kernel(None)
    profile, task = kernel["create"]
    assert profile["metadata"]["sharing_policy"] == "shared"
    assert profile["metadata"]["owner_agent"] == "profile_agent"
    assert profile["metadata"]["provenance_agent"] == "profile_agent"
    assert profile["metadata"]["provenance_user"] == USER
    assert profile["content"].startswith("My name is Ana Li.")
    assert kernel["chat"][0]["user_id"] == USER
    assert result.variants_applied == {}
    assert result.judge_free is not None


def test_kernel_v1_writer_writes_private(kernel):
    result = run_kernel({"profile_agent": "V1"})
    profile, task = kernel["create"]
    assert profile["metadata"]["sharing_policy"] == "private"
    assert task["metadata"]["sharing_policy"] == "shared"
    assert result.variants_applied == {"profile_agent": "V1"}
    assert "profile_agent" not in result.variants_not_applied


def test_kernel_v1_consumer_block_format_is_not_applied(kernel):
    result = run_kernel({"assistant_agent": "V1"})
    reason = result.variants_not_applied["assistant_agent"]
    assert reason.startswith("V1: ")
    assert "retrieval: a chat request carries no retrieval config" in reason
    assert set(kernel["chat"][0]) == {
        "agent_name", "messages", "base_url", "llms", "user_id",
    }


@pytest.mark.parametrize("agent", AGENTS)
def test_kernel_v2_agent_sends_the_email_convention(kernel, agent):
    run_kernel({agent: "V2"})
    email = f"{USER}@users.example"
    by_agent = {c["agent_name"]: c for c in kernel["create"]}
    searches = {c["agent_name"]: c for c in kernel["search"]}
    for name in ("profile_agent", "task_agent"):
        expected = email if name == agent else USER
        assert by_agent[name]["metadata"]["user_id"] == expected
        assert searches[name]["user_id"] == expected
        # Provenance keeps the reference id.
        assert by_agent[name]["metadata"]["provenance_user"] == USER
    assert kernel["chat"][0]["user_id"] == (
        email if agent == "assistant_agent" else USER
    )


def test_kernel_v3_writer_omits_owner_and_policy(kernel):
    run_kernel({"task_agent": "V3"})
    by_agent = {c["agent_name"]: c for c in kernel["create"]}
    task = by_agent["task_agent"]["metadata"]
    assert "owner_agent" not in task and "sharing_policy" not in task
    assert task["provenance_agent"] == "task_agent"
    assert by_agent["profile_agent"]["metadata"]["owner_agent"] == (
        "profile_agent"
    )


def test_kernel_v3_and_v5_consumer_are_not_applied(kernel):
    result = run_kernel({"assistant_agent": "V3"})
    reason = result.variants_not_applied["assistant_agent"]
    assert "write: the kernel writes the conversation itself" in reason
    assert "access control: the kernel enforces visibility" in reason
    result = run_kernel({"assistant_agent": "V5"})
    assert "write: the kernel writes" in (
        result.variants_not_applied["assistant_agent"]
    )


def test_kernel_v4_is_ignored_and_recorded(kernel):
    result = run_kernel({"assistant_agent": "V4", "profile_agent": "V4"})
    assert "kernel applies its own" in (
        result.variants_not_applied["assistant_agent"]
    )
    assert "SDK search carries k only" in (
        result.variants_not_applied["profile_agent"]
    )


def test_kernel_v5_writer_sends_the_structured_json(kernel):
    run_kernel({"profile_agent": "V5"})
    by_agent = {c["agent_name"]: c for c in kernel["create"]}
    content = by_agent["profile_agent"]["content"]
    assert json.loads(content)["user_name"] == "Ana Li"
    assert content == by_agent["profile_agent"]["metadata"]["structured"]
    assert by_agent["task_agent"]["content"].startswith("I'm working on")


def test_kernel_agents_are_restored_after_the_trial(kernel):
    run_kernel({"profile_agent": "V5", "task_agent": "V3"})
    assert isinstance(profile_module.create_memory, MagicMock)
    assert isinstance(task_module.update_memory, MagicMock)
    kernel["create"].clear()
    run_kernel(None)
    profile, task = kernel["create"]
    assert profile["content"].startswith("My name is")
    assert task["metadata"]["owner_agent"] == "task_agent"


# -- the native locus --------------------------------------------------------

SCORES = {"profile": 0.42, "task_context": 0.45, "conversation": 0.3}


class FakeNativeMemory:
    """A native backend: rows by user, scored by type (the 9d scores of
    relevant memories were below 0.5)."""

    backend_extraction = False

    def __init__(self, rows, k=10):
        self.rows = rows
        self.settings = SimpleNamespace(k=k)

    def write(self, messages, text, agent_name, metadata):
        self.rows.append({
            "memory_id": f"r{len(self.rows)}", "content": text,
            "metadata": dict(metadata), "messages": messages,
            "score": SCORES.get(metadata.get("memory_type"), 0.3),
        })
        # The stored ids, as NativeMemory.write returns them (Subtask 14).
        return [self.rows[-1]["memory_id"]]

    def search(self, query, user_id, k, agent_name=None):
        return [dict(r, metadata=dict(r["metadata"])) for r in self.rows
                if r["metadata"].get("user_id") == user_id][:k]


@pytest.fixture
def native_run():
    rows = []
    chat = MagicMock(return_value={
        "response": {"response_message": "Add pooling."},
        "token_usage": USAGE, "llm_timing": {"llm_ms": 5.0},
    })

    def extraction(fields):
        return MagicMock(return_value={
            "response": {"response_message": json.dumps(fields)},
            "token_usage": USAGE,
        })

    def run(variants_by_agent, extra_rows=()):
        rows.clear()
        rows.extend(extra_rows)
        pipeline = MethodPipeline("native_inhouse")
        memory = FakeNativeMemory(rows)
        pipeline._native_agents = (
            native.NativeProfileAgent("profile_agent", memory),
            native.NativeTaskAgent("task_agent", memory),
            native.NativeAssistantAgent("assistant_agent", memory),
        )
        return pipeline.run_trial(TRIAL, variants=variants_by_agent)

    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch.object(native, "llm_chat", chat))
        enter(patch.object(profile_module, "llm_chat_with_json_output",
                           extraction(PROFILE)))
        enter(patch.object(task_module, "llm_chat_with_json_output",
                           extraction(TASK)))
        yield run, rows, chat


NATIVE_USER = TRIAL.user_id + "__native_inhouse"


def block_of(chat):
    return chat.call_args.kwargs["messages"][0]["content"]


def test_native_reference_injects_both_writers(native_run):
    run, rows, chat = native_run
    result = run(None)
    measures = result.judge_free
    assert result.injection_diagnostics.injected_count == 2
    assert measures.memories_missing == 0
    assert measures.profile_facts_in_block == 1.0
    assert measures.cross_user_rows == measures.private_rows_from_others == 0
    assert measures.raw_payload_rows == 0
    assert block_of(chat).startswith("Relevant memories about this user:")


def test_a_v1_agent_managed_result_names_its_memory_backend(native_run):
    """Amendment 5 decides an empty write by the backend, which the
    agent-managed path reads off the agents' memory."""
    run, rows, chat = native_run
    with patch.object(FakeNativeMemory, "backend", "graphiti",
                      create=True):
        assert run(None).memory_backend == "graphiti"


def test_native_v1_writer_misses_and_v1_consumer_builds_legacy(native_run):
    run, rows, chat = native_run
    result = run({"profile_agent": "V1"})
    assert result.judge_free.memories_missing_writers == ["profile_agent"]
    assert result.judge_free.memories_withheld_writers == ["profile_agent"]
    assert result.judge_free.memories_lost == 0
    assert result.judge_free.profile_facts_in_block < 0.5
    result = run({"assistant_agent": "V1"})
    assert block_of(chat).startswith("===== MEMORY CONTEXT =====")
    assert result.injection_diagnostics.block_format == "legacy"
    assert result.judge_free.profile_facts_in_block == 1.0
    assert "sharing: the assistant writes only" in (
        result.variants_not_applied["assistant_agent"]
    )


def test_native_v2_writer_and_consumer_miss(native_run):
    run, rows, chat = native_run
    result = run({"task_agent": "V2"})
    assert result.judge_free.memories_missing_writers == ["task_agent"]
    assert result.judge_free.memories_lost_writers == ["task_agent"]
    result = run({"assistant_agent": "V2"})
    assert result.judge_free.memories_missing == 2
    assert result.judge_free.memories_lost == 2
    assert result.judge_free.memories_withheld == 0
    assert result.judge_free.profile_facts_in_block == 0.0
    assert result.judge_free.cross_user_rows == 0


def test_native_v3_writer_misses_and_v3_consumer_alone_changes_nothing(
        native_run):
    run, rows, chat = native_run
    result = run({"profile_agent": "V3"})
    stored = [r for r in rows if r["metadata"].get("memory_type") == "profile"]
    assert "owner_agent" not in stored[0]["metadata"]
    assert result.judge_free.memories_missing_writers == ["profile_agent"]
    # No policy on the write is the private default: withheld.
    assert result.judge_free.memories_withheld_writers == ["profile_agent"]
    result = run({"assistant_agent": "V3"})
    assert result.judge_free.memories_missing == 0
    assert result.judge_free.private_rows_from_others == 0


def test_native_v1_writer_with_v3_consumer_leaks_the_private_memory(
        native_run):
    """The one native leak the catalog allows (HETEROGENEITY.md, V3)."""
    run, rows, chat = native_run
    result = run({"profile_agent": "V1", "assistant_agent": "V3"})
    measures = result.judge_free
    assert measures.private_rows_from_others == 1
    assert measures.memories_missing == 0
    reference = run({"profile_agent": "V1"})
    assert reference.judge_free.private_rows_from_others == 0


def test_native_v4_consumer_thresholds_away_the_rows(native_run):
    run, rows, chat = native_run
    result = run({"assistant_agent": "V4"})
    diagnostics = result.injection_diagnostics
    assert diagnostics.threshold_used == 0.5
    assert diagnostics.after_visibility == 2
    assert diagnostics.after_threshold == 0
    assert result.judge_free.memories_missing == 2
    assert result.judge_free.memories_lost == 2
    assert "native writers do not read" in run(
        {"task_agent": "V4"}).variants_not_applied["task_agent"]


def test_native_v5_writer_stores_json_with_the_values(native_run):
    run, rows, chat = native_run
    result = run({"profile_agent": "V5"})
    stored = [r for r in rows if r["metadata"].get("memory_type") == "profile"]
    assert json.loads(stored[0]["content"])["user_name"] == "Ana Li"
    assert stored[0]["messages"] == [
        {"role": "user", "content": stored[0]["content"]}
    ]
    assert result.judge_free.raw_payload_rows == 1
    assert result.judge_free.profile_facts_in_block == 1.0


def test_native_agents_are_restored(native_run):
    run, rows, chat = native_run
    pipeline = MethodPipeline("native_inhouse")
    memory = FakeNativeMemory(rows)
    assistant = native.NativeAssistantAgent("assistant_agent", memory)
    with apply_variant(variants.variant("V4"), assistant,
                       "assistant_agent", "native"):
        assert assistant.relevance_threshold == 0.5 and assistant.k == 5
    assert assistant.relevance_threshold is None and assistant.k is None
    writer = native.NativeProfileAgent("profile_agent", memory)
    writer.user_id = "u"
    with apply_variant(variants.variant("V5"), writer, "profile_agent",
                       "native"):
        assert "write" in vars(memory)
    assert "write" not in vars(memory)
    with apply_variant(variants.variant("V2"), writer, "profile_agent",
                       "native"):
        assert writer.user_id == "u@users.example"
    assert writer.user_id == "u"


# -- the variants themselves ---------------------------------------------------


def test_v2_case_convention_and_v3_keeps_provenance():
    case = variants.v2_identity_convention.IdentityConvention("case")
    assert case.user_id("ana_t0") == "ANA_T0"
    content, metadata = variants.V3.write("x", {
        "owner_agent": "a", "sharing_policy": "shared", "user_id": "u",
        "provenance_agent": "a", "provenance_user": "u",
    })
    assert metadata == {"user_id": "u", "provenance_agent": "a",
                        "provenance_user": "u"}


def test_v5_conversation_becomes_json():
    content, _ = variants.V5.write(
        "User: hi\nAssistant: hello",
        {"memory_type": "conversation"},
    )
    assert json.loads(content) == {"user": "hi", "assistant": "hello"}


def test_every_aspect_without_a_channel_has_a_reason():
    """apply_variant raises if an aspect has neither; run them all."""
    class Agent:
        user_id = "u"
        share_memory = True
        memory = SimpleNamespace(write=lambda *a: None)
        k = relevance_threshold = max_memory_tokens = None
        block_format = "native"
        check_visibility = True

    for locus in ("kernel", "native"):
        for name in AGENTS:
            for code in VARIANT_CODES:
                agent = Agent()
                if locus == "kernel" and name != "assistant_agent":
                    agent = profile_module.ProfileAgent.__new__(
                        profile_module.ProfileAgent)
                    agent.user_id, agent.share_memory = "u", True
                with apply_variant(variants.variant(code), agent, name,
                                   locus):
                    pass


# -- the judge-free measures ------------------------------------------------------


def entry(**kwargs):
    defaults = {"owner_agent": "profile_agent", "memory_type": "profile",
                "user_id": "u", "sharing_policy": "shared"}
    return InjectedMemoryEntry(**{**defaults, **kwargs})


def written(*agents):
    return [WrittenMemoryRecord(agent_name=a, memory_type="", user_id="u",
                                sharing_policy="shared") for a in agents]


def test_measures_count_facts_leaks_and_misses():
    profile = SyntheticProfile(**PROFILE)
    diagnostics = InjectionDiagnostics(
        injected_count=3,
        block_text=("Known about this user:\n- My name is Ana Li. I prefer "
                    "VIM.\n- other user's row\n- a private note"),
        injected_memories=[
            entry(provenance_agent="profile_agent", provenance_user="u"),
            entry(owner_agent="task_agent", user_id="v",
                  provenance_user="v"),
            entry(owner_agent="", sharing_policy="",
                  provenance_agent="task_agent", provenance_user="u"),
        ],
    )
    result = measure(profile, "u", diagnostics,
                     written("profile_agent", "task_agent"))
    # name and vim present; git, Go and terse missing.
    assert result.profile_facts_in_block == pytest.approx(2 / 5)
    assert sorted(result.profile_facts_missing) == ["Go", "git", "terse"]
    assert result.cross_user_rows == 1
    assert result.private_rows_from_others == 1
    assert result.memories_missing == 0  # task_agent's private row reached it


def test_missing_writers_split_into_withheld_and_lost():
    """Subtask 14: a writer whose rows were all private (or carried no
    policy, the private default) was withheld; one that stored a shared
    row that never arrived was lost."""
    profile = SyntheticProfile(**PROFILE)
    records = [
        WrittenMemoryRecord(agent_name="profile_agent", memory_type="p",
                            user_id="u", sharing_policy="private"),
        WrittenMemoryRecord(agent_name="task_agent", memory_type="t",
                            user_id="U@x.example", sharing_policy="shared"),
        WrittenMemoryRecord(agent_name="calendar_agent", memory_type="c",
                            user_id="u", sharing_policy=""),
    ]
    result = measure(profile, "u", InjectionDiagnostics(block_text=""),
                     records)
    assert result.memories_missing == 3
    assert result.memories_withheld_writers == ["calendar_agent",
                                                "profile_agent"]
    assert result.memories_lost_writers == ["task_agent"]
    assert (result.memories_withheld, result.memories_lost) == (2, 1)
    # Stored dicts split the same way (old result files).
    dicts = [r.model_dump() for r in records]
    assert split_missing(["task_agent", "profile_agent"], dicts) == (
        ["profile_agent"], ["task_agent"])
    reached = InjectionDiagnostics(block_text="- x", injected_memories=[
        entry(owner_agent="task_agent", provenance_agent="task_agent",
              provenance_user="u")])
    assert measure(profile, "u", reached, records[1:2]).memories_lost == 0


def test_facts_match_whole_words_only():
    profile = SyntheticProfile(user_name="Bo", preferred_tools=["Git"],
                               preferred_language="Go",
                               response_style="formal")
    diagnostics = InjectionDiagnostics(
        block_text="- My algorithm uses Gitlab; informal notes.",
    )
    assert measure(profile, "u", diagnostics, []).profile_facts_in_block == 0
    diagnostics.block_text = "- I'm Bo (Go, Git), formal."
    assert measure(profile, "u", diagnostics, []).profile_facts_in_block == 1


def test_measures_without_block_and_raw_rows():
    profile = SyntheticProfile(**PROFILE)
    none = measure(profile, "u", None, written("profile_agent"))
    assert none.profile_facts_in_block is None
    assert none.memories_missing_writers == ["profile_agent"]
    assert is_raw_payload('{"user_name": "Ana"}')
    assert is_raw_payload("User profile: user_name: Ana. preferred_tools: vim.")
    assert not is_raw_payload("My name is Ana. My goals are: x.")
    legacy = InjectionDiagnostics(
        block_text="===== MEMORY CONTEXT =====\nx\n\n- [2026] {\"a\": 1}\n"
                   "\n===== END MEMORY CONTEXT =====",
    )
    assert measure(profile, "u", legacy, []).raw_payload_rows == 1


def test_trial_result_records_heterogeneity():
    trial = TrialResult(trial_index=0, condition="kernel_shared",
                        heterogeneity_level=1,
                        variants_applied={"task_agent": "V2"})
    data = json.loads(trial.model_dump_json())
    assert data["variants_applied"] == {"task_agent": "V2"}
    assert data["heterogeneity_level"] == 1
    assert TrialResult(trial_index=0, condition="c").variants_applied == {}


# -- the replicated locus, in a fresh interpreter ---------------------------


def test_replicated_variant_checks_in_a_fresh_interpreter():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS), "-q",
         "-p", "no:cacheprovider",
         "-o", "python_files=_heterogeneity_checks.py"],
        cwd=REPO, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, (
        result.stdout[-6000:] + result.stderr[-3000:]
    )
    assert " passed" in result.stdout
