"""Benchmark v2's harness (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Harness"): session ordering, the probes after
the history, the failure rules, the controls, what a revoke leaves
behind, and the probe_results schema, over an in-memory fake locus.

Amendment 2's harness changes are tested over the same fakes, the real
``KernelLocus`` with the kernel's replies faked (``FakeKernel``) and the
real ``AgentManagedLocus`` with fake agents: failed retrievals and
injections, errored probes recorded unscored, any exception failing the
user with what ran kept, rows per event from the listings, and the
agent-managed backend usage over every user id.

Amendment 4 (AIOS docs/DELETION_AND_SUPERSESSION.md): the kernel and
replicated listings are the raw store (the kernel's ``/memory/audit``,
the replicated provider's ``list``), so the audits see a row the
tombstone guard hides from the agents; the kernel writers revoke through
the user's forget; the controls writer_scoped and no_supersession; and
the retired statements, from the dataset."""
import json
import re
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from benchmarks.shared_memory import dataset, history, run_evaluation, synth_v2
from benchmarks.shared_memory.models import (
    InjectionDiagnostics,
    ProbeResult,
    TrialResult,
    V2UserData,
)
from benchmarks.shared_memory.pipeline import AgentPipeline, VariantRunner
from benchmarks.shared_memory.probes import match_forms, score_probe
from cerebrum.example.agents.native.sharing import in_partition, visible
from cerebrum.example.agents.shared_memory_utils import WriterError
from cerebrum.utils import usage

BASE = dataset.load("users_v1")
USER_ID = "jordan_r1_t0__kernel_shared"
RETRIEVAL_ERROR = ("own: ConnectionError: refused; "
                   "shared: ConnectionError: refused")


def v2_user(index=0):
    record = synth_v2.build_user(index, BASE.users[index])
    return V2UserData(
        index=index, user_id=USER_ID,
        profile=record["final"]["profile"],
        task_context=record["final"]["task_context"],
        follow_up_query=record["base"]["follow_up_query"],
        plausible_actions=record["base"]["plausible_actions"],
        sessions=record["sessions"], probes=record["probes"],
    )


class Store:
    """Rows of every agent, as the loci keep them. ``forgotten`` maps a
    user id to the forms a forget tombstoned: an owner's own listing
    (``own``, the library's ``list_own``) withholds a row that carries
    one, as the kernel's and the replicated agents' listings do; the
    raw store (``user_rows``: the kernel's ``/memory/audit``, the
    replicated provider's ``list``) keeps it (Amendment 4)."""

    def __init__(self):
        self.rows, self.next = {}, 0
        self.forgotten = {}

    def add(self, owner, content, metadata):
        mid = f"m{self.next}"
        self.next += 1
        self.rows[mid] = {"memory_id": mid, "content": content,
                          "metadata": dict(metadata, owner_agent=owner)}
        return mid

    def own(self, owner, uid):
        forms = self.forgotten.get(uid, [])
        return [r for r in self.user_rows(uid)
                if r["metadata"]["owner_agent"] == owner
                and match_forms(r["content"], forms) is None]

    def user_rows(self, uid):
        """Every row of the user, of every agent, in storage order."""
        return [dict(r) for r in self.rows.values()
                if r["metadata"].get("user_id") == uid]


class Listed:
    """A row as a provider's ``list`` returns it (``Candidate``)."""

    def __init__(self, row):
        self.row = row

    def to_row(self):
        return dict(self.row, score=None)


class StoreProvider:
    """The replicated store's provider over the fake store: ``list``
    returns the user's rows, of every agent, unfiltered, in storage
    order, cut at ``top_k`` (``MemoryProvider.list``)."""

    def __init__(self, store):
        self.store = store

    def list(self, user_id, top_k):
        return [Listed(r) for r in self.store.user_rows(user_id)[:top_k]]


class FakeResponse:
    """A ``requests`` response with a JSON body."""

    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Server Error")

    def json(self):
        return self.body


def block_diagnostics(rows, session, user_id):
    """Injection diagnostics of a block that holds ``rows``, built at
    ``session`` in the session unit."""
    return {
        "injected_count": len(rows), "session": session,
        "block_recency_unit": "session",
        "resolved_user_id": user_id,
        "block_text": "Known about this user:\n" + "\n".join(
            f"- {r['content']}" for r in rows),
        "injected_memories": [
            {"memory_id": r["memory_id"], "content": r["content"],
             "owner_agent": r["metadata"]["owner_agent"],
             "memory_type": "profile",
             "provenance_event": r["metadata"].get("provenance_event"),
             "fact_key": r["metadata"].get("fact_key"),
             "session": r["metadata"].get("session")} for r in rows],
        "own_fetched": len(rows), "after_threshold": len(rows),
        "after_cap": min(len(rows), 10),
        "after_budget": min(len(rows), 10),
    }


class FakeWriter:
    """A v2 writer over the store. ``facts`` rows are stored per write,
    each with the write's metadata, as Mem0's extraction stores sibling
    facts, and the reply names the first only, as the kernel's and the
    library's Mem0 add do."""

    def __init__(self, name, store, log):
        self.name, self.store, self.log = name, store, log
        self.user_id = None
        self.delete_on_revoke = True
        self.fail_on = None
        self.facts = 1
        self.facts_of = {}  # event id -> rows stored (overrides facts)

    def run(self, task_input):
        session = json.loads(task_input)["v2_session"]
        self.log.append(("session", session["session"], self.name))
        events, deleted, stored = [], [], 0
        for event in session["events"]:
            if self.fail_on == event["event_id"]:
                return {"agent_name": self.name, "user_id": self.user_id,
                        "events": events, "writer_failed": True,
                        "error": "create: Memory not found",
                        "deleted_ids": deleted, "stored_rows": stored}
            if event["type"] == "revoke":
                found = [r["memory_id"] for r in
                         self.store.own(self.name, self.user_id)
                         if r["metadata"].get("fact_key")
                         == event["fact_key"]]
                if self.delete_on_revoke:
                    for mid in found:
                        del self.store.rows[mid]
                    deleted += found
                events.append({"event_id": event["event_id"],
                               "found_ids": found,
                               "deleted_ids": found
                               if self.delete_on_revoke else []})
                continue
            metadata = {
                "user_id": self.user_id, "fact_key": event["fact_key"],
                "session": session["session"],
                "provenance_event": event["event_id"],
                "sharing_policy": "private" if event["type"] == "private"
                else "shared"}
            ids = [self.store.add(self.name, event["utterance"] if n == 0
                                  else f"{event['utterance']} ({n + 1})",
                                  metadata) for n in range(
                                      self.facts_of.get(event["event_id"],
                                                        self.facts))]
            stored += 1
            events.append({"event_id": event["event_id"],
                           "memory_ids": ids[:1]})
        return {"agent_name": self.name, "user_id": self.user_id,
                "events": events, "stored_rows": stored,
                "deleted_ids": deleted, "writer_failed": False,
                "error": None, "written": []}

    def list_own_rows(self, user_id=None):
        return self.store.own(self.name, user_id or self.user_id)


class FakeConsumer:
    """The assistant: every row of its user in the block, ``extra``
    added to its diagnostics, its conversation stored unless
    ``store_conversation`` is False (a v2 probe turn, Amendment 3). Its
    ``memory.provider`` lists the raw store, as a replicated agent's
    provider does (the replicated locus's audit reads it)."""

    def __init__(self, store, log, answer=None, diagnostics=None,
                 extra=None):
        self.store, self.log = store, log
        self.user_id, self.session, self.probe_id = None, None, None
        self.store_conversation = True
        self.answer = answer or (lambda q: f"An answer to: {q}")
        self.diagnostics = diagnostics
        self.extra = extra or {}
        self.memory = SimpleNamespace(provider=StoreProvider(store))

    def run(self, question):
        self.log.append(("probe", self.session, self.probe_id))
        rows = [r for r in self.store.rows.values()
                if r["metadata"].get("user_id") == self.user_id]
        diagnostics = dict(self.diagnostics or block_diagnostics(
            rows, self.session, self.user_id), **self.extra)
        answer = self.answer(question)
        if self.store_conversation:
            self.store.add("assistant_agent", f"User: {question}\n"
                           f"Assistant: {answer}",
                           {"user_id": self.user_id,
                            "session": self.session,
                            "provenance_event": self.probe_id})
        return {"result": answer, "injection_diagnostics": diagnostics,
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                "total_tokens": 15}}

    def list_own_rows(self, user_id=None):
        return self.store.own("assistant_agent", user_id or self.user_id)


class FakeLocus:
    locus = "kernel"
    writes_from_results = True

    def __init__(self, **consumer):
        self.store, self.log = Store(), []
        self.writers = {n: FakeWriter(n, self.store, self.log)
                        for n in history.WRITERS}
        self.assistant = FakeConsumer(self.store, self.log, **consumer)

    def start_user(self, user_id, control):
        for agent in (*self.writers.values(), self.assistant):
            agent.user_id = user_id
        for agent in self.writers.values():
            agent.delete_on_revoke = control != "no_delete"

    def writer(self, name):
        return self.writers[name]

    def consumer(self, user_id, probe_id):
        self.assistant.session, self.assistant.probe_id = 7, probe_id
        self.assistant.store_conversation = False  # as the loci do
        return self.assistant

    def lister(self, name):
        return self.assistant if name == "assistant_agent" \
            else self.writers[name]

    def audit_rows(self, user_id):
        """The raw store of the user, as the kernel's ``/memory/audit``
        lists it (Amendment 4); a listing at the limit fails."""
        rows = self.store.user_rows(user_id)
        if len(rows) >= history.LIST_LIMIT:
            raise history.LocusFailure(
                f"listing_at_limit: audit of {user_id}")
        return rows

    def capture(self, written):
        from contextlib import ExitStack
        return ExitStack()

    def backend_usage(self, turns, user_ids=()):
        return None, None

    def finish_user(self):
        pass


def run(locus, user=None, control=None, variants=None):
    user = user or v2_user()
    outcome = history.run_history(user, locus,
                                  VariantRunner(variants, locus.locus),
                                  control=control)
    return user, outcome


def managed(kind, writer=None, consumer=None, **options):
    """The real ``AgentManagedLocus`` (``native`` or ``replicated``) over
    fake agents sharing one store; ``options`` go to the consumer."""
    store, log = Store(), []
    make_writer = writer or FakeWriter
    make_consumer = consumer or FakeConsumer
    agents = {n: make_writer(n, store, log) for n in history.WRITERS}
    agents[history.CONSUMER] = make_consumer(store, log, **options)
    return history.AgentManagedLocus(kind, agents)


class FakeKernel:
    """The kernel's replies to the kernel agents' SDK calls (create,
    list, delete, forget and chat) and to the harness's audit, over one
    store, for the real ``KernelLocus``. A create stores ``facts`` rows
    with its metadata and names the first, as the kernel's Mem0 add
    does; a chat reply's diagnostics hold every row of the user plus
    ``extra``, and the kernel stores the turn only with
    ``auto_extract`` (off in v2 since Amendment 3).

    Amendment 4: a forget deletes, whoever owns it, every row of the
    user whose ``fact_key`` is the slot and every row that carries a
    form of the slot's values (its statements' ``structured`` value
    and ``value_aliases``, under the scorer's matcher), tombstones the
    forms (the owner listings then withhold a carrier) and replies with
    the kernel's report in ``metadata``; ``GET /memory/audit`` lists
    the raw store of the user, ``at_limit`` when it reaches the
    harness's limit."""

    def __init__(self, facts=1, extra=None, auto_extract=False):
        self.store, self.facts, self.extra = Store(), facts, extra or {}
        self.auto_extract = auto_extract
        self.forgets, self.audits = [], []

    def create_memory(self, agent_name, content=None, metadata=None,
                      base_url=None, **kwargs):
        owner = (metadata or {}).get("owner_agent", agent_name)
        ids = [self.store.add(owner, content if n == 0
                              else f"{content} ({n + 1})", metadata or {})
               for n in range(self.facts)]
        return {"response": {"success": True, "memory_id": ids[0]}}

    def list_memories(self, agent_name, user_id=None, base_url=None,
                      k=None, **kwargs):
        return {"response": {"success": True,
                             "search_results": self.store.own(agent_name,
                                                              user_id)}}

    def delete_memory(self, agent_name, memory_id, base_url=None,
                      user_id=None, **kwargs):
        if memory_id not in self.store.rows:
            return {"response": {"success": False,
                                 "error": "Memory not found"}}
        del self.store.rows[memory_id]
        return {"response": {"success": True, "memory_id": memory_id}}

    def forget_memories(self, agent_name, fact_key=None, user_id=None,
                        base_url=None, **kwargs):
        self.forgets.append({"agent_name": agent_name,
                             "fact_key": fact_key, "user_id": user_id})
        rows = self.store.user_rows(user_id)
        values = {}
        for row in rows:
            metadata = row["metadata"]
            if metadata.get("fact_key") != fact_key:
                continue
            value = json.loads(metadata.get("structured") or "{}").get(
                "value")
            if value:
                values.setdefault(value, []).extend(json.loads(
                    metadata.get("value_aliases") or "[]"))
        forms = [*values, *(a for aliases in values.values()
                            for a in aliases)]
        self.store.forgotten.setdefault(user_id, []).extend(forms)
        deleted = []
        for row in rows:
            metadata = row["metadata"]
            form = match_forms(row["content"], forms)
            if metadata.get("fact_key") == fact_key:
                reason = "fact_key"
            elif form is not None:
                reason = "value" if form in values else "alias"
            else:
                continue
            del self.store.rows[row["memory_id"]]
            deleted.append({"memory_id": row["memory_id"],
                            "owner_agent": metadata["owner_agent"],
                            "reason": reason})
        report = {"deleted": deleted, "values_count": len(values),
                  "forms_count": len(forms),
                  "scrubbed": {"messages": 0, "history": 0},
                  "listed": len(rows), "not_found": []}
        return {"response": {"success": True, "metadata": report}}

    def get(self, url, params=None, timeout=None, **kwargs):
        """``requests.get`` as the kernel answers it: only the audit
        route, ``GET /memory/audit?user_id=``."""
        assert url.endswith("/memory/audit"), url
        user_id = (params or {})["user_id"]
        self.audits.append(user_id)
        rows = self.store.user_rows(user_id)
        return FakeResponse({
            "user_id": user_id, "rows": [dict(r, score=None) for r in rows],
            "at_limit": len(rows) >= history.LIST_LIMIT})

    def llm_chat(self, agent_name, messages, base_url=None, llms=None,
                 user_id=None, session=None, **kwargs):
        question = messages[-1]["content"]
        rows = [r for r in self.store.rows.values()
                if r["metadata"].get("user_id") == user_id]
        diagnostics = dict(block_diagnostics(rows, session, user_id),
                           **self.extra)
        answer = f"An answer to: {question}"
        if self.auto_extract:
            self.store.add(agent_name,
                           f"User: {question}\nAssistant: {answer}",
                           {"user_id": user_id, "session": session,
                            "memory_type": "conversation",
                            "provenance_event": kwargs.get(
                                "provenance_event")})
        return {"response": {"response_message": answer},
                "injection_diagnostics": diagnostics,
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                "total_tokens": 15}}

    def patched(self) -> ExitStack:
        """The kernel agents' module-level SDK calls and the harness's
        audit request (``requests.get``, which ``KernelLocus.audit_rows``
        imports when it runs), answered here."""
        from cerebrum.example.agents.assistant_agent import (
            agent as assistant,
        )
        from cerebrum.example.agents.calendar_agent import agent as calendar
        from cerebrum.example.agents.profile_agent import agent as profile
        from cerebrum.example.agents.task_agent import agent as task

        stack = ExitStack()
        for module in (profile, task, calendar):
            for name in ("create_memory", "list_memories", "delete_memory",
                         "forget_memories"):
                stack.enter_context(
                    patch.object(module, name, getattr(self, name)))
        stack.enter_context(patch.object(assistant, "llm_chat",
                                         self.llm_chat))
        stack.enter_context(patch.object(assistant, "list_memories",
                                         self.list_memories))
        stack.enter_context(patch.object(requests, "get", self.get))
        return stack


def record_usage(tag):
    """One backend LLM call and one embedding call tagged ``tag``."""
    usage.ACCUMULATOR.record(tag, usage.BACKEND_EXTRACTION, "azure/gpt-4o",
                             100, 20)
    usage.ACCUMULATOR.record(tag, usage.EMBEDDING,
                             "ollama/nomic-embed-text", 8, 0)


class UsageWriter(FakeWriter):
    """A writer whose backend makes one LLM and one embedding call per
    write, tagged with the user id it writes under (a V2 variant's
    rewritten one), as the native and replicated writers' calls are."""

    def run(self, task_input):
        result = super().run(task_input)
        for event in result["events"]:
            if "memory_ids" in event:
                record_usage(self.user_id)
        return result


class UsageConsumer(FakeConsumer):
    """An assistant that, as the native and replicated ones do, makes
    its own backend calls and then takes everything tagged with its
    own user id, reported as its ``backend_usage``."""

    def run(self, question):
        result = super().run(question)
        record_usage(self.user_id)
        records = usage.ACCUMULATOR.take(self.user_id)
        result["backend_usage"] = {
            "backend_llm_tokens": usage.summarize(
                records, usage.BACKEND_EXTRACTION),
            "embedding_tokens": usage.summarize(records, usage.EMBEDDING),
            "records": records,
        }
        return result


# -- ordering ---------------------------------------------------------------

def test_sessions_run_in_order_then_the_probes_at_session_7():
    locus = FakeLocus()
    user, outcome = run(locus)
    sessions = [entry for entry in locus.log if entry[0] == "session"]
    assert [s[1] for s in sessions] == [1, 2, 3, 4, 5, 6]
    assert [s[2] for s in sessions] == [s["writer"] for s in user.sessions]
    probes = [entry for entry in locus.log if entry[0] == "probe"]
    assert [p[2] for p in probes] == [p["probe_id"] for p in user.probes]
    assert all(p[1] == 7 for p in probes)
    # Every session came before every probe.
    assert locus.log.index(probes[0]) == len(sessions)
    # Listings after each session, after the history, after the probes.
    assert [l["after"] for l in outcome.listings] == [
        f"session {i}" for i in range(1, 7)] + ["history", "probes"]
    assert outcome.failure is None
    assert [s.session for s in outcome.sessions] == [1, 2, 3, 4, 5, 6]
    assert all(set(s.listing_counts) == set(history.AGENTS)
               for s in outcome.sessions)


def test_the_no_memory_control_skips_the_sessions():
    locus = FakeLocus()
    _, outcome = run(locus, control="no_memory")
    assert not [e for e in locus.log if e[0] == "session"]
    assert len([e for e in locus.log if e[0] == "probe"]) == 6
    assert outcome.sessions == []


def test_the_no_delete_control_reaches_the_writers():
    locus = FakeLocus()
    user, outcome = run(locus, control="no_delete")
    assert history.deleted_ids(outcome) == []
    revoked = history.revoked_value_rows(user, outcome)
    assert {r["listing"] for r in revoked} == {"history", "probes"}


# -- failures ---------------------------------------------------------------

def test_a_writer_error_stops_the_history():
    locus = FakeLocus()
    user = v2_user()
    locus.writers["task_agent"].fail_on = user.sessions[1]["events"][1][
        "event_id"]
    _, outcome = run(locus, user)
    assert outcome.failure.startswith("writer_failed: task_agent in session 2")
    assert not [e for e in locus.log if e[0] == "probe"]


@pytest.mark.parametrize("answer", ["", "   ", "Error: boom"])
def test_a_consumer_error_fails_instead_of_passing(answer):
    locus = FakeLocus(answer=lambda q: answer)
    _, outcome = run(locus)
    assert "consumer" in outcome.failure
    # It stopped at the first probe: deletion, a hard constraint.
    assert len(outcome.turns) == 1


def test_a_block_not_built_at_session_7_fails():
    locus = FakeLocus(diagnostics={"injected_count": 2, "session": None,
                                   "block_recency_unit": "time"})
    _, outcome = run(locus)
    assert "session None" in outcome.failure


@pytest.mark.parametrize("kind", ["fake", "kernel", "replicated", "native"])
def test_a_listing_at_its_limit_fails(monkeypatch, kind):
    """A listing that reaches the limit may be cut, so the user fails:
    the raw store's (Amendment 4: the kernel's ``/memory/audit``
    reports ``at_limit``; the replicated provider's ``list`` returns
    the limit) and an owner's own listing (native) alike."""
    monkeypatch.setattr(history, "LIST_LIMIT", 3)
    if kind == "kernel":
        kernel = FakeKernel()
        with kernel.patched():
            _, outcome = run(history.KernelLocus())
    elif kind == "fake":
        _, outcome = run(FakeLocus())
    else:
        _, outcome = run(managed(kind))
    if kind == "native":
        assert re.fullmatch(r"listing_at_limit: \w+ after session \d",
                            outcome.failure), outcome.failure
    else:
        assert outcome.failure == f"listing_at_limit: audit of {USER_ID}"


# -- what a revoke leaves --------------------------------------------------

def test_deleted_ids_reappearing_and_residue_are_recorded():
    locus = FakeLocus()
    user, outcome = run(locus, v2_user(0))  # user 0 has an echo
    deleted = history.deleted_ids(outcome)
    assert deleted
    assert history.reappeared_ids(outcome) == []
    # Put a deleted row back, as a backend that resurrects one would.
    final = outcome.listings[-1]["rows"]["profile_agent"]
    final.append({"memory_id": deleted[0], "content": "x",
                  "metadata": {}})
    assert history.reappeared_ids(outcome) == [deleted[0]]
    residue = history.revoked_value_rows(user, outcome)
    echo = next(e for s in user.sessions for e in s["events"]
                if e.get("echo_of"))
    assert {r["provenance_event"] for r in residue} >= {echo["event_id"]}
    assert all(r["owner_agent"] != "profile_agent" or
               r["provenance_event"] is None for r in residue)


def test_the_extraction_guard_counts_rows_by_event():
    locus = FakeLocus()
    user, outcome = run(locus)
    assert history.extraction_failure(user, outcome, True) is None
    assert history.extraction_failure(user, outcome, False) is None
    # A write that stored nothing: drop its row from its listing.
    event = user.sessions[2]["events"][0]
    listing = outcome.listings[2]["rows"][user.sessions[2]["writer"]]
    listing[:] = [r for r in listing if r["metadata"]["provenance_event"]
                  != event["event_id"]]
    assert event["event_id"] in history.extraction_failure(
        user, outcome, True)


# -- probe_results schema ----------------------------------------------------

def test_probe_results_have_the_spec_fields():
    locus = FakeLocus()
    user, outcome = run(locus)
    results = history.score_turns(user, outcome, "kernel")
    assert [r.type for r in results] == [
        "deletion", "privacy", "recall", "recency", "contradiction",
        "integration"]
    for r, probe in zip(results, user.probes):
        assert isinstance(r, ProbeResult)
        assert r.probe_id == probe["probe_id"]
        assert r.question == probe["question"]
        assert r.expected == probe["expected"]
        assert r.forbidden == probe["forbidden"]
        assert r.observed.startswith("An answer to")
        assert r.diagnostics is not None and r.diagnostics.session == 7
        assert r.token_usage["total_tokens"] == 15
        assert r.cap_bound is not None
    assert results[-1].passed is None  # integration is judged
    # The fake's block holds every row: the revoked value is in it.
    assert results[0].forbidden_in_block is True
    assert results[0].passed is False
    trial = TrialResult(trial_index=0, condition="kernel_shared",
                        probe_results=results, sessions=outcome.sessions)
    again = TrialResult.model_validate_json(trial.model_dump_json())
    assert again.probe_results[2].expected == results[2].expected
    assert len(again.sessions) == 6


# -- the orchestrator ----------------------------------------------------------

def orchestrator(**kwargs):
    with patch.object(run_evaluation, "SyntheticDataGenerator"), \
            patch.object(run_evaluation, "HybridJudge"):
        return run_evaluation.EvaluationOrchestrator(
            trials=1, output_dir="out", write_csv=False, condition=None,
            method=kwargs.pop("method", "kernel_shared"),
            dataset=kwargs.pop("dataset", "users_v1"), **kwargs)


def test_controls_need_v2_and_no_judge(tmp_path):
    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=2)
    with pytest.raises(ValueError):
        orchestrator(control="no_delete")  # v1 dataset
    with pytest.raises(ValueError):
        orchestrator(dataset=str(path), control="no_delete")  # judged
    with pytest.raises(ValueError):
        orchestrator(dataset=str(path), method="naive_concat", judge=False)
    o = orchestrator(dataset=str(path), control="no_delete", judge=False)
    assert o.v2 and o._run_settings()["control"] == "no_delete"


def test_a_v2_trial_mirrors_the_integration_probe_and_judges_it(tmp_path):
    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=1)
    o = orchestrator(dataset=str(path))
    o.generator.run_id = "r1"
    o._embed = False
    o.judge = MagicMock()
    o.judge.evaluate.return_value = SimpleNamespace(
        profile_usage_score=4, task_usage_score=3, integration_score=5,
        judge_attempts=1)
    locus = FakeLocus()

    def run_history_trial(user, variants=None, *, control=None,
                          recency_session=True):
        user = user.model_copy(update={"user_id": USER_ID})
        outcome = history.run_history(
            user, locus, VariantRunner(None, "kernel"), control=control)
        outcome.backend_extraction = False
        return user, outcome, "kernel"

    pipeline = SimpleNamespace(run_history_trial=run_history_trial)
    with patch.object(run_evaluation, "read_backend_usage",
                      return_value={"backend_llm_tokens": None,
                                    "embedding_tokens": None}):
        trial = o.run_single_trial(0, "kernel_shared", pipeline,
                                   method="kernel_shared")
    assert trial.failed is False, trial.error_message
    assert len(trial.probe_results) == 6 and len(trial.sessions) == 6
    integration = trial.probe_results[-1]
    assert trial.assistant_response == integration.observed
    assert trial.integration_score == integration.integration_score == 5
    kwargs = o.judge.evaluate.call_args.kwargs
    assert kwargs["query"] == trial.follow_up_query
    assert kwargs["profile"] == trial.synthetic_profile
    assert trial.input_sha256 and trial.user_id == USER_ID
    assert trial.token_usage.total_tokens == 6 * 15


def test_base_events_reach_the_writers_with_their_fields():
    """The harness hands a base event the fields it states (as a v1
    writer got them), so V5's raw payload has facts in it."""
    sent = []
    locus = FakeLocus()
    real = FakeWriter.run

    def recording(self, task_input):
        sent.append(json.loads(task_input)["v2_session"])
        return real(self, task_input)
    user = v2_user()
    with patch.object(FakeWriter, "run", recording):
        run(locus, user)
    bases = [e for s in sent for e in s["events"] if e["type"] == "base"]
    assert [b["fact_key"] for b in bases] == ["base_profile", "base_task"]
    assert bases[0]["fields"] == user.profile.model_dump()
    assert bases[1]["fields"] == user.task_context.model_dump()
    # The dataset's own events are left as they were.
    assert all("fields" not in e for s in user.sessions
               for e in s["events"])


# -- Amendment 2: the models ------------------------------------------------

def test_diagnostics_and_probe_results_carry_the_error_fields():
    reader = AgentPipeline(share_memory=True)
    diagnostics = reader._extract_injection_diagnostics(
        {"injection_diagnostics": {
            "injected_count": 0, "block_text": "",
            "retrieval_error": RETRIEVAL_ERROR,
            "injection_error": "RuntimeError: provider down"}})
    assert diagnostics.retrieval_error == RETRIEVAL_ERROR
    assert diagnostics.injection_error == "RuntimeError: provider down"
    result = ProbeResult(probe_id="p", type="recall", question="q",
                         semantic_error="ConnectionError: refused")
    assert result.semantic_error == "ConnectionError: refused"
    # A falsy error is no error; any other value is kept as its text,
    # so a producer's odd value cannot make the results file unloadable.
    assert InjectionDiagnostics(retrieval_error="").retrieval_error is None
    assert InjectionDiagnostics(
        injection_error=ValueError("bad row")).injection_error == "bad row"


def test_a_results_file_from_before_amendment_2_still_loads():
    old = {
        "trial_index": 0, "condition": "kernel_shared",
        "method": "kernel_shared",
        "injection_diagnostics": {"injected_count": 1, "block_text": "- x"},
        "sessions": [{
            "session": 1, "writer": "profile_agent", "stored_rows": 3,
            "events": [{"event_id": "u000-e00", "type": "base",
                        "memory_ids": ["m0"], "stored_rows": 1}],
            "listing_counts": {"profile_agent": 6}}],
        "probe_results": [{
            "probe_id": "u000-p3-recall", "type": "recall",
            "question": "q", "passed": True, "semantic_best": 0.4,
            "diagnostics": {"injected_count": 1, "block_text": "- x"}}],
    }
    trial = TrialResult.model_validate(old)
    assert trial.sessions[0].stored_rows == 3
    assert trial.sessions[0].events[0]["memory_ids"] == ["m0"]
    probe = trial.probe_results[0]
    assert probe.passed is True and probe.semantic_error is None
    assert probe.diagnostics.retrieval_error is None
    assert trial.injection_diagnostics.injection_error is None
    assert TrialResult.model_validate_json(trial.model_dump_json()) == trial


# -- Amendment 2: failed retrievals and injections --------------------------

def failing_block(kind, key, error):
    """A locus of ``kind`` whose consumer's diagnostics report ``key``
    as ``error``, and the patches it runs under."""
    if kind == "kernel":
        kernel = FakeKernel(extra={key: error})
        return history.KernelLocus(), kernel.patched()
    if kind == "fake":
        return FakeLocus(extra={key: error}), ExitStack()
    return managed(kind, extra={key: error}), ExitStack()


@pytest.mark.parametrize("kind", ["fake", "kernel", "replicated", "native"])
@pytest.mark.parametrize("key,what", [
    ("retrieval_error", "retrieval failed"),
    ("injection_error", "injection failed")])
def test_a_failed_retrieval_or_injection_fails_the_user(kind, key, what):
    """Before, a failed fetch looked like an empty store, so the
    deletion probe passed; now it is a consumer error in every locus."""
    error = RETRIEVAL_ERROR if key == "retrieval_error" else \
        "RuntimeError: provider down"
    locus, patches = failing_block(kind, key, error)
    with patches:
        user, outcome = run(locus)
    [turn] = outcome.turns  # it stopped at the first probe: deletion
    assert turn.error == f"consumer {what}: {error}"
    assert outcome.failure == f"{user.probes[0]['probe_id']}: {turn.error}"
    assert turn.answer.startswith("An answer to")  # the answer was fine
    assert len(outcome.sessions) == 6


@pytest.mark.parametrize("value", [None, ""])
def test_an_empty_error_field_is_no_error(value):
    locus = FakeLocus(extra={"retrieval_error": value,
                             "injection_error": value})
    _, outcome = run(locus)
    assert outcome.failure is None
    assert len(outcome.turns) == 6


def test_both_block_errors_are_named():
    locus = FakeLocus(extra={"retrieval_error": RETRIEVAL_ERROR,
                             "injection_error": "KeyError: 'x'"})
    _, outcome = run(locus)
    assert outcome.turns[0].error == (
        f"consumer retrieval failed: {RETRIEVAL_ERROR}; "
        "consumer injection failed: KeyError: 'x'")


# -- Amendment 2: errored probes are recorded unscored ----------------------

def with_session(session):
    """A consumer's diagnostics as built at ``session``."""
    def diagnostics(locus):
        real = locus.assistant.run

        def run_at(question):
            result = real(question)
            result["injection_diagnostics"]["session"] = session
            return result
        locus.assistant.run = run_at
    return diagnostics


ERRORED = {
    "empty answer": (dict(answer=lambda q: ""), None,
                     "consumer returned an empty answer"),
    "error text": (dict(answer=lambda q: "Error: model timed out"), None,
                   "consumer error: Error: model timed out"),
    "failed retrieval": (dict(extra={"retrieval_error": RETRIEVAL_ERROR}),
                         None, f"consumer retrieval failed: "
                         f"{RETRIEVAL_ERROR}"),
    "block at session 6": ({}, with_session(6),
                           "block built at session 6, not 7"),
}
SCORE_FIELDS_NONE = (
    "passed", "expected_present", "stale_present", "forbidden_in_answer",
    "forbidden_in_block", "transition_marked", "expected_in_block",
    "stale_in_block", "newest_target_row_has_stale", "cap_bound",
    "budget_bound", "answer_words", "semantic_best", "semantic_only",
    "semantic_error", "contaminated", "visible_stored_rows",
    "judge_scores", "integration_score", "retired_in_block")
SCORE_FIELDS_EMPTY = (
    "matched_expected", "matched_forbidden", "rows_with_expected",
    "rows_with_stale", "rows_with_forbidden", "other_values_in_answer",
    "deleted_ids_in_block")


@pytest.mark.parametrize("how", ERRORED)
def test_an_errored_probe_is_recorded_unscored(how):
    """pilot_v2 user 1's deletion probe (forbidden 'Kittiwake', no
    echo): scored, an errored turn over a clean block passed the hard
    constraint. It is recorded with its ground truth and the error."""
    options, setup, error = ERRORED[how]
    user = v2_user(1)
    locus = FakeLocus(**options)
    if setup:
        setup(locus)
    _, outcome = run(locus, user)
    [turn] = outcome.turns
    assert turn.error == error
    assert outcome.failure == f"u001-p1-deletion: {error}"
    # Scored, this turn would pass deletion: the block lacks the value.
    assert score_probe(turn.probe, turn.answer, turn.diagnostics,
                       user_values=[], locus="kernel")["passed"] is True
    # Native, so even the native-only visible_stored_rows is not set.
    [result] = history.score_turns(user, outcome, "native")
    probe = user.probes[0]
    assert (result.probe_id, result.type) == ("u001-p1-deletion",
                                              "deletion")
    assert result.question == probe["question"]
    assert result.expected == probe["expected"] == []
    assert result.forbidden == probe["forbidden"]
    assert result.target_event == probe["target_event"]
    assert result.observed == turn.answer and result.error == error
    assert result.diagnostics.block_text == turn.diagnostics["block_text"]
    assert result.token_usage["total_tokens"] == 15
    for name in SCORE_FIELDS_NONE:
        assert getattr(result, name) is None, name
    for name in SCORE_FIELDS_EMPTY:
        assert getattr(result, name) == [], name


def test_turns_before_an_error_are_still_scored():
    user = v2_user(1)
    failing = user.probes[2]["probe_id"]  # recall
    locus = FakeLocus()
    real = locus.assistant.run

    def run_probe(question):
        result = real(question)
        if locus.assistant.probe_id == failing:
            result["result"] = ""
        return result
    locus.assistant.run = run_probe
    _, outcome = run(locus, user)
    results = history.score_turns(user, outcome, "kernel")
    assert [r.type for r in results] == ["deletion", "privacy", "recall"]
    assert [r.error is None for r in results] == [True, True, False]
    assert results[0].passed is not None and results[1].passed is not None
    assert results[2].passed is None and results[2].matched_expected == []


# -- Amendment 2: any exception fails the user, what ran is kept ------------

LISTING_ERRORS = {
    # An owner's own listing (native): a list reply that is an error.
    "owner": (WriterError("list: success is false"),
              "WriterError: list: success is false"),
    # The raw store (kernel and replicated, Amendment 4): the audit
    # request failed.
    "store": (requests.HTTPError("500 Server Error: audit"),
              "HTTPError: 500 Server Error: audit"),
}


@pytest.mark.parametrize("listing", LISTING_ERRORS)
@pytest.mark.parametrize("at,listings,turns", [(3, 2, 0), (8, 7, 6)])
def test_a_listing_error_fails_the_user_and_keeps_what_ran(
        listing, at, listings, turns):
    """A listing that raises (an owner's list reply that is an error,
    or the raw store's audit) escaped run_history; the trial then kept
    nothing. Each listing lists the calendar writer once (owner
    listings) or the store once (the audit): the 3rd follows session
    3, the 8th the probes."""
    error, failure = LISTING_ERRORS[listing]
    calls = []
    if listing == "owner":
        locus = managed("native")
        writer = locus.agents["calendar_agent"]

        def failing(user_id=None):
            calls.append(user_id)
            if len(calls) == at:
                raise error
            return FakeWriter.list_own_rows(writer, user_id)
        writer.list_own_rows = failing
    else:
        locus = FakeLocus()
        real = locus.audit_rows

        def failing(user_id):
            calls.append(user_id)
            if len(calls) == at:
                raise error
            return real(user_id)
        locus.audit_rows = failing
    _, outcome = run(locus)
    assert outcome.failure == failure
    assert [s.session for s in outcome.sessions] == list(
        range(1, min(at, 6) + 1))
    assert len(outcome.listings) == listings
    assert len(outcome.turns) == turns
    assert all(t.error is None for t in outcome.turns)  # the probes ran


def test_a_consumer_that_raises_fails_the_user_and_keeps_its_turn():
    """A native or replicated consumer whose search raises: the user
    fails with the exception, and the probe is recorded unscored."""
    user = v2_user()
    locus = FakeLocus()
    real = locus.assistant.run

    def run_probe(question):
        if locus.assistant.probe_id == user.probes[1]["probe_id"]:
            raise RuntimeError("search failed")
        return real(question)
    locus.assistant.run = run_probe
    _, outcome = run(locus, user)
    assert outcome.failure == "RuntimeError: search failed"
    assert len(outcome.sessions) == 6 and len(outcome.listings) == 7
    first, raised = outcome.turns
    assert first.error is None
    assert raised.error == "consumer raised RuntimeError: search failed"
    assert raised.answer == "" and raised.diagnostics is None
    results = history.score_turns(user, outcome, "native")
    assert results[1].error == raised.error and results[1].passed is None
    assert results[1].forbidden == user.probes[1]["forbidden"]


def test_a_writer_that_raises_fails_the_user_and_records_its_session():
    locus = FakeLocus()

    def broken(task_input):
        raise KeyError("events")
    locus.writers["task_agent"].run = broken  # session 2's writer
    _, outcome = run(locus)
    assert outcome.failure == "KeyError: 'events'"
    first, failed = outcome.sessions
    assert first.session == 1 and not first.writer_failed
    assert (failed.session, failed.writer) == (2, "task_agent")
    assert failed.writer_failed and failed.error == "KeyError: 'events'"
    assert failed.events == [] and failed.stored_rows is None
    assert not [e for e in locus.log if e[0] == "probe"]


def test_a_harness_misuse_still_raises():
    """A control the locus cannot run is the caller's error, not the
    user's: it is raised before the history starts."""
    with pytest.raises(ValueError):
        run(history.KernelLocus(), control="no_visibility")


# -- Amendment 2: rows per event from the listings --------------------------

def check_rows_per_event(user, outcome):
    """Each write event holds both facts the store kept for it, from
    the listing; the reply named the first; revokes are untouched: an
    owner's revoke deleted what it found, the user's forget (Amendment
    4) the slot's rows it found and any other carrier of the value."""
    kinds = {e["event_id"]: e["type"]
             for s in user.sessions for e in s["events"]}
    for record in outcome.sessions:
        writes = 0
        for event in record.events:
            if kinds[event["event_id"]] == "revoke":
                assert "reported_ids" not in event
                assert event["found_ids"] != []
                if event.get("revoke_path") == "forget":
                    assert set(event["found_ids"]) <= set(
                        event["deleted_ids"])
                else:
                    assert event["deleted_ids"] == event["found_ids"]
                continue
            writes += 1
            [first] = event["reported_ids"]
            assert event["memory_ids"][0] == first
            assert event["stored_rows"] == len(event["memory_ids"]) == 2
        assert record.stored_rows == 2 * writes


def test_each_write_event_records_every_row_its_listing_shows():
    """A write Mem0 split into two facts (one reply id): before, the
    event recorded 1 row and the session the reply count."""
    locus = FakeLocus()
    for writer in locus.writers.values():
        writer.facts = 2
    user, outcome = run(locus)
    assert outcome.failure is None
    check_rows_per_event(user, outcome)
    # The fake writer's own reply-based record, kept as it was sent.
    revoke = next(e for s in outcome.sessions for e in s.events
                  if "reported_ids" not in e)
    assert set(revoke) == {"event_id", "found_ids", "deleted_ids"}
    # Each id is a row of the session's writer, in the listing after the
    # session, that carries the event (a later revoke may delete it).
    for record, listing in zip(outcome.sessions, outcome.listings):
        rows = {r["memory_id"]: r for r in listing["rows"][record.writer]}
        for event in record.events:
            for memory_id in event.get("memory_ids") or []:
                assert rows[memory_id]["metadata"][
                    "provenance_event"] == event["event_id"]


def test_kernel_events_record_every_fact_the_kernel_stored():
    """The kernel locus (the real kernel writers, the kernel's replies
    faked): the kernel's Mem0 add names only the first fact."""
    kernel = FakeKernel(facts=2)
    with kernel.patched():
        user, outcome = run(history.KernelLocus())
    assert outcome.failure is None
    check_rows_per_event(user, outcome)
    # These are run_v2_session's records (its keys), not a fake's.
    event = outcome.sessions[0].events[0]
    assert event["type"] == "base" and event["error"] is None
    # The revoke was the user's forget (Amendment 4).
    [revoke] = [e for s in outcome.sessions for e in s.events
                if e["type"] == "revoke"]
    assert revoke["revoke_path"] == "forget"
    assert [f["fact_key"] for f in kernel.forgets] == [revoke["fact_key"]]


def test_a_failed_session_keeps_its_reported_ids_and_lists_no_rows():
    locus = FakeLocus()
    user = v2_user()
    locus.writers["task_agent"].fail_on = user.sessions[1]["events"][1][
        "event_id"]
    _, outcome = run(locus, user)
    listed, failed = outcome.sessions
    assert listed.stored_rows == 3
    assert [e["stored_rows"] for e in listed.events] == [1, 1, 1]
    # No listing followed the failed session: its rows are unknown.
    assert failed.writer_failed and failed.stored_rows is None
    [base] = failed.events  # the base event ran before the failed add
    assert len(base["reported_ids"]) == 1
    assert base["memory_ids"] is None and base["stored_rows"] is None
    assert base["forgotten_ids"] is None
    # A listed session: no write lost a row to its own session.
    assert [e["forgotten_ids"] for e in listed.events] == [[], [], []]


def test_a_write_that_stored_nothing_records_zero_rows():
    """A listed session whose write left no row (Mem0 extracting nothing)
    records [] and 0, not None: only a session with no listing has
    unknown rows."""
    locus = FakeLocus()
    user = v2_user()
    session = user.sessions[0]
    empty = session["events"][1]["event_id"]
    locus.writers[session["writer"]].facts_of[empty] = 0
    _, outcome = run(locus, user)
    record = outcome.sessions[0]
    event = next(e for e in record.events if e["event_id"] == empty)
    assert event["memory_ids"] == [] and event["stored_rows"] == 0
    assert event["reported_ids"] == []
    others = [e for e in record.events if e["event_id"] != empty]
    assert record.stored_rows == sum(e["stored_rows"] for e in others) > 0


def test_the_kernel_capture_records_only_creates_the_kernel_accepted():
    """A create the kernel refused fails the writer and is not counted
    as written, as in the agent-managed loci (before, the capture
    recorded it as it was sent)."""
    class RefusingKernel(FakeKernel):
        def create_memory(self, agent_name, content=None, metadata=None,
                          base_url=None, **kwargs):
            if (metadata or {}).get("provenance_event") == self.refused:
                return {"response": {"success": False,
                                     "error": "provider down"}}
            return super().create_memory(agent_name, content, metadata,
                                         base_url, **kwargs)

    kernel = RefusingKernel()
    user = v2_user()
    kernel.refused = user.sessions[0]["events"][1]["event_id"]
    with kernel.patched():
        _, outcome = run(history.KernelLocus(), user)
    assert outcome.failure and "provider down" in outcome.failure
    # Only the base event's create, the one before the refused one.
    assert len(outcome.written) == 1


# -- Amendment 2: agent-managed backend usage -------------------------------

@pytest.mark.parametrize("variants", [
    None, {"profile_agent": "V2"}, {"assistant_agent": "V2"}])
def test_agent_managed_backend_usage_counts_every_user_id_once(variants):
    """Each assistant run takes only its own id's calls. A V2 writer's
    calls (its rewritten id) or, under a V2 consumer, every writer's
    (the base id) were never taken."""
    locus = managed("native", writer=UsageWriter, consumer=UsageConsumer)
    code = "-".join(sorted(variants or {})) or "none"
    user = v2_user().model_copy(update={"user_id": f"usage_{code}_t0"})
    _, outcome = run(locus, user, variants=variants)
    assert outcome.failure is None
    calls = len(history.write_events(user)) + len(user.probes)  # 19 + 6
    assert outcome.backend_llm_tokens.calls == calls
    assert outcome.backend_llm_tokens.total_tokens == 120 * calls
    assert outcome.backend_llm_tokens.models == ["azure/gpt-4o"]
    assert outcome.embedding_tokens.calls == calls
    # Nothing is left under any id the trial used.
    for uid in (user.user_id, f"{user.user_id}@users.example"):
        assert usage.ACCUMULATOR.take(uid, wait=0) == []


# -- Amendment 2: a failed v2 trial's record --------------------------------

def test_a_failed_v2_trial_records_what_ran(tmp_path):
    """run_single_trial_v2: a consumer that raises fails the trial with
    the exception, and the record keeps the user id, the sessions and
    the probes that ran (the errored one unscored); no judge call."""
    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=1)
    o = orchestrator(dataset=str(path))
    o.generator.run_id = "r1"
    o._embed = False
    o.judge = MagicMock()
    locus = FakeLocus()
    real = locus.assistant.run

    def run_probe(question):
        if locus.assistant.probe_id.endswith("p2-privacy"):
            raise RuntimeError("search failed")
        return real(question)
    locus.assistant.run = run_probe

    def run_history_trial(user, variants=None, *, control=None,
                          recency_session=True):
        user = user.model_copy(update={"user_id": USER_ID})
        outcome = history.run_history(
            user, locus, VariantRunner(None, "kernel"), control=control)
        return user, outcome, "kernel"

    trial = o.run_single_trial(
        0, "kernel_shared", SimpleNamespace(
            run_history_trial=run_history_trial), method="kernel_shared")
    assert trial.failed is True
    assert trial.error_message == "RuntimeError: search failed"
    assert trial.user_id == USER_ID and len(trial.sessions) == 6
    deletion, privacy = trial.probe_results
    assert deletion.error is None and deletion.passed is not None
    assert privacy.passed is None
    assert privacy.error == "consumer raised RuntimeError: search failed"
    assert trial.deleted_memory_ids  # the revoke's deletes are recorded
    o.judge.evaluate.assert_not_called()
    again = TrialResult.model_validate_json(trial.model_dump_json())
    assert again.probe_results[1].error == privacy.error


# -- the native consumer's visible stored rows (native cap_bound) ------------

class NativeRulesConsumer(FakeConsumer):
    """The native consumer's own rules over the store
    (``native/sharing.py``): the rows of the partition it serves, only
    the visible ones unless ``check_visibility`` is off, and
    ``visibility_checked`` in its diagnostics. It writes its
    conversation through ``memory.write``, where V3 strips metadata."""

    def __init__(self, store, log, **options):
        super().__init__(store, log, **options)
        self.check_visibility = True
        self.memory = SimpleNamespace(write=self._write)

    def _write(self, messages, text, agent_name, metadata):
        return self.store.add(agent_name, text, metadata)

    def run(self, question):
        self.log.append(("probe", self.session, self.probe_id))
        rows = [r for r in self.store.rows.values()
                if in_partition(self.user_id, r["metadata"])
                and (not self.check_visibility
                     or visible(history.CONSUMER, r["metadata"]))]
        diagnostics = dict(block_diagnostics(rows, self.session,
                                             self.user_id),
                           visibility_checked=self.check_visibility)
        answer = self.answer(question)
        if self.store_conversation:
            self.memory.write(
                [{"role": "user", "content": question}],
                f"User: {question}\nAssistant: {answer}", history.CONSUMER,
                {"user_id": self.user_id, "session": self.session,
                 "provenance_event": self.probe_id,
                 "owner_agent": history.CONSUMER,
                 "sharing_policy": "private"})
        return {"result": answer, "injection_diagnostics": diagnostics,
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                "total_tokens": 15}}


@pytest.mark.parametrize("variants, control, partition, all_policies", [
    (None, None, "base", False),
    ({"assistant_agent": "V2"}, None, "alias", False),
    ({"assistant_agent": "V3"}, None, "base", True),
    (None, "no_visibility", "base", True),
])
def test_native_visible_rows_follow_the_consumers_partition_and_visibility(
        variants, control, partition, all_policies):
    """visible_stored_rows counts what the native consumer could fetch:
    the writers' rows in the partition it searched (a V2 consumer's is
    its rewritten id, which holds none of them) and, when it does not
    check visibility (V3, no_visibility), the private ones too; plus
    its own rows when the probe began (none since Amendment 3: a probe
    writes nothing). It used to count the writers' shared rows under
    the base id for every consumer."""
    locus = managed("native", consumer=NativeRulesConsumer)
    user = v2_user()
    _, outcome = run(locus, user, control=control, variants=variants)
    assert outcome.failure is None
    uid = user.user_id if partition == "base" else \
        f"{user.user_id}@users.example"
    listed = next(l for l in outcome.listings
                  if l["after"] == "history")["rows"]
    metadata = [r["metadata"] for name in history.WRITERS
                for r in listed.get(name, [])]
    expected = sum(1 for m in metadata if m.get("user_id") == uid and (
        all_policies or m.get("sharing_policy") == "shared"))
    shared_base = sum(1 for m in metadata if m.get("user_id") ==
                      user.user_id and m.get("sharing_policy") == "shared")
    if variants is None and control is None:
        assert expected == shared_base  # the reference count is unchanged
    elif all_policies:
        assert expected > shared_base  # the user's private fact
    else:
        assert expected == 0 < shared_base  # the V2 alias holds none
    results = history.score_turns(user, outcome, "native")
    for turn, result in zip(outcome.turns, results):
        assert result.diagnostics.visibility_checked is (not all_policies)
        assert result.visible_stored_rows == (
            expected + turn.consumer_rows_before)
        # The fake injects every row it can see, so its own count checks
        # both halves, its own rows (a V2 consumer's, under its alias)
        # included.
        assert result.visible_stored_rows == (
            result.diagnostics.injected_count)


# -- Amendment 3: a probe writes nothing ------------------------------------

def rows_by_agent(listing):
    return {name: sorted(str(r["memory_id"]) for r in rows)
            for name, rows in listing["rows"].items()}


@pytest.mark.parametrize("kind", ["kernel", "native", "replicated"])
def test_a_probe_turn_writes_nothing_in_every_locus(kind):
    """After the probes every agent holds the rows it held after the
    last session, and the consumer none (the kernel with
    ``auto_extract`` off, as v2 runs it)."""
    if kind == "kernel":
        kernel = FakeKernel()
        with kernel.patched():
            _, outcome = run(history.KernelLocus())
    else:
        _, outcome = run(managed(kind))
    assert outcome.failure is None
    assert len(outcome.turns) == 6
    before, after = outcome.listings[-2:]
    assert (before["after"], after["after"]) == ("history", "probes")
    assert rows_by_agent(after) == rows_by_agent(before)
    assert after["rows"][history.CONSUMER] == []


class StoringConsumer(FakeConsumer):
    """A consumer that stores its turn whatever the locus tells it."""

    @property
    def store_conversation(self):
        return True

    @store_conversation.setter
    def store_conversation(self, value):
        pass


@pytest.mark.parametrize("kind", ["kernel", "native", "replicated"])
def test_a_probe_turn_that_stores_a_row_fails_the_user(kind):
    """A kernel run with extraction on, or a consumer that writes
    anyway: the listing after the probes holds rows the history's did
    not, and the user fails; the probe turns stay recorded."""
    if kind == "kernel":
        kernel = FakeKernel(auto_extract=True)
        with kernel.patched():
            _, outcome = run(history.KernelLocus())
    else:
        _, outcome = run(managed(kind, consumer=StoringConsumer))
    assert outcome.failure == ("probe_writes: probe turns stored 6 rows "
                               "(6 assistant_agent)")
    assert len(outcome.turns) == 6


def test_the_agent_managed_locus_turns_the_write_off_for_probe_turns():
    seen = []

    class Recording(FakeConsumer):
        def run(self, question):
            seen.append(self.store_conversation)
            return super().run(question)
    locus = managed("native", consumer=Recording)
    _, outcome = run(locus)
    assert outcome.failure is None
    assert seen == [False] * 6
    # Restored for the consumer's next use outside the probes.
    assert locus.agents[history.CONSUMER].store_conversation is True


# -- Amendment 4: the audit reads the store ---------------------------------

def test_the_kernel_audit_reads_memory_audit_and_fails_at_its_limit():
    """KernelLocus.audit_rows lists the raw store through the kernel's
    ``GET <kernel>/memory/audit?user_id=`` (the configured kernel URL
    without one given), its rows as ``{memory_id, content,
    metadata}``; a reply at its limit fails the user, and an HTTP error
    raises."""
    from cerebrum.config.config_manager import config

    row = {"memory_id": "m1", "content": "We chat on Mattermost.",
           "metadata": {"owner_agent": "task_agent", "user_id": USER_ID},
           "score": None, "keywords": [], "tags": []}
    get = MagicMock(return_value=FakeResponse(
        {"user_id": USER_ID, "rows": [row], "at_limit": False}))
    with patch.object(requests, "get", get):
        rows = history.KernelLocus(kernel_url="http://kernel:9/").audit_rows(
            USER_ID)
    assert rows == [{"memory_id": "m1", "content": "We chat on Mattermost.",
                     "metadata": row["metadata"]}]
    assert get.call_args.args == ("http://kernel:9/memory/audit",)
    assert get.call_args.kwargs["params"] == {"user_id": USER_ID}
    with patch.object(requests, "get", get), \
            patch.object(config, "get_kernel_url",
                         return_value="http://configured:1"):
        history.KernelLocus().audit_rows(USER_ID)
    assert get.call_args.args == ("http://configured:1/memory/audit",)
    get.return_value = FakeResponse(
        {"user_id": USER_ID, "rows": [row], "at_limit": True})
    with patch.object(requests, "get", get), pytest.raises(
            history.LocusFailure,
            match=f"^listing_at_limit: audit of {USER_ID}$"):
        history.KernelLocus(kernel_url="http://kernel:9").audit_rows(USER_ID)
    get.return_value = FakeResponse({}, status=500)
    with patch.object(requests, "get", get), pytest.raises(
            requests.HTTPError):
        history.KernelLocus(kernel_url="http://kernel:9").audit_rows(USER_ID)


ALIAS_ID = f"{USER_ID}@users.example"


def plant_rows(store):
    """Rows the raw store holds and an owner's own listing does not all
    show: a shared row, another agent's private row, a carrier of a
    tombstoned value (the guard withholds it from its owner's own
    listing), a row of an agent outside the four, and a row under the
    rewritten id a V2 writer used. Returns their ids by kind."""
    store.forgotten[USER_ID] = ["Kestrel"]
    return {
        "shared": store.add("profile_agent", "My team chats on Mattermost.",
                            {"user_id": USER_ID, "sharing_policy": "shared"}),
        "private": store.add("task_agent", "Off the record: Ravelstone.",
                             {"user_id": USER_ID,
                              "sharing_policy": "private"}),
        "carrier": store.add("calendar_agent", "The retro is on Kestrel.",
                             {"user_id": USER_ID,
                              "sharing_policy": "shared"}),
        "outsider": store.add("other_agent", "An outsider's row.",
                              {"user_id": USER_ID,
                               "sharing_policy": "shared"}),
        "alias": store.add("task_agent", "Written under the alias.",
                           {"user_id": ALIAS_ID,
                            "sharing_policy": "shared"}),
    }


@pytest.mark.parametrize("kind", ["kernel", "replicated"])
def test_the_kernel_and_replicated_listings_are_the_raw_store(kind):
    """Amendment 4, "The audit reads the store": in the kernel and the
    replicated locus a listing is every row of every partition the
    agents used, of every agent, with no visibility rule and no
    tombstone guard, grouped by owner (``source`` "store"): another
    agent's private row, a carrier its owner's own listing withholds
    and a row of an agent outside the four are all in it, with their
    text. Through the owners' listings the carrier and the outsider's
    row would be missing."""
    ids = {name: {USER_ID} for name in history.AGENTS}
    ids["task_agent"].add(ALIAS_ID)
    stack = ExitStack()
    if kind == "kernel":
        kernel = FakeKernel()
        store, locus = kernel.store, history.KernelLocus()
        stack.enter_context(kernel.patched())
    else:
        locus = managed("replicated")
        store = locus.agents[history.CONSUMER].store
    planted = plant_rows(store)
    with stack:
        locus.start_user(USER_ID, None)
        listing = history._listing(locus, "history", ids)
        own = {name: {r["memory_id"] for r in
                      locus.lister(name).list_own_rows(USER_ID)}
               for name in history.AGENTS}
    assert listing["after"] == "history" and listing["source"] == "store"
    by_owner = {owner: [r["memory_id"] for r in rows]
                for owner, rows in listing["rows"].items()}
    assert by_owner == {
        "profile_agent": [planted["shared"]],
        "task_agent": [planted["private"], planted["alias"]],
        "calendar_agent": [planted["carrier"]],
        "assistant_agent": [],
        "other_agent": [planted["outsider"]],
    }
    carrier = listing["rows"]["calendar_agent"][0]
    assert carrier["content"] == "The retro is on Kestrel."
    assert set(carrier) == {"memory_id", "content", "metadata"}
    # The owner's own listing withholds the carrier (the guard).
    assert planted["carrier"] not in own["calendar_agent"]
    assert planted["private"] in own["task_agent"]
    if kind == "kernel":
        assert sorted(kernel.audits) == sorted({USER_ID, ALIAS_ID})


def test_native_listings_stay_each_owners_own():
    """Native lists each agent's own rows through its backend, which
    has no guard (``source`` "owner"): a row of an agent outside the
    four is in no listing."""
    locus = managed("native")
    store = locus.agents[history.CONSUMER].store
    planted = plant_rows(store)
    store.forgotten.clear()  # native keeps no tombstones
    locus.start_user(USER_ID, None)
    ids = {name: {USER_ID} for name in history.AGENTS}
    listing = history._listing(locus, "history", ids)
    assert listing["source"] == "owner"
    assert set(listing["rows"]) == set(history.AGENTS)
    listed = {r["memory_id"] for rows in listing["rows"].values()
              for r in rows}
    assert listed == {planted["shared"], planted["private"],
                      planted["carrier"]}


def test_revoked_value_rows_reports_a_carrier_the_guard_hides():
    """User 0's revoke through the kernel's forget (the fake's) deletes
    the fact's row and the echo, so nothing carries the value. A carrier
    planted afterwards, as one the forget missed, is withheld from its
    owner's own listing by the tombstone guard, but the listing reads
    the raw store, so ``revoked_value_rows`` reports it with its owner,
    event and value, from a row that holds its text. Read through the
    owners' listings it would be hidden, and "no carrier is left" would
    hold by construction."""
    kernel = FakeKernel()
    user = v2_user(0)
    [revoke] = [e for s in user.sessions for e in s["events"]
                if e["type"] == "revoke"]
    value = next(e["value"] for s in user.sessions for e in s["events"]
                 if e["event_id"] == revoke["target_event"])
    text = f"The retro is back on {value}."
    ids = {name: {USER_ID} for name in history.AGENTS}
    with kernel.patched():
        _, outcome = run(history.KernelLocus(), user)
        assert outcome.failure is None
        assert history.revoked_value_rows(user, outcome) == []
        planted = kernel.store.add("task_agent", text, {
            "user_id": USER_ID, "fact_key": "retro_tool",
            "provenance_event": "planted", "sharing_policy": "shared"})
        own = kernel.list_memories("task_agent", user_id=USER_ID)
        outcome.listings[-1] = history._listing(
            history.KernelLocus(), "probes", ids)
    assert planted not in {r["memory_id"] for r in
                           own["response"]["search_results"]}
    [carrier] = history.revoked_value_rows(user, outcome)
    expected = {
        "listing": "probes", "memory_id": planted,
        "owner_agent": "task_agent", "provenance_event": "planted",
        "fact_key": "retro_tool", "revoke_event": revoke["event_id"],
        "value": value}
    assert {key: carrier.get(key) for key in expected} == expected
    row = next(r for r in outcome.listings[-1]["rows"]["task_agent"]
               if r["memory_id"] == planted)
    assert row["content"] == text


def test_a_carriers_record_holds_its_text():
    """A carrier the forget missed "shows in ``revoked_value_rows`` with
    its text" (AIOS docs/DELETION_AND_SUPERSESSION.md, "The audit reads
    the store"; the function's docstring: "still shows here, with its
    text"), so a reader of the results sees what escaped (an echo, a
    Mem0 fold or rewording), not only its id. The record holds the
    row's stored content."""
    user = hand_built([
        {"session": 1, "writer": "profile_agent", "events": [
            statement("x1", "add", "pet", "Mochi")]},
        {"session": 4, "writer": "profile_agent", "events": [
            statement("x4", "revoke", "pet", target_event="x1")]},
    ])
    text = "I booked a vet visit for Mochi."
    outcome = history.HistoryOutcome(listings=[listed({
        "calendar_agent": [("r1", text, {"fact_key": "vet"})]})])
    [carrier] = history.revoked_value_rows(user, outcome)
    assert carrier["memory_id"] == "r1"
    assert carrier.get("content") == text


def test_a_kernel_revoke_forgets_the_echo_too():
    """User 0 has an echo: another writer's row of another slot with
    the revoked value. The kernel writers revoke through the user's
    forget, which deletes it with the fact's own rows; the revoke's
    ``deleted_ids`` hold it (so the reappearance check covers it) and
    ``found_ids`` only the slot's rows."""
    kernel = FakeKernel()
    user = v2_user(0)
    writer_of = {e["event_id"]: s["writer"] for s in user.sessions
                 for e in s["events"]}
    [scripted] = [e for s in user.sessions for e in s["events"]
                  if e["type"] == "revoke"]
    echo = next(e for s in user.sessions for e in s["events"]
                if e.get("echo_of"))
    assert writer_of[echo["event_id"]] != writer_of[scripted["event_id"]]
    with kernel.patched():
        _, outcome = run(history.KernelLocus(), user)
    assert outcome.failure is None
    [revoke] = [e for s in outcome.sessions for e in s.events
                if e["type"] == "revoke"]
    stored = {e["event_id"]: e["memory_ids"] for s in outcome.sessions
              for e in s.events if e.get("memory_ids")}
    assert revoke["found_ids"] == stored[scripted["target_event"]]
    assert revoke["deleted_ids"] == (revoke["found_ids"]
                                     + stored[echo["event_id"]])
    reasons = {(d["owner_agent"], d["reason"])
               for d in revoke["forget"]["deleted"]}
    assert reasons == {(writer_of[scripted["event_id"]], "fact_key"),
                       (writer_of[echo["event_id"]], "value")}
    assert history.deleted_ids(outcome) == revoke["deleted_ids"]
    assert history.reappeared_ids(outcome) == []


# -- Amendment 4: the controls ----------------------------------------------

@pytest.mark.parametrize("control", [None, "no_memory", "no_delete",
                                     "writer_scoped", "no_supersession"])
def test_the_writers_forget_scope_follows_the_control(control):
    """Under writer_scoped the writers revoke by their own list and
    delete (``forget_scope`` "writer"); under every other control, and
    none, through the user's forget ("user"), in the kernel and the
    replicated locus alike. no_delete stays its own switch."""
    want = "writer" if control == "writer_scoped" else "user"
    assert history.forget_scope(control) == want
    kernel = history.KernelLocus()
    kernel.start_user(USER_ID, control)
    replicated = managed("replicated")
    replicated.start_user(USER_ID, control)
    for locus in (kernel, replicated):
        for name in history.WRITERS:
            writer = locus.writer(name)
            assert writer.forget_scope == want, (locus, name)
            assert writer.delete_on_revoke is (control != "no_delete")
        locus.finish_user()


@pytest.mark.parametrize("control", ["writer_scoped", "no_supersession"])
def test_the_library_controls_are_refused_for_native(control):
    """writer_scoped and no_supersession switch the library's forget
    and supersession, which native does not run: the native locus
    refuses them before the history starts (a harness misuse), and the
    kernel and replicated loci run them."""
    assert control in history.CONTROLS
    assert control in history.LIBRARY_CONTROLS
    native = managed("native")
    with pytest.raises(ValueError, match=control):
        run(native, control=control)
    assert native.agents["profile_agent"].log == []  # nothing ran
    for locus in (FakeLocus(), managed("replicated")):
        _, outcome = run(locus, control=control)
        assert outcome.failure is None and len(outcome.turns) == 6


# -- Amendment 4: what the history left behind -------------------------------

def test_a_suppressed_write_is_no_extraction_failure():
    """A write the library suppressed (its rows carried a forgotten
    value and were swept) stored nothing on purpose: the extraction
    check skips it, and still reports another write that stored
    nothing."""
    locus = FakeLocus()
    user, outcome = run(locus)
    session = user.sessions[2]
    first, second = session["events"][:2]
    listing = outcome.listings[2]["rows"][session["writer"]]
    listing[:] = [r for r in listing if r["metadata"]["provenance_event"]
                  != first["event_id"]]
    assert first["event_id"] in history.extraction_failure(user, outcome,
                                                           True)
    record = next(e for e in outcome.sessions[2].events
                  if e["event_id"] == first["event_id"])
    record["suppressed"] = True
    assert history.extraction_failure(user, outcome, True) is None
    listing[:] = [r for r in listing if r["metadata"]["provenance_event"]
                  != second["event_id"]]
    failure = history.extraction_failure(user, outcome, True)
    assert second["event_id"] in failure
    assert first["event_id"] not in failure


class FoldingKernel(FakeKernel):
    """The kernel whose Mem0 extraction folds a fact's value into one
    later write's row, as gpt-4o folded the revoked codename into user
    19's docs wiki row in the Amendment 4 smoke (``s15``)."""

    def __init__(self, event_id=None, value=None, **kwargs):
        super().__init__(**kwargs)
        self.event_id, self.value = event_id, value

    def create_memory(self, agent_name, content=None, metadata=None,
                      base_url=None, **kwargs):
        if (metadata or {}).get("provenance_event") == self.event_id:
            content = f"{content} That is for {self.value}."
        return super().create_memory(agent_name, content, metadata,
                                     base_url, **kwargs)


def write_before_its_sessions_revoke(user):
    """The first write of a session that later revokes a fact, and the
    revoked value; ``(None, None)`` for a user without one."""
    values = {e["event_id"]: e.get("value") for s in user.sessions
              for e in s["events"]}
    for s in user.sessions:
        kinds = [e["type"] for e in s["events"]]
        if "revoke" not in kinds:
            continue
        at = kinds.index("revoke")
        writes = [e for e in s["events"][:at]
                  if e["type"] in history.WRITE_EVENTS]
        if writes:
            return writes[0], values[s["events"][at]["target_event"]]
    return None, None


def test_a_write_its_sessions_forget_took_is_no_extraction_failure():
    """Mem0 can fold a fact's value into the next row the same writer
    stores, and the forget deletes that row as a carrier (Amendment 4).
    When the write comes earlier in the revoke's own session, the
    listing after the session holds no row of it. The write stored a
    row, so it is no extraction failure, and its record names the row
    its session deleted (``forgotten_ids``). In ``s15`` the check
    failed user 19 for this (``u019-e08``)."""
    user = next(u for u in map(v2_user, range(5))
                if write_before_its_sessions_revoke(u)[0])
    write, value = write_before_its_sessions_revoke(user)
    kernel = FoldingKernel(write["event_id"], value)
    with kernel.patched():
        _, outcome = run(history.KernelLocus(), user)
    assert outcome.failure is None
    session = next(s for s in outcome.sessions for e in s.events
                   if e["event_id"] == write["event_id"])
    record = next(e for e in session.events
                  if e["event_id"] == write["event_id"])
    [named] = record["reported_ids"]
    assert record["memory_ids"] == [] and record["stored_rows"] == 0
    assert record["forgotten_ids"] == [named]
    [revoke] = [e for e in session.events if e["type"] == "revoke"]
    assert (named, "value") in {(d["memory_id"], d["reason"])
                               for d in revoke["forget"]["deleted"]}
    assert history.extraction_failure(user, outcome, True) is None
    # No other write lost a row to its own session.
    assert all(not e.get("forgotten_ids") for s in outcome.sessions
               for e in s.events if e is not record)


@pytest.mark.parametrize("removal,excused", [
    ("deleted in its session", True),
    ("swept in its session", True),
    ("no reported id", False),
    ("deleted in a later session", False),
    ("one of two reported ids", False),
])
def test_only_its_own_sessions_removal_of_every_named_row_excuses_a_write(
        removal, excused):
    """The extraction check excuses a write that was not suppressed and
    that the listing after its session shows empty only when its reply
    named rows and its own session deleted or swept every one. Such a
    write whose reply named no row failed silently, whatever else the
    session deleted; a later
    session's delete cannot explain the earlier listing; and a named
    row that nothing removed never reached the store."""
    user, outcome = run(FakeLocus())
    record = outcome.sessions[2]  # session 3: no revoke
    event = user.sessions[2]["events"][0]
    rows = outcome.listings[2]["rows"][record.writer]
    rows[:] = [r for r in rows if r["metadata"]["provenance_event"]
               != event["event_id"]]
    write = next(e for e in record.events
                 if e["event_id"] == event["event_id"])
    [named] = write["reported_ids"]
    if removal == "deleted in its session":
        record.deleted_ids.append(named)
    elif removal == "swept in its session":
        write["swept_ids"] = [named]
    elif removal == "no reported id":
        write["reported_ids"] = []
        record.deleted_ids.append("m-another-row")
    elif removal == "deleted in a later session":
        outcome.sessions[3].deleted_ids.append(named)
    else:
        write["reported_ids"].append("m-never-stored")
        record.deleted_ids.append(named)
    failure = history.extraction_failure(user, outcome, True)
    assert (failure is None) is excused
    if not excused:
        assert event["event_id"] in failure


def statement(event_id, kind, fact_key, value=None, aliases=(), **extra):
    """A hand-built dataset event."""
    return {"event_id": event_id, "type": kind, "fact_key": fact_key,
            "value": value, "aliases": list(aliases), **extra}


def hand_built(sessions):
    """v2_user(0) with these sessions and no probes."""
    return v2_user(0).model_copy(update={"sessions": sessions,
                                         "probes": []})


def listed(owner_rows):
    """One "history" listing of ``{owner: [(id, text, metadata)]}``."""
    return {"after": "history", "rows": {
        owner: [{"memory_id": i, "content": text, "metadata": metadata}
                for i, text, metadata in rows]
        for owner, rows in owner_rows.items()}}


def test_revoked_value_rows_checks_every_statement_of_the_revoked_slot():
    """A revoke forgets the fact, so a row that carries the value of
    any of its statements is a carrier: the add's, a contradiction's,
    an update's or one of its aliases (Amendment 4). Before, only the
    add's (or the private statement's) value was checked. The dataset
    revokes no restated slot, so the user is built by hand."""
    user = hand_built([
        {"session": 1, "writer": "profile_agent", "events": [
            statement("x1", "add", "pet", "Mochi")]},
        {"session": 2, "writer": "task_agent", "events": [
            statement("x2", "contradict", "pet", "Biscuit",
                      target_event="x1")]},
        {"session": 4, "writer": "profile_agent", "events": [
            statement("x3", "update", "pet", "Pepper Jack", ["Pepper"],
                      target_event="x1"),
            statement("x4", "revoke", "pet", target_event="x1")]},
    ])
    outcome = history.HistoryOutcome(listings=[listed({
        "calendar_agent": [
            ("r1", "I booked a vet visit for Pepper.", {"fact_key": "vet"}),
            ("r2", "Biscuit loves the park.", {"fact_key": "park"}),
            ("r3", "Nothing to see here.", {"fact_key": "misc"})],
        "task_agent": [("r4", "Mochi again.", {"fact_key": "misc"})]})])
    found = {r["memory_id"]: (r["owner_agent"], r["value"])
             for r in history.revoked_value_rows(user, outcome)}
    assert found == {"r1": ("calendar_agent", "Pepper Jack"),
                     "r2": ("calendar_agent", "Biscuit"),
                     "r4": ("task_agent", "Mochi")}


@pytest.mark.parametrize("index", range(5))
def test_retired_events_are_the_earlier_statements_of_a_restated_fact(
        index):
    """An update retires the add, a contradiction by another writer
    retires the original statement, and a fact stated once (recall,
    deletion, the echo, the private fact, fillers) is never retired: in
    the dataset, exactly the first source event of the recency and the
    contradiction probe."""
    user = v2_user(index)
    probes = {p["type"]: p for p in user.probes}
    assert sorted(history.retired_events(user)) == sorted(
        [probes["recency"]["source_events"][0],
         probes["contradiction"]["source_events"][0]])


def test_retired_events_follow_the_session_order_not_the_list():
    """Statements count in session order, as they were stated: a list
    that holds session 4 before session 1 still retires the session-1
    add, not the session-4 update; a base event states nothing."""
    user = hand_built([
        {"session": 4, "writer": "profile_agent", "events": [
            statement("x3", "update", "pet", "Pepper", target_event="x1")]},
        {"session": 1, "writer": "profile_agent", "events": [
            statement("x0", "base", "base_profile"),
            statement("x1", "add", "pet", "Mochi"),
            statement("x2", "add", "city", "Tallinn")]},
        {"session": 2, "writer": "task_agent", "events": [
            statement("x5", "base", "base_profile")]},
    ])
    assert history.retired_events(user) == ["x1"]


def test_retired_rows_list_the_earlier_statements_rows_with_their_marks():
    """retired_rows: the rows of the retired statements in the listing
    after the history, of every agent, each with its mark
    (``superseded_by``; None when unmarked); the later statements' rows
    are not listed."""
    user = v2_user(0)
    probes = {p["type"]: p for p in user.probes}
    recency_add = probes["recency"]["source_events"][0]
    original = probes["contradiction"]["source_events"][0]
    _, outcome = run(FakeLocus(), user)
    rows = {r["metadata"]["provenance_event"]: (owner, r)
            for l in outcome.listings if l["after"] == "history"
            for owner, found in l["rows"].items() for r in found}
    marked = dict(rows[recency_add][1],
                  metadata=dict(rows[recency_add][1]["metadata"],
                                superseded_by=probes["recency"][
                                    "target_event"]))
    history_listing = next(l for l in outcome.listings
                           if l["after"] == "history")
    owner = rows[recency_add][0]
    history_listing["rows"][owner] = [
        marked if r["memory_id"] == marked["memory_id"] else r
        for r in history_listing["rows"][owner]]
    found = {r["provenance_event"]: r
             for r in history.retired_rows(user, outcome)}
    assert set(found) == {recency_add, original}
    assert found[recency_add] == {
        "memory_id": marked["memory_id"], "owner_agent": owner,
        "provenance_event": recency_add,
        "fact_key": probes["recency"]["slot"],
        "superseded_by": probes["recency"]["target_event"]}
    assert found[original]["superseded_by"] is None
    assert found[original]["owner_agent"] == rows[original][0]


def test_probe_results_carry_the_retired_rows_in_their_block():
    """``retired_in_block``, from the dataset (Amendment 4): each
    probe's lists exactly the injected rows of the retired statements.
    The fake's block holds every row of the user, so every probe's
    holds the rows of both retired statements (the recency add and the
    contradicted statement)."""
    user = v2_user(0)
    _, outcome = run(FakeLocus(), user)
    retired = set(history.retired_events(user))
    results = history.score_turns(user, outcome, "kernel")
    assert len(results) == 6
    for turn, result in zip(outcome.turns, results):
        injected = {str(r["memory_id"]): r["provenance_event"]
                    for r in turn.diagnostics["injected_memories"]}
        assert result.retired_in_block == [
            memory_id for memory_id, event in injected.items()
            if event in retired]
        assert {injected[i] for i in result.retired_in_block} == retired
