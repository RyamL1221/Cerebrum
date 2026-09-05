# Static Threshold Search — Implementation Report & Full-Run Cost/Time Estimate

**Track:** threshold-search (offline coordinate search for
`memory.static_thresholds`, run against a live AIOS kernel via the
`kernel_shared_tuned` benchmark method).

**Status:** Investigation, implementation, and a real minimal dry run are
complete. **The full 45-candidate search has NOT been run.** This report is the
go/no-go deliverable; running the full search requires a separate, explicit
go-ahead (see §6).

> Pure synthesis of already-captured evidence. No AIOS code was modified and no
> live kernel was started for this report.

---

## 1. Investigation findings (Subtasks 1–3 — summarized, not re-derived)

Three prior reports established the mechanics; this section summarizes them.

1. **Config reload/restart mechanics** —
   `docs/threshold-search-config-reload-mechanics.md` (commit `dcc8929`).
   `POST /core/refresh` returns `success` but does **not** apply
   `memory.static_thresholds` changes (the kernel's `restart_kernel()` reassigns
   `active_components` without a `global`, discarding the rebuilt MemoryManager).
   **A full AIOS process restart is required** between candidate configs.
   `/core/config/update` funnels through the same broken path. Evidence: live
   before/after `GET /memory/gating_status` snapshots (0.7 stays 0.7 after
   refresh; becomes 0.6 only after a real restart).

2. **Trial pool structure & disjointness** —
   `docs/threshold-search-trial-pool-structure.md` (commit `a4f7f9e`).
   Trial data is **freshly LLM-generated per trial** (no fixed pool, no seed);
   `trial_index` is a prompt-diversity hint, not a deterministic content key.
   `kernel_shared_tuned` requires **both** `static_thresholds.enabled=true` **and**
   `adaptive_policy.enabled=false` — two independent kernel toggles the harness
   verifies (raises on mismatch) but does not set. No existing hard disjointness
   mechanism; a frozen corpus + index slice would be the only guarantee (deferred).

3. **Harness invocation & output schema** —
   `docs/threshold-search-harness-invocation.md` (commit `3342e92`).
   Exact CLI: `run_evaluation.py --trials N --method kernel_shared_tuned
   --assistant-model "<name>:<backend>" --judge-model <judge> --kernel-url <url>
   --output <dir> --run-id <id> --csv`. Model strings: GPT-4o=`gpt-4o:azure`,
   Llama=`llama3.1:8b:ollama`, Qwen=`qwen2.5:7b:ollama` (Ollama required for the
   latter two). The gating pre-flight fires automatically for
   `kernel_shared_tuned`. Judge scores land in
   `results_kernel_shared_tuned.json` → `conditions[0].trials[*].{profile_usage_score,
   task_usage_score, integration_score}`; per-trial reward = mean of the non-null
   three (`run_evaluation.py:462-469`). Verified by a real 2-trial run.

---

## 2. What was built (Subtasks 4–7)

All in **`benchmarks/shared_memory/threshold_search.py`**, tested by
**`tests/agents/test_threshold_search_primitives.py`** (34 kernel-free tests, all
passing). Line numbers are current as of this report.

### Config → restart → verify primitives (Subtask 4, commit `8dc0889`)
- `write_candidate_config()` (`:272`) — surgical, format-preserving edit: forces
  `static_thresholds.enabled: true` / `adaptive_policy.enabled: false`, writes the
  varied threshold's wildcard override `{llm_core, value}`, holds other defaults,
  clears stale overrides. Helpers `_replace_block_toggle` (`:136`),
  `_set_threshold` (`:175`).
- `restart_kernel_and_wait()` (`:364`) — stops any kernel (`lsof`), spawns
  `python -m runtime.launch`, polls `GET /status`. Raises `KernelStartupError`.
- `verify_gating_status()` (`:500`) — the loud safety net; raises
  `GatingVerificationError` with expected-vs-actual on any toggle/default/override
  mismatch.
- `apply_candidate_and_verify()` (`:622`) — wires the three; terminates the
  started kernel if verification fails. `CandidateConfig` (`:101`).

### Candidate trial runner + judge-score aggregation (Subtask 5, commit `79f2f9c`)
- `run_candidate_trials()` (`:877`) — subprocess-invokes `run_evaluation.py` with
  the confirmed flags against an already-verified kernel.
- `aggregate_judge_scores()` (`:791`) / `parse_candidate_results()` (`:834`) /
  `_trial_reward()` (`:769`) — pure, testable core. `CandidateTrialResult` (`:727`).
- **Judge model default** `DEFAULT_SEARCH_JUDGE_MODEL = "gpt-5.4:azure"` (`:710`) —
  search optimizes against the same reliable judge as final reporting.
- **Failed-trial policy:** a trial is excluded (counted in `num_trials_failed`,
  never folded as 0) when `failed:true` or all-null scores; partial-null averages
  present dims; all-failed batch → `batch_mean_score=None` (no signal).

### Coordinate search loop (Subtask 6, commit `70e5044`)
- `search_one_threshold()` (`:1153`), `search_one_model()` (`:1296`),
  `run_full_search()` (`:1396`), `write_final_overrides()` (`:1499`),
  `select_winner()` (`:1096`). `CoordinateSearchState` (`:1057`),
  `CandidateAttempt` (`:1040`).
- Grid `DEFAULT_CANDIDATE_GRID=(0.5,0.6,0.7,0.8,0.9)` (`:1021`),
  `DEFAULT_TRIALS_PER_CANDIDATE=8` (`:1022`), order novelty→similarity→redundancy
  (`:1014`), models `("gpt-4o","llama3.1:8b","qwen2.5:7b")` (`:1027`).
- **Winner rule:** highest batch mean; ties → first/lowest (strictly-greater
  replacement); `None` treated as worst but kept in history; all-None → first
  candidate, score `None`. Models fully independent. **Final config written
  exactly once**, after all models, via `write_final_overrides` — never per-candidate.

### Resumability + crash-safe progress (Subtask 7, commit `82fa2ba`)
- `ProgressLog` (`:1610`): `append_attempt()` (`:1626`, JSONL flush+fsync per
  candidate), `write_summary()` (`:1653`, atomic temp+`os.replace`).
  `_read_jsonl_tolerant()` (`:1682`, drops only a torn final line),
  `load_progress()` (`:1713`, reconstructs per-model done/in-progress/pending).
- `run_full_search(search_run_id=..., resume=True)` skips fully-complete models,
  skips already-won thresholds, and never re-runs an on-disk candidate. Progress
  under `benchmarks/shared_memory/threshold_search_progress/<run_id>/` (gitignored).

---

## 3. Dry-run trace (Subtask 8, commit `976cb1d`)

Full trace: `docs/threshold-search-dry-run-trace.md`. Real, non-mocked, 4-trial
run (qwen2.5:7b, `novelty_threshold`, candidates 0.5/0.6, 2 trials each) via
`search_one_threshold`. Result: candidate 0.5 mean **5.0** `[5.0, 5.0]`, candidate
0.6 mean **4.333** `[5.0, 3.667]`, **winner 0.5** (correct). Progress logged
incrementally; config restored to baseline; no kernel left running. Also
confirmed `load_progress` cross-model partitioning is correct (new test
`test_load_progress_partitions_by_model`).

**Measured timing (the anchor for §4):**

| Candidate | restart+verify | 2 trials |
|-----------|----------------|----------|
| 0.5 | 14.1s | 150.7s |
| 0.6 | 16.1s | 100.6s |
| Total | 30.2s | 251.3s |

⇒ **restart+verify ≈ 15.1s/candidate**; **trials ≈ 251.3s / 4 = 62.8s/trial**
(qwen2.5:7b local, incl. 3-agent ProfileAgent→TaskAgent→AssistantAgent pipeline +
local judge).

---

## 4. Full-run time estimate (extrapolated transparently)

**Full search parameters:** 3 models × 3 thresholds × 5 candidates = **45
candidates**; **8 trials/candidate** ⇒ **360 trials total**.

### Per-candidate cost model
```
candidate_time ≈ restart_verify + (trials_per_candidate × per_trial_time)
               ≈ 15.1s          + (8 × per_trial_time)
```
Restart+verify is a fixed ~15s/candidate → **45 × 15.1s ≈ 680s ≈ 11 min** total
restart overhead (small term). Trial time dominates and is **model-dependent**, so
estimates are given **per model** (a single blended number would be misleading).

### Per-model per-trial time — data availability
- **qwen2.5:7b (local):** measured **62.8s/trial** (Subtask 8, 4 trials).
  *(Subtask 3's 2-trial run showed ~11.7s assistant latency but higher total
  including generation+judge; the 62.8s figure is the more complete end-to-end
  per-trial wall time and is used here.)*
- **llama3.1:8b (local):** **no direct measurement.** Similar size/host to qwen
  (8B vs 7B, same Ollama backend). Used as **~60–75s/trial (placeholder,
  qwen-anchored)** — flagged as an assumption, not measured.
- **gpt-4o (Azure API):** **no direct end-to-end trial measurement.** API latency
  is typically lower per token than a local 7–8B model, but each trial still runs
  the full 3-agent pipeline + a GPT-5.4 judge call. Used as **~30–45s/trial
  (placeholder, assumption)** — could be faster (API parallelism) or slower
  (network/rate limits). Flagged.

### Per-model wall-clock (15 candidates × [15.1s + 8 × per_trial])
| Model | per-trial (basis) | per-candidate | × 15 candidates |
|-------|-------------------|---------------|-----------------|
| qwen2.5:7b | 62.8s (measured) | 15.1 + 502.4 = 517.5s | **~2.16 h** |
| llama3.1:8b | ~68s (assumed) | 15.1 + 544 = 559s | **~2.33 h** |
| gpt-4o | ~38s (assumed) | 15.1 + 304 = 319s | **~1.33 h** |

**Total estimated wall-clock ≈ 2.16 + 2.33 + 1.33 ≈ 5.8 hours**, dominated by the
two local models. Realistic band, accounting for the placeholder assumptions and
occasional slow trials/restarts: **~5–8 hours**. Runs are serial (one kernel at a
time by design), so the models' times add.

> All arithmetic shown. The only measured input is qwen's 62.8s/trial and
> ~15s/candidate restart; llama and gpt-4o per-trial times are **assumptions**
> (flagged) pending their own measurement — a fast way to tighten this is a
> 2-trial dry run per remaining model (as in Subtask 8) before committing to the
> full run.

---

## 5. Full-run API cost estimate (GPT-4o assistant + GPT-5.4 judge)

Only the **gpt-4o model tier** incurs API spend on the assistant side; **all three
tiers** incur GPT-5.4 judge spend (the search judge default is `gpt-5.4:azure`).
The two local-assistant tiers (qwen, llama) cost nothing on the assistant side.

### Token anchor (real, captured)
Subtask 3's real run captured per-trial `token_usage` for the **assistant** call
(qwen, but token counts are model-agnostic for the prompt/response shape):
`{prompt 322, completion 582, total 904}` and `{prompt 316, completion 223, total
539}` ⇒ assistant ≈ **300–330 prompt + 220–580 completion**, call it **~750
tokens/assistant-call** average. Each trial also runs ProfileAgent + TaskAgent LLM
calls (structured, smaller) and one judge call.

### Assumptions (flagged — judge token usage was NOT directly captured; the smoke
tests used a local judge)
- **Judge (GPT-5.4)** input ≈ profile + task + response + rubric ≈ **~1,500 prompt
  tokens**, output ≈ **~400 completion tokens** per trial (rough; the judge prompt
  embeds the full assistant response). **Assumption.**
- **gpt-4o assistant** per trial ≈ the 3 agent calls ≈ **~1,500 prompt + ~1,000
  completion** combined (profile/task calls + the main assistant call).
  **Assumption, anchored on the ~750-token assistant call + two smaller structured
  calls.**

### Trial counts by tier
- gpt-4o tier: 15 candidates × 8 = **120 trials** (GPT-4o assistant **and** GPT-5.4
  judge).
- qwen + llama tiers: 30 candidates × 8 = **240 trials** (GPT-5.4 judge **only**;
  local assistant is free).
- **Judge runs on all 360 trials.**

### Token totals (order-of-magnitude)
- **Judge (GPT-5.4), 360 trials:** 360 × (1,500 in + 400 out) ≈ **540K input +
  144K output**.
- **GPT-4o assistant, 120 trials:** 120 × (1,500 in + 1,000 out) ≈ **180K input +
  120K output**.

### Cost (using representative Azure list prices — VERIFY current rates before relying on this)
> Prices change and depend on the deployment/region; the numbers below use
> commonly-cited list rates as of the model generations named and are an **estimate
> to be re-checked**, not a quote.
- GPT-4o ≈ $2.50 / 1M input, $10 / 1M output (representative).
  - Assistant: 0.18M×$2.50 + 0.12M×$10 ≈ $0.45 + $1.20 = **~$1.65**.
- GPT-5.4-as-judge: pricing **unknown to this report** (a newer/hypothetical judge
  model in this environment). Using a GPT-4o-class rate as a **placeholder**:
  0.54M×$2.50 + 0.144M×$10 ≈ $1.35 + $1.44 = **~$2.80**. If GPT-5.4 is priced
  higher, scale accordingly.
- **Total estimated API spend ≈ $4–5, plausibly up to ~$10–15** if GPT-5.4 judge
  pricing is several× GPT-4o. This is **small** relative to the ~6-hour wall-clock;
  **time, not API cost, is the binding constraint.**

> Cost caveats: judge token estimate and GPT-5.4 pricing are the two biggest
> unknowns and are explicitly flagged. The assistant-token anchor is real; the
> judge-token figure is an assumption. A single real gpt-4o-tier candidate (8
> trials) would capture true judge `token_usage` and pin this down.

---

## 6. Full search has NOT been executed

**The real 45-candidate / 360-trial search has not been run, has not been
simulated, and no partial results are presented as if it had.** Only the 4-trial
dry run (§3) has actually executed. Running the full search:
- takes an estimated **~5–8 hours** wall-clock (§4),
- costs an estimated **~$4–15** in API spend (§5),
- writes the 9 winning overrides to the real `config.yaml` **once at the end** via
  `run_full_search(..., write_final=True)`.

It **requires a separate, explicit go-ahead.** Recommended pre-flight to tighten
the estimate first: a 2-trial dry run for `llama3.1:8b` and `gpt-4o` (mirroring
Subtask 8) to replace the two placeholder per-trial times and capture real GPT-5.4
judge `token_usage`.

---

## 7. Master-prompt acceptance-criteria checklist

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Determine whether config reload suffices or a full restart is required | ✅ | Subtask 1, `docs/threshold-search-config-reload-mechanics.md`, commit `dcc8929` — full restart required (live before/after evidence). |
| 2 | Understand trial pool / disjointness options | ✅ | Subtask 2, `...trial-pool-structure.md`, commit `a4f7f9e` — fresh per-trial generation; disjointness options documented. |
| 3 | Confirm exact harness invocation + output schema + judge field | ✅ | Subtask 3, `...harness-invocation.md`, commit `3342e92` — verified by a real 2-trial run. |
| 4 | Config→restart→verify primitives, surgical edits, loud verify | ✅ | Subtask 4, `threshold_search.py` (`:272/:364/:500/:622`), commit `8dc0889`; live exercise (novelty=0.6 verified). |
| 5 | Candidate trial runner, judge-score aggregation, failed-trial policy | ✅ | Subtask 5, `threshold_search.py` (`:877/:791`), commit `79f2f9c`; live smoke (batch_mean 4.667). |
| 6 | Coordinate search: order, grid, winner selection, per-model repeat, single final write | ✅ | Subtask 6, `threshold_search.py` (`:1096/:1153/:1296/:1396/:1499`), commit `70e5044`; mocked control-flow tests. |
| 7 | Resumability: incremental crash-safe persistence + resume from last step | ✅ | Subtask 7, `threshold_search.py` (`:1610/:1713`), commit `82fa2ba`; partial-run resume test. |
| 8 | Real dry run (minimal scale), full trace, correct winner, no leftover state | ✅ | Subtask 8, `...dry-run-trace.md`, commit `976cb1d` — 4 real trials, winner 0.5, config restored, no kernel left. |
| 9 | Implementation report + full-run cost/time estimate, no full run | ✅ | This report; §4 time (~5–8h), §5 cost (~$4–15), §6 explicit no-run statement. |
| — | Tuned regime = static thresholds ON + adaptive OFF, verified per candidate | ✅ | `verify_gating_status` (`:500`); confirmed live in Subtasks 4/8. |
| — | Never persist intermediate values to real config mid-search | ✅ | `write_final_overrides` called only in `run_full_search` final step; `search_one_threshold`/dry run never write it (Subtask 8 confirmed config restored). |
| — | No AIOS code modified (config.yaml transient only) | ✅ | AIOS `git status` clean after every subtask; config restored to baseline each time. |

---

## 8. Summary

The full offline threshold-search pipeline is **built, unit-tested (34 tests), and
proven end-to-end on real infrastructure at minimal scale.** The confirmed
mechanics (full restart between candidates; static-on/adaptive-off; GPT-5.4 judge;
fresh per-trial generation) are encapsulated in reusable, resumable, crash-safe
primitives. The full 45-candidate run is estimated at **~5–8 hours** and
**~$4–15** in API spend, with the two local-model per-trial times and the GPT-5.4
judge token/price being the flagged assumptions worth pinning down with a small
per-model dry run first. **The full search awaits a separate, explicit go-ahead.**
