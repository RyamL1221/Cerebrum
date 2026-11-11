"""Helpers for tests of Graphiti in the native locus (NeurIPS Subtask 16).

A copy of AIOS tests/modules/memory/_graphiti_script.py's scripted LLM:
the two repos' tests do not import each other.

``ScriptedLLM`` answers Graphiti's prompts offline and deterministically
(docs/GRAPHITI_BACKEND.md, "Tests"): the user and one entity per fact;
each fact worded as the write's text (``split=False``, the contract
tests' verbatim case) or one fact per sentence (``split=True``); no
duplicate entities, no contradictions, no dates. Graphiti itself still
runs every step on the real Neo4j and the pinned embedder: entity
resolution, the verbatim merge of a restated fact, storage, search.

``drop_groups`` deletes a test's groups from the shared database.
"""
import hashlib
import json
import os
import re
import socket
import uuid
from pathlib import Path

import pytest

AIOS_ROOT = Path(__file__).resolve().parents[3] / "AIOS"
# The prompt templates put the message between the tags on lines of
# its own; capture it exactly, trailing spaces included.
CURRENT = re.compile(
    r"<CURRENT[ _]MESSAGE>\n(.*?)\n</CURRENT[ _]MESSAGE>", re.DOTALL)
ROLE = re.compile(r"^(?:\[[^\]]*\]\s*)?(?:user|assistant): ",
                  re.IGNORECASE)
COUNT = re.compile(r"contains (\d+) entities")
ENTITIES = re.compile(r"<ENTITIES>\s*(.*?)\s*</ENTITIES>", re.DOTALL)


def load_env() -> None:
    """NEO4J_* from AIOS/.env, without overriding the environment."""
    path = AIOS_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def neo4j_ready() -> bool:
    load_env()
    if not os.environ.get("NEO4J_PASSWORD"):
        return False
    try:
        with socket.create_connection(("127.0.0.1", 7687), timeout=1):
            return True
    except OSError:
        return False


needs_neo4j = pytest.mark.skipif(
    not neo4j_ready(), reason="needs the local Neo4j (docs/GRAPHITI_BACKEND.md)")


def topic(fact: str) -> str:
    return "topic " + hashlib.sha256(fact.encode()).hexdigest()[:8]


def _llm_class():
    from graphiti_core.llm_client.client import LLMClient
    from graphiti_core.llm_client.config import LLMConfig

    class ScriptedLLM(LLMClient):
        def __init__(self, split: bool = False):
            super().__init__(LLMConfig(model="scripted",
                                       small_model="scripted"))
            self.split = split
            self.calls = []

        def facts(self, prompt: str):
            match = CURRENT.search(prompt)
            text = match.group(1) if match else ""
            lines = [ROLE.sub("", line, count=1) for line in text.split("\n")]
            text = "\n".join(line for line in lines if line.strip())
            if not self.split:
                return [text] if text.strip() else []
            return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
                    if s.strip()]

        async def _generate_response(self, messages, response_model=None,
                                     max_tokens=None, model_size=None, *,
                                     model=None):
            prompt = "\n".join(m.content for m in messages)
            name = response_model.__name__ if response_model else ""
            self.calls.append(name)
            if name == "ExtractedEntities":
                return {"extracted_entities": [
                    {"name": "user", "entity_type_id": 0}] + [
                    {"name": topic(f), "entity_type_id": 0}
                    for f in self.facts(prompt)]}
            if name == "ExtractedEdges":
                return {"edges": [
                    {"source_entity_name": "user",
                     "target_entity_name": topic(f),
                     "relation_type": "STATES", "fact": f,
                     "valid_at": None, "invalid_at": None}
                    for f in self.facts(prompt)]}
            if name == "NodeResolutions":
                count = COUNT.search(prompt)
                n = int(count.group(1)) if count else 0
                names = [""] * n
                block = ENTITIES.search(prompt)
                try:
                    for item in json.loads(block.group(1)) if block else []:
                        if 0 <= int(item.get("id", -1)) < n:
                            names[int(item["id"])] = item.get("name", "")
                except (ValueError, TypeError, AttributeError):
                    pass
                return {"entity_resolutions": [
                    {"id": i, "name": names[i], "duplicate_candidate_id": -1}
                    for i in range(n)]}
            if name == "EdgeDuplicate":
                return {"duplicate_facts": [], "contradicted_facts": []}
            if name == "EdgeTimestamps":
                return {"valid_at": None, "invalid_at": None}
            if name == "BatchEdgeTimestamps":
                return {"timestamps": []}
            if name == "SummarizedEntities":
                return {"summaries": []}
            return {}

    return ScriptedLLM


def scripted_llm(split: bool = False):
    return _llm_class()(split=split)


def drop_groups(runner, graphiti, groups) -> None:
    """Delete every node of ``groups`` from the shared database."""
    async def clear():
        await graphiti.driver.execute_query(
            "MATCH (n) WHERE n.group_id IN $groups DETACH DELETE n",
            params={"groups": list(groups)})
    runner.run(clear)
