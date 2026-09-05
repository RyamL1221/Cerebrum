# Threshold Search Dry Run — Full Trace (1 model, 1 threshold, 2 candidates, 2 trials)

**Track:** threshold-search
**Goal:** First real, non-mocked end-to-end run of the whole chain at minimal
scale — config edit → restart → gating verify → trial subprocess → score parse
→ winner selection → incremental progress log — plus real timing for the
Subtask 9 cost estimate.

- **Model:** `qwen2.5:7b` (ollama) — chosen for speed/cost, consistent with
  prior smoke tests.
- **Threshold:** `novelty_threshold` (first in the coordinate order).
- **Candidates:** `0.5`, `0.6` (a real subset of the 5-value grid).
- **Trials per candidate:** `2` (dry-run scale, not the real 8) → **4 real
  trials total**.
- **search_run_id:** `dryrun-20260905` (real progress log, not a temp dir).
- **Judge:** local `qwen2.5:7b:ollama` (cheap for the dry run; the real search
  uses `gpt-5.4:azure` per `DEFAULT_SEARCH_JUDGE_MODEL`).

## Entry point used, and why

`search_one_threshold(...)` was called **directly** (not `run_full_search`).
Rationale: the scope is a single threshold; `run_full_search`/`search_one_model`
would run all three thresholds (novelty → similarity → redundancy). Calling the
one primitive keeps the dry run to exactly 2 candidates × 2 trials and — by
design — does **not** invoke `write_final_overrides` (only `run_full_search`'s
final step does), so no final overrides are persisted. `search_one_threshold`
also terminates each candidate's kernel process in its `finally` block, so no
kernel is left running.

The real `apply_candidate_and_verify` and `run_candidate_trials` primitives were
used (wrapped only with timing/printing shims) — **no mocks anywhere in this
run**.

---

## Cross-model partitioning check (Subtask 7 review item)

`load_progress` groups `attempts.jsonl` records into `by_model` keyed on each
record's `model_name`, and reconstructs each model's `CoordinateSearchState`
(history + per-threshold completeness + winner) using only that model's records.
No cross-model leakage. Verified by reading the code and by a new explicit unit
test, `test_load_progress_partitions_by_model` (two models interleaved in one
log → each recovers only its own 5 attempts and its own independent winner:
A→0.5, B→0.9). **No fix needed** — the logic was already correct. Full suite: 34
tests pass.

---

## Full trace (real command output, not paraphrased)

### Candidate `novelty_threshold=0.5` — apply + verify

Surgical config edit produced (grep of the relevant lines):
```
112:    enabled: false       # master switch; false = frozen baseline   [adaptive_policy]
143:    enabled: true       # master switch for this variant; ...        [static_thresholds]
146:      overrides: [{llm_core: "qwen2.5:7b", value: 0.5}]      # ...    [novelty_threshold]
148:      default: 0.7 ... / 149: overrides: []                          [similarity: held]
151:      default: 0.7 ... / 152: overrides: []                          [redundancy: held]
```
`apply+verify took 14.1s; kernel pid=24842` (config edit + full process restart
+ `GET /status` poll + `GET /memory/gating_status` verify, all passing).

### Candidate `0.5` — 2 trials (subprocess `run_evaluation.py`)
```
CandidateAttempt for 0.5: mean=5.0 completed=2 failed=0 per_trial=[5.0, 5.0]
trials took 150.7s
```
Raw per-trial judge scores (from `results_kernel_shared_tuned.json`):
```
trial 0  p=5 t=5 i=5   → 5.0
trial 1  p=5 t=5 i=5   → 5.0
```

### Candidate `novelty_threshold=0.6` — apply + verify

Config edit updated only the novelty override (others still held):
```
146:      overrides: [{llm_core: "qwen2.5:7b", value: 0.6}]
```
`apply+verify took 16.1s; kernel pid=25308`.

### Candidate `0.6` — 2 trials
```
CandidateAttempt for 0.6: mean=4.333333333333333 completed=2 failed=0 per_trial=[5.0, 3.6666666666666665]
trials took 100.6s
```
Raw per-trial judge scores:
```
trial 0  p=5 t=5 i=5   → 5.0
trial 1  p=3 t=5 i=3   → 3.667
```

### Incremental progress log (`attempts.jsonl` after the run)
```json
{"model_name": "qwen2.5:7b", "model_backend": "ollama", "threshold_name": "novelty_threshold", "value": 0.5, "batch_mean_score": 5.0, "num_trials_completed": 2, "num_trials_failed": 0, "results_json_path": ".../dryrun-20260905_qwen2.5_7b_novelty_threshold_0.5/results_kernel_shared_tuned.json", "ts": 1788634351.79}
{"model_name": "qwen2.5:7b", "model_backend": "ollama", "threshold_name": "novelty_threshold", "value": 0.6, "batch_mean_score": 4.333333333333333, "num_trials_completed": 2, "num_trials_failed": 0, "results_json_path": ".../dryrun-20260905_qwen2.5_7b_novelty_threshold_0.6/results_kernel_shared_tuned.json", "ts": 1788634468.83}
```
Two lines, one appended per candidate as it completed (incremental, fsync'd). No
`summary.json` — expected, since `search_one_threshold` alone does not write the
summary checkpoint (that happens in `search_one_model`/`run_full_search` after a
full threshold milestone). Kept as evidence at
`benchmarks/shared_memory/threshold_search_progress/dryrun-20260905/`
(gitignored, so not committed).

### Winner
```
WINNER: 0.5
  novelty_threshold=0.5 mean=5.0
  novelty_threshold=0.6 mean=4.333333333333333
```
**Correct:** `0.5` has the higher batch mean (5.0 > 4.333), matching the raw
scores. (Had they tied, the tie-break would pick `0.5` as the lower/first grid
value — not exercised here.)

---

## Timing (real, for the Subtask 9 cost estimate)

| Candidate | restart + verify | 2 trials |
|-----------|------------------|----------|
| 0.5 | 14.1s | 150.7s |
| 0.6 | 16.1s | 100.6s |
| **Total** | **30.2s** | **251.3s** |

- **Total wall-clock (4 trials): 282.1s (~4.7 min).**
- **Restart+verify:** ~15s per candidate (kernel came up fast; warm caches).
- **Trials dominate:** ~251s of the ~282s. Per-trial cost varied
  (150.7s vs 100.6s for 2 trials each ⇒ ~50–75s/trial on qwen2.5:7b local,
  including the 3-agent pipeline + judge). Trial time is the dominant term for
  the full-search cost projection; restart overhead is a small fixed per-candidate
  add (~15s).

> Note on scores: qwen2.5:7b as its own judge tends to score high (5s); this is
> a wiring/timing dry run, not a quality result. The real search uses the GPT-5.4
> judge.

---

## Cleanup / invariants

- **No final overrides written** — `search_one_threshold` never calls
  `write_final_overrides`; confirmed by inspecting the config afterward.
- **config.yaml restored to baseline** after the run: `adaptive_policy.enabled:
  true`, `static_thresholds.enabled: false`, all three thresholds `default: 0.7`
  / `overrides: []` (0 wildcard overrides). AIOS `git status` clean.
- **No kernel left running:** `GET /status` refused, port 8000 free.
- **Progress artifacts kept** as evidence (gitignored).
- **No AIOS code modified** — only transient `config.yaml` edits, restored.
