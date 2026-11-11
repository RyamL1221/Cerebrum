# bench_v2_smoke_a4: provenance

The benchmark v2 smoke under Amendment 4 (NeurIPS Subtask 15, step 1:
complete deletion and supersession), on `users_v2` revision 3. Design:
AIOS `docs/BENCHMARK_V2.md`, "Functional check and smoke", with
Amendments 1 to 4, and AIOS `docs/DELETION_AND_SUPERSESSION.md`. A
smoke, not a verdict: no rule was pre-registered. Results: AIOS
`docs/DEV_STATUS.md`, Subtask 15.

- **Code**: every results file records Cerebrum
  `64da5f765ec9cd9926dc486f9b167f6b0574a107` and AIOS
  `ef3fdc9ddff37c619565f71d015fb6142d39472e`, neither `-dirty`; the
  driver refuses a tracked change in either repo. Cerebrum `64da5f7`
  is the functional check's code (`059e5a5`) with the extraction check
  fixed (below). AIOS `52bf922` and `ef3fdc9` change only documents,
  so the kernel's code is the functional check's (`945548e`). Library
  `PIPELINE_VERSION` `73b1b63748628e57` (kernel and replicated trials;
  native trials record none, and their `run_settings` record the
  kernel's).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`),
  all 30 users, with the same per-user `input_sha256` in every cell,
  in the first attempt and, for users 0 to 4, in
  `bench_v2_functional_a4`. Six cells at H = 0: kernel, replicated and
  native, each on Mem0 and in-house. 180 user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384 (every trial's `decoding`). Judge v2 on the
  integration probe only: `gpt-5.4:azure` through the kernel, prompt v2
  (SHA-256 `17f43dd9…`), temperature 0.0, seed 20261105, one call per
  probe, each on its first attempt. The judge model is not in the
  results files; the driver sets it (`run_bench_v2.sh`, `MODE=smoke`),
  and the kernel logs show 30 gpt-5.4 calls per cell. Mem0's
  extraction in the three Mem0 cells: Azure gpt-4o, temperature 0.0,
  seed 20261105, `mem0ai` 2.0.2 in both venvs, without its `[nlp]`
  extra (spaCy absent; AIOS `DEV_STATUS.md`, open decision 1).
  Embedding: `nomic-embed-text` (Ollama).
- **Settings** (pre-flight checked, recorded as `run_settings`): k 10,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms, `supersession` `exclude`. Kernel
  `auto_inject` on and `auto_extract` off in the kernel phases, both
  off in the agent phase.
- **Store files**: the kernel keeps its tombstones in AIOS
  `.aios_state/tombstones.sqlite` and its Mem0 history in AIOS
  `.mem0/history.db`. Each replicated store keeps its own
  (`.replicated_memory/s15b/<backend>/tombstones.sqlite`, and
  `history.db` for Mem0), and native Mem0 keeps its history in its
  store directory (`.native_memory/s15b/native_mem0/`). The pre-flight
  records the kernel's tombstones path in every cell, and its Mem0
  history path in every cell but kernel in-house, whose kernel runs no
  Mem0 (`history_db_path` null there). The agent cells record the
  agent phase's kernel's paths, not their own stores'.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=smoke`,
  `RUN_PREFIX=s15b` and `OUTROOT=results/bench_v2_smoke_a4`, under
  `caffeinate -is`, started 2026-11-10 21:28 EST and finished
  2026-11-11 01:46 EST: kernel Mem0 21:28 to 22:15, kernel in-house
  22:16 to 22:54, and the agent phase 22:54 to 01:46 (replicated Mem0,
  replicated in-house, native Mem0, native in-house). Run ids
  `s15b-<model>-<phase>-<method>-<condition>`. The driver restored
  `config.yaml` from its copy at exit (01:46:50); it holds the
  settings from before the run.
- **UTC dates** (AIOS known issue 42: Mem0's extraction prompt holds
  the UTC date, which it writes into facts): the run ran from 02:28 to
  06:46 UTC, all on 2026-11-11. Every full date Mem0 wrote into a fact
  is November 11, 2026 (once "the week of November 11, 2026", for
  "this week"). Mem0 also wrote that month ("as of November 2026"),
  the year for "this year" in 3 of its 4 inputs, and, in every Mem0
  store, "December 2026" for "next month"; of those, only native
  Mem0's rows for users 3, 9 and 18 reached a block. In-house rows hold
  no calendar date. Every calendar date an answer takes from its block
  is one of these. Four privacy answers give made-up events dates that
  are in no block: replicated Mem0 user 15 (January to April 2027),
  native Mem0 user 15 (November 15, 18 and 22, 2026), and native
  in-house users 21 (March 14 to 22) and 6 ("2023", in a webinar's
  title). In-house privacy answers also give made-up events weekdays
  (kernel and replicated user 21, native users 6 and 21).
- **Kernels**: one fresh kernel per phase:
  `kernel_qwen_kmem0_20261110T212802.log`,
  `kernel_qwen_kinh_20261110T221539.log` and
  `kernel_qwen_agent_20261110T225431.log`. The driver's end-of-phase
  checks found no stored conversation turn and no guard warning in
  either kernel phase's log, and 0 memory operations in the agent
  phase's log. No user failed the harness's `probe_writes` check.
- **Logs**: no traceback and no ERROR-level record in any kernel or
  run log. Each kernel log has the four lines LSFS prints without a
  level (`bench_v2_smoke`'s provenance): one "Failed to connect to
  Redis" at startup and three "Error handling file change" from its
  file watcher; neither is on the memory path. The only warnings are
  Mem0's "Failed to load spaCy … model". No writer retried, no OpenAI
  client call was retried, and every recorded write-barrier wait
  drained (360, none timed out). None of this run's 16 files (results,
  run and kernel logs, the driver log) holds the Zep or the Azure key,
  nor does the first attempt's kernel log.

## Reading the records

- `config_snapshot` is the kernel's configuration. In the agent phase
  every file records provider `mem0`, the in-house cells included;
  each trial's `backend_extraction` and the method name give the cell's
  own backend.
- No probe answer is stored: `contaminated` is false for all 900
  judge-free probes, and all 10,554 injected rows are the three
  writers' (none is a conversation row).
- The functional check's criteria need its controls, which the smoke
  does not run (`--no-criteria`). Amendment 4's criteria that need no
  control hold at H = 0 in the four kernel and replicated cells: all
  120 deletion probes pass, no audit kept a carrier, and all 120
  revokes went through the forget; no block of their 720 probes holds
  a retired row; the guard reported its stage in all 720, was armed in
  every probe after a forget and dropped nothing; all 60 Mem0 forgets
  scrubbed a message (80 messages).
- The budget bound in 3 in-house probes per locus (all integration)
  and in 5 Mem0 probes per locus (kernel: 3 integration, 2 privacy;
  replicated: 2 integration, 1 privacy, 2 recency). Under Amendment 4
  that is reported, not required. Native has no budget, so
  `budget_bound` is empty there and a native block can pass 300
  estimated tokens (301 in-house, 323 Mem0).
- Kernel against replicated: the in-house blocks are identical in 180
  of 180 probes. On Mem0, 1 of the 150 paired judge-free outcomes
  differs (user 8's recency: kernel failed, replicated passed). Both
  Mem0 loci store what Mem0's extraction writes, and on the same inputs
  the loci can differ (AIOS known issue 42).
- **Folds** (AIOS `DELETION_AND_SUPERSESSION.md`, "Not pre-stated").
  In both Mem0 library cells the forget deleted two rows of the
  revoking writer's other facts by the value (`same_writer` in the
  forget reading): Mem0 had folded user 13's codename into its client
  row and user 25's teammate into its codename row. Each was its
  user's recall target and its only row, so recall failed for both
  users in both loci (`target_forgotten` in the misses reading).
- Every recency failure in the Mem0 library cells (8 kernel, 7
  replicated) is through the target's own row, which Mem0's extraction
  wrote as a transition ("moved from Ryver to Brosix"). Such a row is
  the new statement, so supersession does not retire it. Each failing
  answer named the new value; 14 of the 15 also named the old one as
  past.
- Native runs neither the forget nor supersession, and its writers
  revoke their own rows: deletion failed through 9 in-house and 2 Mem0
  echo rows and 2 Mem0 folds, and a retired row reached 168 in-house
  and 131 Mem0 probe blocks. Native Mem0's ranking (AIOS
  `DEV_STATUS.md`, Subtask 15, step 0, A) kept most targets out of its
  10-row fetch: recall passed 5 of 30.

## The first attempt

- **`s15`** (Cerebrum `5b3295e`, AIOS `52bf922`; started 2026-11-10
  19:52 EST) stopped in its first cell, kernel Mem0, after its 30
  users: the extraction check failed user 19 because the forget had
  deleted, by the value, the only row of a write in its own session
  (`u019-e08`), into which Mem0 had folded the revoked codename. Fixed
  in Cerebrum `64da5f7` (AIOS `BENCHMARK_V2.md`, Amendment 4,
  "Corrected during the smoke"); AIOS `DEV_STATUS.md`, Subtask 15,
  "Smoke, first attempt". Its numbers are not this smoke's. Its
  results file, run log, kernel log and driver log are in
  `repo-artifacts/Cerebrum/bench_v2_smoke_a4_s15/`; an identical copy
  of its kernel log, `kernel_qwen_kmem0_20261110T195140.log`, is also
  in this directory's `logs/`.

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py --no-criteria`
  output at Cerebrum `ec623ab`. `0995994` added two readings after the
  run, `target_forgotten` (misses) and `same_writer` (forgets), and
  `ec623ab` prints every integration mean with two decimals (native
  Mem0's 3 as 3.00); nothing else in the output changed.
- The per-trial results files, run logs, kernel logs and the driver log
  are in `repo-artifacts/Cerebrum/bench_v2_smoke_a4/` (checksums in its
  `SHA256SUMS`). They are not committed.
