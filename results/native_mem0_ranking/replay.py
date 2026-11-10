"""Replay native Mem0's searches from the benchmark v2 smoke (``s14b``).

For each user of the smoke's ``native_mem0`` cell, the store is rebuilt
as it was at each probe, on a copy of the cell's store: the rows the
user's probes wrote (Mem0's facts from each probe's conversation, which
carry the probe id as ``provenance_event``) are taken out, then put back
probe by probe, after that probe's searches. Mem0's history holds only
``ADD`` events and the revokes' ``DELETE`` events, all made before the
probes, so this gives each probe's store.

The searches are Mem0's own: ``Memory.search`` through the native
agents' ``NativeMemory.search``, and the kept rows are the native
assistant's own ``_select``. Per probe:

- **Reproduction.** The fetch at the consumer's k must give the rows the
  smoke recorded: ``own_fetched`` rows, and the kept ones, in order and
  with their scores, equal to ``injected_memories``.
- **Mem0's order** of all the user's rows: a search with ``top_k`` 60,
  whose pool (``max(4 * top_k, 60)`` nearest rows) holds every row of
  the user. For each row: its rank and Mem0 score, its squared L2
  distance and cosine to the question (the stored embedding against
  Mem0's own query embedding), its rank by cosine, whether the consumer
  may see it, and whether it is the target's own row or carries the
  expected or the stale value. Rows Mem0's default threshold drops
  (score below 0.1) are listed apart.

Usage, from the Cerebrum repo, with Ollama serving ``nomic-embed-text``:

    .venv/bin/python results/native_mem0_ranking/replay.py \\
        --results <results_native_mem0.json> \\
        --store .native_memory/s14b/native_mem0 \\
        --out results/native_mem0_ranking/replay.json
"""
import argparse
import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PROBES = ("recall", "recency", "contradiction")
# Mem0's payload keys that are not the write's metadata
# (mem0/memory/main.py, Memory._search_vector_store).
CORE = {"data", "hash", "created_at", "updated_at", "id", "text_lemmatized",
        "attributed_to", "user_id", "agent_id", "run_id", "actor_id", "role"}


def metadata_of(payload: dict) -> dict:
    """A row's metadata as ``NativeMemory.search`` builds it: Mem0's
    additional payload keys, and the promoted ``user_id``."""
    meta = {k: v for k, v in payload.items() if k not in CORE}
    meta["user_id"] = payload.get("user_id")
    return meta


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a))
                  * math.sqrt(sum(y * y for y in b)))


def sq_distance(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def history_events(store: str) -> dict:
    """Counts of Mem0's history events by type."""
    with sqlite3.connect(os.path.join(store, "history.db")) as db:
        return dict(db.execute(
            "select event, count(*) from history group by event"
        ).fetchall())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--results", required=True)
    parser.add_argument("--store", required=True,
                        help="the cell's native_mem0 directory "
                             "(chroma/ and history.db)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--full-k", type=int, default=60)
    args = parser.parse_args()

    events = history_events(args.store)
    if set(events) - {"ADD", "DELETE"}:
        raise SystemExit(f"history has other events than ADD and DELETE: "
                         f"{events}; the replay assumes none")

    work = tempfile.mkdtemp(prefix="mem0_replay_")
    shutil.copytree(args.store, os.path.join(work, "native_mem0"))
    # Read at import by backends.STORE_ROOT.
    os.environ["CEREBRUM_NATIVE_MEMORY_DIR"] = work
    sys.path.insert(0, REPO)
    from benchmarks.shared_memory.probes import match_entry
    from cerebrum.example.agents.native import backends
    from cerebrum.example.agents.native.agents import (
        NativeAssistantAgent,
        NativeMemory,
    )
    from cerebrum.example.agents.native.sharing import in_partition, visible

    with open(args.results) as handle:
        data = json.load(handle)
    settings = backends.NativeSettings.from_kernel_config(
        data["experiment_metadata"]["config_snapshot"]
    )
    memory = NativeMemory("mem0", settings)
    assistant = NativeAssistantAgent("assistant_agent", memory)
    collection = memory.mem0.vector_store.collection

    out = {"results": os.path.basename(args.results),
           "run_id": data["experiment_metadata"].get("run_id"),
           "store": os.path.normpath(args.store),
           "history_events": events, "full_k": args.full_k, "probes": []}
    for trial in data["conditions"][0]["trials"]:
        uid = trial["user_id"]
        got = collection.get(where={"user_id": uid},
                             include=["embeddings", "metadatas", "documents"])
        rows = {
            mid: {"embedding": [float(x) for x in emb], "payload": meta,
                  "document": doc}
            for mid, emb, meta, doc in zip(
                got["ids"], got["embeddings"], got["metadatas"],
                got["documents"])
        }
        probe_ids = [p["probe_id"] for p in trial["probe_results"]]
        written = {pid: [mid for mid, r in rows.items()
                         if r["payload"].get("provenance_event") == pid]
                   for pid in probe_ids}
        held = [mid for ids in written.values() for mid in ids]
        if held:
            collection.delete(ids=held)
        present = set(rows) - set(held)
        for probe in trial["probe_results"]:
            if probe["type"] in PROBES and probe.get("error") is None:
                out["probes"].append(replay_probe(
                    trial, probe, uid, rows, present, memory, assistant,
                    args.full_k, match_entry, in_partition, visible))
            back = written[probe["probe_id"]]
            if back:
                kwargs = {}
                if all(rows[m]["document"] is not None for m in back):
                    kwargs["documents"] = [rows[m]["document"] for m in back]
                collection.add(
                    ids=back,
                    embeddings=[rows[m]["embedding"] for m in back],
                    metadatas=[rows[m]["payload"] for m in back], **kwargs)
                present |= set(back)
    shutil.rmtree(work)

    reproduced = sum(p["reproduced"] for p in out["probes"])
    out["reproduced"] = f"{reproduced} of {len(out['probes'])}"
    with open(args.out, "w") as handle:
        json.dump(out, handle, indent=0)
    print(f"reproduced {out['reproduced']} recorded fetches; wrote {args.out}")
    return 0 if reproduced == len(out["probes"]) else 1


def replay_probe(trial, probe, uid, rows, present, memory, assistant,
                 full_k, match_entry, in_partition, visible) -> dict:
    question = probe["question"]
    diagnostics = probe["diagnostics"]
    k = diagnostics["top_k_used"]["own"]
    fetched = memory.search(question, uid, k)
    kept, _ = assistant._select(fetched, uid, k)
    recorded = diagnostics["injected_memories"]
    reproduced = (
        len(fetched) == diagnostics["own_fetched"]
        and [r["memory_id"] for r in kept]
        == [m["memory_id"] for m in recorded]
        and all(math.isclose(r["score"], m["match_score"], abs_tol=1e-9)
                for r, m in zip(kept, recorded))
    )

    order = memory.search(question, uid, full_k)
    if [r["memory_id"] for r in order[:k]] != \
            [r["memory_id"] for r in fetched]:
        raise SystemExit(f"{probe['probe_id']}: the top {k} of the full "
                         "order differ from the fetch")
    query = memory.mem0.embedding_model.embed(question, "search")
    by_cosine = sorted(present, key=lambda m: -cosine(
        query, rows[m]["embedding"]))
    cosine_rank = {m: i + 1 for i, m in enumerate(by_cosine)}
    expected = probe.get("expected") or []
    stale = [] if probe["type"] == "recall" else (probe.get("forbidden") or [])
    fetched_ids = {r["memory_id"] for r in fetched}
    kept_ids = {r["memory_id"] for r in kept}

    def describe(mid, rank=None, score=None):
        row = rows[mid]
        meta = metadata_of(row["payload"])
        content = row["payload"].get("data", "")
        distance = sq_distance(query, row["embedding"])
        return {
            "rank": rank,
            "memory_id": mid,
            "mem0_score": score,
            "sq_distance": distance,
            "cosine": cosine(query, row["embedding"]),
            "cosine_rank": cosine_rank[mid],
            "score_is_clamped_distance": (
                None if score is None
                else math.isclose(score, min(distance, 1.0), abs_tol=1e-6)),
            "visible": bool(in_partition(uid, meta)
                            and visible("assistant_agent", meta)),
            "owner_agent": meta.get("owner_agent"),
            "memory_type": meta.get("memory_type"),
            "provenance_event": meta.get("provenance_event"),
            "fact_key": meta.get("fact_key"),
            "session": meta.get("session"),
            "target": meta.get("provenance_event") == probe["target_event"],
            "carries_expected": any(match_entry(content, e) for e in expected),
            "carries_stale": any(match_entry(content, e) for e in stale),
            "in_fetch": mid in fetched_ids,
            "injected": mid in kept_ids,
            "content": content,
        }

    ranked = [describe(r["memory_id"], i + 1, r["score"])
              for i, r in enumerate(order)]
    in_order = {r["memory_id"] for r in order}
    dropped = [describe(m) for m in by_cosine if m not in in_order]
    return {
        "user": trial["trial_index"],
        "user_id": uid,
        "probe_id": probe["probe_id"],
        "type": probe["type"],
        "slot": probe.get("slot"),
        "question": question,
        "expected": [e["value"] for e in expected],
        "stale": [e["value"] for e in stale],
        "target_event": probe["target_event"],
        "passed": probe["passed"],
        "contaminated": probe.get("contaminated"),
        "k": k,
        "rows_at_probe": len(present),
        "recorded_fetch": diagnostics["own_fetched"],
        "reproduced": reproduced,
        "order": ranked,
        "dropped_by_threshold": dropped,
    }


if __name__ == "__main__":
    sys.exit(main())
