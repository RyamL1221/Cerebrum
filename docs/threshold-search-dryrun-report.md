# Threshold-Search Pre-Flight Dry-Run Report — llama3.1:8b & gpt-4o

**Track:** threshold-search (offline coordinate search for
`memory.static_thresholds`, run against a live AIOS kernel via the
`kernel_shared_tuned` benchmark method).

**Purpose:** the consolidated pre-flight deliverable requested before deciding
whether to run the full 45-candidate search. It pulls together the two remaining
per-model dry runs (llama3.1:8b, gpt-4o), the real timing and token data captured
for them, the mid-flight engineering discoveries that were surfaced and retired,
the updated full-run cost/time estimate (old vs. new), and the final cleanup
verification — so the decision-maker has one document to work from.

**Scope note:** this is a **pre-flight report**, kept distinct from the ongoing
`docs/threshold-search-implementation-report.md` (the build/go-no-go document)
and the first-model trace `docs/threshold-search-dry-run-trace.md` (qwen2.5:7b).
It does not restate those in full; it references them and adds the two new model
traces plus the consolidated picture. Chosen as a separate doc because a
pre-flight report and an implementation report are distinct artifacts with
different audiences and lifespans.

> All numbers below are **real, captured** from this session's non-mocked runs
> (Subtasks 3 and 5) unless explicitly labeled an assumption. No full search was
> run. AIOS code was not modified; `config.yaml` edits were transient and
> restored (verified — see §6).

---

## 1. Prerequisites confirmed before spending (Subtask 1)

Verified **before** any paid/long run, with live 1-token connectivity checks
mirroring the kernel's exact call path:

- **gpt-4o:azure** (assistant) — reachable, returns `ok`.
- **gpt-5.4:azure** (judge) — reachable, returns `ok` (`finish_reason=stop`).
- **llama3.1:8b** (Ollama, local) — pulled and reachable.

An initial check was **blocked by an Azure VNet/firewall 403** on the un-VPN'd
public IP (`173.3.202.177`); reconnecting the VPN (allowlisted IP `128.6.36.26`)
cleared it. The key authenticated (403 firewall, not 401 auth) — reported, not
worked around. All three models confirmed before the first trial ran. ✅

---

## 2. Dry-run trace — llama3.1:8b (Subtask 3)

Same minimal shape as the qwen2.5:7b trace (`docs/threshold-search-dry-run-trace.md`):
`novelty_threshold`, candidates `0.5`/`0.6`, 2 trials each → **4 real trials**,
driven by `search_one_threshold` directly (owns the kernel lifecycle; never calls
`write_final_overrides`). **Assistant `llama3.1:8b:ollama`, judge `gpt-5.4:azure`**
(the real search judge, not a local proxy).

### Per-trial data (from `results_kernel_shared_tuned.json`)

| Candidate | Trial | latency (s) | P/T/I scores | assistant token_usage (p/c/t) | judge token_usage (p/c/t) |
|-----------|-------|-------------|--------------|-------------------------------|----------------------------|
| 0.5 | 0 | 14.21 | 4/5/4 | 323 / 238 / 561 | 943 / 241 / 1184 |
| 0.5 | 1 | 18.91 | 5/5/5 | 286 / 277 / 563 | 996 / 244 / 1240 |
| 0.6 | 0 | 13.80 | 4/2/2 | 224 / 181 / 405 | 890 / 208 / 1098 |
| 0.6 | 1 | 25.81 | 5/5/4 | 324 / 360 / 684 | 1129 / 255 / 1384 |

- **Winner:** `novelty_threshold=0.5` (batch mean **4.667**) vs. `0.6` (**3.667**).
  Sanity only — n=2/candidate, not a quality result.
- **Completion:** 4/4 trials completed, 0 failed.
- **Total wall-clock:** **280.2s** (~4.7 min), incl. 2 kernel restarts+verifies.
- **Per-trial latency:** avg **18.18s** (range 13.80–25.81).

---

## 3. Dry-run trace — gpt-4o (Subtasks 4 → 5)

Same shape, **assistant `gpt-4o:azure`, judge `gpt-5.4:azure`**. This one has an
honest two-part history: a first attempt that mostly failed, a diagnosed root
cause, a fix (§4), and a clean re-run. **The data below is the successful re-run
(4/4).**

### First attempt (Subtask 4) — 1/4 succeeded, reported not hidden

3 of 4 trials failed with `Expecting value: line 1 column 1 (char 0)` during
**synthetic data generation** (before assistant/judge ran). **Not** rate limiting
— every Azure call returned HTTP 200 (`x-ratelimit-remaining 1499/1500`). Root
cause: gpt-4o intermittently wraps its generator JSON in ```` ```json ... ``` ````
fences, and `synth.py` did a bare `json.loads` with no fence handling. The one
trial that passed proved the pipeline + token capture worked (latency 5.81s,
scores 5/5/5, assistant `314/672/986`, judge `1470/208/1678`). See §5 discovery #2.

### Re-run after the fix (Subtask 5) — 4/4 succeeded

| Candidate | Trial | latency (s) | P/T/I scores | assistant token_usage (p/c/t) | judge token_usage (p/c/t) |
|-----------|-------|-------------|--------------|-------------------------------|----------------------------|
| 0.5 | 0 | 9.38 | 3/5/3 | 315 / 414 / 729 | 1203 / 267 / 1470 |
| 0.5 | 1 | 4.67 | 5/5/5 | 290 / 480 / 770 | 1252 / 241 / 1493 |
| 0.6 | 0 | 6.91 | 5/5/4 | 308 / 638 / 946 | 1428 / 248 / 1676 |
| 0.6 | 1 | 4.81 | 5/5/5 | 313 / 401 / 714 | 1179 / 225 / 1404 |

- **Winner:** `novelty_threshold=0.6` (batch mean **4.833**) vs. `0.5` (**4.333**).
  Sanity only.
- **Completion:** 4/4 trials completed, 0 failed, **no fence failures**.
- **Total wall-clock:** **153.3s**, incl. 2 kernel restarts+verifies.
- **Per-trial latency:** avg **6.44s** (range 4.67–9.38) — much faster than the
  local models (cloud API round-trip).

---

## 4. Real captured token & timing summary (all three models)

Per-trial latency (the anchor for the cost estimate):

| Model | per-trial latency (measured) | source |
|-------|------------------------------|--------|
| qwen2.5:7b (local) | **62.8s** | prior trace (`...dry-run-trace.md`), unchanged |
| llama3.1:8b (local) | **18.18s** | §2, this session |
| gpt-4o (Azure) | **6.44s** | §3 re-run, this session |

Real token averages:

| Call | prompt (in) | completion (out) | basis |
|------|-------------|------------------|-------|
| gpt-4o main assistant call | 306 | 483 | 4 gpt-4o trials (§3) |
| **gpt-5.4 judge** | **1,128** | **241** | **8 real judge calls** (llama §2 + gpt-4o §3) |

The judge token figure is now **measured**, not assumed — this is the gap that
Subtask 2 closed (§5 discovery #1). It is captured on `TrialResult.judge_token_usage`
and confirmed populated on live (non-mocked) runs for both models.

---

## 5. Mid-flight discoveries & scope changes (retired engineering risk)

These are surfaced prominently, not as footnotes: each represents real risk that
was found and retired during the effort, and each is the kind of thing a
"final input before a bigger decision" report exists to make visible.

### Discovery #1 — Judge `token_usage` was silently discarded (found Subtask 2, fixed Subtask 2)
The kernel emits the judge LLM's `token_usage` as a top-level sibling of
`response`, but `judge.py` read only `response_message` and dropped it —
`JudgeScores`/`TrialResult` had no judge-token field at all. **Without this fix,
the acceptance criterion "capture real judge token_usage" was impossible.** Fixed
by threading it: `LLMJudge.evaluate()` captures it → `JudgeScores.token_usage` →
`HybridJudge` passthrough → `TrialResult.judge_token_usage` (distinct from the
assistant-only `token_usage`) → results JSON. Mirrors the existing assistant
path; no SDK/runner changes. Commit `9e4bf21`.

### Discovery #2 — gpt-4o markdown-fenced JSON broke synth parsing (found Subtask 4, fixed Subtask 5)
gpt-4o intermittently fences its generator JSON; `synth.py`'s bare `json.loads`
failed on it, killing 3/4 gpt-4o trials during data generation. Diagnosed from the
kernel log (all Azure calls were HTTP 200 — a parsing bug, not throttling or auth).
Fixed with `_loads_json_tolerant()` (strips fences/prose via first-`{`..last-`}`,
mirroring `judge.py`'s existing pattern; re-raises on genuine garbage so error
detection isn't weakened). Verified against bare, fenced, and garbage inputs;
re-run succeeded 4/4. Commit `a076b0d`. **This is a real risk retired for the full
run: any gpt-4o-tier candidate would have hit it.**

### Discovery #3 — Test regression from #1's wiring (found & fixed Subtask 5)
Running the suite after #1 surfaced a failure in `test_unified_trial_data_props.py`
(introduced by `9e4bf21`, confirmed via `git stash` that it predated the fence
work): the mocked judge returned a `MagicMock` for `.token_usage`, which failed
`TrialResult`'s pydantic dict validation. Fixed the **test mocks**
(`token_usage=None`, the real dict|None contract) rather than loosening production
validation. Committed with the fence fix (`a076b0d`).

### Discovery #4 — Two gitignore surprises (operational, reported)
- `aios/config/config.yaml` is **gitignored** in AIOS, so `git checkout` can't
  restore it and `git status` never shows the search's transient edits. Each dry
  run's config restore was therefore done by **direct value editing** and verified
  line-by-line (not via git).
- `.kiro/` is **gitignored** in Cerebrum, so the Subtask-6 steering note lives on
  disk (active for steering) but isn't tracked. Convention, not drift.

### Discovery #5 — Stray kernel processes after search (found & handled Subtask 3, repeated 5)
`search_one_threshold`'s `proc.terminate()` released port 8000 but left lingering
`runtime.launch` processes after the run. Cleaned up with `pkill` each time;
verified none remain (§6).

---

## 6. Updated full-run cost/time estimate — old (placeholder) vs. new (measured) (Subtask 6)

Full-search formula (confirmed in `threshold_search.py`): 3 models × 3 thresholds
× 5 candidates = **45 candidates** × **8 trials** = **360 trials**; restart+verify
**15.1s/candidate** (measured). Per-model wall-clock = 15 candidates ×
[15.1s + 8 × per-trial].

| Model | per-trial OLD (assumed) | per-trial NEW (measured) | wall-clock OLD | wall-clock NEW |
|-------|-------------------------|--------------------------|----------------|----------------|
| qwen2.5:7b | 62.8s (measured) | **62.8s** (measured) | ~2.16 h | ~2.16 h |
| llama3.1:8b | ~68s (assumed) | **18.18s** (measured) | ~2.33 h | ~0.67 h |
| gpt-4o | ~38s (assumed) | **6.44s** (measured) | ~1.33 h | ~0.28 h |
| **Total** | | | **~5.8 h** | **~3.1 h** |

> ### ⚠️ LARGE DELTA: full-run wall-clock ~5.8 h → ~3.1 h (≈ 2.7 h / ~47% less)
> Both placeholders were large overestimates (llama ~3.7× faster, gpt-4o ~6×
> faster than assumed). **qwen2.5:7b now dominates at ~70% of the total.** Restart
> overhead across the whole search is ~11 min. Runs are serial (one kernel at a
> time), so the three add. Realistic band: **~3–4 hours**.

**API cost (real token anchors + sourced pricing):**

| Component | Trials | Tokens | Rate | Cost |
|-----------|--------|--------|------|------|
| gpt-4o assistant | 120 | ~69K in / ~84K out | $2.50 / $10 per 1M (confirmed) | **~$1.02** |
| gpt-5.4 judge | 360 (all) | ~406K in / ~87K out | $1.75 / $14 per 1M (GPT-5.4 est.) | **~$1.93** |
| **Total** | | | | **~$2.4 – $2.9** |

- gpt-4o pricing **$2.50 in / $10 out** is confirmed across multiple 2026 sources.
- **GPT-5.4 has no cleanly published standalone rate**; it's bracketed by
  [GPT-5 ($1.25/$10)](https://futureagi.com/llm-cost-calculator/azure-openai/gpt-5/)
  and [GPT-5.2 ($1.75/$14)](https://futureagi.com/llm-cost-calculator/azure-openai/gpt-5-2/).
  The estimate uses the GPT-5.2 rate as a conservative proxy; at the GPT-5 rate the
  judge is ~$1.38 and the total ~$2.4. **The only remaining flagged assumption.**
- Down from the prior **~$4–15** band (real judge tokens are lower than assumed;
  pricing is now sourced). **Time, not cost, is the binding constraint.**

Full derivation and side-by-side prose: `docs/threshold-search-implementation-report.md`
§4–5 (updated in Subtask 6, commit `e5f12ff`).

---

## 7. Cleanup verification (Subtask 7)

A full end-of-effort sweep confirmed no leftover drift. Full checklist with
evidence: **`docs/threshold-search-cleanup-verification.md`** (commit `41ac758`).
Summary — **all PASS**:

- Cerebrum + AIOS git clean; AIOS `config.yaml` at baseline (verified directly,
  since gitignored): `adaptive_policy.enabled: true`, `static_thresholds.enabled:
  false`, all `overrides: []`, all `default: 0.7`.
- No `runtime.launch` process; port 8000 free.
- `policy_trials.jsonl` still **324** records (no `kernel_shared_tuned` run ever
  wrote to it — that method forces adaptive off, so the only writer never ran).
- No leftover temp files (`/tmp`, repo roots).
- **No Azure key/secret** in any committed file, log, or results file (the literal
  84-char key is absent everywhere in Cerebrum; kernel log masks it as `REDACTED`).
- `results/dryrun_*` dirs gitignored and untracked.

---

## 8. Original acceptance criteria — explicit status

| # | Criterion | Status | Where |
|---|-----------|--------|-------|
| 1 | Prerequisites confirmed before spending | ✅ | §1 (live 1-token checks; firewall gap found & cleared) |
| 2 | Real timing captured for both models | ✅ | §2 (llama 18.18s avg), §3 (gpt-4o 6.44s avg) |
| 3 | Real judge `token_usage` captured (non-mocked) | ✅ | §2/§3 tables; enabled by the Subtask 2 fix (§5 #1) |
| 4 | Updated estimate presented alongside original | ✅ | §6 old-vs-new table + delta callout |
| 5 | Config / processes / git left clean | ✅ | §7 + `...cleanup-verification.md` |
| 6 | All deviations reported, not silently resolved | ✅ | §5 (judge-token gap, fence gap, test regression, gitignore surprises, stray processes) |

---

## 9. What this report enables (input, not the decision)

This report provides the **input** for a go/no-go on the full 45-candidate search:

- **Time:** ~**3.1 hours** wall-clock (realistic band ~3–4 h), serial, dominated
  by qwen2.5:7b (~70%).
- **Cost:** ~**$2.4–2.9** Azure spend (gpt-4o assistant + gpt-5.4 judge), with the
  exact GPT-5.4 rate the only remaining bracketed unknown.
- **Risk retired:** the judge-token gap and the gpt-4o fence-parsing gap — both of
  which would otherwise have surfaced *during* the full run — are fixed and
  verified; the pipeline ran 4/4 clean for both new models.
- **Environment:** confirmed clean and reproducible (§7).

**The go/no-go decision itself is the user's call and is deliberately not made
here.** When/if the full run is authorized, `run_full_search(..., write_final=True)`
executes it and writes the 9 winning overrides to `config.yaml` once at the end;
resuming a partial run is supported (`search_run_id=..., resume=True`).
