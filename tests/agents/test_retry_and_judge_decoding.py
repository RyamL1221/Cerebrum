"""Subtask 9d follow-up: writer retries that actually retry, and the
greedy judge.

Under greedy decoding a retry repeats the first answer, so attempt n > 0
samples at RETRY_TEMPERATURE with seed + n; the first attempt keeps the
request's decoding, and every trial records each writer's attempts. The
judge runs at temperature 0 with a fixed seed and the results record it.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from benchmarks.shared_memory import models
from benchmarks.shared_memory.judge import (
    JUDGE_SEED,
    JUDGE_TEMPERATURE,
    HybridJudge,
)
from benchmarks.shared_memory.pipeline import writer_report
from benchmarks.shared_memory.rejudge import rejudge_experiment
from cerebrum.example.agents import shared_memory_utils as smu
from cerebrum.example.agents.profile_agent import agent as profile_module

QWEN = [{"name": "qwen2.5:7b", "backend": "ollama",
         "temperature": 0.0, "seed": 100}]
PROFILE = {"user_name": "Ana Li", "preferred_tools": ["vim", "git"],
           "preferred_language": "Go", "response_style": "terse"}
STATUS = {"status": "success", "message": "done"}


def test_first_attempt_unchanged_retries_sample_with_seed_plus_n():
    assert smu.attempt_llms(QWEN, 0) == QWEN
    assert smu.attempt_llms(QWEN, 1) == [dict(
        QWEN[0], temperature=smu.RETRY_TEMPERATURE, seed=101)]
    assert smu.attempt_llms(QWEN, 2)[0]["seed"] == 102
    assert QWEN[0]["seed"] == 100  # not mutated
    no_seed = [{"name": "m", "temperature": 0.0}]
    assert smu.attempt_llms(no_seed, 1) == [
        {"name": "m", "temperature": smu.RETRY_TEMPERATURE}]
    assert smu.attempt_llms(None, 1) is None
    assert smu.RETRY_TEMPERATURE == 0.3


def test_extract_validated_sends_and_records_each_attempts_settings():
    sent = []

    def once(llms):
        sent.append(llms)
        return STATUS if len(sent) < 3 else PROFILE

    result = smu.extract_validated("profile", once, llms=QWEN)
    assert not result.failed
    assert [entry[0]["seed"] for entry in sent] == [100, 101, 102]
    assert [entry[0]["temperature"] for entry in sent] == [0.0, 0.3, 0.3]
    assert result.attempt_settings == [
        {"attempt": 0, "temperature": 0.0, "seed": 100},
        {"attempt": 1, "temperature": 0.3, "seed": 101},
        {"attempt": 2, "temperature": 0.3, "seed": 102},
    ]
    assert result.report()["writer_attempt_settings"] == \
        result.attempt_settings


def test_writer_agent_sends_the_attempts_decoding():
    sent = []
    answers = iter([STATUS, PROFILE])

    def chat(**kwargs):
        sent.append(kwargs["llms"])
        return {"response": {"response_message": json.dumps(next(answers))},
                "token_usage": None}

    agent = profile_module.ProfileAgent("profile_agent")
    agent.llms = QWEN
    with patch.object(profile_module, "llm_chat_with_json_output", chat):
        extraction = agent.extract("I'm Ana.")
    assert extraction.fields["user_name"] == "Ana Li"
    assert sent == [QWEN, smu.attempt_llms(QWEN, 1)]
    assert agent.llms == QWEN


def test_trials_record_writer_attempt_settings():
    settings = [{"attempt": 0, "temperature": 0.0, "seed": 100}]
    _, _, attempts = writer_report(
        {"agent_name": "profile_agent", "writer_retries": 0,
         "writer_attempt_settings": settings},
        {"agent_name": "task_agent"},
    )
    assert attempts == {"profile_agent": settings}
    trial = models.TrialResult.model_fields["writer_attempt_settings"]
    assert trial.default == {}


def test_judge_is_greedy_with_a_fixed_seed():
    judge = HybridJudge(llms=[{"name": "gpt-5.4", "backend": "azure"}])
    assert (JUDGE_TEMPERATURE, judge.temperature) == (0.0, 0.0)
    assert judge.seed == JUDGE_SEED
    assert judge.llm_judge.llms == [{"name": "gpt-5.4", "backend": "azure",
                                     "temperature": 0.0,
                                     "seed": JUDGE_SEED}]
    sampled = HybridJudge(llms=[{"name": "gpt-5.4"}], temperature=None,
                          seed=None)
    assert sampled.llm_judge.llms == [{"name": "gpt-5.4"}]
    assert HybridJudge().temperature is None  # no entry to carry it


def test_the_judge_call_carries_the_decoding():
    sent = []

    def chat(**kwargs):
        sent.append(kwargs["llms"])
        return {"response": {"response_message": json.dumps({
            "profile_usage_score": 5, "profile_usage_reasoning": "",
            "task_usage_score": 5, "task_usage_reasoning": "",
            "integration_score": 5, "integration_reasoning": "",
        })}}

    from benchmarks.shared_memory import judge as judge_module
    from tests.agents.test_judge_prompt_v2 import PROFILE as P, TASK as T

    judge = HybridJudge(llms=[{"name": "gpt-5.4", "backend": "azure"}])
    with patch.object(judge_module, "llm_chat_with_json_output", chat):
        judge.evaluate("q", "an answer", P, T)
    assert sent and all(
        entry[0]["temperature"] == 0.0 and entry[0]["seed"] == JUDGE_SEED
        for entry in sent
    )


def test_metadata_records_the_judge_decoding(tmp_path):
    from benchmarks.shared_memory.run_evaluation import EvaluationOrchestrator

    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        orch = EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path), write_csv=False,
            condition=None, method="kernel_shared",
            assistant_llms=[{"name": "qwen2.5:7b", "backend": "ollama"}],
            judge_llms=[{"name": "gpt-5.4", "backend": "azure"}],
        )
    assert (orch.judge.temperature, orch.judge.seed) == (0.0, JUDGE_SEED)
    meta = models.ExperimentMetadata(
        trials_per_condition=1, timestamp="t", kernel_url="u",
        conditions_run=["kernel_shared"],
    )
    experiment = models.ExperimentResults(
        experiment_metadata=meta, conditions=[],
    )
    out = rejudge_experiment(experiment, orch.judge, "src", "gpt-5.4:azure")
    m = out.experiment_metadata
    assert (m.judge_temperature, m.judge_seed) == (0.0, JUDGE_SEED)
    assert m.judge_prompt_version == 2
    assert m.rejudge["source_judge_temperature"] is None
