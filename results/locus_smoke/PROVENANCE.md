# Provenance: locus_smoke (NeurIPS Subtask 8)

30 trials per model of `kernel_shared` on Mem0 and on the in-house
provider, re-run under the memory pipeline library (type-ordered block,
Decision 1), and of the replicated-logic conditions `replicated_mem0`
and `replicated_inhouse` (AIOS `docs/REPLICATED_LOGIC.md`). A smoke, not
a verdict. Analysis: AIOS `docs/DEV_STATUS.md`, Subtask 8. Per-cell
comparison: `summary.csv` (`benchmarks/shared_memory/locus_compare.py`).

- Driver: AIOS `scripts/run_locus_smoke.sh`, one fresh kernel per
  model. It switches `memory.provider` and the kernel memory mode with
  `scripts/set_memory_mode.py` between runs and restores `config.yaml`
  at exit. The re-draw of the in-house Llama `kernel_shared` cell
  (`kernel_inhouse_redraw/`) ran from
  `scripts/run_provider_smoke.sh` with `MODELS=llama`.
- Judge `gpt-5.4:azure`, judge prompt v2 (SHA-256 `17f43dd9...`).
- Run 2026-11-03:
  - kernel_mem0: GPT-4o and Llama 14:18-15:06, Qwen 15:51-16:19;
  - kernel_inhouse: 16:20-17:45;
  - replicated_inhouse: 17:45-18:55;
  - replicated_mem0: 18:56-20:04;
  - in-house Llama re-draw: 20:05-20:31.
- Assistants: `gpt-4o:azure`, `llama3.1:8b:ollama`, `qwen2.5:7b:ollama`.
  The writers' extraction calls use the same model in every condition.
- Commits, recorded in every file: Cerebrum `408ceea`, AIOS `149aa7d`.
  `pipeline_version` `72185008bbe22f83` on every trial, kernel and
  replicated.
- Kernel memory mode (`config_snapshot`):
  - kernel cells: `auto_inject` and `auto_extract` true, provider as
    named;
  - replicated cells: both false, provider `mem0` (unused: 0
    memory-operation lines in every kernel log).
- `max_injected_memories` 10, `max_memory_tokens` 2000,
  `relevance_threshold` 0.0, from `/memory/config` in every condition.
- Embedding: `ollama` / `nomic-embed-text` / 768.
- Backends: kernel `mem0ai` 2.0.0; harness `mem0ai` 2.0.2 and
  `chromadb` 1.5.9.
- Stores: the kernel's own stores (`.mem0/`,
  `.aios_state/chroma_inhouse/`); the replicated stores are in
  `Cerebrum/.replicated_memory/ls8-<condition>/`. None is committed.
- Users are generated per trial, so kernel and replicated cells do not
  share users: the comparisons are unpaired.
- Run ids: `ls8-kmem0-<model>`, `ls8-kinh-<model>`,
  `ls8-kinh-r2-llama`, `ls8-<condition>-<model>`.
- 390 trials, 0 failed.
- In `repo-artifacts/Cerebrum/locus_smoke/`, not committed:
  - the JSON, harness logs and kernel logs (the kernel logs print the
    memory config);
  - the driver logs;
  - `rebuild_blocks.py` and its output `llama_inhouse_rebuilt_blocks.json`,
    the in-house Llama blocks rebuilt from the stores with the library.
