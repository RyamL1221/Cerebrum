# Provenance: revalidation_v2

The 900 responses of `results/revalidation/` (Subtask 3), re-scored with
judge prompt version 2 in Subtask 4 of the NeurIPS plan. Analysis and
comparison: AIOS `docs/REVALIDATION.md`, "Judge prompt v2".

- Command, run 2026-11-02 11:35-11:48 against a kernel on AIOS
  `cb6df45` plus the Subtask 4 working tree:

      python -m benchmarks.shared_memory.rejudge \
          results/revalidation/{gpt4o,llama,qwen}_{kernel_shared,mem0_default}/results_*.json \
          --output results/revalidation_v2 --judge-model gpt-5.4:azure --workers 6

- Harness: Cerebrum `63de853` plus the uncommitted Subtask 4 changes
  (recorded as `63de853-dirty` in each file's `rejudge.harness_commit`).
  `judge.py`, `rejudge.py` and `models.py` were committed unchanged from
  what ran, in the Subtask 4 commit (tag `neurips-subtask-04`).
- Judge prompt version 2, SHA-256
  `17f43dd91cc76aed0fc97616475958791cf8718aaee90604723e9246a623b2ce`,
  recorded in every file's `experiment_metadata`.
- Each file's `git_commit` / `kernel_git_commit` are those the responses
  were produced on (Subtask 3); `rejudge.source` names the source file.
- Directories use the current name, `kernel_private`; the sources use
  the old one, `mem0_default`.
- 900 trials, 0 failed. `memory_counts` and `written_memories` are the
  stored Subtask 3 values (empty: the capture bug fixed in Subtask 4).
- Committed here: `judge_comparison.csv` (v1 against v2 per cell),
  `summary.csv` (v2 against the workshop, by `revalidate.py`). The JSON
  and the re-judge log are in `repo-artifacts/Cerebrum/revalidation_v2/`;
  the kernel log, which prints the config, in
  `repo-artifacts/AIOS/subtask04/`.
