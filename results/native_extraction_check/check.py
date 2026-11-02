"""Mem0 infer=True extraction check on 20 real writer outputs."""
import json, os, re, sys, tempfile, time
from dotenv import dotenv_values
from mem0 import Memory

SP = os.path.dirname(os.path.abspath(__file__))
AZ = dotenv_values(sys.argv[1])
items = json.load(open(os.path.join(SP, "..", "writer_outputs.json")))

sys.path.insert(0, SP)
from render import normalize, render as nl


def values(memory_type, d):
    fields = normalize(memory_type, d)["fields"]
    out = []
    for v in fields.values():
        out += v if isinstance(v, list) else [v]
    return [str(v) for v in out]

def covered(value, text):
    words = [w for w in re.findall(r"[a-z0-9+#.]+", value.lower()) if len(w) > 3] or [value.lower()]
    hit = sum(w in text for w in words)
    return hit / len(words) >= 0.6

LLMS = {
    "qwen2.5:7b": {"provider": "ollama", "config": {"model": "qwen2.5:7b", "ollama_base_url": "http://localhost:11434", "temperature": 0.1}},
    "llama3.1:8b": {"provider": "ollama", "config": {"model": "llama3.1:8b", "ollama_base_url": "http://localhost:11434", "temperature": 0.1}},
    "gpt-4o": {"provider": "azure_openai", "config": {"model": "gpt-4o", "temperature": 0.1, "azure_kwargs": {
        "api_key": AZ["AZURE_API_KEY"], "azure_endpoint": AZ["AZURE_API_BASE"],
        "api_version": AZ["AZURE_API_VERSION"], "azure_deployment": "gpt-4o"}}},
}
report = {}
for llm_name in sys.argv[2].split(","):
    for fmt in ("json", "nl"):
        d = tempfile.mkdtemp(dir=SP)
        m = Memory.from_config({
            "llm": LLMS[llm_name],
            "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text", "ollama_base_url": "http://localhost:11434", "embedding_dims": 768}},
            "vector_store": {"provider": "chroma", "config": {"collection_name": "check", "path": d}},
            "history_db_path": os.path.join(d, "history.db"),
        })
        rows = []
        for memory_type in ("profile", "task_context"):
            for i, item in enumerate(items[memory_type]):
                data = json.loads(item["content"])
                text = item["content"] if fmt == "json" else nl(memory_type, data)
                user = f"{memory_type}_{i}"
                start = time.time()
                try:
                    m.add([{"role": "user", "content": text}], user_id=user,
                          agent_id=item["owner"], metadata={"memory_type": memory_type, "sharing_policy": "shared"}, infer=True)
                    error = None
                except Exception as e:
                    error = repr(e)[:200]
                seconds = time.time() - start
                stored = m.get_all(filters={"user_id": user}, top_k=100)["results"]
                joined = " ".join(r["memory"] for r in stored).lower()
                vals = values(memory_type, data)
                rows.append({"type": memory_type, "user": user, "stored": len(stored),
                    "coverage": sum(covered(v, joined) for v in vals) / len(vals),
                    "seconds": round(seconds, 1), "error": error,
                    "memories": [r["memory"] for r in stored],
                    "agent_ids": sorted({r.get("agent_id") for r in stored}),
                    "metadata_kept": all((r.get("metadata") or {}).get("sharing_policy") == "shared" for r in stored)})
        key = f"{llm_name}/{fmt}"
        report[key] = rows
        n = len(rows)
        print(key, "empty:", sum(r["stored"] == 0 for r in rows), "/", n,
              "mean rows:", round(sum(r["stored"] for r in rows) / n, 1),
              "coverage profile:", round(sum(r["coverage"] for r in rows if r["type"] == "profile") / 10, 2),
              "task:", round(sum(r["coverage"] for r in rows if r["type"] == "task_context") / 10, 2),
              "errors:", sum(bool(r["error"]) for r in rows),
              "metadata kept:", all(r["metadata_kept"] for r in rows),
              "mean s:", round(sum(r["seconds"] for r in rows) / n, 1), flush=True)
json.dump(report, open(os.path.join(SP, f"report_{sys.argv[2].replace(',', '_')}.json"), "w"), indent=1)
