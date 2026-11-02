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
from cerebrum.example.agents.native.render import render
from cerebrum.example.agents.native.sharing import (
    PRIVATE,
    SHARED,
    in_partition,
    memory_metadata,
    visible,
)
from cerebrum.example.agents.profile_agent.agent import ProfileAgent
from cerebrum.example.agents.task_agent.agent import TaskAgent
from cerebrum.llm.apis import llm_chat

BACKENDS = ("mem0", "inhouse")
COSINE = {"hnsw": {"space": "cosine"}}


class NativeMemory:
    """One agent's own handle on the condition's store."""

    def __init__(self, backend: str, settings: backends.NativeSettings):
        if backend not in BACKENDS:
            raise ValueError(f"unknown native backend {backend!r}")
        self.backend = backend
        self.settings = settings
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
        in-house store keeps ``text`` verbatim."""
        user_id = metadata["user_id"]
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

    def _extract(self, task_input: str) -> dict:
        raise NotImplementedError

    def run(self, task_input: str) -> dict:
        self.extractor.llms = self.llms
        data = self._extract(task_input)
        text = render(self.memory_type, data)
        metadata = memory_metadata(
            self.agent_name, self.user_id, self.memory_type,
            SHARED if self.share_memory else PRIVATE,
        )
        self.memory.write(
            [{"role": "user", "content": text}], text,
            self.agent_name, metadata,
        )
        return {
            "agent_name": self.agent_name,
            "result": text,
            "written": metadata,
        }


class NativeProfileAgent(_NativeWriter):
    memory_type = "profile"
    extractor_class = ProfileAgent

    def _extract(self, task_input: str) -> dict:
        return self.extractor._extract_profile(task_input)


class NativeTaskAgent(_NativeWriter):
    memory_type = "task_context"
    extractor_class = TaskAgent

    def _extract(self, task_input: str) -> dict:
        return self.extractor._extract_task_context(task_input)


def _load_assistant_prompt() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assistant_agent", "config.json",
    )
    with open(path) as handle:
        return "".join(json.load(handle).get("description", []))


class NativeAssistantAgent:
    """Retrieves, filters, formats and prepends its own memory block,
    then answers through the kernel's ``llm_chat``."""

    BLOCK_HEADER = "Relevant memories about this user:"

    def __init__(self, agent_name: str, memory: NativeMemory):
        self.agent_name = agent_name
        self.memory = memory
        self.system_prompt = _load_assistant_prompt()
        self.user_id: Optional[str] = None
        self.llms: Optional[list] = None

    def _block(self, rows: List[dict]) -> str:
        return "\n".join(
            [self.BLOCK_HEADER] + [f"- {row['content']}" for row in rows]
        )

    def run(self, task_input: str) -> dict:
        user_id = self.user_id
        k = self.memory.settings.k
        started = time.perf_counter()
        rows = self.memory.search(task_input, user_id, k)
        partitioned = [r for r in rows if in_partition(user_id, r["metadata"])]
        kept = [
            r for r in partitioned if visible(self.agent_name, r["metadata"])
        ][:k]
        retrieved = time.perf_counter()

        messages = []
        block = self._block(kept) if kept else ""
        if block:
            messages.append({"role": "system", "content": block})
        messages += [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task_input},
        ]
        response = llm_chat(
            agent_name=self.agent_name,
            messages=messages,
            base_url=config.get_kernel_url(),
            llms=self.llms,
            user_id=user_id,
        )
        answer = response["response"]["response_message"] if response else ""
        answered = time.perf_counter()

        self.memory.write(
            [
                {"role": "user", "content": task_input},
                {"role": "assistant", "content": answer},
            ],
            f"User: {task_input}\nAssistant: {answer}",
            self.agent_name,
            memory_metadata(self.agent_name, user_id, "conversation", PRIVATE),
        )
        written = time.perf_counter()

        return {
            "agent_name": self.agent_name,
            "result": answer,
            "rounds": 1,
            "injection_diagnostics": self._diagnostics(
                user_id, k, rows, partitioned, kept, block
            ),
            "timing": {
                "retrieve_seconds": retrieved - started,
                "llm_seconds": answered - retrieved,
                "write_seconds": written - answered,
            },
        }

    @staticmethod
    def _diagnostics(user_id, k, rows, partitioned, kept, block) -> dict:
        """The kernel's diagnostic keys, filled by the agent."""
        scores_present = any(r["score"] is not None for r in rows)
        return {
            "resolved_user_id": user_id,
            "own_fetched": len(rows),
            "shared_fetched": 0,
            "after_partition": len(partitioned),
            "after_visibility": len(kept),
            "after_dedupe": len(kept),
            "scores_present": scores_present,
            "threshold_used": None,
            "after_threshold": len(kept),
            "after_cap": len(kept),
            "top_k_used": {"own": k, "shared": 0},
            "after_budget": len(kept),
            "injected_count": len(kept),
            "tokens_estimated": int(len(block.split()) * 1.3),
            "injected_memories": [
                {
                    "memory_id": r["memory_id"],
                    "owner_agent": r["metadata"].get("owner_agent", ""),
                    "memory_type": r["metadata"].get("memory_type", ""),
                    "match_score": r["score"],
                }
                for r in kept
            ],
        }
