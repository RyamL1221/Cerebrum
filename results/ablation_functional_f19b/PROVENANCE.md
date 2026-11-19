# ablation_functional_f19b: provenance

The functional check of the kernel ablation switches (NeurIPS Subtask
19; AIOS `docs/ABLATION.md`, "Checks"). Result: AIOS
`docs/DEV_STATUS.md`, Subtask 19.

- **Code**: AIOS `64bbbee`, Cerebrum `bb7e845` (the review's fixes), for
  every cell. Driver: AIOS `scripts/run_ablation.sh`, `MODE=functional`,
  run prefix `f19b`, one attempt (2026-11-18, 11:58 to 15:14 EST), no
  failed trial, no resume.
- **Data**: `pilot_agents_n6`, users 0 to 4 (derived from `pilot_v2` by
  `agents_v1.py`), N = 6. Qwen (`qwen2.5:7b:ollama`), judge-free.
  In-house only, so no Azure call.
- **Phases**: `kinh` (the full kernel, every condition once: `n6conc`,
  `n6wrong_user`, `n6v2`, `n6v3`, `n6h0`, `n6v4`, `n6flood10`,
  `n6flood50`), `kinh_<switch>` for each of the eleven switches under
  its row's conditions, and `agent` (the replicated in-house V4 cell,
  for `consumer_config`): 22 cells, 110 trials. Every kernel: session
  ages, the write barrier at 60 s, k 30, a 300-token budget,
  supersession `exclude`; the write quota on (`max_writes` 4, dedupe)
  for the flood conditions and off for the others, each on a fresh
  kernel.
- **Excluded**: the first attempt, `f19` (from 2026-11-18 11:24, on AIOS
  `894ee06` and Cerebrum `440e705`), stopped at 11:43 in its fourth
  full-kernel cell (`n6v3`; the driver logged it FAILED), three cells
  finished, for the review's fixes; left in
  `results/ablation_functional_f19`, not used and not archived.
- **Analysis**: `analysis.md`, `analysis.json` and `contribution.svg`
  (`benchmarks.shared_memory.ablation_report`).
- **Archive**: `../repo-artifacts/Cerebrum/ablation_functional_f19b`
  (the driver's copy at the end of the run), through
  `scripts/archive_artifacts.py`.
