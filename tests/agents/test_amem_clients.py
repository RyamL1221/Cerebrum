"""A-MEM's clients and stores (``cerebrum/utils/amem.py``; NeurIPS
Subtask 17, AIOS docs/AMEM_BACKEND.md), which every locus builds A-MEM
from: the pinned LLM call, the shared stores, the pinned embedder, the
notes a write's evolution changed, and the collections' names. No LLM
or embedding call is made."""
import contextlib
import hashlib
import json
import re
import uuid
from types import SimpleNamespace

import pytest

from cerebrum.utils import amem, usage


def amem_installed() -> bool:
    try:
        import agentic_memory.memory_system  # noqa: F401
    except Exception:
        return False
    return True


needs_amem = pytest.mark.skipif(
    not amem_installed(), reason="needs agentic-memory (A-mem-sys) installed")

BACKEND_LLM = {"provider": "azure_openai", "model": "gpt-4o",
               "temperature": 0.0, "seed": 20261105}
EMBEDDING = {"provider": "ollama", "model": "nomic-embed-text",
             "dimension": 768}


def test_amems_llm_is_the_pinned_backend_llm(monkeypatch):
    """A-MEM's LLM is ``memory.backend_llm``: LiteLLM's Azure route for
    the pinned model, temperature 0 whatever A-MEM asks (its default is
    1.0), the seed, A-MEM's own system message and ``response_format``,
    and the reply without code fences; and the usage logger that records
    each call to the trial is installed (a native process installs it
    nowhere else)."""
    import litellm

    installed, calls = [], []
    monkeypatch.setattr(usage, "install_litellm_logger",
                        lambda: installed.append(True))

    def completion(**params):
        calls.append(params)
        message = SimpleNamespace(content='```json\n{"tags": []}\n```')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(litellm, "completion", completion)
    llm = amem.llm_controller(BACKEND_LLM)
    assert installed == [True]
    schema = {"type": "json_schema", "json_schema": {"name": "analysis"}}
    assert llm.get_completion("Analyze this.", response_format=schema,
                              temperature=1.0) == '{"tags": []}'
    (params,) = calls
    assert params["model"] == "azure/gpt-4o"
    assert params["temperature"] == 0.0
    assert params["seed"] == 20261105
    assert params["response_format"] == schema
    assert params["messages"] == [
        {"role": "system", "content": "You must respond with a JSON object."},
        {"role": "user", "content": "Analyze this."}]


def test_the_agents_of_a_process_share_its_stores(monkeypatch):
    """One configuration, one set of stores: a replicated or native
    cell's agents read the notes its writers wrote."""
    monkeypatch.setattr(usage, "install_litellm_logger", lambda: None)
    namespace = uuid.uuid4().hex[:8]
    first = amem.shared_stores(BACKEND_LLM, EMBEDDING, namespace)
    assert amem.shared_stores(BACKEND_LLM, EMBEDDING, namespace) is first
    assert amem.shared_stores(BACKEND_LLM, EMBEDDING,
                              namespace + "x") is not first


@needs_amem
def test_each_store_embeds_with_the_pinned_model():
    """A user's collection embeds with ``memory.embedding`` (not
    Chroma's default model), and its store keeps A-MEM's default of
    consolidating every 100 evolutions, which no benchmark store
    reaches."""
    function = amem.embedding_function(EMBEDDING)
    seen = []

    def embed(model, input):
        seen.append((model, list(input)))
        return SimpleNamespace(embeddings=[[0.0] * 767 + [1.0]
                                           for _ in input])

    function.client.embed = embed
    stores = amem.Stores(None, function, uuid.uuid4().hex[:8])
    store = stores.store("u1")
    store.retriever.collection.add(ids=["n1"],
                                   documents=["My chat app is Slack."])
    assert seen == [("nomic-embed-text", ["My chat app is Slack."])]
    assert store.evo_threshold == 100


class EvolvingStore:
    """An A-MEM store whose write changes one note's tags and leaves the
    other note as it was."""

    def __init__(self):
        self.memories = {
            name: SimpleNamespace(tags=["note"], context="About it.",
                                  links=[])
            for name in ("a", "b")}

    def add_note(self, content, **kwargs):
        self.memories["a"].tags = ["note", "evolved"]
        self.memories["n"] = SimpleNamespace(tags=[], context="", links=[])
        return "n"


def test_a_write_counts_the_notes_its_evolution_changed(caplog):
    """Only the notes whose tags, context or links changed count (a
    change of tags alone too), and each write logs the count at INFO in
    the line the readings count (AIOS docs/AMEM_BACKEND.md, "One note
    per write")."""
    caplog.set_level("INFO", logger="cerebrum.utils.amem")
    assert amem.add_note(EvolvingStore(), "I use Rust.") == ("n", ["a"])
    assert [(r.levelname, r.getMessage()) for r in caplog.records
            if r.name == "cerebrum.utils.amem"] == [
        ("INFO", "A-MEM evolved 1 note(s) at note n")]


def test_two_user_ids_never_share_a_collection():
    """A V2 variant's email id and the base id share their first 32
    readable characters in a long id; the SHA-256 digest keeps their
    collections apart (a V2 agent's note opens a store of its own)."""
    base = "u" * 40
    variant = base + "@users.example"
    assert amem.collection_name(base) != amem.collection_name(variant)
    digest = hashlib.sha256(variant.encode("utf-8")).hexdigest()[:12]
    assert amem.collection_name(variant).endswith("_" + digest)


def test_a_native_amem_write_gives_amems_time(monkeypatch):
    """native_amem's write: the metadata as the note's ``category`` and
    the time in A-MEM's ``YYYYMMDDHHMM``, which its evolution prompt
    shows the LLM."""
    from cerebrum.example.agents.native import agents as native

    seen = {}

    def add_note(store, text, **kwargs):
        seen.update(kwargs, store=store, text=text)
        return "n1", []

    monkeypatch.setattr(amem, "add_note", add_note)
    memory = native.NativeMemory.__new__(native.NativeMemory)
    memory.amem = SimpleNamespace(store=lambda user: f"store of {user}",
                                  lock=lambda user: contextlib.nullcontext())
    assert memory._amem_write("I use Rust.", {"owner_agent": "a"},
                              "u1") == "n1"
    assert seen["store"] == "store of u1" and seen["text"] == "I use Rust."
    assert json.loads(seen["category"]) == {"owner_agent": "a"}
    assert re.fullmatch(r"\d{12}", seen["time"])
