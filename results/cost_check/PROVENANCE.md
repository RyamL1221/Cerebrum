# Provenance: cost_check (NeurIPS Subtask 7)

10 GPT-4o trials each of `kernel_shared` and `native_mem0`, run to check
the cost instrumentation, not to compare conditions. Analysis: AIOS
`docs/DEV_STATUS.md`, Subtask 7. Per-cell means: `summary.csv`
(`python -m benchmarks.shared_memory.cost results/cost_check --csv
results/cost_check/summary.csv`).

- Driver: AIOS `scripts/run_cost_check.sh` (`METHOD=kernel_shared`, then
  `METHOD=native_mem0`), one fresh kernel per condition, harness
  `run_evaluation.py --method <condition> --assistant-model gpt-4o:azure`,
  judge `gpt-5.4:azure`, judge prompt v2. Per-trial check: AIOS
  `scripts/cost_check.py` (0 problems in both cells).
- Run 2026-11-03: kernel_shared 13:18-13:23, native_mem0 13:23-13:29.
- Commits: the files record Cerebrum `52330ff-dirty` and AIOS
  `4d89763-dirty`. The dirty trees are the code committed unchanged as
  Cerebrum `f0e18ca` and AIOS `5f61bff`; only `docs/NATIVE_USAGE.md`
  changed between the runs and those commits.
- Kernel memory mode (`config_snapshot`): kernel_shared `auto_inject` /
  `auto_extract` true; native_mem0 both false (0 memory-operation lines
  in its kernel log). Provider `mem0`.
- Mem0's internal LLM (`memory.backend_llm`): gpt-4o on Azure, reached
  through Mem0's `litellm` provider as `azure/gpt-4o`. Embedding
  `ollama` / `nomic-embed-text` / 768.
- Prices: `benchmarks/shared_memory/prices.yaml` as of 2026-11-03
  (gpt-4o 2.50 / 10.00 USD per 1M input / output tokens; local models 0).
- Run ids `cc7-kernel_shared`, `cc7-native_mem0`. Native store:
  `Cerebrum/.native_memory/cc7-native_mem0/`, not committed.
- JSON, harness logs, kernel logs (which print the memory config) and
  the checker's output are in `repo-artifacts/Cerebrum/cost_check/`, not
  committed.
