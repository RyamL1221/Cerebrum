"""Agents that run the kernel's memory pipeline themselves
(docs/REPLICATED_LOGIC.md in AIOS).

Each agent builds its own ``MemoryPipeline`` over its own provider
client, with its own write barrier and identity resolver, and does what
the kernel does for it in the kernel conditions: the writers upsert
their memory as the kernel writers' SDK calls do, and the assistant
injects the block and writes the conversation as the kernel's injector
and extractor do. The kernel serves the LLM calls only: no agent here
makes a kernel memory call.
"""
import json
import os
import time
from typing import Any, Dict, Optional

from cerebrum.config.config_manager import config
from cerebrum.example.agents.profile_agent.agent import ProfileAgent
from cerebrum.example.agents.replicated import library
from cerebrum.example.agents.shared_memory_utils import (
    MEMORY_TYPE_PROFILE,
    MEMORY_TYPE_TASK_CONTEXT,
    POLICY_PRIVATE,
    POLICY_SHARED,
    build_memory_metadata,
)
from cerebrum.example.agents.task_agent.agent import TaskAgent
from cerebrum.llm.apis import llm_chat
from cerebrum.utils import usage

BACKENDS = {"mem0": "mem0", "inhouse": "in-house"}
STORE_ROOT = os.environ.get(
    "CEREBRUM_REPLICATED_MEMORY_DIR", ".replicated_memory"
)
# The SDK's search_memories default, which the kernel writers use.
WRITER_SEARCH_K = 5


def store_config(
    backend: str, embedding: Dict[str, Any], backend_llm: Dict[str, Any],
) -> Dict[str, Any]:
    """The ``memory:`` sections a provider is configured from, with the
    condition's own store in place of the kernel's.

    Mem0 needs an LLM to construct (``mem0ai`` 2.0.2 builds its default
    OpenAI client at once and wants a key). Writes are verbatim
    (``infer=False``), so it is never called; it is the pinned
    ``memory.backend_llm`` through LiteLLM, as for the native agents.
    """
    root = os.path.abspath(os.path.join(STORE_ROOT, backend))
    os.makedirs(root, exist_ok=True)
    mem0 = {"vector_store": {"provider": "chroma", "config": {
        "collection_name": "mem0_memories",
        "path": os.path.join(root, "chroma"),
    }}}
    if backend_llm.get("provider") and backend_llm.get("model"):
        mem0["llm"] = {"provider": "litellm", "config": {
            "model": usage.litellm_model_name(
                backend_llm["provider"], backend_llm["model"]
            ),
        }}
    return {
        "embedding": embedding,
        "mem0": mem0,
        "chroma_inhouse": {"path": os.path.join(root, "chroma")},
    }


class ReplicatedMemory:
    """One agent's own pipeline: provider client, settings, barrier and
    identity resolver, built from the kernel's ``/memory/config``."""

    def __init__(
        self, backend: str, kernel_config: Dict[str, Any],
        provider: Any = None,
    ):
        """``provider`` replaces the backend's client (tests)."""
        if backend not in BACKENDS:
            raise ValueError(f"unknown replicated backend {backend!r}")
        pipeline = library.load()
        from aios.memory.providers.factory import (
            ProviderFactory,
            provider_config,
        )

        provider_type = BACKENDS[backend]
        self.backend = backend
        self.provider = provider or ProviderFactory.create(
            provider_type,
            provider_config(
                provider_type,
                store_config(
                    backend, kernel_config["embedding"],
                    kernel_config.get("backend_llm") or {},
                ),
            ),
        )
        self.settings = pipeline.PipelineSettings.from_memory_config(
            kernel_config["pipeline"]
        )
        # Its own barrier and resolver (the library's defaults).
        self.pipeline = pipeline.MemoryPipeline(self.provider, self.settings)
        self.version = pipeline.PIPELINE_VERSION
        self.library = pipeline


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

    def _extract(self, task_input: str) -> dict:
        raise NotImplementedError

    def _upsert(self, user_id: str, content: str) -> Dict[str, Any]:
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
                    content, {"user_id": user_id},
                )
            return dict(matching[0]["metadata"])
        metadata = build_memory_metadata(
            owner_agent=self.agent_name,
            user_id=user_id,
            memory_type=self.memory_type,
            sharing_policy=(
                POLICY_SHARED if self.share_memory else POLICY_PRIVATE
            ),
        )
        note = self.memory.library.note_from_request(
            {"content": content, "metadata": metadata}
        )
        pipeline.write(self.agent_name, user_id, note)
        return dict(note.metadata)

    def run(self, task_input: str) -> dict:
        self.extractor.llms = self.llms
        data = self._extract(task_input)
        content = json.dumps(data)
        written = self._upsert(self.user_id, content)
        return {
            "agent_name": self.agent_name,
            "result": content,
            "written": written,
            "token_usage": self.extractor.token_usage,
        }


class ReplicatedProfileAgent(_ReplicatedWriter):
    memory_type = MEMORY_TYPE_PROFILE
    query_prefix = "profile"
    extractor_class = ProfileAgent

    def _extract(self, task_input: str) -> dict:
        return self.extractor._extract_profile(task_input)


class ReplicatedTaskAgent(_ReplicatedWriter):
    memory_type = MEMORY_TYPE_TASK_CONTEXT
    query_prefix = "task context"
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


class ReplicatedAssistantAgent:
    """Sends the kernel AssistantAgent's messages, with the block its own
    pipeline injects, and writes the conversation turn afterwards."""

    def __init__(self, agent_name: str, memory: ReplicatedMemory):
        self.agent_name = agent_name
        self.memory = memory
        self.system_prompt = _load_assistant_prompt()
        self.user_id: Optional[str] = None
        self.llms: Optional[list] = None

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
        messages, diagnostics = pipeline.inject(
            self.agent_name, messages, user_id=user_id
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
        # resolved user's scope.
        if task_input and answer:
            pipeline.write(
                self.agent_name, None,
                self.memory.library.conversation_note(
                    self.agent_name, task_input, str(answer),
                    diagnostics.get("resolved_user_id"),
                ),
            )
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
