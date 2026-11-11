"""Provenance of conversation rows (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, Amendment 2, "Provenance of conversation rows").

The kernel AssistantAgent sends its probe id as
``LLMQuery.provenance_event``, which the kernel stamps on the
conversation turn it stores, as the replicated and native assistants
stamp the turns they store themselves. The kernel is mocked: at the
agent module's ``llm_chat``, or at the SDK's HTTP ``post``. The
replicated assistant's stamp is checked in ``_v2_replicated_checks.py``,
which ``test_v2_writers.py`` runs in a fresh interpreter (known issue
18).
"""
from unittest.mock import MagicMock, patch

from cerebrum.example.agents.assistant_agent import agent as assistant_module
from cerebrum.example.agents.native import agents as native
from cerebrum.example.agents.native import backends
from cerebrum.llm import apis
from cerebrum.utils import communication

USER = "ana_r1_t0__kernel_shared"
PROBE = "u0_p3_recall"
QUESTION = [{"role": "user", "content": "Where do I live?"}]
REPLY = {"response": {"response_message": "You live in Tallinn."}}
# The keyword arguments a v1 request passes to llm_chat.
V1_KWARGS = {"agent_name", "messages", "base_url", "llms", "user_id"}


def posted(call) -> dict:
    """The body of the kernel ``/query`` request in a mocked ``post``
    call."""
    _, endpoint, body = call.args
    assert endpoint == "/query" and body["query_type"] == "llm"
    return body


# -- the SDK -----------------------------------------------------------------


def test_llm_query_provenance_event_defaults_to_none():
    assert apis.LLMQuery(messages=QUESTION).provenance_event is None
    query = apis.LLMQuery(messages=QUESTION, provenance_event=PROBE)
    assert query.provenance_event == PROBE


def test_llm_chat_sends_the_provenance_event_when_given():
    with patch.object(communication, "post", return_value=REPLY) as post:
        apis.llm_chat("assistant_agent", QUESTION, user_id=USER,
                      session=7, provenance_event=PROBE)
    data = posted(post.call_args)["query_data"]
    assert data["provenance_event"] == PROBE
    assert (data["session"], data["user_id"]) == (7, USER)


def test_llm_chat_without_a_provenance_event_sends_none():
    """No provenance asked for, none sent: the kernel stamps nothing."""
    with patch.object(communication, "post", return_value=REPLY) as post:
        apis.llm_chat("assistant_agent", QUESTION, user_id=USER, session=7)
    data = posted(post.call_args)["query_data"]
    assert data.get("provenance_event") is None
    assert data["session"] == 7


def test_llm_chat_keeps_its_positional_parameters():
    """``provenance_event`` is the last parameter, so a positional call
    of the earlier signature means what it meant."""
    with patch.object(apis, "send_request", return_value=REPLY) as send:
        apis.llm_chat("assistant_agent", QUESTION, "http://kernel", None,
                      USER, 7)
    _, query, base_url = send.call_args.args
    assert base_url == "http://kernel"
    assert (query.user_id, query.session) == (USER, 7)
    assert query.provenance_event is None


# -- the kernel AssistantAgent ----------------------------------------------


def kernel_assistant(session=None, probe_id=None):
    agent = assistant_module.AssistantAgent("assistant_agent")
    agent.user_id = USER
    agent.session, agent.probe_id = session, probe_id
    return agent


def chat_kwargs(agent) -> dict:
    """The keyword arguments ``agent.run`` passes to a mocked
    ``llm_chat``."""
    chat = MagicMock(return_value=REPLY)
    with patch.object(assistant_module, "llm_chat", chat):
        result = agent.run("Where do I live?")
    assert result["result"] == "You live in Tallinn."
    return chat.call_args.kwargs


def test_kernel_assistant_sends_its_probe_id_as_provenance_event():
    kwargs = chat_kwargs(kernel_assistant(session=7, probe_id=PROBE))
    assert kwargs["provenance_event"] == PROBE
    assert (kwargs["session"], kwargs["user_id"]) == (7, USER)


def test_kernel_assistant_sends_a_probe_id_without_a_session():
    kwargs = chat_kwargs(kernel_assistant(probe_id=PROBE))
    assert kwargs["provenance_event"] == PROBE
    assert "session" not in kwargs


def test_kernel_assistant_without_a_probe_sends_no_provenance_event():
    kwargs = chat_kwargs(kernel_assistant(session=7))
    assert "provenance_event" not in kwargs and kwargs["session"] == 7
    # A v1 request (neither set) is sent as before.
    assert set(chat_kwargs(kernel_assistant())) == V1_KWARGS


def test_kernel_assistant_probe_id_reaches_the_kernel_request():
    """Through the real ``llm_chat``: the probe id is in the
    ``query_data`` the kernel's ``/query`` receives."""
    agent = kernel_assistant(session=7, probe_id=PROBE)
    with patch.object(communication, "post", return_value=REPLY) as post:
        result = agent.run("Where do I live?")
    assert result["result"] == "You live in Tallinn."
    data = posted(post.call_args)["query_data"]
    assert (data["provenance_event"], data["session"]) == (PROBE, 7)
    assert data["user_id"] == USER


# -- the native assistant stamps its own turn, as before ----------------------

EMBEDDING = {"provider": "ollama", "model": "nomic-embed-text",
             "dimension": 8, "ollama_base_url": "http://localhost:11434"}


class OneRowMemory:
    """A native in-house memory holding one row; records the writes."""

    backend = "inhouse"
    backend_extraction = False

    def __init__(self):
        self.settings = backends.NativeSettings(
            embedding=EMBEDDING, backend_llm={}, k=10)
        self.writes = []

    def search(self, query, user_id, k, agent_name=None):
        return [{"memory_id": "a", "content": "I live in Tallinn.",
                 "score": 0.5,
                 "metadata": {"user_id": user_id,
                              "owner_agent": "profile_agent",
                              "sharing_policy": "shared",
                              "memory_type": "profile",
                              "fact_key": "home_city", "session": 1,
                              "provenance_event": "e1"}}]

    def write(self, messages, text, agent_name, metadata):
        self.writes.append(dict(metadata))
        return [f"w{len(self.writes)}"]


def test_native_assistant_still_stamps_its_probe_on_its_own_row():
    memory = OneRowMemory()
    agent = native.NativeAssistantAgent("assistant_agent", memory)
    agent.user_id = USER
    agent.session, agent.probe_id = 7, PROBE
    chat = MagicMock(return_value=REPLY)
    with patch.object(native, "llm_chat", chat):
        agent.run("Where do I live?")
    (metadata,) = memory.writes
    assert metadata["provenance_event"] == PROBE
    assert metadata["session"] == 7
    assert metadata["memory_type"] == "conversation"
    # It stores its turn itself, so its kernel request is as before.
    assert set(chat.call_args.kwargs) == V1_KWARGS
