# Kernel-boundary compliance review — `report_reward` feature

**Scope:** Full accumulated diff of `feature/self-improving-memory` vs base
`origin/main` (`e7898fa`), covering all 5 commits:

- `31cdc38` Subtask 1 — add `report_reward` operation type to `MemoryQuery`
- `b48219e` Subtask 2 — track injected memory IDs (kernel-side attempt)
- `e2d049e` Subtask 2 rework — revert kernel change; payload-only extraction
- `6113fe4` Subtask 3 — local logging for `report_reward`
- `b28f822` Subtask 4 — send `report_reward` after judging

**Verdict:** PASS. Zero (c) classifications. Cerebrum stays strictly in the
messenger role; no memory-management logic was introduced; the kernel/app
boundary is intact.

## Final gate re-verifications (checked against the actual diff, not intent)

1. **`aios/memory/context_injector.py` has ZERO net diff.**
   `git diff origin/main...HEAD -- aios/memory/context_injector.py` → empty.
   Furthermore `git diff --name-only origin/main...HEAD -- aios/` → empty:
   **no file under the kernel tree is touched at all.** The Subtask-2 near-miss
   (adding `injected_memory_ids` to the kernel `InjectionResult`) was fully
   reverted in `e2d049e`.

2. **Reward attribution is uniform / equal-credit, arithmetic only.**
   `reward_value = sum(reward_scores) / len(reward_scores)` — a plain mean of
   the three trial-level judge scores. There is no per-memory weighting, no
   conditional that treats one `memory_id` differently from another. The same
   scalar `reward_value` and the same `memory_ids_involved` list are passed
   verbatim to both the log and the send. This is the master prompt's
   "naive attribution (v1): equal credit."

3. **Failure handling only logs and continues.**
   The `try/except` around `send_request` (and the `response.get("error")`
   check) route solely to `log_report_reward_failure(...)`. No retry, no
   alternate/fallback memory IDs, no parameter mutation, no memory-management
   decision under failure. The trial result is already recorded before the send.

## File-by-file classification

Classification key: (a) plumbing/pass-through, (b) observational/read-only,
(c) inspects a value and branches/decides/filters/weights in a way that affects
what is stored, retrieved, or injected.

| File | Class | One-line justification (messenger-role compliance) |
|------|-------|-----------------------------------------------------|
| `cerebrum/memory/apis.py` | (a) | Adds `"report_reward"` to the `MemoryQuery.operation_type` Literal + docstring; no new fields, no logic. A new message type, not a new behavior. |
| `benchmarks/shared_memory/models.py` | (b) | Three additive optional data fields (`memory_id`, `injected_memory_ids`) defaulting to None/empty; pure data carriers, no logic. |
| `benchmarks/shared_memory/pipeline.py` | (b) | Reads `memory_id`/`id` from the existing kernel response payload into an observability list; a log-only warning for the Mem0 gap. Does not filter/reorder/drop which memories are retained or injected (existing control flow unchanged). |
| `benchmarks/shared_memory/reward_logging.py` | (b) | Local logging only. Its one branch picks a log level / reason string; never alters what is stored/retrieved/injected/sent. Both functions swallow exceptions. |
| `benchmarks/shared_memory/run_evaluation.py` | (a) | Computes the mean-of-scores reward, copies IDs, builds a `MemoryQuery`, sends via existing `send_request`. Pure pass-through; failure path logs and continues. |
| `docs/mem0-search-results-memory-id-gap.md` | (doc) | Documentation of the AIOS-side dependency; no code. |

No file classified (c). Nothing to flag for remediation.

## Cross-reference against the master prompt's non-goals

Each verified against the actual diff, not intent:

- **No threshold logic in Cerebrum.** Confirmed. Added lines contain no
  `threshold` comparison. The relevance-threshold `continue` in
  `pipeline._build_retrieval_log_from_search` is pre-existing context (not a
  `+` line) and unchanged. A grep of added lines for
  `threshold|weight|rank|sort|filter|cache|persist|state|learn` returns nothing.
- **No `ContextInjector` changes.** Confirmed — zero net diff on
  `context_injector.py`; no kernel-tree file touched.
- **No retrieval-request changes.** Confirmed. No `retrieve_memory` call sites,
  params, `k`, `user_id`, or `sharing_policy` were modified. The feature only
  reads IDs out of responses already returned and sends a separate
  `report_reward` message.
- **No client-side policy state / caching / learning.** Confirmed. No module
  holds reward/memory state between trials; nothing is cached or persisted; no
  model is updated. Each trial computes a scalar, logs it, sends it, and moves on.

## Notes carried forward (not violations)

- `memory_ids_involved` is empty under the Mem0 provider because the kernel's
  `retrieve_memory` payload omits per-entry IDs (`docs/mem0-search-results-memory-id-gap.md`).
  This is an AIOS-side dependency, correctly labeled in logs as `mem0_id_gap`.
- The kernel currently returns HTTP 500 for `report_reward` (operation not yet
  implemented kernel-side). This is handled as the non-fatal fire-and-forget
  failure path and is an AIOS-side item, not a Cerebrum boundary issue.
