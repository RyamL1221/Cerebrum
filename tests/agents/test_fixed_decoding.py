"""Subtask 9d: fixed decoding for the assistant and writer calls.

The kernel's /query handler drops ``LLMQuery.temperature``, so the
harness puts ``temperature`` and ``seed`` on every ``llms`` entry it
hands the agents; the kernel applies them to the model call. The judge
keeps its own settings. ExperimentMetadata records the requested
decoding, and each trial what the kernel applied.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import models
from benchmarks.shared_memory.pipeline import PipelineResult, cost_fields
from benchmarks.shared_memory.run_evaluation import (
    DEFAULT_SEED,
    EvaluationOrchestrator,
    build_arg_parser,
    decoding_from_args,
    with_decoding,
)
from cerebrum.example.agents.assistant_agent.agent import AssistantAgent
from cerebrum.example.agents.profile_agent import agent as profile_module
from cerebrum.example.agents.task_agent import agent as task_module

QWEN = [{"name": "qwen2.5:7b", "backend": "ollama"}]
FIXED = {"temperature": 0.0, "seed": 11}


def test_with_decoding_adds_the_settings_to_every_entry():
    llms = QWEN + [{"name": "gpt-4o", "backend": "azure"}]
    out = with_decoding(llms, FIXED)
    assert out == [dict(entry, **FIXED) for entry in llms]
    assert llms[0] == {"name": "qwen2.5:7b", "backend": "ollama"}
    assert with_decoding(QWEN, {"temperature": 0.0, "seed": None}) == [
        dict(QWEN[0], temperature=0.0),
    ]
    assert with_decoding(QWEN, None) == QWEN
    assert with_decoding(None, FIXED) is None


def _args(*argv):
    return build_arg_parser().parse_args(["--method", "kernel_shared",
                                          *argv])


def test_cli_defaults_to_fixed_decoding():
    assert decoding_from_args(_args()) == {
        "temperature": 0.0, "seed": DEFAULT_SEED,
    }
    assert decoding_from_args(_args("--seed", "none")) == {
        "temperature": 0.0, "seed": None,
    }
    assert decoding_from_args(_args("--temperature", "0.2", "--seed",
                                    "5")) == {"temperature": 0.2, "seed": 5}
    assert decoding_from_args(_args("--sampled")) is None


def _orchestrator(tmp_path, **kwargs):
    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        return EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path), write_csv=False,
            condition=None, method="kernel_shared", **kwargs,
        )


def test_assistant_llms_carry_the_decoding_and_the_judge_does_not(tmp_path):
    orch = _orchestrator(tmp_path, assistant_llms=QWEN, decoding=FIXED)
    assert orch.assistant_llms == [dict(QWEN[0], **FIXED)]
    assert orch.judge_llms == QWEN
    assert orch.generator.llms == orch.assistant_llms
    judge = _orchestrator(
        tmp_path, assistant_llms=QWEN, decoding=FIXED,
        judge_llms=[{"name": "gpt-5.4", "backend": "azure"}],
    ).judge_llms
    assert judge == [{"name": "gpt-5.4", "backend": "azure"}]


def test_fixed_decoding_needs_a_model_entry(tmp_path):
    with pytest.raises(ValueError, match="--assistant-model"):
        _orchestrator(tmp_path, decoding=FIXED)
    assert _orchestrator(tmp_path).decoding is None


def test_writers_and_assistant_send_the_decoding(tmp_path):
    llms = with_decoding(QWEN, FIXED)
    sent = []

    def json_chat(**kwargs):
        # Every extraction attempt (an empty reply fails validation and
        # is retried) carries the decoding.
        sent.append(kwargs["llms"])
        return {"response": {"response_message": "{}"},
                "token_usage": None}

    for module, cls in ((profile_module, profile_module.ProfileAgent),
                        (task_module, task_module.TaskAgent)):
        agent = cls(cls.__name__.lower())
        agent.llms = llms
        with patch.object(module, "llm_chat_with_json_output", json_chat):
            try:
                agent.run("I'm Ana; I use vim.")
            except Exception:
                pass  # storing is not under test here
    assert len(sent) == 6  # two writers, three attempts each
    assert all(entry == llms for entry in sent)

    replies = []

    def chat(**kwargs):
        replies.append(kwargs["llms"])
        return {"response": {"response_message": "hi"},
                "token_usage": None, "decoding": dict(FIXED)}

    assistant = AssistantAgent("assistant_agent", llms=llms)
    with patch("cerebrum.example.agents.assistant_agent.agent.llm_chat",
               chat):
        result = assistant.run("hello")
    assert replies == [llms]
    assert result["decoding"] == FIXED
    assert cost_fields(result, [], llms)["decoding"] == FIXED


def test_metadata_and_trials_record_the_decoding(tmp_path):
    from benchmarks.shared_memory.models import SyntheticTrialData
    from tests.agents.test_judge_prompt_v2 import PROFILE as P, TASK as T

    orch = _orchestrator(tmp_path, assistant_llms=QWEN, decoding=FIXED)
    pipeline = SimpleNamespace(run_trial=lambda _d: PipelineResult(
        profile_result={}, task_result={}, assistant_result={},
        assistant_response="answer", latency_seconds=0.0,
        decoding=dict(FIXED),
    ))
    data = SyntheticTrialData(profile=P, task_context=T,
                              follow_up_query="q", user_id="u")
    scores = SimpleNamespace(
        profile_usage_score=5, task_usage_score=5, integration_score=5,
        profile_usage_reasoning="", task_usage_reasoning="",
        integration_reasoning="", scorer="hybrid", attempts=1,
    )
    with patch.object(orch.judge, "evaluate", return_value=scores), \
            patch.object(models.requests, "get"):
        trial = orch.run_single_trial(
            0, "kernel_shared", pipeline, method="kernel_shared",
            trial_data=data,
        )
    assert trial.decoding == FIXED
    meta = models.ExperimentMetadata(
        trials_per_condition=1, timestamp="t", kernel_url="u",
        conditions_run=["kernel_shared"], decoding=orch.decoding,
    )
    assert json.loads(meta.model_dump_json())["decoding"] == FIXED
