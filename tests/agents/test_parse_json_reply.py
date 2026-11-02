"""A fenced JSON reply parses at every harness and agent call site."""

import json
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import synth
from cerebrum.example.agents.profile_agent import agent as profile
from cerebrum.example.agents.task_agent import agent as task
from cerebrum.llm.apis import parse_json_reply

PROFILE = {
    "user_name": "Ana",
    "preferred_tools": ["Git"],
    "preferred_language": "Python",
    "response_style": "concise",
}
TASK = {
    "current_project": "audit",
    "active_experiment": "pilot",
    "goals": ["finish"],
    "blockers": ["none"],
    "next_steps": ["review"],
}


def fenced(data, label="json"):
    return f"```{label}\n{json.dumps(data)}\n```"


def reply(content):
    return {"response": {"response_message": content}}


@pytest.mark.parametrize("raw", [
    json.dumps(PROFILE),
    fenced(PROFILE),
    fenced(PROFILE, ""),
    f"  {fenced(PROFILE)}\n",
    f"```json{json.dumps(PROFILE)}```",
    PROFILE,
])
def test_parse_json_reply(raw):
    assert parse_json_reply(raw) == PROFILE


def test_parse_json_reply_still_rejects_prose():
    with pytest.raises(json.JSONDecodeError):
        parse_json_reply("Sorry, I cannot do that.")


def test_generator_accepts_fenced_profile():
    with patch.object(
        synth, "llm_chat_with_json_output", return_value=reply(fenced(PROFILE)),
    ):
        generator = synth.SyntheticDataGenerator(llms=[{"name": "m"}])
        assert generator.generate_profile(0).user_name == "Ana"


def test_generator_accepts_fenced_task_context():
    with patch.object(
        synth, "llm_chat_with_json_output", return_value=reply(fenced(TASK)),
    ):
        generator = synth.SyntheticDataGenerator(llms=[{"name": "m"}])
        context = generator.generate_task_context(
            0, synth.SyntheticProfile(**PROFILE),
        )
        assert context.current_project == "audit"


@pytest.mark.parametrize("module, name, method, expected", [
    (profile, "ProfileAgent", "_extract_profile", PROFILE),
    (task, "TaskAgent", "_extract_task_context", TASK),
])
def test_agents_accept_fenced_reply(module, name, method, expected):
    agent = getattr(module, name)("agent")
    with patch.object(
        module,
        "llm_chat_with_json_output",
        return_value=reply(fenced(expected)),
    ):
        assert getattr(agent, method)("input") == expected
