# bench_v2_smoke_amem: provenance

The benchmark v2 smoke on A-MEM (NeurIPS Subtask 17): kernel, replicated
and native at H = 0 on `users_v2` revision 3, beside the k = 30 cells of
in-house, Mem0 and Graphiti (`results/bench_v2_smoke_s17`), which ran
the same users with the same per-user inputs and settings. Design: AIOS
`docs/BENCHMARK_V2.md`, Amendments 6 to 8; the backend: AIOS
`docs/AMEM_BACKEND.md` and `docs/NATIVE_USAGE.md`, "native_amem". A
smoke, not a verdict: no rule was pre-registered. Results: AIOS
`docs/DEV_STATUS.md`, Subtask 17.

`analysis.md` and `analysis.json` are
`benchmarks.shared_memory.bench_v2_analysis`'s output on the three
cells, without the functional check's criteria (`--no-criteria`),
generated after the run with Cerebrum `33bd093` (the block columns'
note per table, `a83cf8e`); it reads the same files.

- **Code**: every results file records Cerebrum
  `f6d2646739687f6a49b393ba16b2301b6bd61684` and AIOS
  `a145a2603dfcaf11284f20f4c0657628761ab819`, neither `-dirty`; the
  driver refuses a tracked change in either repo. Library
  `PIPELINE_VERSION` `e8dadd1ced3dea04` in the kernel and replicated
  trials (native trials record none).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`),
  all 30 users, each with the same `input_sha256` in every cell and in
  every cell of `bench_v2_smoke_s17`. Three cells at H = 0: kernel
  (`kamem`, `kernel_shared`), replicated and native (`agent_amem`,
  `replicated_amem` and `native_amem`). 90 user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384 (every trial's `decoding`). Judge v2 on the
  integration probe only: `gpt-5.4:azure` through the kernel, prompt v2
  (SHA-256 `17f43dd9…`), temperature 0.0, seed 20261105, one call per
  probe, each on its first attempt (the kernel logs show 30 gpt-5.4
  calls per cell). A-MEM's LLM (every cell, `backend_extraction` true):
  Azure gpt-4o through LiteLLM's synchronous `completion`, temperature
  0.0, seed 20261105, each call tagged with the user and counted to the
  trial. Embedding: `nomic-embed-text` (Ollama, 768 dimensions).
- **Backend**: `agentic_memory` (WujiangXu/A-mem-sys) at
  `f303dfc71e07bdc787f4bc135d4cea328ae30e99` with `chromadb` 1.5.9 in
  both venvs (LiteLLM 1.83.0). One `AgenticMemorySystem` per user, in a
  temporary Chroma directory of the store's process; nothing persists
  across processes. Each cell's `config_snapshot.backend_versions`
  records the two versions.
- **Settings** (pre-flight checked, recorded as `run_settings`): k 30,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms, `supersession` `exclude`; `scored_search`
  true (`config_snapshot.capabilities`); `history_db_path` null (no
  Mem0). Native consumers use k 10 (`V2_NATIVE_K`: `top_k_used` is 10
  in all 180 native probes) and no token budget (`NATIVE_USAGE.md`); the
  native cell records the kernel's settings, which it does not use.
  Kernel `auto_inject` on and `auto_extract` off in the kernel phase,
  both off in the agent phase.
- **Store files**: the kernel keeps its tombstones in AIOS
  `.aios_state/tombstones.sqlite`, the replicated store in Cerebrum
  `.replicated_memory/s17a/amem/tombstones.sqlite`; native A-MEM keeps
  nothing outside its process. The agent cells record the agent phase's
  kernel's tombstones path, not their own store's.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=smoke`,
  `PHASES="kamem agent_amem"` (the agent phase's two methods,
  `replicated_amem` and `native_amem`), `RUN_PREFIX=s17a`,
  `OUTROOT=results/bench_v2_smoke_amem` and
  `ARCHIVE=../repo-artifacts/Cerebrum/bench_v2_smoke_amem`, started
  2026-11-15 20:51 EST, after the pilot_v1 smoke
  (`results/pilot_v1_amem`), and finished 23:52 EST: kernel 20:51 to
  21:52, replicated 21:53 to 22:53, native 22:53 to 23:52. Run ids
  `s17a-qwen-<phase>-<method>-h0`. Its log is `driver.log` here. The
  driver restored `config.yaml` from its copy at exit (23:52:35). At
  the end it archived this folder through AIOS
  `scripts/archive_artifacts.py`: 9 files scanned, none holds a key
  value.
- **Machine**: one laptop on AC power. Qwen generated at 52, 53 and 54
  ms per completion token (kernel, replicated, native; Amendment 7's
  split), 118 to 123 s per user.
- **Kernels**: one fresh kernel per phase,
  `kernel_qwen_kamem_20261115T205102.log` and
  `kernel_qwen_agent_amem_20261115T215251.log`. The driver's
  end-of-phase checks found no stored conversation turn and no guard
  warning in the kernel phase's log, and 0 memory operations in the
  agent phase's log.
- **Logs**: no traceback, no WARNING-level record and no write-barrier
  `TIMEOUT` in any kernel, run or driver log. Each kernel log has the
  four lines LSFS prints without a level (one "Failed to connect to
  Redis" and three "Error handling file change"; neither is on the
  memory path). One ERROR-level record, in the native cell's run log:
  A-MEM's "Error in memory evolution" (below). No writer failed or
  retried, no write returned without a note (`writes_without_fact` 0 in
  all 90 trials), and every recorded write-barrier wait drained (210,
  kernel; the replicated and native stores record none).
- **Backend calls**, from the logs against the trials' records (LiteLLM
  logs each call twice): each cell's log holds exactly twice its
  trials' count, 1,038 calls per cell (the kernel cell's in its phase's
  kernel log, the replicated and native cells' in their run logs).

## Reading the records

- No probe answer is stored: `contaminated` is false for all 450
  judge-free probes, and all 5,815 injected rows are the three writers'
  (none is a conversation row).
- Amendment 4's criteria that need no control hold at H = 0 in the
  kernel and replicated cells: all 60 deletion probes pass, no audit
  kept a carrier, and all 60 revokes went through the forget; no block
  of their 360 probes holds a retired row; the guard reported its stage
  in all 360, was armed in all (every probe follows the user's forget)
  and dropped nothing.
- **The forget** deleted 41 rows in the kernel cell (30 by the slot's
  `fact_key`, 10 by a value, 1 `derived`; 11 of other agents) and 40 in
  the replicated cell (30, 10 and 0; 10), against 40 in-house and on
  Graphiti and 43 on Mem0 (`bench_v2_smoke_s17`). The `derived` row is
  the runs' first: in user 2's forget of `conference` (event
  `u002-e15`), the kernel's scrub deleted the user's base task context,
  the task agent's note of event `u002-e02`, because A-MEM's evolution
  had written a form of the revoked value into that note's derived text
  (its context, keywords or tags); `history` counts the same note. The
  deletion took the base task with it: user 2's integration block held
  no base task row in the kernel cell, while the replicated and native
  blocks did, and the probe scored 2 in all three cells. The replicated
  store's evolution had not carried the value there, and its forget
  deleted only the slot's row.
- **Kernel against replicated**: all 150 paired judge-free outcomes
  agree. The blocks' text is the same in 14 of 180 probes, and they
  hold rows of the same writes in 106: A-MEM's analysis and evolution
  text, which differ between runs, enter each note's embedding, so the
  two stores rank the same notes differently (`AMEM_BACKEND.md`, "Open
  risks", 3).
- **Against in-house** (`bench_v2_smoke_s17`, the same users at the
  same settings): A-MEM stores each write verbatim, as in-house does,
  but ranks by its notes' embeddings. The blocks hold rows of the same
  writes as in-house's in 67 of 180 probes in each locus (the same text
  in 3), and 20 kernel and 22 replicated answers are the same. All 150
  judge-free probes pass with either backend in each locus, the budget
  binds in 156 of 180 probes with both, and the integration means are
  2.57 and 2.63 against in-house's 2.57 and 2.60. (With pilot_v1's 3
  notes a user every note is in the block, and at H = 0 the kernel and
  replicated answers equal in-house's: `results/pilot_v1_amem`.)
- **The budget, not the cap**, in the kernel and replicated cells: the
  budget bound in 156 of 180 probes each and the cap in none (in-house
  156, Mem0 180, Graphiti 108 and 96, in `bench_v2_smoke_s17`), with
  11.5 rows and about 262 estimated tokens a block. Native, at k 10 and
  without a budget, hit the cap in all 180 probes (9.3 rows; its
  visibility rule removed another agent's private row in 129 of them),
  up to 314 tokens.
- **Integration** (judge v2): kernel 2.57 [2.20, 2.93], replicated 2.63
  [2.22, 3.04], native 2.73 [2.32, 3.15], against in-house 2.57 and
  2.60, Mem0 3.40 and 3.57, and Graphiti 2.50, 2.17 and 2.07 (kernel,
  replicated, native) in `bench_v2_smoke_s17`. Eight kernel, nine
  replicated and twelve native answers scored 4 or more.
- **Native** runs neither the forget nor supersession, and its writers
  delete their own notes:
  - Deletion failed in 10 of 30, each through an echo (another writer's
    statement of the value, which no native writer deletes): the store
    kept the echo for 10 users (20 rows), and in each it reached the
    block. The 20 deletions with no echo all passed, and the echoes are
    the only rows holding a revoked value that outlived the revoke.
    Native Graphiti (`bench_v2_smoke_s17`): 7 of 30, its echo left out
    of the block in 3.
  - An earlier statement's row reached 170 of 180 probe blocks (native
    Graphiti, with its `invalid_at` filter, 27). Recency passed 17 of 30
    and contradiction 17 of 30 (native Graphiti 30 and 26); each of the
    26 failures held the stale value in a writer's row. Leniently (the
    new value named, stale or not), recency 28 of 30 and contradiction
    20 of 30; 11 recency answers named both values, 9 of them the stale
    one as past.
- **A-MEM** (Amendment 8's readings): 1,602 writes (534 per cell, 17.8
  per user), each with one store-helper line `A-MEM evolved <n> note(s)
  at note <id>` in every locus: the existing notes a write's evolution
  changed, 1.39 (kernel), 1.46 (replicated) and 1.45 (native) on
  average, 1.47 to 1.54 per evolution call, at most 5, none in 156, 145
  and 144 writes. One line of A-MEM's own caught failures, in the
  native cell: "Error in memory evolution: 'tags_to_update'" (user 11,
  23:15:56), an evolution reply of gpt-4o's without that key. The note
  was stored, its evolution changed nothing (`evolved 0`), and the trial
  passed its five judge-free probes, among them the recall probe whose
  target the note was. 1.94 calls per write: an analysis call per note
  and an evolution call for each but a store's first (1,038 = 2 x 534 -
  30 per cell), about 670 prompt tokens a call.

## Cost and latency

Per user (the 6 sessions and 6 probes), against `bench_v2_smoke_s17`:

| cell | backend calls | per write | prompt tokens | USD | wall time | ms per token |
|---|---:|---:|---:|---:|---:|---:|
| A-MEM kernel | 34.6 | 1.94 | 23,254 | 0.10 | 123 s | 52 |
| A-MEM replicated | 34.6 | 1.94 | 23,208 | 0.10 | 121 s | 53 |
| A-MEM native | 34.6 | 1.94 | 23,181 | 0.10 | 118 s | 54 |
| Graphiti kernel | 73.2 | 4.11 | 153,224 | 0.42 | 185 s | 52 |
| Graphiti replicated | 72.9 | 4.10 | 152,806 | 0.42 | 187 s | 51 |
| Graphiti native | 73.8 | 4.15 | 154,885 | 0.42 | 179 s | 49 |
| Mem0 kernel | 17.8 | 1.00 | 139,721 | 0.36 | 133 s | 81 |
| Mem0 replicated | 17.8 | 1.00 | 139,716 | 0.36 | 99 s | 55 |
| in-house kernel | 0 | 0 | 0 | 0 | 99 s | 89 |
| in-house replicated | 0 | 0 | 0 | 0 | 100 s | 92 |

17.8 writes per user. USD is the backend's, at the committed price
table (gpt-4o; the assistant and the embedder are local, and the judge
is the benchmark's cost). Wall time is the cell's duration over its 30
users, from the driver logs; ms per token is Qwen's per completion
token in the cell (Amendment 7), and only cells at about the same speed
compare, here A-MEM's and Graphiti's. A-MEM's write (its two calls)
took a median of 3.33 s in the kernel (p90 3.94 s, longest 16.3 s),
from each `add_memory` line to its `A-MEM evolved` line in the kernel
log, about 60 s of each user's time; Graphiti's `add_episode` took 6.3
to 6.5 s (`bench_v2_smoke_graphiti`).

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py --no-criteria`
  output at Cerebrum `33bd093`.
- The per-trial results files, run logs, kernel logs and the driver log
  are in `repo-artifacts/Cerebrum/bench_v2_smoke_amem/` (checksums in
  its `SHA256SUMS`). They are not committed.
