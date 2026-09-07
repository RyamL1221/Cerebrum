# Decomposed Judge Rubric (v2)

Source spec for the v2 decomposed LLM judge. This is the authoritative wording
for the criteria implemented in `LLMJudge._build_judge_prompt_v2()`
(`benchmarks/shared_memory/judge.py`). Committed to the repo so the criteria
text cannot drift or be re-improvised on a future re-read.

## Why decomposed

The v1 judge asks for a single holistic 1–5 per dimension. Weak/inconsistent
judges tend to default to a high score. The v2 rubric decomposes each dimension
into five binary sub-criteria: the model marks each 1 (clearly and fully
satisfied) or 0, and the dimension score is the **sum** of its five criteria
(an integer 0–5). This forces the model to justify a high score rather than
awarding a 5 by default.

Still a **single LLM call** covering all three dimensions (matching v1's
architecture and the token-cost tradeoff), not three separate calls.

## Dimensions and criteria (verbatim)

### Profile Usage

1. **Specific reference** — names a concrete fact from the synthetic profile,
   not a generic acknowledgment.
2. **Accuracy** — every profile fact referenced is stated correctly.
3. **Material use** — a referenced fact materially shapes the advice, not just
   mentioned.
4. **No clear omission** — no directly relevant profile fact present in context
   is left out.
5. **Goal-directed framing** — ties a profile fact to the user's own stated
   goals/preferences.

### Task Usage

1. **Specific reference** — names a concrete task-context fact (project,
   blocker, deadline, milestone, next step).
2. **Accuracy** — every task fact referenced is correct.
3. **Actionable use** — a referenced fact produces a concrete recommendation,
   not a restatement.
4. **No clear omission** — no directly relevant task fact present in context is
   left out.
5. **Status-aware** — distinguishes done vs. open based on task memory.

### Integration

1. **Joint reference** — a recommendation draws on a profile fact and a task
   fact together in the same sentence/reasoning step.
2. **Causal coherence** — the profile↔task connection is logically stated, not
   just adjacent.
3. **Single coherent answer** — reads as one prioritized answer, not a bulleted
   recitation.
4. **Personalized prioritization** — ordering/weighting is shaped by profile
   info, not identical to a context-free answer.
5. **No redundancy** — no memory fact restated verbatim as padding.

## Judge instructions

- Award 1 point per criterion only if it is clearly and fully satisfied;
  otherwise award 0. Do not award a 5 by default; a 5 requires all five criteria
  to hold. The dimension score is the sum of its five criteria (0–5).
- For the Profile and Task dimensions: **Do not let a strong performance on one
  criterion inflate another.**
- For the Integration dimension: **it should be the hardest dimension to max
  out, since it requires both Profile and Task criteria to be partially met
  before Integration criteria can apply at all.**
- Provide a one-sentence justification for each criterion scored 0
  (justification is required only for 0-scored criteria; it may be omitted for
  criteria scored 1).

## Output contract

Respond with ONLY a JSON object (no markdown fences, no explanation, no text
before or after). Exactly three top-level keys — `profile_usage`, `task_usage`,
`integration` — each an object of this shape:

```json
{
  "profile_usage": {
    "criteria": {"1": 0, "2": 1, "3": 0, "4": 1, "5": 0},
    "score": 2,
    "justification": {"1": "…", "3": "…", "5": "…"}
  },
  "task_usage":   { "criteria": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}, "score": 0, "justification": {"1": "…"} },
  "integration":  { "criteria": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}, "score": 0, "justification": {"1": "…"} }
}
```

`justification` need only cover the criteria scored 0.

## Compatibility note — do not merge v1 and v2 scores

v1 (holistic 1–5) and v2 (decomposed sum 0–5) scores are **not** on the same
scale or from the same instrument and must never be pooled into one table,
aggregated together, or averaged into a single reward. Every score carries a
`rubric_version` tag (`"v1"` / `"v2"`); aggregation, CSV output, and reward
calculation partition by that tag. See `docs/judge-v1-prompt-parsing-inventory.md`
for the v1 side and `benchmarks/shared_memory/results.py` for the enforcement.
