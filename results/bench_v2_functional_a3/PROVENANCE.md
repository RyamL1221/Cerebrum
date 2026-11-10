# bench_v2_functional_a3: provenance

The benchmark v2 functional check under Amendment 3 (NeurIPS Subtask
15, step 0), on `users_v2` revision 3. Design and pass conditions: AIOS
`docs/BENCHMARK_V2.md`, "Functional check and smoke", with Amendments 1
to 3 (Amendment 3: probes write nothing, a 300-token budget, revision 3
of the data). Result: AIOS `docs/DEV_STATUS.md`, Subtask 15.

- **Code**: every results file records Cerebrum
  `af078c3f12d8d14a9334cf9cca8fbac3223abd72` and AIOS
  `38696f3910c0a3139df1e93cc690399be4a0978b`, neither `-dirty`. Library
  `PIPELINE_VERSION` `46e28207331f9284` (kernel and replicated cells;
  native trials record none).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`),
  users 0 to 4. 21 cells: the six locus × backend cells at H = 0, H = 2
  and `no_delete`, plus `no_memory` (kernel in-house) and
  `no_visibility` (native, both backends). 105 user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. No judge (the integration probe is
  unscored). Mem0 extraction: Azure gpt-4o, temperature 0.0, seed
  20261105, `mem0ai` 2.0.2 in both venvs, without its `[nlp]` extra
  (spaCy absent; AIOS `DEV_STATUS.md`, open decision 1). Embedding:
  `nomic-embed-text` (Ollama).
- **Settings** (pre-flight checked, recorded as `run_settings`): k 10,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms. Kernel `auto_inject` on and `auto_extract`
  off in the kernel phases, both off in the agent phase.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=functional`
  and `RUN_PREFIX=f15a`, started 2026-11-09 22:22, finished
  2026-11-10 00:35 (EST), that is 03:22 to 05:35 UTC on 2026-11-10, so
  Mem0's extraction prompt carried one date in every phase (AIOS known
  issue 42). Run ids `f15a-<model>-<phase>-<method>-<condition>`.
- **Kernels**: one fresh kernel per phase:
  `kernel_qwen_kmem0_20261109T222233.log`,
  `kernel_qwen_kinh_20261109T224502.log` and
  `kernel_qwen_agent_20261109T230538.log`. The driver's end-of-phase
  checks found no stored conversation turn in either kernel phase's log
  and 0 memory operations in the agent-phase log. No user failed the
  harness's `probe_writes` check.

## Reading the records

- `config_snapshot` is the kernel's configuration. In the agent phase
  every file records provider `mem0`, the in-house cells included;
  each trial's `backend_extraction` and the method name give the cell's
  own backend.
- No probe answer is stored, so `contaminated` is false for all 525
  judge-free probes, and the analysis's "stale value in an earlier
  answer" table has no probe with one.
- `no_memory` stores no writer row, so its blocks are empty. In the
  revision-2 check (`f14c`) they held the consumer's own stored answers.
- **The budget criterion fails.** The 300-token budget bound in no
  probe of a kernel or replicated in-house cell; the largest such block
  was 291 estimated tokens. It bound in 3 Mem0 probes (kernel
  `no_delete` recall and integration, replicated H = 0 recency). The
  other eight criteria hold. See AIOS `DEV_STATUS.md`, Subtask 15.

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py` output at
  Cerebrum `af078c3` (the per-probe pass matrix, cap and budget, the
  check's criteria, kernel against replicated, and the readings).
- The per-trial results files, run logs, kernel logs and the driver log
  are in `repo-artifacts/Cerebrum/bench_v2_functional_a3/`. They are
  not committed.
