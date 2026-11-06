# Provenance: pilot_v1_9d (NeurIPS Subtask 9d)

The pilot_v1 re-baseline re-run under fixed decoding and the shared
compact memory block: 10 cells × 3 models × 30 users of the fixed
dataset `pilot_v1` (the first 30 users of
`benchmarks/shared_memory/data/users_v1.jsonl`, sha256 `e66af516...`,
seed 20261104), paired on the same users in every cell. These files
hold the scores of the **sampled** judge the run used; the table that
replaces Subtask 9's comes from the greedy re-judge of these responses,
`results/pilot_v1_9d_greedy/` (PROVENANCE there). Analysis: AIOS
`docs/DEV_STATUS.md`, Subtask 9d.

- Driver: AIOS `scripts/run_pilot_baseline.sh`, phases `kmem0`
  (kernel memory on, Mem0), `kinh` (kernel memory on, in-house) and
  `agent` (kernel memory off: replicated, native, naive_concat,
  vanilla_rag), one fresh kernel per phase and model, `config.yaml`
  restored at exit. Run 2026-11-05 17:06 to 2026-11-06 00:41 EST, run
  ids `p9d-<phase>-<method>-<model>`.
- Re-run cell: `kmem0/qwen_kernel_shared`. During its first run
  (17:22-17:24) the Cerebrum test suite was run against the live kernel
  and sent writes and searches for a test user (its own collection, no
  pilot user touched) while trials 0-2 ran. That cell was moved to
  `repo-artifacts/Cerebrum/pilot_v1_9d_contaminated/` and re-run
  2026-11-06 00:43-01:09 with the same code, run id
  `p9dr-kmem0-kernel_shared-qwen` (a new prefix, since user ids carry
  the run id).
- Assistant and writer decoding: temperature 0.0, seed 20261105, on
  every assistant and writer call in every condition
  (`experiment_metadata.decoding`; each trial's `decoding` is what the
  kernel or replicated agent applied). Azure gpt-4o treats the seed as
  best effort. max_tokens 1000 (kernel default).
- Judge `gpt-5.4:azure`, judge prompt v2 (SHA-256 `17f43dd9...`),
  sampled at the kernel default (temperature 1.0, no seed; the files
  record no `judge_temperature`).
- Memory block: `block_format` compact, `block_recency` false (kernel
  and replicated trials record `block_format`, native trials
  `native`); `pipeline_version` `fcd25aec0f9978da` on every kernel and
  replicated trial.
- Assistants and writers: `gpt-4o:azure`, `qwen2.5:7b:ollama`
  (`845dbda0ea48`), `llama3.1:8b:ollama` (`46e0c10c039e`); Ollama
  0.40.11.
- Commits recorded in every file: Cerebrum `14b3c67`; AIOS `7cc3774`
  (`7cc3774-dirty` on 27 cells: an uncommitted `docs/MODELS.md` edit,
  no code). Both are tagged `neurips-subtask-09d` with the follow-up.
- Memory config (`config_snapshot`): `max_injected_memories` 10,
  `max_memory_tokens` 2000, `relevance_threshold` 0.0; embedding
  `ollama` / `nomic-embed-text` / 768; Mem0 `infer` true with
  `backend_llm` Azure gpt-4o, temperature 0.1, no seed (Mem0's own
  extraction is not under the fixed decoding).
- Backends: `mem0ai` 2.0.2 in both venvs (pinned in both
  `requirements.txt`); `chromadb` 1.5.9 (harness), 1.5.8 (kernel).
- Stores: kernel `.mem0/` and `.aios_state/chroma_inhouse/`; agent
  stores `Cerebrum/.native_memory/p9d/`, `.replicated_memory/p9d/`.
  None committed.
- 900 trials, none failed; no writer failed or retried in any cell.
- Committed here: `cells.csv`, `paired.csv`
  (`python -m benchmarks.shared_memory.pilot_report results/pilot_v1_9d
  --csv results/pilot_v1_9d/paired.csv --cells-csv
  results/pilot_v1_9d/cells.csv`).
- In `repo-artifacts/Cerebrum/pilot_v1_9d/`, not committed: the results
  JSON, the harness and kernel logs (the kernel logs print the memory
  config) and the driver logs.
