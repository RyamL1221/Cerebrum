# Pilot — `kernel_shared_tuned` loud-failure traces (no trials run)

**Subtask 8 pilot artifact.** Companion to `kernel_shared_tuned_pilot.md` (the success
pilot). Demonstrates that when the requested `kernel_shared*` condition does **not** match the
server's actual gating state — or the endpoint fails — the harness fails **loudly and
immediately**, before any trial, and writes **no** output artifact.

## Server: SIMULATED (same as subtask 7)

Same approach as the success pilot: no live AIOS kernel is reachable, so these traces run the
**real CLI** (`benchmarks/shared_memory/run_evaluation.py` → `EvaluationOrchestrator`) over
**real HTTP transport** against the reused stub `docs/pilots/gating_stub_server.py`,
reconfigured per scenario. No harness internals were called directly.

All three scenarios use the same invocation, varying only the server state:

```bash
CEREBRUM_KERNEL_URL=http://127.0.0.1:8000 \
  python3 benchmarks/shared_memory/run_evaluation.py \
    --method kernel_shared_tuned --trials 3 \
    --output <out>/ --kernel-url http://127.0.0.1:8000
```

`kernel_shared_tuned` requires `static_thresholds_enabled=True` and
`adaptive_policy_enabled=False`.

---

## Scenario 1 — mismatch (server reports the wrong state)

Stub configured with `STUB_STATIC_ENABLED=false` → reports
`static_thresholds_enabled: false`, violating what `kernel_shared_tuned` requires.

```
[INFO] __main__: Running method 'kernel_shared_tuned'.
Traceback (most recent call last):
  ...
  File ".../run_evaluation.py", line 767, in _run_method
    self._verify_gating_status(method_name)
  File ".../run_evaluation.py", line 722, in _verify_gating_status
    raise RuntimeError(
RuntimeError: Pre-flight gating check failed for method 'kernel_shared_tuned': kernel
gating state does not match the tier's requirement. Mismatches: static_thresholds_enabled:
expected True, server reported False. Full server response: adaptive_policy_enabled=False,
static_thresholds_enabled=False, static_thresholds_config={}. No trials will run.
EXIT_CODE=1
```

- Pre-flight fired; **mismatch detected with expected-vs-actual stated explicitly**
  ("expected True, server reported False") plus the full raw server response.
- **No trial progress bar, no trial output.**
- Filesystem: output dir **empty before and after** — no `results_*.json` written.

---

## Scenario 2 — endpoint failure: HTTP 400 "Memory manager not initialized"

Stub configured with `STUB_UNINITIALIZED=true` → `GET /memory/gating_status` returns HTTP 400
(the documented uninitialized-kernel path, mirrored from `AIOS/runtime/launch.py`).

```
RuntimeError: Pre-flight gating check failed for method 'kernel_shared_tuned':
http://127.0.0.1:8000/memory/gating_status returned HTTP 400 (expected 200).
Body: {"detail": "Memory manager not initialized"}. No trials will run.
```

- The harness **raises rather than silently skipping** verification and proceeding —
  satisfying the "don't silently skip and proceed" requirement.
- Filesystem: output dir empty before and after — no `results_*.json`.

---

## Scenario 3 — endpoint failure: server unreachable

Stub stopped entirely (port 8000 free), then the same CLI invocation.

```
RuntimeError: Pre-flight gating check failed for method 'kernel_shared_tuned': could not
reach http://127.0.0.1:8000/memory/gating_status (ConnectionError: HTTPConnectionPool(
host='127.0.0.1', port=8000): ... Connection refused). No trials will run.
EXIT_CODE=1
```

- Connection failure is **fatal, not caught-and-continued.**
- Filesystem: output dir contained only the captured console log; **no `results_*.json`**.

---

## Filesystem confirmation (all scenarios)

Each scenario `ls`'d its `--output` dir immediately before and after the run. In every case the
directory held **zero `results_*.json` files** afterward — the run aborted at the pre-flight,
before `ResultsWriter.write_json` is ever reached (that call lives at the end of `_run_method`,
well after the trial loop the run never entered).

## Acceptance criteria — met

- [x] Console shows the pre-flight detecting the mismatch and raising with expected-vs-actual
      values stated explicitly (Scenario 1).
- [x] A second/third trace shows the endpoint-failure paths (HTTP 400 and unreachable) also
      raising rather than silently proceeding (Scenarios 2 and 3).
- [x] Filesystem check confirms zero trials ran and no output artifact was written in every
      failure scenario.

## Files

- Stub server (reused): `docs/pilots/gating_stub_server.py`
- Success companion: `docs/pilots/kernel_shared_tuned_pilot.md`
- Design context: `docs/harness-aios-gating-dependency-scope.md`

Transient per-scenario `--output` directories were not persisted (they were empty of results by
design); the evidence is the console traces captured above. The stub server was stopped cleanly
after the run.
