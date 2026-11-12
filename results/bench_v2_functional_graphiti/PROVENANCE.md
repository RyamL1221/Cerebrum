# bench_v2_functional_graphiti: provenance

The benchmark v2 functional check of the Graphiti cells (NeurIPS
Subtask 16), on `users_v2` revision 3, under Amendments 1 to 5. Design
and pass conditions: AIOS `docs/BENCHMARK_V2.md`, "Functional check and
smoke", and Amendment 5; the backend: AIOS `docs/GRAPHITI_BACKEND.md`
and `docs/NATIVE_USAGE.md`, "native_graphiti". Result: AIOS
`docs/DEV_STATUS.md`, Subtask 16.

`analysis.md` and `analysis.json` read the 14 cells below from three
result folders (`bench_v2_functional_graphiti`, `_a5`, `_a5b`), linked
into one tree for `bench_v2_analysis`. 70 user-trials, 0 failed. They
were made at Cerebrum `f34653b`, before `abfd503` added the forget
table's `entity` column; regenerated with the final code, the output
differs only by that column (0 in every row) and the forget note.

- **Cells and code.** Each results file records Cerebrum and AIOS
  commits, neither `-dirty`:
  - Cerebrum `2cccb44ad3fe51bcc88380ca8c778d216c2f1097`, AIOS
    `58f0e37a81df29ab22566b024eadae6ed56b78bd`
    (`bench_v2_functional_graphiti`, `RUN_PREFIX=f16b`): kernel H = 0,
    H = 2, `no_delete`, `writer_scoped`; replicated and native H = 0.
  - Cerebrum `674014320e13c2a1432c6f057dcb1c0c9d06c6bb`, AIOS
    `3fafc0913c9a3bfd21679d8c9359406634ea18f0` (`_a5`, `f16d`,
    Amendment 5): replicated and native `no_delete`; native
    `no_visibility`; replicated `writer_scoped`; kernel and replicated
    `no_supersession`.
  - Cerebrum `92fb30c2009a6cda5dad983874e63c04baba0a98`, AIOS
    `15e76447522e50ad49f65b9e3d2f7f79fa2f3ddc` (`_a5b`, `f16e`):
    replicated and native H = 2.

  Library `PIPELINE_VERSION` `c089bfa9a42539cc` in every kernel and
  replicated cell (native trials record none).

  Between the commits: Amendment 5 (a Graphiti write whose reply named
  no fact is a lost memory, not a failed trial), and native Graphiti
  listing a writer's rows by `agent_id` with Amendment 5 narrowed to a
  reply that named no fact. The `f16b` cells recorded no write without
  a row, so both rules read them as the rule they ran under did. The
  `f16d` replicated and native H = 2 cells are in `_a5` and are not
  read: native's listing found none of one user's V3 task agent's six
  writes (`DEV_STATUS.md`); `f16e` re-ran both.
- **Not read.** `bench_v2_functional_graphiti/qwen/agent_gra/
  h2_replicated_graphiti` is the second failed attempt (`f16c`,
  incomplete: a write with no fact, before Amendment 5). Both failed
  attempts are copied to `repo-artifacts/Cerebrum/
  bench_v2_functional_graphiti_failed_cell` and `_failed_cell2`. The
  first launch (`bench_v2_functional_graphiti_attempt1`, 12:15 to
  12:44, kernel H = 0 and H = 2) wrote JSON payloads as `json`
  episodes, 12 of 180 writes of which gave no fact; AIOS `58f0e37`
  writes them as the user's message. It is in `repo-artifacts`.
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`),
  users 0 to 4.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. No judge (the integration probe is
  unscored). Graphiti's extraction (every cell, `backend_extraction`
  true): Azure gpt-4o through LiteLLM's synchronous `completion`,
  temperature 0.0, seed 20261105, each call tagged with the user and
  counted to the trial. Embedding: `nomic-embed-text` (Ollama). No
  cross-encoder.
- **Backend**: `graphiti-core` 0.31.2 and the `neo4j` driver 6.4.1 in
  both venvs (LiteLLM 1.83.0); Neo4j `neo4j:5.26.33-community`
  (`neo4j@sha256:ec10d705830a340c7438e125cb5c4f90522b85369d877c9a581c3de5974ab3d6`),
  Docker container `aios-graphiti-neo4j`, one database shared by the
  kernel, replicated and native stores, separated by group.
- **Settings** (pre-flight checked, recorded as `run_settings`): k 10,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms, `supersession` `exclude` (`off` in the
  `_ns` phases). Kernel `auto_inject` on and `auto_extract` off in the
  kernel phases, both off in the agent phases. `history_db_path` null
  (no Mem0).
- **Driver**: AIOS `scripts/run_bench_v2.sh`, `MODE=functional`:
  - `f16b`, 2026-11-11 12:47 to 14:34 EST: the four kernel cells, then
    replicated and native H = 0; replicated H = 2 INCOMPLETE at 14:34.
    `f16c` (resume) 14:37 to 15:04: replicated H = 2 INCOMPLETE again.
  - `f16d`, `OUTROOT=results/bench_v2_functional_graphiti_a5`, 16:47
    to 18:47: eight cells.
  - `f16e`, `OUTROOT=results/bench_v2_functional_graphiti_a5b`, 18:57
    to 19:26: replicated and native H = 2.

  Every agent phase logged `kernel_memory_ops=0`; every kernel phase
  `stored_conversation_turns=0` and `guard_warnings=0`.
- **Logs**: driver logs `repo-artifacts/Cerebrum/
  bench_v2_functional_graphiti*.log`; kernel and cell logs under each
  folder's `logs/`.
