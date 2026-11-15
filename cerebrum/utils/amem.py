"""A-MEM's clients and stores, shared by every locus.

NeurIPS Subtask 17 (AIOS docs/AMEM_BACKEND.md). The kernel's A-MEM
provider, the replicated agents (through it) and the native agents all
build A-MEM from here, so the backend runs with one configuration in
every locus, as ``cerebrum.utils.graphiti`` does for Graphiti:

- ``LiteLLMController``: A-MEM's LLM, the pinned ``memory.backend_llm``
  (Azure gpt-4o, temperature 0, seed) through the synchronous
  ``litellm.completion``, with A-MEM's own messages and
  ``response_format``. It runs in the caller's thread, so the trial's
  usage tag applies (``usage.LiteLLMUsageLogger``).
- ``OllamaEmbeddingFunction``: the pinned ``memory.embedding`` model as
  each store's Chroma embedding function, through the same
  ``ollama.Client.embed`` call as the other backends, counted by
  ``usage.count_embeddings``.
- ``Stores``: one ``AgenticMemorySystem`` per user, each with its own
  Chroma collection in a client of its own (A-MEM's constructor resets
  the process's default Chroma client, and all its instances share one
  collection there).

``agentic_memory`` (WujiangXu/A-mem-sys at ``PINNED_COMMIT``) is
imported only when a store is built, so importing this module needs no
A-MEM install.
"""
import atexit
import hashlib
import json
import logging
import re
import shutil
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple

from cerebrum.utils import usage
from cerebrum.utils.graphiti import strip_fences

logger = logging.getLogger(__name__)

# WujiangXu/A-mem-sys, the package ``agentic-memory`` (AIOS
# docs/AMEM_BACKEND.md, "Which A-MEM").
PINNED_COMMIT = "f303dfc71e07bdc787f4bc135d4cea328ae30e99"
PINNED_REPO = "https://github.com/WujiangXu/A-mem-sys"

# A-MEM's system message (agentic_memory/llm_controller.py, every
# controller).
SYSTEM_MESSAGE = "You must respond with a JSON object."


def collection_name(user_id: str, namespace: str = "") -> str:
    """A user's Chroma collection: 3 to 63 characters of letters,
    digits, ``.``, ``_`` and ``-``, starting and ending with a letter or
    digit (Chroma's rule); the readable part of the user id and the
    first 12 hex digits of its SHA-256, so two ids never share one."""
    if not user_id:
        raise ValueError("an A-MEM store needs a user id")
    readable = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id))
    readable = re.sub(r"_+", "_", readable).strip("_-")[:32] or "user"
    digest = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:12]
    prefix = f"amem_{namespace}_" if namespace else "amem_"
    return f"{prefix}{readable}_{digest}"[-63:].lstrip("_-.")


class LiteLLMController:
    """A-MEM's LLM controller (``get_completion(prompt,
    response_format, temperature)``) on LiteLLM. A-MEM asks for
    temperature 1.0 by default; the pinned temperature is used whatever
    it asks. Code fences are stripped, as Graphiti's client does. Errors
    raise: A-MEM's own handlers decide what a failed call does."""

    def __init__(self, model: str, temperature: float,
                 seed: Optional[int]):
        self.model = model
        self.temperature = temperature
        self.seed = seed

    def get_completion(self, prompt: str, response_format: dict = None,
                       temperature: float = None, **_) -> str:
        import litellm

        params: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_MESSAGE},
                         {"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if response_format:
            params["response_format"] = response_format
        if self.seed is not None:
            params["seed"] = int(self.seed)
        response = litellm.completion(**params)
        return strip_fences(response.choices[0].message.content or "")


def llm_controller(backend_llm: dict) -> LiteLLMController:
    """A-MEM's LLM for ``memory.backend_llm``."""
    provider = (backend_llm or {}).get("provider")
    model = (backend_llm or {}).get("model")
    if not provider or not model:
        raise ValueError("memory.backend_llm needs a provider and a model")
    if provider not in ("azure_openai", "ollama"):
        raise ValueError(f"unsupported backend_llm provider {provider!r}")
    usage.install_litellm_logger()
    return LiteLLMController(
        usage.litellm_model_name(provider, model),
        float(backend_llm.get("temperature", 0.0)),
        backend_llm.get("seed"),
    )


def _embedding_function_class():
    from chromadb import EmbeddingFunction

    class OllamaEmbeddingFunction(EmbeddingFunction):
        """The pinned embedding model through ``ollama.Client.embed``,
        counted per trial."""

        def __init__(self, model: str, base_url: str, dimension: int):
            import ollama

            self.model = model
            self.base_url = base_url
            self.dimension = int(dimension)
            self.client = ollama.Client(host=base_url)
            usage.count_embeddings(self.client, model)

        def __call__(self, input):
            texts = [str(text) for text in input]
            if not texts:
                return []
            result = self.client.embed(model=self.model, input=texts)
            vectors = [list(v) for v in result.embeddings]
            for vector in vectors:
                if len(vector) != self.dimension:
                    raise ValueError(
                        f"{self.model} returned {len(vector)} dimensions, "
                        f"not {self.dimension}")
            return vectors

        @staticmethod
        def name() -> str:
            return "aios_ollama"

        def get_config(self) -> Dict[str, Any]:
            return {"model": self.model, "base_url": self.base_url,
                    "dimension": self.dimension}

        @staticmethod
        def build_from_config(config: Dict[str, Any]):
            return OllamaEmbeddingFunction(
                config["model"], config["base_url"], config["dimension"])

    return OllamaEmbeddingFunction


def embedding_function(embedding: dict) -> Any:
    """Each store's Chroma embedding function, for ``memory.embedding``."""
    if (embedding or {}).get("provider", "ollama") != "ollama":
        raise ValueError("memory.embedding: only ollama is supported")
    return _embedding_function_class()(
        embedding.get("model", "nomic-embed-text"),
        embedding.get("ollama_base_url", "http://localhost:11434"),
        embedding.get("dimension", 768),
    )


class _NoReset:
    """Stands in for A-MEM's default retriever while a store is built:
    its constructor resets that retriever's client
    (``memory_system.py:117-118``)."""

    class client:  # noqa: N801
        @staticmethod
        def reset():
            pass


class _NoController:
    def __init__(self, *args, **kwargs):
        self.llm = None


# A store is built with A-MEM's default retriever and controller
# replaced in its module; one build at a time.
_BUILD_LOCK = threading.Lock()


def _classes():
    from agentic_memory import memory_system as ms
    from agentic_memory.retrievers import ChromaRetriever

    class UserRetriever(ChromaRetriever):
        """A-MEM's retriever on a collection of the user's own."""

        def __init__(self, client, name: str, function):
            self.client = client
            self.embedding_function = function
            self.collection_name = name
            self.collection = client.get_or_create_collection(
                name=name, embedding_function=function)

    class AMemStore(ms.AgenticMemorySystem):
        """A-MEM's ``AgenticMemorySystem`` with the pinned LLM and
        embedder and a Chroma collection of its own (AIOS
        docs/AMEM_BACKEND.md, "Store, partition and isolation")."""

        def __init__(self, retriever, llm, evo_threshold: int = 100):
            from unittest.mock import patch

            with _BUILD_LOCK, \
                    patch.object(ms, "ChromaRetriever",
                                 lambda **kwargs: _NoReset()), \
                    patch.object(ms, "LLMController", _NoController):
                super().__init__(model_name="", llm_backend="openai",
                                 llm_model="", evo_threshold=evo_threshold)
            self.retriever = retriever
            self.llm_controller.llm = llm

        def consolidate_memories(self):
            """A-MEM rebuilds into a fresh default retriever
            (``memory_system.py:292-313``), the process's shared
            collection; this store rebuilds into its own."""
            old = self.retriever
            old.client.delete_collection(old.collection_name)
            self.retriever = UserRetriever(
                old.client, old.collection_name, old.embedding_function)
            for note in self.memories.values():
                self.retriever.add_document(
                    note.content, note_metadata(note), note.id)

    return UserRetriever, AMemStore


def note_metadata(note: Any) -> Dict[str, Any]:
    """The metadata A-MEM gives a note's Chroma document
    (``memory_system.py:270-283``)."""
    return {
        "id": note.id, "content": note.content, "keywords": note.keywords,
        "links": note.links, "retrieval_count": note.retrieval_count,
        "timestamp": note.timestamp, "last_accessed": note.last_accessed,
        "context": note.context,
        "evolution_history": note.evolution_history,
        "category": note.category, "tags": note.tags,
    }


def _state(note: Any) -> Tuple:
    return (json.dumps(note.tags, default=str), note.context,
            json.dumps(note.links, default=str))


def add_note(store: Any, content: str, **kwargs) -> Tuple[str, List[str]]:
    """A-MEM's ``add_note``, and the ids of the existing notes whose
    tags, context or links its evolution changed (AIOS
    docs/AMEM_BACKEND.md, "One note per write")."""
    before = {note_id: _state(note)
              for note_id, note in store.memories.items()}
    note_id = store.add_note(content, **kwargs)
    changed = sorted(note_id_ for note_id_, state in before.items()
                     if note_id_ in store.memories
                     and _state(store.memories[note_id_]) != state)
    logger.info("A-MEM evolved %d note(s) at note %s", len(changed),
                note_id)
    return note_id, changed


class Stores:
    """One A-MEM store per user, built on first use: an
    ``AMemStore`` whose collection is the user's, in a Chroma client of
    these stores' own (a temporary directory, removed at exit), with a
    lock per user (A-MEM's notes and evolution are not thread-safe)."""

    def __init__(self, llm: Any, function: Any, namespace: str = ""):
        import chromadb
        from chromadb.config import Settings

        self.llm = llm
        self.function = function
        self.namespace = namespace
        self.path = tempfile.mkdtemp(prefix="aios_amem_")
        atexit.register(shutil.rmtree, self.path, True)
        self.client = chromadb.PersistentClient(
            path=self.path, settings=Settings(anonymized_telemetry=False))
        self._stores: Dict[str, Any] = {}
        self._locks: Dict[str, threading.RLock] = {}
        self._lock = threading.Lock()

    def lock(self, user_id: str) -> threading.RLock:
        with self._lock:
            return self._locks.setdefault(
                collection_name(user_id, self.namespace), threading.RLock())

    def store(self, user_id: str) -> Any:
        name = collection_name(user_id, self.namespace)
        with self._lock:
            found = self._stores.get(name)
            if found is None:
                retriever_class, store_class = _classes()
                found = store_class(
                    retriever_class(self.client, name, self.function),
                    self.llm)
                self._stores[name] = found
            return found

    def has(self, user_id: str) -> bool:
        with self._lock:
            return collection_name(user_id, self.namespace) in self._stores


_SHARED: Dict[str, Stores] = {}
_SHARED_LOCK = threading.Lock()


def shared_stores(backend_llm: dict, embedding: dict,
                  namespace: str = "") -> Stores:
    """The process's stores for one configuration, so the agents of a
    process (and a provider and its tests) share them."""
    key = json.dumps([backend_llm, embedding, namespace], sort_keys=True,
                     default=str)
    with _SHARED_LOCK:
        if key not in _SHARED:
            _SHARED[key] = Stores(llm_controller(backend_llm),
                                  embedding_function(embedding), namespace)
        return _SHARED[key]


def versions() -> Dict[str, Optional[str]]:
    """The installed A-MEM's commit (pip's record of a VCS install) and
    Chroma's version, for the run's provenance."""
    from importlib import metadata

    found: Dict[str, Optional[str]] = {"agentic_memory": None,
                                       "chromadb": None}
    try:
        dist = metadata.distribution("agentic-memory")
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        found["agentic_memory"] = (
            (direct.get("vcs_info") or {}).get("commit_id")
            or dist.version)
    except metadata.PackageNotFoundError:
        pass
    try:
        found["chromadb"] = metadata.version("chromadb")
    except metadata.PackageNotFoundError:
        pass
    return found
