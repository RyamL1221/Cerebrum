"""Benchmark v2 in the replicated locus (AIOS docs/BENCHMARK_V2.md):
scripted sessions written through the kernel's library, revoke through
``MemoryPipeline.list_own`` and ``delete``, the calendar writer, session
ages in the assistant's block and its stamped conversation note, a
variant reaching a v2 write, and ``written`` holding the metadata each
row was stored with (Amendment 2, "Stored metadata").

Amendment 4 (AIOS docs/DELETION_AND_SUPERSESSION.md): a revoke through
the library's ``MemoryPipeline.forget`` (the user's), the store's
tombstone file shared by its agents, a variant's pipeline keeping the
tombstones and the usage tag, a write's outcome in its record, and the
harness's audit of the raw store, through the real locus.

Every check keeps the store's root (its tombstone file) in a temporary
directory, so no tombstone persists in the checkout's
``.replicated_memory``, where it would sweep the next run's writes.

Not collected by the suite: ``test_v2_writers.py`` runs this file in a
fresh interpreter, because the replicated agents import the kernel's
``aios`` package, which this checkout's ``aios/`` stub would shadow
(known issue 18).
"""
import json
import os
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from cerebrum.example.agents.replicated import agents as replicated
from cerebrum.example.agents.replicated import library

pipeline_lib = library.load()

from aios.memory.providers import factory  # noqa: E402
from aios.memory.providers.in_house import InHouseProvider  # noqa: E402

from cerebrum.example.agents import shared_memory_utils as smu  # noqa: E402
from cerebrum.example.agents import variants  # noqa: E402
from cerebrum.example.agents.variants import apply_variant  # noqa: E402
from cerebrum.utils import usage  # noqa: E402

USER = "ana_r1_t0__replicated_inhouse"


def config(recency_unit="session", supersession="off"):
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
                     "block_recency_unit": recency_unit,
                     "supersession": supersession},
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
def store(tmp_path, monkeypatch):
    """One in-memory backend shared by every agent's provider client,
    the store's root (and so its tombstone file) in a temporary
    directory, and llm_chat mocked; yields (store, chat)."""
    monkeypatch.setattr(replicated, "STORE_ROOT",
                        str(tmp_path / "replicated_memory"))
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


def writer(cls, name, recency_unit="session", supersession="off",
           **attributes):
    agent = cls(name, replicated.ReplicatedMemory(
        "inhouse", config(recency_unit, supersession)))
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
    """Under writer_scoped (``forget_scope`` "writer") a revoke is the
    owner's list and delete, as in Subtask 14: another writer's echo
    survives."""
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent",
                   forget_scope="writer")
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
    assert record["revoke_path"] == "owner"
    assert record["found_ids"] == record["deleted_ids"]
    assert sibling_id in record["deleted_ids"]
    assert len(record["deleted_ids"]) == 2
    left = {c.metadata["provenance_event"] for c in rows_of(backend)}
    assert left == {"e2", "e5"}
    # Listing after the revoke: nothing of the fact is left in its own rows.
    assert all(r["metadata"]["fact_key"] != "pet"
               for r in agent.list_own_rows())
    # No forget ran: no tombstone, no guard.
    assert agent.memory.pipeline.tombstoned_forms(USER) == []


def test_the_no_delete_control_finds_and_deletes_nothing(store):
    backend, _ = store
    agent = writer(replicated.ReplicatedTaskAgent, "task_agent",
                   delete_on_revoke=False)
    agent.run(payload(2, [event("e1", "add", "client", "Initech")]))
    result = agent.run(payload(5, [event("e9", "revoke", "client")]))
    record = result["events"][0]
    assert record["revoke_path"] == "owner"
    assert len(record["found_ids"]) == 1
    assert record["deleted_ids"] == []
    assert len(rows_of(backend)) == 1
    assert agent.memory.pipeline.tombstoned_forms(USER) == []


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


@pytest.mark.parametrize("scope", ["writer", "user"])
def test_v3_rows_are_owned_private_and_deletable(store, scope):
    """The library fills a V3 row's owner and policy back in, so its
    writer's own revoke (writer_scoped) finds and deletes it; the
    user's forget deletes it too."""
    backend, _ = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent",
                   forget_scope=scope)
    variant = variants.variant("V3")
    with apply_variant(variant, agent, "profile_agent", "replicated"):
        agent.run(payload(1, [event("e1", "add", "pet", "Mochi")]))
    (row,) = rows_of(backend)
    # The library fills the owner and the private default back in.
    assert row.metadata["owner_agent"] == "profile_agent"
    assert row.metadata["sharing_policy"] == "private"
    result = agent.run(payload(4, [event("e9", "revoke", "pet")]))
    assert result["events"][0]["revoke_path"] == (
        "owner" if scope == "writer" else "forget")
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


# -- Amendment 4: the user's forget, tombstones, a write's outcome ----------


def planted_note(text, owner="task_agent"):
    """A shared row of ``owner`` for the provider's own ``add``: it
    skips the library's sweep, as a carrier the forget missed would."""
    return pipeline_lib.note_from_request({"content": text, "metadata": {
        "user_id": USER, "owner_agent": owner,
        "memory_type": "task_context", "sharing_policy": "shared",
        "provenance_event": "planted", "fact_key": "planted"}})


def probe_assistant(**options):
    """The assistant as a probe turn runs it: session 7, writes
    nothing."""
    assistant = replicated.ReplicatedAssistantAgent(
        "assistant_agent",
        replicated.ReplicatedMemory("inhouse", config("session", **options)))
    assistant.user_id = USER
    assistant.session, assistant.probe_id = 7, "p_deletion"
    assistant.store_conversation = False
    return assistant


def test_the_users_forget_deletes_another_writers_echo(store):
    """The converse of the owner-only check above: through the
    library's forget (``forget_scope`` "user", the default) the profile
    writer's revoke deletes the fact's row, its sibling and the
    calendar writer's echo of the value (by value). The tombstone is in
    the store's file, which every agent of the store reads through its
    own memory: the assistant drops a carrier planted after the forget
    from its block and reports the drop."""
    backend, chat = store
    agent = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    agent.run(payload(1, [event("e1", "add", "pet", "Mochi"),
                          event("e2", "add", "city", "Tallinn")]))
    first = rows_of(backend, "profile_agent")[0]
    sibling = pipeline_lib.note_from_request({
        "content": "User has a pet named Mochi.",
        "metadata": dict(first.metadata)})
    sibling_id = agent.memory.pipeline.write("profile_agent", USER, sibling)
    echo = writer(replicated.ReplicatedCalendarAgent, "calendar_agent")
    echo.run(payload(3, [event("e5", "add", "pet_vet_visit", "Mochi",
                               utterance="I booked a vet visit for Mochi.",
                               echo_of="e1")]))
    (echo_row,) = rows_of(backend, "calendar_agent")
    result = agent.run(payload(4, [event("e9", "revoke", "pet")]))
    [record] = result["events"]
    assert record["revoke_path"] == "forget"
    assert record["found_ids"] == [first.memory_id, sibling_id]
    assert record["deleted_ids"] == [first.memory_id, sibling_id,
                                     echo_row.memory_id]
    reasons = {d["memory_id"]: (d["owner_agent"], d["reason"])
               for d in record["forget"]["deleted"]}
    assert reasons[echo_row.memory_id] == ("calendar_agent", "value")
    assert record["forget"]["values_count"] == 1
    assert {c.metadata["provenance_event"] for c in rows_of(backend)} == {
        "e2"}
    planted = backend.add(planted_note("Mochi's vet visit moved to Friday."))
    assistant = probe_assistant()
    diagnostics = assistant.run("What is my pet called?")[
        "injection_diagnostics"]
    assert diagnostics["tombstoned_rows"] == [planted]
    assert diagnostics["tombstoned_forms"] == 1
    block = chat.call_args.kwargs["messages"][0]["content"]
    assert "Tallinn" in block and "Mochi" not in block
    # Shared through the file, not one object.
    assert assistant.memory.tombstones is not agent.memory.tombstones
    assert assistant.memory.tombstones_path == agent.memory.tombstones_path


def test_a_variants_pipeline_keeps_the_tombstones_and_the_usage_tag(store):
    """A variant with retrieval settings (V4) gives the agent a new
    ``MemoryPipeline`` (``_replicated_pipeline``). It keeps the store's
    tombstones, so a forget made through it is the store's and its
    guard holds the store's, and the usage tag, so the provider's calls
    count to the user. A fresh tombstone store would leave both
    blind."""
    backend, _ = store
    profile = writer(replicated.ReplicatedProfileAgent, "profile_agent")
    original = profile.memory.pipeline
    with apply_variant(variants.variant("V4"), profile, "profile_agent",
                       "replicated"):
        tuned = profile.memory.pipeline
        assert tuned is not original
        assert tuned.settings.max_injected_memories == 5
        assert tuned.tombstones is original.tombstones
        assert tuned.usage_tag is usage.tagged
        result = profile.run(payload(1, [
            event("e1", "add", "pet", "Mochi"),
            event("e2", "add", "city", "Tallinn"),
            event("e9", "revoke", "pet")]))
    assert result["events"][2]["revoke_path"] == "forget"
    assert profile.memory.pipeline is original
    assert original.tombstoned_forms(USER) == ["Mochi"]
    planted = backend.add(planted_note("Mochi's vet visit moved to Friday."))
    assistant = probe_assistant()
    with apply_variant(variants.variant("V4"), assistant, "assistant_agent",
                       "replicated"):
        assert assistant.memory.pipeline.usage_tag is usage.tagged
        diagnostics = assistant.run("What is my pet called?")[
            "injection_diagnostics"]
    assert diagnostics["tombstoned_rows"] == [planted]


def test_a_write_reports_what_it_retired_swept_and_lifted(store):
    """``_v2_create`` returns the kernel's reply shape, ``{memory_id,
    metadata}``, the metadata being the library's outcome, and the
    session records it (Amendment 4). With supersession ``exclude`` a
    contradiction by another writer retires the earlier row of its
    slot; after the user's forget another writer's re-write of the
    value is swept and suppressed (no id); the user's restatement lifts
    the tombstone and is kept."""
    backend, _ = store
    profile = writer(replicated.ReplicatedProfileAgent, "profile_agent",
                     supersession="exclude")
    task = writer(replicated.ReplicatedTaskAgent, "task_agent",
                  supersession="exclude")
    metadata = smu.v2_write_metadata(
        profile, "profile", 1, event("e1", "add", "home_city", "Tallinn"))
    reply = profile._v2_create("I live in Tallinn.", metadata)
    assert set(reply) == {"memory_id", "metadata"}
    assert set(reply["metadata"]) >= {"swept", "retired", "lifted",
                                      "suppressed"}
    assert (reply["metadata"]["retired"],
            reply["metadata"]["suppressed"]) == ([], False)
    original = reply["memory_id"]
    [contradicted] = task.run(payload(2, [
        event("e2", "contradict", "home_city", "Ljubljana",
              target_event="e1")]))["events"]
    assert contradicted["retired_ids"] == [original]
    assert (contradicted["swept_ids"], contradicted["lifted"],
            contradicted["suppressed"]) == ([], [], False)
    marks = {c.memory_id: c.metadata.get("superseded_by")
             for c in rows_of(backend)}
    assert marks[original] == "e2"
    profile.run(payload(3, [event("e3", "add", "pet", "Mochi"),
                            event("e9", "revoke", "pet")]))
    [echo] = task.run(payload(4, [
        event("e4", "add", "pet_vet_visit", "Mochi",
              utterance="I booked a vet visit for Mochi.",
              echo_of="e3")]))["events"]
    assert echo["suppressed"] is True
    assert echo["memory_ids"] == [] and echo["stored_rows"] == 0
    [swept] = echo["swept_ids"]
    assert swept not in {c.memory_id for c in rows_of(backend)}
    [restated] = profile.run(payload(5, [
        event("e5", "add", "pet", "Mochi")]))["events"]
    assert restated["lifted"] == ["Mochi"]
    assert restated["suppressed"] is False and restated["swept_ids"] == []
    assert len(restated["memory_ids"]) == 1
    assert profile.memory.pipeline.tombstoned_forms(USER) == []


def test_the_replicated_memory_tags_usage_and_keeps_tombstones_in_its_store(
        store, tmp_path):
    """``ReplicatedMemory`` passes the SDK's usage tag to its pipeline
    (the library imports no cerebrum module, so the caller passes it),
    and keeps the store's tombstones in ``<store root>/
    tombstones.sqlite``, or the ``tombstones_path`` it is given: two
    memories of one store share them through the file."""
    memory = replicated.ReplicatedMemory("inhouse", config())
    assert memory.pipeline.usage_tag is usage.tagged
    root = replicated.store_root("inhouse")
    assert root.startswith(str(tmp_path))
    assert memory.tombstones_path == os.path.join(root, "tombstones.sqlite")
    assert memory.pipeline.tombstones is memory.tombstones
    other = replicated.ReplicatedMemory("inhouse", config())
    memory.tombstones.record(USER, "pet", [("Mochi", ["Mo"])], ["e1"],
                             requested_by="profile_agent")
    assert other.pipeline.tombstoned_forms(USER) == ["Mochi", "Mo"]
    given = str(tmp_path / "elsewhere" / "tombstones.sqlite")
    third = replicated.ReplicatedMemory("inhouse", config(),
                                        tombstones_path=given)
    assert third.tombstones_path == given
    assert third.pipeline.tombstoned_forms(USER) == []


# -- Amendment 4: the harness's audit reads the raw store --------------------


def v2_user(index=0):
    """Dataset user ``index`` (pilot data built from users_v1) under
    USER."""
    from benchmarks.shared_memory import dataset, synth_v2
    from benchmarks.shared_memory.models import V2UserData

    record = synth_v2.build_user(index, dataset.load("users_v1").users[index])
    return V2UserData(
        index=index, user_id=USER,
        profile=record["final"]["profile"],
        task_context=record["final"]["task_context"],
        follow_up_query=record["base"]["follow_up_query"],
        plausible_actions=record["base"]["plausible_actions"],
        sessions=record["sessions"], probes=record["probes"])


def replicated_agents():
    """A replicated cell's four agents, each with its own memory over
    the store, supersession on."""
    def memory():
        return replicated.ReplicatedMemory(
            "inhouse", config("session", "exclude"))
    agents = {name: cls(name, memory()) for name, cls in (
        ("profile_agent", replicated.ReplicatedProfileAgent),
        ("task_agent", replicated.ReplicatedTaskAgent),
        ("calendar_agent", replicated.ReplicatedCalendarAgent))}
    agents["assistant_agent"] = replicated.ReplicatedAssistantAgent(
        "assistant_agent", memory())
    return agents


def test_the_audit_reads_the_raw_store_and_reports_a_hidden_carrier(store):
    """Amendment 4, "The audit reads the store", through the real
    replicated locus and library. User 0's history: the revoke went
    through the forget and took the echo too, so no carrier is left;
    every earlier statement is marked retired and no probe's block held
    one; the guard was armed and dropped nothing. A carrier planted
    with the provider afterwards is withheld from its owner's own
    listing (``list_own``) and dropped from the assistant's block, but
    the harness's listing is the raw store, so it holds the row with
    its text, and ``revoked_value_rows`` reports it."""
    from benchmarks.shared_memory import history
    from benchmarks.shared_memory.pipeline import VariantRunner

    backend, _ = store
    user = v2_user(0)
    agents = replicated_agents()
    locus = history.AgentManagedLocus("replicated", agents)
    outcome = history.run_history(user, locus,
                                  VariantRunner(None, "replicated"))
    assert outcome.failure is None, outcome.failure
    assert {listing["source"] for listing in outcome.listings} == {"store"}
    [revoke] = [e for s in outcome.sessions for e in s.events
                if e["type"] == "revoke"]
    echo = next(e for s in user.sessions for e in s["events"]
                if e.get("echo_of"))
    echo_ids = next(e["memory_ids"] for s in outcome.sessions
                    for e in s.events if e["event_id"] == echo["event_id"])
    assert revoke["revoke_path"] == "forget"
    assert echo_ids and set(echo_ids) <= set(revoke["deleted_ids"])
    assert history.revoked_value_rows(user, outcome) == []
    assert history.reappeared_ids(outcome) == []
    retired = history.retired_rows(user, outcome)
    assert {r["provenance_event"] for r in retired} == set(
        history.retired_events(user))
    assert all(r["superseded_by"] for r in retired)
    for result in history.score_turns(user, outcome, "replicated"):
        assert result.error is None and result.retired_in_block == []
        assert result.diagnostics.after_tombstone is not None
        assert result.diagnostics.tombstoned_rows == []
        assert result.diagnostics.tombstoned_forms >= 1
    events = {e["event_id"]: e for s in user.sessions for e in s["events"]}
    target = events[events[revoke["event_id"]]["target_event"]]
    text = f"We moved the retro back to {target['value']}."
    planted = backend.add(planted_note(text, owner="calendar_agent"))
    assert planted not in {r["memory_id"] for r in
                           agents["calendar_agent"].list_own_rows(USER)}
    ids = {name: {USER} for name in history.AGENTS}
    listing = history._listing(locus, "probes", ids)
    assert listing["source"] == "store"
    row = next(r for r in listing["rows"]["calendar_agent"]
               if r["memory_id"] == planted)
    assert row["content"] == text
    assert any(r["metadata"].get("sharing_policy") == "private"
               for r in listing["rows"]["task_agent"])
    outcome.listings[-1] = listing
    [carrier] = history.revoked_value_rows(user, outcome)
    expected = {
        "listing": "probes", "memory_id": planted,
        "owner_agent": "calendar_agent", "provenance_event": "planted",
        "fact_key": "planted", "revoke_event": revoke["event_id"],
        "value": target["value"]}
    assert {key: carrier.get(key) for key in expected} == expected
    assistant = agents["assistant_agent"]
    assistant.session, assistant.probe_id = 7, "p_check"
    assistant.store_conversation = False
    diagnostics = assistant.run("Which chat app does my team use?")[
        "injection_diagnostics"]
    assert diagnostics["tombstoned_rows"] == [planted]
