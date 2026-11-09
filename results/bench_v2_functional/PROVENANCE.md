# bench_v2_functional: provenance

The benchmark v2 functional check (NeurIPS Subtask 14), on `users_v2`
revision 2. Design and pass conditions: AIOS `docs/BENCHMARK_V2.md`,
"Functional check and smoke", with Amendment 1 (a 500-token budget) and
Amendment 2 (revision 2 of the data, and the scorer and harness
records). Result: AIOS `docs/DEV_STATUS.md`, Subtask 14.

- **Code**: every results file records Cerebrum
  `1eb5ede41a9e33bca228b013d7e9dc2af60e853c` and AIOS
  `554a408ffd371a256c422b995e9d04031d222254`, neither `-dirty`. Library
  `PIPELINE_VERSION` `46e28207331f9284` (kernel and replicated cells;
  native trials record none).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 2, seed 20261108, SHA-256
  `35f68c78a8373a0354c549f4e4755266b889042b76d3735963eaefbc922426de`),
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
  budget 500 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms; kernel `auto_inject` and `auto_extract` on
  in the kernel phases, off in the agent phase.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=functional`
  and `RUN_PREFIX=f14c`, started 2026-11-08 22:49, finished
  2026-11-09 01:07 (EST), that is 03:49 to 06:07 UTC on 2026-11-09, so
  Mem0's extraction prompt carried one date in every phase (AIOS known
  issue 42). Run ids `f14c-<model>-<phase>-<method>-<condition>`.
- **Kernels**: one fresh kernel per phase:
  `kernel_qwen_kmem0_20261108T224913.log`,
  `kernel_qwen_kinh_20261108T231221.log` and
  `kernel_qwen_agent_20261108T233115.log`. The driver's end-of-phase
  check found 0 memory operations in the agent-phase log.

## Reading the records

- `config_snapshot` is the kernel's configuration. In the agent phase
  every file records provider `mem0`, the in-house cells included;
  each trial's `backend_extraction` and the method name give the cell's
  own backend.
- `visible_stored_rows` (native `cap_bound`) is the count before Cerebrum
  `9946612`, which counts the consumer's own partition and
  visibility. It is wrong in 14 native trials (84 probes): too high for
  the V2 consumer (H = 2, user 0) and one low for the V3 consumer
  (H = 2, user 4) and every `no_visibility` trial. Recomputed, it
  changes 0 of the 240 native `cap_bound` values.
- A read-only review recomputed the records with its own code and found
  no other wrong value (AIOS `DEV_STATUS.md`, Subtask 14, "Verification
  of the `f14c` records").

## Earlier attempts

- **`f14`** (2026-11-08 18:05) stopped INCOMPLETE in
  `qwen/kmem0/h2_kernel_shared`: users 0 and 1 failed the extraction
  guard (`backend_extraction_failed`). Their V5 writers replaced a base
  row with the event's fact-less stub, from which Mem0 extracted
  nothing. Fixed in Cerebrum `7d759ec` (base events carry their fields,
  and V5 writes them as JSON, as in v1). Its files are in
  `repo-artifacts/Cerebrum/bench_v2_functional/failed_attempts/f14/`.
- **`f14b`** (18:22 to 20:37) completed on revision 1 (SHA-256
  `768a37ac…`), with Cerebrum `d23dc6a` and AIOS `828fde0`, and passed
  all nine conditions. It is superseded and nothing from it is
  reported: a review then found contradictions that did not conflict,
  paraphrases that changed what a fact says, and incomplete harness
  records (Amendment 2). Its results, logs, driver log and analysis
  are in `repo-artifacts/Cerebrum/bench_v2_functional/superseded_r1/`.

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py` output at
  Cerebrum `1eb5ede` (the per-probe pass matrix, cap and budget, the
  check's criteria, kernel against replicated).
- The per-trial results files, run logs, kernel logs and the driver log
  are in `repo-artifacts/Cerebrum/bench_v2_functional/`. They are not
  committed.
