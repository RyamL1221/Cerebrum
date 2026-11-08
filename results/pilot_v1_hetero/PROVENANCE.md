# pilot_v1_hetero: provenance

The pre-registered locus × heterogeneity pilot (NeurIPS Subtask 11).
Design, rule and result: AIOS `docs/PILOT.md`.

- **Code**: tag `pilot-v1-code` in both repos. Every results file
  records Cerebrum `7fc576923beb5800d200968cbe62a91eee62f67e` and AIOS
  `ef05d66561a880727598da0f7b46e5894f2c9045`, neither `-dirty`.
- **Schedule**: `benchmarks/shared_memory/data/pilot_v1_schedule.json`,
  SHA-256 `f4f2c8fe6fc0bef8857848df15cc365a44652672d79833570c1c44c989e4c10e`,
  recorded in every results file.
- **Data**: dataset `pilot_v1` (30 users), one cell per (model, locus,
  backend, H). 36 cells, 1,080 trials, 0 failed in the files kept.
- **Models**: assistant `qwen2.5:7b:ollama`, then `gpt-4o:azure`.
  Judge: `gpt-5.4:azure`, prompt v2, greedy. Decoding: temperature 0.0,
  seed 20261105. Mem0 extraction on Azure gpt-4o at the same settings.
- **Driver**: AIOS `scripts/run_pilot_v1.sh`, started 2026-11-07 17:23,
  finished 2026-11-08 02:45 (EST). Run ids `pv1-<model>-<phase>-<method>-h<H>`.
- **Kernels**: one fresh kernel per model per phase (plus the two
  noted below). The agent-phase kernel logs show 0 memory operations:
  `kernel_qwen_agent_20261107T194921.log` (checked by hand, since the
  driver stopped before its end-of-phase check),
  `kernel_qwen_agent_rerun_20261107T210732.log`,
  `kernel_qwen_agent_20261107T212825.log` and
  `kernel_gpt4o_agent_20261108T011346.log`.

## Re-run

- `qwen/agent/h0_native_mem0` was re-run whole. In the first attempt
  (2026-11-07 20:32-21:05), Azure refused connections three times
  between 20:35 and 20:50. Mem0 logged "LLM extraction failed" and
  stored nothing for trial 5. The Subtask 10 guard failed that trial
  (`backend_extraction_failed: stored no rows: profile_agent,
  task_agent`), and the driver stopped with INCOMPLETE. The other 29
  trials completed.
- The re-run (21:07) used the driver's command, environment and
  kernel set-up (kernel memory off, its own kernel log, 0 memory
  operations, strict done check), with run id
  `pv1-qwen-agent-native_mem0-h0-r1`. The native store is shared and
  never reset, and user ids include the run id. Under the same run id,
  the re-run would have found the first attempt's rows for the other
  29 users.
- The first attempt's results and log are in
  `repo-artifacts/Cerebrum/pilot_v1_hetero/failed_attempts/`.
- After the re-run passed, the driver was restarted and resumed at
  `qwen/agent/h0_native_inhouse`. Its earlier cells were skipped as
  done.

## Files

- `analysis.md`, `analysis.json`: `pilot_analysis.py` output (cells,
  gaps, DiD, judge-free rates, H = 1 by variant, verdict).
- `cells.csv`, `gaps.csv`, `variants_h1.csv`: the same tables.
- `gap_vs_h.svg`: the draft headline figure (`pilot_figure.py`).
- Per-trial results and logs: `repo-artifacts/Cerebrum/pilot_v1_hetero/`
  (the results tree is gitignored; kernel logs are never committed).

Re-create the analysis:

    python -m benchmarks.shared_memory.pilot_analysis results/pilot_v1_hetero \
        --markdown results/pilot_v1_hetero/analysis.md \
        --json results/pilot_v1_hetero/analysis.json \
        --csv-dir results/pilot_v1_hetero
    python -m benchmarks.shared_memory.pilot_figure results/pilot_v1_hetero \
        --output results/pilot_v1_hetero/gap_vs_h.svg
