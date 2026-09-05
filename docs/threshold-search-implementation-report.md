# Static Threshold Search — Implementation Report & Full-Run Cost/Time Estimate

**Track:** threshold-search (offline coordinate search for
`memory.static_thresholds`, run against a live AIOS kernel via the
`kernel_shared_tuned` benchmark method).

**Status:** Investigation, implementation, and real minimal dry runs for **all
three models** (qwen2.5:7b, llama3.1:8b, gpt-4o) are complete. **The full
45-candidate search has NOT been run.** This report is the go/no-go deliverable;
the cost/time estimate (§4–5) is now based on **measured** per-trial times and real
token usage for every model, not placeholders. Running the full search requires a
separate, explicit go-ahead (see §6).

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

### Per-model per-trial time — NOW ALL MEASURED

> **UPDATE (Subtasks 3 & 5 dry runs):** the two placeholder per-trial times have
> been **replaced with real measurements**. Both local-vs-cloud placeholders were
> **large overestimates.** See the old-vs-new table and delta callout below.

- **qwen2.5:7b (local):** **62.8s/trial** — measured (Subtask 8, 4 trials).
  Unchanged.
- **llama3.1:8b (local):** **18.18s/trial** — **MEASURED** (this session, 4 trials:
  14.21, 18.91, 13.80, 25.81s). Replaces the ~60–75s placeholder. **~3.7× faster
  than assumed.** (The qwen-anchored placeholder wrongly assumed an 8B Ollama model
  would track a 7B one; in practice this llama build ran much faster per trial.)
- **gpt-4o (Azure API):** **6.44s/trial** — **MEASURED** (this session, 4 trials:
  9.38, 4.67, 6.91, 4.81s). Replaces the ~30–45s placeholder. **~6× faster than
  assumed** — the cloud API round-trip for the 3-agent pipeline + GPT-5.4 judge is
  far quicker than the local models.

### Old (placeholder) vs. new (measured) — per-trial and per-model wall-clock

Per-model wall-clock = 15 candidates × [15.1s restart+verify + 8 × per_trial].

| Model | per-trial OLD (assumed) | per-trial NEW (measured) | wall-clock OLD | wall-clock NEW |
|-------|-------------------------|--------------------------|----------------|----------------|
| qwen2.5:7b | 62.8s (measured) | **62.8s** (measured) | ~2.16 h | **~2.16 h** |
| llama3.1:8b | ~68s (assumed) | **18.18s** (measured) | ~2.33 h | **~0.67 h** |
| gpt-4o | ~38s (assumed) | **6.44s** (measured) | ~1.33 h | **~0.28 h** |
| **Total** | | | **~5.8 h** | **~3.1 h** |

> ### ⚠️ LARGE DELTA: full-run wall-clock drops from ~5.8 h to ~3.1 h (≈ 2.7 h / ~47% less)
> The entire reduction comes from the two measured models being **much** faster than
> their placeholders (llama 68→18.2s, gpt-4o 38→6.4s per trial). **qwen2.5:7b is now
> the dominant cost at ~2.16 h (≈ 70% of the total)** — the full-run time is
> essentially "qwen + ~1 h for the other two". Restart+verify overhead is
> negligible: 45 × 15.1s ≈ **11 min** across the whole search. Runs are serial (one
> kernel at a time by design), so the three models' times add. Realistic band
> allowing for occasional slow trials/restarts: **~3–4 hours** (down from the prior
> ~5–8 h band).

> All three per-trial times are now measured, not assumed. Only the fixed
> restart+verify (~15.1s/candidate) is carried over from the qwen dry run; it is a
> small term and not model-specific.

---

## 5. Full-run API cost estimate (GPT-4o assistant + GPT-5.4 judge)

Only the **gpt-4o model tier** incurs API spend on the assistant side; **all three
tiers** incur GPT-5.4 judge spend (the search judge default is `gpt-5.4:azure`).
The two local-assistant tiers (qwen, llama) cost nothing on the assistant side.

### Token anchor — NOW REAL for BOTH assistant and judge

> **UPDATE (Subtask 5):** judge `token_usage` is now captured end-to-end
> (`TrialResult.judge_token_usage`, threaded in Subtask 2). The prior report's
> judge-token figure was an **assumption**; it is now **measured** from 8 real
> GPT-5.4 judge calls across the llama and gpt-4o dry runs.

Real per-trial averages (this session):

| Call | prompt (in) | completion (out) | basis |
|------|-------------|------------------|-------|
| gpt-4o main assistant call | 306 | 483 | 4 gpt-4o trials (Subtask 5) |
| ProfileAgent + TaskAgent gen calls (gpt-4o tier, each) | ~135 | ~110 | AIOS `kernel.log`, 2 calls/trial |
| **GPT-5.4 judge** | **1,128** | **241** | **8 real judge calls** (llama+gpt-4o runs) |

The old report assumed the judge at ~1,500 in / ~400 out — **real is lower**
(~1,128 in / ~241 out), so the prior judge-cost figure was a slight overestimate.

### Trial counts by tier (unchanged — formula confirmed in `threshold_search.py`)
- gpt-4o tier: 15 candidates × 8 = **120 trials** (GPT-4o assistant **and** GPT-5.4
  judge).
- qwen + llama tiers: 30 candidates × 8 = **240 trials** (GPT-5.4 judge **only**;
  local assistant is free).
- **Judge (GPT-5.4) runs on all 360 trials.**

### Token totals (real anchors)
- **GPT-5.4 judge, 360 trials:** 360 × (1,128 in + 241 out) ≈ **406K input +
  87K output**.
- **GPT-4o assistant, 120 trials:** 120 × (306 + 2×135 = 576 in ; 483 + 2×110 =
  703 out) ≈ **69K input + 84K output** (main call + the two structured generation
  calls).

### Pricing (Azure Global Standard, PAYG — sourced; GPT-5.4 rate is the one estimate)
- **GPT-4o: $2.50 / 1M input, $10.00 / 1M output** — consistently confirmed across
  multiple 2026 sources
  ([futureagi](http://www.futureagi.com/llm-cost-calculator/azure-openai/gpt-4o),
  [markaicode](https://markaicode.com/pricing/azure-openai-pricing/),
  [rapidevelopers](https://www.rapidevelopers.com/ai-api-limits-performance-matrix/gpt-4o)).
- **GPT-5.4: no cleanly published standalone rate found.** GPT-5.4 is confirmed
  live on Azure ([cloudzero](https://www.cloudzero.com/blog/azure-openai-pricing/)),
  bracketed by its neighbors —
  [GPT-5 / GPT-5-chat $1.25 in / $10 out](https://futureagi.com/llm-cost-calculator/azure-openai/gpt-5/)
  and [GPT-5.2 $1.75 in / $14 out](https://futureagi.com/llm-cost-calculator/azure-openai/gpt-5-2/).
  This estimate uses the **GPT-5.2 rate ($1.75 in / $14 out)** as a conservative
  (higher) proxy for 5.4. **Flagged: verify the exact GPT-5.4 rate before relying
  on the cost.** (Pricing content rephrased from the cited sources for compliance.)

### Cost
- **GPT-4o assistant** (120 trials): 0.069M × $2.50 + 0.084M × $10 ≈ $0.17 + $0.84
  = **~$1.02**.
- **GPT-5.4 judge** (360 trials): 0.406M × $1.75 + 0.087M × $14 ≈ $0.71 + $1.22
  = **~$1.93** (at the GPT-5.2-proxy rate). *If GPT-5.4 tracks GPT-5 ($1.25/$10)
  instead: ~$1.38.*
- **Total estimated API spend ≈ $2.4 – $2.9** (range spans the GPT-5-vs-5.2 proxy
  for the judge). Down from the prior **~$4–15** band — the real judge tokens are
  lower than assumed and the sourced pricing is tighter. Still **small** relative to
  the ~3-hour wall-clock; **time, not API cost, is the binding constraint.**

> Remaining flagged unknown: the **exact GPT-5.4 Azure rate** (bracketed
> $1.25–$1.75 in / $10–$14 out from its neighbors). Both token anchors are now real
> (assistant and judge). The ~$2.4–2.9 total is robust to the judge-pricing
> uncertainty because the judge is only ~$1.4–1.9 of it.

---

## 6. Full search has NOT been executed

**The real 45-candidate / 360-trial search has not been run, has not been
simulated, and no partial results are presented as if it had.** Only the 4-trial
dry run (§3) has actually executed. Running the full search:
- takes an estimated **~3.1 hours** wall-clock (§4, all per-trial times now
  measured; realistic band ~3–4 h),
- costs an estimated **~$2.4–2.9** in API spend (§5, real token anchors; only the
  exact GPT-5.4 rate remains bracketed),
- writes the 9 winning overrides to the real `config.yaml` **once at the end** via
  `run_full_search(..., write_final=True)`.

It **requires a separate, explicit go-ahead.** The recommended pre-flight (per-model
dry runs for `llama3.1:8b` and `gpt-4o`) has **now been done** (Subtasks 3 & 5):
both placeholder per-trial times are replaced with measurements and real GPT-5.4
judge `token_usage` is captured. The estimate above is updated accordingly:
**~3.1 h** (was ~5.8 h) and **~$2.4–2.9** (was ~$4–15).

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
primitives. With all three per-trial times **now measured** (Subtasks 3 & 5) and
real GPT-5.4 judge tokens captured, the full 45-candidate run is estimated at
**~3.1 hours** (was ~5.8 h — llama and gpt-4o are far faster than the placeholders;
qwen now dominates at ~70% of the total) and **~$2.4–2.9** in API spend (was
~$4–15). The only remaining flagged assumption is the exact GPT-5.4 Azure price
(bracketed by its published neighbors). **The full search awaits a separate,
explicit go-ahead.**
