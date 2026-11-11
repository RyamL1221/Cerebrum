# Benchmark v2 analysis

6 cells, 180 user-trials, 0 failed.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 29 | 0 | 30 |
| qwen | kernel | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 29 | 0 | 30 |
| qwen | kernel | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 29 | 0 | 30 |
| qwen | kernel | inhouse | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 29 | 0 | 30 |
| qwen | kernel | inhouse | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 29 | 0 | 30 |
| qwen | kernel | inhouse | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 10 | 0 | 10 |
| qwen | kernel | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 19 | 0 | 20 |
| qwen | kernel | mem0 | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 2 | 30 |
| qwen | kernel | mem0 | h0 | recall | 28 | 30 | 0.93 | 0.79 | 0.98 |  |  |  |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | recency | 22 | 30 | 0.73 | 0.56 | 0.86 | 1.00 | 8 | 8 |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 10 | 0 | 10 |
| qwen | kernel | mem0 | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 | 0 | 20 |
| qwen | native | inhouse | h0 | deletion | 21 | 30 | 0.70 | 0.52 | 0.83 |  |  |  | 9 | 9 | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | recency | 10 | 30 | 0.33 | 0.19 | 0.51 | 1.00 | 20 | 18 |  |  | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | contradiction | 18 | 30 | 0.60 | 0.42 | 0.75 | 0.67 | 2 | 0 |  |  | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | deletion (echo) | 1 | 10 | 0.10 | 0.02 | 0.40 |  |  |  | 9 | 9 | 0 | 10 |  | 10 |
| qwen | native | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 |  | 20 |
| qwen | native | mem0 | h0 | deletion | 26 | 30 | 0.87 | 0.70 | 0.95 |  |  |  | 4 | 4 | 0 | 30 |  | 30 |
| qwen | native | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 |  | 30 |
| qwen | native | mem0 | h0 | recall | 5 | 30 | 0.17 | 0.07 | 0.34 |  |  |  |  |  | 0 | 30 |  | 30 |
| qwen | native | mem0 | h0 | recency | 0 | 30 | 0.00 | 0.00 | 0.11 | 0.00 | 0 | 0 |  |  | 0 | 30 |  | 30 |
| qwen | native | mem0 | h0 | contradiction | 0 | 30 | 0.00 | 0.00 | 0.11 | 0.00 | 0 | 0 |  |  | 0 | 30 |  | 30 |
| qwen | native | mem0 | h0 | deletion (echo) | 7 | 10 | 0.70 | 0.40 | 0.89 |  |  |  | 3 | 3 | 0 | 10 |  | 10 |
| qwen | native | mem0 | h0 | deletion (no echo) | 19 | 20 | 0.95 | 0.76 | 0.99 |  |  |  | 1 | 1 | 0 | 20 |  | 20 |
| qwen | replicated | inhouse | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 29 | 0 | 30 |
| qwen | replicated | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 29 | 0 | 30 |
| qwen | replicated | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 29 | 0 | 30 |
| qwen | replicated | inhouse | h0 | recency | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 29 | 0 | 30 |
| qwen | replicated | inhouse | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 29 | 0 | 30 |
| qwen | replicated | inhouse | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 10 | 0 | 10 |
| qwen | replicated | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 19 | 0 | 20 |
| qwen | replicated | mem0 | h0 | deletion | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 1 | 30 |
| qwen | replicated | mem0 | h0 | recall | 28 | 30 | 0.93 | 0.79 | 0.98 |  |  |  |  |  | 0 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | recency | 23 | 30 | 0.77 | 0.59 | 0.88 | 1.00 | 7 | 6 |  |  | 0 | 30 | 2 | 30 |
| qwen | replicated | mem0 | h0 | contradiction | 30 | 30 | 1.00 | 0.89 | 1.00 | 1.00 | 0 | 0 |  |  | 0 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | deletion (echo) | 10 | 10 | 1.00 | 0.72 | 1.00 |  |  |  | 0 | 0 | 0 | 10 | 0 | 10 |
| qwen | replicated | mem0 | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 | 0 | 20 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 180 | 174 | 3 | 196.00 | 300 |
| qwen | kernel | mem0 | h0 | 180 | 180 | 5 | 251.00 | 300 |
| qwen | native | inhouse | h0 | 180 | 180 |  | 179.00 | 301 |
| qwen | native | mem0 | h0 | 180 | 180 |  | 224.00 | 323 |
| qwen | replicated | inhouse | h0 | 180 | 174 | 3 | 196.00 | 300 |
| qwen | replicated | mem0 | h0 | 180 | 180 | 5 | 251.00 | 300 |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar |
|---|---|---|---|---|---|---|
| qwen | mem0 | deletion | 30 | 0 | 0 | 1.00 |
| qwen | mem0 | privacy | 30 | 0 | 0 | 1.00 |
| qwen | mem0 | recall | 30 | 0 | 0 | 1.00 |
| qwen | mem0 | recency | 30 | 0 | 1 | 1.00 |
| qwen | mem0 | contradiction | 30 | 0 | 0 | 1.00 |
| qwen | inhouse | deletion | 30 | 0 | 0 | 1.00 |
| qwen | inhouse | privacy | 30 | 0 | 0 | 1.00 |
| qwen | inhouse | recall | 30 | 0 | 0 | 1.00 |
| qwen | inhouse | recency | 30 | 0 | 0 | 1.00 |
| qwen | inhouse | contradiction | 30 | 0 | 0 | 1.00 |
| qwen | inhouse | identical blocks | 180 | 180 |  |  |

## Integration (judge v2)

The mean with its 95% t-interval (none for n < 2).

| model | locus | backend | condition | n | mean | ci_low | ci_high | sd | share_ge_4 |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 30 | 2.87 | 2.50 | 3.23 | 0.97 | 0.40 |
| qwen | kernel | mem0 | h0 | 30 | 3.57 | 3.25 | 3.89 | 0.86 | 0.73 |
| qwen | native | inhouse | h0 | 30 | 3.10 | 2.73 | 3.47 | 0.99 | 0.50 |
| qwen | native | mem0 | h0 | 30 | 3.00 | 2.62 | 3.38 | 1.02 | 0.47 |
| qwen | replicated | inhouse | h0 | 30 | 2.87 | 2.50 | 3.23 | 0.97 | 0.40 |
| qwen | replicated | mem0 | h0 | 30 | 3.60 | 3.31 | 3.89 | 0.77 | 0.77 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the Mem0 history scrub (`messages` deleted, `history` records cleared), and rows later writes `swept` and writes `suppressed`.

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | other_agents | same_writer | no_values | messages | history | swept | suppressed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | kernel | mem0 | h0 | 30 | 30 | 42 | 30 | 12 | 0 | 10 | 2 | 0 | 40 | 84 | 0 | 0 |
| qwen | replicated | inhouse | h0 | 30 | 30 | 40 | 30 | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| qwen | replicated | mem0 | h0 | 30 | 30 | 42 | 30 | 12 | 0 | 10 | 2 | 0 | 40 | 84 | 0 | 0 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 60 | 60 | 60 | 180 | 0 | 360 |
| qwen | kernel | mem0 | h0 | 60 | 60 | 60 | 180 | 0 | 360 |
| qwen | native | inhouse | h0 | 0 | 60 | 0 | 180 | 168 | 0 |
| qwen | native | mem0 | h0 | 0 | 60 | 0 | 180 | 131 | 0 |
| qwen | replicated | inhouse | h0 | 60 | 60 | 60 | 180 | 0 | 360 |
| qwen | replicated | mem0 | h0 | 60 | 60 | 60 | 180 | 0 | 360 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 30 | 30 | 0 | 0 |
| qwen | kernel | inhouse | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | kernel | mem0 | h0 | deletion | 30 | 30 | 0 | 0 |
| qwen | kernel | mem0 | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | native | inhouse | h0 | deletion | 30 | 21 | 10 | 1 |
| qwen | native | inhouse | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | native | mem0 | h0 | deletion | 30 | 26 | 11 | 7 |
| qwen | native | mem0 | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | replicated | inhouse | h0 | deletion | 30 | 30 | 0 | 0 |
| qwen | replicated | inhouse | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | replicated | mem0 | h0 | deletion | 30 | 30 | 0 | 0 |
| qwen | replicated | mem0 | h0 | privacy | 30 | 30 | 0 | 0 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures |
|---|---|---|---|---|---|
| qwen | native | inhouse | h0 | echo | 9 |
| qwen | native | mem0 | h0 | echo | 2 |
| qwen | native | mem0 | h0 | other_fact | 2 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes |
|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | none | 0 | 30 |
| qwen | kernel | mem0 | h0 | none | 0 | 30 |
| qwen | native | inhouse | h0 | echo | 9 | 1 |
| qwen | native | inhouse | h0 | none | 0 | 20 |
| qwen | native | mem0 | h0 | echo | 2 | 7 |
| qwen | native | mem0 | h0 | echo+other_fact | 1 | 0 |
| qwen | native | mem0 | h0 | none | 0 | 18 |
| qwen | native | mem0 | h0 | other_fact | 1 | 1 |
| qwen | replicated | inhouse | h0 | none | 0 | 30 |
| qwen | replicated | mem0 | h0 | none | 0 | 30 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | mem0 | h0 | recall | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| qwen | kernel | mem0 | h0 | recency | 8 | 8 | 0 | 0 | 0 | 0 | 8 |
| qwen | native | inhouse | h0 | recency | 20 | 20 | 0 | 0 | 0 | 0 | 20 |
| qwen | native | inhouse | h0 | contradiction | 12 | 2 | 0 | 0 | 0 | 0 | 12 |
| qwen | native | mem0 | h0 | recall | 25 | 0 | 0 | 25 | 0 | 0 | 0 |
| qwen | native | mem0 | h0 | recency | 30 | 0 | 0 | 30 | 0 | 0 | 0 |
| qwen | native | mem0 | h0 | contradiction | 30 | 0 | 0 | 30 | 0 | 0 | 0 |
| qwen | replicated | mem0 | h0 | recall | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| qwen | replicated | mem0 | h0 | recency | 7 | 7 | 0 | 0 | 0 | 0 | 7 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient |
|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | client | 4 | 4 | 4 |
| qwen | kernel | inhouse | h0 | conference | 3 | 3 | 3 |
| qwen | kernel | inhouse | h0 | home_city | 6 | 6 | 6 |
| qwen | kernel | inhouse | h0 | manager | 4 | 4 | 4 |
| qwen | kernel | inhouse | h0 | offsite_city | 4 | 4 | 4 |
| qwen | kernel | inhouse | h0 | one_on_one | 3 | 3 | 3 |
| qwen | kernel | inhouse | h0 | teammate | 6 | 6 | 6 |
| qwen | kernel | mem0 | h0 | client | 4 | 4 | 4 |
| qwen | kernel | mem0 | h0 | conference | 3 | 3 | 3 |
| qwen | kernel | mem0 | h0 | home_city | 6 | 6 | 6 |
| qwen | kernel | mem0 | h0 | manager | 4 | 4 | 4 |
| qwen | kernel | mem0 | h0 | offsite_city | 4 | 4 | 4 |
| qwen | kernel | mem0 | h0 | one_on_one | 3 | 3 | 3 |
| qwen | kernel | mem0 | h0 | teammate | 6 | 6 | 6 |
| qwen | native | inhouse | h0 | client | 4 | 3 | 3 |
| qwen | native | inhouse | h0 | conference | 3 | 1 | 1 |
| qwen | native | inhouse | h0 | home_city | 6 | 2 | 3 |
| qwen | native | inhouse | h0 | manager | 4 | 2 | 2 |
| qwen | native | inhouse | h0 | offsite_city | 4 | 3 | 4 |
| qwen | native | inhouse | h0 | one_on_one | 3 | 2 | 2 |
| qwen | native | inhouse | h0 | teammate | 6 | 5 | 5 |
| qwen | native | mem0 | h0 | client | 4 | 0 | 0 |
| qwen | native | mem0 | h0 | conference | 3 | 0 | 0 |
| qwen | native | mem0 | h0 | home_city | 6 | 0 | 0 |
| qwen | native | mem0 | h0 | manager | 4 | 0 | 0 |
| qwen | native | mem0 | h0 | offsite_city | 4 | 0 | 0 |
| qwen | native | mem0 | h0 | one_on_one | 3 | 0 | 0 |
| qwen | native | mem0 | h0 | teammate | 6 | 0 | 0 |
| qwen | replicated | inhouse | h0 | client | 4 | 4 | 4 |
| qwen | replicated | inhouse | h0 | conference | 3 | 3 | 3 |
| qwen | replicated | inhouse | h0 | home_city | 6 | 6 | 6 |
| qwen | replicated | inhouse | h0 | manager | 4 | 4 | 4 |
| qwen | replicated | inhouse | h0 | offsite_city | 4 | 4 | 4 |
| qwen | replicated | inhouse | h0 | one_on_one | 3 | 3 | 3 |
| qwen | replicated | inhouse | h0 | teammate | 6 | 6 | 6 |
| qwen | replicated | mem0 | h0 | client | 4 | 4 | 4 |
| qwen | replicated | mem0 | h0 | conference | 3 | 3 | 3 |
| qwen | replicated | mem0 | h0 | home_city | 6 | 6 | 6 |
| qwen | replicated | mem0 | h0 | manager | 4 | 4 | 4 |
| qwen | replicated | mem0 | h0 | offsite_city | 4 | 4 | 4 |
| qwen | replicated | mem0 | h0 | one_on_one | 3 | 3 | 3 |
| qwen | replicated | mem0 | h0 | teammate | 6 | 6 | 6 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | recency | 0 | 0 | 30 | 30 |
| qwen | kernel | inhouse | h0 | contradiction | 0 | 0 | 30 | 30 |
| qwen | kernel | mem0 | h0 | recency | 0 | 0 | 30 | 22 |
| qwen | kernel | mem0 | h0 | contradiction | 0 | 0 | 30 | 30 |
| qwen | native | inhouse | h0 | recency | 0 | 0 | 30 | 10 |
| qwen | native | inhouse | h0 | contradiction | 0 | 0 | 30 | 18 |
| qwen | native | mem0 | h0 | recency | 0 | 0 | 30 | 0 |
| qwen | native | mem0 | h0 | contradiction | 0 | 0 | 30 | 0 |
| qwen | replicated | inhouse | h0 | recency | 0 | 0 | 30 | 30 |
| qwen | replicated | inhouse | h0 | contradiction | 0 | 0 | 30 | 30 |
| qwen | replicated | mem0 | h0 | recency | 0 | 0 | 30 | 23 |
| qwen | replicated | mem0 | h0 | contradiction | 0 | 0 | 30 | 30 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 30 | 9.90 | 0.00 | 9.90 | 3 | 30 | 30 | 30 | 2.87 |  |
| qwen | kernel | mem0 | h0 | 30 | 9.90 | 0.00 | 9.90 | 3 | 30 | 30 | 30 | 3.57 |  |
| qwen | native | inhouse | h0 | 30 | 9.17 | 0.00 | 9.17 |  | 27 | 30 | 27 | 3.26 | 1.67 |
| qwen | native | mem0 | h0 | 30 | 9.47 | 0.00 | 9.47 |  | 28 | 29 | 27 | 3.07 | 2.00 |
| qwen | replicated | inhouse | h0 | 30 | 9.90 | 0.00 | 9.90 | 3 | 30 | 30 | 30 | 2.87 |  |
| qwen | replicated | mem0 | h0 | 30 | 9.90 | 0.00 | 9.90 | 2 | 30 | 29 | 29 | 3.60 |  |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score |
|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 2 | 30 | 2.87 |
| qwen | kernel | mem0 | h0 | 2 | 30 | 3.57 |
| qwen | native | inhouse | h0 | 1 | 3 | 1.67 |
| qwen | native | inhouse | h0 | 2 | 27 | 3.26 |
| qwen | native | mem0 | h0 | 1 | 3 | 2.00 |
| qwen | native | mem0 | h0 | 2 | 27 | 3.11 |
| qwen | replicated | inhouse | h0 | 2 | 30 | 2.87 |
| qwen | replicated | mem0 | h0 | 1 | 1 | 2.00 |
| qwen | replicated | mem0 | h0 | 2 | 29 | 3.66 |

