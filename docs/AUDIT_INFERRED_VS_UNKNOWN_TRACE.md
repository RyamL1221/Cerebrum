# Trace: `audit_inferred` (5×4/3×12) vs `unknown` (2×10) audit path

Read-only diagnostic (no code changes). Determines the variable that flips
the harness audit path from populated (`injection_status="audit_inferred"`,
non-empty `injected_memory_ids`) in the Sep-9 `session_pilot_5x4_gpt` /
`session_pilot_3x12_gpt` runs to empty (`injection_status="unknown"`,
`retrieved_memories: []`, all 20/20 trials) in the Sep-10
`clean_combined_pilot` / `clean_combined_pilot_rerun` runs. All line numbers
are `benchmarks/shared_memory/{pipeline.py,run_evaluation.py}` and the sibling
AIOS `aios/memory/providers/{mem0.py,base.py}`.

**Headline:** it is **NOT session length**, config, or the invocation flags.
The two `unknown` runs have **two different** upstream causes, and the
important one is a **harness-side owner-metadata filter dropping rows the
kernel actually returned**.

---

## 1. Both run types hit the identical audit code path (no code/config diff)

- Same method `kernel_shared_adaptive`, same `trials_per_condition=10`, same
  `kernel_url=http://localhost:8000`, same gating
  (`adaptive_policy_enabled=True, static_thresholds_enabled=False`) recorded in
  every run's `experiment_metadata.gating_status_by_method`.
- **No code changed between the runs.** `git log -- pipeline.py
  run_evaluation.py` in the Sep-9→Sep-11 window shows only the session commit
  `45c0b3f` (2026-09-09 16:34); both run types execute the *same*
  `_audit_shared_memories` (pipeline.py:270) → `_build_retrieval_log_from_search`
  (pipeline.py:385), selected by the same `run_trial` branch (pipeline.py:167-184).
- Only invocation difference: 5×4/3×12 passed `--run-id sess5x4gpt` /
  `sess3x12gpt`; the 2×10 runs used auto-generated UUID run_ids (`0da89b0f`,
  `ecb3dd65`). **This is not causal** — the audit scopes by the written
  `user_id`, whatever its run_id substring.

Both runs are genuinely session-mode (both carry `session_id`/`interaction_index`),
so "one-shot vs session" is not the variable either.

## 2. The two `unknown` runs have TWO different causes

### 2a. `clean_combined_pilot` (`0da89b0f`, 13:30) — kernel-state / genuinely empty

The kernel process **(re)started at 13:54:24** — the current `kernel.log`
begins with the startup banner (`Successfully initialized LLM: …`,
chromadb `Starting component System`, `PolicyManager initialized`). The
`0da89b0f` run ran at **13:30, ~24 min BEFORE that start**, and `grep -c
0da89b0f kernel.log` = **0** — none of its activity is in the live kernel
instance. Its writes went to a prior kernel/store that is gone. So for this
run the audit legitimately retrieved nothing: **empty at the kernel/store
layer** (cause = kernel lifecycle, not harness construction). This is the
straightforward half.

### 2b. `clean_combined_pilot_rerun` (`ecb3dd65`, JSON 14:04) — harness DROPS rows the kernel returned

This is the diagnostic crux. The rerun's result JSON records
`retrieved_memories: []`, `shared_memory_count: 0`, `injection_status:
"unknown"` for **all 20 trials**, including `interaction_index=9` (which has
9 prior interactions' writes). Yet the kernel log for the **exact same
user_ids** shows the audit succeeding — see §3.

## 3. Raw request/response evidence (from `kernel.log`, run `ecb3dd65`)

Harness audit query (per `_audit_shared_memories`, pipeline.py:304-312):
`operation_type="retrieve_memory"`, `params={content=<follow_up_query>,
k=20, user_id=<session user_id>, sharing_policy="shared",
agent_name=<writer>}`, fanned out over `WRITER_AGENTS=["profile_agent",
"task_agent"]` (pipeline.py:269).

Kernel-side outcome for `alex_martinez_ecb3dd65_s0__kernel_shared_adaptive`:

```
retrieve(get_all): user_id=alex_martinez_ecb3dd65_s0__…, top_k=20, result_count=1
retrieve(get_all): user_id=alex_martinez_ecb3dd65_s0__…, top_k=20, result_count=2
…                                                          top_k=20, result_count=11
retrieve_memory sharing filter: retained 1/1 for agent=profile_agent user_id=alex_martinez_ecb3dd65_…
retrieve_memory sharing filter: retained 1/2 for agent=task_agent   user_id=alex_martinez_ecb3dd65_…
```

- **`top_k=20` is the audit fan-out** (AUDIT_TOP_K=20, pipeline.py:266). It
  returned **result_count 1..11, growing across interactions** — non-empty.
- The **sharing filter retained rows for `agent=profile_agent` and
  `agent=task_agent`** — i.e. the harness's own WRITER_AGENTS queries got
  owner-matched rows back. (The `user_id=profile_agent, top_k=5,
  result_count=0` lines are the *separate* mis-scoped diagnostic probe at
  pipeline.py:121-123 — irrelevant, see the earlier
  `MEMORY_IDS_INVOLVED_TRACE.md`.)
- Timeline: first add 13:57:07 → first audit 13:57:14 (writes precede audits);
  the JSON write time 14:04:53 is the run's end. So the kernel log **is** this
  run, and it returned non-empty — contradicting the JSON's `retrieved=0`.

Contrast — a 5×4 `audit_inferred` trial (Sep-9, from its result JSON):
`retrieval_log = {shared_memory_count: 2, retrieved_memories: [2 entries],
injected_memory_ids: [2 real ids], injection_status: "audit_inferred"}`.
Same audit request shape; the difference is purely in what survived the
harness filter.

Response-shape parsing was verified correct with a live query: the `/query`
body nests results at `response.search_results` (top-level keys:
`response, token_usage, start_times, …`), exactly the path
`_audit_shared_memories` reads (pipeline.py:316-319, 336-339). **Not a
nesting/parse bug.**

## 4. The mechanism that drops the rows (cited)

The kernel's `retrieve_memory` builds each emitted `search_results[].metadata`
via `_enrich_metadata(self._extract_filter_metadata(item))`. `_enrich_metadata`
(**AIOS `aios/memory/providers/base.py:117-128`**) does:

```python
def _enrich_metadata(metadata: dict) -> dict:
    for key in ("owner_agent", "user_id", "sharing_policy", "memory_type"):
        metadata.setdefault(key, "")     # <-- empty-string default
    return metadata
```

So when a stored Mem0 row's metadata does **not** carry `owner_agent`, the
kernel still returns the row, but its emitted `metadata.owner_agent == ""`.

The harness filter `_build_retrieval_log_from_search`
(**pipeline.py:419-425**) then does:

```python
meta = mem.get("metadata", {})
if not meta:
    continue
owner = meta.get("owner_agent", "")
mem_type = meta.get("memory_type", "")
if not owner:            # empty string is falsy → DROP the row
    continue
```

An empty `owner_agent` makes `not owner` true, so **every such row is dropped
before it can be counted or have its id read**. The result: `entries = []`,
`injected_memory_ids = []`, `shared_memory_count = 0` (pipeline.py:401-465).
Back in `run_trial`, `shared_memory_count == 0` with `share_memory=True`
takes the else-branch that sets `injection_status = "unknown"` and logs the
"Observability gap … audit query returned 0 results" warning
(**pipeline.py:176-183**).

For the 5×4/3×12 runs the retrieved rows carried a **populated** `owner_agent`
(the ProfileAgent/TaskAgent writes were tagged), so they survived the filter
→ `shared_memory_count > 0` → `injection_status = "audit_inferred"`
(pipeline.py:176-177). Same code, opposite outcome, decided entirely by
whether the retrieved rows' `metadata.owner_agent` is non-empty.

## 5. Definitive determination

The variable is **NOT** session length (3×12 succeeded), method, config,
gating, run-id, or a response-parsing/nesting bug (verified correct). It is
**the presence of a non-empty `metadata.owner_agent` on the rows the kernel
returns to the audit**:

- **`clean_combined_pilot` (`0da89b0f`) → `unknown`:** cause **(a) genuinely
  empty from the kernel/store** — the run predates the 13:54 kernel restart, so
  its writes weren't in the queried instance. Kernel-state timing, not harness
  construction.
- **`clean_combined_pilot_rerun` (`ecb3dd65`) → `unknown`:** cause **(b)
  harness-side drop** — the kernel returned non-empty, owner-matched rows
  (`top_k=20` result_count 1–11; sharing filter "retained …/… for
  agent=profile_agent/task_agent"), but the emitted
  `search_results[].metadata.owner_agent` came back as `""` (defaulted by
  AIOS `_enrich_metadata`, base.py:117-128), so the harness owner check
  (`if not owner: continue`, pipeline.py:424-425) discarded every row →
  `retrieved=0` → `unknown`.

**Fix target for Subtask 2** (not implemented here): the disagreement is at
the **metadata contract between the kernel's emitted `search_results[].metadata`
and the harness's `owner_agent` filter** — either the stored Mem0 rows are
missing `owner_agent` (write-side metadata not persisted/promoted), or the
kernel's `_enrich_metadata` empty-string default is masking a lookup the
harness then rejects. It is upstream of the id-gap and independent of session
length. The `0da89b0f` symptom is a separate, benign kernel-restart artifact.

## 6. Files / evidence cited (no edits)

- `benchmarks/shared_memory/pipeline.py` — `_audit_shared_memories` (:270,
  params :304-312, response read :316-319/:336-339, WRITER_AGENTS :269,
  AUDIT_TOP_K :266), `_build_retrieval_log_from_search` owner drop
  (:419-425, empty→`[]` :401-465), `run_trial` status set (:167-184, unknown
  :176-183), diagnostic red-herring probe (:121-123).
- AIOS `aios/memory/providers/base.py` — `_enrich_metadata` empty-string
  default for `owner_agent` (:117-128); `_apply_sharing_filter` (retained-lines
  source).
- AIOS `aios/memory/providers/mem0.py` — `retrieve_memory` emits
  `metadata=_enrich_metadata(_extract_filter_metadata(item))` per result.
- `kernel.log` — 13:54:24 restart banner; `ecb3dd65` audit `top_k=20`
  result_count 1–11; sharing-filter "retained N/M for agent=profile_agent/
  task_agent"; zero `0da89b0f` occurrences.
- Result JSONs: `session_pilot_5x4_gpt` / `_3x12_gpt` (all `audit_inferred`);
  `clean_combined_pilot` / `_rerun` (all 20 `unknown`, incl. iidx=9).
