"""native_amem's memory calls (NeurIPS Subtask 17; AIOS
docs/NATIVE_USAGE.md, "native_amem"), with A-MEM's own code on the
pinned embedder and a scripted LLM (``_amem_script.py``): a write is one
note with the agent's metadata in its ``category``; the agents of a
process share a user's store; the assistant's search is A-MEM's
``search`` (the README's first example), in its order with its distance
as the score; a writer lists its own notes by ``agent_id`` and revokes
with ``delete``."""
import json
import socket
import uuid

import pytest

from cerebrum.example.agents.native import agents as native
from cerebrum.example.agents.native import backends
from cerebrum.utils import amem
from tests.agents._amem_script import ScriptedLLM, needs_amem

EMBEDDING = {"provider": "ollama", "model": "nomic-embed-text",
             "dimension": 768, "ollama_base_url": "http://localhost:11434"}


def ollama_ready() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [needs_amem, pytest.mark.skipif(
    not ollama_ready(), reason="needs the local Ollama")]


@pytest.fixture
def stores(monkeypatch):
    stores = amem.Stores(ScriptedLLM(), amem.embedding_function(EMBEDDING),
                         uuid.uuid4().hex[:8])
    monkeypatch.setattr(backends, "amem_stores", lambda settings: stores)
    return stores


def handle():
    return native.NativeMemory("amem", backends.NativeSettings(
        embedding=EMBEDDING, backend_llm={}, k=10))


def meta(user, owner, policy="shared", memory_type="profile", **extra):
    return {"owner_agent": owner, "user_id": user,
            "memory_type": memory_type, "sharing_policy": policy,
            "created_at": "2026-11-12T00:00:00+00:00", "agent_id": owner,
            **extra}


def write(memory, user, text, owner="profile_agent", **kwargs):
    return memory.write([{"role": "user", "content": text}], text, owner,
                        meta(user, owner, **kwargs))


def new_user():
    return f"na_{uuid.uuid4().hex[:8]}@users.example"


def test_a_write_is_one_note_with_the_agents_metadata(stores):
    user = new_user()
    memory = handle()
    (note_id,) = write(memory, user, "My team's chat tool is Slack.",
                       fact_key="team_chat", provenance_event="u0-e01")
    note = stores.store(user).read(note_id)
    assert note.content == "My team's chat tool is Slack."
    assert json.loads(note.category) == meta(
        user, "profile_agent", fact_key="team_chat",
        provenance_event="u0-e01")
    assert note.context.startswith("About:")  # A-MEM's own analysis
    assert memory.backend_extraction is True


def test_the_agents_of_a_process_share_a_users_store(stores):
    user = new_user()
    writer, assistant = handle(), handle()
    (note_id,) = write(writer, user, "I live in Utrecht.")
    rows = assistant.search("Where do I live?", user, 10, "assistant_agent")
    assert [r["memory_id"] for r in rows] == [note_id]
    assert search_isolated(assistant, new_user()) == []


def search_isolated(memory, user):
    return memory.search("anything", user, 10, "assistant_agent")


def test_search_is_amems_search_in_its_order_and_score(stores):
    user = new_user()
    memory = handle()
    for text in ("My team's chat tool is Slack.", "I live in Utrecht.",
                 "I bill 40 hours a week."):
        write(memory, user, text)
    rows = memory.search("Which chat tool?", user, 2, "assistant_agent")
    store = stores.store(user)
    raw = store.search("Which chat tool?", 2)
    assert [r["memory_id"] for r in rows] == [x["id"] for x in raw]
    assert [r["score"] for r in rows] == [x["score"] for x in raw]
    assert rows[0]["content"] == "My team's chat tool is Slack."
    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(type(store), "search_agentic", None)
        assert [r["memory_id"] for r in memory.search(
            "Which chat tool?", user, 2, "assistant_agent")] == [
            x["id"] for x in raw]
    assert all(r["metadata"]["owner_agent"] == "profile_agent" for r in rows)


def test_a_writer_lists_its_own_notes_by_agent_id(stores):
    """A V3 writer (Subtask 10) omits ``owner_agent``; its notes still
    carry ``agent_id`` and it lists them by that."""
    user = new_user()
    memory = handle()
    mine = write(memory, user, "I live in Utrecht.")
    write(memory, user, "Retro notes go in #retro.", owner="calendar_agent")
    bare = {k: v for k, v in meta(user, "task_agent").items()
            if k not in ("owner_agent", "sharing_policy")}
    v3 = memory.write([{"role": "user", "content": "I use Linear."}],
                      "I use Linear.", "task_agent", bare)
    assert [r["memory_id"] for r in memory.list_own(user, "profile_agent")
            ] == mine
    assert [r["memory_id"] for r in memory.list_own(user, "task_agent")
            ] == v3
    assert memory.list_own(new_user(), "profile_agent") == []


def test_a_revoke_deletes_the_writers_note(stores):
    user = new_user()
    memory = handle()
    (mine,) = write(memory, user, "My team's chat tool is Slack.")
    (theirs,) = write(memory, user, "Retro notes go in #retro.",
                      owner="calendar_agent")
    assert memory.delete(user, mine)
    store = stores.store(user)
    assert mine not in store.memories
    assert store.retriever.collection.get(ids=[mine])["ids"] == []
    assert theirs in store.memories
    assert not memory.delete(user, mine)
    assert not memory.delete(new_user(), theirs)
