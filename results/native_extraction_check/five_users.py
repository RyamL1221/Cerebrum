import json, os, sys, tempfile
from dotenv import dotenv_values
from mem0 import Memory
SP = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SP)
from render import render
AZ = dotenv_values(sys.argv[1])
items = json.load(open(os.path.join(SP, "..", "writer_outputs.json")))
d = tempfile.mkdtemp(dir=SP)
config = {
    "llm": {"provider": "azure_openai", "config": {"model": "gpt-4o", "temperature": 0.1, "azure_kwargs": {
        "api_key": AZ["AZURE_API_KEY"], "azure_endpoint": AZ["AZURE_API_BASE"],
        "api_version": AZ["AZURE_API_VERSION"], "azure_deployment": "gpt-4o"}}},
    "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text", "ollama_base_url": "http://localhost:11434", "embedding_dims": 768}},
    "vector_store": {"provider": "chroma", "config": {"collection_name": "native_mem0", "path": d}},
    "history_db_path": os.path.join(d, "history.db"),
}
profile_client, task_client, assistant_client = (Memory.from_config(config) for _ in range(3))
def visible(agent, user, r):
    meta = r.get("metadata") or {}
    return r.get("user_id") == user and (meta.get("owner_agent") == agent or meta.get("sharing_policy") == "shared")
summary = []
for i in range(5):
    user = f"user_{i}"
    prof, task = json.loads(items["profile"][i]["content"]), json.loads(items["task_context"][i]["content"])
    for client, agent, mtype, data in ((profile_client, "profile_agent", "profile", prof), (task_client, "task_agent", "task_context", task)):
        client.add([{"role": "user", "content": render(mtype, data)}], user_id=user, agent_id=agent,
                   metadata={"owner_agent": agent, "memory_type": mtype, "sharing_policy": "shared", "user_id": user}, infer=True)
    task_client.add([{"role": "user", "content": "Note to self: my manager's phone number is 555-0101."}], user_id=user, agent_id="task_agent",
                    metadata={"owner_agent": "task_agent", "memory_type": "task_context", "sharing_policy": "private", "user_id": user}, infer=True)
    query = "What should I focus on next, and with which tools?"
    results = assistant_client.search(query, filters={"user_id": user}, top_k=10)["results"]
    kept = [r for r in results if visible("assistant_agent", user, r)]
    by_agent = {}
    for r in results: by_agent[r.get("agent_id")] = by_agent.get(r.get("agent_id"), 0) + 1
    print(f"{user}: returned {len(results)} by agent_id {by_agent}; visible {len(kept)}; private leaked {any('555' in r['memory'] for r in kept)}")
    for r in results[:12]:
        print(f"   {r['score']:.3f} {r.get('agent_id'):13} {(r.get('metadata') or {}).get('sharing_policy'):7} {r['memory'][:90]}")
    name = (prof.get("user_name") or prof.get("username") or next(iter(prof.values()), {}).get("name", ""))
    summary.append({"user": user, "returned": len(results), "visible": len(kept),
                    "agents": sorted(a for a in by_agent if a), "name_found": any(name.split()[0] in r["memory"] for r in kept),
                    "private_returned": any("555" in r["memory"] for r in results), "private_visible": any("555" in r["memory"] for r in kept)})
json.dump(summary, open(os.path.join(SP, "five_users.json"), "w"), indent=1)
print(json.dumps(summary))
