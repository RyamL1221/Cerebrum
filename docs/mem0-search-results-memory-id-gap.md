# Cross-track dependency: Mem0 `retrieve_memory` omits per-entry memory ID

**Status:** BLOCKED — needs an AIOS-side (kernel/provider-layer) fix.
**Track ownership:** AIOS kernel. Do NOT patch from the Cerebrum SDK track.
**Blocks:** Cerebrum Subtask 2 (trial-ID → memory-IDs tracking) full population,
and therefore Subtask 4 (reward attribution), whenever the harness runs against
the Mem0 provider.

## Summary

The AIOS Mem0 provider's `retrieve_memory` path builds `search_results`
entries **without a memory identifier**. The Cerebrum benchmark harness needs
that ID to record which memories were actually injected per trial
(`RetrievalLog.injected_memory_ids`) for reward attribution. Because the ID is
absent from the payload Cerebrum receives, `injected_memory_ids` cannot be
populated when the configured provider is `mem0`.

This is structurally identical to the in-house provider fix (AIOS-side
"Subtask 7"), which already exposes the ID. Only the Mem0 provider is missing
it. The fix belongs on the AIOS side because it is provider-layer plumbing.

## Which field is missing, on which provider — confirmed via which check

- **Configured provider (harness runtime):** `mem0`
  - `AIOS/aios/config/config.yaml:89` → `provider: "mem0"`
- **Missing field:** a per-entry `memory_id` (or `id`) key in each
  `search_results` dict returned by `retrieve_memory`.
- **Provider file (read-only, not modified):**
  `AIOS/aios/memory/providers/mem0.py`

### Evidence

Mem0 `retrieve_memory` → `search_results` mapping (approx. lines 1182–1210)
emits only these keys per entry:

```
content, keywords, tags, category, timestamp, score, similarity, metadata
```

There is no `memory_id` / `id`. The raw Mem0 `item` DOES carry an `id` — proven
by two other code paths in the same file:

- `_resolve_memory_id` checks `("id", "memory_id")` (approx. line 681).
- `retrieve_memory_raw` extracts it:
  `id=(item.get("id") or metadata.get("memory_note_id"))` (approx. line 1348).

So the ID exists on the item and is simply not copied into the
`retrieve_memory` `search_results` dict.

### Contrast — in-house provider already includes it

`AIOS/aios/memory/providers/in_house.py` (approx. line 360) sets:

```python
search_results.append({
    'memory_id': memory.id,
    ...
})
```

## Proposed AIOS-side fix (one-line-scale, provider layer)

In `aios/memory/providers/mem0.py`, within the `retrieve_memory`
`search_results.append({...})` block, add the ID from the already-available
`item`:

```python
search_results.append({
    "memory_id": item.get("id"),   # <-- add, mirroring in-house provider
    "content": item.get("memory", ""),
    ...
})
```

(Field name `memory_id` to match the in-house provider and the harness reader.)

## Cerebrum-side status (this track)

- `benchmarks/shared_memory/models.py`: additive fields kept as-is
  (`RetrievalLogEntry.memory_id`, `InjectedMemoryEntry.memory_id`,
  `RetrievalLog.injected_memory_ids`). These are Cerebrum-side and harmless.
- `benchmarks/shared_memory/pipeline.py`: reads `memory_id`/`id` purely from the
  existing kernel response payload (`_extract_injection_diagnostics`,
  `_retrieval_log_from_diagnostics`, `_build_retrieval_log_from_search`). No
  dependency on kernel internals or the reverted `ContextInjector` change.
  When the payload lacks IDs (current Mem0 behavior), the reads degrade to
  empty and a runtime warning is logged pointing to this document.
- `aios/memory/context_injector.py`: reverted to its pre-Subtask-2 state
  (zero diff). No kernel file was modified from the Cerebrum track.

**Once the AIOS-side fix lands** (Mem0 `search_results` includes `memory_id`),
the Cerebrum harness will populate `injected_memory_ids` automatically with no
further Cerebrum change, because it already reads that field from the payload.
