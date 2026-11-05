"""Setting up the backends the native agents use directly.

Each agent builds its own client from these; the calls that read and
write memory are in ``agents.py``, where a reviewer can see them. The
settings (pinned embedding model, Mem0's internal LLM, retrieval size)
come from the kernel's ``/memory/config``, so results record them.
"""
import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from cerebrum.utils.usage import (
    count_embeddings,
    install_litellm_logger,
    mem0_llm_config,
)

# Mem0 reports usage to its telemetry service unless told not to.
os.environ.setdefault("MEM0_TELEMETRY", "False")

STORE_ROOT = os.environ.get("CEREBRUM_NATIVE_MEMORY_DIR", ".native_memory")


@dataclass(frozen=True)
class NativeSettings:
    embedding: Dict[str, Any]
    backend_llm: Dict[str, Any]
    k: int

    @classmethod
    def from_kernel_config(cls, config: Dict[str, Any]) -> "NativeSettings":
        if not config.get("embedding"):
            raise ValueError("kernel /memory/config reports no embedding")
        return cls(
            embedding=dict(config["embedding"]),
            backend_llm=dict(config.get("backend_llm") or {}),
            k=int(config["max_injected_memories"]),
        )


def store_dir(condition: str) -> str:
    path = os.path.abspath(os.path.join(STORE_ROOT, condition))
    os.makedirs(path, exist_ok=True)
    return path


def mem0_llm(backend_llm: Dict[str, Any]) -> Dict[str, Any]:
    """Mem0's ``llm`` config for the pinned internal LLM
    (``cerebrum.utils.usage.mem0_llm_config``, which the kernel uses
    too)."""
    return mem0_llm_config(backend_llm)


def mem0_client(settings: NativeSettings):
    """One ``mem0.Memory`` on the condition's shared store."""
    from mem0 import Memory

    install_litellm_logger()
    root = store_dir("native_mem0")
    embedding = settings.embedding
    client = Memory.from_config({
        "llm": mem0_llm(settings.backend_llm),
        "embedder": {"provider": embedding["provider"], "config": {
            "model": embedding["model"],
            "ollama_base_url": embedding["ollama_base_url"],
            "embedding_dims": embedding["dimension"],
        }},
        "vector_store": {"provider": "chroma", "config": {
            "collection_name": "native_mem0",
            "path": os.path.join(root, "chroma"),
        }},
        "history_db_path": os.path.join(root, "history.db"),
    })
    count_embeddings(client.embedding_model.client, embedding["model"])
    return client


def chroma_client():
    """The in-house condition's Chroma store."""
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(
        path=os.path.join(store_dir("native_inhouse"), "chroma"),
        settings=Settings(anonymized_telemetry=False),
    )


def collection_name(user_id: str) -> str:
    """``native_<user>``, made a valid Chroma name; a name too long for
    Chroma keeps a hash of the id so two users never share one."""
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"native_{user_id}")
    if len(name) > 63:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:10]
        name = f"{name[:52].rstrip('_-')}_{digest}"
    return name


class Embedder:
    """The pinned model, called the way the kernel and Mem0 call it."""

    def __init__(self, embedding: Dict[str, Any]):
        from ollama import Client

        self.model = embedding["model"]
        self.dimension = embedding["dimension"]
        self._client = count_embeddings(
            Client(host=embedding["ollama_base_url"]), self.model
        )

    def __call__(self, text: str) -> List[float]:
        vector = self._client.embed(model=self.model, input=text)[
            "embeddings"
        ][0]
        if len(vector) != self.dimension:
            raise ValueError(
                f"{self.model} returned {len(vector)} dimensions, "
                f"expected {self.dimension}"
            )
        return list(vector)
