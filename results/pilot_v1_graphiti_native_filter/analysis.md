## Pairing and completeness

- 2 different commit pairs

## Cells

| model | locus | backend | level | n | failed | profile | task | integration | leak_rate | missing_rate | facts_in_block |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | 0 | 30 | 0 | 3.90 | 4.17 | 3.83 | 0.00 | 0.03 | 0.77 |
| qwen | kernel | graphiti | 2 | 30 | 0 | 3.20 | 3.40 | 2.77 | 0.00 | 0.53 | 0.53 |
| qwen | native | graphiti | 0 | 30 | 0 | 3.83 | 4.13 | 3.77 | 0.00 | 0.07 | 0.72 |
| qwen | native | graphiti | 2 | 30 | 0 | 2.57 | 2.73 | 1.93 | 0.10 | 0.80 | 0.37 |
| qwen | replicated | graphiti | 0 | 30 | 0 | 3.70 | 4.10 | 3.70 | 0.00 | 0.03 | 0.72 |
| qwen | replicated | graphiti | 2 | 30 | 0 | 2.47 | 2.63 | 1.77 | 0.00 | 0.87 | 0.35 |

## Cost and latency (per user)

| model | locus | level | n | v2_trials | backend_calls | backend_usd | total_usd | latency_s |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | 0 | 30 |  | 17.70 | 0.0936 | 0.0936 | 27.66 |
| qwen | kernel | 2 | 30 |  | 15.73 | 0.0847 | 0.0847 | 30.08 |
| qwen | native | 0 | 30 | 0 | 18.03 | 0.0950 | 0.0950 | 21.06 |
| qwen | native | 2 | 30 | 12 | 13.70 | 0.0762 | 0.0762 | 16.60 |
| qwen | replicated | 0 | 30 | 0 | 19.23 | 0.1004 | 0.1004 | 21.77 |
| qwen | replicated | 2 | 30 | 12 | 11.27 | 0.0626 | 0.0626 | 17.35 |

`v2_trials`: an agent locus's trials with a V2 (identity) variant. A harness before Subtask 16's fix (`pipeline.trial_backend_usage`) did not count the backend calls a V2 agent tagged with its rewritten id: in a cell it recorded, with `v2_trials` > 0, `backend_calls` and the USD are lower bounds.

## Kernel − replicated and kernel − native (mean [95% CI])

### qwen: kernel − replicated

| dimension | H0 | H2 | H2−H0 |
|---|---|---|---|
| profile | +0.20 [-0.03, +0.43] | +0.73 [+0.23, +1.23] | +0.53 [+0.11, +0.96] |
| task | +0.07 [-0.17, +0.31] | +0.77 [+0.30, +1.23] | +0.70 [+0.16, +1.24] |
| integration | +0.13 [-0.12, +0.39] | +1.00 [+0.57, +1.43] | +0.87 [+0.40, +1.33] |

### qwen: kernel − native

| dimension | H0 | H2 | H2−H0 |
|---|---|---|---|
| profile | +0.07 [-0.17, +0.31] | +0.63 [+0.09, +1.17] | +0.57 [+0.01, +1.12] |
| task | +0.03 [-0.20, +0.26] | +0.67 [+0.10, +1.23] | +0.63 [+0.05, +1.22] |
| integration | +0.07 [-0.17, +0.31] | +0.83 [+0.34, +1.32] | +0.77 [+0.21, +1.33] |

## Readings (reported, not required)

`h0_tie`: the H = 0 interval holds 0. `same_direction`: the H = 2 mean has the sign of the pilot's H = 2 mean in every scope (pooled, Mem0, in-house; Subtask 11).

| model | vs | dimension | H0 | h0_tie | H2 | pilot H2 | same_direction |
|---|---|---|---|---|---|---|---|
| qwen | replicated | profile | +0.20 [-0.03, +0.43] | True | +0.73 [+0.23, +1.23] | inhouse +0.70, mem0 +0.77, pooled +0.73 | True |
| qwen | replicated | integration | +0.13 [-0.12, +0.39] | True | +1.00 [+0.57, +1.43] | inhouse +0.77, mem0 +0.87, pooled +0.82 | True |
| qwen | native | profile | +0.07 [-0.17, +0.31] | True | +0.63 [+0.09, +1.17] | inhouse +0.60, mem0 +0.50, pooled +0.55 | True |
| qwen | native | integration | +0.07 [-0.17, +0.31] | True | +0.83 [+0.34, +1.32] | inhouse +0.63, mem0 +0.60, pooled +0.62 | True |
