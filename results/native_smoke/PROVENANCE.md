# Provenance: native_smoke (NeurIPS Subtask 6)

30 trials per model of each agent-managed condition, `native_mem0` and
`native_inhouse` (AIOS `docs/NATIVE_USAGE.md`). A smoke, not a verdict.
Analysis: AIOS `docs/DEV_STATUS.md`, Subtask 6. Per-cell numbers:
`summary.csv`.

- Driver: AIOS `scripts/run_native_smoke.sh`, `METHOD=native_mem0` then
  `METHOD=native_inhouse`, one fresh kernel per model, harness
  `run_evaluation.py --method <condition>`, judge `gpt-5.4:azure`,
  judge prompt v2 (SHA-256 `17f43dd9...a623b2ce`).
- Run 2026-11-02: native_mem0 17:12-18:39, native_inhouse 18:39-19:51.
- Assistants: `gpt-4o:azure`, `llama3.1:8b:ollama`, `qwen2.5:7b:ollama`.
  The writers' extraction LLM calls use the same model, as in the
  kernel conditions.
- Commits, recorded in every file: Cerebrum `066bc29`, AIOS `0c59a28`.
- Kernel memory mode (`config_snapshot`): `auto_inject` false,
  `auto_extract` false, provider `mem0` (unused: no memory calls).
- Mem0's internal LLM (`memory.backend_llm`, in `config_snapshot`):
  `azure_openai` / `gpt-4o`, temperature 0.1, for every assistant
  model. Its cost is not measured here (Subtask 7).
- Embedding (`config_snapshot.embedding`): `ollama` / `nomic-embed-text`
  / 768, both conditions.
- Backends: `mem0ai` 2.0.2, `chromadb` 1.5.9 (Cerebrum venv). Stores in
  `Cerebrum/.native_memory/ns6-<condition>/`, not committed.
- `k` = 10 (`max_injected_memories` from `/memory/config`).
- Run ids `ns6-<condition>-<model>`.
- 180 trials, 0 failed, agent-recorded `injection_diagnostics` on every
  trial; every kernel log has 0 memory-operation lines (the driver's
  check).
- Compared against `results/revalidation_v2/` (`kernel_shared`,
  `kernel_private`).
- JSON, harness logs and kernel logs (which print the memory config) are
  in `repo-artifacts/Cerebrum/native_smoke/`, not committed.
