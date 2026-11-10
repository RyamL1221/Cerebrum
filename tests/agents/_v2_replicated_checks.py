"""Benchmark v2 in the replicated locus (AIOS docs/BENCHMARK_V2.md):
scripted sessions written through the kernel's library, revoke through
``MemoryPipeline.list_own`` and ``delete``, the calendar writer, session
ages in the assistant's block and its stamped conversation note, a
variant reaching a v2 write, and ``written`` holding the metadata each
row was stored with (Amendment 2, "Stored metadata").

Not collected by the suite: ``test_v2_writers.py`` runs this file in a
fresh interpreter, because the replicated agents import the kernel's
``aios`` package, which this checkout's ``aios/`` stub would shadow
(known issue 18).
"""
import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from cerebrum.example.agents.replicated import agents as replicated
from cerebrum.example.agents.replicated import library

pipeline_lib = library.load()

from aios.memory.providers import factory  # noqa: E402
from aios.memory.providers.in_house import InHouseProvider  # noqa: E402

from cerebrum.example.agents import variants  # noqa: E402
from cerebrum.example.agents.variants import apply_variant  # noqa: E402

USER = "ana_r1_t0__replicated_inhouse"


def config(recency_unit="session"):
    """The kernel's /memory/config, as the replicated agents read it."""
    return {
        "max_injected_memories": 10,
        "embedding": {"provider": "ollama", "model": "nomic-embed-text",
                      "dimension": 768,
                      "ollama_base_url": "http://localhost:11434"},
        "auto_inject": False, "auto_extract": False,
        "pipeline": {"relevance_threshold": 0.0,
                     "max_injected_memories": 10,
                     "max_memory_tokens": 2000,
                     "write_barrier": {"enabled": True, "timeout_ms": 2000},
                     "block_format": "compact", "block_recency": True,
                     "block_recency_unit": recency_unit},
        "pipeline_version": pipeline_lib.PIPELINE_VERSION,
    }


def event(event_id, kind, fact_key, value=None, utterance=None, **extra):
    """A dataset event (docs/BENCHMARK_V2.md, "File")."""
    return {"event_id": event_id, "type": kind, "slot": fact_key,
            "fact_key": fact_key, "value": value, "aliases": [],
            "old_value": None, "sharing": "private" if kind == "private"
            else "shared", "template": "", "paraphrased": False,
            "utterance": utterance or (f"I said {value}." if value else
                                       f"Please forget my {fact_key}."),
            **extra}


def payload(session, events):
    return json.dumps({"v2_session": {"session": session, "events": events}})


@pytest.fixture
def store():
    """One in-memory backend shared by every agent's provider client,
    and llm_chat mocked; yields (store, chat)."""
    backend = InHouseProvider()
    backend.initialize({})
    chat = MagicMock(return_value={
        "response": {"response_message": "You live in Tallinn."},
        "token_usage": {"prompt_tokens": 9, "completion_tokens": 1,
                        "total_tokens": 10},
        "llm_timing": {"llm_ms": 7.0, "schedule_wait_ms": 1.0},
    })
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            factory.ProviderFactory, "create",
            classmethod(lambda cls, kind, cfg: backend)))
        stack.enter_context(patch.object(replicated, "llm_chat", chat))
        yield backend, chat


def writer(cls, name, recency_unit="session", **attributes):
    agent = cls(name, replicated.ReplicatedMemory("inhouse",
                                                  config(recency_unit)))
    agent.user_id = USER
    agent.extra_metadata = {"provenance_agent": name,
                            "provenance_user": USER}
    for key, value in attributes.items():
        setattr(agent, key, value)
    return agent


def rows_of(backend, owner=None):
    found = backend.list(USER, 1000)
    return [c for c in found
            if owner is None or c.metadata.get("owner_agent") == owner]


def test_a_v2_session_writes_one_row_per_event_with_its_metadata(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    result = agent.run(payload(1, [
        event("e1", "add", "pet", "Mochi"),
        event("e2", "private", "interview", "Halcyon Robotics"),
    ]))
    assert result["writer_failed"] is False
    assert result["user_id"] == USER
    assert result["stored_rows"] == 2
    rows = {c.metadata["provenance_event"]: c for c in rows_of(backend)}
    assert set(rows) == {"e1", "e2"}
    pet = rows["e1"].metadata
    assert (pet["fact_key"], pet["event_type"], pet["session"]) == (
        "pet", "add", 1)
    assert pet["sharing_policy"] == "shared"
    assert pet["owner_agent"] == "profile_agent"
    assert json.loads(pet["structured"])["value"] == "Mochi"
    assert rows["e2"].metadata["sharing_policy"] == "private"
    assert result["events"][0]["memory_ids"] == [rows["e1"].memory_id]


def test_a_revoke_deletes_every_row_of_the_fact_and_only_its_own(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    agent.run(payload(1, [event("e1", "add", "pet", "Mochi"),
                          event("e2", "add", "city", "Tallinn")]))
    # A Mem0-style sibling of e1's write, and another writer's row of
    # the same slot (an echo), which this writer must not delete.
    first = rows_of(backend, "profile_agent")[0]
    sibling = pipeline_lib.note_from_request({
        "content": "User has a pet named Mochi.",
        "metadata": dict(first.metadata)})
    sibling_id = agent.memory.pipeline.write("profile_agent", USER, sibling)
    echo = writer(replicated.ReplicatedCalendarAgent, "calendar_agent")
    echo.run(payload(3, [event("e5", "add", "pet", "Mochi",
                               utterance="I booked a vet visit for Mochi.",
                               echo_of="e1")]))
    result = agent.run(payload(4, [event("e9", "revoke", "pet")]))
    record = result["events"][0]
    assert record["found_ids"] == record["deleted_ids"]
    assert sibling_id in record["deleted_ids"]
    assert len(record["deleted_ids"]) == 2
    left = {c.metadata["provenance_event"] for c in rows_of(backend)}
    assert left == {"e2", "e5"}
    # Listing after the revoke: nothing of the fact is left in its own rows.
    assert all(r["metadata"]["fact_key"] != "pet"
               for r in agent.list_own_rows())


def test_the_no_delete_control_finds_and_deletes_nothing(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedTaskAgent, "task_agent",
                   delete_on_revoke=False)
    agent.run(payload(2, [event("e1", "add", "client", "Initech")]))
    result = agent.run(payload(5, [event("e9", "revoke", "client")]))
    record = result["events"][0]
    assert len(record["found_ids"]) == 1
    assert record["deleted_ids"] == []
    assert len(rows_of(backend)) == 1


def test_the_calendar_writer_writes_calendar_rows(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedCalendarAgent, "calendar_agent")
    result = agent.run(payload(3, [event("e1", "add", "sync_room",
                                         "Juniper")]))
    assert result["writer_failed"] is False
    (row,) = rows_of(backend)
    assert row.metadata["memory_type"] == "calendar"
    assert row.metadata["owner_agent"] == "calendar_agent"
    # A non-v2 input fails the calendar writer instead of writing.
    assert agent.run('{"anything": 1}')["writer_failed"] is True


def test_the_assistant_prints_session_ages_and_stamps_its_turn(store):
    backend, chat = store
    profile = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    profile.run(payload(1, [event("e1", "add", "city", "Tallinn")]))
    calendar = writer(replicated.ReplicatedCalendarAgent, "calendar_agent")
    calendar.run(payload(6, [event("e7", "add", "sync_room", "Birch")]))
    assistant = replicated.ReplicatedAssistantAgent(
        "assistant_agent",
        replicated.ReplicatedMemory("inhouse", config("session")))
    assistant.user_id = USER
    assistant.extra_metadata = {"provenance_agent": "assistant_agent",
                                "provenance_user": USER}
    assistant.session, assistant.probe_id = 7, "p_recall"
    result = assistant.run("Which city do I live in?")
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert "(6 sessions ago)" in block
    assert "(1 session ago)" in block
    diagnostics = result["injection_diagnostics"]
    assert diagnostics["session"] == 7
    assert diagnostics["block_recency_unit"] == "session"
    entries = {e["provenance_event"]: e
               for e in diagnostics["injected_memories"]}
    assert entries["e1"]["content"]
    (turn,) = rows_of(backend, "assistant_agent")
    assert turn.metadata["session"] == 7
    assert turn.metadata["provenance_event"] == "p_recall"
    assert turn.metadata["memory_type"] == "conversation"
    # The next turn sees the earlier one as this session's.
    assistant.run("Which room is my sync in?")
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert "(this session)" in block
    listed = assistant.list_own_rows()
    assert len(listed) == 2
    assert {r["metadata"]["provenance_event"] for r in listed} == {
        "p_recall"}


def test_without_a_session_the_assistant_injects_as_in_v1(store):
    _, chat = store
    profile = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    profile.run(payload(1, [event("e1", "add", "city", "Tallinn")]))
    assistant = replicated.ReplicatedAssistantAgent(
        "assistant_agent",
        replicated.ReplicatedMemory("inhouse", config("time")))
    assistant.user_id = USER
    assistant.run("Which city do I live in?")
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert "Tallinn" in block
    assert "session ago" not in block and "sessions ago" not in block
    assert "(this session)" not in block


def test_v5_writes_the_events_structured_json(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    variant = variants.variant("V5")
    with apply_variant(variant, agent, "profile_agent", "replicated"):
        agent.run(payload(1, [event("e1", "add", "pet", "Mochi")]))
    (row,) = rows_of(backend)
    assert row.content == row.metadata["structured"]
    assert json.loads(row.content)["value"] == "Mochi"


def test_v3_rows_are_owned_private_and_deletable(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    variant = variants.variant("V3")
    with apply_variant(variant, agent, "profile_agent", "replicated"):
        agent.run(payload(1, [event("e1", "add", "pet", "Mochi")]))
    (row,) = rows_of(backend)
    # The library fills the owner and the private default back in.
    assert row.metadata["owner_agent"] == "profile_agent"
    assert row.metadata["sharing_policy"] == "private"
    result = agent.run(payload(4, [event("e9", "revoke", "pet")]))
    assert result["events"][0]["deleted_ids"] == [row.memory_id]
    assert rows_of(backend) == []


def test_v1_makes_a_shared_event_private(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedTaskAgent, "task_agent")
    variant = variants.variant("V1")
    with apply_variant(variant, agent, "task_agent", "replicated"):
        agent.run(payload(2, [event("e1", "add", "client", "Initech")]))
    (row,) = rows_of(backend)
    assert row.metadata["sharing_policy"] == "private"


# -- what a write records (Amendment 2, "Stored metadata") ------------------


def test_a_v3_write_is_recorded_as_stored_private_and_owned(store):
    """V3 sends a shared event's row without owner and policy, and the
    library stores it owned by the writer and private. ``written`` says
    so; it said shared (review storage-1 / trial-05), which counted the
    writer as lost instead of withheld."""
    backend, _ = store
    agent = writer(replicated.ReplicatedTaskAgent, "task_agent")
    with apply_variant(variants.variant("V3"), agent, "task_agent",
                       "replicated"):
        result = agent.run(payload(2, [
            event("e1", "add", "client", "Initech")]))
    (row,) = rows_of(backend)
    (written,) = result["written"]
    assert written["sharing_policy"] == "private"
    assert row.metadata["sharing_policy"] == "private"
    assert written["owner_agent"] == row.metadata["owner_agent"]
    assert written["owner_agent"] == "task_agent"
    assert written["provenance_event"] == "e1"


@pytest.mark.parametrize("code", [None, "V1", "V3", "V5"])
def test_written_is_the_metadata_each_row_was_stored_with(store, code):
    """Every key ``written`` records has the stored row's value (the
    store adds the note's own fields), with or without a variant."""
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    variant = variants.variant(code) if code else None
    with apply_variant(variant, agent, "profile_agent", "replicated"):
        result = agent.run(payload(1, [
            event("e1", "add", "pet", "Mochi"),
            event("e2", "private", "interview", "Halcyon Robotics"),
        ]))
    stored = {c.metadata["provenance_event"]: c.metadata
              for c in rows_of(backend)}
    assert [w["provenance_event"] for w in result["written"]] == [
        "e1", "e2"]
    for written in result["written"]:
        row = stored[written["provenance_event"]]
        assert {key: row.get(key) for key in written} == written
        assert written["created_at"]  # the library's, as stored


def test_a_write_the_store_refuses_is_not_recorded(store):
    """A write that raised stored nothing, so ``written`` is empty (it
    held the row's metadata, recorded before the write)."""
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    with patch.object(backend, "add",
                      side_effect=RuntimeError("store down")):
        result = agent.run(payload(1, [event("e1", "add", "pet", "Mochi")]))
    assert result["writer_failed"] is True
    assert "store down" in result["error"]
    assert result["written"] == []
    assert rows_of(backend) == []


def test_a_replicated_probe_turn_writes_nothing(store):
    """Amendment 3: on a probe turn (``store_conversation`` False) the
    replicated assistant writes no note; a stored turn writes one."""
    backend, chat = store
    profile = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    profile.run(payload(1, [event("e1", "add", "city", "Tallinn")]))
    assistant = replicated.ReplicatedAssistantAgent(
        "assistant_agent",
        replicated.ReplicatedMemory("inhouse", config("session")))
    assistant.user_id = USER
    assistant.session, assistant.probe_id = 7, "p_recall"
    assistant.store_conversation = False
    result = assistant.run("Which city do I live in?")
    assert result["result"] == "You live in Tallinn."
    assert rows_of(backend, "assistant_agent") == []
    assert len(rows_of(backend)) == 1  # the writer's row only
    assistant.store_conversation = True
    assistant.run("Which city do I live in?")
    assert len(rows_of(backend, "assistant_agent")) == 1


def test_the_assistant_stamps_its_probe_on_its_turn_as_before(store):
    """The replicated assistant writes its turn itself, stamped with
    the probe id; its kernel request carries no session and no
    ``provenance_event`` (only the kernel assistant sends them)."""
    backend, chat = store
    profile = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    profile.run(payload(1, [event("e1", "add", "city", "Tallinn")]))
    assistant = replicated.ReplicatedAssistantAgent(
        "assistant_agent",
        replicated.ReplicatedMemory("inhouse", config("session")))
    assistant.user_id = USER
    assistant.session, assistant.probe_id = 7, "p_privacy"
    assistant.run("Which city do I live in?")
    (turn,) = rows_of(backend, "assistant_agent")
    assert turn.metadata["provenance_event"] == "p_privacy"
    assert turn.metadata["session"] == 7
    assert set(chat.call_args.kwargs) == {
        "agent_name", "messages", "base_url", "llms", "user_id"}
