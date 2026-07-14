# Human Rating Evaluation Harness

A three-phase workflow for human evaluation of benchmark trials, designed to measure human-judge agreement and intra-rater consistency for the shared memory personalization benchmark.

## Workflow

### Phase 1: Sample & Blind

```bash
python -m benchmarks.human_rating.sample_and_blind \
    --results-dir results/post_fix_gpt4o/ \
    --run-name gpt4o_human_eval \
    --seed 12345
```

Produces:
- `human_rating_runs/<run_name>/rater/rating_queue.json` — blinded items for rating
- `human_rating_runs/<run_name>/private/answer_key.json` — unblinded metadata (never shown to rater)

### Phase 2: Rate

```bash
python -m benchmarks.human_rating.rate \
    --queue human_rating_runs/gpt4o_human_eval/rater/rating_queue.json
```

Interactive CLI that presents items one at a time. Ratings are recorded to `ratings.jsonl` (append-only, crash-safe). Supports resumption.

### Phase 3: Compile

```bash
python -m benchmarks.human_rating.compile_ratings \
    --run-dir human_rating_runs/gpt4o_human_eval/
```

Joins ratings with the answer key and produces:
- `compiled/item_level_results.csv`
- `compiled/method_question_type_summary.csv`
- `compiled/human_judge_agreement.json`
- `compiled/intra_rater_consistency.json`

## Design Principles

- **Blinding:** The rating CLI never sees method, model, question type, trial ID, judge score, or duplicate status.
- **Immutability:** Once a rating is submitted, it cannot be edited or overwritten.
- **Process isolation:** The `rate` command operates correctly even when `private/` is unavailable.
- **Reproducibility:** All randomness is seeded and recorded in the answer key.
- **Consistency measurement:** 6 duplicate items are inserted to measure intra-rater reliability.

## Directory Layout

```
human_rating_runs/
└── <run_name>/
    ├── rater/
    │   ├── rating_queue.json     (blinded, rater-visible)
    │   └── ratings.jsonl         (append-only session)
    ├── private/
    │   └── answer_key.json       (preprocessing + compilation only)
    └── compiled/
        ├── item_level_results.csv
        ├── method_question_type_summary.csv
        ├── human_judge_agreement.json
        └── intra_rater_consistency.json
```

## Scoring Rubric

Uses the same 1–5 rubric as the GPT-5.4 automated judge (see `rubric.py`):

| Score | Meaning |
|-------|---------|
| 5 | Excellent personalization — references multiple profile + task attributes, seamlessly integrated |
| 4 | Good — references most attributes with minor gaps |
| 3 | Moderate — references some attributes but misses key ones |
| 2 | Weak — vague/incorrect references |
| 1 | No personalization — entirely generic |

## Tests

```bash
python benchmarks/human_rating/tests/test_schemas.py
```
