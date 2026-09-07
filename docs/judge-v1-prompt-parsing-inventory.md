# v1 Judge — Prompt, Parsing & Score-Field Inventory

Investigation-only inventory (Subtask 1). No code changed. Purpose: pin the
exact locations of the current v1 holistic judge prompt, the judge call site,
the parsing logic, the three score-field definitions, and every consumer of
those fields — so later subtasks are edits to known lines, not guesses.

All paths are relative to the repo root. Line numbers reflect the files as read
during this investigation and may shift by a line or two if the files are
edited before the next subtask; re-grep the anchors below if in doubt.

## 1. Prompt template

- **File:** `benchmarks/shared_memory/judge.py`
- **Builder:** `LLMJudge._build_judge_prompt()` — defined at `judge.py:122`.
  - Assembles a single `user` message (`user_content`, `judge.py:141`–`199`)
    plus a `system` message (`judge.py:201`–`214`).
  - The scoring rubric text lives inline in `user_content`: profile/task/
    integration each on a 1–5 scale, content-based (explicitly "regardless of
    response length"), no `generic_penalty`.
  - The required output contract is stated at `judge.py:195`–`198`: a single
    JSON object with exactly the keys `profile_usage_score`,
    `task_usage_score`, `integration_score` (ints 1–5) plus the three
    `*_reasoning` string keys. **This confirms v1 asks for all three
    dimensions in ONE call, as a single JSON blob — not one call per
    dimension, and not a bare integer.**
  - The `system` message (`judge.py:201`–`214`) forces "ONLY a valid JSON
    object" and injects the shared-memory awareness note.

## 2. Judge call site + parsing

- **File:** `benchmarks/shared_memory/judge.py`
- **Method that sends the prompt and parses the result:** `LLMJudge.evaluate()`
  — defined at `judge.py:216`.
  - **Send:** `llm_chat_with_json_output(...)` at `judge.py:263`, passing a
    `response_format` `json_schema` (built at `judge.py:228`–`254`) that
    requires the same 6 keys. `self.llms` selects the judge model (GPT-5.4 in
    the threshold search / default reporting).
  - **Token usage:** captured from the top-level `token_usage` sibling of the
    `/query` body at `judge.py:269` (and re-captured on the fallback path at
    `judge.py:289`).
  - **Fallback:** if `response_message` is `None`, retries with plain
    `llm_chat` at `judge.py:280`–`291` (kernel may not honor `response_format`
    passthrough).
  - **Parse:** `judge.py:301`–`325`.
    - If the raw is a str, `json.loads`; on `JSONDecodeError`, falls back to
      `_extract_json_from_text()` (`judge.py:101`, first `{` … last `}`).
    - Key normalization: if the dict already has all three `*_score` keys it is
      used as-is (`judge.py:318`); otherwise `_normalize_judge_keys()`
      (`judge.py:61`) canonicalizes CamelCase / Title Case / hyphenated /
      UPPER_SNAKE / `_score`-suffixed variants via `_canonicalize_key()`
      (`judge.py:33`) and `_CANONICAL_MAP` (`judge.py:52`).
    - Scores clamped to [1,5] by `_clamp_score()` (`judge.py:88`) and packed
      into a `JudgeScores` at `judge.py:332`–`340`.
  - **Failure returns:** every early-out returns a `JudgeScores(...)` (usually
    with all scores `None`, token_usage preserved) rather than raising —
    `judge.py:299, 309, 314, 329, 345`.

- **Wrapper actually used by the harness:** `HybridJudge.evaluate()` —
  `judge.py:429`. Averages deterministic keyword scores (`keyword_score()`
  `judge.py:378`, `_extract_keywords()` `judge.py:349`) with the LLM scores.
  The **orchestrator instantiates `HybridJudge`, not `LLMJudge` directly**
  (`run_evaluation.py:283`). So the "judge" seen by trials is the hybrid;
  `LLMJudge` is its `.llm_judge` member.

- **Orchestrator call site:** `EvaluationOrchestrator` in
  `benchmarks/shared_memory/run_evaluation.py`:
  - Judge constructed at `run_evaluation.py:283` (`HybridJudge(llms=self.judge_llms)`),
    kernel URL patched at `run_evaluation.py:285`.
  - `judge_llms` resolved from `--judge-model` (arg at `run_evaluation.py:206`,
    parsed at `run_evaluation.py:882`), falling back to the assistant model
    (`run_evaluation.py:273`).
  - `self.judge.evaluate(...)` called per trial at `run_evaluation.py:438`
    (inside a try/except that degrades to an empty `JudgeScores()`).

- **`pipeline.py` does NOT call the judge.** The pipeline
  (`AgentPipeline` / `MethodPipeline`) only produces the assistant response +
  retrieval log; judging is entirely orchestrator-side. (Drift note: the plan
  listed `pipeline.py` as a judge call-site candidate — it is not.)

## 3. Score-field definitions

Two independent definitions of the same three fields:

- **`JudgeScores`** (judge output) — `benchmarks/shared_memory/models.py:90`:
  - `profile_usage_score` / `task_usage_score` / `integration_score`, each
    `Optional[int] = None` (`models.py:93`–`95`).
  - Also carries a legacy `generic_penalty: Optional[bool]` (`models.py:97`,
    unused by current prompt), the three `*_reasoning` strings, and
    `token_usage`.
- **`TrialResult`** (persisted per-trial record) —
  `benchmarks/shared_memory/models.py:163`:
  - Re-declares `profile_usage_score` / `task_usage_score` /
    `integration_score` as `Optional[int] = None` (`models.py:167`–`169`).
  - These are copied from `JudgeScores` when the `TrialResult` is built at
    `run_evaluation.py:556`–`558`.

## 4. Every consumer of the three score fields

### Written (producers)
- `judge.py` — builds `JudgeScores` in `LLMJudge.evaluate` (`judge.py:332`) and
  `HybridJudge.evaluate` (`judge.py:455`–`457`).
- `run_evaluation.py`:
  - Reward computation `reward_value` = mean of the non-null scores,
    `run_evaluation.py:463`–`469` (this is the canonical per-trial reward
    formula the rest of the harness mirrors).
  - `trial_metadata` dict for `report_reward`, `run_evaluation.py:476`–`478`.
  - `TrialResult(...)` construction, `run_evaluation.py:556`–`558`.

### Read (consumers)
- **`benchmarks/shared_memory/results.py`** — the ONLY in-harness statistical
  consumer:
  - Summary aggregation (mean/std/min/max via `SummaryStatistics`):
    `results.py:65`–`67`.
  - Flat CSV columns: header at `results.py:131`–`133`, row values at
    `results.py:156`–`158`.
- **`benchmarks/shared_memory/threshold_search.py`** — reads the three fields
  out of the persisted `results_*.json` to compute each trial's reward:
  `_JUDGE_SCORE_FIELDS` (`threshold_search.py:714`), `_trial_reward()`
  (`threshold_search.py:770`+), `aggregate_judge_scores()`. Mirrors the
  `run_evaluation.py:463`–`469` formula.
- **`benchmarks/human_rating/`** (downstream, reads finalized result JSON):
  - `trial_loader.py:185`–`233` — extracts all three, uses `integration_score`
    as the `judge_score`.
  - `validation.py:32, 99, 150, 155, 189` — schema/consistency checks
    (including `judge_score == integration_score`).
  - `sampling.py:84` — same equality invariant.
  - `compile_ratings.py:52`–`54, 345, 396`–`398` — answer-key fields + invariant.
  - `artifact_audit.py:56`–`58, 132`–`134, 202`–`215, 342` — presence audit of
    the three fields in candidate artifacts.
  - `schemas.py` — `select_judge_score()` rule (profile→profile_usage_score,
    task→task_usage_score) per the project overview.

## 5. Assumption drift vs. the plan — called out

1. **No Welch/MWU/bootstrap significance pipeline exists.** A repo-wide search
   for `welch|mann-whitney|mwu|bootstrap|ttest|scipy.stats` found no
   statistical-testing code that consumes these fields. Downstream stats stop
   at `results.py` (mean/std/min/max) and the CSV; anything more (significance
   tests, notebooks) is not in this repo. Later subtasks assuming such a
   pipeline should treat it as out of scope / not present.
2. **`join_policy_actions.py` is NOT a consumer of the three score fields.** It
   only reads/writes `TrialResult.policy_action` from `policy_trials.jsonl`
   reward events (`join`s on `reward.trial_id == trial_index`). It never reads
   `profile_usage_score` / `task_usage_score` / `integration_score`.
3. **`pipeline.py` does not run the judge** (see §2) — judging is
   orchestrator-side only.
4. **v1 is already a single-call, single-JSON-blob, three-dimension judge** —
   not per-dimension calls and not a bare integer. The parsing already tolerates
   free-form JSON extraction and key-format variants.
5. **The effective judge is `HybridJudge`** (keyword + LLM average), not raw
   `LLMJudge`. Any change to the LLM prompt/parsing flows through
   `HybridJudge.evaluate`'s averaging (`judge.py:449`–`457`) before landing in a
   `TrialResult`.
6. **`policy_trials.jsonl`** stores adaptive-policy reward records, NOT the
   judge scores; the judge scores are persisted only in the results JSON/CSV
   (via `results.py`) and re-derived into `report_reward` metadata.
