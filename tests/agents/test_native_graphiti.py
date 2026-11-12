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
from datetime import datetime, timedelta, timezone

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


def make_memory(monkeypatch, split=False, llm=None):
    runner = clients.GraphitiRunner()
    graphiti = clients.build_graphiti(
        runner, {}, EMBEDDING, llm=llm or scripted_llm(split=split))
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


def test_a_writer_without_sharing_fields_lists_its_own_rows(memory):
    """A V3 writer (Subtask 10) omits ``owner_agent`` and
    ``sharing_policy``; its rows still carry ``agent_id``, the writer, as
    a native Mem0 or in-house row does, and it lists them by that, so its
    stored rows are counted and its revokes find them. Another agent's
    row is not listed."""
    user = new_user(memory)
    bare = {k: v for k, v in meta(user, "task_agent").items()
            if k not in ("owner_agent", "sharing_policy")}
    text = "Our tracker is Linear."
    mine = memory.write([{"role": "user", "content": text}], text,
                        "task_agent", bare)
    write(memory, user, "I live in Utrecht.")
    rows = memory.list_own(user, "task_agent")
    assert mine and [r["memory_id"] for r in rows] == mine
    assert "owner_agent" not in rows[0]["metadata"]
    assert [r["memory_id"] for r in memory.list_own(user, "calendar_agent")
            ] == []


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


def test_a_search_leaves_the_recipe_ingestion_reads(memory):
    """``search()`` writes ``num_results`` into the shared
    ``EDGE_HYBRID_SEARCH_RRF``, which Graphiti's edge resolution also
    reads (``edge_operations.py:532, :564``). A V4 consumer searches with
    k 5: the recipe must be as it was after, so the next writes, its own
    and the next user's, are ingested as everyone else's."""
    from graphiti_core.search.search_config_recipes import (
        EDGE_HYBRID_SEARCH_RRF,
    )

    user = new_user(memory)
    write(memory, user, "My chat tool is Mattermost.")
    before = EDGE_HYBRID_SEARCH_RRF.limit
    memory.search("chat tool", user, 5, agent_name="assistant_agent")
    assert EDGE_HYBRID_SEARCH_RRF.limit == before


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


def test_a_write_is_dated_now_in_utc(memory, monkeypatch):
    """A writer's episode has ``reference_time=<now, UTC>``, a
    timezone-aware time (docs/NATIVE_USAGE.md, "native_graphiti",
    "Writers"). Graphiti dates the episode, and the facts it extracts,
    from it; a naive local time would be compared with Graphiti's own
    UTC times."""
    sent = []
    add_episode = memory.graphiti.add_episode

    async def spy(**kwargs):
        sent.append(kwargs)
        return await add_episode(**kwargs)

    monkeypatch.setattr(memory.graphiti, "add_episode", spy)
    user = new_user(memory)
    before = datetime.now(timezone.utc)
    write(memory, user, "I live in Utrecht.")
    after = datetime.now(timezone.utc)
    (call,) = sent
    moment = call["reference_time"]
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)
    assert before <= moment <= after


# Each fact's valid_at (the scripted LLM dates none by itself), and the
# order the test's search() returns them in: neither by date nor against
# it, so a sort by date in either direction would move them.
DATED = {
    "My chat tool is Mattermost.": "2026-03-01T00:00:00Z",
    "My calendar is Outlook.": "2026-06-01T00:00:00Z",
    "My notes app is Obsidian.": "2026-01-01T00:00:00Z",
}
SEARCH_ORDER = ["My chat tool is Mattermost.", "My calendar is Outlook.",
                "My notes app is Obsidian."]


def dated_llm(dates):
    """The scripted LLM, giving each fact it extracts its ``valid_at``
    from ``dates`` (by the fact's text)."""
    llm = scripted_llm()
    extract = llm._generate_response

    async def dated(messages, response_model=None, *args, **kwargs):
        reply = await extract(messages, response_model, *args, **kwargs)
        if getattr(response_model, "__name__", "") == "ExtractedEdges":
            for edge in reply["edges"]:
                edge["valid_at"] = dates.get(edge["fact"])
        return reply

    llm._generate_response = dated
    return llm


def test_search_keeps_graphitis_order_for_dated_facts(monkeypatch):
    """Facts are used in the order ``search()`` returns them
    (docs/NATIVE_USAGE.md, "native_graphiti", "Order and scores", and
    "Evidence: native Graphiti's search as returned", which says the
    order is pinned by tests), also when Graphiti has dated them: here
    ``search()`` returns them in an order that is not their dates', and
    the rows keep it. Without dates (the other tests) a reorder by date
    would go unseen."""
    memory = make_memory(monkeypatch, llm=dated_llm(DATED))
    try:
        user = new_user(memory)
        for text in DATED:
            write(memory, user, text)
        search = memory.graphiti.search

        async def in_order(*args, **kwargs):
            edges = await search(*args, **kwargs)
            assert sorted(e.fact for e in edges) == sorted(DATED)
            return sorted(edges, key=lambda e: SEARCH_ORDER.index(e.fact))

        monkeypatch.setattr(memory.graphiti, "search", in_order)
        rows = memory.search("my tools", user, 10,
                             agent_name="assistant_agent")
        assert [r["content"] for r in rows] == SEARCH_ORDER
        assert [r["metadata"]["graphiti_valid_at"][:10] for r in rows] == [
            DATED[text][:10] for text in SEARCH_ORDER]
    finally:
        close(memory)


def test_a_fact_takes_the_first_episode_the_agent_may_see(memory):
    """A fact several writes claim gets the metadata of the first of its
    episodes the searching agent may see (``NativeMemory._graphiti_search``;
    docs/NATIVE_USAGE.md, "native_graphiti", "Sharing"): here another
    agent's private write, then two shared ones; the row carries the
    first shared write's owner, session and event, which the block's
    session age and the probes' provenance read."""
    user = new_user(memory)
    text = "My chat tool is Mattermost."
    write(memory, user, text, owner="task_agent", policy="private",
          session=0, provenance_event="u0-e00")
    write(memory, user, text, session=1, provenance_event="u0-e01")
    write(memory, user, text, owner="calendar_agent", session=2,
          provenance_event="u0-e02")
    rows = memory.search(text, user, 10, agent_name="assistant_agent")
    (row,) = [r for r in rows if r["content"] == text]
    metadata = row["metadata"]
    assert metadata["graphiti_episode_count"] == 3
    assert (metadata["owner_agent"], metadata["session"],
            metadata["provenance_event"]) == ("profile_agent", 1, "u0-e01")


def test_the_assistant_sees_a_fact_through_its_shared_episode(memory,
                                                               monkeypatch):
    """The AssistantAgent's own search applies the sharing convention per
    fact through its episodes (docs/NATIVE_USAGE.md, "native_graphiti",
    "Sharing"): it passes its name, so a fact Graphiti merged from another
    agent's private write and a shared one reaches its block through the
    shared one. Searching without the name would give the fact its first
    episode, the private one, which the convention then hides."""
    user = new_user(memory)
    text = "My chat tool is Mattermost."
    write(memory, user, text, owner="task_agent", policy="private")
    write(memory, user, text)
    monkeypatch.setattr(native, "llm_chat", lambda **kwargs: {
        "response": {"response_message": "Noted."}})
    assistant = native.NativeAssistantAgent("assistant_agent", memory)
    assistant.user_id = user
    assistant.store_conversation = False
    result = assistant.run("Which chat tool do I use?")
    injected = {m["content"]: m
                for m in result["injection_diagnostics"]["injected_memories"]}
    assert text in injected
    assert injected[text]["owner_agent"] == "profile_agent"
    assert injected[text]["sharing_policy"] == "shared"
    assert text in result["injection_diagnostics"]["block_text"]
