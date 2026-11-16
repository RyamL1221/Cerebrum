# Benchmark v2 analysis

3 cells, 90 user-trials, 0 failed.

Every table but the criteria ends with `block_tokens` and `block_rows`: the mean block, in tokens and in rows, of a set of the row's cell's probes. In the pass matrix, the row's own probes (a deletion row split by echo, its split's); in the kernel-against-replicated table, the row's probe type, per locus (all probes for `identical blocks`); in the integration table and the integration readings, the cell's integration probes; elsewhere, the row's probe type where the row names one, else all of the cell's probes. A reading's row that splits a cell's probes further (a slot, a carrier, a count of base rows) shows its set's mean, not its own.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 264.53 | 11.60 |
| qwen | kernel | amem | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 255.83 | 11.90 |
| qwen | kernel | amem | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 0 | 26 | 30 | 250.60 | 11.70 |
| qwen | kernel | amem | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 266.60 | 11.63 |
| qwen | kernel | amem | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 245.43 | 11.57 |
| qwen | kernel | amem | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 10 | 10 | 262.80 | 12.10 |
| qwen | kernel | amem | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 16 | 20 | 265.40 | 11.35 |
| qwen | native | amem | h0 | deletion | 20 | 30 | 0.67 | 0.49 | 0.81 |  |  |  | 10 | 8 | 0 | 30 |  | 30 | 194.97 | 9.23 |
| qwen | native | amem | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 |  | 30 | 183.40 | 9.00 |
| qwen | native | amem | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 |  | 30 | 188.03 | 9.50 |
| qwen | native | amem | h0 | recency | 17 | 30 | 0.57 | 0.39 | 0.73 | 0.93 | 11 | 9 |  |  | 0 | 30 |  | 30 | 202.97 | 9.40 |
| qwen | native | amem | h0 | contradiction | 17 | 30 | 0.57 | 0.39 | 0.73 | 0.67 | 3 | 0 |  |  | 0 | 30 |  | 30 | 186.27 | 9.17 |
| qwen | native | amem | h0 | deletion (echo) | 0 | 10 | 0.00 | 0.00 | 0.28 |  |  |  | 10 | 8 | 0 | 10 |  | 10 | 187.40 | 9.20 |
| qwen | native | amem | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 |  | 20 | 198.75 | 9.25 |
| qwen | replicated | amem | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 259.20 | 11.50 |
| qwen | replicated | amem | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 26 | 30 | 262.57 | 12.00 |
| qwen | replicated | amem | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 0 | 26 | 30 | 253.13 | 11.67 |
| qwen | replicated | amem | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 260.93 | 11.50 |
| qwen | replicated | amem | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 0 | 26 | 30 | 250.00 | 11.53 |
| qwen | replicated | amem | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 10 | 10 | 249.80 | 11.90 |
| qwen | replicated | amem | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 16 | 20 | 263.90 | 11.30 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 180 | 0 | 156 | 287.00 | 300 | 261.49 | 11.52 |
| qwen | native | amem | h0 | 180 | 180 |  | 179.50 | 314 | 202.86 | 9.28 |
| qwen | replicated | amem | h0 | 180 | 0 | 156 | 283.00 | 300 | 262.07 | 11.50 |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar | kernel_block_tokens | kernel_block_rows | replicated_block_tokens | replicated_block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | amem | deletion | 30 | 0 | 0 | 1.00 | 264.53 | 11.60 | 259.20 | 11.50 |
| qwen | amem | privacy | 30 | 0 | 0 | 1.00 | 255.83 | 11.90 | 262.57 | 12.00 |
| qwen | amem | recall | 30 | 0 | 0 | 1.00 | 250.60 | 11.70 | 253.13 | 11.67 |
| qwen | amem | recency | 30 | 0 | 0 | 1.00 | 266.60 | 11.63 | 260.93 | 11.50 |
| qwen | amem | contradiction | 30 | 0 | 0 | 1.00 | 245.43 | 11.57 | 250.00 | 11.53 |

## Integration (judge v2)

The mean with its 95% t-interval (none for n < 2).

| model | locus | backend | condition | n | mean | ci_low | ci_high | sd | share_ge_4 | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 30 | 2.57 | 2.20 | 2.93 | 0.97 | 0.27 | 285.97 | 10.73 |
| qwen | native | amem | h0 | 30 | 2.73 | 2.32 | 3.15 | 1.11 | 0.40 | 261.53 | 9.40 |
| qwen | replicated | amem | h0 | 30 | 2.63 | 2.22 | 3.04 | 1.10 | 0.30 | 286.57 | 10.80 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`, or an `entity`: a Graphiti scrub deleted it with an entity a form names, or `derived`: an A-MEM scrub deleted it because its derived text carried a form; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the history scrub (Mem0: `messages` deleted, `history` records cleared; A-MEM: `history` counts the carrier notes it deleted, as `derived` does), and rows later writes `swept` and writes `suppressed`.

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | entity | derived | other_agents | same_writer | no_values | messages | history | swept | suppressed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 30 | 30 | 41 | 30 | 10 | 0 | 0 | 1 | 11 | 0 | 0 | 0 | 1 | 0 | 0 | 261.49 | 11.52 |
| qwen | replicated | amem | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 262.07 | 11.50 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 261.49 | 11.52 |
| qwen | native | amem | h0 | 0 | 60 | 0 | 180 | 170 | 0 | 202.86 | 9.28 |
| qwen | replicated | amem | h0 | 60 | 60 | 60 | 180 | 0 | 360 | 262.07 | 11.50 |

## Graphiti writes that stored no fact (Amendment 5)

Graphiti sometimes extracts a write's entities but no fact, and its search returns facts only: a write Graphiti stored no fact from is a lost memory, not a failed trial (and an A-MEM write that stored no note, Amendment 8). `trials`: scored trials; `with_one`: scored trials with such a write; `writes_without_fact`: those writes; `probes_on_them`: probes whose target was one, and `passed_on_them`.

| model | locus | backend | condition | trials | with_one | writes_without_fact | probes_on_them | passed_on_them | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 30 | 0 | 0 | 0 | 0 | 261.49 | 11.52 |
| qwen | native | amem | h0 | 30 | 0 | 0 | 0 | 0 | 202.86 | 9.28 |
| qwen | replicated | amem | h0 | 30 | 0 | 0 | 0 | 0 | 262.07 | 11.50 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | deletion | 30 | 30 | 0 | 0 | 264.53 | 11.60 |
| qwen | kernel | amem | h0 | privacy | 30 | 30 | 0 | 0 | 255.83 | 11.90 |
| qwen | native | amem | h0 | deletion | 30 | 20 | 10 | 0 | 194.97 | 9.23 |
| qwen | native | amem | h0 | privacy | 30 | 30 | 0 | 0 | 183.40 | 9.00 |
| qwen | replicated | amem | h0 | deletion | 30 | 30 | 0 | 0 | 259.20 | 11.50 |
| qwen | replicated | amem | h0 | privacy | 30 | 30 | 0 | 0 | 262.57 | 12.00 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|
| qwen | native | amem | h0 | echo | 10 | 202.86 | 9.28 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | none | 0 | 30 | 261.49 | 11.52 |
| qwen | native | amem | h0 | echo | 10 | 0 | 202.86 | 9.28 |
| qwen | native | amem | h0 | none | 0 | 20 | 202.86 | 9.28 |
| qwen | replicated | amem | h0 | none | 0 | 30 | 262.07 | 11.50 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | native | amem | h0 | recency | 13 | 11 | 0 | 0 | 0 | 0 | 13 | 202.97 | 9.40 |
| qwen | native | amem | h0 | contradiction | 13 | 3 | 0 | 0 | 0 | 0 | 13 | 186.27 | 9.17 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | client | 4 | 4 | 4 | 261.49 | 11.52 |
| qwen | kernel | amem | h0 | conference | 3 | 3 | 3 | 261.49 | 11.52 |
| qwen | kernel | amem | h0 | home_city | 6 | 6 | 6 | 261.49 | 11.52 |
| qwen | kernel | amem | h0 | manager | 4 | 4 | 4 | 261.49 | 11.52 |
| qwen | kernel | amem | h0 | offsite_city | 4 | 4 | 4 | 261.49 | 11.52 |
| qwen | kernel | amem | h0 | one_on_one | 3 | 3 | 3 | 261.49 | 11.52 |
| qwen | kernel | amem | h0 | teammate | 6 | 6 | 6 | 261.49 | 11.52 |
| qwen | native | amem | h0 | client | 4 | 2 | 2 | 202.86 | 9.28 |
| qwen | native | amem | h0 | conference | 3 | 0 | 1 | 202.86 | 9.28 |
| qwen | native | amem | h0 | home_city | 6 | 3 | 4 | 202.86 | 9.28 |
| qwen | native | amem | h0 | manager | 4 | 2 | 2 | 202.86 | 9.28 |
| qwen | native | amem | h0 | offsite_city | 4 | 3 | 4 | 202.86 | 9.28 |
| qwen | native | amem | h0 | one_on_one | 3 | 2 | 2 | 202.86 | 9.28 |
| qwen | native | amem | h0 | teammate | 6 | 5 | 5 | 202.86 | 9.28 |
| qwen | replicated | amem | h0 | client | 4 | 4 | 4 | 262.07 | 11.50 |
| qwen | replicated | amem | h0 | conference | 3 | 3 | 3 | 262.07 | 11.50 |
| qwen | replicated | amem | h0 | home_city | 6 | 6 | 6 | 262.07 | 11.50 |
| qwen | replicated | amem | h0 | manager | 4 | 4 | 4 | 262.07 | 11.50 |
| qwen | replicated | amem | h0 | offsite_city | 4 | 4 | 4 | 262.07 | 11.50 |
| qwen | replicated | amem | h0 | one_on_one | 3 | 3 | 3 | 262.07 | 11.50 |
| qwen | replicated | amem | h0 | teammate | 6 | 6 | 6 | 262.07 | 11.50 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | recency | 0 | 0 | 30 | 30 | 266.60 | 11.63 |
| qwen | kernel | amem | h0 | contradiction | 0 | 0 | 30 | 30 | 245.43 | 11.57 |
| qwen | native | amem | h0 | recency | 0 | 0 | 30 | 17 | 202.97 | 9.40 |
| qwen | native | amem | h0 | contradiction | 0 | 0 | 30 | 17 | 186.27 | 9.17 |
| qwen | replicated | amem | h0 | recency | 0 | 0 | 30 | 30 | 260.93 | 11.50 |
| qwen | replicated | amem | h0 | contradiction | 0 | 0 | 30 | 30 | 250.00 | 11.53 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 30 | 10.73 | 0.00 | 10.73 | 26 | 28 | 29 | 27 | 2.64 | 1.50 | 285.97 | 10.73 |
| qwen | native | amem | h0 | 30 | 9.40 | 0.00 | 9.40 |  | 27 | 24 | 22 | 2.89 | 1.33 | 261.53 | 9.40 |
| qwen | replicated | amem | h0 | 30 | 10.80 | 0.00 | 10.80 | 26 | 28 | 29 | 27 | 2.71 | 1.50 | 286.57 | 10.80 |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | amem | h0 | 1 | 3 | 1.67 | 285.97 | 10.73 |
| qwen | kernel | amem | h0 | 2 | 27 | 2.67 | 285.97 | 10.73 |
| qwen | native | amem | h0 | 0 | 1 | 1.00 | 261.53 | 9.40 |
| qwen | native | amem | h0 | 1 | 7 | 1.86 | 261.53 | 9.40 |
| qwen | native | amem | h0 | 2 | 22 | 3.09 | 261.53 | 9.40 |
| qwen | replicated | amem | h0 | 1 | 3 | 1.67 | 286.57 | 10.80 |
| qwen | replicated | amem | h0 | 2 | 27 | 2.74 | 286.57 | 10.80 |

