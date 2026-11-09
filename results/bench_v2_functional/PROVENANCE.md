# bench_v2_functional: provenance

The benchmark v2 functional check (NeurIPS Subtask 14). Design and pass
conditions: AIOS `docs/BENCHMARK_V2.md`, "Functional check and smoke",
with Amendment 1 (a 500-token budget). Result: AIOS `docs/DEV_STATUS.md`,
Subtask 14.

- **Code**: every results file records Cerebrum
  `d23dc6aec84181f4301c6904d72dc08d13d74b6e` and AIOS
  `828fde0e74e0f191a0bc29c37fc8d432bb5c4cea`, neither `-dirty`. Library
  `PIPELINE_VERSION` `521a05c92298c454` (kernel and replicated cells).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`, seed
  20261108, SHA-256
  `768a37ac790479f7a2b1d58ea32932833617cece297da760fae802da9034ad98`),
  users 0 to 4. 21 cells: the six locus × backend cells at H = 0, H = 2
  and `no_delete`, plus `no_memory` (kernel in-house) and
  `no_visibility` (native, both backends). 105 user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. No judge (the integration probe is
  unscored). Mem0 extraction: Azure gpt-4o, temperature 0.0, seed
  20261105. Embedding: `nomic-embed-text` (Ollama).
- **Settings** (pre-flight checked, recorded as `run_settings`): k 10,
  budget 500 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms; kernel `auto_inject` and `auto_extract` on
  in the kernel phases, off in the agent phase.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=functional`,
  started 2026-11-08 18:22, finished 20:37 (EST). Run ids
  `f14b-<model>-<phase>-<method>-<condition>`.
- **Kernels**: one fresh kernel per phase:
  `kernel_qwen_kmem0_20261108T182259.log`,
  `kernel_qwen_kinh_20261108T184611.log` and
  `kernel_qwen_agent_20261108T190545.log`. The driver's end-of-phase
  check found 0 memory operations in the agent-phase log.

## Earlier attempt

- The first attempt (run prefix `f14`, 18:05) stopped INCOMPLETE in
  `qwen/kmem0/h2_kernel_shared`: users 0 and 1 failed the extraction
  guard (`backend_extraction_failed`). Their V5 writers replaced a base
  row with the event's fact-less stub, from which Mem0 extracted
  nothing.
- Fixed in Cerebrum `7d759ec`: base events carry their fields, and V5
  writes them as JSON, as in v1. The whole check was then re-run under
  run prefix `f14b`, from the first cell.
- The attempt's results, logs and driver log are in
  `repo-artifacts/Cerebrum/bench_v2_functional/failed_attempts/f14/`.

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py` output (the
  per-probe pass matrix, cap and budget, the check's criteria, kernel
  against replicated).
- Two changes to the analysis came after the run, with their tests.
  - The cap criterion first treated each condition as a separate cell,
    so it also checked the `no_memory` control, whose store is empty by
    design. The spec's cells are locus × backend, read over H = 0 and
    H = 2. The criterion now follows the spec.
  - The matrix gained the `contaminated` and `named_as_past` counts.
  - No probe score changed.
- The per-trial results files, run logs, kernel logs and the driver log
  are in `repo-artifacts/Cerebrum/bench_v2_functional/`. They are not
  committed.
