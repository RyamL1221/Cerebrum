# Pilot — `kernel_shared_tuned` successful gating match

**Subtask 7 pilot artifact.** Demonstrates the full user-facing path for a
`kernel_shared_tuned` run: CLI invocation → pre-flight `GET /memory/gating_status`
passes → trials execute → output artifact carries the real captured gating state.

## Server: SIMULATED (stated plainly)

**No live AIOS kernel was reachable in this environment.** A real connection to the
configured kernel URL (`http://localhost:8000`) was attempted first and refused on every
endpoint:

```
configured kernel url: http://localhost:8000
  GET /memory/gating_status -> UNREACHABLE (ConnectionError: ... port 8000 ... refused)
  GET /core/llms/list       -> UNREACHABLE (ConnectionError: ... refused)
  GET /                     -> UNREACHABLE (ConnectionError: ... refused)
```

Rather than mock `requests.get` in-process, this pilot runs against a **clearly-labeled
simulated AIOS server**: a minimal stdlib `http.server` stub
(`docs/pilots/gating_stub_server.py`) exercised over **real HTTP transport** through the
**real CLI** (`benchmarks/shared_memory/run_evaluation.py` → `EvaluationOrchestrator`). No
harness internals were called directly.

The stub's `GET /memory/gating_status` mirrors the real AIOS handler exactly
(`AIOS/runtime/launch.py:915` — same three fields, same 400 "Memory manager not initialized"
path). Its `/query` is a minimal JSON-LLM that answers whichever `response_format` json_schema
the caller sends, so the synthetic-data generator and judge complete and trials genuinely run.
It was configured to report the `kernel_shared_tuned`-matching state:
`static_thresholds_enabled=true`, `adaptive_policy_enabled=false`.

> The `[simulated assistant]` response text and the constant judge scores are artifacts of the
> stub, not of the harness. The gating pre-flight, provenance capture, trial loop, and output
> serialization exercised here are the real code paths.

## CLI command

```bash
# Terminal A — start the simulated AIOS server (kernel_shared_tuned state):
STUB_STATIC_ENABLED=true STUB_ADAPTIVE_ENABLED=false \
  STUB_STATIC_CONFIG_JSON='{"relevance_threshold":0.3,"max_injected_memories":10,"max_memory_tokens":2000}' \
  python3 -u docs/pilots/gating_stub_server.py --port 8000

# Terminal B — real CLI, real HTTP to the stub:
CEREBRUM_KERNEL_URL=http://127.0.0.1:8000 \
  python3 benchmarks/shared_memory/run_evaluation.py \
    --method kernel_shared_tuned --trials 3 \
    --output docs/pilots/run_kernel_shared_tuned/ \
    --kernel-url http://127.0.0.1:8000
```

Stub confirmed serving the matching state before the run:

```
gating HTTP 200 {"adaptive_policy_enabled": false, "static_thresholds_enabled": true,
                 "static_thresholds_config": {"relevance_threshold": 0.3,
                 "max_injected_memories": 10, "max_memory_tokens": 2000}}
```

## Console output — pre-flight passes, then trials run

```
[INFO] __main__: Running method 'kernel_shared_tuned'.
[INFO] __main__: Pre-flight gating check passed for 'kernel_shared_tuned':
                 adaptive_policy_enabled=False, static_thresholds_enabled=True.
Method: kernel_shared_tuned: 100%|██████████| 3/3 [00:00<00:00, 35.71it/s]
[INFO] __main__: Results written to docs/pilots/run_kernel_shared_tuned/results_kernel_shared_tuned.json

=== Personalization Method Comparison ===
Method                  Profile       Task Integration    Latency   Total  Failed
kernel_shared_tuned       2.000      2.000      2.000      0.002       3       0
```

- The pre-flight log line fires **once**, before the trial loop, and **passes** (the reported
  state matches the tier's requirement).
- **Total=3, Failed=0** — trial count matches `--trials 3`; all trials executed and were judged.
- (Memory-audit "Observability gap" warnings appear because the stub has no real Mem0 store, so
  cross-agent injection finds nothing. That is orthogonal to the gating pre-flight and expected
  for a stub.)

## Output artifact — `gating_status_by_method` carries the real reported values

From `docs/pilots/run_kernel_shared_tuned/results_kernel_shared_tuned.json`
(`experiment_metadata`):

```json
{
  "trials_per_condition": 3,
  "kernel_url": "http://127.0.0.1:8000",
  "conditions_run": ["kernel_shared_tuned"],
  "methods_run": ["kernel_shared_tuned"],
  "gating_status_by_method": {
    "kernel_shared_tuned": {
      "adaptive_policy_enabled": false,
      "static_thresholds_enabled": true,
      "static_thresholds_config": {
        "relevance_threshold": 0.3,
        "max_injected_memories": 10,
        "max_memory_tokens": 2000
      }
    }
  }
}
```

The recorded `gating_status_by_method.kernel_shared_tuned` is **byte-for-byte what the
(simulated) server reported** — not a hardcoded expectation. A sample trial confirms real
execution: `method=kernel_shared_tuned`, `integration_score=2`,
`token_usage={prompt_tokens: 42, completion_tokens: 21, total_tokens: 63}`.

## Acceptance criteria — met

- [x] Real-vs-simulated stated plainly: **simulated** AIOS server, over real HTTP.
- [x] Evidence from an actual CLI invocation through `EvaluationOrchestrator` (not an in-process
      unit test).
- [x] Console output shows the pre-flight passing before any trial.
- [x] Final artifact shows `gating_status_by_method` populated with the values the server
      reported; trial count matches `--trials` with zero failures.

## Reproducing / files

- Stub server: `docs/pilots/gating_stub_server.py`
- Output artifact: `docs/pilots/run_kernel_shared_tuned/results_kernel_shared_tuned.json`
- Design context: `docs/harness-aios-gating-dependency-scope.md`

A mismatch/failure pilot (pre-flight raises, zero trials) is subtask 8.
