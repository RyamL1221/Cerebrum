# bench_v2_functional_amem: provenance

The benchmark v2 functional check of the A-MEM cells (NeurIPS
Subtask 17), on `users_v2` revision 3, under Amendments 1 to 8. Design
and pass conditions: AIOS `docs/BENCHMARK_V2.md`, "Functional check and
smoke", and Amendments 5, 6 and 8; the backend: AIOS
`docs/AMEM_BACKEND.md` and `docs/NATIVE_USAGE.md`, "native_amem".
Result: AIOS `docs/DEV_STATUS.md`, Subtask 17.

`analysis.md` and `analysis.json` are
`benchmarks.shared_memory.bench_v2_analysis`'s output on the 14 cells,
with the functional check's criteria, generated after the run with
Cerebrum `1d7d99f` (the review's fixes: the block columns' note);
it reads the same files.

- **Code**: every results file records Cerebrum
  `56f05739e0b2934d1f5df8566f82292f83a5527a` and AIOS
  `13708eeda0b1bad263d9a402a0e134d431b8cecc`, neither `-dirty`; the
  driver refuses a tracked change in either repo. Library
  `PIPELINE_VERSION`: `565e7d5b4e140752` in the four `kamem` cells,
  `138e9bd852d8be89` in the `kamem_ns` cell and the five replicated
  cells (native trials record none). Both are the same code:
  `565e7d5b…` is the hash of the commit's package, `138e9bd8…` the same
  hash with the untracked iCloud copy `aios/memory/pipeline/deletion
  2.py` (an older `deletion.py`, which no import loads; its name is not
  a module name) included. The `kamem` kernel, started at 15:59, hashed
  the package without it; every process started from 16:40 on, with
  it. Both values were recomputed after the run, from the committed
  tree and from the directory. Since AIOS `34833e7` the hash leaves such
  files out.
- **Data**: `pilot_v2` (the first 30 users of `users_v2.jsonl`
  revision 3, seed 20261108, SHA-256
  `ecd3585ffb511ce1f6277eeb78587ddffb8b7ffe3316b7df7a7ce52675ee00b8`),
  users 0 to 4. 14 cells, 70 user-trials, 0 failed:
  - kernel (`kamem`, `kernel_shared`): H = 0, H = 2, `no_delete`,
    `writer_scoped`;
  - replicated (`agent_amem`, `replicated_amem`): H = 0, H = 2,
    `no_delete`, `writer_scoped`;
  - native (`agent_amem`, `native_amem`): H = 0, H = 2, `no_delete`,
    `no_visibility`;
  - `no_supersession`: kernel (`kamem_ns`) and replicated
    (`agent_amem_ns`).

  Run ids `f17-qwen-<phase>-<method>-<condition>`.
- **Models**: assistant `qwen2.5:7b:ollama`, temperature 0.0, seed
  20261105, `num_ctx` 16384. No judge (the integration probe is
  unscored). A-MEM's LLM in every cell (`backend_extraction` true):
  `memory.backend_llm`, Azure gpt-4o through LiteLLM's synchronous
  `completion`, temperature 0.0, seed 20261105, each call tagged with
  the user and counted to the trial. Embedding: `nomic-embed-text`
  (Ollama, 768 dimensions).
- **Backend**: `agentic_memory` (WujiangXu/A-mem-sys) at
  `f303dfc71e07bdc787f4bc135d4cea328ae30e99` with `chromadb` 1.5.9,
  recorded in every cell's `config_snapshot.backend_versions`,
  installed in both venvs from Cerebrum `requirements-amem.txt`
  (`--no-deps`). One `AgenticMemorySystem` per user, in a temporary
  Chroma directory of the store's process; nothing persists across
  processes.
- **Settings** (pre-flight checked, recorded as `run_settings`): k 30,
  budget 300 tokens, threshold 0.0, compact block, session ages, write
  barrier timeout 60,000 ms, `supersession` `exclude` (`off` in the
  `_ns` phases), the kernel's tombstones in
  `.aios_state/tombstones.sqlite`. Native consumers use k 10
  (`V2_NATIVE_K`): `top_k_used` is 10 in every native probe but the H = 2
  V4 consumer's 6, which fetch 5. Kernel `auto_inject` on and
  `auto_extract` off in the kernel phases, both off in the agent
  phases. `history_db_path` null (no Mem0).
- **Driver**: AIOS `scripts/run_bench_v2.sh`, `MODE=functional`, the
  phases `kamem agent_amem kamem_ns agent_amem_ns`, `RUN_PREFIX=f17`,
  `OUTROOT=results/bench_v2_functional_amem`,
  `ARCHIVE=../repo-artifacts/Cerebrum/bench_v2_functional_amem`, under
  `caffeinate -is`, 2026-11-15 15:59 to 18:21 EST: `kamem` 15:59 to
  16:40, `agent_amem` 16:40 to 17:59, `kamem_ns` 17:59 to 18:10,
  `agent_amem_ns` 18:10 to 18:21. Its log is `driver.log` here. At the
  end it archived this folder through AIOS
  `scripts/archive_artifacts.py`: 33 files scanned, none holds a key
  value.
- **Machine**: one laptop on AC power. Qwen generated at 49 to 57 ms
  per completion token per cell (Amendment 7's split), 112 to 132 s
  per user.
- **Kernels**: one fresh kernel per phase (`logs/kernel_qwen_*`). The
  driver's end-of-phase checks found no stored conversation turn and
  no guard warning in each kernel phase's log, and 0 memory operations
  in each agent phase's log.
- **Logs**: no traceback, no ERROR- or WARNING-level record and no
  write-barrier `TIMEOUT` in any kernel, cell or driver log. No writer
  failed or retried, no write returned without a row
  (`writes_without_fact` empty in all 70 trials), and every kernel
  barrier wait drained (35 per kernel cell). The trials record 175
  backend calls per cell (174 in the replicated and native H = 2
  cells), 2,448 in all; LiteLLM logs two lines per call, and each log
  holds exactly twice its cells' count (the `kamem` kernel's 1,400 for
  four cells).
- **A-MEM**: 1,260 writes (90 per cell), each with one store-helper
  line `A-MEM evolved <n> note(s) at note <id>` (Cerebrum
  `cerebrum/utils/amem.py`), in every locus: the existing notes a
  write's evolution changed, 1.12 to 1.70 on average per cell, at most
  5, none in 13 to 30 writes per cell. No line of A-MEM's own caught
  failures (`Error analyzing content`, `Error in memory evolution`,
  `Error in process_memory`, `Error in find_related_memories`;
  `AMEM_BACKEND.md`, "Open risks", 4). 1.93 to 1.94 calls per write:
  an analysis call and an evolution call, except for a store's first
  note, which has no neighbours (175 = 2 x 90 - 5 users); 664 to 680
  prompt tokens per call, $0.10 per user.
