# stress_functional_f18b: provenance

The functional check of the stress dimensions (NeurIPS Subtask 18; AIOS
`docs/STRESS_DIMENSIONS.md`, "Functional check and smoke"). Result: AIOS
`docs/DEV_STATUS.md`, Subtask 18.

- **Code**: AIOS `d451801`, Cerebrum `8ef6d6f` (the review's fixes), for
  every cell. Driver: AIOS `scripts/run_stress_s18.sh`, `MODE=functional`.
- **Data**: `pilot_agents_n3`, `pilot_agents_n6` and `pilot_agents_n12`
  (users 0 to 4; the load cells users 0 to 15), derived from `pilot_v2`
  by `agents_v1.py`. Qwen (`qwen2.5:7b:ollama`), judge-free. Every
  phase: session ages, the write barrier at 60 s, k 30, a 300-token
  budget, supersession `exclude`; the write quota off, and on
  (`max_writes` 4, dedupe) in the flood phases (`kinh_q`, `kmem0_q`,
  `agent_q`). Mem0's extraction and native Mem0: Azure `gpt-4o`.
- **Cells**: 72, each with its results file; the in-house and Mem0
  kernel cells (agent counts N = 3, 6, 12 at H = 0 and 2; `n6conc`;
  `n6wrong_user`; `n6missing_metadata`; `n6load1`, `n6load4`,
  `n6load16`), the same nine non-load conditions in the four
  agent-managed cells (replicated and native, in-house and Mem0), and
  `n6flood10` and `n6flood50` in all six.
- **Attempts** (`driver.log`; each a new run prefix, known issue 36):
  - `f18b`, from 2026-11-16 18:17 EST: stopped at the kernel Mem0 cell
    `n12h0`, user 4 failed: Mem0 stored no row for `u004-e17` ("Issues
    are sent to Rollbar.", logged "Mem0 extracted no facts"). Kept in
    `failed_attempts/kmem0_n12h0_kernel_shared_f18b` and
    `logs/qwen_kmem0_kernel_shared_n12h0.failed_f18b.log`.
  - `f18c`, from 20:53: that cell passed. Stopped at 21:15 before the
    laptop's lid closed: the kernel Mem0 cell `n6conc`, in flight, was
    killed (its log `...n6conc.stopped_f18c.log`; no results).
  - `f18d`, from 22:55 (on AC power again): stopped at the replicated
    Mem0 cell `n12h0`, user 0 failed on `u000-e05` (the same sentence).
    Kept in `failed_attempts/agent_n12h0_replicated_mem0_f18d` and
    `logs/qwen_agent_replicated_mem0_n12h0.failed_f18d.log`.
  - `f18e`, from 02:29 on 2026-11-17: that cell failed again the same
    way; kept in place as the cell's result. Not retried further.
  - `f18r1` to `f18r31`, 02:39 to 06:36: the 31 remaining cells, one
    driver invocation each, so a failed cell stopped none of the others.
- **Excluded**: the first attempt, `f18` (2026-11-16 from 17:03, on
  Cerebrum `d876f0f` and AIOS `c389539`), stopped after about 30
  minutes for the review's fixes; not used and not archived.
- **Analysis**: `analysis.md` and `analysis.json`
  (`benchmarks.shared_memory.stress_report`).
- **Archive**: `../repo-artifacts/Cerebrum/stress_functional_f18b`,
  through `scripts/archive_artifacts.py`.
