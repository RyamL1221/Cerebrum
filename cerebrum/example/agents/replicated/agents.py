"""Agents that run the kernel's memory pipeline themselves
(docs/REPLICATED_LOGIC.md in AIOS).

Each agent builds its own ``MemoryPipeline`` over its own provider
client, with its own write barrier and identity resolver, and does what
the kernel does for it in the kernel conditions: the writers upsert
their memory as the kernel writers' SDK calls do, and the assistant
injects the block and writes the conversation as the kernel's injector
and extractor do. The kernel serves the LLM calls only: no agent here
makes a kernel memory call.

Benchmark v2 (docs/BENCHMARK_V2.md): the writers run scripted sessions
(``shared_memory_utils.run_v2_session``) and revoke a fact through the
library's ``MemoryPipeline.forget`` (Amendment 4), or, under the
``writer_scoped`` control, through ``MemoryPipeline.list_own`` and
``delete``: the code the kernel runs for its forget, list and delete
requests. A store's agents share its tombstones, a SQLite file in the
store (``tombstones.sqlite``), as the kernel's requests share the
kernel's. The assistant passes the current session to
``MemoryPipeline.inject`` and stamps its conversation note.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional

from cerebrum.config.config_manager import config
from cerebrum.example.agents.calendar_agent.agent import CalendarAgent
from cerebrum.example.agents.profile_agent.agent import ProfileAgent
from cerebrum.example.agents.replicated import library
from cerebrum.example.agents.shared_memory_utils import (
    FIELD_STRUCTURED,
    MEMORY_TYPE_CALENDAR,
    MEMORY_TYPE_PROFILE,
    MEMORY_TYPE_TASK_CONTEXT,
    POLICY_PRIVATE,
    POLICY_SHARED,
    V2_LIST_LIMIT,
    build_memory_metadata,
    listed_rows,
    parse_v2_session,
    require_user_id,
    run_v2_session,
    structured,
)
from cerebrum.example.agents.task_agent.agent import TaskAgent
from cerebrum.llm.apis import llm_chat
from cerebrum.utils import usage

# The harness's backend names and the kernel's provider types.
BACKENDS = {"mem0": "mem0", "inhouse": "in-house", "graphiti": "graphiti"}
STORE_ROOT = os.environ.get(
    "CEREBRUM_REPLICATED_MEMORY_DIR", ".replicated_memory"
)
# The SDK's search_memories default, which the kernel writers use.
WRITER_SEARCH_K = 5


def store_root(backend: str) -> str:
    """The condition's store for ``backend``: its Chroma data, Mem0's
    history file (``history.db``, next to ``chroma``: the provider puts
    it there) and its tombstones (``tombstones.sqlite``)."""
    root = os.path.abspath(os.path.join(STORE_ROOT, backend))
    os.makedirs(root, exist_ok=True)
    return root


def store_config(
    backend: str, embedding: Dict[str, Any], backend_llm: Dict[str, Any],
    backend_extraction: bool = False,
) -> Dict[str, Any]:
    """The ``memory:`` sections a provider is configured from, with the
    condition's own store in place of the kernel's.

    ``backend_extraction`` is the kernel's (``/memory/config``): with it
    Mem0 writes with ``infer=True`` and the pinned ``memory.backend_llm``,
    as the kernel's Mem0 does. Without it Mem0 still needs an LLM to
    construct (``mem0ai`` 2.0.2 builds its default OpenAI client at once
    and wants a key), so it gets the same one, never called.
    """
    root = store_root(backend)
    mem0 = {"vector_store": {"provider": "chroma", "config": {
        "collection_name": "mem0_memories",
        "path": os.path.join(root, "chroma"),
    }}}
    if backend_extraction:
        mem0["infer"] = True
    if backend_llm.get("provider") and backend_llm.get("model"):
        mem0["llm"] = usage.mem0_llm_config(backend_llm)
    return {
        "embedding": embedding,
        "backend_llm": backend_llm,
        "mem0": mem0,
        "chroma_inhouse": {"path": os.path.join(root, "chroma")},
    }


class ReplicatedMemory:
    """One agent's own pipeline: provider client, settings, barrier and
    identity resolver, built from the kernel's ``/memory/config``."""

    def __init__(
        self, backend: str, kernel_config: Dict[str, Any],
        provider: Any = None, tombstones_path: Optional[str] = None,
    ):
        """``provider`` replaces the backend's client (tests).
        ``tombstones_path`` replaces the store's tombstone file
        (tests); every agent of a store must use the same one."""
        if backend not in BACKENDS:
            raise ValueError(f"unknown replicated backend {backend!r}")
        pipeline = library.load()
        from aios.memory.providers.factory import (
            ProviderFactory,
            provider_config,
        )

        provider_type = BACKENDS[backend]
        self.backend = backend
        if backend in ("mem0", "graphiti"):
            # Mem0's and Graphiti's extraction calls go through LiteLLM;
            # count them per trial, as the native agents and the kernel
            # do. Graphiti's store is the shared Neo4j database, in the
            # users' own groups (docs/GRAPHITI_BACKEND.md); its
            # tombstones are still the store root's file.
            usage.install_litellm_logger()
        self.provider = provider or ProviderFactory.create(
            provider_type,
            provider_config(
                provider_type,
                store_config(
                    backend, kernel_config["embedding"],
                    kernel_config.get("backend_llm") or {},
                    bool(kernel_config.get("backend_extraction"))
                    and backend == "mem0",
                ),
            ),
        )
        self.settings = pipeline.PipelineSettings.from_memory_config(
            kernel_config["pipeline"]
        )
        # The store's tombstones, shared by its agents through the file
        # (read on every check). Not the kernel's file, which
        # /memory/config reports outside ``pipeline``: a replicated
        # store keeps its own.
        self.tombstones_path = tombstones_path or os.path.join(
            store_root(backend), "tombstones.sqlite"
        )
        self.tombstones = pipeline.TombstoneStore(self.tombstones_path)
        # Its own barrier and resolver (the library's defaults).
        # The provider's own LLM and embedding calls count to the user
        # they serve (no module of the library imports the SDK: the tag
        # is passed).
        self.pipeline = pipeline.MemoryPipeline(
            self.provider, self.settings, tombstones=self.tombstones,
            usage_tag=usage.tagged,
        )
        self.version = pipeline.PIPELINE_VERSION
        self.library = pipeline
        self.backend_extraction = bool(
            getattr(self.provider, "backend_extraction", False)
        )

    # The library's owner-only listing and delete (benchmark v2), through
    # the agent's current pipeline (a variant may have replaced it).

    def list_own(self, agent_name: str, user_id: str) -> List[dict]:
        """Every row ``agent_name`` owns for ``user_id``
        (``MemoryPipeline.list_own``), up to ``V2_LIST_LIMIT``."""
        return self.pipeline.list_own(
            agent_name, user_id, top_k=V2_LIST_LIMIT
        )

    def delete(self, agent_name: str, user_id: str, memory_id: str) -> bool:
        """Delete one of ``agent_name``'s rows (``MemoryPipeline.delete``):
        False when it is missing or not the agent's."""
        return self.pipeline.delete(agent_name, user_id, memory_id)

    def forget(
        self, agent_name: str, user_id: str, fact_key: str,
    ) -> Dict[str, Any]:
        """The user's forget of a fact (``MemoryPipeline.forget``): its
        report (Amendment 4)."""
        return self.pipeline.forget(agent_name, user_id, fact_key)


class _ReplicatedWriter:
    """Extracts like the kernel conditions' writer, then upserts through
    its own pipeline with the kernel writer's logic: search its own
    memories of the user, update those of its type, or create one."""

    memory_type = ""
    query_prefix = ""
    extractor_class: Any = None

    def __init__(self, agent_name: str, memory: ReplicatedMemory):
        self.agent_name = agent_name
        self.memory = memory
        self.extractor = self.extractor_class(agent_name)
        self.user_id: Optional[str] = None
        self.llms: Optional[list] = None
        self.share_memory = True
        # False is the no_delete control: a v2 revoke finds the fact's
        # rows and deletes none.
        self.delete_on_revoke = True
        # Metadata the deployment adds to every write (Subtask 10).
        self.extra_metadata: Dict[str, Any] = {}

    def _upsert(
        self, user_id: str, content: str, fields_json: str,
    ) -> tuple:
        """``(metadata written, rows stored)``. A create stores no row
        when the backend's extraction kept nothing (the library returns
        an empty id)."""
        pipeline = self.memory.pipeline
        rows, _ = pipeline.retrieve(
            self.agent_name, user_id, f"{self.query_prefix} {user_id}",
            k=WRITER_SEARCH_K, include_shared=False,
        )
        matching = [
            row for row in rows
            if (row.get("metadata") or {}).get("memory_type")
            == self.memory_type
        ]
        if matching:
            for row in matching:
                pipeline.update(
                    self.agent_name, user_id, row["memory_id"],
                    content,
                    {"user_id": user_id, FIELD_STRUCTURED: fields_json,
                     **self.extra_metadata},
                )
            return dict(matching[0]["metadata"]), len(matching)
        metadata = build_memory_metadata(
            owner_agent=self.agent_name,
            user_id=user_id,
            memory_type=self.memory_type,
            sharing_policy=(
                POLICY_SHARED if self.share_memory else POLICY_PRIVATE
            ),
            **{FIELD_STRUCTURED: fields_json},
            **self.extra_metadata,
        )
        note = self.memory.library.note_from_request(
            {"content": content, "metadata": metadata}
        )
        memory_id = pipeline.write(self.agent_name, user_id, note)
        return dict(note.metadata), 1 if memory_id else 0

    def run(self, task_input: str) -> dict:
        """Extract and validate like the kernel writer (the same
        ``extract``), then upsert the shared rendering; store nothing
        when the extraction fails. A benchmark v2 session
        (``{"v2_session": ...}``) is written event by event instead, with
        no extraction (``shared_memory_utils.run_v2_session``)."""
        session = parse_v2_session(task_input)
        if session is not None:
            return run_v2_session(
                self, session, self.memory_type,
                write=self._v2_create, list_rows=self._v2_list,
                delete=self._v2_delete, forget=self._v2_forget,
            )
        self.extractor.llms = self.llms
        extraction = self.extractor.extract(task_input)
        report = extraction.report()
        if extraction.failed:
            return {
                "agent_name": self.agent_name,
                "result": f"Writer failed: {extraction.problems}",
                "written": None,
                "token_usage": self.extractor.token_usage,
                **report,
            }
        content = extraction.text
        written, stored = self._upsert(
            self.user_id, content, structured(extraction.fields)
        )
        return {
            "agent_name": self.agent_name,
            "result": content,
            "written": written,
            "stored_rows": stored,
            "token_usage": self.extractor.token_usage,
            **report,
        }

    # -- benchmark v2 (docs/BENCHMARK_V2.md) ---------------------------

    def _v2_create(
        self, content: str, metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Store one v2 row as the kernel stores a create request: the
        request's note (``note_from_request``) through the agent's
        current pipeline, which fills the required metadata into it.

        Once the row is stored, ``metadata`` holds the metadata it was
        stored with, which ``run_v2_session`` records in ``written``
        (as v1's ``_upsert`` returns ``note.metadata``). The note
        shares the dict until a variant's write replaces the note's
        metadata with its own copy (``variants.base``): a V3 row is
        stored with the library's owner and private default, and is
        recorded so, not as the shared row it was sent as. A write
        that raises is not copied back, and ``run_v2_session`` does
        not record it; without a variant the library may already have
        filled its defaults (``created_at``) into ``metadata``.

        Returns ``{memory_id, metadata}``, the kernel's reply shape:
        ``metadata`` is what the write did next (the ids it swept and
        retired, the values it lifted, ``suppressed``; Amendment 4)."""
        note = self.memory.library.note_from_request(
            {"content": content, "metadata": metadata}
        )
        outcome: Dict[str, Any] = {}
        memory_id = self.memory.pipeline.write(
            self.agent_name, self.user_id, note, outcome=outcome,
        )
        # A snapshot first: without a variant the note's metadata is
        # ``metadata`` itself, which clear() would empty.
        stored = dict(note.metadata or {})
        metadata.clear()
        metadata.update(stored)
        return {"memory_id": memory_id, "metadata": outcome}

    def _v2_list(self, user_id: str) -> List[dict]:
        return self.memory.list_own(self.agent_name, user_id)

    def _v2_delete(self, user_id: str, memory_id: str) -> bool:
        return self.memory.delete(self.agent_name, user_id, memory_id)

    def _v2_forget(self, user_id: str, fact_key: str) -> Dict[str, Any]:
        return self.memory.forget(self.agent_name, user_id, fact_key)

    def list_own_rows(self, user_id: Optional[str] = None) -> List[dict]:
        """The rows this agent owns for ``user_id`` (default: its
        ``user_id``) as ``{memory_id, content, metadata}``, up to
        ``V2_LIST_LIMIT``, by the call a revoke lists with. Raises
        ``WriterError`` when the listing fails."""
        uid = require_user_id(user_id or self.user_id)
        return listed_rows(self._v2_list(uid))


class ReplicatedProfileAgent(_ReplicatedWriter):
    memory_type = MEMORY_TYPE_PROFILE
    query_prefix = "profile"
    extractor_class = ProfileAgent


class ReplicatedTaskAgent(_ReplicatedWriter):
    memory_type = MEMORY_TYPE_TASK_CONTEXT
    query_prefix = "task context"
    extractor_class = TaskAgent


class ReplicatedCalendarAgent(_ReplicatedWriter):
    """Benchmark v2's calendar writer; v2 sessions only: any other input
    fails the writer (``CalendarAgent.extract``)."""

    memory_type = MEMORY_TYPE_CALENDAR
    query_prefix = "calendar"
    extractor_class = CalendarAgent


def _load_assistant_prompt() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assistant_agent", "config.json",
    )
    with open(path) as handle:
        return "".join(json.load(handle).get("description", []))


class ReplicatedAssistantAgent:
    """Sends the kernel AssistantAgent's messages, with the block its own
    pipeline injects, and writes the conversation turn afterwards.

    Benchmark v2 sets ``session`` (the current session, which the
    block's session ages count from) and ``probe_id`` per probe; the
    conversation note then carries ``session`` and ``provenance_event``
    (the probe id). Since Amendment 3 a probe writes nothing: the
    harness sets ``store_conversation`` to False for its probe turns."""

    def __init__(self, agent_name: str, memory: ReplicatedMemory):
        self.agent_name = agent_name
        self.memory = memory
        self.system_prompt = _load_assistant_prompt()
        self.user_id: Optional[str] = None
        self.llms: Optional[list] = None
        self.extra_metadata: Dict[str, Any] = {}
        self.session: Optional[int] = None
        self.probe_id: Optional[str] = None
        # False: the turn is not stored (a benchmark v2 probe).
        self.store_conversation = True

    def list_own_rows(self, user_id: Optional[str] = None) -> List[dict]:
        """The conversation rows this agent owns for ``user_id``
        (default: its ``user_id``) as ``{memory_id, content,
        metadata}``, up to ``V2_LIST_LIMIT``
        (``MemoryPipeline.list_own``). Raises ``WriterError`` when the
        listing fails."""
        uid = require_user_id(user_id or self.user_id)
        return listed_rows(self.memory.list_own(self.agent_name, uid))

    def run(self, task_input: str) -> dict:
        """Answer one query. The timing keys are the kernel's; the
        backend's own token usage for the trial, writers included, is
        read from this process's accumulator after the conversation
        write."""
        user_id = self.user_id
        pipeline = self.memory.pipeline
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task_input},
        ]
        started = time.perf_counter()
        # The current session goes to the library only when set, so a
        # v1 call is made as before.
        session = {} if self.session is None else {"session": self.session}
        messages, diagnostics = pipeline.inject(
            self.agent_name, messages, user_id=user_id, **session
        )
        injected = time.perf_counter()
        response = llm_chat(
            agent_name=self.agent_name,
            messages=messages,
            base_url=config.get_kernel_url(),
            llms=self.llms,
            user_id=user_id,
        )
        answer = response["response"]["response_message"] if response else ""
        answered = time.perf_counter()

        # As the kernel's extractor does: the pair, private, in the
        # resolved user's scope; nothing when the turn is not stored.
        if self.store_conversation and task_input and answer:
            note = self.memory.library.conversation_note(
                self.agent_name, task_input, str(answer),
                diagnostics.get("resolved_user_id"),
            )
            note.metadata.update(self.extra_metadata)
            # Benchmark v2: the turn's session (as the kernel's
            # extractor stamps it) and the probe it answered.
            if self.session is not None:
                note.metadata["session"] = self.session
            if self.probe_id is not None:
                note.metadata["provenance_event"] = self.probe_id
            pipeline.write(self.agent_name, None, note)
        written = time.perf_counter()
        records = usage.ACCUMULATOR.take(user_id)

        llm_timing = (response or {}).get("llm_timing") or {}
        stages = {
            key: diagnostics.get(key) or 0.0
            for key in ("barrier_wait_ms", "search_ms", "select_ms",
                        "format_ms")
        }
        wait = llm_timing.get("schedule_wait_ms")
        diagnostics.update({
            **stages,
            "schedule_wait_ms": wait,
            "kernel_overhead_ms": sum(stages.values()) + (wait or 0.0),
            "llm_ms": llm_timing.get("llm_ms"),
        })
        return {
            "agent_name": self.agent_name,
            "result": answer,
            "rounds": 1,
            "injection_diagnostics": diagnostics,
            "token_usage": (response or {}).get("token_usage"),
            "llm_timing": llm_timing,
            "decoding": (response or {}).get("decoding"),
            "pipeline_version": self.memory.version,
            "backend_usage": {
                "backend_llm_tokens": usage.summarize(
                    records, usage.BACKEND_EXTRACTION
                ),
                "embedding_tokens": usage.summarize(records, usage.EMBEDDING),
                "records": records,
            },
            "timing": {
                "retrieve_seconds": injected - started,
                "llm_seconds": answered - injected,
                "write_seconds": written - answered,
            },
        }
