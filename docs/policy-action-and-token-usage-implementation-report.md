# Implementation Report: `token_usage` live-path threading + standalone `policy_action` join

## Summary

This report consolidates the full body of work across Subtasks 1–8: surfacing
per-call `token_usage` through the live benchmark path and attributing the
kernel's adaptive-policy reward records to benchmark trials via a standalone
post-hoc join (`policy_action`). Every change is additive; no existing behavior
was altered. Several findings contradicted assumptions in the master prompt and
are reported plainly rather than silently worked around (see "Deviations").

All schema changes live in the benchmark harness. **No AIOS kernel changes, no
Cerebrum SDK changes to `communication.py`/`apis.py`, and no live-path changes
for `policy_action`.** The one live-path change (`token_usage`) is confined to
`AssistantAgent.run()` consuming an already-emitted response key.

Cross-artifact detail (schema/decision evidence) lives in
`docs/policy-trials-jsonl-findings.md` (Subtasks 1–2, 7); this report is the
top-level closeout.

---

## Part A — Investigation findings (Subtasks 1–3)

### Subtask 1 — `policy_trials.jsonl` exists and is populated
- Confirmed from AIOS `aios/config/config.yaml`:
  `memory.adaptive_policy.trial_log: "logs/policy_trials.jsonl"`,
  `enabled: true`. File exists at `<AIOS>/logs/policy_trials.jsonl` with **324
  records** (133 `select`, 191 `reward`).
- Schema is a **discriminated union on `event`** (authoritative source:
  AIOS `aios/memory/policy_log.py`), NOT the flat `{trial_id, bandit, arm,
  reward_value, timestamp}` the brief assumed:
  - `select`: `event, trial_id, bandit, gate, value, arm_index, llm_core,
    task_type, context, ts`
  - `reward`: `event, trial_id, bandit, arm_index, reward, memory_id, ts`
- `trial_id` is nullable and heterogeneously typed (int / null / string).

### Subtask 2 — `trial_id` join compatibility
- The benchmark field is **`trial_index: int`** — there is **no `trial_id`
  field** on `TrialResult`. `trial_index` is the bare `range(self.trials)`
  loop counter (`0..N-1`), sent to the kernel only via `report_reward` metadata
  (`{**trial_metadata, "trial_id": trial_index}`).
- Data confirms: all 180 integer `trial_id`s are `reward` events (values
  `0`–`14`); all 125 `null`s are `select` events (the harness never threads
  `trial_index` into add/retrieve metadata); string values are manual markers.
- Verdict: **`reward` records join directly** (`reward.trial_id ==
  trial_index`); **`select` records are unjoinable** (always null); string
  markers excluded.

### Subtask 3 — `token_usage` drop point (re-confirmed against AIOS source)
- Kernel builds `{"response": <LLMResponse>, "token_usage":
  syscall.get_token_usage(), ...}` in `aios/syscall/syscall.py` — `token_usage`
  is a **top-level sibling** of `response`, not nested.
- `AssistantAgent.run()` read only `response["response"]["response_message"]`
  and returned `{agent_name, result, rounds}`, discarding the sibling. Confirmed.
- **Drift:** the SDK's `LLMResponse` model *does* declare `token_usage`, but it
  is moot because `llm_chat` returns a raw dict, not an `LLMResponse`. Net
  effect matches the brief; mechanism differs.
- **Drift:** there are **four** `TrialResult(...)` construction sites (1 success
  + 3 error), not one.

---

## Part B — What changed (code, with file + line references)

### Live-path `token_usage` (Subtasks 4–6)

1. **`cerebrum/example/agents/assistant_agent/agent.py` — Subtask 4** (commit `fc7221e`)
   - Line **66**: `token_usage = response.get("token_usage") if response else None`
     (reads the top-level sibling defensively).
   - Line **74** (success return) and line **82** (except return): added
     `"token_usage"` key. Additive; existing keys unchanged. `communication.py`
     and `apis.py` untouched.

2. **`benchmarks/shared_memory/pipeline.py` — Subtask 5** (commit `3a88eee`)
   - Line **55**: new dataclass field `token_usage: Optional[Dict[str,
     Optional[int]]] = None` on `PipelineResult` (+ `Dict` added to the typing
     import).
   - Lines **194 / 606 / 713**: all three construction sites populate
     `token_usage=assistant_result.get("token_usage")` (`run_trial`,
     `_run_naive_concat`, `_run_vanilla_rag`). `_run_kernel_shared` /
     `_run_mem0_default` delegate to `run_trial`, inheriting it.

3. **`benchmarks/shared_memory/models.py` + `run_evaluation.py` — Subtask 6** (commit `ed6692c`)
   - `models.py` line **181**: `TrialResult.token_usage: Optional[Dict[str,
     Optional[int]]] = None` (+ `Dict` import).
   - `run_evaluation.py` line **522**: success-path `TrialResult(...)` sets
     `token_usage=pipeline_result.token_usage`. The three error/exception sites
     (~L340, ~L353, ~L632) leave it at the `None` default, matching the file's
     style for other optional fields.

### Standalone `policy_action` join (Subtask 8 — this subtask)

4. **`benchmarks/shared_memory/models.py`** (additive, model-only)
   - Line **137**: new `PolicyActionEntry(BaseModel)` with
     `bandit: str`, `arm_index: int`, `reward: float`,
     `memory_id: Optional[str] = None` — mirrors one `reward` record.
   - Line **188**: `TrialResult.policy_action: Optional[List[PolicyActionEntry]]
     = None`. Placed directly after `token_usage`. NOT threaded through
     `AssistantAgent`/`PipelineResult` (explicit non-goal): populated only by
     the post-hoc join. `None` = not yet joined; `[]` = joined, no records.

5. **`benchmarks/shared_memory/join_policy_actions.py`** (new, 353 lines, stdlib-only)
   - Follows the repo's standalone-script convention (`assert_injection_rate.py`):
     `from __future__ import annotations`, `argparse`, `main(argv) -> int`
     exit-code, `[join_policy_actions]`-prefixed report, JSON loaded via
     `payload["conditions"][*]["trials"]`.
   - CLI: `--results` (harness `results*.json`), `--policy-log` (a single-run
     `policy_trials.jsonl` slice), `--output` (enriched copy — a **new file**,
     not in-place, to keep the original artifact immutable), and optional
     `--since`/`--until` epoch-second `ts` window for single-run scoping.
   - Enforces Subtask 7's scope exactly: **reward events only**; **integer
     `trial_id` only** (drops `null` and string markers, `bool` rejected);
     **single-run-scoped** (never auto-detects run boundaries; caller supplies a
     per-run file or a `ts` window). Joins `reward.trial_id == trial_index`,
     one-trial-to-many. Failed trials are skipped (left `None`); non-failed
     trials always get a list (empty if no records).

---

## Part C — Pilot traces (required, not just unit tests)

### `token_usage` pilot (Subtask 6)
Drove a realistic kernel `/query` response (token_usage as top-level sibling)
through the **real** `AssistantAgent.run()` → **real**
`MethodPipeline._run_naive_concat` → `PipelineResult` → `TrialResult` → JSON,
mocking only the `llm_chat` HTTP hop. Real numbers
`{prompt: 312, completion: 41, total: 353}` arrived intact at the final
persisted model.

### `policy_action` pilot (Subtask 8) — against REAL data
- **Inputs:** the real `<AIOS>/logs/policy_trials.jsonl` (324 records) + a
  `results_kernel_shared.json` built via the real Pydantic models +
  `ResultsWriter.write_json`, with `trial_index` 0–14 (trial 7 deliberately
  `failed=True`).
- **Command:** `join_policy_actions.py --results ... --policy-log
  <real jsonl> --since 1788467158 --until 1788468235 --output ...`
- **Result (real):** 133 non-reward (`select`) dropped, 11 outside the ts window
  (the manual `probe`/`trial-subtask3-verify` markers), **180 reward records
  joined across 15 trial_ids**; **14 trials enriched (≥1 action)**, 1 failed
  trial correctly skipped.
- **One concrete enriched record:** `trial_index=0` received **12** real
  `PolicyActionEntry`s across bandits `novelty_threshold`,
  `similarity_threshold`, `redundancy_threshold` (all `arm_index=0`,
  `reward=5.0`, real `memory_id`s e.g. `2413054b-...`).
- **Validation:** the enriched JSON re-validates against the strict
  `ExperimentResults` Pydantic model; the failed trial's `policy_action` stays
  `None`; the Subtask 6 `token_usage` field coexists unchanged.
- A control run without a ts window confirmed the string-marker exclusion
  (`dropped trial_id=str : 11`).

---

## Part D — Acceptance-criteria checklist

Live-path `token_usage`:
- [x] `AssistantAgent.run()` returns `token_usage` on every return path, read
      from the correct top-level sibling key; no other SDK file modified.
- [x] `PipelineResult` has an `Optional` `token_usage`, populated at every
      construction site with an agent-return dict.
- [x] `TrialResult.token_usage` is `Optional`, validates across None / full /
      partial dict; all four construction sites consistent; round-trips to the
      persisted JSON; pre-change-style construction still succeeds.

Standalone `policy_action` join:
- [x] `TrialResult.policy_action` added (additive, model-only). **No**
      `AssistantAgent`/`PipelineResult` change for this field (non-goal honored).
- [x] Standalone script, separate from the live loop, matching repo conventions.
- [x] Accepts an explicit single-run input (per-run file and/or `ts` window);
      never reads a multi-run file blindly or guesses boundaries.
- [x] Reward events only; integer `trial_id` only (null + string markers
      dropped).
- [x] Groups by `trial_id`, joins on `reward.trial_id == trial_index` against
      already-persisted `TrialResult` JSON, writes an enriched copy (chosen:
      **new `--output` file**, not in-place).
- [x] Real pilot shows ≥1 correctly enriched `TrialResult` end-to-end.

Global non-goals:
- [x] **No AIOS repo changes** (`policy_trials.jsonl` read-only; AIOS working
      tree clean).
- [x] **No Cerebrum SDK changes** beyond the `AssistantAgent.run()` consumption
      of an existing key (`communication.py`/`apis.py` untouched).
- [x] **Additive-only** schema changes throughout.
- [x] **Deviations reported, not silently resolved** (see below).

### What was possible vs. structurally limited (policy_action)
- **Possible (shipped):** reward-event attribution — for each trial, which
  bandit/arm was credited, the reward value, and the `memory_id`. Correct and
  piloted against real data.
- **Structurally limited (documented, not worked around):**
  - **`select`-event (decision-side) linkage** — which arm was *chosen*
    pre-outcome, with its `gate`/`value`/`context` — is **not** joinable: those
    records always carry `trial_id: null` because the harness never threads
    `trial_index` into add/retrieve metadata. The script emits an explicit note
    about this on every run.
  - **Cross-run disambiguation** — integer `trial_id`s restart per run and
    neither artifact carries a run id / user_id, so multi-run joins would
    collide. Mitigated by *requiring* single-run-scoped input; not solved,
    because no reliable in-file run boundary exists.

---

## Deviations from the master prompt (reported plainly)

1. **`TrialResult` has no `trial_id`** — the field is `trial_index`. The
   binary "trial_id matches / doesn't" framing didn't fit; resolved by the
   Subtask 7 scoped GO (reward-only, single-run).
2. **`LLMResponse.token_usage` already exists** as a model field; it's just
   never populated on the live path (raw-dict return). No SDK model change was
   needed to *hold* the value.
3. **Four `TrialResult` construction sites**, not one — all accounted for.
4. **`policy_trials.jsonl` schema** is an `event`-discriminated union, not the
   flat shape the brief described; `trial_id` is nullable/mixed-type.

## How to run the join

```bash
python benchmarks/shared_memory/join_policy_actions.py \
    --results results/<run>/results_kernel_shared.json \
    --policy-log <AIOS>/logs/policy_trials.jsonl \
    --since <run_start_epoch> --until <run_end_epoch> \
    --output results/<run>/results_kernel_shared.enriched.json
```
Point `--policy-log` at a single run's slice, or use `--since`/`--until` to
scope a multi-run file to one run.
