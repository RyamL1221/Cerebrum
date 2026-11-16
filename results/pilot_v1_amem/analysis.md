## Pairing and completeness

- 180 trials expected; every cell complete, paired (same inputs and variants per user), on the schedule, at one clean commit pair.

## Cells

| model | locus | backend | level | n | failed | profile | task | integration | leak_rate | missing_rate | facts_in_block |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | 0 | 30 | 0 | 3.07 | 5.00 | 3.07 | 0.00 | 0.00 | 1.00 |
| qwen | kernel | amem | 2 | 30 | 0 | 3.10 | 4.10 | 2.67 | 0.00 | 0.53 | 0.68 |
| qwen | native | amem | 0 | 30 | 0 | 3.13 | 4.93 | 3.20 | 0.00 | 0.00 | 1.00 |
| qwen | native | amem | 2 | 30 | 0 | 2.60 | 3.27 | 2.17 | 0.10 | 0.73 | 0.51 |
| qwen | replicated | amem | 0 | 30 | 0 | 3.07 | 5.00 | 3.07 | 0.00 | 0.00 | 1.00 |
| qwen | replicated | amem | 2 | 30 | 0 | 2.43 | 2.97 | 1.97 | 0.00 | 0.87 | 0.38 |

## Cost and latency (per user)

| model | locus | level | n | v2_trials | backend_calls | backend_usd | total_usd | latency_s |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | 0 | 30 |  | 5.00 | 0.0144 | 0.0144 | 19.42 |
| qwen | kernel | 2 | 30 |  | 5.00 | 0.0143 | 0.0143 | 17.39 |
| qwen | native | 0 | 30 | 0 | 5.00 | 0.0145 | 0.0145 | 18.75 |
| qwen | native | 2 | 30 | 12 | 4.60 | 0.0122 | 0.0122 | 13.78 |
| qwen | replicated | 0 | 30 | 0 | 5.00 | 0.0145 | 0.0145 | 17.63 |
| qwen | replicated | 2 | 30 | 12 | 4.60 | 0.0122 | 0.0122 | 12.93 |

`v2_trials`: an agent locus's trials with a V2 (identity) variant. A harness before Subtask 16's fix (`pipeline.trial_backend_usage`) did not count the backend calls a V2 agent tagged with its rewritten id: in a cell it recorded, with `v2_trials` > 0, `backend_calls` and the USD are lower bounds.

## Kernel − replicated and kernel − native (mean [95% CI])

### qwen: kernel − replicated

| dimension | H0 | H2 | H2−H0 |
|---|---|---|---|
| profile | +0.00 [-0.26, +0.26] | +0.67 [+0.11, +1.22] | +0.67 [+0.01, +1.32] |
| task | +0.00 [+0.00, +0.00] | +1.13 [+0.51, +1.76] | +1.13 [+0.51, +1.76] |
| integration | +0.00 [-0.24, +0.24] | +0.70 [+0.26, +1.14] | +0.70 [+0.14, +1.26] |

### qwen: kernel − native

| dimension | H0 | H2 | H2−H0 |
|---|---|---|---|
| profile | -0.07 [-0.49, +0.36] | +0.50 [-0.08, +1.08] | +0.57 [-0.10, +1.23] |
| task | +0.07 [-0.03, +0.16] | +0.83 [+0.22, +1.45] | +0.77 [+0.16, +1.37] |
| integration | -0.13 [-0.48, +0.22] | +0.50 [+0.00, +1.00] | +0.63 [+0.06, +1.21] |

## Readings (reported, not required)

`h0_tie`: the H = 0 interval holds 0. `same_direction`: the H = 2 mean has the sign of the pilot's H = 2 mean in every scope (pooled, Mem0, in-house; Subtask 11).

| model | vs | dimension | H0 | h0_tie | H2 | pilot H2 | same_direction |
|---|---|---|---|---|---|---|---|
| qwen | replicated | profile | +0.00 [-0.26, +0.26] | True | +0.67 [+0.11, +1.22] | inhouse +0.70, mem0 +0.77, pooled +0.73 | True |
| qwen | replicated | integration | +0.00 [-0.24, +0.24] | True | +0.70 [+0.26, +1.14] | inhouse +0.77, mem0 +0.87, pooled +0.82 | True |
| qwen | native | profile | -0.07 [-0.49, +0.36] | True | +0.50 [-0.08, +1.08] | inhouse +0.60, mem0 +0.50, pooled +0.55 | True |
| qwen | native | integration | -0.13 [-0.48, +0.22] | True | +0.50 [+0.00, +1.00] | inhouse +0.63, mem0 +0.60, pooled +0.62 | True |
