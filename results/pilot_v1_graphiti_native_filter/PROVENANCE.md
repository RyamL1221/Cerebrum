# pilot_v1_graphiti_native_filter: provenance

Subtask 17's Decision 2 re-run on pilot_v1: native Graphiti with the
agents' `invalid_at` filter (AIOS `docs/NATIVE_USAGE.md`,
"native_graphiti", "Validity"), at H = 0 and H = 2 on pilot_v1's 30
users, beside the Subtask 16 pilot_v1 smoke on Graphiti
(`results/pilot_v1_graphiti`, `RUN_PREFIX=pg16e`), whose native cells
it re-runs. Result: AIOS `docs/DEV_STATUS.md`, Subtask 17, and
`docs/NATIVE_USAGE.md`, "With the filter".

`analysis.md` and `analysis.json` are
`benchmarks.shared_memory.graphiti_smoke`'s output on six cells: this
run's two native cells and `results/pilot_v1_graphiti`'s kernel and
replicated cells (read through a scratch directory of links to the six
cells), against the Subtask 11 pilot's gaps
(`results/pilot_v1_hetero/gaps.csv`), generated with Cerebrum
`f74b1b9`. Its pairing check reports "2
different commit pairs": the native cells' and the kernel and
replicated cells' (below). Every other check passed: each cell is
complete, on the committed schedule, and each user has the same inputs
and variants in all six cells. The readings (the H = 0 tie and the
direction of the H = 2 gap) are reported, not required.

- **Cells and code.** This run's cells, `qwen/agent_gra/h0_native_graphiti`
  and `qwen/agent_gra/h2_native_graphiti`, record Cerebrum
  `2b9a776239b708d0c8658bc31c9c09673ba915a3` and AIOS
  `612c989a71c2b6b58fb678b58f4eebf7b6435e68`, neither `-dirty`
  (`RUN_PREFIX=pg17n`); the kernel and replicated cells, Cerebrum
  `abfd503` and AIOS `d9ca01f` (`results/pilot_v1_graphiti`'s
  provenance). Between the two, the native agents changed by the filter
  (Cerebrum `e2d4b1f`) and the harness by the V2 backend-call count
  (`a836d69`), the v2 k (`7f554d2`, not used by v1) and the redaction
  (`2b9a776`); the rest are tests and documents.
- **Data**: `pilot_v1` (`users_v1.jsonl`, 30 users, seed 20261104,
  SHA-256
  `e66af516f862ef85d3f09aee3c4c300dfe5d6224e5497c42220b8b0e86eb683f`),
  variants from the committed schedule (`pilot_v1_schedule.json`,
  version 1, SHA-256 `f4f2c8fe…`, variant seed 20261106), so each user
  gets the same variants in every cell; every trial's `input_sha256`
  equals the same user's in `results/pilot_v1_graphiti`.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. Judge `gpt-5.4:azure`, prompt version 2
  (SHA-256 `17f43dd9…`), temperature 0.0, seed 20261105. Graphiti's
  extraction: Azure gpt-4o through LiteLLM, temperature 0.0, seed
  20261105, each call tagged with the user and counted to the trial.
  Embedding: `nomic-embed-text` (Ollama).
- **Backend**: `graphiti-core` 0.31.2, the `neo4j` driver 6.4.1,
  `neo4j:5.26.33-community` (Docker container `aios-graphiti-neo4j`),
  as each cell's `config_snapshot.backend_versions` records.
- **Settings** (each cell's `config_snapshot`): k 10, budget 2,000
  tokens, threshold 0.0, compact block, `supersession` `off`, write
  barrier timeout 60,000 ms; kernel `auto_inject` and `auto_extract`
  off (the agent phase).
- **Driver**: AIOS `scripts/run_pilot_v1_graphiti.sh` with
  `PHASES=agent_gra`, `METHODS=native_graphiti`, `RUN_PREFIX=pg17n`,
  `OUTROOT=results/pilot_v1_graphiti_native_filter`, 2026-11-13 03:28
  to 04:24 EST, right after the benchmark v2 re-run
  (`results/bench_v2_smoke_s17`); one kernel (`logs/`). The agent phase
  logged `kernel_memory_ops=0`.
- **Checks after the run.** No traceback, ERROR-level record or
  write-barrier `TIMEOUT` in the kernel or run logs; no writer failed
  or retried. Backend calls, from the logs against the trials' records
  (LiteLLM logs each gpt-4o call twice): 541 (H = 0) and 411 (H = 2),
  one for one; the H = 2 cell's 12 trials with a V2 variant are counted
  in full since `a836d69`, so its backend cost is not a lower bound, as
  `results/pilot_v1_graphiti`'s H = 2 agent cells' are.
- **Graphiti's invalidations**: none. Every trial's
  `backend_invalidated_rows` is empty, as in `results/pilot_v1_graphiti`'s
  native cells: a pilot_v1 user's three writes (profile, task context,
  the conversation turn) hold no contradiction. The filter removed
  nothing, and the native cells' changes against Subtask 16's (paired
  over users: profile −0.17 and −0.07, task −0.03 and −0.03,
  integration −0.13 and −0.13 at H = 0 and 2, every 95% interval
  holding 0) are the cell's run-to-run variation.
- **Key scan and archive**: `scripts/archive_artifacts.py` found no
  configured key value or fragment of one in this directory's files
  and copied them, with `SHA256SUMS`, to
  `repo-artifacts/Cerebrum/pilot_v1_graphiti_native_filter/`.
