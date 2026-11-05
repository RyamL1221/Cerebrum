"""Subtask 9: writer validation and the same stored content in every
locus.

Kernel, replicated and native writers validate their extraction, retry
up to WRITER_RETRIES times, store the one shared rendering with the
fields as JSON in the metadata, and store nothing when the extraction
never validates.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cerebrum.example.agents import shared_memory_utils as smu
from cerebrum.example.agents.native.agents import (
    NativeProfileAgent,
    NativeTaskAgent,
)
from cerebrum.example.agents.profile_agent import agent as profile_module
from cerebrum.example.agents.replicated.agents import (
    ReplicatedProfileAgent,
    ReplicatedTaskAgent,
)
from cerebrum.example.agents.task_agent import agent as task_module

PROFILE = {"user_name": "Ana Li", "preferred_tools": ["vim", "git"],
           "preferred_language": "Go", "response_style": "terse"}
TASK = {"current_project": "web server", "active_experiment": "load test",
        "goals": ["handle 10k connections"], "blockers": [],
        "next_steps": ["add pooling"]}
STATUS = {"status": "success",
          "message": "Task context extracted successfully."}
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def replies(*payloads):
    """A fake ``llm_chat_with_json_output`` answering with ``payloads``
    in turn."""
    answers = iter(payloads)

    def chat(**_):
        return {"response": {"response_message": json.dumps(next(answers))},
                "token_usage": USAGE}
    return chat


# --- validation -------------------------------------------------------

def test_status_payload_does_not_validate():
    fields, problems = smu.validate_extraction("task_context", STATUS)
    assert fields is None and "missing current_project" in problems


def test_aliases_and_one_nested_object_validate():
    fields, _ = smu.validate_extraction("profile", {"user": {
        "name": "Ana Li", "tools": "vim", "language": "Go",
        "style": "terse", "mood": "calm",
    }})
    assert fields == {"user_name": "Ana Li", "preferred_tools": ["vim"],
                      "preferred_language": "Go", "response_style": "terse"}


@pytest.mark.parametrize("change", [
    {"blockers": None}, {"goals": []}, {"current_project": ""},
    {"next_steps": [{"step": 1}]},
])
def test_bad_fields_do_not_validate(change):
    data = {**TASK, **change}
    data = {k: v for k, v in data.items() if v is not None}
    assert smu.validate_extraction("task_context", data)[0] is None


def test_empty_blockers_validate():
    assert smu.validate_extraction("task_context", TASK)[0] == TASK


def test_render_is_the_native_text():
    assert smu.render("profile", PROFILE) == (
        "My name is Ana Li. I prefer to use vim; git. My preferred "
        "programming language is Go. I like terse responses."
    )
    # An empty list is left out.
    assert "blockers" not in smu.render("task_context", TASK)


def test_extract_validated_retries_then_fails():
    calls = []

    def once(_llms):
        calls.append(1)
        return STATUS

    result = smu.extract_validated("task_context", once)
    assert result.failed
    assert len(calls) == 1 + smu.WRITER_RETRIES
    assert result.retries == smu.WRITER_RETRIES
    assert len(result.token_usages) == len(calls)


def test_extract_validated_counts_retries_and_exceptions():
    answers = iter([ValueError("not JSON"), STATUS, TASK])

    def once(_llms):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    result = smu.extract_validated("task_context", once)
    assert not result.failed and result.retries == 2
    assert result.fields == TASK


# --- the same stored content in every locus -----------------------------

class FakeNativeMemory:
    backend_extraction = False

    def __init__(self):
        self.writes = []

    def write(self, messages, text, agent_name, metadata):
        self.writes.append({"messages": messages, "text": text,
                            "metadata": dict(metadata)})


class FakePipeline:
    def __init__(self):
        self.writes, self.updates = [], []

    def retrieve(self, *args, **kwargs):
        return [], {}

    def write(self, agent_name, user_id, note):
        self.writes.append(note)
        return "m1"

    def update(self, *args):
        self.updates.append(args)


class _Note(SimpleNamespace):
    pass


def replicated_memory():
    pipeline = FakePipeline()
    library = SimpleNamespace(note_from_request=lambda params: _Note(
        content=params["content"], metadata=dict(params["metadata"]),
    ))
    return SimpleNamespace(pipeline=pipeline, library=library,
                           backend_extraction=False)


def kernel_write(agent_cls, module, payloads):
    """What a kernel writer sends to ``create_memory``."""
    created = []

    def create_memory(agent_name, content, metadata=None, base_url=None):
        created.append({"content": content, "metadata": metadata})
        return {"response": {"memory_id": "k1"}}

    agent = agent_cls(agent_cls.__name__.lower())
    agent.user_id, agent.share_memory = "u1", True
    with patch.object(module, "llm_chat_with_json_output",
                      side_effect=replies(*payloads)), \
            patch.object(module, "search_memories", return_value={}), \
            patch.object(module, "create_memory",
                         side_effect=create_memory):
        result = agent.run("input")
    return result, created


@pytest.mark.parametrize("memory_type,data,kernel_cls,module,native_cls,"
                         "replicated_cls", [
    ("profile", PROFILE, profile_module.ProfileAgent, profile_module,
     NativeProfileAgent, ReplicatedProfileAgent),
    ("task_context", TASK, task_module.TaskAgent, task_module,
     NativeTaskAgent, ReplicatedTaskAgent),
])
def test_every_locus_stores_the_same_text_and_fields(
    memory_type, data, kernel_cls, module, native_cls, replicated_cls,
):
    wrapped = {"extracted": data}  # a nested reply, as Llama sends
    _, created = kernel_write(kernel_cls, module, [wrapped])

    native_memory = FakeNativeMemory()
    native = native_cls("writer", native_memory)
    native.user_id = "u1"
    with patch.object(module, "llm_chat_with_json_output",
                      side_effect=replies(wrapped)):
        native.run("input")

    memory = replicated_memory()
    replicated = replicated_cls("writer", memory)
    replicated.user_id = "u1"
    with patch.object(module, "llm_chat_with_json_output",
                      side_effect=replies(wrapped)):
        replicated.run("input")

    expected = smu.render(memory_type, data)
    stored = [
        (created[0]["content"], created[0]["metadata"]),
        (native_memory.writes[0]["text"], native_memory.writes[0]["metadata"]),
        (memory.pipeline.writes[0].content,
         memory.pipeline.writes[0].metadata),
    ]
    for text, metadata in stored:
        assert text == expected
        assert json.loads(metadata[smu.FIELD_STRUCTURED]) == data
        assert metadata["memory_type"] == memory_type
    assert native_memory.writes[0]["messages"] == [
        {"role": "user", "content": expected}
    ]


# --- writer failure: recorded, never stored -----------------------------

def test_kernel_writer_failure_stores_nothing():
    result, created = kernel_write(
        task_module.TaskAgent, task_module, [STATUS] * 3
    )
    assert created == []
    assert result["writer_failed"] is True
    assert result["writer_retries"] == smu.WRITER_RETRIES
    assert len(result["token_usages"]) == 3


def test_kernel_writer_retry_then_success_is_recorded():
    result, created = kernel_write(
        task_module.TaskAgent, task_module, [STATUS, TASK]
    )
    assert len(created) == 1
    assert result["writer_failed"] is False
    assert result["writer_retries"] == 1


@pytest.mark.parametrize("make", ["native", "replicated"])
def test_agent_managed_writer_failure_stores_nothing(make):
    if make == "native":
        memory = FakeNativeMemory()
        agent = NativeTaskAgent("task_agent", memory)
        stored = memory.writes
    else:
        memory = replicated_memory()
        agent = ReplicatedTaskAgent("task_agent", memory)
        stored = memory.pipeline.writes
    agent.user_id = "u1"
    with patch.object(task_module, "llm_chat_with_json_output",
                      side_effect=replies(*[STATUS] * 3)):
        result = agent.run("input")
    assert stored == []
    assert result["writer_failed"] is True and result["written"] is None


def test_writer_tokens_count_every_attempt():
    from benchmarks.shared_memory.pipeline import cost_fields

    result, _ = kernel_write(
        task_module.TaskAgent, task_module, [STATUS, TASK]
    )
    fields = cost_fields({}, [result], [{"name": "m", "backend": "b"}])
    assert fields["writer_tokens"].calls == 2
    assert fields["writer_tokens"].total_tokens == 30


def test_writer_failure_fails_the_trial_without_judging(tmp_path):
    from benchmarks.shared_memory import models
    from benchmarks.shared_memory.models import SyntheticTrialData
    from benchmarks.shared_memory.pipeline import PipelineResult
    from benchmarks.shared_memory.run_evaluation import (
        EvaluationOrchestrator,
    )
    from tests.agents.test_judge_prompt_v2 import PROFILE as P, TASK as T

    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        orchestrator = EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path), write_csv=False,
            condition=None, method="kernel_shared",
        )
    pipeline = SimpleNamespace(run_trial=lambda _d: PipelineResult(
        profile_result={}, task_result={}, assistant_result={},
        assistant_response="", latency_seconds=0.0,
        writer_failed=["task_agent"],
        writer_retries={"profile_agent": 0, "task_agent": 2},
        backend_extraction=True,
    ))
    data = SyntheticTrialData(profile=P, task_context=T,
                              follow_up_query="q", user_id="u")
    with patch.object(orchestrator.judge, "evaluate") as evaluate, \
            patch.object(models.requests, "get"):
        trial = orchestrator.run_single_trial(
            0, "kernel_shared", pipeline, method="kernel_shared",
            trial_data=data,
        )
    evaluate.assert_not_called()
    assert trial.failed
    assert trial.writer_failed == ["task_agent"]
    assert trial.writer_retries == {"profile_agent": 0, "task_agent": 2}
    assert trial.backend_extraction is True
    assert trial.profile_usage_score is None
