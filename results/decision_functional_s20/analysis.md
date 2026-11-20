# Benchmark v2 analysis

13 cells, 65 user-trials, 0 failed.

Every table but the criteria ends with `block_tokens` and `block_rows`: the mean block, in tokens and in rows, of a set of the row's cell's probes. In the pass matrix, the row's own probes (a deletion row split by echo, its split's); in the kernel-against-replicated table, the row's probe type, per locus (all probes for `identical blocks`); in the integration table and the integration readings, the cell's integration probes; elsewhere, the row's probe type where the row names one, else all of the cell's probes. A reading's row that splits a cell's probes further (a slot, a carrier, a count of base rows) shows its set's mean, not its own.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 0 | 1 | 0 | 0 | 4 | 5 | 265.20 | 11.60 |
| qwen | kernel | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 240.00 | 12.60 |
| qwen | kernel | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 264.00 | 11.60 |
| qwen | kernel | inhouse | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 253.00 | 11.40 |
| qwen | kernel | inhouse | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 246.00 | 11.80 |
| qwen | kernel | inhouse | h0 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 0 | 1 | 0 | 0 | 2 | 2 | 263.00 | 12.00 |
| qwen | kernel | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 266.67 | 11.33 |
| qwen | kernel | inhouse | no_memory | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 2 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 3 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 5 | 5 | 264.80 | 12.80 |
| qwen | kernel | inhouse | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 5 | 5 | 267.60 | 14.40 |
| qwen | kernel | inhouse | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 5 | 5 | 263.60 | 12.60 |
| qwen | kernel | inhouse | no_supersession | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 1.00 | 5 | 5 |  |  | 0 | 0 | 5 | 5 | 237.60 | 12.60 |
| qwen | kernel | inhouse | no_supersession | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 0 | 5 | 5 | 250.40 | 13.20 |
| qwen | kernel | inhouse | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 2 | 234.50 | 13.00 |
| qwen | kernel | inhouse | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 3 | 3 | 285.00 | 12.67 |
| qwen | kernel | inhouse | writer_scoped | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 0 | 4 | 5 | 251.20 | 11.80 |
| qwen | kernel | inhouse | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 248.20 | 13.00 |
| qwen | kernel | inhouse | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 266.40 | 11.60 |
| qwen | kernel | inhouse | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 257.40 | 11.60 |
| qwen | kernel | inhouse | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 254.00 | 12.20 |
| qwen | kernel | inhouse | writer_scoped | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 0 | 2 | 2 | 228.00 | 12.50 |
| qwen | kernel | inhouse | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 266.67 | 11.33 |
| qwen | kernel | inhouse | wrong_user | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 0 | 1 | 0 | 0 | 4 | 5 | 265.20 | 11.60 |
| qwen | kernel | inhouse | wrong_user | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 240.00 | 12.60 |
| qwen | kernel | inhouse | wrong_user | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 264.00 | 11.60 |
| qwen | kernel | inhouse | wrong_user | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 253.00 | 11.40 |
| qwen | kernel | inhouse | wrong_user | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 246.00 | 11.80 |
| qwen | kernel | inhouse | wrong_user | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 0 | 1 | 0 | 0 | 2 | 2 | 263.00 | 12.00 |
| qwen | kernel | inhouse | wrong_user | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 266.67 | 11.33 |
| qwen | native | inhouse | h0 | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 5 |  | 5 | 197.80 | 9.20 |
| qwen | native | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 5 |  | 5 | 182.60 | 9.00 |
| qwen | native | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 5 |  | 5 | 214.00 | 9.20 |
| qwen | native | inhouse | h0 | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 2 |  |  | 0 | 5 |  | 5 | 191.80 | 9.40 |
| qwen | native | inhouse | h0 | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 5 |  | 5 | 166.40 | 9.00 |
| qwen | native | inhouse | h0 | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 2 |  | 2 | 181.00 | 9.00 |
| qwen | native | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 | 209.00 | 9.33 |
| qwen | native | inhouse | no_memory | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 |  | 5 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 |  | 5 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 0 |  | 5 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 |  | 5 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 |  | 5 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 |  | 2 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 |  | 3 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 1 | 1 | 0 | 4 |  | 5 | 210.00 | 9.20 |
| qwen | native | inhouse | wrong_user | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 4 |  | 5 | 189.00 | 9.00 |
| qwen | native | inhouse | wrong_user | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 4 |  | 5 | 218.60 | 9.20 |
| qwen | native | inhouse | wrong_user | recency | 2 | 5 | 0.40 | 0.12 | 0.77 | 1.00 | 3 | 2 |  |  | 0 | 4 |  | 5 | 197.60 | 9.40 |
| qwen | native | inhouse | wrong_user | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 4 |  | 5 | 205.60 | 9.00 |
| qwen | native | inhouse | wrong_user | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 1 | 1 | 0 | 1 |  | 2 | 214.50 | 9.00 |
| qwen | native | inhouse | wrong_user | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 3 |  | 3 | 207.00 | 9.33 |
| qwen | replicated | inhouse | h0 | deletion | 4 | 5 | 0.80 | 0.38 | 0.96 |  |  |  | 0 | 1 | 0 | 0 | 4 | 5 | 265.20 | 11.60 |
| qwen | replicated | inhouse | h0 | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 240.00 | 12.60 |
| qwen | replicated | inhouse | h0 | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 264.00 | 11.60 |
| qwen | replicated | inhouse | h0 | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 253.00 | 11.40 |
| qwen | replicated | inhouse | h0 | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 246.00 | 11.80 |
| qwen | replicated | inhouse | h0 | deletion (echo) | 1 | 2 | 0.50 | 0.09 | 0.91 |  |  |  | 0 | 1 | 0 | 0 | 2 | 2 | 263.00 | 12.00 |
| qwen | replicated | inhouse | h0 | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 266.67 | 11.33 |
| qwen | replicated | inhouse | no_memory | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | recall | 0 | 5 | 0.00 | 0.00 | 0.43 |  |  |  |  |  | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | contradiction | 0 | 5 | 0.00 | 0.00 | 0.43 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 5 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 2 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 3 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 5 | 5 | 264.80 | 12.80 |
| qwen | replicated | inhouse | no_supersession | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 5 | 5 | 267.60 | 14.40 |
| qwen | replicated | inhouse | no_supersession | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 5 | 5 | 263.60 | 12.60 |
| qwen | replicated | inhouse | no_supersession | recency | 0 | 5 | 0.00 | 0.00 | 0.43 | 1.00 | 5 | 4 |  |  | 0 | 0 | 5 | 5 | 237.60 | 12.60 |
| qwen | replicated | inhouse | no_supersession | contradiction | 3 | 5 | 0.60 | 0.23 | 0.88 | 0.60 | 0 | 0 |  |  | 0 | 0 | 5 | 5 | 250.40 | 13.20 |
| qwen | replicated | inhouse | no_supersession | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 2 | 234.50 | 13.00 |
| qwen | replicated | inhouse | no_supersession | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 3 | 3 | 285.00 | 12.67 |
| qwen | replicated | inhouse | writer_scoped | deletion | 3 | 5 | 0.60 | 0.23 | 0.88 |  |  |  | 2 | 2 | 0 | 0 | 4 | 5 | 251.20 | 11.80 |
| qwen | replicated | inhouse | writer_scoped | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 4 | 5 | 248.20 | 13.00 |
| qwen | replicated | inhouse | writer_scoped | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 4 | 5 | 266.40 | 11.60 |
| qwen | replicated | inhouse | writer_scoped | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 257.40 | 11.60 |
| qwen | replicated | inhouse | writer_scoped | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 4 | 5 | 254.00 | 12.20 |
| qwen | replicated | inhouse | writer_scoped | deletion (echo) | 0 | 2 | 0.00 | 0.00 | 0.66 |  |  |  | 2 | 2 | 0 | 0 | 2 | 2 | 228.00 | 12.50 |
| qwen | replicated | inhouse | writer_scoped | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 266.67 | 11.33 |
| qwen | replicated | inhouse | wrong_user | deletion | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 3 | 5 | 248.20 | 11.00 |
| qwen | replicated | inhouse | wrong_user | privacy | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 3 | 5 | 223.40 | 11.80 |
| qwen | replicated | inhouse | wrong_user | recall | 5 | 5 | 1.00 | 0.57 | 1.00 |  |  |  |  |  | 0 | 0 | 3 | 5 | 251.00 | 11.20 |
| qwen | replicated | inhouse | wrong_user | recency | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 3 | 5 | 237.20 | 11.60 |
| qwen | replicated | inhouse | wrong_user | contradiction | 5 | 5 | 1.00 | 0.57 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 3 | 5 | 235.40 | 11.40 |
| qwen | replicated | inhouse | wrong_user | deletion (echo) | 2 | 2 | 1.00 | 0.34 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 1 | 2 | 270.50 | 10.00 |
| qwen | replicated | inhouse | wrong_user | deletion (no echo) | 3 | 3 | 1.00 | 0.44 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 2 | 3 | 233.33 | 11.67 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 30 | 0 | 24 | 275.00 | 300 | 259.37 | 11.60 |
| qwen | kernel | inhouse | no_memory | 30 | 0 | 0 | 0.00 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | 30 | 0 | 30 | 267.00 | 300 | 262.93 | 12.73 |
| qwen | kernel | inhouse | writer_scoped | 30 | 0 | 24 | 275.00 | 300 | 261.37 | 11.80 |
| qwen | kernel | inhouse | wrong_user | 30 | 0 | 24 | 275.00 | 300 | 259.37 | 11.60 |
| qwen | native | inhouse | h0 | 30 | 30 |  | 176.00 | 283 | 198.03 | 9.17 |
| qwen | native | inhouse | no_memory | 30 | 0 |  | 0.00 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | 30 | 24 |  | 192.00 | 332 | 210.53 | 9.13 |
| qwen | replicated | inhouse | h0 | 30 | 0 | 24 | 275.00 | 300 | 259.37 | 11.60 |
| qwen | replicated | inhouse | no_memory | 30 | 0 | 0 | 0.00 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | 30 | 0 | 30 | 267.00 | 300 | 262.93 | 12.73 |
| qwen | replicated | inhouse | writer_scoped | 30 | 0 | 24 | 275.00 | 300 | 261.37 | 11.80 |
| qwen | replicated | inhouse | wrong_user | 30 | 0 | 18 | 246.50 | 300 | 243.40 | 11.30 |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar | kernel_block_tokens | kernel_block_rows | replicated_block_tokens | replicated_block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | inhouse | deletion | 5 | 0 | 0 | 1.00 | 265.20 | 11.60 | 265.20 | 11.60 |
| qwen | inhouse | privacy | 5 | 0 | 0 | 1.00 | 240.00 | 12.60 | 240.00 | 12.60 |
| qwen | inhouse | recall | 5 | 0 | 0 | 1.00 | 264.00 | 11.60 | 264.00 | 11.60 |
| qwen | inhouse | recency | 5 | 0 | 0 | 1.00 | 253.00 | 11.40 | 253.00 | 11.40 |
| qwen | inhouse | contradiction | 5 | 0 | 0 | 1.00 | 246.00 | 11.80 | 246.00 | 11.80 |
| qwen | inhouse | identical blocks | 30 | 30 |  |  | 259.37 | 11.60 | 259.37 | 11.60 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`, or an `entity`: a Graphiti scrub deleted it with an entity a form names, or `derived`: an A-MEM scrub deleted it because its derived text carried a form; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the history scrub (Mem0: `messages` deleted, `history` records cleared; A-MEM: `history` counts the carrier notes it deleted, as `derived` does), rows later writes `swept` and writes `suppressed`, and `scoped`: revokes through a forget the kernel ran under an ablated scope (no_delete, writer_scoped since Subtask 19; counted in no other column).

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | entity | derived | other_agents | same_writer | no_values | messages | history | swept | suppressed | scoped | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 259.37 | 11.60 |
| qwen | kernel | inhouse | no_memory | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 262.93 | 12.73 |
| qwen | kernel | inhouse | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 261.37 | 11.80 |
| qwen | kernel | inhouse | wrong_user | 5 | 5 | 7 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 259.37 | 11.60 |
| qwen | replicated | inhouse | h0 | 5 | 5 | 7 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 259.37 | 11.60 |
| qwen | replicated | inhouse | no_memory | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | 5 | 5 | 7 | 5 | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 262.93 | 12.73 |
| qwen | replicated | inhouse | writer_scoped | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 261.37 | 11.80 |
| qwen | replicated | inhouse | wrong_user | 5 | 5 | 6 | 5 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 243.40 | 11.30 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 10 | 10 | 10 | 30 | 0 | 60 | 259.37 | 11.60 |
| qwen | kernel | inhouse | no_memory | 0 | 0 | 0 | 30 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | 0 | 10 | 0 | 30 | 30 | 0 | 262.93 | 12.73 |
| qwen | kernel | inhouse | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 | 261.37 | 11.80 |
| qwen | kernel | inhouse | wrong_user | 10 | 10 | 10 | 30 | 0 | 60 | 259.37 | 11.60 |
| qwen | native | inhouse | h0 | 0 | 10 | 0 | 30 | 26 | 0 | 198.03 | 9.17 |
| qwen | native | inhouse | no_memory | 0 | 0 | 0 | 30 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | 0 | 5 | 0 | 30 | 20 | 0 | 210.53 | 9.13 |
| qwen | replicated | inhouse | h0 | 10 | 10 | 10 | 30 | 0 | 60 | 259.37 | 11.60 |
| qwen | replicated | inhouse | no_memory | 0 | 0 | 0 | 30 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | 0 | 10 | 0 | 30 | 30 | 0 | 262.93 | 12.73 |
| qwen | replicated | inhouse | writer_scoped | 10 | 10 | 10 | 30 | 0 | 60 | 261.37 | 11.80 |
| qwen | replicated | inhouse | wrong_user | 13 | 5 | 5 | 30 | 0 | 66 | 243.40 | 11.30 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 5 | 4 | 1 | 0 | 265.20 | 11.60 |
| qwen | kernel | inhouse | h0 | privacy | 5 | 5 | 0 | 0 | 240.00 | 12.60 |
| qwen | kernel | inhouse | no_memory | deletion | 5 | 5 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | privacy | 5 | 5 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | deletion | 5 | 5 | 0 | 0 | 264.80 | 12.80 |
| qwen | kernel | inhouse | no_supersession | privacy | 5 | 5 | 0 | 0 | 267.60 | 14.40 |
| qwen | kernel | inhouse | writer_scoped | deletion | 5 | 3 | 2 | 0 | 251.20 | 11.80 |
| qwen | kernel | inhouse | writer_scoped | privacy | 5 | 5 | 0 | 0 | 248.20 | 13.00 |
| qwen | kernel | inhouse | wrong_user | deletion | 5 | 4 | 1 | 0 | 265.20 | 11.60 |
| qwen | kernel | inhouse | wrong_user | privacy | 5 | 5 | 0 | 0 | 240.00 | 12.60 |
| qwen | native | inhouse | h0 | deletion | 5 | 3 | 2 | 0 | 197.80 | 9.20 |
| qwen | native | inhouse | h0 | privacy | 5 | 5 | 0 | 0 | 182.60 | 9.00 |
| qwen | native | inhouse | no_memory | deletion | 5 | 5 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | privacy | 5 | 5 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | deletion | 5 | 4 | 1 | 0 | 210.00 | 9.20 |
| qwen | native | inhouse | wrong_user | privacy | 5 | 5 | 0 | 0 | 189.00 | 9.00 |
| qwen | replicated | inhouse | h0 | deletion | 5 | 4 | 1 | 0 | 265.20 | 11.60 |
| qwen | replicated | inhouse | h0 | privacy | 5 | 5 | 0 | 0 | 240.00 | 12.60 |
| qwen | replicated | inhouse | no_memory | deletion | 5 | 5 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | privacy | 5 | 5 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | deletion | 5 | 5 | 0 | 0 | 264.80 | 12.80 |
| qwen | replicated | inhouse | no_supersession | privacy | 5 | 5 | 0 | 0 | 267.60 | 14.40 |
| qwen | replicated | inhouse | writer_scoped | deletion | 5 | 3 | 2 | 0 | 251.20 | 11.80 |
| qwen | replicated | inhouse | writer_scoped | privacy | 5 | 5 | 0 | 0 | 248.20 | 13.00 |
| qwen | replicated | inhouse | wrong_user | deletion | 5 | 5 | 0 | 0 | 248.20 | 11.00 |
| qwen | replicated | inhouse | wrong_user | privacy | 5 | 5 | 0 | 0 | 223.40 | 11.80 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | answer only | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | writer_scoped | echo | 2 | 261.37 | 11.80 |
| qwen | kernel | inhouse | wrong_user | answer only | 1 | 259.37 | 11.60 |
| qwen | native | inhouse | h0 | echo | 2 | 198.03 | 9.17 |
| qwen | native | inhouse | wrong_user | echo | 1 | 210.53 | 9.13 |
| qwen | replicated | inhouse | h0 | answer only | 1 | 259.37 | 11.60 |
| qwen | replicated | inhouse | writer_scoped | echo | 2 | 261.37 | 11.80 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | none | 1 | 4 | 259.37 | 11.60 |
| qwen | kernel | inhouse | no_memory | none | 0 | 5 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | none | 0 | 5 | 262.93 | 12.73 |
| qwen | kernel | inhouse | writer_scoped | echo | 2 | 0 | 261.37 | 11.80 |
| qwen | kernel | inhouse | writer_scoped | none | 0 | 3 | 261.37 | 11.80 |
| qwen | kernel | inhouse | wrong_user | none | 1 | 4 | 259.37 | 11.60 |
| qwen | native | inhouse | h0 | echo | 2 | 0 | 198.03 | 9.17 |
| qwen | native | inhouse | h0 | none | 0 | 3 | 198.03 | 9.17 |
| qwen | native | inhouse | no_memory | none | 0 | 5 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | echo | 1 | 0 | 210.53 | 9.13 |
| qwen | native | inhouse | wrong_user | none | 0 | 4 | 210.53 | 9.13 |
| qwen | replicated | inhouse | h0 | none | 1 | 4 | 259.37 | 11.60 |
| qwen | replicated | inhouse | no_memory | none | 0 | 5 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | none | 0 | 5 | 262.93 | 12.73 |
| qwen | replicated | inhouse | writer_scoped | echo | 2 | 0 | 261.37 | 11.80 |
| qwen | replicated | inhouse | writer_scoped | none | 0 | 3 | 261.37 | 11.80 |
| qwen | replicated | inhouse | wrong_user | none | 0 | 5 | 243.40 | 11.30 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | recall | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | recency | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | contradiction | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | recency | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 237.60 | 12.60 |
| qwen | kernel | inhouse | no_supersession | contradiction | 2 | 0 | 0 | 0 | 0 | 0 | 2 | 250.40 | 13.20 |
| qwen | native | inhouse | h0 | recency | 3 | 3 | 0 | 0 | 0 | 0 | 3 | 191.80 | 9.40 |
| qwen | native | inhouse | h0 | contradiction | 2 | 0 | 0 | 0 | 0 | 0 | 2 | 166.40 | 9.00 |
| qwen | native | inhouse | no_memory | recall | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | recency | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | contradiction | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | recency | 3 | 3 | 0 | 0 | 0 | 0 | 3 | 197.60 | 9.40 |
| qwen | replicated | inhouse | no_memory | recall | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | recency | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | contradiction | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | recency | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 237.60 | 12.60 |
| qwen | replicated | inhouse | no_supersession | contradiction | 2 | 0 | 0 | 0 | 0 | 0 | 2 | 250.40 | 13.20 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | client | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | h0 | conference | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | h0 | home_city | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | h0 | manager | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | h0 | one_on_one | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | no_memory | client | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | conference | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | home_city | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | manager | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | one_on_one | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | client | 1 | 0 | 0 | 262.93 | 12.73 |
| qwen | kernel | inhouse | no_supersession | conference | 1 | 0 | 0 | 262.93 | 12.73 |
| qwen | kernel | inhouse | no_supersession | home_city | 1 | 1 | 1 | 262.93 | 12.73 |
| qwen | kernel | inhouse | no_supersession | manager | 1 | 1 | 1 | 262.93 | 12.73 |
| qwen | kernel | inhouse | no_supersession | one_on_one | 1 | 1 | 1 | 262.93 | 12.73 |
| qwen | kernel | inhouse | writer_scoped | client | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | kernel | inhouse | writer_scoped | conference | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | kernel | inhouse | writer_scoped | home_city | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | kernel | inhouse | writer_scoped | manager | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | kernel | inhouse | writer_scoped | one_on_one | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | kernel | inhouse | wrong_user | client | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | wrong_user | conference | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | wrong_user | home_city | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | wrong_user | manager | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | kernel | inhouse | wrong_user | one_on_one | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | native | inhouse | h0 | client | 1 | 1 | 1 | 198.03 | 9.17 |
| qwen | native | inhouse | h0 | conference | 1 | 0 | 0 | 198.03 | 9.17 |
| qwen | native | inhouse | h0 | home_city | 1 | 0 | 0 | 198.03 | 9.17 |
| qwen | native | inhouse | h0 | manager | 1 | 1 | 1 | 198.03 | 9.17 |
| qwen | native | inhouse | h0 | one_on_one | 1 | 1 | 1 | 198.03 | 9.17 |
| qwen | native | inhouse | no_memory | client | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | conference | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | home_city | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | manager | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | one_on_one | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | client | 1 | 1 | 1 | 210.53 | 9.13 |
| qwen | native | inhouse | wrong_user | conference | 1 | 1 | 1 | 210.53 | 9.13 |
| qwen | native | inhouse | wrong_user | home_city | 1 | 1 | 1 | 210.53 | 9.13 |
| qwen | native | inhouse | wrong_user | manager | 1 | 1 | 1 | 210.53 | 9.13 |
| qwen | native | inhouse | wrong_user | one_on_one | 1 | 1 | 1 | 210.53 | 9.13 |
| qwen | replicated | inhouse | h0 | client | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | replicated | inhouse | h0 | conference | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | replicated | inhouse | h0 | home_city | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | replicated | inhouse | h0 | manager | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | replicated | inhouse | h0 | one_on_one | 1 | 1 | 1 | 259.37 | 11.60 |
| qwen | replicated | inhouse | no_memory | client | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | conference | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | home_city | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | manager | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | one_on_one | 1 | 0 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | client | 1 | 0 | 0 | 262.93 | 12.73 |
| qwen | replicated | inhouse | no_supersession | conference | 1 | 0 | 0 | 262.93 | 12.73 |
| qwen | replicated | inhouse | no_supersession | home_city | 1 | 1 | 1 | 262.93 | 12.73 |
| qwen | replicated | inhouse | no_supersession | manager | 1 | 1 | 1 | 262.93 | 12.73 |
| qwen | replicated | inhouse | no_supersession | one_on_one | 1 | 1 | 1 | 262.93 | 12.73 |
| qwen | replicated | inhouse | writer_scoped | client | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | replicated | inhouse | writer_scoped | conference | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | replicated | inhouse | writer_scoped | home_city | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | replicated | inhouse | writer_scoped | manager | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | replicated | inhouse | writer_scoped | one_on_one | 1 | 1 | 1 | 261.37 | 11.80 |
| qwen | replicated | inhouse | wrong_user | client | 1 | 1 | 1 | 243.40 | 11.30 |
| qwen | replicated | inhouse | wrong_user | conference | 1 | 1 | 1 | 243.40 | 11.30 |
| qwen | replicated | inhouse | wrong_user | home_city | 1 | 1 | 1 | 243.40 | 11.30 |
| qwen | replicated | inhouse | wrong_user | manager | 1 | 1 | 1 | 243.40 | 11.30 |
| qwen | replicated | inhouse | wrong_user | one_on_one | 1 | 1 | 1 | 243.40 | 11.30 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | recency | 0 | 0 | 5 | 5 | 253.00 | 11.40 |
| qwen | kernel | inhouse | h0 | contradiction | 0 | 0 | 5 | 5 | 246.00 | 11.80 |
| qwen | kernel | inhouse | no_memory | recency | 0 | 0 | 5 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | contradiction | 0 | 0 | 5 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | recency | 0 | 0 | 5 | 0 | 237.60 | 12.60 |
| qwen | kernel | inhouse | no_supersession | contradiction | 0 | 0 | 5 | 3 | 250.40 | 13.20 |
| qwen | kernel | inhouse | writer_scoped | recency | 0 | 0 | 5 | 5 | 257.40 | 11.60 |
| qwen | kernel | inhouse | writer_scoped | contradiction | 0 | 0 | 5 | 5 | 254.00 | 12.20 |
| qwen | kernel | inhouse | wrong_user | recency | 0 | 0 | 5 | 5 | 253.00 | 11.40 |
| qwen | kernel | inhouse | wrong_user | contradiction | 0 | 0 | 5 | 5 | 246.00 | 11.80 |
| qwen | native | inhouse | h0 | recency | 0 | 0 | 5 | 2 | 191.80 | 9.40 |
| qwen | native | inhouse | h0 | contradiction | 0 | 0 | 5 | 3 | 166.40 | 9.00 |
| qwen | native | inhouse | no_memory | recency | 0 | 0 | 5 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | no_memory | contradiction | 0 | 0 | 5 | 0 | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | recency | 0 | 0 | 5 | 2 | 197.60 | 9.40 |
| qwen | native | inhouse | wrong_user | contradiction | 0 | 0 | 5 | 5 | 205.60 | 9.00 |
| qwen | replicated | inhouse | h0 | recency | 0 | 0 | 5 | 5 | 253.00 | 11.40 |
| qwen | replicated | inhouse | h0 | contradiction | 0 | 0 | 5 | 5 | 246.00 | 11.80 |
| qwen | replicated | inhouse | no_memory | recency | 0 | 0 | 5 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_memory | contradiction | 0 | 0 | 5 | 0 | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | recency | 0 | 0 | 5 | 0 | 237.60 | 12.60 |
| qwen | replicated | inhouse | no_supersession | contradiction | 0 | 0 | 5 | 3 | 250.40 | 13.20 |
| qwen | replicated | inhouse | writer_scoped | recency | 0 | 0 | 5 | 5 | 257.40 | 11.60 |
| qwen | replicated | inhouse | writer_scoped | contradiction | 0 | 0 | 5 | 5 | 254.00 | 12.20 |
| qwen | replicated | inhouse | wrong_user | recency | 0 | 0 | 5 | 5 | 237.20 | 11.60 |
| qwen | replicated | inhouse | wrong_user | contradiction | 0 | 0 | 5 | 5 | 235.40 | 11.40 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 5 | 10.60 | 0.00 | 10.60 | 4 | 5 | 5 | 5 |  |  | 288.00 | 10.60 |
| qwen | kernel | inhouse | no_memory | 5 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0 |  |  | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | 5 | 10.80 | 0.00 | 10.80 | 5 | 5 | 5 | 5 |  |  | 293.60 | 10.80 |
| qwen | kernel | inhouse | writer_scoped | 5 | 10.60 | 0.00 | 10.60 | 4 | 5 | 5 | 5 |  |  | 291.00 | 10.60 |
| qwen | kernel | inhouse | wrong_user | 5 | 10.60 | 0.00 | 10.60 | 4 | 5 | 5 | 5 |  |  | 288.00 | 10.60 |
| qwen | native | inhouse | h0 | 5 | 9.20 | 0.00 | 9.20 |  | 3 | 5 | 3 |  |  | 235.60 | 9.20 |
| qwen | native | inhouse | no_memory | 5 | 0.00 | 0.00 | 0.00 |  | 0 | 0 | 0 |  |  | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | 5 | 9.00 | 0.00 | 9.00 |  | 3 | 3 | 2 |  |  | 242.40 | 9.00 |
| qwen | replicated | inhouse | h0 | 5 | 10.60 | 0.00 | 10.60 | 4 | 5 | 5 | 5 |  |  | 288.00 | 10.60 |
| qwen | replicated | inhouse | no_memory | 5 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0 |  |  | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | 5 | 10.80 | 0.00 | 10.80 | 5 | 5 | 5 | 5 |  |  | 293.60 | 10.80 |
| qwen | replicated | inhouse | writer_scoped | 5 | 10.60 | 0.00 | 10.60 | 4 | 5 | 5 | 5 |  |  | 291.00 | 10.60 |
| qwen | replicated | inhouse | wrong_user | 5 | 10.80 | 0.00 | 10.80 | 3 | 4 | 3 | 2 |  |  | 265.20 | 10.80 |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 2 | 5 |  | 288.00 | 10.60 |
| qwen | kernel | inhouse | no_memory | 0 | 5 |  | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_supersession | 2 | 5 |  | 293.60 | 10.80 |
| qwen | kernel | inhouse | writer_scoped | 2 | 5 |  | 291.00 | 10.60 |
| qwen | kernel | inhouse | wrong_user | 2 | 5 |  | 288.00 | 10.60 |
| qwen | native | inhouse | h0 | 1 | 2 |  | 235.60 | 9.20 |
| qwen | native | inhouse | h0 | 2 | 3 |  | 235.60 | 9.20 |
| qwen | native | inhouse | no_memory | 0 | 5 |  | 0.00 | 0.00 |
| qwen | native | inhouse | wrong_user | 0 | 1 |  | 242.40 | 9.00 |
| qwen | native | inhouse | wrong_user | 1 | 2 |  | 242.40 | 9.00 |
| qwen | native | inhouse | wrong_user | 2 | 2 |  | 242.40 | 9.00 |
| qwen | replicated | inhouse | h0 | 2 | 5 |  | 288.00 | 10.60 |
| qwen | replicated | inhouse | no_memory | 0 | 5 |  | 0.00 | 0.00 |
| qwen | replicated | inhouse | no_supersession | 2 | 5 |  | 293.60 | 10.80 |
| qwen | replicated | inhouse | writer_scoped | 2 | 5 |  | 291.00 | 10.60 |
| qwen | replicated | inhouse | wrong_user | 1 | 3 |  | 265.20 | 10.80 |
| qwen | replicated | inhouse | wrong_user | 2 | 2 |  | 265.20 | 10.80 |

## Decision probe (Amendment 10)

Two items per user, four options each (chance 0.25), scored exactly from the letter named. Accuracy with its 95% Wilson interval; each error as its count and (its share of the items scored); `turn_errors`, items with a turn error (recorded, not scored); `echo_d1`, echo users' d1 items, and how many picked the revoked option.

| model | locus | backend | condition | items | correct | accuracy | ci_low | ci_high | stale | revoked | private | foreign | no_letter | multiple_letters | turn_errors | echo_d1 | echo_d1_revoked |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 10 | 10 | 1.00 | 0.72 | 1.00 | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |
| qwen | kernel | inhouse | no_memory | 10 | 0 | 0.00 | 0.00 | 0.28 | 3 (0.30) | 2 (0.20) | 1 (0.10) | 4 (0.40) | 0 (0.00) | 0 (0.00) | 0 | 2 | 1 |
| qwen | kernel | inhouse | no_supersession | 10 | 5 | 0.50 | 0.24 | 0.76 | 5 (0.50) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |
| qwen | kernel | inhouse | writer_scoped | 10 | 9 | 0.90 | 0.60 | 0.98 | 0 (0.00) | 1 (0.10) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 1 |
| qwen | kernel | inhouse | wrong_user | 10 | 10 | 1.00 | 0.72 | 1.00 | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |
| qwen | native | inhouse | h0 | 10 | 3 | 0.30 | 0.11 | 0.60 | 7 (0.70) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |
| qwen | native | inhouse | no_memory | 10 | 0 | 0.00 | 0.00 | 0.28 | 3 (0.30) | 2 (0.20) | 1 (0.10) | 4 (0.40) | 0 (0.00) | 0 (0.00) | 0 | 2 | 1 |
| qwen | native | inhouse | wrong_user | 10 | 6 | 0.60 | 0.31 | 0.83 | 1 (0.10) | 0 (0.00) | 0 (0.00) | 3 (0.30) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |
| qwen | replicated | inhouse | h0 | 10 | 10 | 1.00 | 0.72 | 1.00 | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |
| qwen | replicated | inhouse | no_memory | 10 | 0 | 0.00 | 0.00 | 0.28 | 3 (0.30) | 2 (0.20) | 1 (0.10) | 4 (0.40) | 0 (0.00) | 0 (0.00) | 0 | 2 | 1 |
| qwen | replicated | inhouse | no_supersession | 10 | 5 | 0.50 | 0.24 | 0.76 | 5 (0.50) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |
| qwen | replicated | inhouse | writer_scoped | 10 | 9 | 0.90 | 0.60 | 0.98 | 0 (0.00) | 1 (0.10) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 (0.00) | 0 | 2 | 1 |
| qwen | replicated | inhouse | wrong_user | 10 | 7 | 0.70 | 0.40 | 0.89 | 0 (0.00) | 0 (0.00) | 0 (0.00) | 3 (0.30) | 0 (0.00) | 0 (0.00) | 0 | 2 | 0 |

### Functional criteria D1-D5

| criterion | holds | evidence |
|---|---|---|
| D1 full system: pooled accuracy >= 0.6 | True | 23 of 30 over 3 cells |
| D2 no_memory: pooled accuracy in [0.10, 0.45] | False | 0 of 30 over 3 cells |
| D3 no_supersession: more stale errors than the same loci's full system | True | stale 10 of 20 vs 0 of 20 |
| D4 writer_scoped: >= 1 revoked error among echo users' d1 items, 0 in the full system | True | revoked 2 of 4 vs 0 of 4 |
| D5 wrong_user: >= 1 foreign error in the replicated and native cells, 0 in the kernel's | True | foreign 6 of 20 vs 0 of 10 |

### Picks by option kind and letter

Of the items scored, those that named one letter (`picked`), by the kind of the option named (chance 0.25 each): count (share) [95% Wilson interval]; `must_not_use` is `revoked` on d1 and `private` on d2. Letters picked and the items' correct letters as A/B/C/D, each with a chi-square test's p against uniform.

| model | locus | backend | condition | item | items | picked | correct | stale | must_not_use | foreign | letters | letters_p | correct_letters | correct_letters_p | no_letter | multiple_letters | turn_errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | d1 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 3/1/0/1 | 0.28 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | kernel | inhouse | h0 | d2 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/1/2/0 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | kernel | inhouse | h0 | pooled | 10 | 10 | 10 (1.00) [0.72, 1.00] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 5/2/2/1 | 0.31 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | d1 | 5 | 5 | 0 (0.00) [0.00, 0.43] | 1 (0.20) [0.04, 0.62] | 2 (0.40) [0.12, 0.77] | 2 (0.40) [0.12, 0.77] | 1/1/2/1 | 0.90 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | d2 | 5 | 5 | 0 (0.00) [0.00, 0.43] | 2 (0.40) [0.12, 0.77] | 1 (0.20) [0.04, 0.62] | 2 (0.40) [0.12, 0.77] | 1/2/0/2 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | pooled | 10 | 10 | 0 (0.00) [0.00, 0.28] | 3 (0.30) [0.11, 0.60] | 3 (0.30) [0.11, 0.60] | 4 (0.40) [0.17, 0.69] | 2/3/2/3 | 0.94 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | d1 | 5 | 5 | 1 (0.20) [0.04, 0.62] | 4 (0.80) [0.38, 0.96] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/2/1/0 | 0.53 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | d2 | 5 | 5 | 4 (0.80) [0.38, 0.96] | 1 (0.20) [0.04, 0.62] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 1/1/2/1 | 0.90 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_supersession | pooled | 10 | 10 | 5 (0.50) [0.24, 0.76] | 5 (0.50) [0.24, 0.76] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 3/3/3/1 | 0.75 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | kernel | inhouse | writer_scoped | d1 | 5 | 5 | 4 (0.80) [0.38, 0.96] | 0 (0.00) [0.00, 0.43] | 1 (0.20) [0.04, 0.62] | 0 (0.00) [0.00, 0.43] | 2/1/0/2 | 0.53 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | kernel | inhouse | writer_scoped | d2 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/1/2/0 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | kernel | inhouse | writer_scoped | pooled | 10 | 10 | 9 (0.90) [0.60, 0.98] | 0 (0.00) [0.00, 0.28] | 1 (0.10) [0.02, 0.40] | 0 (0.00) [0.00, 0.28] | 4/2/2/2 | 0.75 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | kernel | inhouse | wrong_user | d1 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 3/1/0/1 | 0.28 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | kernel | inhouse | wrong_user | d2 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/1/2/0 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | kernel | inhouse | wrong_user | pooled | 10 | 10 | 10 (1.00) [0.72, 1.00] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 5/2/2/1 | 0.31 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | native | inhouse | h0 | d1 | 5 | 5 | 1 (0.20) [0.04, 0.62] | 4 (0.80) [0.38, 0.96] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/2/1/0 | 0.53 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | native | inhouse | h0 | d2 | 5 | 5 | 2 (0.40) [0.12, 0.77] | 3 (0.60) [0.23, 0.88] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 1/1/2/1 | 0.90 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | native | inhouse | h0 | pooled | 10 | 10 | 3 (0.30) [0.11, 0.60] | 7 (0.70) [0.40, 0.89] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 3/3/3/1 | 0.75 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | native | inhouse | no_memory | d1 | 5 | 5 | 0 (0.00) [0.00, 0.43] | 1 (0.20) [0.04, 0.62] | 2 (0.40) [0.12, 0.77] | 2 (0.40) [0.12, 0.77] | 1/1/2/1 | 0.90 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | native | inhouse | no_memory | d2 | 5 | 5 | 0 (0.00) [0.00, 0.43] | 2 (0.40) [0.12, 0.77] | 1 (0.20) [0.04, 0.62] | 2 (0.40) [0.12, 0.77] | 1/2/0/2 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | native | inhouse | no_memory | pooled | 10 | 10 | 0 (0.00) [0.00, 0.28] | 3 (0.30) [0.11, 0.60] | 3 (0.30) [0.11, 0.60] | 4 (0.40) [0.17, 0.69] | 2/3/2/3 | 0.94 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | native | inhouse | wrong_user | d1 | 5 | 5 | 4 (0.80) [0.38, 0.96] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 1 (0.20) [0.04, 0.62] | 4/0/0/1 | 0.04 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | native | inhouse | wrong_user | d2 | 5 | 5 | 2 (0.40) [0.12, 0.77] | 1 (0.20) [0.04, 0.62] | 0 (0.00) [0.00, 0.43] | 2 (0.40) [0.12, 0.77] | 1/1/2/1 | 0.90 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | native | inhouse | wrong_user | pooled | 10 | 10 | 6 (0.60) [0.31, 0.83] | 1 (0.10) [0.02, 0.40] | 0 (0.00) [0.00, 0.28] | 3 (0.30) [0.11, 0.60] | 5/1/2/2 | 0.31 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h0 | d1 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 3/1/0/1 | 0.28 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h0 | d2 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/1/2/0 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | replicated | inhouse | h0 | pooled | 10 | 10 | 10 (1.00) [0.72, 1.00] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 5/2/2/1 | 0.31 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_memory | d1 | 5 | 5 | 0 (0.00) [0.00, 0.43] | 1 (0.20) [0.04, 0.62] | 2 (0.40) [0.12, 0.77] | 2 (0.40) [0.12, 0.77] | 1/1/2/1 | 0.90 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_memory | d2 | 5 | 5 | 0 (0.00) [0.00, 0.43] | 2 (0.40) [0.12, 0.77] | 1 (0.20) [0.04, 0.62] | 2 (0.40) [0.12, 0.77] | 1/2/0/2 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_memory | pooled | 10 | 10 | 0 (0.00) [0.00, 0.28] | 3 (0.30) [0.11, 0.60] | 3 (0.30) [0.11, 0.60] | 4 (0.40) [0.17, 0.69] | 2/3/2/3 | 0.94 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | d1 | 5 | 5 | 1 (0.20) [0.04, 0.62] | 4 (0.80) [0.38, 0.96] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/2/1/0 | 0.53 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | d2 | 5 | 5 | 4 (0.80) [0.38, 0.96] | 1 (0.20) [0.04, 0.62] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 1/1/2/1 | 0.90 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | replicated | inhouse | no_supersession | pooled | 10 | 10 | 5 (0.50) [0.24, 0.76] | 5 (0.50) [0.24, 0.76] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 3/3/3/1 | 0.75 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | replicated | inhouse | writer_scoped | d1 | 5 | 5 | 4 (0.80) [0.38, 0.96] | 0 (0.00) [0.00, 0.43] | 1 (0.20) [0.04, 0.62] | 0 (0.00) [0.00, 0.43] | 2/1/0/2 | 0.53 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | replicated | inhouse | writer_scoped | d2 | 5 | 5 | 5 (1.00) [0.57, 1.00] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2/1/2/0 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | replicated | inhouse | writer_scoped | pooled | 10 | 10 | 9 (0.90) [0.60, 0.98] | 0 (0.00) [0.00, 0.28] | 1 (0.10) [0.02, 0.40] | 0 (0.00) [0.00, 0.28] | 4/2/2/2 | 0.75 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |
| qwen | replicated | inhouse | wrong_user | d1 | 5 | 5 | 4 (0.80) [0.38, 0.96] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 1 (0.20) [0.04, 0.62] | 4/0/0/1 | 0.04 | 3/1/0/1 | 0.28 | 0 | 0 | 0 |
| qwen | replicated | inhouse | wrong_user | d2 | 5 | 5 | 3 (0.60) [0.23, 0.88] | 0 (0.00) [0.00, 0.43] | 0 (0.00) [0.00, 0.43] | 2 (0.40) [0.12, 0.77] | 2/1/2/0 | 0.53 | 2/1/2/0 | 0.53 | 0 | 0 | 0 |
| qwen | replicated | inhouse | wrong_user | pooled | 10 | 10 | 7 (0.70) [0.40, 0.89] | 0 (0.00) [0.00, 0.28] | 0 (0.00) [0.00, 0.28] | 3 (0.30) [0.11, 0.60] | 6/1/2/1 | 0.08 | 5/2/2/1 | 0.31 | 0 | 0 | 0 |

