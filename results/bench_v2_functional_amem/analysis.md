# Benchmark v2 analysis

14 cells, 70 user-trials, 0 failed.

Every table ends with `block_tokens` and `block_rows`: the mean block, in tokens and in rows, of the row's probe type in its cell where the row names one (per locus in the kernel-against-replicated table), else of the cell's probes (its integration probes in the integration readings): a row that splits a cell's probes further (a slot, a carrier, a count of base rows) shows its cell's mean.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 245.80 | 11.40 |
| qwen | kernel | amem | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 218.80 | 11.00 |
| qwen | kernel | amem | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 243.40 | 11.40 |
| qwen | kernel | amem | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 232.20 | 11.00 |
| qwen | kernel | amem | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 220.80 | 11.20 |
| qwen | kernel | amem | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 2 | 261.50 | 12.00 |
| qwen | kernel | amem | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 235.33 | 11.00 |
| qwen | kernel | amem | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 237.40 | 9.00 |
| qwen | kernel | amem | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 215.80 | 10.20 |
| qwen | kernel | amem | h2 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 229.00 | 9.60 |
| qwen | kernel | amem | h2 | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 202.40 | 9.20 |
| qwen | kernel | amem | h2 | contradiction | 4 | 5 | 0.80 | 0.38 | 0.96 | 0.80 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 206.00 | 9.60 |
| qwen | kernel | amem | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 2 | 287.00 | 10.50 |
| qwen | kernel | amem | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 204.33 | 8.00 |
| qwen | kernel | amem | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 0 | 4 | 5 | 270.40 | 11.80 |
| qwen | kernel | amem | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 238.60 | 12.60 |
| qwen | kernel | amem | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 274.20 | 12.00 |
| qwen | kernel | amem | no_delete | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 260.60 | 11.60 |
| qwen | kernel | amem | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 248.00 | 12.80 |
| qwen | kernel | amem | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 0 | 2 | 2 | 254.50 | 11.00 |
| qwen | kernel | amem | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 0 | 2 | 3 | 281.00 | 12.33 |
| qwen | kernel | amem | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 261.00 | 12.40 |
| qwen | kernel | amem | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 225.80 | 13.00 |
| qwen | kernel | amem | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 259.40 | 12.40 |
| qwen | kernel | amem | no_supersession | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 1.00 | 5 | 4 |  |  | 0 | 0 | 4 | 5 | 255.80 | 12.40 |
| qwen | kernel | amem | no_supersession | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 0 |  |  | 0 | 0 | 4 | 5 | 234.60 | 13.20 |
| qwen | kernel | amem | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 2 | 282.00 | 13.00 |
| qwen | kernel | amem | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 247.00 | 12.00 |
| qwen | kernel | amem | writer_scoped | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 0 | 4 | 5 | 269.40 | 11.80 |
| qwen | kernel | amem | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 234.40 | 12.40 |
| qwen | kernel | amem | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 262.40 | 11.40 |
| qwen | kernel | amem | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 254.60 | 11.40 |
| qwen | kernel | amem | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 228.40 | 11.60 |
| qwen | kernel | amem | writer_scoped | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 0 | 2 | 2 | 267.00 | 12.00 |
| qwen | kernel | amem | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 271.00 | 11.67 |
| qwen | native | amem | h0 | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 |  | 5 | 215.40 | 9.20 |
| qwen | native | amem | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 | 161.40 | 9.00 |
| qwen | native | amem | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 | 211.20 | 9.40 |
| qwen | native | amem | h0 | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 1.00 | 1 | 0 |  |  | 0 | 5 |  | 5 | 188.20 | 9.40 |
| qwen | native | amem | h0 | contradiction | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 0 |  |  | 0 | 5 |  | 5 | 167.40 | 9.00 |
| qwen | native | amem | h0 | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 | 225.50 | 9.00 |
| qwen | native | amem | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 | 208.67 | 9.33 |
| qwen | native | amem | h2 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 3 |  | 5 | 114.20 | 5.20 |
| qwen | native | amem | h2 | privacy | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 3 |  | 5 | 82.80 | 4.80 |
| qwen | native | amem | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 3 |  | 5 | 119.00 | 5.40 |
| qwen | native | amem | h2 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 0.60 | 1 | 1 |  |  | 0 | 3 |  | 5 | 107.60 | 5.20 |
| qwen | native | amem | h2 | contradiction | 1 | 5 | 0.20 | 0.04 | 0.62 | 0.20 | 0 | 0 |  |  | 0 | 3 |  | 5 | 92.80 | 5.00 |
| qwen | native | amem | h2 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 1 |  | 2 | 135.50 | 5.00 |
| qwen | native | amem | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 2 |  | 3 | 100.00 | 5.33 |
| qwen | native | amem | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 |  | 5 | 177.60 | 9.20 |
| qwen | native | amem | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 | 159.20 | 9.00 |
| qwen | native | amem | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 | 217.40 | 9.40 |
| qwen | native | amem | no_delete | recency | 1 | 5 | 0.20 | 0.04 | 0.62 | 1.00 | 4 | 3 |  |  | 0 | 5 |  | 5 | 207.80 | 9.60 |
| qwen | native | amem | no_delete | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 5 |  | 5 | 166.20 | 9.00 |
| qwen | native | amem | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 | 180.00 | 9.00 |
| qwen | native | amem | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 3 |  | 3 | 176.00 | 9.33 |
| qwen | native | amem | no_visibility | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 |  | 5 | 232.80 | 10.00 |
| qwen | native | amem | no_visibility | privacy | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 5 |  | 5 | 183.40 | 10.00 |
| qwen | native | amem | no_visibility | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 | 225.40 | 10.00 |
| qwen | native | amem | no_visibility | recency | 4 | 5 | 0.80 | 0.38 | 0.96 | 1.00 | 1 | 0 |  |  | 0 | 5 |  | 5 | 217.60 | 10.00 |
| qwen | native | amem | no_visibility | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 1 |  |  | 0 | 5 |  | 5 | 185.40 | 10.00 |
| qwen | native | amem | no_visibility | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 | 247.50 | 10.00 |
| qwen | native | amem | no_visibility | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 | 223.00 | 10.00 |
| qwen | replicated | amem | h0 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 267.80 | 11.80 |
| qwen | replicated | amem | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 256.60 | 11.40 |
| qwen | replicated | amem | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 260.80 | 11.40 |
| qwen | replicated | amem | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 255.20 | 11.20 |
| qwen | replicated | amem | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 223.60 | 11.40 |
| qwen | replicated | amem | h0 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 2 | 263.00 | 12.00 |
| qwen | replicated | amem | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 271.00 | 11.67 |
| qwen | replicated | amem | h2 | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 1 | 5 | 115.60 | 5.40 |
| qwen | replicated | amem | h2 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 1 | 5 | 105.80 | 5.00 |
| qwen | replicated | amem | h2 | recall | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  |  |  | 0 | 0 | 1 | 5 | 115.00 | 5.40 |
| qwen | replicated | amem | h2 | recency | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 0 | 1 | 5 | 123.60 | 5.00 |
| qwen | replicated | amem | h2 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 0 | 1 | 5 | 120.60 | 4.80 |
| qwen | replicated | amem | h2 | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 2 | 125.00 | 5.00 |
| qwen | replicated | amem | h2 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 1 | 3 | 109.33 | 5.67 |
| qwen | replicated | amem | no_delete | deletion | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  | 5 | 5 | 0 | 0 | 4 | 5 | 288.60 | 12.00 |
| qwen | replicated | amem | no_delete | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 252.60 | 12.20 |
| qwen | replicated | amem | no_delete | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 272.00 | 12.00 |
| qwen | replicated | amem | no_delete | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 262.00 | 11.80 |
| qwen | replicated | amem | no_delete | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 261.80 | 12.60 |
| qwen | replicated | amem | no_delete | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 0 | 2 | 2 | 285.00 | 13.00 |
| qwen | replicated | amem | no_delete | deletion (no echo) | 0 | 3 | 0.00 | 0.00 | 0.56 |  |  |  | 3 | 3 | 0 | 0 | 2 | 3 | 291.00 | 11.33 |
| qwen | replicated | amem | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 5 | 5 | 271.00 | 12.00 |
| qwen | replicated | amem | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 5 | 5 | 257.60 | 12.80 |
| qwen | replicated | amem | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 5 | 5 | 261.80 | 12.60 |
| qwen | replicated | amem | no_supersession | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 1.00 | 5 | 4 |  |  | 0 | 0 | 5 | 5 | 248.60 | 12.20 |
| qwen | replicated | amem | no_supersession | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.80 | 1 | 0 |  |  | 0 | 0 | 5 | 5 | 231.80 | 13.00 |
| qwen | replicated | amem | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 2 | 283.00 | 13.00 |
| qwen | replicated | amem | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 3 | 3 | 263.00 | 11.33 |
| qwen | replicated | amem | writer_scoped | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 0 | 4 | 5 | 256.80 | 11.00 |
| qwen | replicated | amem | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 248.00 | 12.00 |
| qwen | replicated | amem | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 261.20 | 11.40 |
| qwen | replicated | amem | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 276.40 | 11.40 |
| qwen | replicated | amem | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 248.00 | 11.80 |
| qwen | replicated | amem | writer_scoped | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 0 | 2 | 2 | 242.50 | 10.50 |
| qwen | replicated | amem | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 266.33 | 11.33 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 30 | 0 | 24 | 229.50 | 300 | 235.77 | 11.13 |
| qwen | kernel | amem | h2 | 30 | 0 | 24 | 283.00 | 300 | 222.47 | 9.47 |
| qwen | kernel | amem | no_delete | 30 | 0 | 24 | 269.00 | 299 | 262.53 | 12.03 |
| qwen | kernel | amem | no_supersession | 30 | 0 | 24 | 256.00 | 300 | 250.33 | 12.47 |
| qwen | kernel | amem | writer_scoped | 30 | 0 | 24 | 263.50 | 300 | 254.77 | 11.63 |
| qwen | native | amem | h0 | 30 | 30 |  | 173.00 | 287 | 195.43 | 9.20 |
| qwen | native | amem | h2 | 30 | 18 |  | 88.50 | 280 | 112.27 | 5.17 |
| qwen | native | amem | no_delete | 30 | 30 |  | 174.50 | 284 | 193.20 | 9.27 |
| qwen | native | amem | no_visibility | 30 | 30 |  | 192.50 | 296 | 214.03 | 10.00 |
| qwen | replicated | amem | h0 | 30 | 0 | 24 | 275.00 | 300 | 256.87 | 11.40 |
| qwen | replicated | amem | h2 | 30 | 0 | 6 | 40.00 | 300 | 116.43 | 5.03 |
| qwen | replicated | amem | no_delete | 30 | 0 | 24 | 286.00 | 299 | 270.27 | 12.00 |
| qwen | replicated | amem | no_supersession | 30 | 0 | 30 | 267.00 | 300 | 258.87 | 12.33 |
| qwen | replicated | amem | writer_scoped | 30 | 0 | 24 | 275.00 | 300 | 260.33 | 11.40 |

## Functional check criteria

| criterion | holds | evidence |
|---|---|---|
| deletion passes and fails in real conditions, and fails under no_delete | True | real: 27 pass, 3 fail; no_delete: 15 of 15 fail |
| privacy passes and fails in real conditions, and fails under no_visibility | True | real: 29 pass, 1 fail; no_visibility: 5 of 5 fail |
| recall passes and fails in real conditions, and fails under no_memory | False | real: 28 pass, 2 fail; no_memory: 0 of 0 fail |
| recency passes and fails in real conditions, and fails under no_memory | False | real: 23 pass, 7 fail; no_memory: 0 of 0 fail |
| contradiction passes and fails in real conditions, and fails under no_memory | False | real: 20 pass, 10 fail; no_memory: 0 of 0 fail |
| deletion passes among non-echo users in in-house cells and fails under no_delete | False | non-echo in-house: 0 of 0 pass; no_delete: 15 of 15 fail |
| the kernel's privacy probe never fails (block or answer) | True | 0 of 25 kernel privacy probes leaked |
| a limit (the budget or the cap) binds in some probe of every kernel and replicated cell (H = 0 and H = 2) | True | kernel amem: budget 48, cap 0 of 60; replicated amem: budget 30, cap 0 of 60 |
| kernel and replicated delete completely at H = 0: every deletion probe passes, no carrier is left and every revoke went through the forget | True | 2 cells: 10 pass, 0 fail, 0 unscored, 0 failed trials; 0 trials with revoked_value_rows; 0 of 10 revokes not through the forget |
| writer_scoped fails some echo user in a kernel or replicated cell | True | 4 of 4 echo-user deletion probes fail |
| no kernel or replicated block holds a retired row at H = 0, and no_supersession puts one in some block | True | h0: 0 of 60 probes hold one (0 unrecorded); no_supersession: 59 probes hold one |
| the guard was armed and dropped nothing in the kernel and replicated cells at H = 0 | True | 240 probes: 0 without the guard's stage, 0 unarmed after a forget, 0 with a dropped row |
| every Mem0 forget at H = 0 scrubbed a message | False | 0 of 0 forgets (0 messages) |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar | kernel_block_tokens | kernel_block_rows | replicated_block_tokens | replicated_block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | amem | deletion | 5 | 0 | 0 | 1.00 | 245.80 | 11.40 | 267.80 | 11.80 |
| qwen | amem | privacy | 5 | 0 | 0 | 1.00 | 218.80 | 11.00 | 256.60 | 11.40 |
| qwen | amem | recall | 5 | 0 | 0 | 1.00 | 243.40 | 11.40 | 260.80 | 11.40 |
| qwen | amem | recency | 5 | 0 | 0 | 1.00 | 232.20 | 11.00 | 255.20 | 11.20 |
| qwen | amem | contradiction | 5 | 0 | 0 | 1.00 | 220.80 | 11.20 | 223.60 | 11.40 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`, or an `entity`: a Graphiti scrub deleted it with an entity a form names, or `derived`: an A-MEM scrub deleted it because its derived text carried a form; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the history scrub (Mem0: `messages` deleted, `history` records cleared; A-MEM: `history` counts the carrier notes it deleted, as `derived` does), and rows later writes `swept` and writes `suppressed`.

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | entity | derived | other_agents | same_writer | no_values | messages | history | swept | suppressed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 5 | 5 | 8 | 5 | 2 | 0 | 0 | 1 | 3 | 0 | 0 | 0 | 1 | 0 | 0 | 235.77 | 11.13 |
| qwen | kernel | amem | h2 | 5 | 5 | 8 | 5 | 2 | 0 | 0 | 1 | 3 | 0 | 0 | 0 | 1 | 0 | 0 | 222.47 | 9.47 |
| qwen | kernel | amem | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 262.53 | 12.03 |
| qwen | kernel | amem | no_supersession | 5 | 5 | 8 | 5 | 2 | 0 | 0 | 1 | 3 | 0 | 0 | 0 | 1 | 0 | 0 | 250.33 | 12.47 |
| qwen | kernel | amem | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 254.77 | 11.63 |
| qwen | replicated | amem | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 256.87 | 11.40 |
| qwen | replicated | amem | h2 | 5 | 5 | 8 | 5 | 2 | 0 | 0 | 1 | 3 | 0 | 0 | 0 | 1 | 0 | 0 | 116.43 | 5.03 |
| qwen | replicated | amem | no_delete | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 270.27 | 12.00 |
| qwen | replicated | amem | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 258.87 | 12.33 |
| qwen | replicated | amem | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 260.33 | 11.40 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 10 | 10 | 10 | 30 | 0 | 60 | 235.77 | 11.13 |
| qwen | kernel | amem | h2 | 10 | 10 | 10 | 30 | 0 | 48 | 222.47 | 9.47 |
| qwen | kernel | amem | no_delete | 10 | 10 | 10 | 30 | 0 | 60 | 262.53 | 12.03 |
| qwen | kernel | amem | no_supersession | 0 | 10 | 0 | 30 | 30 | 0 | 250.33 | 12.47 |
| qwen | kernel | amem | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 | 254.77 | 11.63 |
| qwen | native | amem | h0 | 0 | 10 | 0 | 30 | 28 | 0 | 195.43 | 9.20 |
| qwen | native | amem | h2 | 0 | 10 | 0 | 30 | 16 | 0 | 112.27 | 5.17 |
| qwen | native | amem | no_delete | 0 | 10 | 0 | 30 | 27 | 0 | 193.20 | 9.27 |
| qwen | native | amem | no_visibility | 0 | 10 | 0 | 30 | 29 | 0 | 214.03 | 10.00 |
| qwen | replicated | amem | h0 | 10 | 10 | 10 | 30 | 0 | 60 | 256.87 | 11.40 |
| qwen | replicated | amem | h2 | 9 | 10 | 9 | 30 | 0 | 30 | 116.43 | 5.03 |
| qwen | replicated | amem | no_delete | 10 | 10 | 10 | 30 | 0 | 60 | 270.27 | 12.00 |
| qwen | replicated | amem | no_supersession | 0 | 10 | 0 | 30 | 29 | 0 | 258.87 | 12.33 |
| qwen | replicated | amem | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 | 260.33 | 11.40 |

## Graphiti writes that stored no fact (Amendment 5)

Graphiti sometimes extracts a write's entities but no fact, and its search returns facts only: a write Graphiti stored no fact from is a lost memory, not a failed trial (and an A-MEM write that stored no note, Amendment 8). `trials`: scored trials; `with_one`: scored trials with such a write; `writes_without_fact`: those writes; `probes_on_them`: probes whose target was one, and `passed_on_them`.

| model | locus | backend | condition | trials | with_one | writes_without_fact | probes_on_them | passed_on_them | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 5 | 0 | 0 | 0 | 0 | 235.77 | 11.13 |
| qwen | kernel | amem | h2 | 5 | 0 | 0 | 0 | 0 | 222.47 | 9.47 |
| qwen | kernel | amem | no_delete | 5 | 0 | 0 | 0 | 0 | 262.53 | 12.03 |
| qwen | kernel | amem | no_supersession | 5 | 0 | 0 | 0 | 0 | 250.33 | 12.47 |
| qwen | kernel | amem | writer_scoped | 5 | 0 | 0 | 0 | 0 | 254.77 | 11.63 |
| qwen | native | amem | h0 | 5 | 0 | 0 | 0 | 0 | 195.43 | 9.20 |
| qwen | native | amem | h2 | 5 | 0 | 0 | 0 | 0 | 112.27 | 5.17 |
| qwen | native | amem | no_delete | 5 | 0 | 0 | 0 | 0 | 193.20 | 9.27 |
| qwen | native | amem | no_visibility | 5 | 0 | 0 | 0 | 0 | 214.03 | 10.00 |
| qwen | replicated | amem | h0 | 5 | 0 | 0 | 0 | 0 | 256.87 | 11.40 |
| qwen | replicated | amem | h2 | 5 | 0 | 0 | 0 | 0 | 116.43 | 5.03 |
| qwen | replicated | amem | no_delete | 5 | 0 | 0 | 0 | 0 | 270.27 | 12.00 |
| qwen | replicated | amem | no_supersession | 5 | 0 | 0 | 0 | 0 | 258.87 | 12.33 |
| qwen | replicated | amem | writer_scoped | 5 | 0 | 0 | 0 | 0 | 260.33 | 11.40 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | deletion | 5 | 5 | 0 | 0 | 245.80 | 11.40 |
| qwen | kernel | amem | h0 | privacy | 5 | 5 | 0 | 0 | 218.80 | 11.00 |
| qwen | kernel | amem | h2 | deletion | 5 | 5 | 0 | 0 | 237.40 | 9.00 |
| qwen | kernel | amem | h2 | privacy | 5 | 5 | 0 | 0 | 215.80 | 10.20 |
| qwen | kernel | amem | no_delete | deletion | 5 | 0 | 5 | 0 | 270.40 | 11.80 |
| qwen | kernel | amem | no_delete | privacy | 5 | 5 | 0 | 0 | 238.60 | 12.60 |
| qwen | kernel | amem | no_supersession | deletion | 5 | 5 | 0 | 0 | 261.00 | 12.40 |
| qwen | kernel | amem | no_supersession | privacy | 5 | 5 | 0 | 0 | 225.80 | 13.00 |
| qwen | kernel | amem | writer_scoped | deletion | 5 | 3 | 2 | 0 | 269.40 | 11.80 |
| qwen | kernel | amem | writer_scoped | privacy | 5 | 5 | 0 | 0 | 234.40 | 12.40 |
| qwen | native | amem | h0 | deletion | 5 | 3 | 2 | 0 | 215.40 | 9.20 |
| qwen | native | amem | h0 | privacy | 5 | 5 | 0 | 0 | 161.40 | 9.00 |
| qwen | native | amem | h2 | deletion | 5 | 4 | 1 | 0 | 114.20 | 5.20 |
| qwen | native | amem | h2 | privacy | 5 | 4 | 1 | 0 | 82.80 | 4.80 |
| qwen | native | amem | no_delete | deletion | 5 | 0 | 5 | 0 | 177.60 | 9.20 |
| qwen | native | amem | no_delete | privacy | 5 | 5 | 0 | 0 | 159.20 | 9.00 |
| qwen | native | amem | no_visibility | deletion | 5 | 3 | 2 | 0 | 232.80 | 10.00 |
| qwen | native | amem | no_visibility | privacy | 5 | 0 | 5 | 0 | 183.40 | 10.00 |
| qwen | replicated | amem | h0 | deletion | 5 | 5 | 0 | 0 | 267.80 | 11.80 |
| qwen | replicated | amem | h0 | privacy | 5 | 5 | 0 | 0 | 256.60 | 11.40 |
| qwen | replicated | amem | h2 | deletion | 5 | 5 | 0 | 0 | 115.60 | 5.40 |
| qwen | replicated | amem | h2 | privacy | 5 | 5 | 0 | 0 | 105.80 | 5.00 |
| qwen | replicated | amem | no_delete | deletion | 5 | 0 | 5 | 0 | 288.60 | 12.00 |
| qwen | replicated | amem | no_delete | privacy | 5 | 5 | 0 | 0 | 252.60 | 12.20 |
| qwen | replicated | amem | no_supersession | deletion | 5 | 5 | 0 | 0 | 271.00 | 12.00 |
| qwen | replicated | amem | no_supersession | privacy | 5 | 5 | 0 | 0 | 257.60 | 12.80 |
| qwen | replicated | amem | writer_scoped | deletion | 5 | 3 | 2 | 0 | 256.80 | 11.00 |
| qwen | replicated | amem | writer_scoped | privacy | 5 | 5 | 0 | 0 | 248.00 | 12.00 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | no_delete | echo+target | 2 | 262.53 | 12.03 |
| qwen | kernel | amem | no_delete | target | 3 | 262.53 | 12.03 |
| qwen | kernel | amem | writer_scoped | echo | 2 | 254.77 | 11.63 |
| qwen | native | amem | h0 | echo | 2 | 195.43 | 9.20 |
| qwen | native | amem | h2 | echo | 1 | 112.27 | 5.17 |
| qwen | native | amem | no_delete | echo+target | 2 | 193.20 | 9.27 |
| qwen | native | amem | no_delete | target | 3 | 193.20 | 9.27 |
| qwen | native | amem | no_visibility | echo | 2 | 214.03 | 10.00 |
| qwen | replicated | amem | no_delete | echo+target | 2 | 270.27 | 12.00 |
| qwen | replicated | amem | no_delete | target | 3 | 270.27 | 12.00 |
| qwen | replicated | amem | writer_scoped | echo | 2 | 260.33 | 11.40 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | none | 0 | 5 | 235.77 | 11.13 |
| qwen | kernel | amem | h2 | none | 0 | 5 | 222.47 | 9.47 |
| qwen | kernel | amem | no_delete | echo+target | 2 | 0 | 262.53 | 12.03 |
| qwen | kernel | amem | no_delete | target | 3 | 0 | 262.53 | 12.03 |
| qwen | kernel | amem | no_supersession | none | 0 | 5 | 250.33 | 12.47 |
| qwen | kernel | amem | writer_scoped | echo | 2 | 0 | 254.77 | 11.63 |
| qwen | kernel | amem | writer_scoped | none | 0 | 3 | 254.77 | 11.63 |
| qwen | native | amem | h0 | echo | 2 | 0 | 195.43 | 9.20 |
| qwen | native | amem | h0 | none | 0 | 3 | 195.43 | 9.20 |
| qwen | native | amem | h2 | echo | 1 | 1 | 112.27 | 5.17 |
| qwen | native | amem | h2 | none | 0 | 3 | 112.27 | 5.17 |
| qwen | native | amem | no_delete | echo+target | 2 | 0 | 193.20 | 9.27 |
| qwen | native | amem | no_delete | target | 3 | 0 | 193.20 | 9.27 |
| qwen | native | amem | no_visibility | echo | 2 | 0 | 214.03 | 10.00 |
| qwen | native | amem | no_visibility | none | 0 | 3 | 214.03 | 10.00 |
| qwen | replicated | amem | h0 | none | 0 | 5 | 256.87 | 11.40 |
| qwen | replicated | amem | h2 | none | 0 | 5 | 116.43 | 5.03 |
| qwen | replicated | amem | no_delete | echo+target | 2 | 0 | 270.27 | 12.00 |
| qwen | replicated | amem | no_delete | target | 3 | 0 | 270.27 | 12.00 |
| qwen | replicated | amem | no_supersession | none | 0 | 5 | 258.87 | 12.33 |
| qwen | replicated | amem | writer_scoped | echo | 2 | 0 | 260.33 | 11.40 |
| qwen | replicated | amem | writer_scoped | none | 0 | 3 | 260.33 | 11.40 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h2 | recency | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 202.40 | 9.20 |
| qwen | kernel | amem | h2 | contradiction | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 206.00 | 9.60 |
| qwen | kernel | amem | no_supersession | recency | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 255.80 | 12.40 |
| qwen | kernel | amem | no_supersession | contradiction | 2 | 1 | 0 | 0 | 0 | 0 | 2 | 234.60 | 13.20 |
| qwen | native | amem | h0 | recency | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 188.20 | 9.40 |
| qwen | native | amem | h0 | contradiction | 3 | 1 | 0 | 0 | 0 | 0 | 3 | 167.40 | 9.00 |
| qwen | native | amem | h2 | recall | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 119.00 | 5.40 |
| qwen | native | amem | h2 | recency | 3 | 1 | 0 | 2 | 0 | 0 | 1 | 107.60 | 5.20 |
| qwen | native | amem | h2 | contradiction | 4 | 0 | 0 | 2 | 0 | 0 | 2 | 92.80 | 5.00 |
| qwen | native | amem | no_delete | recency | 4 | 4 | 0 | 0 | 0 | 0 | 4 | 207.80 | 9.60 |
| qwen | native | amem | no_delete | contradiction | 2 | 0 | 0 | 0 | 0 | 0 | 2 | 166.20 | 9.00 |
| qwen | native | amem | no_visibility | recency | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 217.60 | 10.00 |
| qwen | native | amem | no_visibility | contradiction | 2 | 1 | 0 | 0 | 0 | 0 | 2 | 185.40 | 10.00 |
| qwen | replicated | amem | h2 | recall | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 115.00 | 5.40 |
| qwen | replicated | amem | h2 | recency | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 123.60 | 5.00 |
| qwen | replicated | amem | h2 | contradiction | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 120.60 | 4.80 |
| qwen | replicated | amem | no_supersession | recency | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 248.60 | 12.20 |
| qwen | replicated | amem | no_supersession | contradiction | 2 | 1 | 0 | 0 | 0 | 0 | 2 | 231.80 | 13.00 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | client | 1 | 1 | 1 | 235.77 | 11.13 |
| qwen | kernel | amem | h0 | conference | 1 | 1 | 1 | 235.77 | 11.13 |
| qwen | kernel | amem | h0 | home_city | 1 | 1 | 1 | 235.77 | 11.13 |
| qwen | kernel | amem | h0 | manager | 1 | 1 | 1 | 235.77 | 11.13 |
| qwen | kernel | amem | h0 | one_on_one | 1 | 1 | 1 | 235.77 | 11.13 |
| qwen | kernel | amem | h2 | client | 1 | 0 | 0 | 222.47 | 9.47 |
| qwen | kernel | amem | h2 | conference | 1 | 1 | 1 | 222.47 | 9.47 |
| qwen | kernel | amem | h2 | home_city | 1 | 1 | 1 | 222.47 | 9.47 |
| qwen | kernel | amem | h2 | manager | 1 | 1 | 1 | 222.47 | 9.47 |
| qwen | kernel | amem | h2 | one_on_one | 1 | 1 | 1 | 222.47 | 9.47 |
| qwen | kernel | amem | no_delete | client | 1 | 1 | 1 | 262.53 | 12.03 |
| qwen | kernel | amem | no_delete | conference | 1 | 1 | 1 | 262.53 | 12.03 |
| qwen | kernel | amem | no_delete | home_city | 1 | 1 | 1 | 262.53 | 12.03 |
| qwen | kernel | amem | no_delete | manager | 1 | 1 | 1 | 262.53 | 12.03 |
| qwen | kernel | amem | no_delete | one_on_one | 1 | 1 | 1 | 262.53 | 12.03 |
| qwen | kernel | amem | no_supersession | client | 1 | 0 | 1 | 250.33 | 12.47 |
| qwen | kernel | amem | no_supersession | conference | 1 | 0 | 0 | 250.33 | 12.47 |
| qwen | kernel | amem | no_supersession | home_city | 1 | 1 | 1 | 250.33 | 12.47 |
| qwen | kernel | amem | no_supersession | manager | 1 | 1 | 1 | 250.33 | 12.47 |
| qwen | kernel | amem | no_supersession | one_on_one | 1 | 1 | 1 | 250.33 | 12.47 |
| qwen | kernel | amem | writer_scoped | client | 1 | 1 | 1 | 254.77 | 11.63 |
| qwen | kernel | amem | writer_scoped | conference | 1 | 1 | 1 | 254.77 | 11.63 |
| qwen | kernel | amem | writer_scoped | home_city | 1 | 1 | 1 | 254.77 | 11.63 |
| qwen | kernel | amem | writer_scoped | manager | 1 | 1 | 1 | 254.77 | 11.63 |
| qwen | kernel | amem | writer_scoped | one_on_one | 1 | 1 | 1 | 254.77 | 11.63 |
| qwen | native | amem | h0 | client | 1 | 0 | 0 | 195.43 | 9.20 |
| qwen | native | amem | h0 | conference | 1 | 0 | 0 | 195.43 | 9.20 |
| qwen | native | amem | h0 | home_city | 1 | 0 | 1 | 195.43 | 9.20 |
| qwen | native | amem | h0 | manager | 1 | 1 | 1 | 195.43 | 9.20 |
| qwen | native | amem | h0 | one_on_one | 1 | 1 | 1 | 195.43 | 9.20 |
| qwen | native | amem | h2 | client | 1 | 0 | 0 | 112.27 | 5.17 |
| qwen | native | amem | h2 | conference | 1 | 0 | 0 | 112.27 | 5.17 |
| qwen | native | amem | h2 | home_city | 1 | 1 | 1 | 112.27 | 5.17 |
| qwen | native | amem | h2 | manager | 1 | 0 | 0 | 112.27 | 5.17 |
| qwen | native | amem | h2 | one_on_one | 1 | 0 | 0 | 112.27 | 5.17 |
| qwen | native | amem | no_delete | client | 1 | 1 | 1 | 193.20 | 9.27 |
| qwen | native | amem | no_delete | conference | 1 | 0 | 0 | 193.20 | 9.27 |
| qwen | native | amem | no_delete | home_city | 1 | 0 | 0 | 193.20 | 9.27 |
| qwen | native | amem | no_delete | manager | 1 | 1 | 1 | 193.20 | 9.27 |
| qwen | native | amem | no_delete | one_on_one | 1 | 1 | 1 | 193.20 | 9.27 |
| qwen | native | amem | no_visibility | client | 1 | 1 | 1 | 214.03 | 10.00 |
| qwen | native | amem | no_visibility | conference | 1 | 0 | 0 | 214.03 | 10.00 |
| qwen | native | amem | no_visibility | home_city | 1 | 0 | 1 | 214.03 | 10.00 |
| qwen | native | amem | no_visibility | manager | 1 | 1 | 1 | 214.03 | 10.00 |
| qwen | native | amem | no_visibility | one_on_one | 1 | 1 | 1 | 214.03 | 10.00 |
| qwen | replicated | amem | h0 | client | 1 | 1 | 1 | 256.87 | 11.40 |
| qwen | replicated | amem | h0 | conference | 1 | 1 | 1 | 256.87 | 11.40 |
| qwen | replicated | amem | h0 | home_city | 1 | 1 | 1 | 256.87 | 11.40 |
| qwen | replicated | amem | h0 | manager | 1 | 1 | 1 | 256.87 | 11.40 |
| qwen | replicated | amem | h0 | one_on_one | 1 | 1 | 1 | 256.87 | 11.40 |
| qwen | replicated | amem | h2 | client | 1 | 0 | 0 | 116.43 | 5.03 |
| qwen | replicated | amem | h2 | conference | 1 | 1 | 1 | 116.43 | 5.03 |
| qwen | replicated | amem | h2 | home_city | 1 | 1 | 1 | 116.43 | 5.03 |
| qwen | replicated | amem | h2 | manager | 1 | 1 | 1 | 116.43 | 5.03 |
| qwen | replicated | amem | h2 | one_on_one | 1 | 0 | 0 | 116.43 | 5.03 |
| qwen | replicated | amem | no_delete | client | 1 | 1 | 1 | 270.27 | 12.00 |
| qwen | replicated | amem | no_delete | conference | 1 | 1 | 1 | 270.27 | 12.00 |
| qwen | replicated | amem | no_delete | home_city | 1 | 1 | 1 | 270.27 | 12.00 |
| qwen | replicated | amem | no_delete | manager | 1 | 1 | 1 | 270.27 | 12.00 |
| qwen | replicated | amem | no_delete | one_on_one | 1 | 1 | 1 | 270.27 | 12.00 |
| qwen | replicated | amem | no_supersession | client | 1 | 0 | 1 | 258.87 | 12.33 |
| qwen | replicated | amem | no_supersession | conference | 1 | 0 | 0 | 258.87 | 12.33 |
| qwen | replicated | amem | no_supersession | home_city | 1 | 1 | 1 | 258.87 | 12.33 |
| qwen | replicated | amem | no_supersession | manager | 1 | 1 | 1 | 258.87 | 12.33 |
| qwen | replicated | amem | no_supersession | one_on_one | 1 | 1 | 1 | 258.87 | 12.33 |
| qwen | replicated | amem | writer_scoped | client | 1 | 1 | 1 | 260.33 | 11.40 |
| qwen | replicated | amem | writer_scoped | conference | 1 | 1 | 1 | 260.33 | 11.40 |
| qwen | replicated | amem | writer_scoped | home_city | 1 | 1 | 1 | 260.33 | 11.40 |
| qwen | replicated | amem | writer_scoped | manager | 1 | 1 | 1 | 260.33 | 11.40 |
| qwen | replicated | amem | writer_scoped | one_on_one | 1 | 1 | 1 | 260.33 | 11.40 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | recency | 0 | 0 | 5 | 5 | 232.20 | 11.00 |
| qwen | kernel | amem | h0 | contradiction | 0 | 0 | 5 | 5 | 220.80 | 11.20 |
| qwen | kernel | amem | h2 | recency | 0 | 0 | 5 | 4 | 202.40 | 9.20 |
| qwen | kernel | amem | h2 | contradiction | 0 | 0 | 5 | 4 | 206.00 | 9.60 |
| qwen | kernel | amem | no_delete | recency | 0 | 0 | 5 | 5 | 260.60 | 11.60 |
| qwen | kernel | amem | no_delete | contradiction | 0 | 0 | 5 | 5 | 248.00 | 12.80 |
| qwen | kernel | amem | no_supersession | recency | 0 | 0 | 5 | 0 | 255.80 | 12.40 |
| qwen | kernel | amem | no_supersession | contradiction | 0 | 0 | 5 | 3 | 234.60 | 13.20 |
| qwen | kernel | amem | writer_scoped | recency | 0 | 0 | 5 | 5 | 254.60 | 11.40 |
| qwen | kernel | amem | writer_scoped | contradiction | 0 | 0 | 5 | 5 | 228.40 | 11.60 |
| qwen | native | amem | h0 | recency | 0 | 0 | 5 | 4 | 188.20 | 9.40 |
| qwen | native | amem | h0 | contradiction | 0 | 0 | 5 | 2 | 167.40 | 9.00 |
| qwen | native | amem | h2 | recency | 0 | 0 | 5 | 2 | 107.60 | 5.20 |
| qwen | native | amem | h2 | contradiction | 0 | 0 | 5 | 1 | 92.80 | 5.00 |
| qwen | native | amem | no_delete | recency | 0 | 0 | 5 | 1 | 207.80 | 9.60 |
| qwen | native | amem | no_delete | contradiction | 0 | 0 | 5 | 3 | 166.20 | 9.00 |
| qwen | native | amem | no_visibility | recency | 0 | 0 | 5 | 4 | 217.60 | 10.00 |
| qwen | native | amem | no_visibility | contradiction | 0 | 0 | 5 | 3 | 185.40 | 10.00 |
| qwen | replicated | amem | h0 | recency | 0 | 0 | 5 | 5 | 255.20 | 11.20 |
| qwen | replicated | amem | h0 | contradiction | 0 | 0 | 5 | 5 | 223.60 | 11.40 |
| qwen | replicated | amem | h2 | recency | 0 | 0 | 5 | 3 | 123.60 | 5.00 |
| qwen | replicated | amem | h2 | contradiction | 0 | 0 | 5 | 3 | 120.60 | 4.80 |
| qwen | replicated | amem | no_delete | recency | 0 | 0 | 5 | 5 | 262.00 | 11.80 |
| qwen | replicated | amem | no_delete | contradiction | 0 | 0 | 5 | 5 | 261.80 | 12.60 |
| qwen | replicated | amem | no_supersession | recency | 0 | 0 | 5 | 0 | 248.60 | 12.20 |
| qwen | replicated | amem | no_supersession | contradiction | 0 | 0 | 5 | 3 | 231.80 | 13.00 |
| qwen | replicated | amem | writer_scoped | recency | 0 | 0 | 5 | 5 | 276.40 | 11.40 |
| qwen | replicated | amem | writer_scoped | contradiction | 0 | 0 | 5 | 5 | 248.00 | 11.80 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 5 | 10.80 | 0.00 | 10.80 | 4 | 3 | 5 | 3 |  |  | 253.60 | 10.80 |
| qwen | kernel | amem | h2 | 5 | 9.20 | 0.00 | 9.20 | 4 | 4 | 4 | 4 |  |  | 244.20 | 9.20 |
| qwen | kernel | amem | no_delete | 5 | 11.40 | 0.00 | 11.40 | 4 | 4 | 5 | 4 |  |  | 283.40 | 11.40 |
| qwen | kernel | amem | no_supersession | 5 | 11.40 | 0.00 | 11.40 | 4 | 3 | 5 | 3 |  |  | 265.40 | 11.40 |
| qwen | kernel | amem | writer_scoped | 5 | 11.20 | 0.00 | 11.20 | 4 | 4 | 5 | 4 |  |  | 279.40 | 11.20 |
| qwen | native | amem | h0 | 5 | 9.20 | 0.00 | 9.20 |  | 3 | 4 | 3 |  |  | 229.00 | 9.20 |
| qwen | native | amem | h2 | 5 | 5.40 | 0.00 | 5.40 |  | 3 | 2 | 2 |  |  | 157.20 | 5.40 |
| qwen | native | amem | no_delete | 5 | 9.40 | 0.00 | 9.40 |  | 3 | 4 | 3 |  |  | 231.00 | 9.40 |
| qwen | native | amem | no_visibility | 5 | 10.00 | 0.00 | 10.00 |  | 3 | 3 | 3 |  |  | 239.60 | 10.00 |
| qwen | replicated | amem | h0 | 5 | 11.20 | 0.00 | 11.20 | 4 | 4 | 5 | 4 |  |  | 277.20 | 11.20 |
| qwen | replicated | amem | h2 | 5 | 4.60 | 0.00 | 4.60 | 1 | 2 | 1 | 1 |  |  | 118.00 | 4.60 |
| qwen | replicated | amem | no_delete | 5 | 11.40 | 0.00 | 11.40 | 4 | 4 | 5 | 4 |  |  | 284.60 | 11.40 |
| qwen | replicated | amem | no_supersession | 5 | 11.40 | 0.00 | 11.40 | 5 | 4 | 5 | 4 |  |  | 282.40 | 11.40 |
| qwen | replicated | amem | writer_scoped | 5 | 10.80 | 0.00 | 10.80 | 4 | 4 | 5 | 4 |  |  | 271.60 | 10.80 |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 1 | 2 |  | 253.60 | 10.80 |
| qwen | kernel | amem | h0 | 2 | 3 |  | 253.60 | 10.80 |
| qwen | kernel | amem | h2 | 0 | 1 |  | 244.20 | 9.20 |
| qwen | kernel | amem | h2 | 2 | 4 |  | 244.20 | 9.20 |
| qwen | kernel | amem | no_delete | 1 | 1 |  | 283.40 | 11.40 |
| qwen | kernel | amem | no_delete | 2 | 4 |  | 283.40 | 11.40 |
| qwen | kernel | amem | no_supersession | 1 | 2 |  | 265.40 | 11.40 |
| qwen | kernel | amem | no_supersession | 2 | 3 |  | 265.40 | 11.40 |
| qwen | kernel | amem | writer_scoped | 1 | 1 |  | 279.40 | 11.20 |
| qwen | kernel | amem | writer_scoped | 2 | 4 |  | 279.40 | 11.20 |
| qwen | native | amem | h0 | 0 | 1 |  | 229.00 | 9.20 |
| qwen | native | amem | h0 | 1 | 1 |  | 229.00 | 9.20 |
| qwen | native | amem | h0 | 2 | 3 |  | 229.00 | 9.20 |
| qwen | native | amem | h2 | 0 | 2 |  | 157.20 | 5.40 |
| qwen | native | amem | h2 | 1 | 1 |  | 157.20 | 5.40 |
| qwen | native | amem | h2 | 2 | 2 |  | 157.20 | 5.40 |
| qwen | native | amem | no_delete | 0 | 1 |  | 231.00 | 9.40 |
| qwen | native | amem | no_delete | 1 | 1 |  | 231.00 | 9.40 |
| qwen | native | amem | no_delete | 2 | 3 |  | 231.00 | 9.40 |
| qwen | native | amem | no_visibility | 0 | 2 |  | 239.60 | 10.00 |
| qwen | native | amem | no_visibility | 2 | 3 |  | 239.60 | 10.00 |
| qwen | replicated | amem | h0 | 1 | 1 |  | 277.20 | 11.20 |
| qwen | replicated | amem | h0 | 2 | 4 |  | 277.20 | 11.20 |
| qwen | replicated | amem | h2 | 0 | 3 |  | 118.00 | 4.60 |
| qwen | replicated | amem | h2 | 1 | 1 |  | 118.00 | 4.60 |
| qwen | replicated | amem | h2 | 2 | 1 |  | 118.00 | 4.60 |
| qwen | replicated | amem | no_delete | 1 | 1 |  | 284.60 | 11.40 |
| qwen | replicated | amem | no_delete | 2 | 4 |  | 284.60 | 11.40 |
| qwen | replicated | amem | no_supersession | 1 | 1 |  | 282.40 | 11.40 |
| qwen | replicated | amem | no_supersession | 2 | 4 |  | 282.40 | 11.40 |
| qwen | replicated | amem | writer_scoped | 1 | 1 |  | 271.60 | 10.80 |
| qwen | replicated | amem | writer_scoped | 2 | 4 |  | 271.60 | 10.80 |

