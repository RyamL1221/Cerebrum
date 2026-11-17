# Stress dimensions: judge-free report

## Checks that must hold

| check | holds | detail |
|---|---|---|
| every failed trial is a write the backend stored nothing for | True | 6 such trials |
| N = 12 runs end to end | True | 12 cells, 60 trials |
| in-house H = 0, kernel: the same outcomes at N = 3, 6 and 12, byte-equal blocks | True | 25/25 outcomes, 30/30 blocks |
| in-house H = 0, native: the same outcomes at N = 3, 6 and 12 | True | 25/25 outcomes, 30/30 blocks |
| in-house H = 0, replicated: the same outcomes at N = 3, 6 and 12, byte-equal blocks | True | 25/25 outcomes, 30/30 blocks |
| kernel inhouse n6conc: no probe reads a late write the kernel accepted before it, and no barrier wait times out | True | 0 covered late writes, 0 timeouts |
| kernel inhouse n6flood10: at most max_writes less its write events accepted per flooding turn, and no reference writer's write rejected | True | turns over the bound per user [0, 0, 0, 0, 0] |
| kernel inhouse n6flood50: at most max_writes less its write events accepted per flooding turn, and no reference writer's write rejected | True | turns over the bound per user [0, 0, 0, 0, 0] |
| kernel inhouse n6wrong_user: no row misfiled, and every faulty request records identity_overridden | True | misfiled [0, 0, 0, 0, 0] |
| kernel mem0 n6conc: no probe reads a late write the kernel accepted before it, and no barrier wait times out | True | 0 covered late writes, 0 timeouts |
| kernel mem0 n6flood10: at most max_writes less its write events accepted per flooding turn, and no reference writer's write rejected | True | turns over the bound per user [0, 0, 0, 0, 0] |
| kernel mem0 n6flood50: at most max_writes less its write events accepted per flooding turn, and no reference writer's write rejected | True | turns over the bound per user [0, 0, 0, 0, 0] |
| kernel mem0 n6wrong_user: no row misfiled, and every faulty request records identity_overridden | True | misfiled [0, 0, 0, 0, 0] |

## Pass rates per cell

| model | locus | backend | condition | trials | failed | deletion | privacy | recall | recency | contradiction | writes_without_row |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | n12h0 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | inhouse | n12h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 0 |
| qwen | kernel | inhouse | n3h0 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | inhouse | n3h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 4/5 [0.38, 0.96] | 4/5 [0.38, 0.96] | 0 |
| qwen | kernel | inhouse | n6conc | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | inhouse | n6flood10 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | inhouse | n6flood50 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | inhouse | n6h0 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | inhouse | n6h2 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 4/5 [0.38, 0.96] | 4/5 [0.38, 0.96] | 0 |
| qwen | kernel | inhouse | n6load1 | 16 | 0 | 15/16 [0.72, 0.99] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 0 |
| qwen | kernel | inhouse | n6load16 | 16 | 0 | 15/16 [0.72, 0.99] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 0 |
| qwen | kernel | inhouse | n6load4 | 16 | 0 | 15/16 [0.72, 0.99] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 0 |
| qwen | kernel | inhouse | n6missing_metadata | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 0 |
| qwen | kernel | inhouse | n6wrong_user | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | mem0 | n12h0 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | mem0 | n12h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 3/5 [0.23, 0.88] | 0 |
| qwen | kernel | mem0 | n3h0 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | mem0 | n3h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 2/5 [0.12, 0.77] | 4/5 [0.38, 0.96] | 0 |
| qwen | kernel | mem0 | n6conc | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | mem0 | n6flood10 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 4/5 [0.38, 0.96] | 0 |
| qwen | kernel | mem0 | n6flood50 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | mem0 | n6h0 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 0 |
| qwen | kernel | mem0 | n6h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | kernel | mem0 | n6load1 | 16 | 0 | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 11/16 [0.44, 0.86] | 16/16 [0.81, 1.00] | 0 |
| qwen | kernel | mem0 | n6load16 | 16 | 0 | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 13/16 [0.57, 0.93] | 16/16 [0.81, 1.00] | 0 |
| qwen | kernel | mem0 | n6load4 | 16 | 0 | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 16/16 [0.81, 1.00] | 12/16 [0.51, 0.90] | 15/16 [0.72, 0.99] | 0 |
| qwen | kernel | mem0 | n6missing_metadata | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 4/5 [0.38, 0.96] | 0 |
| qwen | kernel | mem0 | n6wrong_user | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 0 |
| qwen | native | inhouse | n12h0 | 5 | 0 | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | native | inhouse | n12h2 | 5 | 0 | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | native | inhouse | n3h0 | 5 | 0 | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | native | inhouse | n3h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 1/5 [0.04, 0.62] | 1/5 [0.04, 0.62] | 0 |
| qwen | native | inhouse | n6conc | 5 | 0 | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | native | inhouse | n6flood10 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 3/5 [0.23, 0.88] | 0 |
| qwen | native | inhouse | n6flood50 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 2/5 [0.12, 0.77] | 0 |
| qwen | native | inhouse | n6h0 | 5 | 0 | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | native | inhouse | n6h2 | 5 | 0 | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 0/5 [0.00, 0.43] | 2/5 [0.12, 0.77] | 0 |
| qwen | native | inhouse | n6missing_metadata | 5 | 0 | 3/5 [0.23, 0.88] | 3/5 [0.23, 0.88] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | native | inhouse | n6wrong_user | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 1/5 [0.04, 0.62] | 4/5 [0.38, 0.96] | 0 |
| qwen | native | mem0 | n12h0 | 5 | 2 | 3/3 [0.44, 1.00] | 3/3 [0.44, 1.00] | 0/3 [0.00, 0.56] | 0/3 [0.00, 0.56] | 0/3 [0.00, 0.56] | 2 |
| qwen | native | mem0 | n12h2 | 5 | 1 | 4/4 [0.51, 1.00] | 4/4 [0.51, 1.00] | 0/4 [0.00, 0.49] | 0/4 [0.00, 0.49] | 0/4 [0.00, 0.49] | 1 |
| qwen | native | mem0 | n3h0 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0 |
| qwen | native | mem0 | n3h2 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 1/5 [0.04, 0.62] | 0/5 [0.00, 0.43] | 1/5 [0.04, 0.62] | 0 |
| qwen | native | mem0 | n6conc | 5 | 1 | 4/4 [0.51, 1.00] | 4/4 [0.51, 1.00] | 0/4 [0.00, 0.49] | 0/4 [0.00, 0.49] | 0/4 [0.00, 0.49] | 1 |
| qwen | native | mem0 | n6flood10 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0 |
| qwen | native | mem0 | n6flood50 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0 |
| qwen | native | mem0 | n6h0 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0 |
| qwen | native | mem0 | n6h2 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0 |
| qwen | native | mem0 | n6missing_metadata | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0 |
| qwen | native | mem0 | n6wrong_user | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0/5 [0.00, 0.43] | 0 |
| qwen | replicated | inhouse | n12h0 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | inhouse | n12h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 0 |
| qwen | replicated | inhouse | n3h0 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | inhouse | n3h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | replicated | inhouse | n6conc | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | inhouse | n6flood10 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | inhouse | n6flood50 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | inhouse | n6h0 | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | inhouse | n6h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 2/5 [0.12, 0.77] | 3/5 [0.23, 0.88] | 0 |
| qwen | replicated | inhouse | n6missing_metadata | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 0 |
| qwen | replicated | inhouse | n6wrong_user | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 0 |
| qwen | replicated | mem0 | n12h0 | 5 | 1 | 4/4 [0.51, 1.00] | 4/4 [0.51, 1.00] | 4/4 [0.51, 1.00] | 3/4 [0.30, 0.95] | 4/4 [0.51, 1.00] | 1 |
| qwen | replicated | mem0 | n12h2 | 5 | 1 | 4/4 [0.51, 1.00] | 4/4 [0.51, 1.00] | 3/4 [0.30, 0.95] | 2/4 [0.15, 0.85] | 2/4 [0.15, 0.85] | 1 |
| qwen | replicated | mem0 | n3h0 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | mem0 | n3h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 1/5 [0.04, 0.62] | 3/5 [0.23, 0.88] | 0 |
| qwen | replicated | mem0 | n6conc | 5 | 0 | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 4/5 [0.38, 0.96] | 0 |
| qwen | replicated | mem0 | n6flood10 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 5/5 [0.57, 1.00] | 0 |
| qwen | replicated | mem0 | n6flood50 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 2/5 [0.12, 0.77] | 4/5 [0.38, 0.96] | 0 |
| qwen | replicated | mem0 | n6h0 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 4/5 [0.38, 0.96] | 0 |
| qwen | replicated | mem0 | n6h2 | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 1/5 [0.04, 0.62] | 3/5 [0.23, 0.88] | 0 |
| qwen | replicated | mem0 | n6missing_metadata | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 4/5 [0.38, 0.96] | 4/5 [0.38, 0.96] | 0 |
| qwen | replicated | mem0 | n6wrong_user | 5 | 0 | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 5/5 [0.57, 1.00] | 3/5 [0.23, 0.88] | 4/5 [0.38, 0.96] | 0 |

## Agent count: H = 0 across N

| model | locus | backend | level | users | outcomes | same_outcomes | blocks | same_blocks |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | H0 across N | 5 | 25 | 25 | 30 | 30 |
| qwen | kernel | mem0 | H0 across N | 5 | 25 | 24 | 30 | 0 |
| qwen | native | inhouse | H0 across N | 5 | 25 | 25 | 30 | 30 |
| qwen | native | mem0 | H0 across N | 3 | 15 | 15 | 18 | 0 |
| qwen | replicated | inhouse | H0 across N | 5 | 25 | 25 | 30 | 30 |
| qwen | replicated | mem0 | H0 across N | 4 | 20 | 17 | 24 | 0 |

## Agent count: H = 2 against H = 0

| model | locus | backend | level | deletion | privacy | recall | recency | contradiction | cross_user_rows | memories_missing |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | N3 H2 vs H0 | -0/+1 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -1/+0 (p 1) | -1/+0 (p 1) | 0 | +0.40 [-0.71, +1.51] |
| qwen | kernel | inhouse | N6 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | -1/+0 (p 1) | -1/+0 (p 1) | 0 | +0.80 [-0.24, +1.84] |
| qwen | kernel | inhouse | N12 H2 vs H0 | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | 0 | +0.60 [-0.82, +2.02] |
| qwen | kernel | mem0 | N3 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -1/+0 (p 1) | -1/+0 (p 1) | 0 | +0.40 [-0.71, +1.51] |
| qwen | kernel | mem0 | N6 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | -2/+1 (p 1) | -2/+0 (p 0.5) | 0 | +0.80 [-0.24, +1.84] |
| qwen | kernel | mem0 | N12 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -2/+0 (p 0.5) | 0 | +1.60 [+0.49, +2.71] |
| qwen | native | inhouse | N3 H2 vs H0 | -0/+2 (p 0.5) | -0/+0 (p 1) | -2/+0 (p 0.5) | -1/+0 (p 1) | -3/+1 (p 0.62) | 0 | +1.40 [+0.29, +2.51] |
| qwen | native | inhouse | N6 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | -2/+0 (p 0.5) | -2/+1 (p 1) | 0 | +2.40 [+0.52, +4.28] |
| qwen | native | inhouse | N12 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -1/+1 (p 1) | -0/+0 (p 1) | 0 | +1.40 [-0.02, +2.82] |
| qwen | native | mem0 | N3 H2 vs H0 | -1/+1 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | 0 | +1.20 [+0.16, +2.24] |
| qwen | native | mem0 | N6 H2 vs H0 | -1/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | 0 | +2.00 [+0.48, +3.52] |
| qwen | native | mem0 | N12 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | 0 | +1.33 [-0.10, +2.77] |
| qwen | replicated | inhouse | N3 H2 vs H0 | -0/+1 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | -3/+0 (p 0.25) | -2/+0 (p 0.5) | 0 | +1.40 [+0.29, +2.51] |
| qwen | replicated | inhouse | N6 H2 vs H0 | -0/+1 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | -3/+0 (p 0.25) | -2/+0 (p 0.5) | 0 | +2.40 [+0.52, +4.28] |
| qwen | replicated | inhouse | N12 H2 vs H0 | -0/+1 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | 0 | +1.20 [-0.42, +2.82] |
| qwen | replicated | mem0 | N3 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | -2/+1 (p 1) | -2/+0 (p 0.5) | 0 | +1.20 [+0.16, +2.24] |
| qwen | replicated | mem0 | N6 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -2/+0 (p 0.5) | -3/+1 (p 0.62) | -2/+1 (p 1) | 0 | +2.20 [+0.58, +3.82] |
| qwen | replicated | mem0 | N12 H2 vs H0 | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -1/+0 (p 1) | -2/+0 (p 0.5) | 0 | +1.50 [-0.55, +3.55] |

## Concurrency (n6conc against n6h0)

| model | locus | backend | probes | with_writes_in_flight | with_late_writes | late_writes | late_covered | late_rows | uncovered_writes | timing_misses | stale_reads | late_forgets | barrier_wait_ms_median | barrier_wait_ms_max | barrier_timeouts | memories_missing_timing | memories_missing | deletion | privacy | recall | recency | contradiction |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 99.4 | 128 | 0 | 0 | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | kernel | mem0 | 30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3.67e+03 | 3.98e+03 | 0 | 0 | +0.00 [+0.00, +0.00] | -1/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -2/+1 (p 1) | -0/+0 (p 1) |
| qwen | native | inhouse | 30 | 30 | 30 | 77 | 77 | 72 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | native | mem0 | 24 | 24 | 24 | 72 | 72 | 60 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | -0.25 [-1.05, +0.55] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | replicated | inhouse | 30 | 30 | 30 | 90 | 90 | 72 | 0 | 0 | 0 | 0 | 0.243 | 1.07 | 0 | 0 | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | replicated | mem0 | 30 | 30 | 30 | 90 | 90 | 72 | 0 | 0 | 0 | 1 | 0.286 | 0.91 | 0 | 0 | +0.00 [+0.00, +0.00] | -1/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -0/+0 (p 1) |

## Load

| model | locus | backend | load | users | failed | users_per_minute | latency_p50_s | latency_p95_s | barrier_timeouts | barrier_wait_ms_median | barrier_wait_ms_p95 | search_ms_median | search_ms_p95 | select_ms_median | select_ms_p95 | format_ms_median | format_ms_p95 | schedule_wait_ms_median | schedule_wait_ms_p95 | llm_ms_median | llm_ms_p95 | ms_per_completion_token |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | 1 | 16 | 0 | 0.754 | 8.85 | 30.9 | 0 | 0.15 | 0.522 | 138 | 320 | 1.47 | 9.45 | 0.161 | 0.429 | 1.13 | 9.15 | 8.75e+03 | 3.06e+04 | 75.9 |
| qwen | kernel | inhouse | 16 | 16 | 0 | 0.999 | 79.7 | 331 | 0 | 0.171 | 1.87 | 344 | 564 | 1.22 | 2.9 | 0.125 | 0.294 | 1.22e+04 | 3.12e+04 | 4.72e+04 | 2.11e+05 | 441 |
| qwen | kernel | inhouse | 4 | 16 | 0 | 0.958 | 34 | 92.7 | 0 | 0.152 | 1.9 | 136 | 242 | 1.2 | 3.6 | 0.139 | 0.344 | 8.82e+03 | 4.64e+04 | 1.26e+04 | 5.43e+04 | 112 |
| qwen | kernel | mem0 | 1 | 16 | 0 | 0.662 | 8.61 | 23.8 | 0 | 0.121 | 0.208 | 115 | 155 | 1.36 | 2.37 | 0.243 | 0.378 | 0.847 | 1.45 | 8.51e+03 | 2.36e+04 | 54.5 |
| qwen | kernel | mem0 | 16 | 16 | 0 | 0.609 | 146 | 348 | 0 | 0.169 | 1.42 | 949 | 1.64e+03 | 1.49 | 2.62 | 0.258 | 0.558 | 5.86e+04 | 1.27e+05 | 4.91e+04 | 1.47e+05 | 315 |
| qwen | kernel | mem0 | 4 | 16 | 0 | 0.694 | 43.4 | 92.5 | 0 | 0.145 | 0.658 | 290 | 538 | 1.58 | 3.19 | 0.258 | 0.516 | 1.15e+04 | 4.52e+04 | 1.52e+04 | 4.68e+04 | 107 |

## Faults (against n6h0)

| model | locus | backend | fault | users | failed | faulty_agents | misfiled_rows | identity_overridden | cross_user_rows | private_rows_from_others | flood_rows_stored | flood_writes_accepted | flood_sessions_over_bound | flood_rows_in_block_per_probe | quota_rejected | memories_missing | profile_facts_in_block | deletion | privacy | recall | recency | contradiction |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | flood10 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 9 | 9 | 0 | 1.3 | {'duplicate': 31, 'quota': 50} | +0.20 [-0.36, +0.76] | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | kernel | inhouse | flood50 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 9 | 9 | 0 | 1.3 | {'duplicate': 120, 'quota': 321} | +0.20 [-0.36, +0.76] | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | kernel | inhouse | missing_metadata | 5 | 0 | {'assistant_agent': 2, 'profile_agent': 1, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | {} | +0.40 [-0.28, +1.08] | -0.20 [-0.76, +0.36] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) |
| qwen | kernel | inhouse | wrong_user | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | {} | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | kernel | mem0 | flood10 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 7 | 9 | 0 | 0.7 | {'duplicate': 31, 'quota': 50} | +0.20 [-0.36, +0.76] | +0.03 [-0.06, +0.13] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -1/+0 (p 1) |
| qwen | kernel | mem0 | flood50 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 7 | 9 | 0 | 0.833 | {'duplicate': 120, 'quota': 321} | +0.40 [-0.28, +1.08] | +0.00 [-0.15, +0.15] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | kernel | mem0 | missing_metadata | 5 | 0 | {'assistant_agent': 2, 'profile_agent': 1, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | {} | +0.40 [-0.28, +1.08] | -0.10 [-0.66, +0.45] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -1/+0 (p 1) |
| qwen | kernel | mem0 | wrong_user | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | {} | +0.00 [+0.00, +0.00] | +0.03 [-0.06, +0.13] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -0/+0 (p 1) |
| qwen | native | inhouse | flood10 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 90 | 90 | 9 | 4.7 | {} | +1.20 [+0.16, +2.24] | -0.20 [-0.76, +0.36] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -1/+1 (p 1) |
| qwen | native | inhouse | flood50 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 450 | 450 | 9 | 7.53 | {} | +1.60 [+0.92, +2.28] | -0.57 [-1.21, +0.08] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -2/+1 (p 1) |
| qwen | native | inhouse | missing_metadata | 5 | 0 | {'assistant_agent': 2, 'profile_agent': 1, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | {} | +0.60 [-0.08, +1.28] | -0.20 [-0.76, +0.36] | -0/+0 (p 1) | -2/+0 (p 0.5) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | native | inhouse | wrong_user | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 27 | 0 | 65 | 0 | 0 | 0 | 0 | 0 | {} | +1.00 [+0.12, +1.88] | -0.40 [-1.08, +0.28] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -0/+1 (p 1) |
| qwen | native | mem0 | flood10 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 31 | 90 | 9 | 2.37 | {} | +0.20 [-0.84, +1.24] | -0.10 [-0.20, +0.01] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | native | mem0 | flood50 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 340 | 450 | 9 | 4.43 | {} | +0.40 [-0.28, +1.08] | -0.27 [-0.71, +0.17] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | native | mem0 | missing_metadata | 5 | 0 | {'assistant_agent': 2, 'profile_agent': 1, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | {} | +0.80 [-0.24, +1.84] | -0.17 [-0.67, +0.33] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | native | mem0 | wrong_user | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 34 | 0 | 73 | 0 | 0 | 0 | 0 | 0 | {} | +1.20 [+0.64, +1.76] | -0.34 [-1.02, +0.34] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | replicated | inhouse | flood10 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 89 | 90 | 9 | 6.5 | {} | +1.00 [-0.24, +2.24] | +0.00 [+0.00, +0.00] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | replicated | inhouse | flood50 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 444 | 450 | 9 | 9.83 | {} | +1.20 [+0.16, +2.24] | -0.37 [-0.99, +0.26] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) |
| qwen | replicated | inhouse | missing_metadata | 5 | 0 | {'assistant_agent': 2, 'profile_agent': 1, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | {} | +0.40 [-0.28, +1.08] | -0.20 [-0.76, +0.36] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) |
| qwen | replicated | inhouse | wrong_user | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 27 | 0 | 88 | 0 | 0 | 0 | 0 | 0 | {} | +0.80 [+0.24, +1.36] | -0.40 [-1.08, +0.28] | -0/+1 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) |
| qwen | replicated | mem0 | flood10 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 30 | 90 | 9 | 2.5 | {} | +0.60 [-0.51, +1.71] | -0.09 [-0.27, +0.09] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -0/+1 (p 1) |
| qwen | replicated | mem0 | flood50 | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 153 | 450 | 9 | 5.1 | {} | +0.80 [-0.24, +1.84] | -0.12 [-0.28, +0.03] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+0 (p 1) | -1/+1 (p 1) |
| qwen | replicated | mem0 | missing_metadata | 5 | 0 | {'assistant_agent': 2, 'profile_agent': 1, 'task_agent': 1, 'docs_agent': 1} | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | {} | +0.40 [-0.28, +1.08] | -0.10 [-0.66, +0.45] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -0/+1 (p 1) | -1/+1 (p 1) |
| qwen | replicated | mem0 | wrong_user | 5 | 0 | {'calendar_agent': 1, 'profile_agent': 2, 'task_agent': 1, 'docs_agent': 1} | 32 | 0 | 81 | 0 | 0 | 0 | 0 | 0 | {} | +1.00 [+0.12, +1.88] | -0.37 [-1.02, +0.28] | -0/+0 (p 1) | -0/+0 (p 1) | -0/+0 (p 1) | -1/+1 (p 1) | -1/+1 (p 1) |
