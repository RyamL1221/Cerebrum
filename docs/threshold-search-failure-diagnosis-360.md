# Failure diagnosis report — full 360-trial threshold search (`full-search-360`)

Watched the full detached search (`run_full_search(search_run_id="full-search-360")`)
to completion and diagnosed trial failures, with particular attention to the
markdown-fence JSON-parsing gap (fixed for the dry runs in `synth.py`, never
before exercised at 360-trial scale on `qwen2.5:7b` / `llama3.1:8b`).

## Headline result

**45/45 candidates completed. 360/360 trials attempted. 0 failed trials.**

- Every candidate wrote a durable record to `attempts.jsonl` (45 lines, all
  unique — 15 per model, no duplicates).
- Every candidate's `results_kernel_shared_tuned.json` reports
  `num_trials_failed = 0`.
- **The fence-parsing bug did NOT reappear at scale — on any model.** No
  stop-and-report condition was triggered.
- No modifications were made to `threshold_search.py` or `synth.py` (diagnosis
  was read-only; monitoring used a separate throwaway scanner).

Because there were zero failed trials, there are **no `error_message` values to
quote or classify** — the failure taxonomy below is reported as all-zero counts.

## Running tally — total / failed, by model and pattern

| Model | Candidates | Trials | Failed | Fence bug | Other JSON-parse | Network/timeout | Unclassified |
|-------|-----------:|-------:|-------:|----------:|-----------------:|----------------:|-------------:|
| gpt-4o (azure) | 15/15 | 120 | **0** | 0 | 0 | 0 | 0 |
| llama3.1:8b (ollama) | 15/15 | 120 | **0** | 0 | 0 | 0 | 0 |
| qwen2.5:7b (ollama) | 15/15 | 120 | **0** | 0 | 0 | 0 | 0 |
| **Total** | **45/45** | **360** | **0** | **0** | **0** | **0** | **0** |

## How this was verified (evidence, not assumption)

- **Per-candidate scan.** A read-only scanner
  (`benchmarks/shared_memory/_failure_scan.py`, temporary) opened every
  `results/threshold_search_full/*/results_kernel_shared_tuned.json`, walked
  `conditions[].trials[]`, and counted `failed == True`. It also matched each
  failed trial's `error_message` against the known fence signature
  (`"Expecting value: line 1 column 1 (char 0)"`) and other patterns, and would
  have printed `*** KNOWN_FENCE_BUG DETECTED AT SCALE — STOP AND REPORT ***` on
  any hit. It never fired: final scan reported `total failed: 0`.
- **Fence bug specifically.** The historical failure mode was 3/4 gpt-4o dry-run
  trials dying during synthetic-data generation with
  `Expecting value: line 1 column 1 (char 0)` (bare `json.loads` on
  markdown-fenced JSON). The fix is `synth.py:60` `_loads_json_tolerant`
  (try bare `json.loads`, else parse first-`{`..last-`}`, else re-raise). At 360
  trials — 120 on gpt-4o (the model that originally exhibited it) and 120 each
  on llama3.1:8b / qwen2.5:7b (never scale-tested before) — the bug did not
  recur. The fix holds at scale.
- **Live monitoring.** The detached run was polled continuously from launch to
  completion (process liveness, `attempts.jsonl` growth, the driver log's
  `Search step` / `Winner for` lines, and the kernel's per-trial
  `..._t<index>` memory-write markers). At several points a candidate that ran
  longer than average was explicitly checked (subprocess elapsed time + latest
  trial index + kernel-log freshness) and confirmed to be progressing, not
  stalled. No stall or crash occurred; the proven resume path was never needed.

## Run facts

- **Wall-clock:** 2026-09-06 11:33:33 → 17:36:16 ≈ **6h 3m** (single detached
  process, PID 41384, `nohup`+`disown`).
- **Per-model completion:** gpt-4o 12:34:48, llama3.1:8b 15:01:06,
  qwen2.5:7b 17:36:16.
- **Pace note (informational, not a failure):** the ~6h wall-clock exceeded the
  earlier ~3.1h estimate. The two local models ran ~9–16 min per 8-trial
  candidate — slower than the dry-run's assistant-only 18.18s/trial figure —
  because each trial runs the full 3-agent pipeline (Profile + Task + Assistant)
  entirely on the local model, plus a GPT-5.4 judge and a per-candidate kernel
  restart. gpt-4o (cloud assistant) ran ~4 min/candidate. This is a timing
  observation only; it did not cause any trial failure.
- **Completion was clean:** the process exited on its own, the last candidate's
  kernel was terminated, port 8000 freed, and `write_final_overrides` wrote the
  9 winners to the kernel `config.yaml` in one final write.

## Winners (context, produced by the same run)

| Model | novelty | similarity | redundancy |
|-------|--------:|-----------:|-----------:|
| gpt-4o | 0.7 | 0.8 | 0.5 |
| llama3.1:8b | 0.6 | 0.5 | 0.5 |
| qwen2.5:7b | 0.6 | 0.9 | 0.7 |

## Bottom line vs. acceptance criteria

- **45/45 candidates in `attempts.jsonl`** — met (none missing/irrecoverable).
- **360 trials attempted, per-trial failures reported explicitly** — met: **0
  failures**, so every failure bucket is zero; there are no `error_message`s to
  quote.
- **Fence bug / structural issue reappearance** — did not occur; the
  stop-and-report path was armed (scanner flag) but never triggered.
- **No modifications to `threshold_search.py` or `synth.py`** — honored.
