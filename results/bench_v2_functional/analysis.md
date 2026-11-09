# Benchmark v2 analysis

21 cells, 105 user-trials, 0 failed.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 1 | 5 |
| qwen | kernel | inhouse | h0 | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 1 |  |  | 0 | 5 | 2 | 5 |
| qwen | kernel | inhouse | h0 | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 1 | 5 | 4 | 5 |
| qwen | kernel | inhouse | h0 | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | inhouse | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 4 | 0 | 5 |
| qwen | kernel | inhouse | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | inhouse | h2 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 4 | 2 | 5 |
| qwen | kernel | inhouse | h2 | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 4 | 2 | 5 |
| qwen | kernel | inhouse | h2 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 4 | 3 | 5 |
| qwen | kernel | inhouse | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 3 |
| qwen | kernel | inhouse | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 2 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 1 | 5 | 2 | 5 |
| qwen | kernel | inhouse | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | kernel | inhouse | no_memory | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 2 | 5 |
| qwen | kernel | inhouse | no_memory | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 5 | 5 |
| qwen | kernel | inhouse | no_memory | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 2 |
| qwen | kernel | inhouse | no_memory | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 3 |
| qwen | kernel | mem0 | h0 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 1.00 | 5 | 2 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.40 | 1 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | mem0 | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.80 | 2 | 0 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 0 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 3 |
| qwen | kernel | mem0 | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 1 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | native | inhouse | h0 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 2 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 |  | 2 |
| qwen | native | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | inhouse | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 2 |  | 5 |
| qwen | native | inhouse | h2 | privacy | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 0 | 0 | 2 |  | 5 |
| qwen | native | inhouse | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 2 |  | 5 |
| qwen | native | inhouse | h2 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 1 |  |  | 0 | 2 |  | 5 |
| qwen | native | inhouse | h2 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 0 | 2 |  | 5 |
| qwen | native | inhouse | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 1 |  | 2 |
| qwen | native | inhouse | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 1 |  | 3 |
| qwen | native | inhouse | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 1 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.40 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 |
| qwen | native | inhouse | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 |  | 3 |
| qwen | native | inhouse | no_visibility | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | privacy | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 4 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 1 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.40 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 |  | 2 |
| qwen | native | inhouse | no_visibility | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | mem0 | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | recall | 1 | 5 | 0.20 | 0.04 | 0.62 |  |  |  |  |  | 1 | 5 |  | 5 |
| qwen | native | mem0 | h0 | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 2 |
| qwen | native | mem0 | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | mem0 | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 5 |
| qwen | native | mem0 | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 5 |
| qwen | native | mem0 | h2 | recall | 1 | 5 | 0.20 | 0.04 | 0.62 |  |  |  |  |  | 0 | 2 |  | 5 |
| qwen | native | mem0 | h2 | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 2 |  | 5 |
| qwen | native | mem0 | h2 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 0 | 2 |  | 5 |
| qwen | native | mem0 | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 1 |  | 2 |
| qwen | native | mem0 | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 1 |  | 3 |
| qwen | native | mem0 | no_delete | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 1 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 2 |
| qwen | native | mem0 | no_delete | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | mem0 | no_visibility | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | privacy | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 1 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 1 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.40 | 0 | 0 |  |  | 1 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 2 |
| qwen | native | mem0 | no_visibility | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | replicated | inhouse | h0 | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 1 | 5 |
| qwen | replicated | inhouse | h0 | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 1 |  |  | 0 | 5 | 2 | 5 |
| qwen | replicated | inhouse | h0 | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 1 | 5 | 4 | 5 |
| qwen | replicated | inhouse | h0 | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | replicated | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | inhouse | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 2 | 0 | 5 |
| qwen | replicated | inhouse | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 5 |
| qwen | replicated | inhouse | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 2 | 0 | 5 |
| qwen | replicated | inhouse | h2 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 0 |  |  | 0 | 2 | 0 | 5 |
| qwen | replicated | inhouse | h2 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 0 | 2 | 4 | 5 |
| qwen | replicated | inhouse | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 1 | 0 | 2 |
| qwen | replicated | inhouse | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 3 |
| qwen | replicated | inhouse | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 2 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 1 | 5 | 2 | 5 |
| qwen | replicated | inhouse | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | replicated | inhouse | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | replicated | mem0 | h0 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 1.00 | 5 | 1 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | replicated | mem0 | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | mem0 | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 3 | 0 | 5 |
| qwen | replicated | mem0 | h2 | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.60 | 2 | 1 |  |  | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.40 | 1 | 0 |  |  | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 1 | 0 | 2 |
| qwen | replicated | mem0 | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 3 |
| qwen | replicated | mem0 | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 1.00 | 4 | 1 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | replicated | mem0 | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 30 | 30 | 11 | 307.00 | 500 |
| qwen | kernel | inhouse | h2 | 30 | 24 | 11 | 313.50 | 499 |
| qwen | kernel | inhouse | no_delete | 30 | 30 | 7 | 311.00 | 500 |
| qwen | kernel | inhouse | no_memory | 30 | 0 | 12 | 345.00 | 477 |
| qwen | kernel | mem0 | h0 | 30 | 30 | 0 | 243.00 | 434 |
| qwen | kernel | mem0 | h2 | 30 | 24 | 0 | 258.00 | 417 |
| qwen | kernel | mem0 | no_delete | 30 | 30 | 0 | 257.50 | 413 |
| qwen | native | inhouse | h0 | 30 | 30 |  | 435.50 | 1128 |
| qwen | native | inhouse | h2 | 30 | 12 |  | 292.50 | 939 |
| qwen | native | inhouse | no_delete | 30 | 30 |  | 347.00 | 769 |
| qwen | native | inhouse | no_visibility | 30 | 30 |  | 417.50 | 1371 |
| qwen | native | mem0 | h0 | 30 | 30 |  | 257.00 | 380 |
| qwen | native | mem0 | h2 | 30 | 12 |  | 113.50 | 341 |
| qwen | native | mem0 | no_delete | 30 | 30 |  | 237.50 | 371 |
| qwen | native | mem0 | no_visibility | 30 | 30 |  | 253.00 | 357 |
| qwen | replicated | inhouse | h0 | 30 | 30 | 11 | 307.00 | 500 |
| qwen | replicated | inhouse | h2 | 30 | 12 | 8 | 306.50 | 494 |
| qwen | replicated | inhouse | no_delete | 30 | 30 | 7 | 311.00 | 500 |
| qwen | replicated | mem0 | h0 | 30 | 30 | 0 | 255.50 | 384 |
| qwen | replicated | mem0 | h2 | 30 | 13 | 0 | 76.00 | 393 |
| qwen | replicated | mem0 | no_delete | 30 | 30 | 0 | 272.00 | 426 |

## Functional check criteria

| criterion | holds | evidence |
|---|---|---|
| deletion passes and fails in real conditions, and fails under no_delete | True | real: 48 pass, 12 fail; no_delete: 25 of 30 fail |
| privacy passes and fails in real conditions, and fails under no_visibility | True | real: 59 pass, 1 fail; no_visibility: 7 of 10 fail |
| recall passes and fails in real conditions, and fails under no_memory | True | real: 49 pass, 11 fail; no_memory: 5 of 5 fail |
| recency passes and fails in real conditions, and fails under no_memory | True | real: 19 pass, 41 fail; no_memory: 5 of 5 fail |
| contradiction passes and fails in real conditions, and fails under no_memory | True | real: 25 pass, 35 fail; no_memory: 5 of 5 fail |
| deletion passes among non-echo users in in-house cells and fails under no_delete | True | non-echo in-house: 18 of 18 pass; no_delete: 25 of 30 fail |
| the kernel's privacy probe never fails (block or answer) | True | 0 of 35 kernel privacy probes leaked |
| the cap binds in some probe of every kernel and replicated cell (H = 0 and H = 2) | True | kernel inhouse: 54 of 60; kernel mem0: 54 of 60; replicated inhouse: 42 of 60; replicated mem0: 43 of 60 |
| the budget binds in some probe of a kernel or replicated in-house cell (H = 0 and H = 2) | True | 41 probes with a binding budget |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar |
|---|---|---|---|---|---|---|
| qwen | mem0 | deletion | 5 | 0 | 0 | 1.00 |
| qwen | mem0 | privacy | 5 | 0 | 0 | 1.00 |
| qwen | mem0 | recall | 5 | 0 | 0 | 1.00 |
| qwen | mem0 | recency | 5 | 0 | 0 | 1.00 |
| qwen | mem0 | contradiction | 5 | 0 | 2 | 0.50 |
| qwen | inhouse | deletion | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | privacy | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | recall | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | recency | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | contradiction | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | identical blocks | 30 | 30 |  |  |

