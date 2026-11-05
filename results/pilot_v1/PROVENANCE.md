# Provenance: pilot_v1 (NeurIPS Subtask 9)

The pilot_v1 re-baseline: 10 cells × 3 models × 30 users of the fixed
dataset `pilot_v1` (the first 30 users of
`benchmarks/shared_memory/data/users_v1.jsonl`, sha256 `e66af516...`,
seed 20261104), so every cell scores the same users and the comparisons
are paired. Analysis: AIOS `docs/DEV_STATUS.md`, Subtasks 9 and 9c.
Superseded by the Subtask 9d re-run (fixed decoding, shared block
renderer).

- Driver: AIOS `scripts/run_pilot_baseline.sh`, phases `kmem0`
  (kernel memory on, Mem0), `kinh` (kernel memory on, in-house) and
  `agent` (kernel memory off: replicated, native, naive_concat,
  vanilla_rag), one fresh kernel per phase and model, `config.yaml`
  restored at exit. Run 2026-11-04 14:46-21:46 EST.
- Judge `gpt-5.4:azure`, judge prompt v2 (SHA-256 `17f43dd9...`).
- Assistants and writers: `gpt-4o:azure`, `qwen2.5:7b:ollama`
  (`845dbda0ea48`), `llama3.1:8b:ollama` (`46e0c10c039e`); Ollama
  0.40.11. Assistant decoding: the kernel defaults (temperature 1.0,
  max_tokens 1000, no seed).
- Commits recorded in every file: Cerebrum `f9cf426-dirty`, AIOS
  `c953fad-dirty`; the uncommitted Subtask 9 work is the commit tagged
  `neurips-subtask-09` in both repos. `pipeline_version`
  `72185008bbe22f83` on every kernel and replicated trial.
- Memory config (`config_snapshot`): `max_injected_memories` 10,
  `max_memory_tokens` 2000, `relevance_threshold` 0.0; embedding
  `ollama` / `nomic-embed-text` / 768; Mem0 `infer` true with
  `backend_llm` Azure gpt-4o, temperature 0.1 (`backend_extraction`
  true on every Mem0 cell).
- Backends: kernel `mem0ai` 2.0.0; harness `mem0ai` 2.0.2, `chromadb`
  1.5.9 (pinned to one version in Subtask 9d).
- Run ids `p9-<phase>-<method>-<model>`. Stores: kernel `.mem0/` and
  `.aios_state/chroma_inhouse/`; agent stores
  `Cerebrum/.native_memory/p9/`, `.replicated_memory/p9/`. None
  committed.
- 900 trials; 3 failed, all Llama writer failures after two retries
  (stored nothing, not judged).
- Committed here: `cells.csv`, `paired.csv`
  (`python -m benchmarks.shared_memory.pilot_report results/pilot_v1
  --csv results/pilot_v1/paired.csv --cells-csv results/pilot_v1/cells.csv`).
- In `repo-artifacts/Cerebrum/pilot_v1/`, not committed: the results
  JSON, the harness and kernel logs (the kernel logs print the memory
  config) and the driver log; `repo-artifacts/Cerebrum/s9c/`: the
  Subtask 9c scripts and outputs.
