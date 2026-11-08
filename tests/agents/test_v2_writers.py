"""Benchmark v2 writers and consumers (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md): the one event loop every writer runs
(``shared_memory_utils.run_v2_session``), and each locus's writes,
listings, deletes, session ages and conversation stamps. The kernel is
mocked at the agents' module names; native in-house runs on a real
Chroma store in a temporary directory with a fake embedder; native Mem0
on a fake client. The replicated locus is checked in a fresh
interpreter (``_v2_replicated_checks.py``; known issue 18).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import chromadb
import pytest
from chromadb.config import Settings

from cerebrum.example.agents import shared_memory_utils as smu
from cerebrum.example.agents import variants
from cerebrum.example.agents.assistant_agent import agent as assistant_module
from cerebrum.example.agents.calendar_agent import agent as calendar_module
from cerebrum.example.agents.native import agents as native
from cerebrum.example.agents.native import backends
from cerebrum.example.agents.profile_agent import agent as profile_module
from cerebrum.example.agents.task_agent import agent as task_module
from cerebrum.example.agents.variants import apply_variant

REPO = Path(__file__).resolve().parents[2]
CHECKS = Path(__file__).with_name("_v2_replicated_checks.py")
USER = "ana_r1_t0__kernel_shared"
PROVENANCE = {"provenance_agent": "profile_agent", "provenance_user": USER}


def event(event_id, kind, fact_key, value=None, utterance=None, **extra):
    """A dataset event (contract: event_id, type, slot, fact_key, value,
    aliases, old_value, sharing, template, utterance, paraphrased)."""
    return {
        "event_id": event_id, "type": kind,
        "slot": None if kind == "base" else fact_key,
        "fact_key": fact_key, "value": value, "aliases": [],
        "old_value": None,
        "sharing": "private" if kind == "private" else "shared",
        "template": utterance, "paraphrased": False,
        "utterance": (
            utterance if utterance is not None
            else f"Please forget my {fact_key}." if kind == "revoke"
            else f"My {fact_key} is {value}."
        ),
        **extra,
    }


def payload(session, events):
    return json.dumps({"v2_session": {"session": session, "events": events}})


HISTORY = [
    event("e0", "base", "base_profile",
          utterance="My name is Ana Li. I prefer to use vim."),
    event("e1", "add", "pet", "Mochi"),
    event("e2", "update", "city", "Tallinn", target_event="e9"),
    event("e3", "contradict", "chat_app", "Zulip", target_event="e8"),
    event("e4", "add", "pet_vet_visit", "Mochi", echo_of="e1",
          target_event="e1"),
    event("e5", "private", "job_interview", "Northwind"),
]


class Writer(SimpleNamespace):
    """A writer's attributes, as the harness sets them."""

    def __init__(self, **kwargs):
        super().__init__(**{
            "agent_name": "profile_agent", "user_id": USER,
            "share_memory": True, "delete_on_revoke": True,
            "extra_metadata": dict(PROVENANCE), **kwargs,
        })


class Locus:
    """A locus's create, list and delete calls over one dict of rows;
    ``fail`` maps an operation to the reply (or exception) it returns."""

    def __init__(self, fail=None, rows=None):
        self.rows = dict(rows or {})
        self.fail = fail or {}
        self.creates, self.lists, self.deletes = [], [], []

    def _reply(self, operation, value):
        if operation in self.fail:
            reply = self.fail[operation]
            if isinstance(reply, Exception):
                raise reply
            return reply
        return value

    def write(self, content, metadata):
        self.creates.append((content, metadata))
        memory_id = f"m{len(self.rows)}"
        self.rows[memory_id] = {"memory_id": memory_id, "content": content,
                                "metadata": dict(metadata)}
        return self._reply("create", memory_id)

    def list_rows(self, user_id):
        self.lists.append(user_id)
        return self._reply("list", [dict(r) for r in self.rows.values()])

    def delete(self, user_id, memory_id):
        self.deletes.append((user_id, memory_id))
        return self._reply("delete", self.rows.pop(memory_id, None)
                           is not None)


def run(agent, events, locus, session=2, memory_type="profile"):
    return smu.run_v2_session(
        agent, {"session": session, "events": events}, memory_type,
        write=locus.write, list_rows=locus.list_rows, delete=locus.delete,
    )


# -- the event loop --------------------------------------------------------


def test_each_write_event_stores_its_utterance_with_v2_metadata():
    locus = Locus()
    result = run(Writer(), HISTORY, locus)
    assert [c for c, _ in locus.creates] == [e["utterance"] for e in HISTORY]
    by_event = {m["provenance_event"]: m for _, m in locus.creates}
    for e in HISTORY:
        metadata = by_event[e["event_id"]]
        assert metadata["fact_key"] == e["fact_key"]
        assert metadata["event_type"] == e["type"]  # an echo is "add"
        assert metadata["session"] == 2
        assert metadata["owner_agent"] == "profile_agent"
        assert metadata["user_id"] == USER
        assert metadata["memory_type"] == "profile"
        assert metadata["provenance_agent"] == "profile_agent"
        assert metadata["provenance_user"] == USER
        assert json.loads(metadata["structured"]) == {
            "fact_key": e["fact_key"], "value": e["value"],
            "event_type": e["type"],
        }
        assert metadata["structured"] == json.dumps(
            json.loads(metadata["structured"]), sort_keys=True)
    assert by_event["e0"]["event_type"] == "base"
    assert by_event["e4"]["event_type"] == "add"
    assert [r["memory_ids"] for r in result["events"]] == [
        [f"m{i}"] for i in range(6)]
    assert result["stored_rows"] == 6 and not result["writer_failed"]
    assert result["written"] == [m for _, m in locus.creates]


def test_provenance_event_comes_from_the_event_and_is_set_last():
    agent = Writer(extra_metadata={**PROVENANCE, "provenance_event": "x",
                                   "fact_key": "x"})
    locus = Locus()
    run(agent, HISTORY[1:2], locus)
    metadata = locus.creates[0][1]
    assert metadata["provenance_event"] == "e1"
    # The rest of extra_metadata goes over the v2 keys (the contract's
    # order); only provenance_event is the event's.
    assert metadata["fact_key"] == "x"
    assert metadata["provenance_agent"] == "profile_agent"


@pytest.mark.parametrize("share,expected", [
    (True, "shared"), (False, "private"),
    # The kernel writers' share_memory method, when the harness set no
    # attribute: not a bool, so the default.
    (lambda memory_id: None, "shared"),
])
def test_sharing_rule(share, expected):
    locus = Locus()
    run(Writer(share_memory=share), HISTORY, locus)
    policies = {m["provenance_event"]: m["sharing_policy"]
                for _, m in locus.creates}
    assert policies.pop("e5") == "private"  # the private event, always
    assert set(policies.values()) == {expected}


def test_v1_shares_nothing():
    """V1 sets share_memory False: every v2 row is private."""
    agent = Writer()
    locus = Locus()
    with apply_variant(variants.variant("V1"), agent, "profile_agent",
                       "native"):
        run(agent, HISTORY, locus)
    assert {m["sharing_policy"] for _, m in locus.creates} == {"private"}
    assert agent.share_memory is True  # restored


def sibling_rows():
    """Mem0-style: one write became three facts, each with the write's
    metadata; plus another fact of the same writer."""
    meta = {"fact_key": "pet", "owner_agent": "profile_agent"}
    rows = {f"p{i}": {"memory_id": f"p{i}", "content": f"Mochi fact {i}",
                      "metadata": dict(meta)} for i in range(3)}
    rows["c0"] = {"memory_id": "c0", "content": "I live in Tallinn.",
                  "metadata": {"fact_key": "city"}}
    return rows


def test_revoke_deletes_every_row_with_the_fact_key():
    locus = Locus(rows=sibling_rows())
    result = run(Writer(), [event("e9", "revoke", "pet")], locus)
    record = result["events"][0]
    assert record["found_ids"] == record["deleted_ids"] == ["p0", "p1", "p2"]
    assert record["memory_ids"] == [] and record["stored_rows"] == 0
    assert locus.lists == [USER]
    assert locus.deletes == [(USER, f"p{i}") for i in range(3)]
    assert list(locus.rows) == ["c0"]
    assert result["deleted_ids"] == ["p0", "p1", "p2"]
    assert result["stored_rows"] == 0 and locus.creates == []


def test_no_delete_control_records_found_ids_and_deletes_nothing():
    locus = Locus(rows=sibling_rows())
    result = run(Writer(delete_on_revoke=False),
                 [event("e9", "revoke", "pet")], locus)
    record = result["events"][0]
    assert record["found_ids"] == ["p0", "p1", "p2"]
    assert record["deleted_ids"] == [] and locus.deletes == []
    assert len(locus.rows) == 4 and not result["writer_failed"]


def test_a_revoke_that_finds_nothing_is_no_error():
    locus = Locus(rows=sibling_rows())
    result = run(Writer(), [event("e9", "revoke", "manager")], locus)
    assert result["events"][0]["found_ids"] == []
    assert not result["writer_failed"]


FAILURES = [
    ("create", None, "create: no reply"),
    ("create", {"response": {"success": False, "error": "boom"}},
     "create: boom"),
    ("create", {"response": {"success": False}}, "create: success is"),
    ("create", RuntimeError("down"), "RuntimeError: down"),
    ("list", None, "list: no reply"),
    ("list", {"response": {"success": False, "error": "x"}}, "list: x"),
    ("list", {"response": {"success": True}}, "list: the reply holds no"),
    ("list", ConnectionError("refused"), "ConnectionError: refused"),
    ("delete", None, "delete: no reply"),
    ("delete", False, "delete: Memory not found"),
    ("delete", {"response": {"success": False,
                             "error": "Memory not found"}},
     "delete: Memory not found"),
    ("delete", {"response": {"error": "Memory not found"}},
     "delete: Memory not found"),
    ("delete", ValueError("Memory with id p0 not found"),
     "ValueError: Memory with id p0 not found"),
]


@pytest.mark.parametrize("operation,reply,message", FAILURES)
def test_writer_error_rule_stops_the_session(operation, reply, message):
    events = [event("e1", "add", "pet", "Mochi"),
              event("e9", "revoke", "pet"),
              event("e2", "add", "city", "Tallinn")]
    if operation != "create":
        events = events[1:]
    locus = Locus(fail={operation: reply}, rows=sibling_rows())
    result = run(Writer(), events, locus)
    assert result["writer_failed"] is True
    assert result["error"].startswith(message)
    failed = result["events"][-1]
    assert failed["error"] == result["error"]
    # Stopped: no later event ran (the city add was never sent).
    assert len(result["events"]) == (1 if operation == "create" else 1)
    assert all(c[0] != "My city is Tallinn." for c in locus.creates)
    if operation == "delete":
        assert failed["found_ids"] == ["p0", "p1", "p2"]
        assert failed["deleted_ids"] == []  # the first delete failed


def test_a_listing_at_its_limit_fails_the_revoke():
    rows = {f"r{i}": {"memory_id": f"r{i}", "content": "x",
                      "metadata": {"fact_key": "pet"}}
            for i in range(smu.V2_LIST_LIMIT)}
    locus = Locus(rows=rows)
    result = run(Writer(), [event("e9", "revoke", "pet")], locus)
    assert result["writer_failed"] and "limit" in result["error"]
    assert locus.deletes == []


def test_an_empty_memory_id_is_a_write_that_stored_no_row():
    """The kernel's reply when Mem0's extraction kept nothing."""
    result = smu.run_v2_session(
        Writer(), {"session": 1, "events": HISTORY[1:2]}, "profile",
        write=lambda c, m: {"response": {"memory_id": "", "success": True}},
        list_rows=None, delete=None,
    )
    assert result["events"][0]["memory_ids"] == []
    assert result["stored_rows"] == 0 and not result["writer_failed"]


def test_result_shape():
    result = run(Writer(), HISTORY[:2], Locus(), session=3)
    assert set(result) == {
        "agent_name", "result", "session", "user_id", "events",
        "stored_rows", "deleted_ids", "written", "writer_failed", "error",
        "token_usage",
    }
    assert result["result"] == "v2 session 3: 2 events"
    assert (result["agent_name"], result["session"], result["user_id"]) == (
        "profile_agent", 3, USER)
    assert result["token_usage"] is None and result["error"] is None
    assert set(result["events"][0]) == {
        "event_id", "type", "fact_key", "memory_ids", "stored_rows",
        "deleted_ids", "found_ids", "error",
    }
    assert result["events"][1] == {
        "event_id": "e1", "type": "add", "fact_key": "pet",
        "memory_ids": ["m1"], "stored_rows": 1, "deleted_ids": [],
        "found_ids": [], "error": None,
    }


@pytest.mark.parametrize("bad,reason", [
    ({"session": "2", "events": []}, "session must be an integer"),
    ({"session": True, "events": []}, "session must be an integer"),
    ({"session": 2, "events": {}}, "events must be a list"),
    ({}, "session must be an integer"),
])
def test_malformed_session_fails_without_calls(bad, reason):
    locus = Locus()
    result = smu.run_v2_session(
        Writer(), bad, "profile", write=locus.write,
        list_rows=locus.list_rows, delete=locus.delete,
    )
    assert result["writer_failed"] and reason in result["error"]
    assert result["events"] == [] and locus.creates == locus.lists == []


@pytest.mark.parametrize("user_id", [None, "", "  "])
def test_a_writer_without_a_user_fails_without_calls(user_id):
    locus = Locus()
    result = run(Writer(user_id=user_id), HISTORY, locus)
    assert result["writer_failed"] and "no user_id" in result["error"]
    assert locus.creates == []


@pytest.mark.parametrize("bad,reason", [
    (dict(event("e1", "add", "pet", "Mochi"), type="rename"),
     "unknown event type"),
    (dict(event("e1", "add", "pet", "Mochi"), utterance=""),
     "no utterance"),
    (dict(event("e1", "add", "pet", "Mochi"), fact_key=None), "no fact_key"),
    (dict(event("e1", "add", "pet", "Mochi"), event_id=""), "no event_id"),
])
def test_a_malformed_event_fails_the_writer(bad, reason):
    locus = Locus()
    result = run(Writer(), [bad, event("e2", "add", "city", "Tallinn")],
                 locus)
    assert result["writer_failed"] and reason in result["error"]
    assert locus.creates == [] and len(result["events"]) == 1


def test_parse_v2_session():
    assert smu.parse_v2_session(payload(1, [])) == {"session": 1,
                                                    "events": []}
    assert smu.parse_v2_session(json.dumps({"user_name": "Ana"})) is None
    assert smu.parse_v2_session("not json") is None
    assert smu.parse_v2_session(None) is None
    # A v2 input whose session is not an object is refused, not v1.
    assert smu.parse_v2_session(json.dumps({"v2_session": None})) == {}


def test_listed_rows_and_reply_ids():
    kernel = {"response": {"success": True, "search_results": [
        {"memory_id": "k1", "content": "c", "metadata": {"a": 1},
         "score": None, "timestamp": "t"}]}}
    assert smu.listed_rows(kernel) == [
        {"memory_id": "k1", "content": "c", "metadata": {"a": 1}}]
    assert smu.listed_rows([]) == []
    with pytest.raises(smu.WriterError, match="no reply"):
        smu.listed_rows(None)
    assert smu.reply_ids({"response": {"memory_id": "k1"}}) == ["k1"]
    assert smu.reply_ids("r1") == ["r1"] and smu.reply_ids("") == []
    assert smu.reply_ids(["a", "b"]) == ["a", "b"]
    assert smu.reply_error({"response": {"success": True}}) is None
    assert smu.reply_error(True) is None


# -- the kernel locus ------------------------------------------------------

KERNEL_WRITERS = [
    (profile_module, profile_module.ProfileAgent, "profile_agent",
     "profile"),
    (task_module, task_module.TaskAgent, "task_agent", "task_context"),
    (calendar_module, calendar_module.CalendarAgent, "calendar_agent",
     "calendar"),
]


class FakeKernel:
    """The kernel's create, owner-only list and owner-only delete, as
    the SDK replies to them."""

    def __init__(self):
        self.rows = {}

    def create(self, agent_name, content, metadata=None, base_url=None):
        memory_id = f"k{len(self.rows)}"
        metadata = dict(metadata or {})
        metadata.setdefault("owner_agent", agent_name)
        metadata.setdefault("sharing_policy", "private")
        self.rows[memory_id] = {"memory_id": memory_id, "content": content,
                                "metadata": metadata, "score": None}
        return {"response": {"response_class": "memory", "success": True,
                             "memory_id": memory_id, "error": None}}

    def list(self, agent_name, user_id, base_url=None, *, k=None):
        rows = [dict(r) for r in self.rows.values()
                if r["metadata"]["owner_agent"] == agent_name
                and r["metadata"].get("user_id") == user_id]
        return {"response": {"success": True, "search_results": rows[:k]}}

    def delete(self, agent_name, memory_id, base_url=None, user_id=None):
        row = self.rows.get(memory_id)
        if row is None or row["metadata"]["owner_agent"] != agent_name:
            return {"response": {"success": False,
                                 "error": "Memory not found"}}
        del self.rows[memory_id]
        return {"response": {"success": True, "memory_id": memory_id}}


@pytest.fixture
def kernel():
    """The SDK memory calls of every kernel agent module, mocked."""
    fake = FakeKernel()
    calls = SimpleNamespace(create=MagicMock(side_effect=fake.create),
                            list=MagicMock(side_effect=fake.list),
                            delete=MagicMock(side_effect=fake.delete),
                            fake=fake)
    patches = []
    for module, *_ in KERNEL_WRITERS:
        patches += [
            patch.object(module, "create_memory", calls.create),
            patch.object(module, "list_memories", calls.list),
            patch.object(module, "delete_memory", calls.delete),
        ]
    patches.append(patch.object(assistant_module, "list_memories",
                                calls.list))
    for p in patches:
        p.start()
    yield calls
    for p in patches:
        p.stop()


def kernel_writer(cls, name, **attributes):
    agent = cls(name)
    agent.user_id = USER
    agent.extra_metadata = {"provenance_agent": name,
                            "provenance_user": USER}
    for key, value in attributes.items():
        setattr(agent, key, value)
    return agent


@pytest.mark.parametrize("module,cls,name,memory_type", KERNEL_WRITERS)
def test_kernel_writer_sends_keyword_creates(kernel, module, cls, name,
                                             memory_type):
    agent = kernel_writer(cls, name, share_memory=True)
    result = agent.run(payload(1, HISTORY))
    assert not result["writer_failed"] and result["stored_rows"] == 6
    for call, e in zip(kernel.create.call_args_list, HISTORY):
        assert call.args == ()  # keyword content= and metadata=
        assert set(call.kwargs) == {"agent_name", "content", "metadata",
                                    "base_url"}
        assert call.kwargs["agent_name"] == name
        assert call.kwargs["content"] == e["utterance"]
        assert call.kwargs["metadata"]["memory_type"] == memory_type
        assert call.kwargs["metadata"]["provenance_event"] == e["event_id"]
        assert call.kwargs["base_url"] == module.aios_kernel_url
    assert [r["memory_ids"] for r in result["events"]] == [
        [f"k{i}"] for i in range(6)]


@pytest.mark.parametrize("module,cls,name,memory_type", KERNEL_WRITERS)
def test_kernel_revoke_lists_and_deletes_through_the_module(
        kernel, module, cls, name, memory_type):
    agent = kernel_writer(cls, name)
    agent.run(payload(1, [event("e1", "add", "pet", "Mochi"),
                          event("e2", "add", "city", "Tallinn")]))
    # A sibling fact of e1's write (Mem0 copies its metadata), and
    # another writer's row of the same slot, which is not this one's.
    kernel.fake.rows["s1"] = dict(kernel.fake.rows["k0"], memory_id="s1")
    kernel.fake.create("other_agent", "Mochi again", {
        "fact_key": "pet", "user_id": USER, "owner_agent": "other_agent"})
    result = agent.run(payload(4, [event("e9", "revoke", "pet")]))
    record = result["events"][0]
    assert record["found_ids"] == record["deleted_ids"] == ["k0", "s1"]
    assert kernel.list.call_args.kwargs == {
        "agent_name": name, "user_id": USER,
        "base_url": module.aios_kernel_url, "k": smu.V2_LIST_LIMIT}
    assert [c.kwargs for c in kernel.delete.call_args_list] == [
        {"agent_name": name, "memory_id": mid,
         "base_url": module.aios_kernel_url, "user_id": USER}
        for mid in ("k0", "s1")]
    # k3: the other writer's row (the fake numbers by row count).
    assert sorted(kernel.fake.rows) == ["k1", "k3"]


def test_kernel_writer_failure_is_loud(kernel):
    """A delete the kernel refuses fails the writer (no silent skip)."""
    agent = kernel_writer(task_module.TaskAgent, "task_agent")
    agent.run(payload(2, [event("e1", "add", "client", "Initech")]))
    kernel.delete.side_effect = lambda **kw: {"response": {
        "success": False, "error": "Memory not found"}}
    result = agent.run(payload(5, [event("e9", "revoke", "client"),
                                   event("e2", "add", "host", "atlas")]))
    assert result["writer_failed"] is True
    assert result["error"] == "delete: Memory not found"
    assert kernel.create.call_count == 1  # the later add never ran


def test_kernel_writer_without_the_attribute_shares(kernel):
    """The share_memory method trap: no attribute set, so shared."""
    agent = profile_module.ProfileAgent("profile_agent")
    agent.user_id = USER
    agent.run(payload(1, HISTORY[1:2]))
    assert kernel.create.call_args.kwargs["metadata"][
        "sharing_policy"] == "shared"


def test_kernel_v1_input_keeps_the_v1_path(kernel):
    profile = {"user_name": "Ana Li", "preferred_tools": ["vim"],
               "preferred_language": "Go", "response_style": "terse"}
    agent = kernel_writer(profile_module.ProfileAgent, "profile_agent",
                          share_memory=True)
    with patch.object(profile_module, "llm_chat_with_json_output",
                      return_value={"response": {
                          "response_message": json.dumps(profile)}}), \
            patch.object(profile_module, "search_memories",
                         return_value={}):
        result = agent.run(json.dumps(profile))
    assert result["writer_failed"] is False and "events" not in result
    assert kernel.create.call_args.kwargs["content"].startswith(
        "My name is Ana Li.")
    assert kernel.list.call_count == kernel.delete.call_count == 0


def test_harness_create_capture_sees_every_v2_create(kernel):
    """The harness patches the writers' module ``create_memory`` with
    ``(agent_name, content, metadata=None, base_url=None)``."""
    captured = []

    def capturing(agent_name, content, metadata=None, base_url=None):
        captured.append(metadata["provenance_event"])
        return kernel.fake.create(agent_name, content, metadata, base_url)

    for module, cls, name, _ in KERNEL_WRITERS:
        with patch.object(module, "create_memory", side_effect=capturing):
            kernel_writer(cls, name).run(payload(1, HISTORY[:2]))
    assert captured == ["e0", "e1"] * 3


@pytest.mark.parametrize("module,cls,name", [
    (profile_module, profile_module.ProfileAgent, "profile_agent"),
    (task_module, task_module.TaskAgent, "task_agent"),
])
@pytest.mark.parametrize("code", ["V1", "V3", "V5"])
def test_kernel_variants_change_a_v2_create(kernel, module, cls, name,
                                            code):
    agent = kernel_writer(cls, name, share_memory=True)
    with apply_variant(variants.variant(code), agent, name, "kernel"):
        result = agent.run(payload(2, HISTORY[1:2]))
    assert not result["writer_failed"]
    sent = kernel.create.call_args.kwargs
    metadata = sent["metadata"]
    if code == "V1":
        assert metadata["sharing_policy"] == "private"
    elif code == "V3":
        assert "owner_agent" not in metadata
        assert "sharing_policy" not in metadata
        assert metadata["provenance_event"] == "e1"
        # The kernel fills in the writer as owner: it still lists and
        # deletes its row.
        revoked = agent.run(payload(4, [event("e9", "revoke", "pet")]))
        assert revoked["events"][0]["deleted_ids"] == ["k0"]
    else:
        assert sent["content"] == metadata["structured"]
        assert json.loads(sent["content"])["value"] == "Mochi"
    # Restored: the module calls the mock again, unwrapped.
    assert module.create_memory is kernel.create


def test_kernel_v2_variant_uses_the_rewritten_user(kernel):
    agent = kernel_writer(task_module.TaskAgent, "task_agent")
    with apply_variant(variants.variant("V2"), agent, "task_agent",
                       "kernel"):
        result = agent.run(payload(2, [event("e1", "add", "host", "atlas"),
                                       event("e9", "revoke", "host")]))
    alias = f"{USER}@users.example"
    assert result["user_id"] == alias
    assert kernel.create.call_args.kwargs["metadata"]["user_id"] == alias
    assert kernel.list.call_args.kwargs["user_id"] == alias
    assert result["events"][1]["deleted_ids"] == ["k0"]


@pytest.mark.parametrize("module,cls,name,memory_type", KERNEL_WRITERS)
def test_kernel_list_own_rows(kernel, module, cls, name, memory_type):
    agent = kernel_writer(cls, name)
    agent.run(payload(1, HISTORY[1:3]))
    rows = agent.list_own_rows()
    assert [set(r) for r in rows] == [{"memory_id", "content",
                                       "metadata"}] * 2
    assert [r["metadata"]["provenance_event"] for r in rows] == ["e1", "e2"]
    assert kernel.list.call_args.kwargs["k"] == smu.V2_LIST_LIMIT
    assert agent.list_own_rows("someone_else") == []
    kernel.list.side_effect = lambda **kw: {"response": {
        "success": False, "error": "list failed"}}
    with pytest.raises(smu.WriterError, match="list failed"):
        agent.list_own_rows()


def assistant(llm_chat):
    agent = assistant_module.AssistantAgent("assistant_agent")
    agent.user_id = USER
    return agent, patch.object(assistant_module, "llm_chat", llm_chat)


def test_kernel_assistant_sends_the_current_session():
    chat = MagicMock(return_value={"response": {"response_message": "ok"}})
    agent, patched = assistant(chat)
    agent.session, agent.probe_id = 7, "p_recall"
    with patched:
        agent.run("Where do I live?")
    assert chat.call_args.kwargs["session"] == 7
    assert chat.call_args.kwargs["user_id"] == USER


def test_kernel_assistant_v1_request_is_unchanged():
    chat = MagicMock(return_value={"response": {"response_message": "ok"}})
    agent, patched = assistant(chat)
    assert agent.session is None and agent.probe_id is None
    with patched:
        agent.run("Where do I live?")
    assert set(chat.call_args.kwargs) == {
        "agent_name", "messages", "base_url", "llms", "user_id"}


def test_session_reaches_the_llm_query():
    """``llm_chat(session=)`` puts the session on the LLMQuery the kernel
    receives (the SDK change this relies on)."""
    from cerebrum.llm import apis

    with patch.object(apis, "send_request") as send:
        apis.llm_chat("assistant_agent", [{"role": "user", "content": "q"}],
                      user_id=USER, session=7)
    query = send.call_args.args[1]
    assert (query.session, query.user_id) == (7, USER)


def test_kernel_assistant_list_own_rows(kernel):
    kernel.fake.create("assistant_agent", "User: q\nAssistant: a", {
        "user_id": USER, "memory_type": "conversation", "session": 7})
    agent, _ = assistant(MagicMock())
    rows = agent.list_own_rows()
    assert [r["metadata"]["session"] for r in rows] == [7]
    assert kernel.list.call_args.kwargs == {
        "agent_name": "assistant_agent", "user_id": USER,
        "base_url": assistant_module.aios_kernel_url,
        "k": smu.V2_LIST_LIMIT}


# -- the native locus --------------------------------------------------------

NATIVE_USER = "ana_r1_t0__native_inhouse"
EMBEDDING = {"provider": "ollama", "model": "nomic-embed-text",
             "dimension": 8, "ollama_base_url": "http://localhost:11434"}


def fake_embed(text):
    digest = hashlib.sha256(text.encode()).digest()
    return [b / 255 for b in digest[:8]]


def settings(**kwargs):
    return backends.NativeSettings(embedding=EMBEDDING, backend_llm={},
                                   k=10, **kwargs)


@pytest.fixture
def inhouse(tmp_path, monkeypatch):
    """``NativeMemory("inhouse")`` handles on a real Chroma store in a
    temporary directory, with a fake embedder."""
    client = chromadb.PersistentClient(
        path=str(tmp_path / "chroma"),
        settings=Settings(anonymized_telemetry=False),
    )
    monkeypatch.setattr(backends, "chroma_client", lambda: client)
    monkeypatch.setattr(backends, "Embedder", lambda e: fake_embed)
    return lambda **kw: native.NativeMemory("inhouse", settings(**kw))


def native_writer(cls, name, memory, **attributes):
    agent = cls(name, memory)
    agent.user_id = NATIVE_USER
    agent.extra_metadata = {"provenance_agent": name,
                            "provenance_user": NATIVE_USER}
    for key, value in attributes.items():
        setattr(agent, key, value)
    return agent


def test_native_inhouse_write_list_own_and_delete(inhouse):
    memory = inhouse()
    ids = memory.write([], "My pet is Mochi.", "profile_agent", {
        "user_id": NATIVE_USER, "agent_id": "profile_agent",
        "fact_key": "pet"})
    assert len(ids) == 1 and isinstance(ids[0], str)
    memory.write([], "Other agent.", "task_agent", {
        "user_id": NATIVE_USER, "agent_id": "task_agent"})
    memory.write([], "Other user.", "profile_agent", {
        "user_id": "someone", "agent_id": "profile_agent"})
    rows = memory.list_own(NATIVE_USER, "profile_agent")
    assert rows == [{"memory_id": ids[0], "content": "My pet is Mochi.",
                     "metadata": {"user_id": NATIVE_USER,
                                  "agent_id": "profile_agent",
                                  "fact_key": "pet"}}]
    assert memory.delete("someone", ids[0]) is False  # not that user's
    assert memory.delete(NATIVE_USER, ids[0]) is True
    assert memory.delete(NATIVE_USER, ids[0]) is False  # gone
    assert memory.list_own(NATIVE_USER, "profile_agent") == []
    assert len(memory.list_own(NATIVE_USER, "task_agent")) == 1


def test_native_inhouse_writer_runs_a_session_and_revokes(inhouse):
    agent = native_writer(native.NativeProfileAgent, "profile_agent",
                          inhouse())
    result = agent.run(payload(1, HISTORY))
    assert not result["writer_failed"] and result["stored_rows"] == 6
    for metadata in result["written"]:
        assert metadata["agent_id"] == "profile_agent"
        assert metadata["created_at"]  # the native convention
    rows = agent.list_own_rows()
    assert sorted(r["metadata"]["provenance_event"] for r in rows) == [
        e["event_id"] for e in HISTORY]
    assert {r["memory_id"] for r in rows} == {
        i for r in result["events"] for i in r["memory_ids"]}
    revoked = agent.run(payload(4, [event("e9", "revoke", "pet")]))
    pet = [r["memory_id"] for r in rows if r["metadata"]["fact_key"] == "pet"]
    assert revoked["events"][0]["deleted_ids"] == pet
    assert "pet" not in {r["metadata"]["fact_key"]
                         for r in agent.list_own_rows()}


def test_native_v1_writer_counts_the_ids(inhouse):
    agent = native_writer(native.NativeTaskAgent, "task_agent", inhouse())
    task = {"current_project": "web server", "active_experiment": "load",
            "goals": ["fast"], "blockers": [], "next_steps": ["pool"]}
    with patch.object(task_module, "llm_chat_with_json_output",
                      return_value={"response": {
                          "response_message": json.dumps(task)}}):
        result = agent.run(json.dumps(task))
    assert result["stored_rows"] == 1
    # A v1 row carries no agent_id (v1 metadata is unchanged).
    assert "agent_id" not in result["written"]


class FakeMem0:
    """Shaped like ``mem0.Memory`` 2.0.2: ``add`` extracts ``facts``
    facts per write, each with a copy of the write's metadata (the
    entity ids at the top level); ``get_all``, ``get`` and ``delete`` as
    documented (``delete`` raises for a missing id)."""

    def __init__(self, facts=2):
        self.facts = facts
        self.rows = {}
        self.get_all_calls = []

    def add(self, messages, *, user_id, agent_id, metadata, infer):
        results = []
        for n in range(self.facts):
            memory_id = f"f{len(self.rows)}"
            self.rows[memory_id] = {
                "id": memory_id, "memory": f"{messages[-1]['content']} #{n}",
                "user_id": user_id, "agent_id": agent_id,
                "metadata": {k: v for k, v in metadata.items()
                             if k not in ("user_id", "agent_id")},
            }
            results.append({"id": memory_id, "event": "ADD"})
        return {"results": results}

    def get_all(self, *, filters, top_k=20):
        self.get_all_calls.append((dict(filters), top_k))
        rows = [dict(r) for r in self.rows.values()
                if all(r.get(k) == v for k, v in filters.items())]
        return {"results": rows[:top_k]}

    def get(self, memory_id):
        row = self.rows.get(memory_id)
        return dict(row) if row else None

    def delete(self, memory_id):
        if memory_id not in self.rows:
            raise ValueError(f"Memory with id {memory_id} not found")
        del self.rows[memory_id]
        return {"message": "Memory deleted successfully!"}

    def search(self, query, filters, top_k):
        rows = [dict(r, score=0.5) for r in self.rows.values()
                if r["user_id"] == filters["user_id"]]
        return {"results": rows[:top_k]}


@pytest.fixture
def mem0(monkeypatch):
    client = FakeMem0()
    monkeypatch.setattr(backends, "mem0_client", lambda s: client)
    return client


def test_native_mem0_writes_lists_and_deletes_sibling_facts(mem0):
    agent = native_writer(native.NativeTaskAgent, "task_agent",
                          native.NativeMemory("mem0", settings()))
    result = agent.run(payload(2, [event("e1", "add", "client", "Initech"),
                                   event("e2", "add", "host", "atlas")]))
    assert [r["memory_ids"] for r in result["events"]] == [
        ["f0", "f1"], ["f2", "f3"]]
    assert result["stored_rows"] == 4
    assert "agent_id" not in result["written"][0]  # Mem0's own kwarg
    other = native_writer(native.NativeProfileAgent, "profile_agent",
                          native.NativeMemory("mem0", settings()))
    other.run(payload(1, [event("e0", "add", "client", "Initech")]))
    revoked = agent.run(payload(5, [event("e9", "revoke", "client")]))
    assert revoked["events"][0]["deleted_ids"] == ["f0", "f1"]
    assert mem0.get_all_calls[-1] == (
        {"user_id": NATIVE_USER, "agent_id": "task_agent"},
        smu.V2_LIST_LIMIT)
    assert sorted(mem0.rows) == ["f2", "f3", "f4", "f5"]
    rows = agent.list_own_rows()
    assert [r["metadata"]["fact_key"] for r in rows] == ["host", "host"]
    assert rows[0]["metadata"]["agent_id"] == "task_agent"
    assert rows[0]["metadata"]["user_id"] == NATIVE_USER


def test_native_mem0_delete_is_scoped_to_the_user(mem0):
    memory = native.NativeMemory("mem0", settings())
    [first, _] = memory.write([{"role": "user", "content": "x"}], "x",
                              "task_agent", {"user_id": "someone"})
    assert memory.delete(NATIVE_USER, first) is False
    assert memory.delete(NATIVE_USER, "missing") is False
    assert first in mem0.rows
    assert memory.delete("someone", first) is True


def test_native_settings_follow_the_kernels_recency():
    config = {"embedding": EMBEDDING, "max_injected_memories": 10}
    default = backends.NativeSettings.from_kernel_config(config)
    assert (default.block_recency, default.block_recency_unit) == (
        False, "time")
    on = backends.NativeSettings.from_kernel_config(dict(config, pipeline={
        "block_recency": True, "block_recency_unit": "session"}))
    assert (on.block_recency, on.block_recency_unit) == (True, "session")
    with pytest.raises(ValueError, match="block_recency_unit"):
        settings(block_recency_unit="days")


@pytest.mark.parametrize("row,current,age", [
    (7, 7, "this session"), (6, 7, "1 session ago"),
    (1, 7, "6 sessions ago"), (5, 7, "2 sessions ago"),
    (8, 7, None), (None, 7, None), ("6", 7, None), (True, 7, None),
    (6, None, None), (6.0, 7, None),
])
def test_native_session_age_wording(row, current, age):
    assert native.session_age(row, current) == age


class RowsMemory:
    """A native memory that returns fixed rows and records writes."""

    backend = "inhouse"
    backend_extraction = False

    def __init__(self, rows, **recency):
        self.rows = rows
        self.settings = settings(**recency)
        self.writes = []

    def search(self, query, user_id, k):
        return [dict(r, metadata=dict(r["metadata"])) for r in self.rows][:k]

    def write(self, messages, text, agent_name, metadata):
        self.writes.append({"text": text, "metadata": dict(metadata),
                            "messages": messages})
        return [f"w{len(self.writes)}"]


def row(memory_id, content, session, **metadata):
    return {"memory_id": memory_id, "content": content, "score": 0.5,
            "metadata": {"user_id": NATIVE_USER, "owner_agent": "task_agent",
                         "sharing_policy": "shared", "memory_type": "task",
                         "fact_key": memory_id, "session": session,
                         "provenance_event": f"ev_{memory_id}",
                         **metadata}}


AGED_ROWS = [row("a", "We moved to Birch.", 6), row("b", "Mochi.", 1),
             row("c", "Earlier answer.", 7), row("d", "No session.", None),
             row("e", "Future.", 9), row("f", "Text session.", "6")]


def native_assistant(memory, session=7, probe_id="p_recency"):
    agent = native.NativeAssistantAgent("assistant_agent", memory)
    agent.user_id = NATIVE_USER
    agent.session, agent.probe_id = session, probe_id
    return agent


def chat():
    return MagicMock(return_value={"response": {"response_message": "ok"}})


def test_native_block_prints_session_ages():
    memory = RowsMemory(AGED_ROWS, block_recency=True,
                        block_recency_unit="session")
    agent, llm = native_assistant(memory), chat()
    with patch.object(native, "llm_chat", llm):
        result = agent.run("Where is the team sync?")
    block = llm.call_args.kwargs["messages"][0]["content"]
    assert block.split("\n") == [
        "Relevant memories about this user:",
        "- We moved to Birch. (1 session ago)",
        "- Mochi. (6 sessions ago)",
        "- Earlier answer. (this session)",
        "- No session.", "- Future.", "- Text session.",
    ]
    diagnostics = result["injection_diagnostics"]
    assert diagnostics["block_recency"] is True
    assert diagnostics["block_recency_unit"] == "session"
    assert diagnostics["session"] == 7
    first = diagnostics["injected_memories"][0]
    assert first["content"] == "We moved to Birch."  # without the age
    assert (first["fact_key"], first["session"],
            first["provenance_event"]) == ("a", 6, "ev_a")


def test_native_legacy_block_prints_session_ages_too():
    memory = RowsMemory(AGED_ROWS[:1], block_recency=True,
                        block_recency_unit="session")
    agent, llm = native_assistant(memory), chat()
    agent.block_format = "legacy"
    with patch.object(native, "llm_chat", llm):
        agent.run("q")
    block = llm.call_args.kwargs["messages"][0]["content"]
    assert "- [unknown] We moved to Birch. (1 session ago)" in block


@pytest.mark.parametrize("recency", [
    {}, {"block_recency": False, "block_recency_unit": "session"},
    {"block_recency": True, "block_recency_unit": "time"},
])
def test_native_block_has_no_session_ages_otherwise(recency):
    memory = RowsMemory(AGED_ROWS, **recency)
    agent, llm = native_assistant(memory), chat()
    with patch.object(native, "llm_chat", llm):
        result = agent.run("q")
    block = llm.call_args.kwargs["messages"][0]["content"]
    # No age suffix; some row texts hold the word "session" themselves.
    assert "session ago" not in block and "sessions ago" not in block
    assert "(this session)" not in block
    diagnostics = result["injection_diagnostics"]
    assert diagnostics["block_recency"] == recency.get("block_recency",
                                                        False)
    assert diagnostics["block_recency_unit"] == recency.get(
        "block_recency_unit", "time")


def test_native_conversation_row_is_stamped():
    memory = RowsMemory(AGED_ROWS[:1])
    agent = native_assistant(memory)
    with patch.object(native, "llm_chat", chat()):
        agent.run("Where do I live?")
    metadata = memory.writes[0]["metadata"]
    assert metadata["session"] == 7
    assert metadata["provenance_event"] == "p_recency"
    assert metadata["agent_id"] == "assistant_agent"
    assert metadata["memory_type"] == "conversation"
    assert metadata["sharing_policy"] == "private"


def test_native_v1_conversation_row_is_unchanged():
    memory = RowsMemory(AGED_ROWS[:1])
    agent = native_assistant(memory, session=None, probe_id=None)
    agent.extra_metadata = {"provenance_agent": "assistant_agent"}
    with patch.object(native, "llm_chat", chat()):
        result = agent.run("q")
    metadata = memory.writes[0]["metadata"]
    assert set(metadata) == {"owner_agent", "user_id", "memory_type",
                             "sharing_policy", "created_at",
                             "provenance_agent"}
    assert result["injection_diagnostics"]["session"] is None


def test_native_assistant_lists_its_conversation_rows(inhouse):
    memory = inhouse()
    agent = native_assistant(memory)
    with patch.object(native, "llm_chat", chat()):
        agent.run("Where do I live?")
    rows = agent.list_own_rows()
    assert len(rows) == 1
    assert rows[0]["content"] == "User: Where do I live?\nAssistant: ok"
    assert rows[0]["metadata"]["session"] == 7


@pytest.mark.parametrize("code", ["V1", "V3", "V5"])
def test_native_variants_change_a_v2_write(inhouse, code):
    agent = native_writer(native.NativeProfileAgent, "profile_agent",
                          inhouse())
    with apply_variant(variants.variant(code), agent, "profile_agent",
                       "native"):
        result = agent.run(payload(1, HISTORY[1:2]))
    assert not result["writer_failed"]
    [stored] = agent.list_own_rows()
    metadata = stored["metadata"]
    if code == "V1":
        assert metadata["sharing_policy"] == "private"
    elif code == "V3":
        # No owner and no policy: private to the visibility rule, but
        # the agent_id key still lists and deletes it.
        assert "owner_agent" not in metadata
        assert "sharing_policy" not in metadata
        assert metadata["agent_id"] == "profile_agent"
        revoked = agent.run(payload(4, [event("e9", "revoke", "pet")]))
        assert revoked["events"][0]["deleted_ids"] == [stored["memory_id"]]
    else:
        assert stored["content"] == metadata["structured"]
        assert json.loads(stored["content"])["value"] == "Mochi"
    assert "write" not in vars(agent.memory)  # restored


# -- the replicated locus, in a fresh interpreter -----------------------------


def test_replicated_v2_checks_in_a_fresh_interpreter():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS), "-q",
         "-p", "no:cacheprovider",
         "-o", "python_files=_v2_replicated_checks.py"],
        cwd=REPO, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, (
        result.stdout[-6000:] + result.stderr[-3000:]
    )
    assert " passed" in result.stdout and " failed" not in result.stdout


# -- V5 on a base event ---------------------------------------------------------

BASE_FIELDS = {"user_name": "Ana Li", "preferred_tools": ["vim", "git"],
               "preferred_language": "Go", "response_style": "terse"}


def test_a_base_events_payload_is_its_fields():
    """V5 writes ``structured``: for a base event that is the profile or
    task JSON, as v1 kept it, never a fact-less stub that leaves Mem0
    nothing to extract (functional check, H = 2, users 0 and 1)."""
    base = event("e0", "base", "base_profile", utterance="My name is Ana.",
                 fields=BASE_FIELDS)
    assert smu.v2_structured(base) == smu.structured(BASE_FIELDS)
    assert json.loads(smu.v2_structured(base))["user_name"] == "Ana Li"
    without = dict(base)
    del without["fields"]
    assert json.loads(smu.v2_structured(without)) == {
        "fact_key": "base_profile", "value": None, "event_type": "base"}
    add = event("e1", "add", "pet", "Mochi", fields=BASE_FIELDS)
    assert json.loads(smu.v2_structured(add))["value"] == "Mochi"


def test_v5_writes_the_base_fields_in_the_kernel(kernel):
    agent = kernel_writer(profile_module.ProfileAgent, "profile_agent")
    base = event("e0", "base", "base_profile",
                 utterance="My name is Ana Li.", fields=BASE_FIELDS)
    with apply_variant(variants.variant("V5"), agent, "profile_agent",
                       "kernel"):
        agent.run(payload(1, [base]))
    content = kernel.create.call_args.kwargs["content"]
    assert json.loads(content) == BASE_FIELDS
