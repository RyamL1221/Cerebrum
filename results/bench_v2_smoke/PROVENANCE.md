# bench_v2_smoke: provenance

The benchmark v2 smoke (NeurIPS Subtask 14), on `users_v2` revision 2.
Design: AIOS `docs/BENCHMARK_V2.md`, "Functional check and smoke", with
Amendment 1 (a 500-token budget) and Amendment 2 (revision 2 of the
data, and the scorer and harness records). A smoke, not a verdict: no
rule was pre-registered. Results: AIOS `docs/DEV_STATUS.md`, Subtask 14.

- **Code**: every results file records Cerebrum
  `2bb46b824a5e3dd7278646ffcf8735284a9fa2de` and AIOS
  `208322c1bf5c8a1887e0a69df9e413dc086689de`. The driver refuses a
  tracked change in either repo. Their code is that of Cerebrum
  `9946612` and AIOS `e3cdc52`. The later commits change documents and
  records, and in AIOS `208322c` also two docstrings in
  `aios/memory/providers/mem0.py` (the module's and
  `sync_llm_from_query`'s) and comments in
  `aios/config/config.yaml.example`; the code that runs is the same
  (the AST without docstrings and the parsed YAML are equal). Library
  `PIPELINE_VERSION` `46e28207331f9284` (kernel and replicated cells;
  native trials record none).
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 2, seed 20261108, SHA-256
  `35f68c78a8373a0354c549f4e4755266b889042b76d3735963eaefbc922426de`),
  all 30 users. Six cells at H = 0: kernel, replicated and native, each
  on Mem0 and in-house. 180 user-trials, 0 failed.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. Judge v2 on the integration probe only:
  `gpt-5.4:azure` through the kernel, prompt v2 (SHA-256 `17f43dd9…`),
  temperature 0.0, seed 20261105, one call per probe, each on its
  first attempt. The judge model is not in the results files; the
  driver sets it (`run_bench_v2.sh`, `MODE=smoke`), and the kernel logs
  show 30 gpt-5.4 calls per cell. Mem0 extraction: Azure gpt-4o,
  temperature 0.0, seed 20261105, `mem0ai` 2.0.2 in both venvs, without
  its `[nlp]` extra (spaCy absent; AIOS `DEV_STATUS.md`, open decision
  1). Embedding: `nomic-embed-text` (Ollama).
- **Settings** (pre-flight checked, recorded as `run_settings`): k 10,
  budget 500 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms; kernel `auto_inject` and `auto_extract` on
  in the kernel phases, off in the agent phase.
- **Driver**: AIOS `scripts/run_bench_v2.sh` with `MODE=smoke` and
  `RUN_PREFIX=s14b`, started 2026-11-09 03:31 and finished 07:51 (EST),
  that is 08:31 to 12:51 UTC, so Mem0's extraction prompt carried one
  date in every phase (AIOS known issue 42). Run ids
  `s14b-<model>-<phase>-<method>-<condition>`. `config.yaml` was
  restored byte for byte.
- **Kernels**: one fresh kernel per phase:
  `kernel_qwen_kmem0_20261109T033201.log`,
  `kernel_qwen_kinh_20261109T042311.log` and
  `kernel_qwen_agent_20261109T045613.log`. The driver's end-of-phase
  check found 0 memory operations in the agent-phase log.
- **Logs**: no traceback and no ERROR-level record in any kernel or
  run log. Each kernel log has four error lines that LSFS (the storage
  file system; the smoke made no storage call) prints without a level:
  at startup "Failed to connect to Redis: Error 61 connecting to
  localhost:6379. Connection refused." (Redis is not run; LSFS starts
  without it), and three "Error handling file change: 'utf-8' codec
  can't decode byte 0xd9 in position 31: invalid continuation byte"
  from its file watcher on `root/`, which reads LSFS's own
  `root/chroma.sqlite3` as text. Neither is on the memory path. The
  only warnings are Mem0's "Failed to load spaCy … model: spaCy is not
  installed" (open decision 1). One Mem0 extraction call (replicated
  Mem0, user 24, 05:38:30) was retried by the OpenAI client and
  completed. No writer retried, no write barrier timed out. None of
  this run's 18 files (results, logs, analysis, driver log) holds the
  Zep or the Azure key (AIOS `e3cdc52`); the earlier attempt's kernel
  log does (below).

## Reading the records

- `config_snapshot` is the kernel's configuration. In the agent phase
  every file records provider `mem0`, the in-house cells included;
  each trial's `backend_extraction` and the method name give the cell's
  own backend.
- An independent re-score found no wrong value: the dataset's ground
  truth on all 1,080 probes, the block and answer checks, the pass
  of every scored probe, `cap_bound` and `budget_bound`, the judge
  scores, and the pass counts and integration means in
  `analysis.json`. A read-only review, each of its 36 error or
  imprecise findings checked by an adversarial verifier (its two style
  findings were not), then recounted all 991 values `analysis.json`
  held before its fixes (the readings included) with its own code and
  found none wrong; the 121 values its fixes added to the analysis
  (1,112 in all) match its counts, and an independent recount of them
  found none wrong. After a second review, of the corrected files, two
  notes in `analysis.md` changed (no value); after a third, a fourth
  and a fifth, nothing in it changed. The in-house kernel and replicated
  blocks are identical in 180 of 180 probes.
- The integration probe's block (known issue 45), the contradiction
  wording (known issue 44) and the earlier answers that carry a stale
  value: AIOS `DEV_STATUS.md`, Subtask 14, "Smoke".

## Earlier attempt

- **`s14`** (2026-11-08 20:48 to 21:34 EST), on revision 1, was stopped
  in its first cell (`qwen/kmem0/h0_kernel_shared`, 27 of 30 users)
  when a review found revision 1's problems (Amendment 2). Nothing from
  it is reported. Its run log, kernel log and driver log are in
  `repo-artifacts/Cerebrum/bench_v2_smoke/failed_attempts/s14/`. Its
  kernel log predates AIOS `e3cdc52` and holds the Zep key in clear
  (line 51, the memory configuration): redact it or rotate the key
  before sharing it.

## Files

- `analysis.md`, `analysis.json`: `bench_v2_analysis.py --no-criteria`
  output at the commit that adds this file (the functional check's
  criteria need its controls, which the smoke does not run). It holds
  the readings added after the run: trial-level exposure, deletion
  carriers, what the store kept behind each deletion probe, where the
  expected value was in each failure, contradiction per slot, earlier
  answers with a stale value, and the integration probe's block with
  its score by the base rows it holds.
- The per-trial results files, run logs, kernel logs and the driver log
  are in `repo-artifacts/Cerebrum/bench_v2_smoke/`. They are not
  committed.
