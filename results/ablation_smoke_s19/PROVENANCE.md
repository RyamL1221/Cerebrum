# ablation_smoke_s19: provenance

The smoke of the kernel ablation switches (NeurIPS Subtask 19; AIOS
`docs/ABLATION.md`, "Checks"): the four switches whose measurement is
judge-free and whose mechanism is not definitional. Result: AIOS
`docs/DEV_STATUS.md`, Subtask 19.

- **Code**: AIOS `64bbbee`, Cerebrum `bb7e845`, every cell. Driver: AIOS
  `scripts/run_ablation.sh`, `MODE=smoke`, run prefix `s19`, one attempt
  (2026-11-18 15:16 to 2026-11-19 00:08 EST), no failed trial, no
  resume.
- **Data**: `pilot_agents_n6`, users 0 to 29 (derived from `pilot_v2` by
  `agents_v1.py`), N = 6. Qwen (`qwen2.5:7b:ollama`), judge-free.
  In-house only, so no Azure call.
- **Cells** (10, 300 trials): the full kernel (`kinh`) under `n6conc`,
  `n6wrong_user`, `n6h0`, `n6flood10` and `n6flood50`; `barrier: off`
  under `n6conc`, `identity: claim` under `n6wrong_user`, `quota: off`
  under both floods and `forget_scope: writer` under `n6h0`. Every
  kernel: session ages, the write barrier at 60 s, k 30, a 300-token
  budget, supersession `exclude`; the write quota on (`max_writes` 4,
  dedupe) for the floods and off for the others, each on a fresh kernel.
- **Kernel log checks** (`driver.log`): no probe turn stored; the
  tombstone guard's warnings 0 in every phase but `kinh_barrier` (46:
  rows a read met after a forget recorded its tombstone and before it
  deleted them).
- **Analysis**: `analysis.md`, `analysis.json` and `contribution.svg`
  (`benchmarks.shared_memory.ablation_report`).
- **Archive**: `../repo-artifacts/Cerebrum/ablation_smoke_s19` (the
  driver's copy at the end of the run), through
  `scripts/archive_artifacts.py`.
