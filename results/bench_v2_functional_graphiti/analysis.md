# Benchmark v2 analysis

14 cells, 70 user-trials, 0 failed.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | graphiti | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | graphiti | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | graphiti | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | graphiti | h2 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | graphiti | h2 | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | graphiti | h2 | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | graphiti | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | graphiti | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 3 |
| qwen | kernel | graphiti | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_delete | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | kernel | graphiti | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | kernel | graphiti | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_supersession | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.80 | 3 | 2 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_supersession | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.40 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | graphiti | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | graphiti | writer_scoped | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | graphiti | writer_scoped | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | kernel | graphiti | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | native | graphiti | h0 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 |  | 5 |
| qwen | native | graphiti | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | graphiti | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | h0 | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.80 | 3 | 1 |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | h0 | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.40 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | h0 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 |  | 2 |
| qwen | native | graphiti | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | graphiti | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 3 |  | 5 |
| qwen | native | graphiti | h2 | privacy | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 3 |  | 5 |
| qwen | native | graphiti | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 3 |  | 5 |
| qwen | native | graphiti | h2 | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.60 | 2 | 1 |  |  | 0 | 3 |  | 5 |
| qwen | native | graphiti | h2 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 0 | 3 |  | 5 |
| qwen | native | graphiti | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 1 |  | 2 |
| qwen | native | graphiti | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 3 |
| qwen | native | graphiti | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_delete | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.40 | 1 | 1 |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_delete | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.40 | 1 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 |
| qwen | native | graphiti | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 |  | 3 |
| qwen | native | graphiti | no_visibility | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_visibility | privacy | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_visibility | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_visibility | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.40 | 1 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_visibility | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.40 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | graphiti | no_visibility | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 |  | 2 |
| qwen | native | graphiti | no_visibility | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | replicated | graphiti | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | replicated | graphiti | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | graphiti | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 5 |
| qwen | replicated | graphiti | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 5 |
| qwen | replicated | graphiti | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 3 | 0 | 5 |
| qwen | replicated | graphiti | h2 | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 3 | 0 | 5 |
| qwen | replicated | graphiti | h2 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 3 | 0 | 5 |
| qwen | replicated | graphiti | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 2 |
| qwen | replicated | graphiti | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 3 |
| qwen | replicated | graphiti | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_delete | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | replicated | graphiti | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | replicated | graphiti | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_supersession | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.80 | 2 | 1 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_supersession | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.40 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | replicated | graphiti | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | graphiti | writer_scoped | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | graphiti | writer_scoped | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | replicated | graphiti | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 30 | 0 | 164.00 | 179 |
| qwen | kernel | graphiti | h2 | 30 | 24 | 0 | 158.00 | 176 |
| qwen | kernel | graphiti | no_delete | 30 | 30 | 0 | 164.00 | 176 |
| qwen | kernel | graphiti | no_supersession | 30 | 30 | 0 | 159.00 | 175 |
| qwen | kernel | graphiti | writer_scoped | 30 | 30 | 0 | 165.50 | 185 |
| qwen | native | graphiti | h0 | 30 | 30 |  | 148.50 | 172 |
| qwen | native | graphiti | h2 | 30 | 18 |  | 82.00 | 182 |
| qwen | native | graphiti | no_delete | 30 | 30 |  | 150.00 | 171 |
| qwen | native | graphiti | no_visibility | 30 | 30 |  | 169.50 | 187 |
| qwen | replicated | graphiti | h0 | 30 | 30 | 0 | 162.00 | 196 |
| qwen | replicated | graphiti | h2 | 30 | 18 | 0 | 86.50 | 178 |
| qwen | replicated | graphiti | no_delete | 30 | 30 | 0 | 162.00 | 179 |
| qwen | replicated | graphiti | no_supersession | 30 | 30 | 0 | 165.00 | 176 |
| qwen | replicated | graphiti | writer_scoped | 30 | 30 | 0 | 162.00 | 178 |

## Functional check criteria

| criterion | holds | evidence |
|---|---|---|
| deletion passes and fails in real conditions, and fails under no_delete | True | real: 28 pass, 2 fail; no_delete: 15 of 15 fail |
| privacy passes and fails in real conditions, and fails under no_visibility | True | real: 29 pass, 1 fail; no_visibility: 5 of 5 fail |
| recall passes and fails in real conditions, and fails under no_memory | False | real: 28 pass, 2 fail; no_memory: 0 of 0 fail |
| recency passes and fails in real conditions, and fails under no_memory | False | real: 19 pass, 11 fail; no_memory: 0 of 0 fail |
| contradiction passes and fails in real conditions, and fails under no_memory | False | real: 20 pass, 10 fail; no_memory: 0 of 0 fail |
| deletion passes among non-echo users in in-house cells and fails under no_delete | False | non-echo in-house: 0 of 0 pass; no_delete: 15 of 15 fail |
| the kernel's privacy probe never fails (block or answer) | True | 0 of 25 kernel privacy probes leaked |
| the cap binds in some probe of every kernel and replicated cell (H = 0 and H = 2) | True | kernel graphiti: 54 of 60; replicated graphiti: 48 of 60 |
| the budget's binding in kernel and replicated in-house cells (H = 0 and H = 2): reported, not required |  | 0 probes with a binding budget |
| kernel and replicated delete completely at H = 0: every deletion probe passes, no carrier is left and every revoke went through the forget | True | 2 cells: 10 pass, 0 fail, 0 unscored, 0 failed trials; 0 trials with revoked_value_rows; 0 of 10 revokes not through the forget |
| writer_scoped fails some echo user in a kernel or replicated cell | True | 2 of 4 echo-user deletion probes fail |
| no kernel or replicated block holds a retired row at H = 0, and no_supersession puts one in some block | True | h0: 0 of 60 probes hold one (0 unrecorded); no_supersession: 48 probes hold one |
| the guard was armed and dropped nothing in the kernel and replicated cells at H = 0 | True | 240 probes: 0 without the guard's stage, 0 unarmed after a forget, 0 with a dropped row |
| every Mem0 forget at H = 0 scrubbed a message | False | 0 of 0 forgets (0 messages) |
| every Graphiti forget at H = 0 scrubbed an episode | True | 10 of 10 forgets (14 episodes) |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar |
|---|---|---|---|---|---|---|
| qwen | graphiti | deletion | 5 | 0 | 0 | 1.00 |
| qwen | graphiti | privacy | 5 | 0 | 0 | 1.00 |
| qwen | graphiti | recall | 5 | 0 | 0 | 1.00 |
| qwen | graphiti | recency | 5 | 0 | 0 | 1.00 |
| qwen | graphiti | contradiction | 5 | 0 | 0 | 1.00 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the Mem0 history scrub (`messages` deleted, `history` records cleared), and rows later writes `swept` and writes `suppressed`.

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | other_agents | same_writer | no_values | messages | history | swept | suppressed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 7 | 10 | 0 | 0 |
| qwen | kernel | graphiti | h2 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 7 | 10 | 0 | 0 |
| qwen | kernel | graphiti | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | 5 | 5 | 8 | 5 | 3 | 0 | 3 | 0 | 0 | 7 | 11 | 0 | 0 |
| qwen | kernel | graphiti | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 7 | 10 | 0 | 0 |
| qwen | replicated | graphiti | h2 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 7 | 10 | 0 | 0 |
| qwen | replicated | graphiti | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 7 | 10 | 0 | 0 |
| qwen | replicated | graphiti | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | kernel | graphiti | h2 | 10 | 10 | 10 | 30 | 0 | 48 |
| qwen | kernel | graphiti | no_delete | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | kernel | graphiti | no_supersession | 0 | 10 | 0 | 30 | 24 | 0 |
| qwen | kernel | graphiti | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | native | graphiti | h0 | 0 | 10 | 0 | 30 | 23 | 0 |
| qwen | native | graphiti | h2 | 0 | 10 | 0 | 30 | 12 | 0 |
| qwen | native | graphiti | no_delete | 0 | 10 | 0 | 30 | 24 | 0 |
| qwen | native | graphiti | no_visibility | 0 | 10 | 0 | 30 | 24 | 0 |
| qwen | replicated | graphiti | h0 | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | replicated | graphiti | h2 | 9 | 10 | 9 | 30 | 0 | 30 |
| qwen | replicated | graphiti | no_delete | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | replicated | graphiti | no_supersession | 0 | 10 | 0 | 30 | 24 | 0 |
| qwen | replicated | graphiti | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 |

## Graphiti's own invalidations (Subtask 16)

Graphiti marks a fact invalid when it judges a later one contradicts it: its own supersession, kept apart from the kernel's above and credited to no locus. `invalidated_rows`: rows after the history it marked invalid; probes whose block held one.

| model | locus | backend | condition | invalidated_rows | probes | invalidated_in_block |
|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 8 | 30 | 0 |
| qwen | kernel | graphiti | h2 | 10 | 30 | 4 |
| qwen | kernel | graphiti | no_delete | 8 | 30 | 0 |
| qwen | kernel | graphiti | no_supersession | 8 | 30 | 20 |
| qwen | kernel | graphiti | writer_scoped | 10 | 30 | 3 |
| qwen | native | graphiti | h0 | 9 | 30 | 20 |
| qwen | native | graphiti | h2 | 7 | 30 | 10 |
| qwen | native | graphiti | no_delete | 8 | 30 | 20 |
| qwen | native | graphiti | no_visibility | 8 | 30 | 20 |
| qwen | replicated | graphiti | h0 | 8 | 30 | 0 |
| qwen | replicated | graphiti | h2 | 9 | 30 | 3 |
| qwen | replicated | graphiti | no_delete | 11 | 30 | 4 |
| qwen | replicated | graphiti | no_supersession | 9 | 30 | 22 |
| qwen | replicated | graphiti | writer_scoped | 8 | 30 | 0 |

## Graphiti writes that stored no fact (Amendment 5)

Graphiti sometimes extracts a write's entities but no fact, and its search returns facts only: a write Graphiti stored no fact from is a lost memory, not a failed trial. `trials`: scored trials; `with_one`: scored trials with such a write; `writes_without_fact`: those writes; `probes_on_them`: probes whose target was one, and `passed_on_them`.

| model | locus | backend | condition | trials | with_one | writes_without_fact | probes_on_them | passed_on_them |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 5 | 0 | 0 | 0 | 0 |
| qwen | kernel | graphiti | h2 | 5 | 0 | 0 | 0 | 0 |
| qwen | kernel | graphiti | no_delete | 5 | 0 | 0 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | 5 | 0 | 0 | 0 | 0 |
| qwen | kernel | graphiti | writer_scoped | 5 | 0 | 0 | 0 | 0 |
| qwen | native | graphiti | h0 | 5 | 0 | 0 | 0 | 0 |
| qwen | native | graphiti | h2 | 5 | 0 | 0 | 0 | 0 |
| qwen | native | graphiti | no_delete | 5 | 0 | 0 | 0 | 0 |
| qwen | native | graphiti | no_visibility | 5 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | h0 | 5 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | h2 | 5 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | no_delete | 5 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | 5 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | writer_scoped | 5 | 0 | 0 | 0 | 0 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | graphiti | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | graphiti | h2 | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | graphiti | h2 | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | graphiti | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | kernel | graphiti | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | graphiti | writer_scoped | deletion | 5 | 4 | 2 | 1 |
| qwen | kernel | graphiti | writer_scoped | privacy | 5 | 5 | 0 | 0 |
| qwen | native | graphiti | h0 | deletion | 5 | 4 | 2 | 1 |
| qwen | native | graphiti | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | native | graphiti | h2 | deletion | 5 | 4 | 1 | 0 |
| qwen | native | graphiti | h2 | privacy | 5 | 4 | 1 | 0 |
| qwen | native | graphiti | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | native | graphiti | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | native | graphiti | no_visibility | deletion | 5 | 4 | 2 | 1 |
| qwen | native | graphiti | no_visibility | privacy | 5 | 0 | 5 | 0 |
| qwen | replicated | graphiti | h0 | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | graphiti | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | graphiti | h2 | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | graphiti | h2 | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | graphiti | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | replicated | graphiti | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | graphiti | writer_scoped | deletion | 5 | 4 | 2 | 1 |
| qwen | replicated | graphiti | writer_scoped | privacy | 5 | 5 | 0 | 0 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures |
|---|---|---|---|---|---|
| qwen | kernel | graphiti | no_delete | echo+target | 1 |
| qwen | kernel | graphiti | no_delete | target | 4 |
| qwen | kernel | graphiti | writer_scoped | echo | 1 |
| qwen | native | graphiti | h0 | echo | 1 |
| qwen | native | graphiti | h2 | echo | 1 |
| qwen | native | graphiti | no_delete | echo+target | 1 |
| qwen | native | graphiti | no_delete | target | 4 |
| qwen | native | graphiti | no_visibility | echo | 1 |
| qwen | replicated | graphiti | no_delete | echo+target | 2 |
| qwen | replicated | graphiti | no_delete | target | 3 |
| qwen | replicated | graphiti | writer_scoped | echo | 1 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes |
|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | none | 0 | 5 |
| qwen | kernel | graphiti | h2 | none | 0 | 5 |
| qwen | kernel | graphiti | no_delete | echo+target | 2 | 0 |
| qwen | kernel | graphiti | no_delete | target | 3 | 0 |
| qwen | kernel | graphiti | no_supersession | none | 0 | 5 |
| qwen | kernel | graphiti | writer_scoped | echo | 1 | 1 |
| qwen | kernel | graphiti | writer_scoped | none | 0 | 3 |
| qwen | native | graphiti | h0 | echo | 1 | 1 |
| qwen | native | graphiti | h0 | none | 0 | 3 |
| qwen | native | graphiti | h2 | echo | 1 | 1 |
| qwen | native | graphiti | h2 | none | 0 | 3 |
| qwen | native | graphiti | no_delete | echo+target | 2 | 0 |
| qwen | native | graphiti | no_delete | target | 3 | 0 |
| qwen | native | graphiti | no_visibility | echo | 1 | 1 |
| qwen | native | graphiti | no_visibility | none | 0 | 3 |
| qwen | replicated | graphiti | h0 | none | 0 | 5 |
| qwen | replicated | graphiti | h2 | none | 0 | 5 |
| qwen | replicated | graphiti | no_delete | echo+target | 2 | 0 |
| qwen | replicated | graphiti | no_delete | target | 3 | 0 |
| qwen | replicated | graphiti | no_supersession | none | 0 | 5 |
| qwen | replicated | graphiti | writer_scoped | echo | 1 | 1 |
| qwen | replicated | graphiti | writer_scoped | none | 0 | 3 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h2 | recency | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| qwen | kernel | graphiti | h2 | contradiction | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | recency | 4 | 3 | 0 | 0 | 0 | 0 | 4 |
| qwen | kernel | graphiti | no_supersession | contradiction | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| qwen | native | graphiti | h0 | recency | 4 | 3 | 0 | 0 | 0 | 0 | 4 |
| qwen | native | graphiti | h0 | contradiction | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| qwen | native | graphiti | h2 | recall | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| qwen | native | graphiti | h2 | recency | 4 | 2 | 0 | 2 | 0 | 0 | 2 |
| qwen | native | graphiti | h2 | contradiction | 4 | 0 | 0 | 2 | 0 | 0 | 2 |
| qwen | native | graphiti | no_delete | recency | 4 | 1 | 0 | 0 | 0 | 0 | 4 |
| qwen | native | graphiti | no_delete | contradiction | 4 | 1 | 0 | 0 | 0 | 0 | 4 |
| qwen | native | graphiti | no_visibility | recency | 4 | 1 | 0 | 0 | 0 | 0 | 4 |
| qwen | native | graphiti | no_visibility | contradiction | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| qwen | replicated | graphiti | h2 | recall | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| qwen | replicated | graphiti | h2 | recency | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| qwen | replicated | graphiti | h2 | contradiction | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | recency | 3 | 2 | 0 | 0 | 0 | 0 | 3 |
| qwen | replicated | graphiti | no_supersession | contradiction | 3 | 0 | 0 | 0 | 0 | 0 | 3 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient |
|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | client | 1 | 1 | 1 |
| qwen | kernel | graphiti | h0 | conference | 1 | 1 | 1 |
| qwen | kernel | graphiti | h0 | home_city | 1 | 1 | 1 |
| qwen | kernel | graphiti | h0 | manager | 1 | 1 | 1 |
| qwen | kernel | graphiti | h0 | one_on_one | 1 | 1 | 1 |
| qwen | kernel | graphiti | h2 | client | 1 | 0 | 0 |
| qwen | kernel | graphiti | h2 | conference | 1 | 1 | 1 |
| qwen | kernel | graphiti | h2 | home_city | 1 | 1 | 1 |
| qwen | kernel | graphiti | h2 | manager | 1 | 1 | 1 |
| qwen | kernel | graphiti | h2 | one_on_one | 1 | 1 | 1 |
| qwen | kernel | graphiti | no_delete | client | 1 | 1 | 1 |
| qwen | kernel | graphiti | no_delete | conference | 1 | 1 | 1 |
| qwen | kernel | graphiti | no_delete | home_city | 1 | 1 | 1 |
| qwen | kernel | graphiti | no_delete | manager | 1 | 1 | 1 |
| qwen | kernel | graphiti | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | kernel | graphiti | no_supersession | client | 1 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | conference | 1 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | home_city | 1 | 0 | 0 |
| qwen | kernel | graphiti | no_supersession | manager | 1 | 1 | 1 |
| qwen | kernel | graphiti | no_supersession | one_on_one | 1 | 1 | 1 |
| qwen | kernel | graphiti | writer_scoped | client | 1 | 1 | 1 |
| qwen | kernel | graphiti | writer_scoped | conference | 1 | 1 | 1 |
| qwen | kernel | graphiti | writer_scoped | home_city | 1 | 1 | 1 |
| qwen | kernel | graphiti | writer_scoped | manager | 1 | 1 | 1 |
| qwen | kernel | graphiti | writer_scoped | one_on_one | 1 | 1 | 1 |
| qwen | native | graphiti | h0 | client | 1 | 1 | 1 |
| qwen | native | graphiti | h0 | conference | 1 | 0 | 0 |
| qwen | native | graphiti | h0 | home_city | 1 | 0 | 0 |
| qwen | native | graphiti | h0 | manager | 1 | 0 | 0 |
| qwen | native | graphiti | h0 | one_on_one | 1 | 1 | 1 |
| qwen | native | graphiti | h2 | client | 1 | 0 | 0 |
| qwen | native | graphiti | h2 | conference | 1 | 0 | 0 |
| qwen | native | graphiti | h2 | home_city | 1 | 1 | 1 |
| qwen | native | graphiti | h2 | manager | 1 | 0 | 0 |
| qwen | native | graphiti | h2 | one_on_one | 1 | 0 | 0 |
| qwen | native | graphiti | no_delete | client | 1 | 0 | 1 |
| qwen | native | graphiti | no_delete | conference | 1 | 0 | 0 |
| qwen | native | graphiti | no_delete | home_city | 1 | 0 | 0 |
| qwen | native | graphiti | no_delete | manager | 1 | 0 | 0 |
| qwen | native | graphiti | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | native | graphiti | no_visibility | client | 1 | 1 | 1 |
| qwen | native | graphiti | no_visibility | conference | 1 | 0 | 0 |
| qwen | native | graphiti | no_visibility | home_city | 1 | 0 | 0 |
| qwen | native | graphiti | no_visibility | manager | 1 | 0 | 0 |
| qwen | native | graphiti | no_visibility | one_on_one | 1 | 1 | 1 |
| qwen | replicated | graphiti | h0 | client | 1 | 1 | 1 |
| qwen | replicated | graphiti | h0 | conference | 1 | 1 | 1 |
| qwen | replicated | graphiti | h0 | home_city | 1 | 1 | 1 |
| qwen | replicated | graphiti | h0 | manager | 1 | 1 | 1 |
| qwen | replicated | graphiti | h0 | one_on_one | 1 | 1 | 1 |
| qwen | replicated | graphiti | h2 | client | 1 | 0 | 0 |
| qwen | replicated | graphiti | h2 | conference | 1 | 1 | 1 |
| qwen | replicated | graphiti | h2 | home_city | 1 | 1 | 1 |
| qwen | replicated | graphiti | h2 | manager | 1 | 1 | 1 |
| qwen | replicated | graphiti | h2 | one_on_one | 1 | 0 | 0 |
| qwen | replicated | graphiti | no_delete | client | 1 | 1 | 1 |
| qwen | replicated | graphiti | no_delete | conference | 1 | 1 | 1 |
| qwen | replicated | graphiti | no_delete | home_city | 1 | 1 | 1 |
| qwen | replicated | graphiti | no_delete | manager | 1 | 1 | 1 |
| qwen | replicated | graphiti | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | replicated | graphiti | no_supersession | client | 1 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | conference | 1 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | home_city | 1 | 0 | 0 |
| qwen | replicated | graphiti | no_supersession | manager | 1 | 1 | 1 |
| qwen | replicated | graphiti | no_supersession | one_on_one | 1 | 1 | 1 |
| qwen | replicated | graphiti | writer_scoped | client | 1 | 1 | 1 |
| qwen | replicated | graphiti | writer_scoped | conference | 1 | 1 | 1 |
| qwen | replicated | graphiti | writer_scoped | home_city | 1 | 1 | 1 |
| qwen | replicated | graphiti | writer_scoped | manager | 1 | 1 | 1 |
| qwen | replicated | graphiti | writer_scoped | one_on_one | 1 | 1 | 1 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | recency | 0 | 0 | 5 | 5 |
| qwen | kernel | graphiti | h0 | contradiction | 0 | 0 | 5 | 5 |
| qwen | kernel | graphiti | h2 | recency | 0 | 0 | 5 | 4 |
| qwen | kernel | graphiti | h2 | contradiction | 0 | 0 | 5 | 4 |
| qwen | kernel | graphiti | no_delete | recency | 0 | 0 | 5 | 5 |
| qwen | kernel | graphiti | no_delete | contradiction | 0 | 0 | 5 | 5 |
| qwen | kernel | graphiti | no_supersession | recency | 0 | 0 | 5 | 1 |
| qwen | kernel | graphiti | no_supersession | contradiction | 0 | 0 | 5 | 2 |
| qwen | kernel | graphiti | writer_scoped | recency | 0 | 0 | 5 | 5 |
| qwen | kernel | graphiti | writer_scoped | contradiction | 0 | 0 | 5 | 5 |
| qwen | native | graphiti | h0 | recency | 0 | 0 | 5 | 1 |
| qwen | native | graphiti | h0 | contradiction | 0 | 0 | 5 | 2 |
| qwen | native | graphiti | h2 | recency | 0 | 0 | 5 | 1 |
| qwen | native | graphiti | h2 | contradiction | 0 | 0 | 5 | 1 |
| qwen | native | graphiti | no_delete | recency | 0 | 0 | 5 | 1 |
| qwen | native | graphiti | no_delete | contradiction | 0 | 0 | 5 | 1 |
| qwen | native | graphiti | no_visibility | recency | 0 | 0 | 5 | 1 |
| qwen | native | graphiti | no_visibility | contradiction | 0 | 0 | 5 | 2 |
| qwen | replicated | graphiti | h0 | recency | 0 | 0 | 5 | 5 |
| qwen | replicated | graphiti | h0 | contradiction | 0 | 0 | 5 | 5 |
| qwen | replicated | graphiti | h2 | recency | 0 | 0 | 5 | 3 |
| qwen | replicated | graphiti | h2 | contradiction | 0 | 0 | 5 | 3 |
| qwen | replicated | graphiti | no_delete | recency | 0 | 0 | 5 | 5 |
| qwen | replicated | graphiti | no_delete | contradiction | 0 | 0 | 5 | 5 |
| qwen | replicated | graphiti | no_supersession | recency | 0 | 0 | 5 | 2 |
| qwen | replicated | graphiti | no_supersession | contradiction | 0 | 0 | 5 | 2 |
| qwen | replicated | graphiti | writer_scoped | recency | 0 | 0 | 5 | 5 |
| qwen | replicated | graphiti | writer_scoped | contradiction | 0 | 0 | 5 | 5 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | kernel | graphiti | h2 | 5 | 8.40 | 0.00 | 8.40 | 0 | 4 | 3 | 3 |  |  |
| qwen | kernel | graphiti | no_delete | 5 | 10.00 | 0.00 | 10.00 | 0 | 4 | 4 | 3 |  |  |
| qwen | kernel | graphiti | no_supersession | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | kernel | graphiti | writer_scoped | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 4 | 4 |  |  |
| qwen | native | graphiti | h0 | 5 | 9.20 | 0.00 | 9.20 |  | 5 | 5 | 5 |  |  |
| qwen | native | graphiti | h2 | 5 | 4.80 | 0.00 | 4.80 |  | 2 | 1 | 0 |  |  |
| qwen | native | graphiti | no_delete | 5 | 9.00 | 0.00 | 9.00 |  | 5 | 4 | 4 |  |  |
| qwen | native | graphiti | no_visibility | 5 | 10.00 | 0.00 | 10.00 |  | 5 | 4 | 4 |  |  |
| qwen | replicated | graphiti | h0 | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | replicated | graphiti | h2 | 5 | 5.40 | 0.00 | 5.40 | 0 | 3 | 1 | 1 |  |  |
| qwen | replicated | graphiti | no_delete | 5 | 10.00 | 0.00 | 10.00 | 0 | 4 | 5 | 4 |  |  |
| qwen | replicated | graphiti | no_supersession | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | replicated | graphiti | writer_scoped | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score |
|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 2 | 5 |  |
| qwen | kernel | graphiti | h2 | 0 | 1 |  |
| qwen | kernel | graphiti | h2 | 1 | 1 |  |
| qwen | kernel | graphiti | h2 | 2 | 3 |  |
| qwen | kernel | graphiti | no_delete | 1 | 2 |  |
| qwen | kernel | graphiti | no_delete | 2 | 3 |  |
| qwen | kernel | graphiti | no_supersession | 2 | 5 |  |
| qwen | kernel | graphiti | writer_scoped | 1 | 1 |  |
| qwen | kernel | graphiti | writer_scoped | 2 | 4 |  |
| qwen | native | graphiti | h0 | 2 | 5 |  |
| qwen | native | graphiti | h2 | 0 | 2 |  |
| qwen | native | graphiti | h2 | 1 | 3 |  |
| qwen | native | graphiti | no_delete | 1 | 1 |  |
| qwen | native | graphiti | no_delete | 2 | 4 |  |
| qwen | native | graphiti | no_visibility | 1 | 1 |  |
| qwen | native | graphiti | no_visibility | 2 | 4 |  |
| qwen | replicated | graphiti | h0 | 2 | 5 |  |
| qwen | replicated | graphiti | h2 | 0 | 2 |  |
| qwen | replicated | graphiti | h2 | 1 | 2 |  |
| qwen | replicated | graphiti | h2 | 2 | 1 |  |
| qwen | replicated | graphiti | no_delete | 1 | 1 |  |
| qwen | replicated | graphiti | no_delete | 2 | 4 |  |
| qwen | replicated | graphiti | no_supersession | 2 | 5 |  |
| qwen | replicated | graphiti | writer_scoped | 2 | 5 |  |

