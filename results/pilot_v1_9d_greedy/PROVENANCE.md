# Provenance: pilot_v1_9d_greedy (NeurIPS Subtask 9d)

The greedy re-judge of `results/pilot_v1_9d/` (PROVENANCE there): the
same 900 stored assistant responses, re-scored with the judge at fixed
decoding. Its scores are the pilot_v1 table that replaces Subtask 9's
(AIOS `docs/DEV_STATUS.md`, Subtask 9d). Every later run uses this
judge.

- Re-judge: `python -m benchmarks.shared_memory.rejudge
  results/pilot_v1_9d/<phase>/*/results_*.json --output
  results/pilot_v1_9d_greedy/<phase> --judge-model gpt-5.4:azure`, per
  phase, 2026-11-06 01:16-01:36 EST. Judge calls only: no assistant,
  writer or memory calls (the kernel ran with kernel memory off and
  logged no memory operation). Cerebrum `be72d70`, AIOS `7cc3774`.
- Judge `gpt-5.4:azure`, judge prompt v2 (SHA-256 `17f43dd9...`, the
  same prompt: still "judge v2"), temperature 0.0, seed 20261105
  (`judge_temperature`, `judge_seed` in `experiment_metadata`; the
  source judge's are under `rejudge.source_judge_*`, null = the kernel
  default 1.0, no seed). 900 trials, none failed, each judged in one
  attempt.
- Everything else in a trial (responses, cost, latency, writer fields,
  decoding, diagnostics) is copied from the source file.
- Committed here: `cells.csv`, `paired.csv` (`pilot_report.py` on this
  root) and `judge_agreement.csv` (`python -m
  benchmarks.shared_memory.judge_compare --pilot --old
  results/pilot_v1_9d --new results/pilot_v1_9d_greedy --csv ...`:
  sampled vs greedy per cell).
- `results/pilot_v1_9d_greedy_retest/`: the `kmem0` phase re-judged a
  second time with the same greedy judge (test-retest); its agreement
  is in `retest_agreement.csv` here.
- In `repo-artifacts/Cerebrum/pilot_v1_9d_greedy/`, not committed: the
  re-judged JSON and the re-judge and kernel logs.
