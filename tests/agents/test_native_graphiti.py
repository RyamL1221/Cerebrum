"""native_graphiti's memory calls (NeurIPS Subtask 16; AIOS
docs/NATIVE_USAGE.md, "native_graphiti"), on the local Neo4j and the
pinned embedder with a scripted LLM (``_graphiti_script.py``): a write is
one ``user:`` message episode with the agent's metadata in its
``source_description``; rows are facts as one episode claims them; the
assistant's search keeps Graphiti's order and gives each fact the
metadata of an episode it may see; a revoke deletes the row's episode
with ``remove_episode``."""
import json
import socket
import uuid

import pytest

from cerebrum.example.agents.native import agents as native
from cerebrum.example.agents.native import backends
from cerebrum.example.agents.native.sharing import visible
from cerebrum.utils import graphiti as clients
from tests.agents._graphiti_script import drop_groups, needs_neo4j, scripted_llm

EMBEDDING = {"provider": "ollama", "model": "nomic-embed-text",
             "dimension": 768, "ollama_base_url": "http://localhost:11434"}


def ollama_ready() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [needs_neo4j, pytest.mark.skipif(
    not ollama_ready(), reason="needs the local Ollama")]


def make_memory(monkeypatch, split=False):
    runner = clients.GraphitiRunner()
    graphiti = clients.build_graphiti(runner, {}, EMBEDDING,
                                      llm=scripted_llm(split=split))
    monkeypatch.setattr(backends, "graphiti_client",
                        lambda settings: (runner, graphiti))
    memory = native.NativeMemory("graphiti", backends.NativeSettings(
        embedding=EMBEDDING, backend_llm={}, k=10))
    memory.test_users = []
    return memory


def close(memory):
    drop_groups(memory.runner, memory.graphiti,
                [backends.graphiti_group(u) for u in memory.test_users])
    memory.runner.run(memory.graphiti.close)
    memory.runner.close()


@pytest.fixture
def memory(monkeypatch):
    memory = make_memory(monkeypatch)
    yield memory
    close(memory)


@pytest.fixture
def splitting(monkeypatch):
    memory = make_memory(monkeypatch, split=True)
    yield memory
    close(memory)


def new_user(memory):
    user = f"ng_{uuid.uuid4().hex[:8]}@users.example"
    memory.test_users.append(user)
    return user


def meta(user, owner, policy="shared", memory_type="profile", **extra):
    return {"owner_agent": owner, "user_id": user,
            "memory_type": memory_type, "sharing_policy": policy,
            "created_at": "2026-11-11T00:00:00+00:00", "agent_id": owner,
            **extra}


def write(memory, user, text, owner="profile_agent", **kwargs):
    return memory.write([{"role": "user", "content": text}], text, owner,
                        meta(user, owner, **kwargs))


def episodes(memory, user):
    return memory.runner.run(
        memory.graphiti.nodes.episode.get_by_group_ids,
        [backends.graphiti_group(user)])


def test_a_write_is_one_user_message_with_the_agents_metadata(memory):
    user = new_user(memory)
    ids = write(memory, user, "My team's chat tool is Slack.",
                fact_key="team_chat", provenance_event="u0-e01")
    (episode,) = episodes(memory, user)
    assert episode.content == "user: My team's chat tool is Slack."
    assert episode.source.value == "message"
    assert json.loads(episode.source_description) == meta(
        user, "profile_agent", fact_key="team_chat",
        provenance_event="u0-e01")
    assert ids and all(i.split(":")[1] == episode.uuid for i in ids)
    turn = memory.write(
        [{"role": "user", "content": "Where is the retro?"},
         {"role": "assistant", "content": "In #retro."}],
        "", "assistant_agent",
        meta(user, "assistant_agent", "private", "conversation"))
    contents = {e.content for e in episodes(memory, user)}
    assert "user: Where is the retro?\nassistant: In #retro." in contents
    assert turn


def test_an_agent_lists_only_its_own_rows(memory):
    user = new_user(memory)
    mine = write(memory, user, "I live in Utrecht.")
    write(memory, user, "Retro notes go in #retro.", owner="calendar_agent")
    rows = memory.list_own(user, "profile_agent")
    assert [r["memory_id"] for r in rows] == mine
    assert rows[0]["content"] == "I live in Utrecht."
    assert rows[0]["metadata"]["owner_agent"] == "profile_agent"
    assert rows[0]["metadata"]["graphiti_episode_count"] == 1
    assert rows[0]["metadata"]["graphiti_invalid_at"] is None


def test_search_gives_each_fact_an_episode_the_agent_may_see(memory):
    """A fact merged from another agent's private write and a shared one
    is visible through the shared one; a fact only another agent's
    private write claims keeps that write's metadata, which the sharing
    convention hides."""
    user = new_user(memory)
    write(memory, user, "My chat tool is Mattermost.", owner="task_agent",
          policy="private")
    write(memory, user, "My chat tool is Mattermost.")
    write(memory, user, "I bill 40 hours a week.", owner="task_agent",
          policy="private")
    rows = memory.search("chat tool hours", user, 10,
                         agent_name="assistant_agent")
    by_text = {r["content"]: r for r in rows}
    merged = by_text["My chat tool is Mattermost."]
    assert merged["metadata"]["owner_agent"] == "profile_agent"
    assert merged["metadata"]["graphiti_episode_count"] == 2
    assert visible("assistant_agent", merged["metadata"])
    private = by_text["I bill 40 hours a week."]
    assert not visible("assistant_agent", private["metadata"])
    assert all(r["score"] is None for r in rows)
    plain = memory.runner.run(
        memory.graphiti.search, "chat tool hours",
        group_ids=[backends.graphiti_group(user)], num_results=10)
    assert [r["content"] for r in rows] == [e.fact for e in plain]


def test_a_revoke_deletes_the_rows_episode(splitting):
    """Deleting a row removes its episode with ``remove_episode``, and
    with it the episode's other facts; a row that went with an episode
    already removed reads as deleted; another user's row, or an unknown
    one, is not found."""
    user = new_user(splitting)
    first, second = write(splitting, user,
                          "I live in Utrecht. My chat tool is Slack.")
    kept = write(splitting, user, "I am a data engineer.")
    assert splitting.delete(user, first)
    assert splitting.delete(user, second)  # its episode is gone already
    rows = splitting.list_own(user, "profile_agent")
    assert [r["memory_id"] for r in rows] == kept
    other = new_user(splitting)
    assert not splitting.delete(other, kept[0])
    assert not splitting.delete(user, f"x:{uuid.uuid4()}")
    assert splitting.backend_extraction is True
