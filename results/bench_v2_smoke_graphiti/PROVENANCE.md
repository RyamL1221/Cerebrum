# bench_v2_smoke_graphiti: provenance

The benchmark v2 smoke on Graphiti (NeurIPS Subtask 16): kernel,
replicated and native at H = 0 on `users_v2` revision 3, under
Amendments 1 to 5, beside the Mem0 and in-house smoke
(`results/bench_v2_smoke_a4`), which ran the same users, the same
per-user inputs and the same settings. Design: AIOS
`docs/BENCHMARK_V2.md`, "Functional check and smoke", and Amendments 1
to 5; the backend: AIOS `docs/GRAPHITI_BACKEND.md` and
`docs/NATIVE_USAGE.md`, "native_graphiti". A smoke, not a verdict: no
rule was pre-registered. Results: AIOS `docs/DEV_STATUS.md`, Subtask 16.

- **Code**: every results file records Cerebrum
  `c3f5adebf9e9d70fcde9d25bf8394881e0607a75` and AIOS
  `d9ca01fe5791508457fe29b796acfe3fa930734f`, neither `-dirty`; the
  driver refuses a tracked change in either repo. Since the functional
  check's last cells (Cerebrum `92fb30c`, AIOS `15e7644`): the review
  fixes (AIOS `236dc99`, `d9ca01f`; Cerebrum `abfd503`), and Cerebrum
  `a836d69`, which counts a V2 agent's backend calls in a v1 trial (v2's
  harness already read every id, Amendment 2). Library
  `PIPELINE_VERSION` `d79cced77347d848` in the kernel and replicated
  trials (native trials record none).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`),
  all 30 users, each with the same `input_sha256` in every cell and in
  `bench_v2_smoke_a4`. Three cells at H = 0: kernel, replicated and
  native, on Graphiti. 90 user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384 (every trial's `decoding`). Judge v2 on the
  integration probe only: `gpt-5.4:azure` through the kernel, prompt v2
  (SHA-256 `17f43dd9…`), temperature 0.0, seed 20261105, one call per
  probe, each on its first attempt (the kernel logs show 30 gpt-5.4
  calls per cell). Graphiti's extraction (every cell,
  `backend_extraction` true): Azure gpt-4o through LiteLLM's
  synchronous `completion`, temperature 0.0, seed 20261105, each call
  tagged with the user and counted to the trial. Embedding:
  `nomic-embed-text` (Ollama). No cross-encoder.
- **Backend**: `graphiti-core` 0.31.2 and the `neo4j` driver 6.4.1 in
  both venvs (LiteLLM 1.83.0); Neo4j `neo4j:5.26.33-community`
  (`neo4j@sha256:ec10d705830a340c7438e125cb5c4f90522b85369d877c9a581c3de5974ab3d6`),
  Docker container `aios-graphiti-neo4j`, one database shared by the
  kernel, replicated and native stores, separated by group (each group
  id carries the run id). Each cell's `config_snapshot.backend_versions`
  records the three versions.
- **Settings** (pre-flight checked, recorded as `run_settings`): k 10,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms, `supersession` `exclude`;
  `scored_search` false; `history_db_path` null (no Mem0). Kernel
  `auto_inject` on and `auto_extract` off in the kernel phase, both off
  in the agent phase.
- **Store files**: the kernel keeps its tombstones in AIOS
  `.aios_state/tombstones.sqlite`, the replicated store in Cerebrum
  `.replicated_memory/s16/graphiti/tombstones.sqlite`; native Graphiti
  keeps nothing outside Neo4j. The agent cells record the agent phase's
  kernel's tombstones path, not their own store's.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=smoke`,
  `PHASES="kgra agent_gra"`, `RUN_PREFIX=s16` and
  `OUTROOT=results/bench_v2_smoke_graphiti`, started 2026-11-12 00:04
  EST and finished 04:44 EST: kernel 00:05 to 01:40, replicated 01:40 to
  03:13, native 03:13 to 04:44. Run ids
  `s16-qwen-<phase>-<method>-h0`. The driver restored `config.yaml`
  from its copy at exit (04:44:54).
- **Dates**: the run ran from 05:04 to 09:44 UTC on 2026-11-12. Graphiti
  wrote no calendar date into a fact's sentence (AIOS known issue 42 is
  Mem0's): of the 1,724 distinct rows the blocks showed, one holds a
  relative date, "this week", from its input (native). Graphiti keeps
  its dates in `valid_at` and `invalid_at`, which no block prints.
- **Kernels**: one fresh kernel per phase,
  `kernel_qwen_kgra_20261112T000442.log` and
  `kernel_qwen_agent_gra_20261112T014028.log`. The driver's
  end-of-phase checks found no stored conversation turn and no guard
  warning in the kernel phase's log, and 0 memory operations in the
  agent phase's log.
- **Logs**: no traceback and no ERROR-level record in any kernel or
  run log. Each kernel log has the four lines LSFS prints without a
  level (one "Failed to connect to Redis" and three "Error handling
  file change"; neither is on the memory path). The only warnings are
  Graphiti's "Materialized N dangling edge endpoint node(s)", 4 times (1
  kernel, 1 replicated, 2 native): its edge extraction named an entity
  its node extraction had not, and Graphiti created the node to keep
  the edge (`edge_operations.py:391`). No writer failed or retried, no
  write gave Graphiti no fact (`writes_without_fact` empty in all 90
  trials), and every recorded write-barrier wait drained (180, kernel;
  the replicated and native stores record none). None of the run's 9
  files (results, run and kernel logs, the driver log) holds the Azure
  key, the Neo4j password or the config's API key.
- **Backend calls**, from the logs against the trials' records
  (LiteLLM logs each call twice; the kernel log split at each
  `/memory/cost` read, a run log at each trial's progress tick): every
  trial matches one for one, 2,173 calls (kernel), 2,179 (replicated)
  and 2,247 (native).

## Reading the records

- No probe answer is stored: `contaminated` is false for all 450
  judge-free probes, and all 5,283 injected rows are the three writers'
  (none is a conversation row).
- Amendment 4's criteria that need no control hold at H = 0 in the
  kernel and replicated cells: all 60 deletion probes pass, no audit
  kept a carrier, and all 60 revokes went through the forget; no block
  of their 360 probes holds a retired row; the guard reported its stage
  in all 360, was armed in all (every probe follows the user's forget)
  and dropped nothing. Each forget blanked at least one episode (40
  episodes per locus, and 63 kernel and 67 replicated entities deleted
  or summaries blanked: the scrub's `messages` and `history`); no fact
  was deleted with an entity (`entity` 0).
- **Kernel against replicated**: all 150 paired judge-free outcomes
  agree. No block's text is the same in both (Graphiti's sentences for
  one input differ between runs, as by a final period); the blocks hold
  rows of the same writes in 68 of 180 probes.
- **The cap, not the budget.** The cap bound in all 540 probes and the
  budget in none (the longest block is 197 estimated tokens). Graphiti
  stores a write's statement as about one fact and the base profile and
  task context as several: counted in Neo4j after the run (the stores as
  the forgets left them), the base profile's episode holds 3 to 5 facts
  (median 5, kernel), the base task's 1 to 11 (median 3.5), every other
  write's 1 (at most 3), about 23 facts per user. Ten facts hold a share
  of the base profile: the integration probe's block held 37% of its
  values in the kernel and replicated cells and 25% in native
  (`profile_facts_in_block`), against 100% in-house and 76 to 80% on
  Mem0 (`bench_v2_smoke_a4`).
- **Integration** (judge v2): kernel 2.20 [1.99, 2.41], replicated 1.97
  [1.74, 2.20], native 2.00 [1.74, 2.26], against in-house 2.87 and
  Mem0 3.57 to 3.60 in the kernel and replicated cells of
  `bench_v2_smoke_a4`. One answer per cell scored 4 or more.
- **Graphiti's own invalidations** (credited to no locus): it marked 53
  rows invalid in the kernel cell, 56 in replicated and 56 in native.
  Of these, 52, 54 and 53 are earlier statements of a slot (the rows
  the kernel's supersession retires; in the kernel cell it retired 60,
  52 of them also marked by Graphiti), and 1, 2 and 3 are a slot's
  latest statement, marked wrongly. Invalidated rows reached no kernel
  block, 5 replicated blocks (two latest statements, users 7 and 27;
  all 5 probes passed) and 132 native blocks.
- **Native** runs neither the forget nor supersession, and its writers
  revoke their own episodes (`remove_episode`):
  - Deletion failed in 7 of 30, each through an echo (another writer's
    statement of the value, which no native writer deletes). The store
    kept the echo for 10 users (20 rows); in 3 it did not reach the
    block. The 20 deletions with no echo all passed, and no row holding
    the revoked value outlived the revoke.
  - An earlier statement's row reached 149 of its 180 probe blocks
    (`bench_v2_smoke_a4`: 168 in-house, 131 Mem0). Recency passed 11 of
    30 and contradiction 13 of 30 (in-house 10 and 18, Mem0 0 and 0).
    Each of the 36 failures held the stale value in a writer's row; in
    32 of them, that row is a fact Graphiti had marked invalid, which
    `search()` returns and the block prints as a sentence
    (`NATIVE_USAGE.md`, "Validity").

## Cost and latency

Per user (the 6 sessions and 6 probes), against `bench_v2_smoke_a4`:

| cell | backend calls | per write | prompt tokens | USD | wall time |
|---|---:|---:|---:|---:|---:|
| Graphiti kernel | 72.4 | 4.07 | 152,270 | 0.41 | 191 s |
| Graphiti replicated | 72.6 | 4.09 | 152,580 | 0.42 | 186 s |
| Graphiti native | 74.9 | 4.21 | 156,200 | 0.43 | 182 s |
| Mem0 kernel | 17.8 | 1.00 | 139,690 | 0.36 | 95 s |
| Mem0 replicated | 17.8 | 1.00 | 139,710 | 0.36 | 96 s |
| Mem0 native | 17.8 | 1.00 | 139,740 | 0.36 | 102 s |
| in-house kernel | 0 | 0 | 0 | 0 | 77 s |

17.8 writes per user. USD is the backend's, at the committed price
table (gpt-4o; the assistant and the embedder are local, and the judge
is the benchmark's cost). Wall time is the cell's duration over its 30
users, from the driver log. Graphiti's `add_episode` took a median of
6.3 to 6.5 s a write (p90 7.1 to 7.6 s, longest 18.3 s), about 116 s
of each user's time.

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py --no-criteria`
  output at Cerebrum `c3f5ade`.
- The per-trial results files, run logs, kernel logs and the driver log
  are in `repo-artifacts/Cerebrum/bench_v2_smoke_graphiti/` (checksums
  in its `SHA256SUMS`). They are not committed.
