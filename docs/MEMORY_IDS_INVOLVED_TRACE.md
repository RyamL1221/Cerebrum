# Harness-side trace: how `memory_ids_involved` is built for `report_reward`

Read-only diagnostic trace (no code changes) of the Cerebrum benchmark
harness path from a per-trial retrieval to the `report_reward` call, to
locate where/why the prior pilot
(`ADAPTIVE_POLICY_COMBINED_FIX_PILOT_REPORT.md`) saw the harness's own
retrieval return **0 memories for a user with confirmed writes**. Pairs
with the AIOS-side trace (`AIOS_REWARD_LOOP_FIX_REPORT.md`).

All line numbers are `benchmarks/shared_memory/{pipeline.py,run_evaluation.py}`
and `cerebrum/memory/apis.py` as currently on `feature/self-improving-memory`.

---

## 1. The end-to-end harness path (with cited lines)

```
AgentPipeline.run_trial(trial_data)                      pipeline.py:81
  ├─ [DIAGNOSTIC, share_memory only] search_memories(...) pipeline.py:121-123
  │      → logs "Mem0 diagnostic: 0 results…" on empty     pipeline.py:136-140
  │      → NOT used for memory_ids_involved (log only)
  ├─ injection_diagnostics = _extract_injection_diagnostics(assistant_result)  pipeline.py:165
  ├─ if injection_diagnostics.injected_count > 0:          pipeline.py:168
  │      retrieval_log = _retrieval_log_from_diagnostics() pipeline.py:169   (status "confirmed")
  │  else:                                                 pipeline.py:172
  │      retrieval_log = _audit_shared_memories(           pipeline.py:172-175
  │                          trial_data.user_id, trial_data.follow_up_query)
  └─ return PipelineResult(retrieval_log=retrieval_log,…)  pipeline.py:186-196

EvaluationOrchestrator.run_single_trial(...)             run_evaluation.py
  memory_ids_involved = list(retrieval_log.injected_memory_ids) if retrieval_log else []   :523-526
  POST {kernel}/memory/report_reward  json={agent_name, memory_ids_involved, reward_value, trial_metadata}   :566-576
```

So `memory_ids_involved` = **`retrieval_log.injected_memory_ids`**
(run_evaluation.py:523-526), and `retrieval_log` is built by exactly one
of two `run_trial` branches (pipeline.py:167-184). In every real
`kernel_shared*` run the kernel returns no inline diagnostics, so
`injection_status == "audit_inferred"` and the **audit branch**
(`_audit_shared_memories`) is what populates `injected_memory_ids`.

## 2. The per-trial retrieval request — exact endpoint + params

`_audit_shared_memories` (pipeline.py:270) fans out one `retrieve_memory`
query **per writer agent** in `WRITER_AGENTS = ["profile_agent",
"task_agent"]` (pipeline.py:269), each via `send_request` (pipeline.py:312):

```python
query_obj = MemoryQuery(
    operation_type="retrieve_memory",          # pipeline.py:304
    params={
        "content": query_text,                 # = trial_data.follow_up_query
        "k": self.AUDIT_TOP_K,                  # = 20  (MAX_INJECTED_MEMORIES*4, pipeline.py:265-267)
        "user_id": user_id,                     # = trial_data.user_id  (the session user_id)
        "sharing_policy": "shared",
        "agent_name": writer_agent,             # "profile_agent" / "task_agent"
    },
)
result = send_request(writer_agent, query_obj, config.get_kernel_url())   # pipeline.py:312
```

`send_request` (`cerebrum/utils/communication.py`) POSTs to `/query` with
top-level `agent_name=writer_agent` and `query_data=params`. Per the SDK
contract in `search_memories` (cerebrum/memory/apis.py docstring): when
`user_id` **is** provided the kernel scopes to that user across agents;
`sharing_policy="shared"` filters to shared memories. The audit therefore
sends the **correct** session `user_id` and routes through each writer's
name so the kernel returns that writer's owned rows.

## 3. Which response field becomes `memory_ids_involved`

The merged/deduped audit results pass through
`_build_retrieval_log_from_search` (pipeline.py:385). Per retained entry:

```python
score = mem.get("score")
if score is not None and score < self.RELEVANCE_THRESHOLD:   # 0.3, pipeline.py:263
    continue
meta = mem.get("metadata", {})
if not meta: continue
owner = meta.get("owner_agent", "")
if not owner: continue
mem_id = mem.get("memory_id") or mem.get("id")               # pipeline.py:428
...
if mem_id:
    injected_memory_ids.append(str(mem_id))                  # pipeline.py:436-437
```

So `injected_memory_ids` is populated from the **audit-retrieval results
after the harness's own relevance/owner filter**, reading each item's
`memory_id` (or `id`) field (pipeline.py:428). It is NOT the kernel's
gate-injected set and NOT the raw pre-filter set — it is the
harness-filtered retrieval set. `run_evaluation.py:523-526` copies that
list verbatim into `memory_ids_involved`.

## 4. Where the "0 memories" actually comes from — TWO different things

The prior pilot's "0 memories for a user with confirmed writes" conflates
two independent code paths. Only one is a request bug, and it is NOT the
one that feeds `report_reward`.

### 4a. The `0 results` LOG line = a request-construction bug in the DIAGNOSTIC call (does NOT feed report_reward)

The "Mem0 diagnostic: 0 results for user_id=… fact extraction may have
failed silently" warning is emitted at pipeline.py:136-140 by the
**diagnostic** call at pipeline.py:121-123:

```python
diag_response = search_memories(
    agent_name="profile_agent",
    query=f"profile {trial_data.user_id}",
)   # NOTE: no user_id= kwarg, no sharing_policy=
```

This call **omits `user_id` entirely**. Per the SDK contract
(cerebrum/memory/apis.py `search_memories`): with no `user_id`, the kernel
does a *default agent-scoped* search restricted to `agent_name`, and
kernel-side `_get_client_for_user` resolves the collection from the
fallback identity (`agent_name="profile_agent"`), **not** the session
`user_id` where the writes actually landed. It therefore queries the wrong
(effectively empty) collection and returns 0 — regardless of whether the
write succeeded. **This is a genuine request-construction bug** (a missing
`user_id=` argument, pipeline.py:121-123), but it is a **diagnostic log
only**: its result (`diag_results`) is never assigned to
`retrieval_log`, `injected_memory_ids`, or `memory_ids_involved`. It is a
red herring for the reward loop and explains the alarming log line the
pilot saw.

### 4b. Empty `memory_ids_involved` (the real reward-loop symptom) = a response/contract gap, NOT wrong audit params

When `memory_ids_involved` was historically empty, it was because the
audit *did* retrieve entries but each entry carried **no `memory_id`/`id`
field to read**. `_build_retrieval_log_from_search` reads
`mem.get("memory_id") or mem.get("id")` (pipeline.py:428); when the Mem0
provider's `retrieve_memory` `search_results` omitted a per-entry id, the
filter retained entries (non-zero `shared_memory_count`) but
`injected_memory_ids` stayed empty — the exact condition the harness
already warns about at pipeline.py:449-459 ("N memories retained but none
carried a memory_id/id… Likely the Mem0 provider… see
docs/mem0-search-results-memory-id-gap.md"). This is a **response-parsing
/ upstream-contract gap** (right request, right field read, but the field
was absent in the payload), not a scoping mistake in the audit request.

## 5. Current reality (this session's live GPT-4o pilots) — the audit path now works

The `kernel_shared_adaptive` 5×4 and 3×12 pilots run this session show the
audit path returning real IDs, so `memory_ids_involved` is **non-empty
today**:

- Harness logs: `Audit post-merge: merged_count=4 → post-dedup:
  unique_count=2 → passing 2 entries to _build_retrieval_log_from_search`.
- `report_reward trial_id=N: reporting reward for 2 memories …
  memory_ids_involved=['f9be400e…','5893c2f7…'] … memory_ids_state:
  'has_ids'`.

i.e. the Mem0 id-gap (§4b) is closed kernel-side (the provider's
`retrieve_memory` now emits `memory_id`), so pipeline.py:428 reads a real
id and `injected_memory_ids` populates. The audit request params (§2) were
correct all along.

(Note: `shared_memory_count` still pins at 2 per interaction — that is the
separate no-within-session-accumulation finding from the mechanism pilot
(Mem0 dedupes same-user writes), unrelated to id construction. It affects
*how many* ids appear, not *whether* ids are read.)

## 6. Definitive statement of the mismatch mechanism

- **For `memory_ids_involved` specifically (the reward-loop path):** the
  historical empty was a **response/contract gap**, not a
  request-construction bug — the audit request (pipeline.py:304-312) sends
  the correct session `user_id` + `sharing_policy="shared"` + writer
  `agent_name`; the failure was that retained entries had **no
  `memory_id`/`id` field** for `_build_retrieval_log_from_search` to read
  (pipeline.py:428), so `injected_memory_ids` (→ `memory_ids_involved`)
  came out empty (guarded/announced at pipeline.py:449-459). With the
  kernel-side id now present, this path yields real ids (§5).

- **The "0 results for a user with confirmed writes" LOG the prior pilot
  cited** is a **separate request-construction bug** in the unrelated
  diagnostic call at **pipeline.py:121-123** (`search_memories` invoked
  **without `user_id=`**, so the kernel scopes to `agent_name`'s fallback
  collection instead of the session `user_id`). It is diagnostic logging
  only and never feeds `report_reward`.

Neither the audit request nor the reward send routes under a wrong id; the
reward-loop emptiness was upstream-payload-shaped (missing id field), and
the scary log line was a mis-scoped diagnostic probe. No fix proposed here
(diagnostic only) — hand off to Subtask 2 alongside the AIOS-side trace.

## 7. Files / functions cited (no edits)

- `benchmarks/shared_memory/pipeline.py` — `AgentPipeline.run_trial`
  (:81, branch :167-184), diagnostic `search_memories` (:121-123, warn
  :136-140), `_audit_shared_memories` (:270, params :304-312),
  `_build_retrieval_log_from_search` (:385, filter/id read :415-440,
  id-gap warn :449-459), constants `RELEVANCE_THRESHOLD`/`AUDIT_TOP_K`/
  `WRITER_AGENTS` (:263-269), `_retrieval_log_from_diagnostics` (:243-262).
- `benchmarks/shared_memory/run_evaluation.py` — `memory_ids_involved`
  construction (:523-526), `report_reward` POST (:566-576).
- `cerebrum/memory/apis.py` — `search_memories` signature + `user_id`
  scoping contract.
- `cerebrum/utils/communication.py` — `send_request` (posts `agent_name`
  + `query_data` to `/query`).
