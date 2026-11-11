# bench_v2_functional_a4: provenance

The benchmark v2 functional check under Amendment 4 (NeurIPS Subtask
15, step 1: complete deletion and supersession), on `users_v2`
revision 3. Design and pass conditions: AIOS `docs/BENCHMARK_V2.md`,
"Functional check and smoke", with Amendments 1 to 4, and AIOS
`docs/DELETION_AND_SUPERSESSION.md`. Result: AIOS `docs/DEV_STATUS.md`,
Subtask 15.

- **Code**: every results file records Cerebrum
  `059e5a54433c0043e5cd09bf5828252cc9e90bbf` and AIOS
  `945548e0748ce16df948a4482197b5d351406632`, neither `-dirty`. Library
  `PIPELINE_VERSION` `73b1b63748628e57` (kernel and replicated cells;
  native trials record none, and their `run_settings` record the
  kernel's).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`),
  users 0 to 4, with the same per-user `input_sha256` as
  `bench_v2_functional_a3`. 29 cells: the six locus × backend cells at
  H = 0, H = 2 and `no_delete`; `no_memory` (kernel in-house);
  `no_visibility` (native, both backends); and Amendment 4's
  `writer_scoped` and `no_supersession` (kernel and replicated, both
  backends; `no_supersession` in the driver's `_ns` phases). 145
  user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. No judge (the integration probe is
  unscored). Mem0's extraction ran in all 14 Mem0 cells
  (`backend_extraction` true): Azure gpt-4o, temperature 0.0, seed
  20261105, `mem0ai` 2.0.2 in both venvs, without its `[nlp]` extra
  (spaCy absent; AIOS `DEV_STATUS.md`, open decision 1). Embedding:
  `nomic-embed-text` (Ollama).
- **Settings** (pre-flight checked, recorded as `run_settings`): k 10,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms, `supersession` `exclude` (`off` in the
  `_ns` phases). Kernel `auto_inject` on and `auto_extract` off in the
  kernel phases, both off in the agent phases.
- **Store files**: the kernel keeps its tombstones in AIOS
  `.aios_state/tombstones.sqlite` and its Mem0 history in AIOS
  `.mem0/history.db`. Each replicated store keeps its own
  (`.replicated_memory/<prefix>/<backend>/tombstones.sqlite`, and
  `history.db` for Mem0), and native Mem0 keeps its history in its
  store directory (`.native_memory/<prefix>/native_mem0/`). The
  pre-flight records the kernel's two paths in every cell, the
  replicated and native ones included.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=functional`
  and `OUTROOT=results/bench_v2_functional_a4`, in two launches:
  - `RUN_PREFIX=f15b`, started 2026-11-10 16:03 EST: the 9 kernel
    cells (Mem0 16:04 to 16:37, in-house 16:37 to 17:04). The first
    agent cell (`replicated_mem0` H = 0, started 17:04) was stopped:
    its harness was sent SIGTERM at 17:11 because the Mac was about
    to sleep (clamshell sleep from 17:11:52 to 17:28:09). The driver
    recorded the cell `FAILED` at 17:28:39 and restored `config.yaml`.
    That cell wrote no results file. Its run log is in
    `repo-artifacts/Cerebrum/bench_v2_functional_a4_killed_f15b/`, its
    kernel log (`kernel_qwen_agent_20261110T170418.log`) is with the
    others, and its rows are in `.replicated_memory/f15b`.
  - `RUN_PREFIX=f15b2`, started 17:30:54 EST (AIOS known issue 36: a
    re-run gets its own run ids): it skipped the 9 finished cells and
    ran the other 20, finishing at 19:36:20.

  Run ids `<prefix>-<model>-<phase>-<method>-<condition>`.
- **UTC dates** (AIOS known issue 42: Mem0's extraction prompt holds
  the UTC date, which it writes into facts): the run crossed 00:00 UTC
  (19:00 EST).
  - The 4 kernel Mem0 cells, and the agent phase's Mem0 cells through
    `no_visibility`, ran on 2026-11-10 UTC.
  - In `writer_scoped` replicated Mem0, users 0 to 2 ran on 2026-11-10
    and users 3 and 4 on 2026-11-11 (user 3's first log line is
    19:00:04 EST).
  - Both `no_supersession` Mem0 cells ran on 2026-11-11.

  Where Mem0 wrote the date of a change into a row ("as of November 10,
  2026"), it is the row's own UTC date in every cell.
- **Kernels**: one fresh kernel per phase:
  `kernel_qwen_kmem0_20261110T160341.log`,
  `kernel_qwen_kinh_20261110T163735.log`,
  `kernel_qwen_agent_20261110T170418.log` (the stopped attempt),
  `kernel_qwen_agent_20261110T173054.log`,
  `kernel_qwen_kmem0_ns_20261110T190811.log`,
  `kernel_qwen_kinh_ns_20261110T191706.log` and
  `kernel_qwen_agent_ns_20261110T192308.log`. The driver's
  end-of-phase checks found no stored conversation turn and no guard
  warning in any kernel phase's log, and 0 memory operations in both
  agent phases' logs. No user failed the harness's `probe_writes`
  check.

## Reading the records

- `config_snapshot` is the kernel's configuration. In the agent phases
  every file records provider `mem0`, the in-house cells included;
  each trial's `backend_extraction` and the method name give the cell's
  own backend.
- No probe answer is stored: `contaminated` is false for all 725
  judge-free probes, and no injected row is a conversation row.
- `no_memory` stores no writer row, so its blocks are empty.
- **Every criterion holds** (`analysis.md`, "Functional check
  criteria"), Amendment 4's included. The guard's criterion counts the
  510 probes of the 17 kernel and replicated cells built on H = 0 (the
  reference and its controls).
- The budget bound in no in-house probe of a kernel or replicated cell
  (the largest such block was 296 estimated tokens) and in 10 Mem0
  probes, in both loci. Under Amendment 4 that is reported, not
  required. Native has no budget, so `budget_bound` is empty there and
  a native block can pass 300 estimated tokens (302 in native Mem0
  `no_visibility`).
- Kernel and replicated Mem0 store what Mem0's extraction writes, and
  on the same inputs the two loci differ (AIOS known issue 42). Kernel
  Mem0 failed 2 recency probes at H = 0 (users 1 and 2) through a row
  of the new statement that names the old value as past ("relocated to
  Kaunas from Utrecht"); replicated Mem0's rows of those events name
  only the new value. Such a row is the new statement, so supersession
  does not retire it (`DELETION_AND_SUPERSESSION.md`).
- At H = 2, replicated leaves user 4's first `home_city` row unmarked
  on both backends: the V2 profile writer stores it under the
  `…@users.example` id, and the later statement, written under the
  canonical id, does not reach it. The kernel folds that domain into
  the canonical id (`identity`: `casefold`, `email_domains`), and marks
  the row.
- `revoked_value_rows` carries each carrier's text as `content`.

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py` output at
  Cerebrum `059e5a5` (the per-probe pass matrix, cap and budget, the
  check's criteria, kernel against replicated, the revokes and the
  forget, supersession, and the readings).
- The per-trial results files, run logs, kernel logs and both driver
  logs are in `repo-artifacts/Cerebrum/bench_v2_functional_a4/`. They
  are not committed.
