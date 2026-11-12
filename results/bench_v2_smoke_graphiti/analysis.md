# Benchmark v2 analysis

3 cells, 90 user-trials, 0 failed.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | kernel | graphiti | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | kernel | graphiti | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | graphiti | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | graphiti | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | graphiti | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 10 | 0 | 10 |
| qwen | kernel | graphiti | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 | 0 | 20 |
| qwen | native | graphiti | h0 | deletion | 23 | 30 | 0.77 | 0.59 | 0.88 |  |  |  | 7 | 7 | 0 | 30 |  | 30 |
| qwen | native | graphiti | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 |  | 30 |
| qwen | native | graphiti | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 |  | 30 |
| qwen | native | graphiti | h0 | recency | 11 | 30 | 0.37 | 0.22 | 0.54 | 0.83 | 14 | 6 |  |  | 0 | 30 |  | 30 |
| qwen | native | graphiti | h0 | contradiction | 13 | 30 | 0.43 | 0.27 | 0.61 | 0.57 | 4 | 1 |  |  | 0 | 30 |  | 30 |
| qwen | native | graphiti | h0 | deletion (echo) | 3 | 10 | 0.30 | 0.11 | 0.60 |  |  |  | 7 | 7 | 0 | 10 |  | 10 |
| qwen | native | graphiti | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 |  | 20 |
| qwen | replicated | graphiti | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | replicated | graphiti | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | replicated | graphiti | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 | 0 | 30 |
| qwen | replicated | graphiti | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 30 | 0 | 30 |
| qwen | replicated | graphiti | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 30 | 0 | 30 |
| qwen | replicated | graphiti | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 10 | 0 | 10 |
| qwen | replicated | graphiti | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 | 0 | 20 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 180 | 180 | 0 | 169.00 | 195 |
| qwen | native | graphiti | h0 | 180 | 180 |  | 161.00 | 192 |
| qwen | replicated | graphiti | h0 | 180 | 180 | 0 | 169.00 | 197 |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar |
|---|---|---|---|---|---|---|
| qwen | graphiti | deletion | 30 | 0 | 0 | 1.00 |
| qwen | graphiti | privacy | 30 | 0 | 0 | 1.00 |
| qwen | graphiti | recall | 30 | 0 | 0 | 1.00 |
| qwen | graphiti | recency | 30 | 0 | 0 | 1.00 |
| qwen | graphiti | contradiction | 30 | 0 | 0 | 1.00 |

## Integration (judge v2)

The mean with its 95% t-interval (none for n < 2).

| model | locus | backend | condition | n | mean | ci_low | ci_high | sd | share_ge_4 |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 2.20 | 1.99 | 2.41 | 0.55 | 0.03 |
| qwen | native | graphiti | h0 | 30 | 2.00 | 1.74 | 2.26 | 0.69 | 0.03 |
| qwen | replicated | graphiti | h0 | 30 | 1.97 | 1.74 | 2.20 | 0.61 | 0.03 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`, or an `entity`: a Graphiti scrub deleted it with an entity a form names; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the Mem0 history scrub (`messages` deleted, `history` records cleared), and rows later writes `swept` and writes `suppressed`.

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | entity | other_agents | same_writer | no_values | messages | history | swept | suppressed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 0 | 10 | 0 | 0 | 40 | 63 | 0 | 0 |
| qwen | replicated | graphiti | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 0 | 10 | 0 | 0 | 40 | 67 | 0 | 0 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 60 | 60 | 60 | 180 | 0 | 360 |
| qwen | native | graphiti | h0 | 0 | 60 | 0 | 180 | 149 | 0 |
| qwen | replicated | graphiti | h0 | 60 | 60 | 60 | 180 | 0 | 360 |

## Graphiti's own invalidations (Subtask 16)

Graphiti marks a fact invalid when it judges a later one contradicts it: its own supersession, kept apart from the kernel's above and credited to no locus. `invalidated_rows`: rows after the history it marked invalid; probes whose block held one.

| model | locus | backend | condition | invalidated_rows | probes | invalidated_in_block |
|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 53 | 180 | 0 |
| qwen | native | graphiti | h0 | 56 | 180 | 132 |
| qwen | replicated | graphiti | h0 | 56 | 180 | 5 |

## Graphiti writes that stored no fact (Amendment 5)

Graphiti sometimes extracts a write's entities but no fact, and its search returns facts only: a write Graphiti stored no fact from is a lost memory, not a failed trial. `trials`: scored trials; `with_one`: scored trials with such a write; `writes_without_fact`: those writes; `probes_on_them`: probes whose target was one, and `passed_on_them`.

| model | locus | backend | condition | trials | with_one | writes_without_fact | probes_on_them | passed_on_them |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 0 | 0 | 0 | 0 |
| qwen | native | graphiti | h0 | 30 | 0 | 0 | 0 | 0 |
| qwen | replicated | graphiti | h0 | 30 | 0 | 0 | 0 | 0 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | deletion | 30 | 30 | 0 | 0 |
| qwen | kernel | graphiti | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | native | graphiti | h0 | deletion | 30 | 23 | 10 | 3 |
| qwen | native | graphiti | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | replicated | graphiti | h0 | deletion | 30 | 30 | 0 | 0 |
| qwen | replicated | graphiti | h0 | privacy | 30 | 30 | 0 | 0 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures |
|---|---|---|---|---|---|
| qwen | native | graphiti | h0 | echo | 7 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes |
|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | none | 0 | 30 |
| qwen | native | graphiti | h0 | echo | 7 | 3 |
| qwen | native | graphiti | h0 | none | 0 | 20 |
| qwen | replicated | graphiti | h0 | none | 0 | 30 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | native | graphiti | h0 | recency | 19 | 14 | 0 | 0 | 0 | 0 | 19 |
| qwen | native | graphiti | h0 | contradiction | 17 | 4 | 0 | 0 | 0 | 0 | 17 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient |
|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | client | 4 | 4 | 4 |
| qwen | kernel | graphiti | h0 | conference | 3 | 3 | 3 |
| qwen | kernel | graphiti | h0 | home_city | 6 | 6 | 6 |
| qwen | kernel | graphiti | h0 | manager | 4 | 4 | 4 |
| qwen | kernel | graphiti | h0 | offsite_city | 4 | 4 | 4 |
| qwen | kernel | graphiti | h0 | one_on_one | 3 | 3 | 3 |
| qwen | kernel | graphiti | h0 | teammate | 6 | 6 | 6 |
| qwen | native | graphiti | h0 | client | 4 | 2 | 2 |
| qwen | native | graphiti | h0 | conference | 3 | 0 | 1 |
| qwen | native | graphiti | h0 | home_city | 6 | 1 | 4 |
| qwen | native | graphiti | h0 | manager | 4 | 1 | 1 |
| qwen | native | graphiti | h0 | offsite_city | 4 | 2 | 2 |
| qwen | native | graphiti | h0 | one_on_one | 3 | 2 | 2 |
| qwen | native | graphiti | h0 | teammate | 6 | 5 | 5 |
| qwen | replicated | graphiti | h0 | client | 4 | 4 | 4 |
| qwen | replicated | graphiti | h0 | conference | 3 | 3 | 3 |
| qwen | replicated | graphiti | h0 | home_city | 6 | 6 | 6 |
| qwen | replicated | graphiti | h0 | manager | 4 | 4 | 4 |
| qwen | replicated | graphiti | h0 | offsite_city | 4 | 4 | 4 |
| qwen | replicated | graphiti | h0 | one_on_one | 3 | 3 | 3 |
| qwen | replicated | graphiti | h0 | teammate | 6 | 6 | 6 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | recency | 0 | 0 | 30 | 30 |
| qwen | kernel | graphiti | h0 | contradiction | 0 | 0 | 30 | 30 |
| qwen | native | graphiti | h0 | recency | 0 | 0 | 30 | 11 |
| qwen | native | graphiti | h0 | contradiction | 0 | 0 | 30 | 13 |
| qwen | replicated | graphiti | h0 | recency | 0 | 0 | 30 | 30 |
| qwen | replicated | graphiti | h0 | contradiction | 0 | 0 | 30 | 30 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 30 | 10.00 | 0.00 | 10.00 | 0 | 30 | 23 | 23 | 2.20 |  |
| qwen | native | graphiti | h0 | 30 | 9.40 | 0.00 | 9.40 |  | 30 | 16 | 16 | 2.00 |  |
| qwen | replicated | graphiti | h0 | 30 | 10.00 | 0.00 | 10.00 | 0 | 29 | 22 | 21 | 1.97 | 2.00 |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score |
|---|---|---|---|---|---|---|
| qwen | kernel | graphiti | h0 | 1 | 7 | 1.86 |
| qwen | kernel | graphiti | h0 | 2 | 23 | 2.30 |
| qwen | native | graphiti | h0 | 1 | 14 | 2.07 |
| qwen | native | graphiti | h0 | 2 | 16 | 1.94 |
| qwen | replicated | graphiti | h0 | 1 | 9 | 1.89 |
| qwen | replicated | graphiti | h0 | 2 | 21 | 2.00 |

