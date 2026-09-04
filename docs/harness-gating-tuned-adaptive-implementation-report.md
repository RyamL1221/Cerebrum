# Implementation Report — `kernel_shared_tuned` / `kernel_shared_adaptive` gating tiers + pre-flight verification

Single deliverable for the feature that adds two new benchmark conditions
(`kernel_shared_tuned`, `kernel_shared_adaptive`), a pre-flight
`GET /memory/gating_status` verification for the `kernel_shared*` family, and
provenance recording of the captured gating state. Covers investigation
findings, exact changes, pilot evidence, the regression sweep, and an explicit
walk-through of every master-prompt acceptance-criteria bullet.

---

## 1. Investigation findings (subtasks 1–3)

Full detail in `docs/harness-aios-gating-dependency-scope.md`. Summary:

- **Scope (subtask 1).** Only the `kernel_shared*` family depends on the kernel's memory-gating
  state. `naive_concat` (plain concat) and `vanilla_rag` (local TF-IDF) touch no kernel memory
  path. `mem0_default` shares the kernel-backed transport with `kernel_shared` but is **not** a
  gating-controlled condition, so it does not get a pre-flight (resolved explicitly, not folded
  in silently). The `GET /memory/gating_status` contract is server-side in AIOS and trusted as
  given; it is a *different mechanism* from the pre-existing `auto_inject`/`auto_extract`
  toggles (a conflation that was caught and corrected in the running doc).

- **Insertion points (subtask 2), re-confirmed against the live repo:**
  - `_ALL_METHODS` lives in `run_evaluation.py` (NOT `pipeline.py` — prior-assumption drift).
  - `--method` / `--condition` `choices` are both in `run_evaluation.py`'s `build_arg_parser()`;
    no second reporting CLI duplicates them (method names are hard-coded in a few tests).
  - Dispatcher is an **if/elif chain** in `MethodPipeline.run_trial()` (`pipeline.py`).
  - `TrialResult` already carried `token_usage` + `policy_action`, and `ExperimentMetadata`
    already carried `methods_run` — flagged as collision risks so subtask 6 wouldn't re-add them.

- **Pre-flight home + field provenance (subtask 3).** `EvaluationOrchestrator` exists
  (`run_evaluation.py`), and the correct pre-flight home is the per-method loop head in
  `_run_method()`. Confirmed `policy_action` is written **only post-hoc** by
  `join_policy_actions.py` (outcome-side), while gating provenance is **decision-side/pre-flight**
  — so they must be distinct fields. The existing `report_reward` `requests.post(.../memory/...)`
  pattern was identified as the model to mirror.

---

## 2. What changed — file + line references (subtasks 4–6)

Four files (three production, one test). All model additions are additive `Optional[...] = None`
or default-valued, backward-compatible with existing serialized results.

### `benchmarks/shared_memory/run_evaluation.py`
- **`_ALL_METHODS`** expanded from 4 → 6 to include `kernel_shared_tuned`, `kernel_shared_adaptive`.
- **`--method` `choices`** expanded to include both new tiers (kept `all`); `--condition`
  left untouched.
- **`_GATING_VERIFIED_METHODS`** and **`_GATING_EXPECTATIONS`** module constants added
  (the per-tier expected state table).
- **`EvaluationOrchestrator._verify_gating_status(method_name)`** added — issues
  `requests.get(f"{config.get_kernel_url().rstrip('/')}/memory/gating_status", timeout=30)`,
  raises `RuntimeError` on transport failure / non-200 / non-JSON / expected-vs-actual mismatch
  (no retry, no auto-correct), caches the parsed response on `self._gating_status_by_method`.
- **`_run_method()`**: guard `if method_name in _GATING_VERIFIED_METHODS: self._verify_gating_status(method_name)`
  at the per-method loop head (before the trial loop); and the `ExperimentMetadata(...)`
  construction now passes `gating_status_by_method` (built from the cache, `None` when empty).

### `benchmarks/shared_memory/pipeline.py`
- **`MethodPipeline.run_trial()` dispatcher**: added
  `elif self.method in ("kernel_shared_tuned", "kernel_shared_adaptive"): return self._run_kernel_shared(...)`;
  updated the `ValueError` message and the class docstring.
- **`_run_kernel_shared()`**: `result.method = self.method` (was a hardcoded `"kernel_shared"`)
  so the shared helper correctly labels whichever tier invoked it. Delegation confirmed safe:
  `AgentPipeline` takes only `share_memory`/`assistant_llms` — no per-tier client parameter; tiers
  differ solely in server-side config. `method_user_id = f"{user_id}__{method}"` gives each tier
  an isolated memory namespace for free.

### `benchmarks/shared_memory/models.py`
- **`ExperimentMetadata.gating_status_by_method: Optional[Dict[str, Dict]] = None`** — raw-dict
  passthrough (mirrors `token_usage`'s treatment of kernel-owned shapes, not a typed sub-model),
  documented as decision-side/pre-flight provenance explicitly distinct from `policy_action`.

### `tests/agents/test_unified_trial_data_props.py`
- Fixed the pre-existing `assistant_llms` `tracking_init` signature bug (the test was already
  broken on a clean checkout); re-derived the `--method all` method enumeration from `_ALL_METHODS`
  so it can't drift; stubbed `_verify_gating_status` in the four `--method all` plumbing tests
  (they validate trial-data plumbing, not gating).

`test_results_writer.py` was left unchanged (its 4-method fixture is orthogonal to the condition
list — verified, not assumed).

---

## 3. Pilot traces (subtasks 7–8)

Both pilots ran the **real CLI** through `EvaluationOrchestrator` over **real HTTP transport**
against a clearly-labeled **simulated AIOS server** (`docs/pilots/gating_stub_server.py`) — no
live kernel was reachable (stated plainly; a real connection to `localhost:8000` was attempted
first and refused). The stub's `/memory/gating_status` mirrors the real AIOS handler
(`AIOS/runtime/launch.py:915`) exactly.

- **Success — `docs/pilots/kernel_shared_tuned_pilot.md`**: stub set to
  `static_thresholds_enabled=true, adaptive_policy_enabled=false`;
  `--method kernel_shared_tuned --trials 3` → pre-flight **passed** (logged once, before trials),
  **3 trials ran, 0 failed**, and the output artifact's
  `experiment_metadata.gating_status_by_method.kernel_shared_tuned` holds the **exact values the
  server reported** (including the real `static_thresholds_config`).
- **Failure — `docs/pilots/kernel_shared_tuned_failure_pilot.md`**: three loud-failure traces —
  (1) mismatch (`RuntimeError` with "expected True, server reported False" + full response),
  (2) HTTP 400 "Memory manager not initialized", (3) server unreachable. Each aborts at the
  pre-flight with **zero trials** and **no `results_*.json`** written (confirmed by before/after
  `ls`).

---

## 4. Regression sweep (this subtask — fresh, single pass)

A directory scan (`grep -rl` for `MethodPipeline|_ALL_METHODS|build_arg_parser|_verify_gating_status|gating_status|EvaluationOrchestrator|run_single_trial`)
was run first rather than trusting subtasks 1–8's list; it surfaced additional candidates
(`test_method_cli`, `test_kernel_shared_preservation`, the per-method props/unit tests). Full
result:

| Test file | Result |
|-----------|--------|
| test_unified_trial_data_props | PASS |
| test_results_writer | PASS |
| test_results_props | PASS |
| test_config_loader | PASS |
| test_summary_output | PASS |
| test_benchmark_harness_preservation | PASS |
| test_method_cli | PASS |
| test_vanilla_rag_props | PASS |
| test_vanilla_rag_unit | PASS |
| test_naive_concat_props | PASS |
| test_naive_concat_unit | PASS |
| test_mem0_default_props | PASS |
| test_benchmark_metrics | PASS |
| test_kernel_log_parser | PASS |
| **test_benchmark_orchestrator** | **FAIL (pre-existing, out of scope)** |
| **test_kernel_shared_preservation** | **FAIL (pre-existing, out of scope)** |
| **test_mem0_default_unit** | **FAIL (pre-existing, out of scope)** |

### The three failures — all confirmed pre-existing

Verified by checking out the pre-subtask-4 baseline commit (`5e0ed3a`) into a temporary
`git worktree` and running each there. **All three fail identically on the baseline**, with the
same error signatures, so this feature neither caused nor worsened any of them:

- **`test_benchmark_orchestrator`** — `TypeError: tracking_init() got an unexpected keyword
  argument 'assistant_llms'`. Pre-existing test-stub signature bug (a `--condition` legacy test);
  its `tracking_init` predates the orchestrator passing `assistant_llms`. Already flagged and
  correctly deferred in subtask 4.
- **`test_kernel_shared_preservation`** — identical `assistant_llms` `tracking_init` bug, same
  root cause, different file.
- **`test_mem0_default_unit`** — `AssertionError: memory.add was never called` (a Mem0
  mock/live-kernel expectation), driven by a refused connection to `localhost:8000`. Orthogonal
  to this feature — the `mem0_default` path was never modified.

### Scope decision on the three failures

**Out of scope; documented, not fixed** (and not silently omitted). Rationale: none is caused by
this feature; the master prompt's acceptance criteria don't cover them; all three are variants of
pre-existing test-harness issues (two are the same `assistant_llms` stub bug, one is a
Mem0/kernel expectation). Fixing them would expand scope beyond the gating feature. They are a
known-pre-existing debt worth a separate cleanup — the `assistant_llms` `tracking_init` bug in
particular recurs across at least three test files and is a good single-purpose follow-up.
(`test_unified_trial_data_props.py` was fixed here only because this feature's `_ALL_METHODS`
change made it additionally stale — fixing its stub was necessary to validate this feature.)

### Non-goals re-confirmed
- **AIOS untouched:** `git status` in the sibling `AIOS/` repo is clean — only read (subtask 7).
- **argparse safety net intact:** `--method kernel_shared_tuned` / `kernel_shared_adaptive`
  accepted; `--method invalid_name` still exits `SystemExit(code=2)`.

---

## 5. Acceptance-criteria checklist (master prompt)

Walking every acceptance-criteria bullet across the feature's subtasks:

**Subtask 4 (add tiers):**
- [x] `--method kernel_shared_tuned` / `kernel_shared_adaptive` accepted by argparse (no exit 2) — verified.
- [x] Route through the dispatcher to a confirmed-correct implementation — both delegate to `_run_kernel_shared`; delegation-safety confirmed (only server-side config differs).
- [x] Invalid method still fails argparse (safety net unweakened) — `invalid_name` → exit 2.
- [x] "Delegation is safe" confirmed explicitly (not assumed) — reported in subtask 4 + §2 here.
- [x] No pre-flight logic in subtask 4 — added only in subtask 5.

**Subtask 5 (pre-flight):**
- [x] Fires exactly once per `kernel_shared*` method, before any trial — verified via CLI path.
- [x] Does not fire for `naive_concat`/`vanilla_rag`/`mem0_default` — verified (GET count 0).
- [x] Correct 200 matching expectations → run proceeds silently — success pilot.
- [x] Mismatch / failure raises before the trial loop, zero trials — failure pilot (all 3 modes).
- [x] Raw parsed response stored for subtask 6, not wired into models yet — cached on `self._gating_status_by_method`.

**Subtask 6 (provenance):**
- [x] New field additive; existing fields/semantics unchanged — `Optional[...] = None`, regression green.
- [x] `kernel_shared*` run's metadata contains the real captured `gating_status` — success pilot artifact.
- [x] Non-gating run's metadata has the field as `None` — verified (falls out of the cache-only-verified design).
- [x] Field documented as distinct from `policy_action` — model docstring + design doc.

**Subtask 7 (success pilot):**
- [x] Clear statement of real-vs-simulated — **simulated**, over real HTTP.
- [x] Evidence from an actual CLI invocation through `EvaluationOrchestrator` — yes.
- [x] Console shows pre-flight passing — captured.
- [x] Final artifact shows `gating_status_by_method` with server-reported values — captured.

**Subtask 8 (failure pilot):**
- [x] Console shows pre-flight detecting the mismatch, raising with expected-vs-actual stated — Scenario 1.
- [x] Endpoint-failure path (400 / unreachable) also raises, not silently proceeding — Scenarios 2 & 3.
- [x] Filesystem confirms zero trials + no output artifact in every failure scenario — before/after `ls`.

**Subtask 9 (this report):**
- [x] Fresh regression sweep reported (pass/fail per file) — §4 table.
- [x] `test_benchmark_orchestrator` status explicitly resolved (pre-existing, out of scope) — §4.
- [x] AIOS-untouched + argparse-safety-net re-confirmed — §4.
- [x] Final report covering every acceptance-criteria bullet — this document.

**Non-goals held:**
- [x] No AIOS repo files modified.
- [x] No retry / auto-correction in the pre-flight.
- [x] argparse safety net not weakened.
- [x] `mem0_default` correctly excluded from gating verification.

---

## 6. Commit traceability

Feature branch: `feature/self-improving-memory`. Nine commits (subtask 1's scope doc `d72544a`
predates the eight below on the branch):

| Hash | Subtask | Message |
|------|---------|---------|
| d72544a | 1 | docs(harness): document AIOS gating dependency scope per condition |
| a486b96 | 1–2 | docs(harness): distinguish gating_status contract from auto_inject; resolve mem0_default scope |
| fea1340 | 2 | docs(harness): re-confirm insertion points for tuned/adaptive conditions |
| 5e0ed3a | 3 | docs(harness): confirm EvaluationOrchestrator._run_method as gating pre-flight home |
| 984025c | 4 | feat(harness): add kernel_shared_tuned and kernel_shared_adaptive as dispatched conditions |
| 2b5d63d | 5 | feat(harness): add pre-flight gating_status verification for kernel_shared* conditions |
| f2a7267 | 6 | feat(harness): record gating_status as provenance on ExperimentMetadata |
| 625c870 | 7 | docs(harness): capture kernel_shared_tuned pilot — successful gating match |
| 35b77c8 | 8 | docs(harness): capture kernel_shared_tuned pilot — deliberate mismatch and endpoint-failure traces |

(This report's commit is added on top by subtask 9.)

## 7. Known pre-existing debt (out of scope, for a future cleanup)
- The `assistant_llms` `tracking_init` stub bug recurs in `test_benchmark_orchestrator.py` and
  `test_kernel_shared_preservation.py` (and was in `test_unified_trial_data_props.py` until fixed
  here). A single follow-up could repair all remaining occurrences.
- `test_mem0_default_unit.py::test_add_called_before_search` asserts `memory.add` was called but
  fails without a reachable kernel/Mem0 mock.
