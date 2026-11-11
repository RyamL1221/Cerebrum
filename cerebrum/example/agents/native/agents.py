"""Agents that manage their own memory (docs/NATIVE_USAGE.md in AIOS).

``backend`` is ``"mem0"`` (the ``mem0`` SDK, used as its documentation
shows), ``"inhouse"`` (Chroma, by the minimal convention in the spec) or
``"graphiti"`` (Graphiti on Neo4j, as its documentation shows; Subtask
16, docs/NATIVE_USAGE.md "native_graphiti").
The kernel serves the LLM calls only: no agent here makes a kernel memory
call. Each agent holds its own backend client.

Benchmark v2 (docs/BENCHMARK_V2.md): the writers run scripted sessions
(``shared_memory_utils.run_v2_session``) and delete a revoked fact's
rows through the backend's documented calls (``NativeMemory.list_own``
and ``delete``); the assistant prints session ages in its block when
the kernel's recency counts sessions, and stamps its conversation row.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cerebrum.config.config_manager import config
from cerebrum.example.agents.calendar_agent.agent import CalendarAgent
from cerebrum.example.agents.native import backends
from cerebrum.example.agents.native.sharing import (
    PRIVATE,
    SHARED,
    in_partition,
    memory_metadata,
    visible,
)
from cerebrum.example.agents.profile_agent.agent import ProfileAgent
from cerebrum.example.agents.shared_memory_utils import (
    FIELD_STRUCTURED,
    MEMORY_TYPE_CALENDAR,
    V2_LIST_LIMIT,
    listed_rows,
    parse_v2_session,
    require_user_id,
    run_v2_session,
    structured,
)
from cerebrum.example.agents.task_agent.agent import TaskAgent
from cerebrum.llm.apis import llm_chat
from cerebrum.utils import usage

BACKENDS = ("mem0", "inhouse", "graphiti")
COSINE = {"hnsw": {"space": "cosine"}}


def session_age(row_session: Any, current_session: Any) -> Optional[str]:
    """``"this session"``, ``"1 session ago"`` or ``"N sessions ago"``:
    the current session minus the row's, worded as the kernel's
    formatter words it. ``None`` (no age) when either is not an integer
    (a bool is not), or the row's session is after the current one."""
    def is_session(value):
        return isinstance(value, int) and not isinstance(value, bool)

    if not (is_session(row_session) and is_session(current_session)):
        return None
    sessions = current_session - row_session
    if sessions < 0:
        return None
    if sessions == 0:
        return "this session"
    return f"{sessions} session{'' if sessions == 1 else 's'} ago"


class NativeMemory:
    """One agent's own handle on the condition's store."""

    def __init__(self, backend: str, settings: backends.NativeSettings):
        if backend not in BACKENDS:
            raise ValueError(f"unknown native backend {backend!r}")
        self.backend = backend
        self.settings = settings
        # Mem0 (infer=True) and Graphiti extract facts from every write.
        self.backend_extraction = backend in ("mem0", "graphiti")
        if backend == "mem0":
            self.mem0 = backends.mem0_client(settings)
        elif backend == "graphiti":
            self.runner, self.graphiti = backends.graphiti_client(settings)
            # Episodes this handle deleted: a row of one went with it.
            self._removed: set = set()
        else:
            self.chroma = backends.chroma_client()
            self.embed = backends.Embedder(settings.embedding)

    def _collection(self, user_id: str):
        return self.chroma.get_or_create_collection(
            name=backends.collection_name(user_id),
            configuration=COSINE,
            embedding_function=None,
        )

    def write(
        self, messages: List[Dict[str, str]], text: str,
        agent_name: str, metadata: Dict[str, Any],
    ) -> List[str]:
        """Store one memory: Mem0 extracts facts from ``messages``; the
        in-house store keeps ``text`` verbatim. The backend's LLM and
        embedding calls count to the user's trial. Returns the ids of
        the rows the write stored: Mem0's extracted facts (none when its
        extraction failed or found nothing; Mem0 does not raise), else
        the one new row's."""
        user_id = metadata["user_id"]
        with usage.tagged(user_id):
            return self._write(messages, text, agent_name, metadata, user_id)

    def _write(self, messages, text, agent_name, metadata, user_id) -> list:
        if self.backend == "graphiti":
            return self.runner.run(
                self._graphiti_write, messages, text, agent_name, metadata,
                user_id)
        if self.backend == "mem0":
            result = self.mem0.add(
                messages, user_id=user_id, agent_id=agent_name,
                metadata=metadata, infer=True,
            )
            rows = result.get("results") if isinstance(result, dict) else None
            # One entry per row, so a count of the ids is the old count.
            return [
                row.get("id") if isinstance(row, dict) else None
                for row in rows or []
            ]
        else:
            memory_id = str(uuid.uuid4())
            self._collection(user_id).add(
                ids=[memory_id],
                documents=[text],
                embeddings=[self.embed(text)],
                metadatas=[metadata],
            )
            return [memory_id]

    # -- Graphiti (docs/NATIVE_USAGE.md, "native_graphiti") -------------

    async def _graphiti_write(self, messages, text, agent_name, metadata,
                              user_id) -> list:
        """One episode: the turn as the documented ``role: message``
        lines, the agent's metadata as JSON in ``source_description``
        (Graphiti keeps no metadata). Returns a row id per fact the
        episode produced or restated (``<fact>:<episode>``)."""
        from graphiti_core.nodes import EpisodeType

        lines = [f"{m['role']}: {m['content']}" for m in messages
                 if m.get("content")]
        group = backends.graphiti_group(user_id)
        async with self.runner.lock(group):
            result = await self.graphiti.add_episode(
                name=f"{agent_name}:{metadata.get('memory_type', '')}:"
                     f"{uuid.uuid4()}",
                episode_body="\n".join(lines) or f"user: {text}",
                source=EpisodeType.message,
                source_description=json.dumps(metadata, default=str),
                reference_time=datetime.now(timezone.utc),
                group_id=group,
            )
        episode = result.episode.uuid
        return [f"{edge.uuid}:{episode}" for edge in result.edges
                if episode in (edge.episodes or [])]

    async def _graphiti_rows(self, user_id: str,
                             owner: Optional[str] = None) -> List[dict]:
        """Every row of the user's group, one per fact and episode, with
        the episode's metadata, by Graphiti's documented getters, in
        write order; ``owner`` keeps only that agent's episodes."""
        group = backends.graphiti_group(user_id)
        episodes = await self.graphiti.nodes.episode.get_by_group_ids(
            [group], limit=V2_LIST_LIMIT)
        edges = await self.graphiti.edges.entity.get_by_group_ids(
            [group], limit=V2_LIST_LIMIT)
        meta = {e.uuid: (e, _episode_metadata(e)) for e in episodes}
        rows = []
        for edge in edges:
            for episode_uuid in edge.episodes or []:
                if episode_uuid not in meta:
                    continue
                episode, metadata = meta[episode_uuid]
                if owner is not None and metadata.get("owner_agent") != owner:
                    continue
                rows.append((episode.created_at, edge.created_at,
                             _graphiti_row(edge, episode_uuid, metadata)))
        rows.sort(key=lambda r: (r[0], r[1], r[2]["memory_id"]))
        return [row for _, _, row in rows]

    async def _graphiti_search(self, query, user_id, k, agent_name):
        """Graphiti's ``search()``, one row per fact in its order, with
        the metadata of the fact's first episode ``agent_name`` may see
        by the sharing convention (the first episode when it may see
        none, so the convention then hides the row)."""
        group = backends.graphiti_group(user_id)
        edges = await self.graphiti.search(
            query, group_ids=[group], num_results=k)
        wanted = sorted({u for edge in edges for u in edge.episodes or []})
        episodes = (await self.graphiti.nodes.episode.get_by_uuids(wanted)
                    if wanted else [])
        meta = {e.uuid: _episode_metadata(e) for e in episodes
                if e.group_id == group}
        rows = []
        for edge in edges:
            own = [(u, meta[u]) for u in edge.episodes or [] if u in meta]
            if not own:
                continue
            seen = [(u, m) for u, m in own
                    if in_partition(user_id, m)
                    and (agent_name is None or visible(agent_name, m))]
            episode_uuid, metadata = (seen or own)[0]
            rows.append(_graphiti_row(edge, episode_uuid, metadata))
        return rows

    async def _graphiti_delete(self, user_id, memory_id) -> bool:
        """The row's episode, deleted with Graphiti's ``remove_episode``:
        it deletes the facts no other episode claims and rebuilds the
        summaries of the entities it mentioned (with the LLM)."""
        from graphiti_core.errors import NodeNotFoundError

        parts = str(memory_id).split(":")
        if len(parts) != 2:
            return False
        episode_uuid = parts[1]
        if episode_uuid in self._removed:
            return True  # the row went with its episode
        try:
            episode = await self.graphiti.nodes.episode.get_by_uuid(
                episode_uuid)
        except NodeNotFoundError:
            return False
        group = backends.graphiti_group(user_id)
        if episode.group_id != group:
            return False
        async with self.runner.lock(group):
            await self.graphiti.remove_episode(episode_uuid)
        self._removed.add(episode_uuid)
        return True

    def list_own(self, user_id: str, agent_name: str) -> List[dict]:
        """Every row ``agent_name`` stored for ``user_id``, as
        ``{memory_id, content, metadata}``, up to ``V2_LIST_LIMIT``, by
        the backend's documented calls: Mem0's ``get_all`` filtered by
        both ids (its default is 20 rows), or a ``get`` on the user's
        Chroma collection where both match (in-house v2 rows carry
        ``agent_id`` as Mem0's do). A writer lists its own rows to delete
        a revoked fact's (benchmark v2)."""
        with usage.tagged(user_id):
            if self.backend == "graphiti":
                return self.runner.run(self._graphiti_rows, user_id,
                                       agent_name)
            if self.backend == "mem0":
                results = self.mem0.get_all(
                    filters={"user_id": user_id, "agent_id": agent_name},
                    top_k=V2_LIST_LIMIT,
                )["results"]
                return [
                    {
                        "memory_id": r.get("id"),
                        "content": r.get("memory", ""),
                        # Mem0 returns the entity ids at the top level.
                        "metadata": {
                            **(r.get("metadata") or {}),
                            "user_id": r.get("user_id"),
                            "agent_id": r.get("agent_id"),
                        },
                    }
                    for r in results
                ]
            found = self._collection(user_id).get(
                where={"$and": [
                    {"user_id": user_id}, {"agent_id": agent_name},
                ]},
                limit=V2_LIST_LIMIT,
                include=["documents", "metadatas"],
            )
            return [
                {"memory_id": memory_id, "content": document,
                 "metadata": dict(metadata or {})}
                for memory_id, document, metadata in zip(
                    found["ids"], found["documents"], found["metadatas"],
                )
            ]

    def delete(self, user_id: str, memory_id: str) -> bool:
        """Delete one of the user's rows by id: True when deleted, False
        when the user has no row with that id. Mem0: ``get`` (the row
        must be the user's), then ``delete(memory_id)``. In-house:
        ``delete(ids=...)`` on the user's collection, after ``get``
        found it (Chroma deletes a missing id silently)."""
        with usage.tagged(user_id):
            if self.backend == "graphiti":
                return self.runner.run(self._graphiti_delete, user_id,
                                       memory_id)
            if self.backend == "mem0":
                row = self.mem0.get(memory_id)
                if not row or row.get("user_id") != user_id:
                    return False
                self.mem0.delete(memory_id)
                return True
            collection = self._collection(user_id)
            if not collection.get(ids=[memory_id], include=[])["ids"]:
                return False
            collection.delete(ids=[memory_id])
            return True

    def search(self, query: str, user_id: str, k: int,
               agent_name: Optional[str] = None) -> List[dict]:
        """The user's memories nearest the query, as
        ``{memory_id, content, metadata, score}`` rows, in backend order.
        Graphiti's rows are facts, each with the metadata of an episode
        ``agent_name`` may see when it has one."""
        with usage.tagged(user_id):
            if self.backend == "graphiti":
                return self.runner.run(self._graphiti_search, query,
                                       user_id, k, agent_name)
            return self._search(query, user_id, k)

    def _search(self, query: str, user_id: str, k: int) -> List[dict]:
        if self.backend == "mem0":
            results = self.mem0.search(
                query, filters={"user_id": user_id}, top_k=k
            )["results"]
            return [
                {
                    "memory_id": r.get("id"),
                    "content": r.get("memory", ""),
                    # Mem0 returns user_id at the top level.
                    "metadata": {
                        **(r.get("metadata") or {}),
                        "user_id": r.get("user_id"),
                    },
                    "score": r.get("score"),
                }
                for r in results
            ]
        collection = self._collection(user_id)
        count = collection.count()
        if count == 0:
            return []
        result = collection.query(
            query_embeddings=[self.embed(query)],
            n_results=min(k, count),
            where={"user_id": user_id},
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "memory_id": memory_id,
                "content": document,
                "metadata": dict(metadata or {}),
                "score": 1.0 - distance,
            }
            for memory_id, document, metadata, distance in zip(
                result["ids"][0], result["documents"][0],
                result["metadatas"][0], result["distances"][0],
            )
        ]


def _episode_metadata(episode: Any) -> Dict[str, Any]:
    """The agent's metadata kept in a Graphiti episode's
    ``source_description``; ``{}`` when it holds none."""
    try:
        value = json.loads(episode.source_description or "")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _graphiti_row(edge: Any, episode_uuid: str,
                  metadata: Dict[str, Any]) -> Dict[str, Any]:
    """A fact as one episode claims it, with that episode's metadata and
    Graphiti's validity (recorded, never filtered on)."""
    return {
        "memory_id": f"{edge.uuid}:{episode_uuid}",
        "content": edge.fact,
        "metadata": {
            **metadata,
            "graphiti_edge_uuid": edge.uuid,
            "graphiti_episode_uuid": episode_uuid,
            "graphiti_valid_at": _iso(edge.valid_at),
            "graphiti_invalid_at": _iso(edge.invalid_at),
            "graphiti_expired_at": _iso(edge.expired_at),
            "graphiti_episode_count": len(edge.episodes or []),
        },
        "score": None,
    }


class _NativeWriter:
    """Extracts like the kernel conditions' writer, then writes itself."""

    memory_type = ""
    extractor_class: Any = None

    def __init__(self, agent_name: str, memory: NativeMemory):
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

    def run(self, task_input: str) -> dict:
        """Extract and validate like the kernel writer (the same
        ``extract``), store the shared rendering, keep the fields as
        JSON in the metadata; store nothing when the extraction fails.
        A benchmark v2 session (``{"v2_session": ...}``) is written
        event by event instead, with no extraction
        (``shared_memory_utils.run_v2_session``)."""
        session = parse_v2_session(task_input)
        if session is not None:
            return run_v2_session(
                self, session, self.memory_type,
                write=self._v2_create, list_rows=self._v2_list,
                delete=self._v2_delete,
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
        text = extraction.text
        metadata = memory_metadata(
            self.agent_name, self.user_id, self.memory_type,
            SHARED if self.share_memory else PRIVATE,
        )
        metadata[FIELD_STRUCTURED] = structured(extraction.fields)
        metadata.update(self.extra_metadata)
        stored = len(self.memory.write(
            [{"role": "user", "content": text}], text,
            self.agent_name, metadata,
        ))
        return {
            "agent_name": self.agent_name,
            "result": text,
            "written": metadata,
            "stored_rows": stored,
            "token_usage": self.extractor.token_usage,
            **report,
        }

    # -- benchmark v2 (docs/BENCHMARK_V2.md) ---------------------------

    def _v2_create(self, content: str, metadata: Dict[str, Any]) -> list:
        """Store one v2 row as a v1 write is stored: the text as the
        user's message. Every native row carries ``created_at`` (the
        native convention, ``sharing.memory_metadata``); in-house rows
        also carry ``agent_id``, the writer, as Mem0's rows do, so both
        backends list a writer's rows the same way."""
        metadata.setdefault(
            "created_at", datetime.now(timezone.utc).isoformat()
        )
        if getattr(self.memory, "backend", None) in ("inhouse", "graphiti"):
            metadata["agent_id"] = self.agent_name
        return self.memory.write(
            [{"role": "user", "content": content}], content,
            self.agent_name, metadata,
        )

    def _v2_list(self, user_id: str) -> List[dict]:
        return self.memory.list_own(user_id, self.agent_name)

    def _v2_delete(self, user_id: str, memory_id: str) -> bool:
        return self.memory.delete(user_id, memory_id)

    def list_own_rows(self, user_id: Optional[str] = None) -> List[dict]:
        """The rows this agent stored for ``user_id`` (default: its
        ``user_id``) as ``{memory_id, content, metadata}``, up to
        ``V2_LIST_LIMIT``, by the call a revoke lists with. Raises
        ``WriterError`` when the listing fails."""
        uid = require_user_id(user_id or self.user_id)
        return listed_rows(self._v2_list(uid))


class NativeProfileAgent(_NativeWriter):
    memory_type = "profile"
    extractor_class = ProfileAgent


class NativeTaskAgent(_NativeWriter):
    memory_type = "task_context"
    extractor_class = TaskAgent


class NativeCalendarAgent(_NativeWriter):
    """Benchmark v2's calendar writer; v2 sessions only: any other input
    fails the writer (``CalendarAgent.extract``)."""

    memory_type = MEMORY_TYPE_CALENDAR
    extractor_class = CalendarAgent


def _load_assistant_prompt() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assistant_agent", "config.json",
    )
    with open(path) as handle:
        return "".join(json.load(handle).get("description", []))


class NativeAssistantAgent:
    """Retrieves, filters, formats and prepends its own memory block,
    then answers through the kernel's ``llm_chat``.

    Its selection settings are attributes, so a deployment (or a
    heterogeneity variant, Subtask 10) can set its own. The defaults are
    the reference: k from the kernel's ``/memory/config``, no threshold,
    no token budget, the visibility rule, the native block.

    Benchmark v2 sets ``session`` (the current session) and ``probe_id``
    per probe. With the kernel's recency on and counting sessions
    (``NativeSettings``), each bullet ends with its row's age in
    sessions, worded as the kernel's (``session_age``); wall-clock ages
    are not printed, as before. The conversation row gets ``session``
    and ``provenance_event`` (the probe id). Since Amendment 3 a probe
    writes nothing: the harness sets ``store_conversation`` to False
    for its probe turns, and the turn is not written to the backend.
    """

    BLOCK_HEADER = "Relevant memories about this user:"
    # The kernel's block before Subtask 9d, for an agent one version
    # behind (variant V1).
    LEGACY_HEADER = "===== MEMORY CONTEXT ====="
    LEGACY_FOOTER = "===== END MEMORY CONTEXT ====="
    LEGACY_INSTRUCTION = (
        "The following are relevant memories from prior interactions "
        "with this user. Use them to personalize your response:"
    )

    def __init__(self, agent_name: str, memory: NativeMemory):
        self.agent_name = agent_name
        self.memory = memory
        self.system_prompt = _load_assistant_prompt()
        self.user_id: Optional[str] = None
        self.llms: Optional[list] = None
        self.extra_metadata: Dict[str, Any] = {}
        self.k: Optional[int] = None
        self.relevance_threshold: Optional[float] = None
        self.max_memory_tokens: Optional[int] = None
        self.check_visibility = True
        self.block_format = "native"
        # Benchmark v2: the current session, and the probe being run.
        self.session: Optional[int] = None
        self.probe_id: Optional[str] = None
        # False: the turn is not stored (a benchmark v2 probe).
        self.store_conversation = True

    def _recency(self) -> tuple:
        """``(on, unit)``: the kernel's block recency settings, from the
        memory's settings (off and ``"time"`` when it has none)."""
        settings = getattr(self.memory, "settings", None)
        return (
            bool(getattr(settings, "block_recency", False)),
            getattr(settings, "block_recency_unit", "time"),
        )

    def _age(self, row: dict) -> str:
        """`` (<age>)`` for a row's bullet when recency counts sessions:
        the current session minus the row's ``metadata.session``; empty
        when recency is off, counts time, or the row has no age."""
        on, unit = self._recency()
        if not on or unit != "session":
            return ""
        age = session_age(
            (row.get("metadata") or {}).get("session"), self.session
        )
        return f" ({age})" if age else ""

    def _block(self, rows: List[dict]) -> str:
        if self.block_format == "legacy":
            lines = [self.LEGACY_HEADER, self.LEGACY_INSTRUCTION, ""]
            lines += [
                f"- [{row['metadata'].get('created_at', 'unknown')}] "
                f"{row['content']}{self._age(row)}"
                for row in rows
            ]
            return "\n".join(lines + ["", self.LEGACY_FOOTER])
        return "\n".join(
            [self.BLOCK_HEADER]
            + [f"- {row['content']}{self._age(row)}" for row in rows]
        )

    def _conversation_metadata(self, user_id: Optional[str]) -> dict:
        """The conversation row's metadata: private to the assistant,
        with the deployment's ``extra_metadata``. A v2 probe (``session``
        or ``probe_id`` set) also stamps ``session``, ``provenance_event``
        (the probe id) and, in-house, ``agent_id``, so the assistant
        lists its own rows as the writers list theirs."""
        metadata = memory_metadata(
            self.agent_name, user_id, "conversation", PRIVATE
        )
        metadata.update(self.extra_metadata)
        if self.session is None and self.probe_id is None:
            return metadata
        if self.session is not None:
            metadata["session"] = self.session
        if self.probe_id is not None:
            metadata["provenance_event"] = self.probe_id
        if getattr(self.memory, "backend", None) in ("inhouse", "graphiti"):
            metadata["agent_id"] = self.agent_name
        return metadata

    def list_own_rows(self, user_id: Optional[str] = None) -> List[dict]:
        """The conversation rows this agent stored for ``user_id``
        (default: its ``user_id``) as ``{memory_id, content,
        metadata}``, up to ``V2_LIST_LIMIT`` (``NativeMemory.list_own``).
        Raises ``WriterError`` when the listing fails."""
        uid = require_user_id(user_id or self.user_id)
        return listed_rows(self.memory.list_own(uid, self.agent_name))

    @staticmethod
    def _tokens(text: str) -> int:
        return int(len(text.split()) * 1.3)

    def _select(self, rows: List[dict], user_id: str, k: int) -> tuple:
        """Partition, visibility, threshold, cap and budget; returns the
        kept rows and the count after each stage."""
        partitioned = [
            r for r in rows if in_partition(user_id, r["metadata"])
        ]
        visible_rows = (
            [r for r in partitioned
             if visible(self.agent_name, r["metadata"])]
            if self.check_visibility else partitioned
        )
        thresholded = visible_rows
        if self.relevance_threshold is not None:
            thresholded = [
                r for r in visible_rows
                if r["score"] is None or r["score"] >= self.relevance_threshold
            ]
        capped = thresholded[:k]
        kept = capped
        if self.max_memory_tokens is not None:
            while kept and self._tokens(self._block(kept)) > (
                self.max_memory_tokens
            ):
                kept = kept[:-1]
        counts = {
            "after_partition": len(partitioned),
            "after_visibility": len(visible_rows),
            "after_threshold": len(thresholded),
            "after_cap": len(capped),
            "after_budget": len(kept),
        }
        return kept, counts

    def run(self, task_input: str) -> dict:
        """Answer one query. The timing keys are the kernel's
        (``barrier_wait_ms`` is 0: there is no barrier); the backend's
        own token usage for the trial, writers included, is read from
        this process's accumulator after the conversation write."""
        user_id = self.user_id
        k = self.k if self.k is not None else self.memory.settings.k
        started = time.perf_counter()
        rows = self.memory.search(task_input, user_id, k,
                                  agent_name=self.agent_name)
        searched = time.perf_counter()
        kept, counts = self._select(rows, user_id, k)
        selected = time.perf_counter()

        messages = []
        block = self._block(kept) if kept else ""
        if block:
            messages.append({"role": "system", "content": block})
        messages += [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task_input},
        ]
        formatted = time.perf_counter()
        response = llm_chat(
            agent_name=self.agent_name,
            messages=messages,
            base_url=config.get_kernel_url(),
            llms=self.llms,
            user_id=user_id,
        )
        answer = response["response"]["response_message"] if response else ""
        answered = time.perf_counter()

        if self.store_conversation:
            conversation = self._conversation_metadata(user_id)
            self.memory.write(
                [
                    {"role": "user", "content": task_input},
                    {"role": "assistant", "content": answer},
                ],
                f"User: {task_input}\nAssistant: {answer}",
                self.agent_name,
                conversation,
            )
        written = time.perf_counter()
        records = usage.ACCUMULATOR.take(user_id)

        llm_timing = (response or {}).get("llm_timing") or {}
        stages = {
            "barrier_wait_ms": 0.0,
            "search_ms": (searched - started) * 1000,
            "select_ms": (selected - searched) * 1000,
            "format_ms": (formatted - selected) * 1000,
        }
        # As in the kernel conditions, the overhead includes the kernel
        # scheduler's wait before the model call.
        wait = llm_timing.get("schedule_wait_ms")
        latency = {
            **stages,
            "schedule_wait_ms": wait,
            "kernel_overhead_ms": sum(stages.values()) + (wait or 0.0),
            "llm_ms": llm_timing.get("llm_ms"),
        }
        recency, recency_unit = self._recency()
        diagnostics = self._diagnostics(
            user_id, k, rows, counts, kept, block,
            self.relevance_threshold, self.block_format,
            recency=recency, recency_unit=recency_unit,
            session=self.session,
            visibility_checked=self.check_visibility,
        )
        diagnostics.update(latency)
        return {
            "agent_name": self.agent_name,
            "result": answer,
            "rounds": 1,
            "injection_diagnostics": diagnostics,
            "token_usage": (response or {}).get("token_usage"),
            "llm_timing": llm_timing,
            "decoding": (response or {}).get("decoding"),
            "backend_usage": {
                "backend_llm_tokens": usage.summarize(
                    records, usage.BACKEND_EXTRACTION
                ),
                "embedding_tokens": usage.summarize(records, usage.EMBEDDING),
                "records": records,
            },
            "timing": {
                "retrieve_seconds": formatted - started,
                "llm_seconds": answered - formatted,
                "write_seconds": written - answered,
            },
        }

    @staticmethod
    def _diagnostics(user_id, k, rows, counts, kept, block,
                     threshold=None, block_format="native", *,
                     recency=False, recency_unit="time",
                     session=None, visibility_checked=None) -> dict:
        """The kernel's diagnostic keys, filled by the agent: the recency
        settings it followed, the current ``session``, whether it applied
        the visibility rule (``visibility_checked``: a V3 consumer or the
        ``no_visibility`` control does not), and per injected row its
        text as printed (without the age), ``fact_key``, ``session`` and
        ``provenance_event`` (benchmark v2)."""
        scores_present = any(r["score"] is not None for r in rows)
        return {
            "resolved_user_id": user_id,
            "own_fetched": len(rows),
            "shared_fetched": 0,
            "after_partition": counts["after_partition"],
            "after_visibility": counts["after_visibility"],
            "visibility_checked": visibility_checked,
            "after_dedupe": counts["after_visibility"],
            "scores_present": scores_present,
            "threshold_used": threshold,
            "after_threshold": counts["after_threshold"],
            "after_cap": counts["after_cap"],
            "top_k_used": {"own": k, "shared": 0},
            "after_budget": counts["after_budget"],
            "injected_count": len(kept),
            "tokens_estimated": int(len(block.split()) * 1.3),
            # "native": its own renderer (NATIVE_USAGE.md).
            "block_format": block_format,
            "block_recency": recency,
            "block_recency_unit": recency_unit,
            # No write barrier in native: none waited (a kernel key).
            "barrier_waits": [],
            # Native's search raises instead of returning an error, and
            # the user then fails; the keys say no error was hidden.
            "retrieval_error": None,
            "injection_error": None,
            "session": session,
            "block_text": block,
            "injected_memories": [
                {
                    "memory_id": r["memory_id"],
                    "owner_agent": r["metadata"].get("owner_agent", ""),
                    "memory_type": r["metadata"].get("memory_type", ""),
                    "match_score": r["score"],
                    "user_id": r["metadata"].get("user_id", ""),
                    "sharing_policy": r["metadata"].get(
                        "sharing_policy", ""
                    ),
                    "provenance_agent": r["metadata"].get(
                        "provenance_agent"
                    ),
                    "provenance_user": r["metadata"].get("provenance_user"),
                    "provenance_event": r["metadata"].get(
                        "provenance_event"
                    ),
                    "content": r["content"],
                    "fact_key": r["metadata"].get("fact_key"),
                    "session": r["metadata"].get("session"),
                }
                for r in kept
            ],
        }
