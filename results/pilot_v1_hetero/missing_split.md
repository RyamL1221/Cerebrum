# memories_missing: withheld vs. lost

Computed after the pilot (Subtask 14) from its result files; the pre-registered analysis is `analysis.md`.

- **Withheld**: every row the missing writer stored was private, or had no policy (the private default), so the visibility rule kept it from the consumer.
- **Lost**: the writer stored a shared row and none reached the block (stored under another user id, or dropped by the threshold, the dedupe, the cap or the budget).

## Trials with a missing writer (both backends pooled)

| model | locus | level | n | missing_rate | withheld_rate | lost_rate |
|---|---|---|---|---|---|---|
| qwen | kernel | 0 | 60 | 0.00 | 0.00 | 0.00 |
| qwen | kernel | 1 | 60 | 0.20 | 0.20 | 0.00 |
| qwen | kernel | 2 | 60 | 0.53 | 0.53 | 0.00 |
| qwen | replicated | 0 | 60 | 0.00 | 0.00 | 0.00 |
| qwen | replicated | 1 | 60 | 0.50 | 0.20 | 0.30 |
| qwen | replicated | 2 | 60 | 0.87 | 0.53 | 0.43 |
| qwen | native | 0 | 60 | 0.00 | 0.00 | 0.00 |
| qwen | native | 1 | 60 | 0.45 | 0.20 | 0.25 |
| qwen | native | 2 | 60 | 0.75 | 0.43 | 0.42 |
| gpt4o | kernel | 0 | 60 | 0.00 | 0.00 | 0.00 |
| gpt4o | kernel | 1 | 60 | 0.20 | 0.20 | 0.00 |
| gpt4o | kernel | 2 | 60 | 0.53 | 0.53 | 0.00 |
| gpt4o | replicated | 0 | 60 | 0.00 | 0.00 | 0.00 |
| gpt4o | replicated | 1 | 60 | 0.50 | 0.20 | 0.30 |
| gpt4o | replicated | 2 | 60 | 0.87 | 0.53 | 0.43 |
| gpt4o | native | 0 | 60 | 0.00 | 0.00 | 0.00 |
| gpt4o | native | 1 | 60 | 0.45 | 0.20 | 0.25 |
| gpt4o | native | 2 | 60 | 0.75 | 0.43 | 0.42 |

## Missing writers by variant (both models and backends)

| locus | level | writer | writer_variant | consumer_variant | withheld | lost |
|---|---|---|---|---|---|---|
| kernel | 1 | profile_agent | V1 | - | 8 | 0 |
| kernel | 1 | profile_agent | V3 | - | 8 | 0 |
| kernel | 1 | task_agent | V1 | - | 4 | 0 |
| kernel | 1 | task_agent | V3 | - | 4 | 0 |
| kernel | 2 | profile_agent | V1 | - | 12 | 0 |
| kernel | 2 | profile_agent | V1 | V1 | 4 | 0 |
| kernel | 2 | profile_agent | V1 | V3 | 4 | 0 |
| kernel | 2 | profile_agent | V3 | - | 12 | 0 |
| kernel | 2 | profile_agent | V3 | V1 | 4 | 0 |
| kernel | 2 | profile_agent | V3 | V3 | 4 | 0 |
| kernel | 2 | task_agent | V1 | - | 12 | 0 |
| kernel | 2 | task_agent | V1 | V2 | 4 | 0 |
| kernel | 2 | task_agent | V3 | - | 12 | 0 |
| kernel | 2 | task_agent | V3 | V3 | 4 | 0 |
| replicated | 1 | profile_agent | - | V2 | 0 | 12 |
| replicated | 1 | profile_agent | - | V4 | 0 | 12 |
| replicated | 1 | profile_agent | V1 | - | 8 | 0 |
| replicated | 1 | profile_agent | V2 | - | 0 | 4 |
| replicated | 1 | profile_agent | V3 | - | 8 | 0 |
| replicated | 1 | task_agent | - | V2 | 0 | 12 |
| replicated | 1 | task_agent | - | V4 | 0 | 6 |
| replicated | 1 | task_agent | V1 | - | 4 | 0 |
| replicated | 1 | task_agent | V2 | - | 0 | 8 |
| replicated | 1 | task_agent | V3 | - | 4 | 0 |
| replicated | 2 | profile_agent | - | V2 | 0 | 8 |
| replicated | 2 | profile_agent | - | V4 | 0 | 8 |
| replicated | 2 | profile_agent | V1 | - | 12 | 0 |
| replicated | 2 | profile_agent | V1 | V1 | 4 | 0 |
| replicated | 2 | profile_agent | V1 | V3 | 4 | 0 |
| replicated | 2 | profile_agent | V2 | - | 0 | 12 |
| replicated | 2 | profile_agent | V2 | V4 | 0 | 4 |
| replicated | 2 | profile_agent | V3 | - | 12 | 0 |
| replicated | 2 | profile_agent | V3 | V1 | 4 | 0 |
| replicated | 2 | profile_agent | V3 | V3 | 4 | 0 |
| replicated | 2 | profile_agent | V4 | V2 | 0 | 4 |
| replicated | 2 | task_agent | - | V2 | 0 | 4 |
| replicated | 2 | task_agent | - | V4 | 0 | 4 |
| replicated | 2 | task_agent | V1 | - | 12 | 0 |
| replicated | 2 | task_agent | V1 | V2 | 4 | 0 |
| replicated | 2 | task_agent | V2 | - | 0 | 12 |
| replicated | 2 | task_agent | V2 | V4 | 0 | 4 |
| replicated | 2 | task_agent | V2 | V5 | 0 | 4 |
| replicated | 2 | task_agent | V3 | - | 12 | 0 |
| replicated | 2 | task_agent | V3 | V3 | 4 | 0 |
| replicated | 2 | task_agent | V4 | V2 | 0 | 4 |
| replicated | 2 | task_agent | V4 | V4 | 0 | 2 |
| native | 1 | profile_agent | - | V2 | 0 | 12 |
| native | 1 | profile_agent | - | V4 | 0 | 6 |
| native | 1 | profile_agent | V1 | - | 8 | 0 |
| native | 1 | profile_agent | V2 | - | 0 | 4 |
| native | 1 | profile_agent | V3 | - | 8 | 0 |
| native | 1 | task_agent | - | V2 | 0 | 12 |
| native | 1 | task_agent | - | V4 | 0 | 6 |
| native | 1 | task_agent | V1 | - | 4 | 0 |
| native | 1 | task_agent | V2 | - | 0 | 8 |
| native | 1 | task_agent | V3 | - | 4 | 0 |
| native | 2 | profile_agent | - | V2 | 0 | 8 |
| native | 2 | profile_agent | - | V4 | 0 | 4 |
| native | 2 | profile_agent | V1 | - | 12 | 0 |
| native | 2 | profile_agent | V1 | V1 | 4 | 0 |
| native | 2 | profile_agent | V2 | - | 0 | 12 |
| native | 2 | profile_agent | V2 | V4 | 0 | 4 |
| native | 2 | profile_agent | V3 | - | 12 | 0 |
| native | 2 | profile_agent | V3 | V1 | 4 | 0 |
| native | 2 | profile_agent | V4 | V2 | 0 | 4 |
| native | 2 | task_agent | - | V2 | 0 | 4 |
| native | 2 | task_agent | - | V4 | 0 | 2 |
| native | 2 | task_agent | V1 | - | 12 | 0 |
| native | 2 | task_agent | V1 | V2 | 4 | 0 |
| native | 2 | task_agent | V2 | - | 0 | 12 |
| native | 2 | task_agent | V2 | V4 | 0 | 4 |
| native | 2 | task_agent | V2 | V5 | 0 | 4 |
| native | 2 | task_agent | V3 | - | 12 | 0 |
| native | 2 | task_agent | V4 | V2 | 0 | 4 |
| native | 2 | task_agent | V4 | V4 | 0 | 2 |
