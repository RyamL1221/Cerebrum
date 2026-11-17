# scheduler_check_s18: provenance

The event-driven scheduler's before/after check (NeurIPS Subtask 18;
AIOS `docs/STRESS_DIMENSIONS.md`, "Kernel and library additions" 3).
Result: AIOS `docs/DEV_STATUS.md`, Subtask 18.

- **Code**: before, AIOS `7053e0a` (the FIFO scheduler sleeping
  `batch_interval`, 1 s, before each collection), run from a temporary
  git worktree of that commit; after, AIOS `c389539` (the event-driven
  scheduler). The harness in both: Cerebrum `d876f0f`. Both kernels
  read one `config.yaml`, identical byte for byte: in-house, kernel
  memory on (`auto_inject` and `auto_extract`), k 10, a 2,000-token
  budget, no session ages, supersession off (pilot_v1's settings).
- **Data**: `pilot_v1`, users 0 to 9, H = 0, `kernel_shared`, Qwen
  (`qwen2.5:7b:ollama`, temperature 0.0, seed 20261105). Run ids
  `s18sched-before2` and `s18sched-after`. 20 trials, 0 failed.
- **Judge**: both runs judge-free, then judged in one pass, one after
  the other within two minutes (`rejudge.py`, `gpt-5.4:azure`, judge
  prompt v2, greedy decoding, the fixed seed): `judged/`.
- **Result** (`analysis.json`): identical blocks, writes and answers for
  all 10 users. `schedule_wait_ms` median 845 ms (409 to 925) before,
  1.0 ms (0.7 to 3.4) after; the kernel's overhead median 906 ms before,
  77 ms after. The scores of the identical answers, judged in one pass,
  agree for 5 of 10 profile, 10 of 10 task and 6 of 10 integration
  scores (means 2.8 / 5.0 / 2.7 before, 2.9 / 5.0 / 3.1 after): the
  judge's own variation (known issue 24), not the scheduler's.
- **Excluded attempts**: the first "before" run (run id
  `s18sched-before`, judged) failed every trial at the judge: Azure
  refused the network ("Access denied due to Virtual Network/Firewall
  rules") after the router's restart. Its judge-free re-run reused the
  run id, so it read the first attempt's rows (the stores are not reset
  between runs, known issue 36): its blocks held the first attempt's
  conversation turns. Neither is used or archived.
- **Archive**: `../repo-artifacts/Cerebrum/scheduler_check_s18` (the
  results, the harness, re-judge and kernel logs), through
  `scripts/archive_artifacts.py`.
