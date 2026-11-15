# bench_v2_smoke_s17: provenance

Amendment 6's re-verification (NeurIPS Subtask 17): the benchmark v2
smoke's kernel and replicated cells on in-house, Mem0 and Graphiti at
k = 30 with the 300-token budget, and its native Graphiti cell with
the agents' `invalid_at` filter (Subtask 17, Decision 2), at H = 0 on
`users_v2` revision 3. Beside the k = 10 smokes it re-runs
(`results/bench_v2_smoke_a4`, in-house and Mem0;
`results/bench_v2_smoke_graphiti`, Graphiti), which ran the same users
with the same per-user inputs. Design: AIOS `docs/BENCHMARK_V2.md`,
Amendments 6 and 7; the native filter: AIOS `docs/NATIVE_USAGE.md`,
"native_graphiti". A smoke, not a verdict: no rule was pre-registered.
Results: Amendment 7 and AIOS `docs/DEV_STATUS.md`, Subtask 17.

`analysis.md` and `analysis.json` are
`benchmarks.shared_memory.bench_v2_analysis`'s output on the seven
cells, without the functional check's criteria (`--no-criteria`),
generated after the run with Cerebrum `f74b1b9`, which adds the block
columns; it reads the same files.

- **Code**: every results file records Cerebrum
  `2b9a776239b708d0c8658bc31c9c09673ba915a3` and AIOS
  `612c989a71c2b6b58fb678b58f4eebf7b6435e68`, neither `-dirty`; the
  driver refuses a tracked change in either repo. Library
  `PIPELINE_VERSION` `d79cced77347d848` in the kernel and replicated
  trials (native trials record none).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`).
  Seven cells at H = 0: kernel on in-house (`kinh`), Mem0 (`kmem0`) and
  Graphiti (`kgra`); replicated on the three; native on Graphiti. 210
  user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. Judge v2 on the integration probe only:
  `gpt-5.4:azure` through the kernel, prompt v2 (SHA-256 `17f43dd9…`),
  temperature 0.0, seed 20261105, one call per trial (the kernel logs
  show 30 gpt-5.4 calls per cell). Mem0's and Graphiti's extraction:
  Azure gpt-4o through LiteLLM, temperature 0.0, seed 20261105, each
  call tagged with the user and counted to the trial. Embedding:
  `nomic-embed-text` (Ollama).
- **Backends**: in-house Chroma; `mem0ai` 2.0.2; `graphiti-core` 0.31.2
  with the `neo4j` driver 6.4.1 on `neo4j:5.26.33-community` (Docker
  container `aios-graphiti-neo4j`); each Graphiti cell's
  `config_snapshot.backend_versions` records the three versions.
- **Settings** (pre-flight checked, recorded as `run_settings`): k 30,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms, `supersession` `exclude`. Native consumers
  use k 10 (`V2_NATIVE_K`; the native cell records the kernel's
  settings, which it does not use). Kernel `auto_inject` on and
  `auto_extract` off in the kernel phases, both off in the agent
  phases.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=smoke`,
  `PHASES="kinh kmem0 agent kgra agent_gra"`, `METHODS="kernel_shared
  replicated_inhouse replicated_mem0 replicated_graphiti
  native_graphiti"`, `OUTROOT=results/bench_v2_smoke_s17`, in two
  launches:
  - `RUN_PREFIX=s17`, 2026-11-12 13:35 to 16:03 EST: the in-house
    kernel cell (13:35 to 14:24) and the Mem0 kernel cell (14:25 to
    15:31); stopped by the user's decision (the laptop was to shut)
    during the Mem0 replicated cell, whose log is kept as
    `logs/qwen_agent_replicated_mem0_h0.killed_s17.log`. The driver
    restored `config.yaml` at exit.
  - `RUN_PREFIX=s17b` (a new prefix for the resume, AIOS known issue
    36), 2026-11-12 21:12 to 2026-11-13 03:28 EST: it found the two
    kernel cells finished at the current commits and re-checked their
    logs, then ran the Mem0 replicated cell whole (21:12 to 22:02), the
    in-house replicated cell (22:02 to 22:52), the Graphiti kernel cell
    (22:52 to 00:24), and the replicated (00:25 to 01:58) and native
    (01:58 to 03:28) Graphiti cells. Run ids
    `<prefix>-qwen-<phase>-<method>-h0`.
  - Driver logs: the first launch's is
    `repo-artifacts/Cerebrum/bench_v2_smoke_s17.log`, the second's
    `driver.s17b.log` in this directory.
- **Machine**: one laptop. Its Qwen speed moved between 48 and 131 ms
  per completion token over the run (10-minute windows), with its heat
  and power state (the second launch ran on battery from 21:12 to
  22:12, from 97% down to 19%), so time per user is not comparable
  between cells (Amendment 7 gives each cell's milliseconds per token).
- **Kernels**: one fresh kernel per phase (`logs/kernel_qwen_*`). The
  driver's end-of-phase checks found no stored conversation turn and
  no guard warning in each kernel phase's log, and 0 memory operations
  in each agent phase's log.
- **Logs**: no traceback, no ERROR-level record and no write-barrier
  `TIMEOUT` in any kernel, run or driver log. Warnings: Mem0's "Failed
  to load spaCy" (two lines in each Mem0 cell's log: the kernel's, the
  replicated cell's and its interrupted first attempt's; NATIVE_USAGE.md,
  "Install") and Graphiti's "Materialized N dangling edge endpoint
  node(s)", 4 times (1 kernel, 3 replicated). No writer failed or
  retried, no write gave
  Graphiti no fact (`writes_without_fact` empty in all 210 trials), and
  all 630 recorded write-barrier waits drained (210 per kernel cell).
- **Backend calls**, from the logs against the trials' records (LiteLLM
  logs each gpt-4o call twice): every cell matches, 534 calls per Mem0
  cell, 2,195 (kernel), 2,187 (replicated) and 2,215 (native) on
  Graphiti.
- **Key scan**: `scripts/archive_artifacts.py --check` (Subtask 17)
  found no configured key value or fragment of one in this directory's
  files or the first launch's driver log before they were archived to
  `repo-artifacts/Cerebrum/bench_v2_smoke_s17/`.
