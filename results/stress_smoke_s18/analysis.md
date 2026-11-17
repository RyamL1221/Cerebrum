# Stress dimensions: judge-free report

## Checks that must hold

| check | holds | detail |
|---|---|---|
| every failed trial is a write the backend stored nothing for | True | 0 such trials |
| kernel inhouse n6conc: no probe reads a late write the kernel accepted before it, and no barrier wait times out | True | 0 covered late writes, 0 timeouts |
| kernel inhouse n6flood10: at most max_writes less its write events accepted per flooding turn, and no reference writer's write rejected | True | turns over the bound per user [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| kernel inhouse n6flood50: at most max_writes less its write events accepted per flooding turn, and no reference writer's write rejected | True | turns over the bound per user [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |

## Pass rates per cell

| model | locus | backend | condition | trials | failed | deletion | privacy | recall | recency | contradiction | writes_without_row |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | n6conc | 30 | 0 | 29/30 [0.83, 0.99] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 0 |
| qwen | kernel | inhouse | n6flood10 | 30 | 0 | 29/30 [0.83, 0.99] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 0 |
| qwen | kernel | inhouse | n6flood50 | 30 | 0 | 29/30 [0.83, 0.99] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 0 |
| qwen | kernel | inhouse | n6h0 | 30 | 0 | 29/30 [0.83, 0.99] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 0 |
| qwen | native | inhouse | n6conc | 30 | 0 | 21/30 [0.52, 0.83] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 10/30 [0.19, 0.51] | 17/30 [0.39, 0.73] | 0 |
| qwen | native | inhouse | n6flood10 | 30 | 0 | 24/30 [0.63, 0.90] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 18/30 [0.42, 0.75] | 19/30 [0.46, 0.78] | 0 |
| qwen | native | inhouse | n6flood50 | 30 | 0 | 24/30 [0.63, 0.90] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 20/30 [0.49, 0.81] | 16/30 [0.36, 0.70] | 0 |
| qwen | native | inhouse | n6h0 | 30 | 0 | 21/30 [0.52, 0.83] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 10/30 [0.19, 0.51] | 18/30 [0.42, 0.75] | 0 |
| qwen | replicated | inhouse | n6conc | 30 | 0 | 29/30 [0.83, 0.99] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 28/30 [0.79, 0.98] | 0 |
| qwen | replicated | inhouse | n6flood10 | 30 | 0 | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 0 |
| qwen | replicated | inhouse | n6flood50 | 30 | 0 | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 0 |
| qwen | replicated | inhouse | n6h0 | 30 | 0 | 29/30 [0.83, 0.99] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 30/30 [0.89, 1.00] | 0 |

## Agent count: H = 0 across N

(none)

## Agent count: H = 2 against H = 0

(none)

## Concurrency (n6conc against n6h0)

| model | locus | backend | probes | with_writes_in_flight | with_late_writes | late_writes | late_covered | late_rows | uncovered_writes | timing_misses | stale_reads | late_forgets | barrier_wait_ms_median | barrier_wait_ms_max | barrier_timeouts | memories_missing_timing | memories_missing | deletion | privacy | recall | recency | contradiction |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | 180 | 180 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 114 | 248 | 0 | 0 | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | native | inhouse | 180 | 180 | 180 | 498 | 498 | 432 | 0 | 1 | 10 | 6 | 0 | 0 | 0 | 5 | -0.03 [-0.10, +0.03] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) |
| qwen | replicated | inhouse | 180 | 180 | 180 | 552 | 552 | 432 | 0 | 0 | 2 | 0 | 0.419 | 7.43 | 0 | 4 | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) |

## Load

(none)

## Faults (against n6h0)

| model | locus | backend | fault | users | failed | faulty_agents | misfiled_rows | identity_overridden | cross_user_rows | private_rows_from_others | flood_rows_stored | flood_writes_accepted | flood_sessions_over_bound | flood_rows_in_block_per_probe | quota_rejected | memories_missing | profile_facts_in_block | deletion | privacy | recall | recency | contradiction |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | flood10 | 30 | 0 | {'calendar_agent': 7, 'profile_agent': 8, 'task_agent': 5, 'docs_agent': 7, 'travel_agent': 3} | 0 | 0 | 0 | 0 | 90 | 94 | 0 | 1.71 | {'duplicate': 163, 'quota': 273} | -0.03 [-0.24, +0.17] | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | kernel | inhouse | flood50 | 30 | 0 | {'calendar_agent': 7, 'profile_agent': 6, 'task_agent': 5, 'docs_agent': 7, 'travel_agent': 5} | 0 | 0 | 0 | 0 | 93 | 98 | 0 | 1.82 | {'duplicate': 723, 'quota': 1829} | -0.03 [-0.24, +0.17] | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | native | inhouse | flood10 | 30 | 0 | {'calendar_agent': 7, 'profile_agent': 8, 'task_agent': 5, 'docs_agent': 7, 'travel_agent': 3} | 0 | 0 | 0 | 0 | 511 | 530 | 53 | 4.33 | {} | +0.60 [+0.23, +0.97] | -0.36 [-0.54, -0.18] | -0/+3 (p 0.25) | -0/+0 (p 1) | -0/+0 (p 1) | -3/+11 (p 0.057) | -2/+3 (p 1) |
| qwen | native | inhouse | flood50 | 30 | 0 | {'calendar_agent': 7, 'profile_agent': 6, 'task_agent': 5, 'docs_agent': 7, 'travel_agent': 5} | 0 | 0 | 0 | 0 | 2510 | 2650 | 53 | 7.06 | {} | +1.47 [+1.03, +1.90] | -0.69 [-0.86, -0.52] | -0/+3 (p 0.25) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+11 (p 0.0063) | -5/+3 (p 0.73) |
| qwen | replicated | inhouse | flood10 | 30 | 0 | {'calendar_agent': 7, 'profile_agent': 8, 'task_agent': 5, 'docs_agent': 7, 'travel_agent': 3} | 0 | 0 | 0 | 0 | 503 | 530 | 53 | 6.43 | {} | +0.60 [+0.21, +0.99] | -0.23 [-0.38, -0.07] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | replicated | inhouse | flood50 | 30 | 0 | {'calendar_agent': 7, 'profile_agent': 6, 'task_agent': 5, 'docs_agent': 7, 'travel_agent': 5} | 0 | 0 | 0 | 0 | 2479 | 2650 | 53 | 10 | {} | +1.03 [+0.57, +1.50] | -0.53 [-0.72, -0.34] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
