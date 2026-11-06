"""Agents that manage their own memory (docs/NATIVE_USAGE.md in AIOS).

``backend`` is ``"mem0"`` (the ``mem0`` SDK, used as its documentation
shows) or ``"inhouse"`` (Chroma, by the minimal convention in the spec).
The kernel serves the LLM calls only: no agent here makes a kernel memory
call. Each agent holds its own backend client.
"""
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from cerebrum.config.config_manager import config
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
    structured,
)
from cerebrum.example.agents.task_agent.agent import TaskAgent
from cerebrum.llm.apis import llm_chat
from cerebrum.utils import usage

BACKENDS = ("mem0", "inhouse")
COSINE = {"hnsw": {"space": "cosine"}}


class NativeMemory:
    """One agent's own handle on the condition's store."""

    def __init__(self, backend: str, settings: backends.NativeSettings):
        if backend not in BACKENDS:
            raise ValueError(f"unknown native backend {backend!r}")
        self.backend = backend
        self.settings = settings
        # Mem0 extracts facts from every write (infer=True).
        self.backend_extraction = backend == "mem0"
        if backend == "mem0":
            self.mem0 = backends.mem0_client(settings)
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
    ) -> None:
        """Store one memory: Mem0 extracts facts from ``messages``; the
        in-house store keeps ``text`` verbatim. The backend's LLM and
        embedding calls count to the user's trial."""
        user_id = metadata["user_id"]
        with usage.tagged(user_id):
            self._write(messages, text, agent_name, metadata, user_id)

    def _write(self, messages, text, agent_name, metadata, user_id) -> None:
        if self.backend == "mem0":
            self.mem0.add(
                messages, user_id=user_id, agent_id=agent_name,
                metadata=metadata, infer=True,
            )
        else:
            self._collection(user_id).add(
                ids=[str(uuid.uuid4())],
                documents=[text],
                embeddings=[self.embed(text)],
                metadatas=[metadata],
            )

    def search(self, query: str, user_id: str, k: int) -> List[dict]:
        """The user's memories nearest the query, as
        ``{memory_id, content, metadata, score}`` rows, in backend order."""
        with usage.tagged(user_id):
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
        # Metadata the deployment adds to every write (Subtask 10).
        self.extra_metadata: Dict[str, Any] = {}

    def run(self, task_input: str) -> dict:
        """Extract and validate like the kernel writer (the same
        ``extract``), store the shared rendering, keep the fields as
        JSON in the metadata; store nothing when the extraction fails."""
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
        self.memory.write(
            [{"role": "user", "content": text}], text,
            self.agent_name, metadata,
        )
        return {
            "agent_name": self.agent_name,
            "result": text,
            "written": metadata,
            "token_usage": self.extractor.token_usage,
            **report,
        }


class NativeProfileAgent(_NativeWriter):
    memory_type = "profile"
    extractor_class = ProfileAgent


class NativeTaskAgent(_NativeWriter):
    memory_type = "task_context"
    extractor_class = TaskAgent


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

    def _block(self, rows: List[dict]) -> str:
        if self.block_format == "legacy":
            lines = [self.LEGACY_HEADER, self.LEGACY_INSTRUCTION, ""]
            lines += [
                f"- [{row['metadata'].get('created_at', 'unknown')}] "
                f"{row['content']}"
                for row in rows
            ]
            return "\n".join(lines + ["", self.LEGACY_FOOTER])
        return "\n".join(
            [self.BLOCK_HEADER] + [f"- {row['content']}" for row in rows]
        )

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
        rows = self.memory.search(task_input, user_id, k)
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

        conversation = memory_metadata(
            self.agent_name, user_id, "conversation", PRIVATE
        )
        conversation.update(self.extra_metadata)
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
        diagnostics = self._diagnostics(
            user_id, k, rows, counts, kept, block,
            self.relevance_threshold, self.block_format,
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
                     threshold=None, block_format="native") -> dict:
        """The kernel's diagnostic keys, filled by the agent."""
        scores_present = any(r["score"] is not None for r in rows)
        return {
            "resolved_user_id": user_id,
            "own_fetched": len(rows),
            "shared_fetched": 0,
            "after_partition": counts["after_partition"],
            "after_visibility": counts["after_visibility"],
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
            "block_recency": False,
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
                }
                for r in kept
            ],
        }
