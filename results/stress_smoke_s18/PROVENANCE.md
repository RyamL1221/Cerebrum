# stress_smoke_s18: provenance

The smoke of the stress dimensions (NeurIPS Subtask 18; AIOS
`docs/STRESS_DIMENSIONS.md`, "Functional check and smoke"). Result:
AIOS `docs/DEV_STATUS.md`, Subtask 18.

- **Code**: AIOS `d451801`, Cerebrum `8ef6d6f`, every cell. Driver: AIOS
  `scripts/run_stress_s18.sh`, `MODE=smoke`, run prefix `s18`, one
  attempt (2026-11-17, 06:37 to 13:30 EST), no failed trial, no resume.
- **Data**: `pilot_agents_n6`, users 0 to 29 (derived from `pilot_v2` by
  `agents_v1.py`), H = 0. Qwen (`qwen2.5:7b:ollama`), judge-free.
  In-house only, so no Azure call.
- **Cells** (12): the sequential reference `n6h0` and `n6conc` in the
  kernel, replicated and native loci (`kinh`, `agent`); `n6flood10` and
  `n6flood50` in the three, with the write quota on (`max_writes` 4,
  dedupe; `kinh_q`, `agent_q`). Every phase: session ages, the write
  barrier at 60 s, k 30, a 300-token budget, supersession `exclude`.
- **Analysis**: `analysis.md` and `analysis.json`
  (`benchmarks.shared_memory.stress_report`): the checks that must
  hold, every cell's pass rates with 95% Wilson intervals, and each
  stressed cell paired with the same users' `n6h0` (exact McNemar for
  outcomes, a t interval for paired means).
- **Archive**: `../repo-artifacts/Cerebrum/stress_smoke_s18` (the
  driver's copy at the end of the run), through
  `scripts/archive_artifacts.py`.
