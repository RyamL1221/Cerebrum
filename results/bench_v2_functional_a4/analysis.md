# Benchmark v2 analysis

29 cells, 145 user-trials, 0 failed.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | inhouse | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | inhouse | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | inhouse | h2 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | inhouse | h2 | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | inhouse | h2 | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | inhouse | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 3 |
| qwen | kernel | inhouse | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | kernel | inhouse | no_memory | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 5 |
| qwen | kernel | inhouse | no_memory | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 2 |
| qwen | kernel | inhouse | no_memory | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 3 |
| qwen | kernel | inhouse | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_supersession | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 1.00 | 4 | 4 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_supersession | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | inhouse | writer_scoped | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | inhouse | writer_scoped | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | kernel | inhouse | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | mem0 | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 2 |  |  | 0 | 5 | 1 | 5 |
| qwen | kernel | mem0 | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | mem0 | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 1 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 4 | 0 | 5 |
| qwen | kernel | mem0 | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 3 |
| qwen | kernel | mem0 | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 2 |  |  | 0 | 5 | 1 | 5 |
| qwen | kernel | mem0 | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | kernel | mem0 | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_supersession | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 5 | 1 | 5 |
| qwen | kernel | mem0 | no_supersession | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | kernel | mem0 | writer_scoped | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 1 | 5 |
| qwen | kernel | mem0 | writer_scoped | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 1.00 | 1 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | kernel | mem0 | writer_scoped | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | kernel | mem0 | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | native | inhouse | h0 | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 2 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | h0 | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 |
| qwen | native | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | inhouse | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 3 |  | 5 |
| qwen | native | inhouse | h2 | privacy | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 3 |  | 5 |
| qwen | native | inhouse | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 3 |  | 5 |
| qwen | native | inhouse | h2 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 1 |  |  | 0 | 3 |  | 5 |
| qwen | native | inhouse | h2 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 0 | 3 |  | 5 |
| qwen | native | inhouse | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 1 |  | 2 |
| qwen | native | inhouse | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 3 |
| qwen | native | inhouse | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 1 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 |
| qwen | native | inhouse | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 |  | 3 |
| qwen | native | inhouse | no_visibility | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | privacy | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 2 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.80 | 2 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | inhouse | no_visibility | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 |
| qwen | native | inhouse | no_visibility | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | mem0 | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 2 |
| qwen | native | mem0 | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | mem0 | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 5 |
| qwen | native | mem0 | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 5 |
| qwen | native | mem0 | h2 | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 3 |  | 5 |
| qwen | native | mem0 | h2 | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 3 |  | 5 |
| qwen | native | mem0 | h2 | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 3 |  | 5 |
| qwen | native | mem0 | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 1 |  | 2 |
| qwen | native | mem0 | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 3 |
| qwen | native | mem0 | no_delete | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_delete | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 2 |
| qwen | native | mem0 | no_delete | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | native | mem0 | no_visibility | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 0 | 1 | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | privacy | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 5 |  | 5 |
| qwen | native | mem0 | no_visibility | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 0 | 1 | 0 | 2 |  | 2 |
| qwen | native | mem0 | no_visibility | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 |
| qwen | replicated | inhouse | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | replicated | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | inhouse | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 5 |
| qwen | replicated | inhouse | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 5 |
| qwen | replicated | inhouse | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 1 | 0 | 5 |
| qwen | replicated | inhouse | h2 | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 1 | 0 | 5 |
| qwen | replicated | inhouse | h2 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 1 | 0 | 5 |
| qwen | replicated | inhouse | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 2 |
| qwen | replicated | inhouse | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 3 |
| qwen | replicated | inhouse | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | replicated | inhouse | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 0 | 3 |
| qwen | replicated | inhouse | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_supersession | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 1.00 | 4 | 3 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_supersession | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | replicated | inhouse | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | inhouse | writer_scoped | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | inhouse | writer_scoped | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | replicated | inhouse | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | mem0 | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 1 | 5 |
| qwen | replicated | mem0 | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | replicated | mem0 | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | mem0 | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 1 |  |  | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 2 | 0 | 5 |
| qwen | replicated | mem0 | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 2 |
| qwen | replicated | mem0 | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 0 | 3 |
| qwen | replicated | mem0 | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 | 1 | 5 |
| qwen | replicated | mem0 | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 1 | 5 |
| qwen | replicated | mem0 | no_delete | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 1.00 | 1 | 1 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 | 0 | 2 |
| qwen | replicated | mem0 | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 | 1 | 3 |
| qwen | replicated | mem0 | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_supersession | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 1.00 | 4 | 3 |  |  | 0 | 5 | 1 | 5 |
| qwen | replicated | mem0 | no_supersession | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 2 | 0 | 2 |
| qwen | replicated | mem0 | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |
| qwen | replicated | mem0 | writer_scoped | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | writer_scoped | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 1.00 | 2 | 2 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 5 | 0 | 5 |
| qwen | replicated | mem0 | writer_scoped | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 2 | 0 | 2 |
| qwen | replicated | mem0 | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 | 0 | 3 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 30 | 30 | 0 | 195.50 | 289 |
| qwen | kernel | inhouse | h2 | 30 | 24 | 0 | 194.00 | 289 |
| qwen | kernel | inhouse | no_delete | 30 | 30 | 0 | 193.00 | 291 |
| qwen | kernel | inhouse | no_memory | 30 | 0 | 0 | 0.00 | 0 |
| qwen | kernel | inhouse | no_supersession | 30 | 30 | 0 | 194.00 | 293 |
| qwen | kernel | inhouse | writer_scoped | 30 | 30 | 0 | 196.00 | 296 |
| qwen | kernel | mem0 | h0 | 30 | 30 | 1 | 242.50 | 276 |
| qwen | kernel | mem0 | h2 | 30 | 24 | 0 | 224.00 | 300 |
| qwen | kernel | mem0 | no_delete | 30 | 30 | 2 | 237.00 | 300 |
| qwen | kernel | mem0 | no_supersession | 30 | 30 | 1 | 235.00 | 293 |
| qwen | kernel | mem0 | writer_scoped | 30 | 30 | 1 | 247.00 | 287 |
| qwen | native | inhouse | h0 | 30 | 30 |  | 176.00 | 283 |
| qwen | native | inhouse | h2 | 30 | 18 |  | 41.00 | 274 |
| qwen | native | inhouse | no_delete | 30 | 30 |  | 175.00 | 283 |
| qwen | native | inhouse | no_visibility | 30 | 30 |  | 195.50 | 299 |
| qwen | native | mem0 | h0 | 30 | 30 |  | 225.00 | 271 |
| qwen | native | mem0 | h2 | 30 | 18 |  | 86.00 | 292 |
| qwen | native | mem0 | no_delete | 30 | 30 |  | 225.00 | 286 |
| qwen | native | mem0 | no_visibility | 30 | 30 |  | 234.00 | 302 |
| qwen | replicated | inhouse | h0 | 30 | 30 | 0 | 195.50 | 289 |
| qwen | replicated | inhouse | h2 | 30 | 6 | 0 | 40.00 | 286 |
| qwen | replicated | inhouse | no_delete | 30 | 30 | 0 | 193.00 | 291 |
| qwen | replicated | inhouse | no_supersession | 30 | 30 | 0 | 194.00 | 293 |
| qwen | replicated | inhouse | writer_scoped | 30 | 30 | 0 | 196.00 | 296 |
| qwen | replicated | mem0 | h0 | 30 | 30 | 1 | 239.00 | 283 |
| qwen | replicated | mem0 | h2 | 30 | 12 | 0 | 40.00 | 286 |
| qwen | replicated | mem0 | no_delete | 30 | 30 | 3 | 224.00 | 292 |
| qwen | replicated | mem0 | no_supersession | 30 | 30 | 1 | 233.00 | 300 |
| qwen | replicated | mem0 | writer_scoped | 30 | 30 | 0 | 248.50 | 297 |

## Functional check criteria

| criterion | holds | evidence |
|---|---|---|
| deletion passes and fails in real conditions, and fails under no_delete | True | real: 57 pass, 3 fail; no_delete: 25 of 30 fail |
| privacy passes and fails in real conditions, and fails under no_visibility | True | real: 59 pass, 1 fail; no_visibility: 6 of 10 fail |
| recall passes and fails in real conditions, and fails under no_memory | True | real: 47 pass, 13 fail; no_memory: 5 of 5 fail |
| recency passes and fails in real conditions, and fails under no_memory | True | real: 34 pass, 26 fail; no_memory: 5 of 5 fail |
| contradiction passes and fails in real conditions, and fails under no_memory | True | real: 38 pass, 22 fail; no_memory: 5 of 5 fail |
| deletion passes among non-echo users in in-house cells and fails under no_delete | True | non-echo in-house: 18 of 18 pass; no_delete: 25 of 30 fail |
| the kernel's privacy probe never fails (block or answer) | True | 0 of 55 kernel privacy probes leaked |
| the cap binds in some probe of every kernel and replicated cell (H = 0 and H = 2) | True | kernel inhouse: 54 of 60; kernel mem0: 54 of 60; replicated inhouse: 36 of 60; replicated mem0: 42 of 60 |
| the budget's binding in kernel and replicated in-house cells (H = 0 and H = 2): reported, not required |  | 0 probes with a binding budget |
| kernel and replicated delete completely at H = 0: every deletion probe passes, no carrier is left and every revoke went through the forget | True | 4 cells: 20 pass, 0 fail, 0 unscored, 0 failed trials; 0 trials with revoked_value_rows; 0 of 20 revokes not through the forget |
| writer_scoped fails some echo user in a kernel or replicated cell | True | 6 of 8 echo-user deletion probes fail |
| no kernel or replicated block holds a retired row at H = 0, and no_supersession puts one in some block | True | h0: 0 of 120 probes hold one (0 unrecorded); no_supersession: 109 probes hold one |
| the guard was armed and dropped nothing in the kernel and replicated cells at H = 0 | True | 510 probes: 0 without the guard's stage, 0 unarmed after a forget, 0 with a dropped row |
| every Mem0 forget at H = 0 scrubbed a message | True | 10 of 10 forgets (14 messages) |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar |
|---|---|---|---|---|---|---|
| qwen | mem0 | deletion | 5 | 0 | 0 | 1.00 |
| qwen | mem0 | privacy | 5 | 0 | 0 | 1.00 |
| qwen | mem0 | recall | 5 | 0 | 0 | 1.00 |
| qwen | mem0 | recency | 5 | 0 | 2 | 0.50 |
| qwen | mem0 | contradiction | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | deletion | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | privacy | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | recall | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | recency | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | contradiction | 5 | 0 | 0 | 1.00 |
| qwen | inhouse | identical blocks | 30 | 30 |  |  |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`; `other_agents`: rows of agents other than the revoking writer), forgets that found no value, the Mem0 history scrub (`messages` deleted, `history` records cleared), and rows later writes `swept` and writes `suppressed`.

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | other_agents | no_values | messages | history | swept | suppressed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | inhouse | h2 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | inhouse | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | mem0 | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 7 | 14 | 0 | 0 |
| qwen | kernel | mem0 | h2 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 7 | 14 | 0 | 0 |
| qwen | kernel | mem0 | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | mem0 | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 7 | 14 | 0 | 0 |
| qwen | kernel | mem0 | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h2 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | inhouse | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | mem0 | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 7 | 14 | 0 | 0 |
| qwen | replicated | mem0 | h2 | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 7 | 14 | 0 | 0 |
| qwen | replicated | mem0 | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | mem0 | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 2 | 0 | 7 | 14 | 0 | 0 |
| qwen | replicated | mem0 | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | kernel | inhouse | h2 | 10 | 10 | 10 | 30 | 0 | 48 |
| qwen | kernel | inhouse | no_delete | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | kernel | inhouse | no_memory | 0 | 0 | 0 | 30 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | 0 | 10 | 0 | 30 | 29 | 0 |
| qwen | kernel | inhouse | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | kernel | mem0 | h0 | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | kernel | mem0 | h2 | 10 | 10 | 10 | 30 | 0 | 48 |
| qwen | kernel | mem0 | no_delete | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | kernel | mem0 | no_supersession | 0 | 10 | 0 | 30 | 26 | 0 |
| qwen | kernel | mem0 | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | native | inhouse | h0 | 0 | 10 | 0 | 30 | 26 | 0 |
| qwen | native | inhouse | h2 | 0 | 10 | 0 | 30 | 12 | 0 |
| qwen | native | inhouse | no_delete | 0 | 10 | 0 | 30 | 25 | 0 |
| qwen | native | inhouse | no_visibility | 0 | 10 | 0 | 30 | 26 | 0 |
| qwen | native | mem0 | h0 | 0 | 10 | 0 | 30 | 19 | 0 |
| qwen | native | mem0 | h2 | 0 | 10 | 0 | 30 | 12 | 0 |
| qwen | native | mem0 | no_delete | 0 | 10 | 0 | 30 | 18 | 0 |
| qwen | native | mem0 | no_visibility | 0 | 10 | 0 | 30 | 20 | 0 |
| qwen | replicated | inhouse | h0 | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | replicated | inhouse | h2 | 9 | 10 | 9 | 30 | 0 | 30 |
| qwen | replicated | inhouse | no_delete | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | replicated | inhouse | no_supersession | 0 | 10 | 0 | 30 | 29 | 0 |
| qwen | replicated | inhouse | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | replicated | mem0 | h0 | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | replicated | mem0 | h2 | 9 | 10 | 9 | 30 | 0 | 30 |
| qwen | replicated | mem0 | no_delete | 10 | 10 | 10 | 30 | 0 | 60 |
| qwen | replicated | mem0 | no_supersession | 0 | 10 | 0 | 30 | 25 | 0 |
| qwen | replicated | mem0 | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | h2 | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | h2 | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | kernel | inhouse | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | inhouse | writer_scoped | deletion | 5 | 3 | 2 | 0 |
| qwen | kernel | inhouse | writer_scoped | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | h0 | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | h2 | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | h2 | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | kernel | mem0 | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | no_supersession | deletion | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | no_supersession | privacy | 5 | 5 | 0 | 0 |
| qwen | kernel | mem0 | writer_scoped | deletion | 5 | 4 | 2 | 1 |
| qwen | kernel | mem0 | writer_scoped | privacy | 5 | 5 | 0 | 0 |
| qwen | native | inhouse | h0 | deletion | 5 | 3 | 2 | 0 |
| qwen | native | inhouse | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | native | inhouse | h2 | deletion | 5 | 4 | 1 | 0 |
| qwen | native | inhouse | h2 | privacy | 5 | 4 | 1 | 0 |
| qwen | native | inhouse | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | native | inhouse | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | native | inhouse | no_visibility | deletion | 5 | 3 | 2 | 0 |
| qwen | native | inhouse | no_visibility | privacy | 5 | 0 | 5 | 0 |
| qwen | native | mem0 | h0 | deletion | 5 | 5 | 2 | 2 |
| qwen | native | mem0 | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | native | mem0 | h2 | deletion | 5 | 5 | 1 | 1 |
| qwen | native | mem0 | h2 | privacy | 5 | 5 | 1 | 1 |
| qwen | native | mem0 | no_delete | deletion | 5 | 5 | 5 | 5 |
| qwen | native | mem0 | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | native | mem0 | no_visibility | deletion | 5 | 4 | 2 | 1 |
| qwen | native | mem0 | no_visibility | privacy | 5 | 4 | 5 | 4 |
| qwen | replicated | inhouse | h0 | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | inhouse | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | inhouse | h2 | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | inhouse | h2 | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | inhouse | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | replicated | inhouse | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | inhouse | writer_scoped | deletion | 5 | 3 | 2 | 0 |
| qwen | replicated | inhouse | writer_scoped | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | h0 | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | h0 | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | h2 | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | h2 | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | no_delete | deletion | 5 | 0 | 5 | 0 |
| qwen | replicated | mem0 | no_delete | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | no_supersession | deletion | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | no_supersession | privacy | 5 | 5 | 0 | 0 |
| qwen | replicated | mem0 | writer_scoped | deletion | 5 | 4 | 2 | 1 |
| qwen | replicated | mem0 | writer_scoped | privacy | 5 | 5 | 0 | 0 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures |
|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_delete | echo+target | 2 |
| qwen | kernel | inhouse | no_delete | target | 3 |
| qwen | kernel | inhouse | writer_scoped | echo | 2 |
| qwen | kernel | mem0 | no_delete | echo+target | 1 |
| qwen | kernel | mem0 | no_delete | other_fact+target | 1 |
| qwen | kernel | mem0 | no_delete | target | 3 |
| qwen | kernel | mem0 | writer_scoped | echo | 1 |
| qwen | native | inhouse | h0 | echo | 2 |
| qwen | native | inhouse | h2 | echo | 1 |
| qwen | native | inhouse | no_delete | echo+target | 1 |
| qwen | native | inhouse | no_delete | target | 4 |
| qwen | native | inhouse | no_visibility | echo | 2 |
| qwen | native | mem0 | no_visibility | answer only | 1 |
| qwen | replicated | inhouse | no_delete | echo+target | 2 |
| qwen | replicated | inhouse | no_delete | target | 3 |
| qwen | replicated | inhouse | writer_scoped | echo | 2 |
| qwen | replicated | mem0 | no_delete | echo+target | 1 |
| qwen | replicated | mem0 | no_delete | other_fact+target | 1 |
| qwen | replicated | mem0 | no_delete | target | 3 |
| qwen | replicated | mem0 | writer_scoped | echo | 1 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes |
|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | none | 0 | 5 |
| qwen | kernel | inhouse | h2 | none | 0 | 5 |
| qwen | kernel | inhouse | no_delete | echo+target | 2 | 0 |
| qwen | kernel | inhouse | no_delete | target | 3 | 0 |
| qwen | kernel | inhouse | no_memory | none | 0 | 5 |
| qwen | kernel | inhouse | no_supersession | none | 0 | 5 |
| qwen | kernel | inhouse | writer_scoped | echo | 2 | 0 |
| qwen | kernel | inhouse | writer_scoped | none | 0 | 3 |
| qwen | kernel | mem0 | h0 | none | 0 | 5 |
| qwen | kernel | mem0 | h2 | none | 0 | 5 |
| qwen | kernel | mem0 | no_delete | echo+target | 2 | 0 |
| qwen | kernel | mem0 | no_delete | other_fact+target | 1 | 0 |
| qwen | kernel | mem0 | no_delete | target | 2 | 0 |
| qwen | kernel | mem0 | no_supersession | none | 0 | 5 |
| qwen | kernel | mem0 | writer_scoped | echo | 1 | 1 |
| qwen | kernel | mem0 | writer_scoped | none | 0 | 3 |
| qwen | native | inhouse | h0 | echo | 2 | 0 |
| qwen | native | inhouse | h0 | none | 0 | 3 |
| qwen | native | inhouse | h2 | echo | 1 | 1 |
| qwen | native | inhouse | h2 | none | 0 | 3 |
| qwen | native | inhouse | no_delete | echo+target | 2 | 0 |
| qwen | native | inhouse | no_delete | target | 3 | 0 |
| qwen | native | inhouse | no_visibility | echo | 2 | 0 |
| qwen | native | inhouse | no_visibility | none | 0 | 3 |
| qwen | native | mem0 | h0 | echo | 0 | 2 |
| qwen | native | mem0 | h0 | none | 0 | 3 |
| qwen | native | mem0 | h2 | echo | 0 | 2 |
| qwen | native | mem0 | h2 | none | 0 | 3 |
| qwen | native | mem0 | no_delete | echo+target | 0 | 2 |
| qwen | native | mem0 | no_delete | target | 0 | 3 |
| qwen | native | mem0 | no_visibility | echo | 1 | 1 |
| qwen | native | mem0 | no_visibility | none | 0 | 3 |
| qwen | replicated | inhouse | h0 | none | 0 | 5 |
| qwen | replicated | inhouse | h2 | none | 0 | 5 |
| qwen | replicated | inhouse | no_delete | echo+target | 2 | 0 |
| qwen | replicated | inhouse | no_delete | target | 3 | 0 |
| qwen | replicated | inhouse | no_supersession | none | 0 | 5 |
| qwen | replicated | inhouse | writer_scoped | echo | 2 | 0 |
| qwen | replicated | inhouse | writer_scoped | none | 0 | 3 |
| qwen | replicated | mem0 | h0 | none | 0 | 5 |
| qwen | replicated | mem0 | h2 | none | 0 | 5 |
| qwen | replicated | mem0 | no_delete | echo+target | 2 | 0 |
| qwen | replicated | mem0 | no_delete | other_fact+target | 1 | 0 |
| qwen | replicated | mem0 | no_delete | target | 2 | 0 |
| qwen | replicated | mem0 | no_supersession | none | 0 | 5 |
| qwen | replicated | mem0 | writer_scoped | echo | 1 | 1 |
| qwen | replicated | mem0 | writer_scoped | none | 0 | 3 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `not_in_block` (never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | not_in_block | in_block_no_row | conversation_only | in_writer_row |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h2 | recency | 1 | 0 | 1 | 0 | 0 | 0 |
| qwen | kernel | inhouse | h2 | contradiction | 1 | 0 | 1 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | recall | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | recency | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | contradiction | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | recency | 4 | 4 | 0 | 0 | 0 | 4 |
| qwen | kernel | inhouse | no_supersession | contradiction | 2 | 1 | 0 | 0 | 0 | 2 |
| qwen | kernel | mem0 | h0 | recency | 2 | 2 | 0 | 0 | 0 | 2 |
| qwen | kernel | mem0 | h2 | recency | 2 | 1 | 1 | 0 | 0 | 1 |
| qwen | kernel | mem0 | h2 | contradiction | 1 | 0 | 1 | 0 | 0 | 0 |
| qwen | kernel | mem0 | no_delete | recency | 2 | 2 | 0 | 0 | 0 | 2 |
| qwen | kernel | mem0 | no_supersession | recency | 1 | 0 | 0 | 0 | 0 | 1 |
| qwen | kernel | mem0 | no_supersession | contradiction | 2 | 0 | 0 | 0 | 0 | 2 |
| qwen | kernel | mem0 | writer_scoped | contradiction | 1 | 1 | 0 | 0 | 0 | 1 |
| qwen | native | inhouse | h0 | recency | 3 | 3 | 0 | 0 | 0 | 3 |
| qwen | native | inhouse | h0 | contradiction | 2 | 0 | 0 | 0 | 0 | 2 |
| qwen | native | inhouse | h2 | recall | 1 | 0 | 1 | 0 | 0 | 0 |
| qwen | native | inhouse | h2 | recency | 3 | 1 | 2 | 0 | 0 | 1 |
| qwen | native | inhouse | h2 | contradiction | 4 | 0 | 2 | 0 | 0 | 2 |
| qwen | native | inhouse | no_delete | recency | 2 | 2 | 0 | 0 | 0 | 2 |
| qwen | native | inhouse | no_delete | contradiction | 2 | 1 | 0 | 0 | 0 | 2 |
| qwen | native | inhouse | no_visibility | recency | 3 | 3 | 0 | 0 | 0 | 3 |
| qwen | native | inhouse | no_visibility | contradiction | 3 | 2 | 0 | 0 | 0 | 3 |
| qwen | native | mem0 | h0 | recall | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | h0 | recency | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | h0 | contradiction | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | h2 | recall | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | h2 | recency | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | h2 | contradiction | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | no_delete | recall | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | no_delete | recency | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | no_delete | contradiction | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | no_visibility | recall | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | no_visibility | recency | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | native | mem0 | no_visibility | contradiction | 5 | 0 | 5 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h2 | recall | 1 | 0 | 1 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h2 | recency | 2 | 0 | 2 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h2 | contradiction | 2 | 0 | 2 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | recency | 4 | 4 | 0 | 0 | 0 | 4 |
| qwen | replicated | inhouse | no_supersession | contradiction | 2 | 1 | 0 | 0 | 0 | 2 |
| qwen | replicated | mem0 | h2 | recall | 1 | 0 | 1 | 0 | 0 | 0 |
| qwen | replicated | mem0 | h2 | recency | 3 | 1 | 2 | 0 | 0 | 1 |
| qwen | replicated | mem0 | h2 | contradiction | 2 | 0 | 2 | 0 | 0 | 0 |
| qwen | replicated | mem0 | no_delete | recency | 1 | 1 | 0 | 0 | 0 | 1 |
| qwen | replicated | mem0 | no_supersession | recency | 4 | 4 | 0 | 0 | 0 | 4 |
| qwen | replicated | mem0 | no_supersession | contradiction | 3 | 1 | 0 | 0 | 0 | 3 |
| qwen | replicated | mem0 | writer_scoped | recency | 2 | 2 | 0 | 0 | 0 | 2 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient |
|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | client | 1 | 1 | 1 |
| qwen | kernel | inhouse | h0 | conference | 1 | 1 | 1 |
| qwen | kernel | inhouse | h0 | home_city | 1 | 1 | 1 |
| qwen | kernel | inhouse | h0 | manager | 1 | 1 | 1 |
| qwen | kernel | inhouse | h0 | one_on_one | 1 | 1 | 1 |
| qwen | kernel | inhouse | h2 | client | 1 | 0 | 0 |
| qwen | kernel | inhouse | h2 | conference | 1 | 1 | 1 |
| qwen | kernel | inhouse | h2 | home_city | 1 | 1 | 1 |
| qwen | kernel | inhouse | h2 | manager | 1 | 1 | 1 |
| qwen | kernel | inhouse | h2 | one_on_one | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_delete | client | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_delete | conference | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_delete | home_city | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_delete | manager | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_memory | client | 1 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | conference | 1 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | home_city | 1 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | manager | 1 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | one_on_one | 1 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | client | 1 | 0 | 1 |
| qwen | kernel | inhouse | no_supersession | conference | 1 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | home_city | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_supersession | manager | 1 | 1 | 1 |
| qwen | kernel | inhouse | no_supersession | one_on_one | 1 | 1 | 1 |
| qwen | kernel | inhouse | writer_scoped | client | 1 | 1 | 1 |
| qwen | kernel | inhouse | writer_scoped | conference | 1 | 1 | 1 |
| qwen | kernel | inhouse | writer_scoped | home_city | 1 | 1 | 1 |
| qwen | kernel | inhouse | writer_scoped | manager | 1 | 1 | 1 |
| qwen | kernel | inhouse | writer_scoped | one_on_one | 1 | 1 | 1 |
| qwen | kernel | mem0 | h0 | client | 1 | 1 | 1 |
| qwen | kernel | mem0 | h0 | conference | 1 | 1 | 1 |
| qwen | kernel | mem0 | h0 | home_city | 1 | 1 | 1 |
| qwen | kernel | mem0 | h0 | manager | 1 | 1 | 1 |
| qwen | kernel | mem0 | h0 | one_on_one | 1 | 1 | 1 |
| qwen | kernel | mem0 | h2 | client | 1 | 0 | 0 |
| qwen | kernel | mem0 | h2 | conference | 1 | 1 | 1 |
| qwen | kernel | mem0 | h2 | home_city | 1 | 1 | 1 |
| qwen | kernel | mem0 | h2 | manager | 1 | 1 | 1 |
| qwen | kernel | mem0 | h2 | one_on_one | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_delete | client | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_delete | conference | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_delete | home_city | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_delete | manager | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_supersession | client | 1 | 0 | 0 |
| qwen | kernel | mem0 | no_supersession | conference | 1 | 0 | 0 |
| qwen | kernel | mem0 | no_supersession | home_city | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_supersession | manager | 1 | 1 | 1 |
| qwen | kernel | mem0 | no_supersession | one_on_one | 1 | 1 | 1 |
| qwen | kernel | mem0 | writer_scoped | client | 1 | 0 | 1 |
| qwen | kernel | mem0 | writer_scoped | conference | 1 | 1 | 1 |
| qwen | kernel | mem0 | writer_scoped | home_city | 1 | 1 | 1 |
| qwen | kernel | mem0 | writer_scoped | manager | 1 | 1 | 1 |
| qwen | kernel | mem0 | writer_scoped | one_on_one | 1 | 1 | 1 |
| qwen | native | inhouse | h0 | client | 1 | 1 | 1 |
| qwen | native | inhouse | h0 | conference | 1 | 0 | 0 |
| qwen | native | inhouse | h0 | home_city | 1 | 0 | 0 |
| qwen | native | inhouse | h0 | manager | 1 | 1 | 1 |
| qwen | native | inhouse | h0 | one_on_one | 1 | 1 | 1 |
| qwen | native | inhouse | h2 | client | 1 | 0 | 0 |
| qwen | native | inhouse | h2 | conference | 1 | 0 | 0 |
| qwen | native | inhouse | h2 | home_city | 1 | 1 | 1 |
| qwen | native | inhouse | h2 | manager | 1 | 0 | 0 |
| qwen | native | inhouse | h2 | one_on_one | 1 | 0 | 0 |
| qwen | native | inhouse | no_delete | client | 1 | 1 | 1 |
| qwen | native | inhouse | no_delete | conference | 1 | 0 | 0 |
| qwen | native | inhouse | no_delete | home_city | 1 | 0 | 1 |
| qwen | native | inhouse | no_delete | manager | 1 | 1 | 1 |
| qwen | native | inhouse | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | native | inhouse | no_visibility | client | 1 | 0 | 1 |
| qwen | native | inhouse | no_visibility | conference | 1 | 0 | 0 |
| qwen | native | inhouse | no_visibility | home_city | 1 | 0 | 1 |
| qwen | native | inhouse | no_visibility | manager | 1 | 1 | 1 |
| qwen | native | inhouse | no_visibility | one_on_one | 1 | 1 | 1 |
| qwen | native | mem0 | h0 | client | 1 | 0 | 0 |
| qwen | native | mem0 | h0 | conference | 1 | 0 | 0 |
| qwen | native | mem0 | h0 | home_city | 1 | 0 | 0 |
| qwen | native | mem0 | h0 | manager | 1 | 0 | 0 |
| qwen | native | mem0 | h0 | one_on_one | 1 | 0 | 0 |
| qwen | native | mem0 | h2 | client | 1 | 0 | 0 |
| qwen | native | mem0 | h2 | conference | 1 | 0 | 0 |
| qwen | native | mem0 | h2 | home_city | 1 | 0 | 0 |
| qwen | native | mem0 | h2 | manager | 1 | 0 | 0 |
| qwen | native | mem0 | h2 | one_on_one | 1 | 0 | 0 |
| qwen | native | mem0 | no_delete | client | 1 | 0 | 0 |
| qwen | native | mem0 | no_delete | conference | 1 | 0 | 0 |
| qwen | native | mem0 | no_delete | home_city | 1 | 0 | 0 |
| qwen | native | mem0 | no_delete | manager | 1 | 0 | 0 |
| qwen | native | mem0 | no_delete | one_on_one | 1 | 0 | 0 |
| qwen | native | mem0 | no_visibility | client | 1 | 0 | 0 |
| qwen | native | mem0 | no_visibility | conference | 1 | 0 | 0 |
| qwen | native | mem0 | no_visibility | home_city | 1 | 0 | 0 |
| qwen | native | mem0 | no_visibility | manager | 1 | 0 | 0 |
| qwen | native | mem0 | no_visibility | one_on_one | 1 | 0 | 0 |
| qwen | replicated | inhouse | h0 | client | 1 | 1 | 1 |
| qwen | replicated | inhouse | h0 | conference | 1 | 1 | 1 |
| qwen | replicated | inhouse | h0 | home_city | 1 | 1 | 1 |
| qwen | replicated | inhouse | h0 | manager | 1 | 1 | 1 |
| qwen | replicated | inhouse | h0 | one_on_one | 1 | 1 | 1 |
| qwen | replicated | inhouse | h2 | client | 1 | 0 | 0 |
| qwen | replicated | inhouse | h2 | conference | 1 | 1 | 1 |
| qwen | replicated | inhouse | h2 | home_city | 1 | 1 | 1 |
| qwen | replicated | inhouse | h2 | manager | 1 | 1 | 1 |
| qwen | replicated | inhouse | h2 | one_on_one | 1 | 0 | 0 |
| qwen | replicated | inhouse | no_delete | client | 1 | 1 | 1 |
| qwen | replicated | inhouse | no_delete | conference | 1 | 1 | 1 |
| qwen | replicated | inhouse | no_delete | home_city | 1 | 1 | 1 |
| qwen | replicated | inhouse | no_delete | manager | 1 | 1 | 1 |
| qwen | replicated | inhouse | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | replicated | inhouse | no_supersession | client | 1 | 0 | 1 |
| qwen | replicated | inhouse | no_supersession | conference | 1 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | home_city | 1 | 1 | 1 |
| qwen | replicated | inhouse | no_supersession | manager | 1 | 1 | 1 |
| qwen | replicated | inhouse | no_supersession | one_on_one | 1 | 1 | 1 |
| qwen | replicated | inhouse | writer_scoped | client | 1 | 1 | 1 |
| qwen | replicated | inhouse | writer_scoped | conference | 1 | 1 | 1 |
| qwen | replicated | inhouse | writer_scoped | home_city | 1 | 1 | 1 |
| qwen | replicated | inhouse | writer_scoped | manager | 1 | 1 | 1 |
| qwen | replicated | inhouse | writer_scoped | one_on_one | 1 | 1 | 1 |
| qwen | replicated | mem0 | h0 | client | 1 | 1 | 1 |
| qwen | replicated | mem0 | h0 | conference | 1 | 1 | 1 |
| qwen | replicated | mem0 | h0 | home_city | 1 | 1 | 1 |
| qwen | replicated | mem0 | h0 | manager | 1 | 1 | 1 |
| qwen | replicated | mem0 | h0 | one_on_one | 1 | 1 | 1 |
| qwen | replicated | mem0 | h2 | client | 1 | 0 | 0 |
| qwen | replicated | mem0 | h2 | conference | 1 | 1 | 1 |
| qwen | replicated | mem0 | h2 | home_city | 1 | 1 | 1 |
| qwen | replicated | mem0 | h2 | manager | 1 | 1 | 1 |
| qwen | replicated | mem0 | h2 | one_on_one | 1 | 0 | 0 |
| qwen | replicated | mem0 | no_delete | client | 1 | 1 | 1 |
| qwen | replicated | mem0 | no_delete | conference | 1 | 1 | 1 |
| qwen | replicated | mem0 | no_delete | home_city | 1 | 1 | 1 |
| qwen | replicated | mem0 | no_delete | manager | 1 | 1 | 1 |
| qwen | replicated | mem0 | no_delete | one_on_one | 1 | 1 | 1 |
| qwen | replicated | mem0 | no_supersession | client | 1 | 0 | 0 |
| qwen | replicated | mem0 | no_supersession | conference | 1 | 0 | 0 |
| qwen | replicated | mem0 | no_supersession | home_city | 1 | 0 | 1 |
| qwen | replicated | mem0 | no_supersession | manager | 1 | 1 | 1 |
| qwen | replicated | mem0 | no_supersession | one_on_one | 1 | 1 | 1 |
| qwen | replicated | mem0 | writer_scoped | client | 1 | 1 | 1 |
| qwen | replicated | mem0 | writer_scoped | conference | 1 | 1 | 1 |
| qwen | replicated | mem0 | writer_scoped | home_city | 1 | 1 | 1 |
| qwen | replicated | mem0 | writer_scoped | manager | 1 | 1 | 1 |
| qwen | replicated | mem0 | writer_scoped | one_on_one | 1 | 1 | 1 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | recency | 0 | 0 | 5 | 5 |
| qwen | kernel | inhouse | h0 | contradiction | 0 | 0 | 5 | 5 |
| qwen | kernel | inhouse | h2 | recency | 0 | 0 | 5 | 4 |
| qwen | kernel | inhouse | h2 | contradiction | 0 | 0 | 5 | 4 |
| qwen | kernel | inhouse | no_delete | recency | 0 | 0 | 5 | 5 |
| qwen | kernel | inhouse | no_delete | contradiction | 0 | 0 | 5 | 5 |
| qwen | kernel | inhouse | no_memory | recency | 0 | 0 | 5 | 0 |
| qwen | kernel | inhouse | no_memory | contradiction | 0 | 0 | 5 | 0 |
| qwen | kernel | inhouse | no_supersession | recency | 0 | 0 | 5 | 1 |
| qwen | kernel | inhouse | no_supersession | contradiction | 0 | 0 | 5 | 3 |
| qwen | kernel | inhouse | writer_scoped | recency | 0 | 0 | 5 | 5 |
| qwen | kernel | inhouse | writer_scoped | contradiction | 0 | 0 | 5 | 5 |
| qwen | kernel | mem0 | h0 | recency | 0 | 0 | 5 | 3 |
| qwen | kernel | mem0 | h0 | contradiction | 0 | 0 | 5 | 5 |
| qwen | kernel | mem0 | h2 | recency | 0 | 0 | 5 | 3 |
| qwen | kernel | mem0 | h2 | contradiction | 0 | 0 | 5 | 4 |
| qwen | kernel | mem0 | no_delete | recency | 0 | 0 | 5 | 3 |
| qwen | kernel | mem0 | no_delete | contradiction | 0 | 0 | 5 | 5 |
| qwen | kernel | mem0 | no_supersession | recency | 0 | 0 | 5 | 4 |
| qwen | kernel | mem0 | no_supersession | contradiction | 0 | 0 | 5 | 3 |
| qwen | kernel | mem0 | writer_scoped | recency | 0 | 0 | 5 | 5 |
| qwen | kernel | mem0 | writer_scoped | contradiction | 0 | 0 | 5 | 4 |
| qwen | native | inhouse | h0 | recency | 0 | 0 | 5 | 2 |
| qwen | native | inhouse | h0 | contradiction | 0 | 0 | 5 | 3 |
| qwen | native | inhouse | h2 | recency | 0 | 0 | 5 | 2 |
| qwen | native | inhouse | h2 | contradiction | 0 | 0 | 5 | 1 |
| qwen | native | inhouse | no_delete | recency | 0 | 0 | 5 | 3 |
| qwen | native | inhouse | no_delete | contradiction | 0 | 0 | 5 | 3 |
| qwen | native | inhouse | no_visibility | recency | 0 | 0 | 5 | 2 |
| qwen | native | inhouse | no_visibility | contradiction | 0 | 0 | 5 | 2 |
| qwen | native | mem0 | h0 | recency | 0 | 0 | 5 | 0 |
| qwen | native | mem0 | h0 | contradiction | 0 | 0 | 5 | 0 |
| qwen | native | mem0 | h2 | recency | 0 | 0 | 5 | 0 |
| qwen | native | mem0 | h2 | contradiction | 0 | 0 | 5 | 0 |
| qwen | native | mem0 | no_delete | recency | 0 | 0 | 5 | 0 |
| qwen | native | mem0 | no_delete | contradiction | 0 | 0 | 5 | 0 |
| qwen | native | mem0 | no_visibility | recency | 0 | 0 | 5 | 0 |
| qwen | native | mem0 | no_visibility | contradiction | 0 | 0 | 5 | 0 |
| qwen | replicated | inhouse | h0 | recency | 0 | 0 | 5 | 5 |
| qwen | replicated | inhouse | h0 | contradiction | 0 | 0 | 5 | 5 |
| qwen | replicated | inhouse | h2 | recency | 0 | 0 | 5 | 3 |
| qwen | replicated | inhouse | h2 | contradiction | 0 | 0 | 5 | 3 |
| qwen | replicated | inhouse | no_delete | recency | 0 | 0 | 5 | 5 |
| qwen | replicated | inhouse | no_delete | contradiction | 0 | 0 | 5 | 5 |
| qwen | replicated | inhouse | no_supersession | recency | 0 | 0 | 5 | 1 |
| qwen | replicated | inhouse | no_supersession | contradiction | 0 | 0 | 5 | 3 |
| qwen | replicated | inhouse | writer_scoped | recency | 0 | 0 | 5 | 5 |
| qwen | replicated | inhouse | writer_scoped | contradiction | 0 | 0 | 5 | 5 |
| qwen | replicated | mem0 | h0 | recency | 0 | 0 | 5 | 5 |
| qwen | replicated | mem0 | h0 | contradiction | 0 | 0 | 5 | 5 |
| qwen | replicated | mem0 | h2 | recency | 0 | 0 | 5 | 2 |
| qwen | replicated | mem0 | h2 | contradiction | 0 | 0 | 5 | 3 |
| qwen | replicated | mem0 | no_delete | recency | 0 | 0 | 5 | 4 |
| qwen | replicated | mem0 | no_delete | contradiction | 0 | 0 | 5 | 5 |
| qwen | replicated | mem0 | no_supersession | recency | 0 | 0 | 5 | 1 |
| qwen | replicated | mem0 | no_supersession | contradiction | 0 | 0 | 5 | 2 |
| qwen | replicated | mem0 | writer_scoped | recency | 0 | 0 | 5 | 3 |
| qwen | replicated | mem0 | writer_scoped | contradiction | 0 | 0 | 5 | 5 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | kernel | inhouse | h2 | 5 | 8.40 | 0.00 | 8.40 | 0 | 4 | 4 | 4 |  |  |
| qwen | kernel | inhouse | no_delete | 5 | 10.00 | 0.00 | 10.00 | 0 | 3 | 5 | 3 |  |  |
| qwen | kernel | inhouse | no_memory | 5 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0 |  |  |
| qwen | kernel | inhouse | no_supersession | 5 | 10.00 | 0.00 | 10.00 | 0 | 4 | 5 | 4 |  |  |
| qwen | kernel | inhouse | writer_scoped | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | kernel | mem0 | h0 | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | kernel | mem0 | h2 | 5 | 8.40 | 0.00 | 8.40 | 0 | 4 | 4 | 4 |  |  |
| qwen | kernel | mem0 | no_delete | 5 | 9.80 | 0.00 | 9.80 | 1 | 5 | 5 | 5 |  |  |
| qwen | kernel | mem0 | no_supersession | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | kernel | mem0 | writer_scoped | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | native | inhouse | h0 | 5 | 9.20 | 0.00 | 9.20 |  | 3 | 5 | 3 |  |  |
| qwen | native | inhouse | h2 | 5 | 4.40 | 0.00 | 4.40 |  | 1 | 1 | 0 |  |  |
| qwen | native | inhouse | no_delete | 5 | 9.20 | 0.00 | 9.20 |  | 2 | 5 | 2 |  |  |
| qwen | native | inhouse | no_visibility | 5 | 10.00 | 0.00 | 10.00 |  | 3 | 5 | 3 |  |  |
| qwen | native | mem0 | h0 | 5 | 9.40 | 0.00 | 9.40 |  | 5 | 5 | 5 |  |  |
| qwen | native | mem0 | h2 | 5 | 4.80 | 0.00 | 4.80 |  | 3 | 2 | 2 |  |  |
| qwen | native | mem0 | no_delete | 5 | 9.40 | 0.00 | 9.40 |  | 5 | 5 | 5 |  |  |
| qwen | native | mem0 | no_visibility | 5 | 10.00 | 0.00 | 10.00 |  | 5 | 5 | 5 |  |  |
| qwen | replicated | inhouse | h0 | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | replicated | inhouse | h2 | 5 | 4.40 | 0.00 | 4.40 | 0 | 2 | 1 | 1 |  |  |
| qwen | replicated | inhouse | no_delete | 5 | 10.00 | 0.00 | 10.00 | 0 | 3 | 5 | 3 |  |  |
| qwen | replicated | inhouse | no_supersession | 5 | 10.00 | 0.00 | 10.00 | 0 | 4 | 5 | 4 |  |  |
| qwen | replicated | inhouse | writer_scoped | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | replicated | mem0 | h0 | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | replicated | mem0 | h2 | 5 | 4.40 | 0.00 | 4.40 | 0 | 2 | 1 | 1 |  |  |
| qwen | replicated | mem0 | no_delete | 5 | 9.80 | 0.00 | 9.80 | 1 | 5 | 5 | 5 |  |  |
| qwen | replicated | mem0 | no_supersession | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |
| qwen | replicated | mem0 | writer_scoped | 5 | 10.00 | 0.00 | 10.00 | 0 | 5 | 5 | 5 |  |  |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score |
|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 2 | 5 |  |
| qwen | kernel | inhouse | h2 | 0 | 1 |  |
| qwen | kernel | inhouse | h2 | 2 | 4 |  |
| qwen | kernel | inhouse | no_delete | 1 | 2 |  |
| qwen | kernel | inhouse | no_delete | 2 | 3 |  |
| qwen | kernel | inhouse | no_memory | 0 | 5 |  |
| qwen | kernel | inhouse | no_supersession | 1 | 1 |  |
| qwen | kernel | inhouse | no_supersession | 2 | 4 |  |
| qwen | kernel | inhouse | writer_scoped | 2 | 5 |  |
| qwen | kernel | mem0 | h0 | 2 | 5 |  |
| qwen | kernel | mem0 | h2 | 0 | 1 |  |
| qwen | kernel | mem0 | h2 | 2 | 4 |  |
| qwen | kernel | mem0 | no_delete | 2 | 5 |  |
| qwen | kernel | mem0 | no_supersession | 2 | 5 |  |
| qwen | kernel | mem0 | writer_scoped | 2 | 5 |  |
| qwen | native | inhouse | h0 | 1 | 2 |  |
| qwen | native | inhouse | h0 | 2 | 3 |  |
| qwen | native | inhouse | h2 | 0 | 3 |  |
| qwen | native | inhouse | h2 | 1 | 2 |  |
| qwen | native | inhouse | no_delete | 1 | 3 |  |
| qwen | native | inhouse | no_delete | 2 | 2 |  |
| qwen | native | inhouse | no_visibility | 1 | 2 |  |
| qwen | native | inhouse | no_visibility | 2 | 3 |  |
| qwen | native | mem0 | h0 | 2 | 5 |  |
| qwen | native | mem0 | h2 | 0 | 2 |  |
| qwen | native | mem0 | h2 | 1 | 1 |  |
| qwen | native | mem0 | h2 | 2 | 2 |  |
| qwen | native | mem0 | no_delete | 2 | 5 |  |
| qwen | native | mem0 | no_visibility | 2 | 5 |  |
| qwen | replicated | inhouse | h0 | 2 | 5 |  |
| qwen | replicated | inhouse | h2 | 0 | 3 |  |
| qwen | replicated | inhouse | h2 | 1 | 1 |  |
| qwen | replicated | inhouse | h2 | 2 | 1 |  |
| qwen | replicated | inhouse | no_delete | 1 | 2 |  |
| qwen | replicated | inhouse | no_delete | 2 | 3 |  |
| qwen | replicated | inhouse | no_supersession | 1 | 1 |  |
| qwen | replicated | inhouse | no_supersession | 2 | 4 |  |
| qwen | replicated | inhouse | writer_scoped | 2 | 5 |  |
| qwen | replicated | mem0 | h0 | 2 | 5 |  |
| qwen | replicated | mem0 | h2 | 0 | 3 |  |
| qwen | replicated | mem0 | h2 | 1 | 1 |  |
| qwen | replicated | mem0 | h2 | 2 | 1 |  |
| qwen | replicated | mem0 | no_delete | 2 | 5 |  |
| qwen | replicated | mem0 | no_supersession | 2 | 5 |  |
| qwen | replicated | mem0 | writer_scoped | 2 | 5 |  |

