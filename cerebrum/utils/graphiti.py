"""Graphiti's clients and runtime, shared by every locus.

NeurIPS Subtask 16 (AIOS docs/GRAPHITI_BACKEND.md). The kernel's
Graphiti provider, the replicated agents (through it) and the native
agents all build Graphiti from here, so the backend runs with one
configuration in every locus, as ``usage.mem0_llm_config`` does for Mem0:

- ``LiteLLMClient``: Graphiti's internal LLM, the pinned
  ``memory.backend_llm`` (Azure gpt-4o, temperature 0, seed) for both of
  Graphiti's model sizes, through the synchronous ``litellm.completion``
  in a worker thread. The usage logger (``usage.LiteLLMUsageLogger``)
  records only synchronous calls; an ``acompletion`` would never be
  counted.
- ``OllamaEmbedder``: the pinned ``memory.embedding`` model through the
  same ``ollama.Client.embed`` call as the other backends, counted by
  ``usage.count_embeddings``.
- ``NoReranker``: Graphiti's ``search()`` and ingestion use no
  cross-encoder; this one raises if anything does.
- ``GraphitiRunner``: Graphiti is async only. One background event loop
  runs it, and each call carries the caller's usage tag into the loop,
  so every LLM and embedding call a write makes is a record of the
  caller's trial.

graphiti_core is imported only when a client is built, so importing
this module needs no Graphiti install.
"""
import asyncio
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from cerebrum.utils import usage

# Graphiti sends a PostHog event per client unless this is "false"
# (graphiti_core/telemetry/telemetry.py).
os.environ["GRAPHITI_TELEMETRY_ENABLED"] = "false"

GROUP_ID = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_TOKENS = 16_384  # gpt-4o's output limit, Graphiti's default


def group_id(user_id: str) -> str:
    """A Graphiti group id for a user: Graphiti accepts only letters,
    digits, ``_`` and ``-`` (graphiti_core/helpers.py), and user ids can
    hold ``@`` and ``.``. The readable part of the id and the first 12
    hex digits of its SHA-256, as AIOS names a user's Chroma collection,
    so two ids never share a group."""
    if not user_id:
        raise ValueError("a Graphiti group needs a user id")
    readable = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id))
    readable = re.sub(r"_+", "_", readable).strip("_-")[:40] or "user"
    digest = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:12]
    return f"{readable}_{digest}"


def _json_object(text: str) -> Optional[dict]:
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


_TURN = re.compile(
    r"\AUser: (?P<user>.*?)\nAssistant: (?P<assistant>.*)\Z", re.DOTALL)


def episode_body(content: str, memory_type: str = "") -> Tuple[str, str]:
    """The ``(episode_body, source)`` a write becomes
    (GRAPHITI_BACKEND.md, "One episode per write"): a JSON object as a
    ``json`` episode; a stored conversation turn (``User: ...\\nAssistant:
    ...``) as ``user:`` and ``assistant:`` message lines; anything else,
    the user's statement, as one ``user:`` message. ``source`` is the
    ``EpisodeType`` value."""
    text = content or ""
    if _json_object(text) is not None:
        return text, "json"
    turn = _TURN.match(text) if memory_type == "conversation" else None
    if turn:
        return (f"user: {turn['user']}\nassistant: {turn['assistant']}",
                "message")
    return f"user: {text}", "message"


def strip_fences(text: str) -> str:
    """A reply's JSON without Markdown code fences, as Graphiti's own
    ``OpenAIGenericClient`` strips them."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _llm_client_class():
    from graphiti_core.llm_client.client import LLMClient
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client.errors import EmptyResponseError

    class LiteLLMClient(LLMClient):
        """Graphiti's ``LLMClient`` on LiteLLM. JSON is schema-guided
        (``response_format`` with the response model's JSON schema): the
        Azure deployment's API version ignores ``json_object``. Graphiti
        appends the schema to the prompt itself and retries on a
        ``JSONDecodeError`` or an empty reply
        (graphiti_core/llm_client/client.py)."""

        def __init__(self, model: str, temperature: float,
                     seed: Optional[int]):
            super().__init__(LLMConfig(
                model=model, small_model=model, temperature=temperature,
                max_tokens=MAX_TOKENS))
            self.litellm_model = model
            self.seed = seed

        async def _generate_response(self, messages, response_model=None,
                                     max_tokens=MAX_TOKENS,
                                     model_size=None, *, model=None):
            payload = [{"role": m.role, "content": m.content}
                       for m in messages]
            if response_model is not None:
                response_format = {"type": "json_schema", "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema()}}
            else:
                response_format = {"type": "json_object"}
            params: Dict[str, Any] = {
                "model": self.litellm_model,
                "messages": payload,
                "temperature": self.temperature,
                "max_tokens": min(int(max_tokens or MAX_TOKENS), MAX_TOKENS),
                "response_format": response_format,
            }
            if self.seed is not None:
                params["seed"] = int(self.seed)
            import litellm

            # Synchronous, in a worker thread: asyncio.to_thread copies
            # the context, so the usage tag reaches LiteLLM's callback.
            response = await asyncio.to_thread(litellm.completion, **params)
            text = strip_fences(response.choices[0].message.content or "")
            if not text:
                raise EmptyResponseError("empty reply")
            return json.loads(text)

    return LiteLLMClient


def llm_client(backend_llm: dict) -> Any:
    """Graphiti's LLM for ``memory.backend_llm``: the provider and model
    LiteLLM routes to, its temperature and seed."""
    provider = backend_llm.get("provider")
    model = backend_llm.get("model")
    if not provider or not model:
        raise ValueError("memory.backend_llm needs a provider and a model")
    if provider not in ("azure_openai", "ollama"):
        raise ValueError(f"unsupported backend_llm provider {provider!r}")
    usage.install_litellm_logger()
    return _llm_client_class()(
        usage.litellm_model_name(provider, model),
        float(backend_llm.get("temperature", 0.0)),
        backend_llm.get("seed"),
    )


def _embedder_class():
    from graphiti_core.embedder.client import EmbedderClient, EmbedderConfig

    class OllamaEmbedder(EmbedderClient):
        """The pinned embedding model through ``ollama.Client.embed``,
        counted per trial."""

        def __init__(self, model: str, base_url: str, dimension: int):
            import ollama

            self.config = EmbedderConfig(embedding_dim=int(dimension))
            self.model = model
            self.dimension = int(dimension)
            self.client = ollama.Client(host=base_url)
            usage.count_embeddings(self.client, model)

        def _embed(self, texts):
            result = self.client.embed(model=self.model, input=list(texts))
            vectors = [list(v) for v in result.embeddings]
            for vector in vectors:
                if len(vector) != self.dimension:
                    raise ValueError(
                        f"{self.model} returned {len(vector)} dimensions, "
                        f"not {self.dimension}")
            return vectors

        async def create(self, input_data):
            if isinstance(input_data, str):
                texts = [input_data]
            else:
                texts = [str(x) for x in input_data][:1]
            return (await asyncio.to_thread(self._embed, texts))[0]

        async def create_batch(self, input_data_list):
            if not input_data_list:
                return []
            return await asyncio.to_thread(self._embed, input_data_list)

    return OllamaEmbedder


def embedder(embedding: dict) -> Any:
    """Graphiti's embedder for ``memory.embedding``."""
    if (embedding or {}).get("provider", "ollama") != "ollama":
        raise ValueError("memory.embedding: only ollama is supported")
    return _embedder_class()(
        embedding.get("model", "nomic-embed-text"),
        embedding.get("ollama_base_url", "http://localhost:11434"),
        embedding.get("dimension", 768),
    )


def _reranker_class():
    from graphiti_core.cross_encoder.client import CrossEncoderClient

    class NoReranker(CrossEncoderClient):
        """No cross-encoder: Graphiti's ``search()`` and ingestion call
        none, and a call would mean a search the design does not use."""

        async def rank(self, query, passages):
            raise RuntimeError("no cross-encoder is configured")

    return NoReranker


def neo4j_settings(config: Optional[dict] = None) -> Tuple[str, str, str]:
    """``(uri, user, password)``: the config's, else ``NEO4J_URI``,
    ``NEO4J_USER`` and ``NEO4J_PASSWORD`` from the environment."""
    config = config or {}
    uri = config.get("uri") or os.environ.get("NEO4J_URI")
    user = config.get("user") or os.environ.get("NEO4J_USER") or "neo4j"
    password = config.get("password") or os.environ.get("NEO4J_PASSWORD")
    if not uri or not password:
        raise ValueError(
            "Graphiti needs NEO4J_URI and NEO4J_PASSWORD (AIOS/.env)")
    return uri, user, password


class GraphitiRunner:
    """One background event loop for Graphiti's async API. ``run``
    blocks until the coroutine is done and carries the caller's usage
    tag into it."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        # One lock per group, taken on the loop: Graphiti requires a
        # group's writes one at a time (graphiti_core/graphiti.py).
        self.locks: Dict[str, asyncio.Lock] = {}
        self.thread = threading.Thread(
            target=self.loop.run_forever, name="graphiti-loop", daemon=True)
        self.thread.start()

    def run(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        tag = usage.current_tag()

        async def call():
            with usage.tagged(tag):
                return await fn(*args, **kwargs)

        return asyncio.run_coroutine_threadsafe(call(), self.loop).result()

    def lock(self, group: str) -> asyncio.Lock:
        """The group's write lock; call on the loop only."""
        if group not in self.locks:
            self.locks[group] = asyncio.Lock()
        return self.locks[group]

    def close(self) -> None:
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)


def build_graphiti(runner: GraphitiRunner, backend_llm: dict,
                   embedding: dict, neo4j: Optional[dict] = None,
                   llm: Any = None) -> Any:
    """A ``Graphiti`` client on the runner's loop, its indices built:
    the pinned LLM (or ``llm``, for tests), the pinned embedder, no
    cross-encoder."""
    uri, user, password = neo4j_settings(neo4j)
    llm = llm if llm is not None else llm_client(backend_llm)
    vectors = embedder(embedding)

    async def make():
        from graphiti_core import Graphiti

        graphiti = Graphiti(uri, user, password, llm_client=llm,
                            embedder=vectors,
                            cross_encoder=_reranker_class()())
        await graphiti.build_indices_and_constraints()
        return graphiti

    return runner.run(make)


_SHARED: Dict[str, Tuple[GraphitiRunner, Any]] = {}
_SHARED_LOCK = threading.Lock()


def shared_graphiti(backend_llm: dict, embedding: dict,
                    neo4j: Optional[dict] = None) -> Tuple[GraphitiRunner,
                                                           Any]:
    """The process's one runner and ``Graphiti`` client for these
    settings: every provider and native agent of a process shares it
    (one loop thread, one Neo4j connection pool), instead of one per
    agent built per trial. Never closed: it lives as long as the
    process."""
    key = json.dumps([backend_llm, embedding, neo4j_settings(neo4j)],
                     sort_keys=True, default=str)
    with _SHARED_LOCK:
        if key not in _SHARED:
            runner = GraphitiRunner()
            _SHARED[key] = (runner, build_graphiti(
                runner, backend_llm, embedding, neo4j))
        return _SHARED[key]


def versions(runner: GraphitiRunner, graphiti: Any) -> Dict[str, str]:
    """The installed graphiti-core and Neo4j driver, and the Neo4j
    server's version and edition, for the run's provenance."""
    from importlib.metadata import version

    async def server():
        records, _, _ = await graphiti.driver.execute_query(
            "CALL dbms.components() YIELD versions, edition "
            "RETURN versions[0] AS version, edition")
        record = records[0]
        return f"{record['version']} {record['edition']}"

    return {"graphiti_core": version("graphiti-core"),
            "neo4j_driver": version("neo4j"),
            "neo4j_server": runner.run(server)}


def utc_time(value: Any = None) -> datetime:
    """A timezone-aware reference time: an ISO string or a datetime as
    UTC, else now."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            moment = datetime.now(timezone.utc)
    else:
        moment = datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment
