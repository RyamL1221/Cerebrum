# Provenance: provider_smoke (NeurIPS Subtask 5)

30 `kernel_shared` trials per model on each conforming memory backend,
after the provider contract (AIOS `docs/PROVIDER_CONTRACT.md`). A smoke,
not a verdict: 30 trials per cell is noisy. Analysis: AIOS
`docs/DEV_STATUS.md`, Subtask 5. Per-cell numbers: `summary.csv`.

- Driver: AIOS `scripts/run_provider_smoke.sh`, `PROVIDER=mem0` then
  `PROVIDER=in-house`, one fresh kernel per model, harness
  `run_evaluation.py --method kernel_shared --provider <name>`, judge
  `gpt-5.4:azure`, judge prompt v2 (SHA-256 `17f43dd9...a623b2ce`).
- Assistants: `gpt-4o:azure`, `llama3.1:8b:ollama`, `qwen2.5:7b:ollama`.
  Each cell generates its own synthetic users.
- Run ids `ps5-mem0-<model>` and `ps5-in-house-<model>`.
- Commits, recorded in every file: Cerebrum `c3dc42e`; AIOS `d7d8682`
  (Mem0, 2026-11-02 13:30-14:54) and `9f06018` (in-house, 14:57-16:10).
  The two AIOS commits differ only in `scripts/` (driver and smoke
  fixes), not kernel code.
- Embedding (both backends, from `memory.embedding`, recorded in each
  file's `config_snapshot.embedding`): `ollama` / `nomic-embed-text` /
  768 dimensions.
- Kernel memory settings (`config_snapshot`): `relevance_threshold` 0.0,
  `max_injected_memories` 10, `max_memory_tokens` 2000.
- Baseline compared against: `results/revalidation_v2/` (judge prompt v2).
- 180 trials, 0 failed, `injection_diagnostics` on every trial.
- JSON, harness logs and kernel logs (which print the memory config) are
  in `repo-artifacts/Cerebrum/provider_smoke/`, not committed.
