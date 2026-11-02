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
    """Mem0's ``llm`` config for the pinned internal LLM."""
    provider = backend_llm.get("provider")
    model = backend_llm.get("model")
    if not provider or not model:
        raise ValueError("memory.backend_llm needs a provider and a model")
    config: Dict[str, Any] = {
        "model": model,
        "temperature": backend_llm.get("temperature", 0.1),
    }
    if provider == "azure_openai":
        # The same variables the kernel's LiteLLM calls read.
        config["azure_kwargs"] = {
            "api_key": os.environ["AZURE_API_KEY"],
            "azure_endpoint": os.environ["AZURE_API_BASE"],
            "api_version": os.environ["AZURE_API_VERSION"],
            "azure_deployment": model,
        }
    elif provider == "ollama":
        config["ollama_base_url"] = backend_llm.get(
            "ollama_base_url", "http://localhost:11434"
        )
    else:
        raise ValueError(f"unsupported backend_llm provider {provider!r}")
    return {"provider": provider, "config": config}


def mem0_client(settings: NativeSettings):
    """One ``mem0.Memory`` on the condition's shared store."""
    from mem0 import Memory

    root = store_dir("native_mem0")
    embedding = settings.embedding
    return Memory.from_config({
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
        self._client = Client(host=embedding["ollama_base_url"])

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
