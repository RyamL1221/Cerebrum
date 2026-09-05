# Config Reload/Restart Mechanics for `memory.static_thresholds`

**Track:** threshold-search (offline static-threshold search harness)
**Question:** Between two candidate `memory.static_thresholds` configs, can a
live-reload endpoint (`POST /core/refresh`, `POST /core/config/update`) apply the
change to the running AIOS kernel, or is a full server-process restart genuinely
required?

**Answer (evidence-backed, not assumed):**
`POST /core/refresh` does **NOT** pick up `memory.static_thresholds` changes. A
full AIOS server **process restart is required**. `POST /core/config/update` is
not a separate working path — it is an API-key updater that internally calls the
same broken refresh routine.

This confirms the prior pilot's suspicion that `/core/refresh` was
insufficient/untested for this specific config key. The threshold-search harness
must restart the kernel between candidate configs.

> Scope note: This is an **investigation** with captured evidence. No AIOS source
> was modified — not the gating mechanism, not the config schema, not the
> `/memory/gating_status` endpoint, and not the `restart_kernel()` reload path.
> The only file edited during the experiment was `aios/config/config.yaml`
> (the value under test), which was restored to its baseline afterward.

---

## Test setup

- **Repo:** `AIOS` (`runtime/launch.py`, `aios/memory/manager.py`,
  `aios/memory/static_thresholds.py`, `aios/config/config_manager.py`,
  `aios/config/config.yaml`).
- **Provider:** `mem0` (config default). Ollama up at `localhost:11434`.
- **Server start:** `.venv/bin/python -m runtime.launch` (equivalent to
  `runtime/launch_kernel.sh`, which is `python -m runtime.launch`).
- **Observable:** `GET /memory/gating_status`, whose
  `static_thresholds_config` field reads directly off the live
  `MemoryManager` instance (`active_components["memory"]._static_thresholds_config`).
- **Variable under test:** `memory.static_thresholds.novelty_threshold.default`,
  toggled `0.7 → 0.6`. `static_thresholds.enabled` was set `true` so the block is
  observable (baseline in the repo is `false`).

The two sibling thresholds (`similarity_threshold`, `redundancy_threshold`) were
left at `0.7` as controls — a correct reload must show `novelty=0.6` while these
stay `0.7`.

---

## Captured request/response payloads (literal)

### 1. BEFORE — baseline, `novelty=0.7` on disk and in memory

Request:
```
GET http://localhost:8000/memory/gating_status
```
Response:
```json
{"adaptive_policy_enabled":true,"static_thresholds_enabled":true,"static_thresholds_config":{"enabled":true,"novelty_threshold":{"default":0.7,"overrides":[]},"similarity_threshold":{"default":0.7,"overrides":[]},"redundancy_threshold":{"default":0.7,"overrides":[]}}}
```
(`adaptive_policy_enabled:true` is incidental — the repo config also has the
adaptive policy on. It does not affect this test, which only watches
`static_thresholds_config`.)

### 2. Edit `config.yaml` on disk: `novelty_threshold.default: 0.7 → 0.6`

Then re-query WITHOUT any reload, to prove the running process is unaffected by a
bare disk edit:

Request:
```
GET http://localhost:8000/memory/gating_status
```
Response (still `0.7` — in-memory unchanged, as expected):
```json
{"adaptive_policy_enabled":true,"static_thresholds_enabled":true,"static_thresholds_config":{"enabled":true,"novelty_threshold":{"default":0.7,"overrides":[]},"similarity_threshold":{"default":0.7,"overrides":[]},"redundancy_threshold":{"default":0.7,"overrides":[]}}}
```

### 3. RELOAD-ONLY path — `POST /core/refresh`

Request:
```
POST http://localhost:8000/core/refresh
```
Response:
```json
{"status":"success","message":"Configuration refreshed and components reinitialized"}
```
The endpoint reports success. Then re-query gating status:

Request:
```
GET http://localhost:8000/memory/gating_status
```
Response (**STILL `0.7`** — the change was NOT applied):
```json
{"adaptive_policy_enabled":true,"static_thresholds_enabled":true,"static_thresholds_config":{"enabled":true,"novelty_threshold":{"default":0.7,"overrides":[]},"similarity_threshold":{"default":0.7,"overrides":[]},"redundancy_threshold":{"default":0.7,"overrides":[]}}}
```
Disk at this point (confirmed): `default: 0.6  # CHANGED for reload test (was 0.7)`.
So despite a `"success"` response, `/core/refresh` left the live
`static_thresholds_config` at the stale `0.7`.

### 4. FULL-RESTART path — stop the process, start a fresh one

Disk config still holds `novelty=0.6`. Stop the running kernel process, start a
new `python -m runtime.launch`, wait for `/status` to report ok, then:

Request:
```
GET http://localhost:8000/memory/gating_status
```
Response (**now `0.6`** — restart DID apply the change; controls stayed `0.7`):
```json
{"adaptive_policy_enabled":true,"static_thresholds_enabled":true,"static_thresholds_config":{"enabled":true,"novelty_threshold":{"default":0.6,"overrides":[]},"similarity_threshold":{"default":0.7,"overrides":[]},"redundancy_threshold":{"default":0.7,"overrides":[]}}}
```

### Result table

| Step | Disk `novelty.default` | `/memory/gating_status` `novelty.default` |
|------|------------------------|-------------------------------------------|
| 1. Baseline | 0.7 | 0.7 |
| 2. Disk edit, no reload | 0.6 | 0.7 (unchanged, expected) |
| 3. After `POST /core/refresh` | 0.6 | **0.7 (not applied)** |
| 4. After full process restart | 0.6 | **0.6 (applied)** |

---

## Root cause (why `/core/refresh` silently fails to apply the change)

`POST /core/refresh` (`runtime/launch.py`) does:

```python
config.refresh()      # re-reads config.yaml fully from disk  ✅ works
restart_kernel()      # meant to rebuild all components        ✗ discards result
```

`config.refresh()` → `ConfigManager.load_config()` genuinely re-reads
`config.yaml` from disk, so the new `0.6` is available in `config.config`.

But `restart_kernel()` is:

```python
def restart_kernel():
    try:
        active_components = initialize_components()   # <-- no `global`
        if not active_components:
            raise Exception("Failed to initialize components")
        ...
```

There is **no `global active_components` declaration** in `restart_kernel()`.
Because the function assigns to `active_components`, Python treats it as a
*function-local* variable. `initialize_components()` does build a brand-new
`MemoryManager` (which would read the fresh `0.6` via
`config.get_memory_config()` → `MemoryManager.__init__` →
`self._static_thresholds_config`), but that freshly-built dict is bound to the
throwaway local and discarded when `restart_kernel()` returns. The **module-level**
`active_components` that every endpoint (including `/memory/gating_status`) reads
is never reassigned, so it keeps pointing at the original `MemoryManager` holding
the stale `0.7`.

Net effect: `/core/refresh` reloads the YAML into the `ConfigManager` singleton
but throws away the rebuilt components, so any component-construction-time config
(like `static_thresholds`, read only in `MemoryManager.__init__`) never takes
effect until the process is restarted and `_ensure_initialized()` runs at import.

### `POST /core/config/update` is not an alternative

`/core/config/update` requires `provider` + `api_key` fields (it is an API-key
setter), writes them to config, then calls `await refresh_configuration()` — i.e.
it funnels through the exact same `/core/refresh` → `restart_kernel()` path. It
provides no separate, working mechanism for `static_thresholds` and inherits the
same discard bug.

---

## Definitive statement

- **`POST /core/refresh` does NOT pick up `memory.static_thresholds` changes.**
  It returns `{"status":"success",...}` but leaves the live `MemoryManager`
  (and therefore `GET /memory/gating_status`) on the old thresholds.
- **`POST /core/config/update` does NOT either** — it is an API-key updater that
  internally calls the same broken refresh routine.
- **A full AIOS server process restart IS required** to apply a
  `memory.static_thresholds` change. After a restart, `GET /memory/gating_status`
  reflects the new value.

### Implication for the threshold-search harness

Between candidate `static_thresholds` configs, the harness must **fully restart
the AIOS process** (stop, start, wait for `/status` ok), not call `/core/refresh`.
The `/memory/gating_status` pre-flight already in the Cerebrum benchmark
(`EvaluationOrchestrator._verify_gating_status`) is the correct way to *confirm*
the restart took effect before running trials — but it cannot itself cause the
change to load.

### Aside (not acted on — out of scope)

The underlying cause is a missing `global active_components` in
`restart_kernel()`. Fixing that would make `/core/refresh` work for
construction-time config like `static_thresholds`. This report does not modify any
AIOS code; the fix (if pursued) belongs to a separate AIOS-side change with its
own review.
