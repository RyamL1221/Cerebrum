# Provenance: heterogeneity_check (NeurIPS Subtask 10)

The functional check of the heterogeneity variants (AIOS
`docs/HETEROGENEITY.md`, "Functional verification"). It is not a scored
run: every cell ran with `--no-judge` (`judged: false`), and none of the
90 trials has a score. Its results are judge-free measures only.

- Driver: AIOS `scripts/run_heterogeneity_check.sh`, which runs every
  locus x backend x H on `pilot_v1`, first 5 users, assistant
  `qwen2.5:7b:ollama`, `--variant-seed 20261106` (catalog version 1).
  It has three phases, each with a fresh kernel:
  - `kmem0`: Mem0 with infer=True, kernel memory on, `kernel_shared`.
  - `kinh`: in-house, `kernel_shared`.
  - `agent`: kernel memory off, `replicated_mem0`,
    `replicated_inhouse`, `native_mem0`, `native_inhouse`.

  The agent-phase kernel logged 0 memory operations
  (`kernel_memory_ops=0`). Mem0's extraction ran on Azure gpt-4o at
  temperature 0.0 with seed 20261105.
- Cells and code. Each results file records `git_commit` and
  `kernel_git_commit`.
  - `kmem0`, `kinh` and agent H0 `replicated_*` ran 2026-11-06,
    15:41-16:08 EST (run prefix `h10`).
    - `kmem0/h0` ran on the uncommitted tree that became Cerebrum
      `268e270` / AIOS `709d0b4`, so it is recorded as dirty. It is a
      reference cell with no variant.
    - The two `replicated` H0 cells are recorded as dirty because only
      `heterogeneity_report.py` was uncommitted (committed as
      `3c6b11d`), and it is not used by a run.
    - Everything else on 2026-11-06 ran at Cerebrum `268e270`, AIOS
      `709d0b4`.
  - The remaining 10 agent cells ran 2026-11-07, 15:33-16:03 EST (run
    prefix `h10s`). They used Cerebrum `04631f6` (with the
    `backend_extraction_failed` guard) and AIOS `da25e2c`.
- Excluded, kept in `repo-artifacts/Cerebrum/heterogeneity_check_interrupted/`:
  - A native Mem0 H0 cell cut off by a laptop shutdown.
  - A native Mem0 H0 cell run from a network that Azure refused. Mem0
    swallowed the errors: 0 backend LLM calls and 0 injected rows, yet
    every trial "completed". This is why the guard exists.
- The cells from before the guard pass it after the fact: every Mem0
  trial recorded 2 backend LLM calls (kernel) or 3 (replicated), and
  none failed.
- Committed here:
  - `trials.csv` and `table.md`, from `python -m
    benchmarks.shared_memory.heterogeneity_report
    results/heterogeneity_check --csv ... --markdown ...`. Each H > 0
    trial is paired with the same trial index at H = 0 in its cell.
  - This file.
- The results JSON and the logs are in
  `repo-artifacts/Cerebrum/heterogeneity_check/`; `h10s_driver.log` is
  under `logs/`.
