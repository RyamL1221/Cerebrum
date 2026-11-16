# Benchmark v2 analysis

7 cells, 210 user-trials, 0 failed.

Every table but the criteria ends with `block_tokens` and `block_rows`: the mean block, in tokens and in rows, of a set of the row's cell's probes. In the pass matrix, the row's own probes (a deletion row split by echo, its split's); in the kernel-against-replicated table, the row's probe type, per locus (all probes for `identical blocks`); in the integration table and the integration readings, the cell's integration probes; elsewhere, the row's probe type where the row names one, else all of the cell's probes. A reading's row that splits a cell's probes further (a slot, a carrier, a count of base rows) shows its set's mean, not its own.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 18 | 30 | 284.90 | 17.47 |
| qwen | kernel | graphiti | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 18 | 30 | 284.20 | 17.43 |
| qwen | kernel | graphiti | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 0 | 18 | 30 | 285.60 | 17.57 |
| qwen | kernel | graphiti | h0 | recency | 29 | 30 | 0.97 | 0.83 | 0.99 | 1.00 | 1 | 1 |  |  | 0 | 0 | 18 | 30 | 285.03 | 17.60 |
| qwen | kernel | graphiti | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 18 | 30 | 284.93 | 17.47 |
| qwen | kernel | graphiti | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 7 | 10 | 288.90 | 17.80 |
| qwen | kernel | graphiti | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 11 | 20 | 282.90 | 17.30 |
| qwen | kernel | inhouse | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 264.77 | 11.70 |
| qwen | kernel | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 255.53 | 12.03 |
| qwen | kernel | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 0 | 26 | 30 | 262.10 | 11.87 |
| qwen | kernel | inhouse | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 256.27 | 11.63 |
| qwen | kernel | inhouse | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 253.93 | 11.73 |
| qwen | kernel | inhouse | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 10 | 10 | 260.30 | 11.90 |
| qwen | kernel | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 16 | 20 | 267.00 | 11.60 |
| qwen | kernel | mem0 | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 30 | 30 | 283.43 | 11.83 |
| qwen | kernel | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 30 | 30 | 286.73 | 11.73 |
| qwen | kernel | mem0 | h0 | recall | 28 | 30 | 0.93 | 0.79 | 0.98 |  |  |  |  |  | 0 | 0 | 30 | 30 | 279.50 | 12.20 |
| qwen | kernel | mem0 | h0 | recency | 23 | 30 | 0.77 | 0.59 | 0.88 | 1.00 | 7 | 7 |  |  | 0 | 0 | 30 | 30 | 284.07 | 11.83 |
| qwen | kernel | mem0 | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 30 | 30 | 285.83 | 12.50 |
| qwen | kernel | mem0 | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 10 | 10 | 275.20 | 11.70 |
| qwen | kernel | mem0 | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 20 | 20 | 287.55 | 11.90 |
| qwen | native | graphiti | h0 | deletion | 23 | 30 | 0.77 | 0.59 | 0.88 |  |  |  | 7 | 7 | 0 | 30 |  | 30 | 159.90 | 9.20 |
| qwen | native | graphiti | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 |  | 30 | 158.73 | 9.00 |
| qwen | native | graphiti | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 |  | 30 | 160.47 | 9.47 |
| qwen | native | graphiti | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 30 |  | 30 | 158.73 | 9.43 |
| qwen | native | graphiti | h0 | contradiction | 26 | 30 | 0.87 | 0.70 | 0.95 | 0.87 | 0 | 0 |  |  | 0 | 30 |  | 30 | 159.53 | 9.13 |
| qwen | native | graphiti | h0 | deletion (echo) | 3 | 10 | 0.30 | 0.11 | 0.60 |  |  |  | 7 | 7 | 0 | 10 |  | 10 | 159.70 | 9.10 |
| qwen | native | graphiti | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 |  | 20 | 160.00 | 9.25 |
| qwen | replicated | graphiti | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 16 | 30 | 284.83 | 17.37 |
| qwen | replicated | graphiti | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 16 | 30 | 284.57 | 17.27 |
| qwen | replicated | graphiti | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 1 | 16 | 30 | 284.13 | 17.43 |
| qwen | replicated | graphiti | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 1 | 16 | 30 | 284.80 | 17.43 |
| qwen | replicated | graphiti | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 1 | 16 | 30 | 284.83 | 17.30 |
| qwen | replicated | graphiti | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 6 | 10 | 288.30 | 17.70 |
| qwen | replicated | graphiti | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 1 | 10 | 20 | 283.10 | 17.20 |
| qwen | replicated | inhouse | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 264.77 | 11.70 |
| qwen | replicated | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 255.53 | 12.03 |
| qwen | replicated | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 0 | 26 | 30 | 262.10 | 11.87 |
| qwen | replicated | inhouse | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 256.27 | 11.63 |
| qwen | replicated | inhouse | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 253.93 | 11.73 |
| qwen | replicated | inhouse | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 10 | 10 | 260.30 | 11.90 |
| qwen | replicated | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 16 | 20 | 267.00 | 11.60 |
| qwen | replicated | mem0 | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 30 | 30 | 279.53 | 11.67 |
| qwen | replicated | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 30 | 30 | 286.13 | 11.47 |
| qwen | replicated | mem0 | h0 | recall | 28 | 30 | 0.93 | 0.79 | 0.98 |  |  |  |  |  | 0 | 0 | 30 | 30 | 279.13 | 12.00 |
| qwen | replicated | mem0 | h0 | recency | 21 | 30 | 0.70 | 0.52 | 0.83 | 1.00 | 9 | 9 |  |  | 0 | 0 | 30 | 30 | 282.10 | 11.87 |
| qwen | replicated | mem0 | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 30 | 30 | 281.23 | 12.10 |
| qwen | replicated | mem0 | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 10 | 10 | 278.40 | 11.80 |
| qwen | replicated | mem0 | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 20 | 20 | 280.10 | 11.60 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 180 | 0 | 108 | 288.00 | 300 | 284.94 | 17.47 |
| qwen | kernel | inhouse | h0 | 180 | 0 | 156 | 286.50 | 300 | 264.08 | 11.59 |
| qwen | kernel | mem0 | h0 | 180 | 0 | 180 | 288.00 | 300 | 284.89 | 11.83 |
| qwen | native | graphiti | h0 | 180 | 180 |  | 159.00 | 209 | 160.25 | 9.26 |
| qwen | replicated | graphiti | h0 | 180 | 6 | 96 | 291.00 | 300 | 284.58 | 17.32 |
| qwen | replicated | inhouse | h0 | 180 | 0 | 156 | 286.50 | 300 | 264.08 | 11.59 |
| qwen | replicated | mem0 | h0 | 180 | 0 | 180 | 288.00 | 300 | 283.24 | 11.64 |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar | kernel_block_tokens | kernel_block_rows | replicated_block_tokens | replicated_block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | mem0 | deletion | 30 | 0 | 0 | 1.00 | 283.43 | 11.83 | 279.53 | 11.67 |
| qwen | mem0 | privacy | 30 | 0 | 0 | 1.00 | 286.73 | 11.73 | 286.13 | 11.47 |
| qwen | mem0 | recall | 30 | 0 | 0 | 1.00 | 279.50 | 12.20 | 279.13 | 12.00 |
| qwen | mem0 | recency | 30 | 4 | 2 | 0.69 | 284.07 | 11.83 | 282.10 | 11.87 |
| qwen | mem0 | contradiction | 30 | 0 | 0 | 1.00 | 285.83 | 12.50 | 281.23 | 12.10 |
| qwen | inhouse | deletion | 30 | 0 | 0 | 1.00 | 264.77 | 11.70 | 264.77 | 11.70 |
| qwen | inhouse | privacy | 30 | 0 | 0 | 1.00 | 255.53 | 12.03 | 255.53 | 12.03 |
| qwen | inhouse | recall | 30 | 0 | 0 | 1.00 | 262.10 | 11.87 | 262.10 | 11.87 |
| qwen | inhouse | recency | 30 | 0 | 0 | 1.00 | 256.27 | 11.63 | 256.27 | 11.63 |
| qwen | inhouse | contradiction | 30 | 0 | 0 | 1.00 | 253.93 | 11.73 | 253.93 | 11.73 |
| qwen | inhouse | identical blocks | 180 | 180 |  |  | 264.08 | 11.59 | 264.08 | 11.59 |
| qwen | graphiti | deletion | 30 | 0 | 0 | 1.00 | 284.90 | 17.47 | 284.83 | 17.37 |
| qwen | graphiti | privacy | 30 | 0 | 0 | 1.00 | 284.20 | 17.43 | 284.57 | 17.27 |
| qwen | graphiti | recall | 30 | 0 | 0 | 1.00 | 285.60 | 17.57 | 284.13 | 17.43 |
| qwen | graphiti | recency | 30 | 0 | 1 | 1.00 | 285.03 | 17.60 | 284.80 | 17.43 |
| qwen | graphiti | contradiction | 30 | 0 | 0 | 1.00 | 284.93 | 17.47 | 284.83 | 17.30 |

## Integration (judge v2)

The mean with its 95% t-interval (none for n < 2).

| model | locus | backend | condition | n | mean | ci_low | ci_high | sd | share_ge_4 | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 2.50 | 2.15 | 2.85 | 0.94 | 0.23 | 284.97 | 17.30 |
| qwen | kernel | inhouse | h0 | 30 | 2.57 | 2.23 | 2.90 | 0.90 | 0.23 | 291.87 | 10.57 |
| qwen | kernel | mem0 | h0 | 30 | 3.40 | 3.07 | 3.73 | 0.89 | 0.63 | 289.77 | 10.87 |
| qwen | native | graphiti | h0 | 30 | 2.07 | 1.77 | 2.36 | 0.78 | 0.10 | 164.13 | 9.30 |
| qwen | replicated | graphiti | h0 | 30 | 2.17 | 1.91 | 2.43 | 0.70 | 0.07 | 284.33 | 17.13 |
| qwen | replicated | inhouse | h0 | 30 | 2.60 | 2.27 | 2.93 | 0.89 | 0.23 | 291.87 | 10.57 |
| qwen | replicated | mem0 | h0 | 30 | 3.57 | 3.26 | 3.87 | 0.82 | 0.77 | 291.33 | 10.73 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`, or an `entity`: a Graphiti scrub deleted it with an entity a form names, or `derived`: an A-MEM scrub deleted it because its derived text carried a form; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the history scrub (Mem0: `messages` deleted, `history` records cleared; A-MEM: `history` counts the carrier notes it deleted, as `derived` does), and rows later writes `swept` and writes `suppressed`.

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | entity | derived | other_agents | same_writer | no_values | messages | history | swept | suppressed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 0 | 0 | 10 | 0 | 0 | 40 | 66 | 0 | 0 | 284.94 | 17.47 |
| qwen | kernel | inhouse | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 264.08 | 11.59 |
| qwen | kernel | mem0 | h0 | 30 | 30 | 43 | 30 | 13 | 0 | 0 | 0 | 10 | 3 | 0 | 40 | 86 | 0 | 0 | 284.89 | 11.83 |
| qwen | replicated | graphiti | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 0 | 0 | 10 | 0 | 0 | 40 | 66 | 0 | 0 | 284.58 | 17.32 |
| qwen | replicated | inhouse | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 264.08 | 11.59 |
| qwen | replicated | mem0 | h0 | 30 | 30 | 43 | 30 | 13 | 0 | 0 | 0 | 10 | 3 | 0 | 40 | 86 | 0 | 0 | 283.24 | 11.64 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 284.94 | 17.47 |
| qwen | kernel | inhouse | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 264.08 | 11.59 |
| qwen | kernel | mem0 | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 284.89 | 11.83 |
| qwen | native | graphiti | h0 | 0 | 60 | 0 | 180 | 27 | 0 | 160.25 | 9.26 |
| qwen | replicated | graphiti | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 284.58 | 17.32 |
| qwen | replicated | inhouse | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 264.08 | 11.59 |
| qwen | replicated | mem0 | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 283.24 | 11.64 |

## Graphiti's own invalidations (Subtask 16)

Graphiti marks a fact invalid when it judges a later one contradicts it: its own supersession, kept apart from the kernel's above and credited to no locus. `invalidated_rows`: rows after the history it marked invalid; probes whose block held one.

| model | locus | backend | condition | invalidated_rows | probes | invalidated_in_block | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 50 | 180 | 0 | 284.94 | 17.47 |
| qwen | native | graphiti | h0 | 54 | 180 | 0 | 160.25 | 9.26 |
| qwen | replicated | graphiti | h0 | 52 | 180 | 7 | 284.58 | 17.32 |

## Graphiti writes that stored no fact (Amendment 5)

Graphiti sometimes extracts a write's entities but no fact, and its search returns facts only: a write Graphiti stored no fact from is a lost memory, not a failed trial (and an A-MEM write that stored no note, Amendment 8). `trials`: scored trials; `with_one`: scored trials with such a write; `writes_without_fact`: those writes; `probes_on_them`: probes whose target was one, and `passed_on_them`.

| model | locus | backend | condition | trials | with_one | writes_without_fact | probes_on_them | passed_on_them | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 0 | 0 | 0 | 0 | 284.94 | 17.47 |
| qwen | native | graphiti | h0 | 30 | 0 | 0 | 0 | 0 | 160.25 | 9.26 |
| qwen | replicated | graphiti | h0 | 30 | 0 | 0 | 0 | 0 | 284.58 | 17.32 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | deletion | 30 | 30 | 0 | 0 | 284.90 | 17.47 |
| qwen | kernel | graphiti | h0 | privacy | 30 | 30 | 0 | 0 | 284.20 | 17.43 |
| qwen | kernel | inhouse | h0 | deletion | 30 | 30 | 0 | 0 | 264.77 | 11.70 |
| qwen | kernel | inhouse | h0 | privacy | 30 | 30 | 0 | 0 | 255.53 | 12.03 |
| qwen | kernel | mem0 | h0 | deletion | 30 | 30 | 0 | 0 | 283.43 | 11.83 |
| qwen | kernel | mem0 | h0 | privacy | 30 | 30 | 0 | 0 | 286.73 | 11.73 |
| qwen | native | graphiti | h0 | deletion | 30 | 23 | 10 | 3 | 159.90 | 9.20 |
| qwen | native | graphiti | h0 | privacy | 30 | 30 | 0 | 0 | 158.73 | 9.00 |
| qwen | replicated | graphiti | h0 | deletion | 30 | 30 | 0 | 0 | 284.83 | 17.37 |
| qwen | replicated | graphiti | h0 | privacy | 30 | 30 | 0 | 0 | 284.57 | 17.27 |
| qwen | replicated | inhouse | h0 | deletion | 30 | 30 | 0 | 0 | 264.77 | 11.70 |
| qwen | replicated | inhouse | h0 | privacy | 30 | 30 | 0 | 0 | 255.53 | 12.03 |
| qwen | replicated | mem0 | h0 | deletion | 30 | 30 | 0 | 0 | 279.53 | 11.67 |
| qwen | replicated | mem0 | h0 | privacy | 30 | 30 | 0 | 0 | 286.13 | 11.47 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|
| qwen | native | graphiti | h0 | echo | 7 | 160.25 | 9.26 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | none | 0 | 30 | 284.94 | 17.47 |
| qwen | kernel | inhouse | h0 | none | 0 | 30 | 264.08 | 11.59 |
| qwen | kernel | mem0 | h0 | none | 0 | 30 | 284.89 | 11.83 |
| qwen | native | graphiti | h0 | echo | 7 | 3 | 160.25 | 9.26 |
| qwen | native | graphiti | h0 | none | 0 | 20 | 160.25 | 9.26 |
| qwen | replicated | graphiti | h0 | none | 0 | 30 | 284.58 | 17.32 |
| qwen | replicated | inhouse | h0 | none | 0 | 30 | 264.08 | 11.59 |
| qwen | replicated | mem0 | h0 | none | 0 | 30 | 283.24 | 11.64 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | recency | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 285.03 | 17.60 |
| qwen | kernel | mem0 | h0 | recall | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 279.50 | 12.20 |
| qwen | kernel | mem0 | h0 | recency | 7 | 7 | 0 | 0 | 0 | 0 | 7 | 284.07 | 11.83 |
| qwen | native | graphiti | h0 | contradiction | 4 | 0 | 0 | 0 | 0 | 0 | 4 | 159.53 | 9.13 |
| qwen | replicated | mem0 | h0 | recall | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 279.13 | 12.00 |
| qwen | replicated | mem0 | h0 | recency | 9 | 9 | 0 | 0 | 0 | 0 | 9 | 282.10 | 11.87 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | client | 4 | 4 | 4 | 284.94 | 17.47 |
| qwen | kernel | graphiti | h0 | conference | 3 | 3 | 3 | 284.94 | 17.47 |
| qwen | kernel | graphiti | h0 | home_city | 6 | 6 | 6 | 284.94 | 17.47 |
| qwen | kernel | graphiti | h0 | manager | 4 | 4 | 4 | 284.94 | 17.47 |
| qwen | kernel | graphiti | h0 | offsite_city | 4 | 4 | 4 | 284.94 | 17.47 |
| qwen | kernel | graphiti | h0 | one_on_one | 3 | 3 | 3 | 284.94 | 17.47 |
| qwen | kernel | graphiti | h0 | teammate | 6 | 6 | 6 | 284.94 | 17.47 |
| qwen | kernel | inhouse | h0 | client | 4 | 4 | 4 | 264.08 | 11.59 |
| qwen | kernel | inhouse | h0 | conference | 3 | 3 | 3 | 264.08 | 11.59 |
| qwen | kernel | inhouse | h0 | home_city | 6 | 6 | 6 | 264.08 | 11.59 |
| qwen | kernel | inhouse | h0 | manager | 4 | 4 | 4 | 264.08 | 11.59 |
| qwen | kernel | inhouse | h0 | offsite_city | 4 | 4 | 4 | 264.08 | 11.59 |
| qwen | kernel | inhouse | h0 | one_on_one | 3 | 3 | 3 | 264.08 | 11.59 |
| qwen | kernel | inhouse | h0 | teammate | 6 | 6 | 6 | 264.08 | 11.59 |
| qwen | kernel | mem0 | h0 | client | 4 | 4 | 4 | 284.89 | 11.83 |
| qwen | kernel | mem0 | h0 | conference | 3 | 3 | 3 | 284.89 | 11.83 |
| qwen | kernel | mem0 | h0 | home_city | 6 | 6 | 6 | 284.89 | 11.83 |
| qwen | kernel | mem0 | h0 | manager | 4 | 4 | 4 | 284.89 | 11.83 |
| qwen | kernel | mem0 | h0 | offsite_city | 4 | 4 | 4 | 284.89 | 11.83 |
| qwen | kernel | mem0 | h0 | one_on_one | 3 | 3 | 3 | 284.89 | 11.83 |
| qwen | kernel | mem0 | h0 | teammate | 6 | 6 | 6 | 284.89 | 11.83 |
| qwen | native | graphiti | h0 | client | 4 | 3 | 3 | 160.25 | 9.26 |
| qwen | native | graphiti | h0 | conference | 3 | 2 | 2 | 160.25 | 9.26 |
| qwen | native | graphiti | h0 | home_city | 6 | 6 | 6 | 160.25 | 9.26 |
| qwen | native | graphiti | h0 | manager | 4 | 4 | 4 | 160.25 | 9.26 |
| qwen | native | graphiti | h0 | offsite_city | 4 | 4 | 4 | 160.25 | 9.26 |
| qwen | native | graphiti | h0 | one_on_one | 3 | 2 | 2 | 160.25 | 9.26 |
| qwen | native | graphiti | h0 | teammate | 6 | 5 | 5 | 160.25 | 9.26 |
| qwen | replicated | graphiti | h0 | client | 4 | 4 | 4 | 284.58 | 17.32 |
| qwen | replicated | graphiti | h0 | conference | 3 | 3 | 3 | 284.58 | 17.32 |
| qwen | replicated | graphiti | h0 | home_city | 6 | 6 | 6 | 284.58 | 17.32 |
| qwen | replicated | graphiti | h0 | manager | 4 | 4 | 4 | 284.58 | 17.32 |
| qwen | replicated | graphiti | h0 | offsite_city | 4 | 4 | 4 | 284.58 | 17.32 |
| qwen | replicated | graphiti | h0 | one_on_one | 3 | 3 | 3 | 284.58 | 17.32 |
| qwen | replicated | graphiti | h0 | teammate | 6 | 6 | 6 | 284.58 | 17.32 |
| qwen | replicated | inhouse | h0 | client | 4 | 4 | 4 | 264.08 | 11.59 |
| qwen | replicated | inhouse | h0 | conference | 3 | 3 | 3 | 264.08 | 11.59 |
| qwen | replicated | inhouse | h0 | home_city | 6 | 6 | 6 | 264.08 | 11.59 |
| qwen | replicated | inhouse | h0 | manager | 4 | 4 | 4 | 264.08 | 11.59 |
| qwen | replicated | inhouse | h0 | offsite_city | 4 | 4 | 4 | 264.08 | 11.59 |
| qwen | replicated | inhouse | h0 | one_on_one | 3 | 3 | 3 | 264.08 | 11.59 |
| qwen | replicated | inhouse | h0 | teammate | 6 | 6 | 6 | 264.08 | 11.59 |
| qwen | replicated | mem0 | h0 | client | 4 | 4 | 4 | 283.24 | 11.64 |
| qwen | replicated | mem0 | h0 | conference | 3 | 3 | 3 | 283.24 | 11.64 |
| qwen | replicated | mem0 | h0 | home_city | 6 | 6 | 6 | 283.24 | 11.64 |
| qwen | replicated | mem0 | h0 | manager | 4 | 4 | 4 | 283.24 | 11.64 |
| qwen | replicated | mem0 | h0 | offsite_city | 4 | 4 | 4 | 283.24 | 11.64 |
| qwen | replicated | mem0 | h0 | one_on_one | 3 | 3 | 3 | 283.24 | 11.64 |
| qwen | replicated | mem0 | h0 | teammate | 6 | 6 | 6 | 283.24 | 11.64 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | recency | 0 | 0 | 30 | 29 | 285.03 | 17.60 |
| qwen | kernel | graphiti | h0 | contradiction | 0 | 0 | 30 | 30 | 284.93 | 17.47 |
| qwen | kernel | inhouse | h0 | recency | 0 | 0 | 30 | 30 | 256.27 | 11.63 |
| qwen | kernel | inhouse | h0 | contradiction | 0 | 0 | 30 | 30 | 253.93 | 11.73 |
| qwen | kernel | mem0 | h0 | recency | 0 | 0 | 30 | 23 | 284.07 | 11.83 |
| qwen | kernel | mem0 | h0 | contradiction | 0 | 0 | 30 | 30 | 285.83 | 12.50 |
| qwen | native | graphiti | h0 | recency | 0 | 0 | 30 | 30 | 158.73 | 9.43 |
| qwen | native | graphiti | h0 | contradiction | 0 | 0 | 30 | 26 | 159.53 | 9.13 |
| qwen | replicated | graphiti | h0 | recency | 0 | 0 | 30 | 30 | 284.80 | 17.43 |
| qwen | replicated | graphiti | h0 | contradiction | 0 | 0 | 30 | 30 | 284.83 | 17.30 |
| qwen | replicated | inhouse | h0 | recency | 0 | 0 | 30 | 30 | 256.27 | 11.63 |
| qwen | replicated | inhouse | h0 | contradiction | 0 | 0 | 30 | 30 | 253.93 | 11.73 |
| qwen | replicated | mem0 | h0 | recency | 0 | 0 | 30 | 21 | 282.10 | 11.87 |
| qwen | replicated | mem0 | h0 | contradiction | 0 | 0 | 30 | 30 | 281.23 | 12.10 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 17.30 | 0.00 | 17.30 | 18 | 30 | 29 | 29 | 2.50 |  | 284.97 | 17.30 |
| qwen | kernel | inhouse | h0 | 30 | 10.57 | 0.00 | 10.57 | 26 | 30 | 30 | 30 | 2.57 |  | 291.87 | 10.57 |
| qwen | kernel | mem0 | h0 | 30 | 10.87 | 0.00 | 10.87 | 30 | 30 | 30 | 30 | 3.40 |  | 289.77 | 10.87 |
| qwen | native | graphiti | h0 | 30 | 9.30 | 0.00 | 9.30 |  | 30 | 19 | 19 | 2.07 |  | 164.13 | 9.30 |
| qwen | replicated | graphiti | h0 | 30 | 17.13 | 0.00 | 17.13 | 16 | 30 | 29 | 29 | 2.17 |  | 284.33 | 17.13 |
| qwen | replicated | inhouse | h0 | 30 | 10.57 | 0.00 | 10.57 | 26 | 30 | 30 | 30 | 2.60 |  | 291.87 | 10.57 |
| qwen | replicated | mem0 | h0 | 30 | 10.73 | 0.00 | 10.73 | 30 | 30 | 29 | 29 | 3.57 |  | 291.33 | 10.73 |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 1 | 1 | 2.00 | 284.97 | 17.30 |
| qwen | kernel | graphiti | h0 | 2 | 29 | 2.52 | 284.97 | 17.30 |
| qwen | kernel | inhouse | h0 | 2 | 30 | 2.57 | 291.87 | 10.57 |
| qwen | kernel | mem0 | h0 | 2 | 30 | 3.40 | 289.77 | 10.87 |
| qwen | native | graphiti | h0 | 1 | 11 | 1.91 | 164.13 | 9.30 |
| qwen | native | graphiti | h0 | 2 | 19 | 2.16 | 164.13 | 9.30 |
| qwen | replicated | graphiti | h0 | 1 | 1 | 2.00 | 284.33 | 17.13 |
| qwen | replicated | graphiti | h0 | 2 | 29 | 2.17 | 284.33 | 17.13 |
| qwen | replicated | inhouse | h0 | 2 | 30 | 2.60 | 291.87 | 10.57 |
| qwen | replicated | mem0 | h0 | 1 | 1 | 2.00 | 291.33 | 10.73 |
| qwen | replicated | mem0 | h0 | 2 | 29 | 3.62 | 291.33 | 10.73 |

