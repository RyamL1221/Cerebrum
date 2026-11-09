# Benchmark v2 analysis

6 cells, 180 user-trials, 0 failed.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 21 | 30 | 0.70 | 0.52 | 0.83 |  |  |  | 9 | 9 | 0 | 30 | 0 | 30 |
| qwen | kernel | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 3 | 30 |
| qwen | kernel | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 1 | 30 | 15 | 30 |
| qwen | kernel | inhouse | h0 | recency | 8 | 30 | 0.27 | 0.14 | 0.44 | 1.00 | 22 | 18 |  |  | 0 | 30 | 16 | 30 |
| qwen | kernel | inhouse | h0 | contradiction | 14 | 30 | 0.47 | 0.30 | 0.64 | 0.57 | 3 | 0 |  |  | 3 | 30 | 21 | 30 |
| qwen | kernel | inhouse | h0 | deletion (echo) | 1 | 10 | 0.10 | 0.02 | 0.40 |  |  |  | 9 | 9 | 0 | 10 | 0 | 10 |
| qwen | kernel | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 | 0 | 20 |
| qwen | kernel | mem0 | h0 | deletion | 22 | 30 | 0.73 | 0.56 | 0.86 |  |  |  | 8 | 8 | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | recall | 29 | 30 | 0.97 | 0.83 | 0.99 |  |  |  |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | recency | 9 | 30 | 0.30 | 0.17 | 0.48 | 0.97 | 20 | 12 |  |  | 0 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | contradiction | 15 | 30 | 0.50 | 0.33 | 0.67 | 0.70 | 6 | 0 |  |  | 2 | 30 | 0 | 30 |
| qwen | kernel | mem0 | h0 | deletion (echo) | 4 | 10 | 0.40 | 0.17 | 0.69 |  |  |  | 6 | 6 | 0 | 10 | 0 | 10 |
| qwen | kernel | mem0 | h0 | deletion (no echo) | 18 | 20 | 0.90 | 0.70 | 0.97 |  |  |  | 2 | 2 | 0 | 20 | 0 | 20 |
| qwen | native | inhouse | h0 | deletion | 22 | 30 | 0.73 | 0.56 | 0.86 |  |  |  | 8 | 8 | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | recency | 13 | 30 | 0.43 | 0.27 | 0.61 | 1.00 | 17 | 13 |  |  | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | contradiction | 11 | 30 | 0.37 | 0.22 | 0.54 | 0.47 | 3 | 0 |  |  | 0 | 30 |  | 30 |
| qwen | native | inhouse | h0 | deletion (echo) | 2 | 10 | 0.20 | 0.06 | 0.51 |  |  |  | 8 | 8 | 0 | 10 |  | 10 |
| qwen | native | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 |  | 20 |
| qwen | native | mem0 | h0 | deletion | 28 | 30 | 0.93 | 0.79 | 0.98 |  |  |  | 2 | 2 | 0 | 30 |  | 30 |
| qwen | native | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 |  | 30 |
| qwen | native | mem0 | h0 | recall | 5 | 30 | 0.17 | 0.07 | 0.34 |  |  |  |  |  | 1 | 30 |  | 30 |
| qwen | native | mem0 | h0 | recency | 0 | 30 | 0.00 | 0.00 | 0.11 | 0.07 | 2 | 1 |  |  | 1 | 30 |  | 30 |
| qwen | native | mem0 | h0 | contradiction | 1 | 30 | 0.03 | 0.01 | 0.17 | 0.07 | 1 | 0 |  |  | 4 | 30 |  | 30 |
| qwen | native | mem0 | h0 | deletion (echo) | 8 | 10 | 0.80 | 0.49 | 0.94 |  |  |  | 2 | 2 | 0 | 10 |  | 10 |
| qwen | native | mem0 | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 |  | 20 |
| qwen | replicated | inhouse | h0 | deletion | 21 | 30 | 0.70 | 0.52 | 0.83 |  |  |  | 9 | 9 | 0 | 30 | 0 | 30 |
| qwen | replicated | inhouse | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 3 | 30 |
| qwen | replicated | inhouse | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 1 | 30 | 15 | 30 |
| qwen | replicated | inhouse | h0 | recency | 8 | 30 | 0.27 | 0.14 | 0.44 | 1.00 | 22 | 18 |  |  | 0 | 30 | 16 | 30 |
| qwen | replicated | inhouse | h0 | contradiction | 14 | 30 | 0.47 | 0.30 | 0.64 | 0.57 | 3 | 0 |  |  | 3 | 30 | 21 | 30 |
| qwen | replicated | inhouse | h0 | deletion (echo) | 1 | 10 | 0.10 | 0.02 | 0.40 |  |  |  | 9 | 9 | 0 | 10 | 0 | 10 |
| qwen | replicated | inhouse | h0 | deletion (no echo) | 20 | 20 | 1.00 | 0.84 | 1.00 |  |  |  | 0 | 0 | 0 | 20 | 0 | 20 |
| qwen | replicated | mem0 | h0 | deletion | 22 | 30 | 0.73 | 0.56 | 0.86 |  |  |  | 8 | 8 | 0 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | privacy | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  | 0 | 0 | 0 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | recall | 30 | 30 | 1.00 | 0.89 | 1.00 |  |  |  |  |  | 0 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | recency | 9 | 30 | 0.30 | 0.17 | 0.48 | 0.93 | 19 | 14 |  |  | 0 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | contradiction | 14 | 30 | 0.47 | 0.30 | 0.64 | 0.73 | 8 | 0 |  |  | 3 | 30 | 0 | 30 |
| qwen | replicated | mem0 | h0 | deletion (echo) | 4 | 10 | 0.40 | 0.17 | 0.69 |  |  |  | 6 | 6 | 0 | 10 | 0 | 10 |
| qwen | replicated | mem0 | h0 | deletion (no echo) | 18 | 20 | 0.90 | 0.70 | 0.97 |  |  |  | 2 | 2 | 0 | 20 | 0 | 20 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 180 | 180 | 82 | 362.00 | 500 |
| qwen | kernel | mem0 | h0 | 180 | 180 | 0 | 255.50 | 475 |
| qwen | native | inhouse | h0 | 180 | 180 |  | 443.00 | 1164 |
| qwen | native | mem0 | h0 | 180 | 180 |  | 247.50 | 475 |
| qwen | replicated | inhouse | h0 | 180 | 180 | 82 | 362.00 | 500 |
| qwen | replicated | mem0 | h0 | 180 | 180 | 0 | 260.50 | 457 |

## Kernel against replicated (paired over users)

| model | backend | probe | pairs | kernel_only | replicated_only | p_mcnemar |
|---|---|---|---|---|---|---|
| qwen | mem0 | deletion | 30 | 0 | 0 | 1.00 |
| qwen | mem0 | privacy | 30 | 0 | 0 | 1.00 |
| qwen | mem0 | recall | 30 | 0 | 1 | 1.00 |
| qwen | mem0 | recency | 30 | 3 | 3 | 1.00 |
| qwen | mem0 | contradiction | 30 | 2 | 1 | 1.00 |
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
| qwen | kernel | inhouse | h0 | 30 | 1.77 | 1.48 | 2.06 | 0.77 | 0.07 |
| qwen | kernel | mem0 | h0 | 30 | 3.33 | 2.98 | 3.69 | 0.96 | 0.63 |
| qwen | native | inhouse | h0 | 30 | 2.90 | 2.50 | 3.30 | 1.06 | 0.43 |
| qwen | native | mem0 | h0 | 30 | 2.93 | 2.59 | 3.27 | 0.91 | 0.37 |
| qwen | replicated | inhouse | h0 | 30 | 1.80 | 1.50 | 2.10 | 0.81 | 0.07 |
| qwen | replicated | mem0 | h0 | 30 | 3.13 | 2.76 | 3.51 | 1.01 | 0.53 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | deletion | 30 | 21 | 9 | 0 |
| qwen | kernel | inhouse | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | kernel | mem0 | h0 | deletion | 30 | 22 | 11 | 3 |
| qwen | kernel | mem0 | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | native | inhouse | h0 | deletion | 30 | 22 | 10 | 2 |
| qwen | native | inhouse | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | native | mem0 | h0 | deletion | 30 | 28 | 10 | 8 |
| qwen | native | mem0 | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | replicated | inhouse | h0 | deletion | 30 | 21 | 9 | 0 |
| qwen | replicated | inhouse | h0 | privacy | 30 | 30 | 0 | 0 |
| qwen | replicated | mem0 | h0 | deletion | 30 | 22 | 11 | 3 |
| qwen | replicated | mem0 | h0 | privacy | 30 | 30 | 0 | 0 |

## Deletion failures by carrier

The sources of the block rows that held the revoked value (`other_fact` is a Mem0 fold); `block, no row`: the block text held it but no row did; `answer only`: the block text did not hold it (only the answer did).

| model | locus | backend | condition | carrier | failures |
|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | echo | 9 |
| qwen | kernel | mem0 | h0 | echo | 5 |
| qwen | kernel | mem0 | h0 | other_fact | 3 |
| qwen | native | inhouse | h0 | echo | 8 |
| qwen | native | mem0 | h0 | echo | 1 |
| qwen | native | mem0 | h0 | other_fact | 1 |
| qwen | replicated | inhouse | h0 | echo | 9 |
| qwen | replicated | mem0 | h0 | echo | 5 |
| qwen | replicated | mem0 | h0 | other_fact | 3 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes |
|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | echo | 9 | 1 |
| qwen | kernel | inhouse | h0 | none | 0 | 20 |
| qwen | kernel | mem0 | h0 | echo | 5 | 4 |
| qwen | kernel | mem0 | h0 | echo+other_fact | 1 | 0 |
| qwen | kernel | mem0 | h0 | none | 0 | 18 |
| qwen | kernel | mem0 | h0 | other_fact | 2 | 0 |
| qwen | native | inhouse | h0 | echo | 8 | 2 |
| qwen | native | inhouse | h0 | none | 0 | 20 |
| qwen | native | mem0 | h0 | echo | 1 | 8 |
| qwen | native | mem0 | h0 | echo+other_fact | 1 | 0 |
| qwen | native | mem0 | h0 | none | 0 | 19 |
| qwen | native | mem0 | h0 | other_fact | 0 | 1 |
| qwen | replicated | inhouse | h0 | echo | 9 | 1 |
| qwen | replicated | inhouse | h0 | none | 0 | 20 |
| qwen | replicated | mem0 | h0 | echo | 5 | 4 |
| qwen | replicated | mem0 | h0 | echo+other_fact | 1 | 0 |
| qwen | replicated | mem0 | h0 | none | 0 | 18 |
| qwen | replicated | mem0 | h0 | other_fact | 2 | 0 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `not_in_block` (never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | not_in_block | in_block_no_row | conversation_only | in_writer_row |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | recency | 22 | 22 | 0 | 0 | 0 | 22 |
| qwen | kernel | inhouse | h0 | contradiction | 16 | 3 | 0 | 0 | 1 | 15 |
| qwen | kernel | mem0 | h0 | recall | 1 | 0 | 0 | 0 | 0 | 1 |
| qwen | kernel | mem0 | h0 | recency | 21 | 20 | 0 | 0 | 0 | 21 |
| qwen | kernel | mem0 | h0 | contradiction | 15 | 6 | 0 | 0 | 0 | 15 |
| qwen | native | inhouse | h0 | recency | 17 | 17 | 0 | 0 | 0 | 17 |
| qwen | native | inhouse | h0 | contradiction | 19 | 3 | 0 | 0 | 0 | 19 |
| qwen | native | mem0 | h0 | recall | 25 | 0 | 25 | 0 | 0 | 0 |
| qwen | native | mem0 | h0 | recency | 30 | 2 | 28 | 0 | 1 | 1 |
| qwen | native | mem0 | h0 | contradiction | 29 | 1 | 27 | 0 | 1 | 1 |
| qwen | replicated | inhouse | h0 | recency | 22 | 22 | 0 | 0 | 0 | 22 |
| qwen | replicated | inhouse | h0 | contradiction | 16 | 3 | 0 | 0 | 1 | 15 |
| qwen | replicated | mem0 | h0 | recency | 21 | 19 | 0 | 0 | 0 | 21 |
| qwen | replicated | mem0 | h0 | contradiction | 16 | 8 | 0 | 0 | 0 | 16 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient |
|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | client | 4 | 4 | 4 |
| qwen | kernel | inhouse | h0 | conference | 3 | 1 | 2 |
| qwen | kernel | inhouse | h0 | home_city | 6 | 6 | 6 |
| qwen | kernel | inhouse | h0 | manager | 4 | 0 | 0 |
| qwen | kernel | inhouse | h0 | offsite_city | 4 | 0 | 2 |
| qwen | kernel | inhouse | h0 | one_on_one | 3 | 2 | 2 |
| qwen | kernel | inhouse | h0 | teammate | 6 | 1 | 1 |
| qwen | kernel | mem0 | h0 | client | 4 | 3 | 3 |
| qwen | kernel | mem0 | h0 | conference | 3 | 3 | 3 |
| qwen | kernel | mem0 | h0 | home_city | 6 | 5 | 6 |
| qwen | kernel | mem0 | h0 | manager | 4 | 0 | 0 |
| qwen | kernel | mem0 | h0 | offsite_city | 4 | 0 | 2 |
| qwen | kernel | mem0 | h0 | one_on_one | 3 | 2 | 3 |
| qwen | kernel | mem0 | h0 | teammate | 6 | 2 | 4 |
| qwen | native | inhouse | h0 | client | 4 | 2 | 4 |
| qwen | native | inhouse | h0 | conference | 3 | 1 | 1 |
| qwen | native | inhouse | h0 | home_city | 6 | 5 | 5 |
| qwen | native | inhouse | h0 | manager | 4 | 0 | 0 |
| qwen | native | inhouse | h0 | offsite_city | 4 | 0 | 1 |
| qwen | native | inhouse | h0 | one_on_one | 3 | 1 | 1 |
| qwen | native | inhouse | h0 | teammate | 6 | 2 | 2 |
| qwen | native | mem0 | h0 | client | 4 | 0 | 0 |
| qwen | native | mem0 | h0 | conference | 3 | 0 | 0 |
| qwen | native | mem0 | h0 | home_city | 6 | 0 | 0 |
| qwen | native | mem0 | h0 | manager | 4 | 1 | 2 |
| qwen | native | mem0 | h0 | offsite_city | 4 | 0 | 0 |
| qwen | native | mem0 | h0 | one_on_one | 3 | 0 | 0 |
| qwen | native | mem0 | h0 | teammate | 6 | 0 | 0 |
| qwen | replicated | inhouse | h0 | client | 4 | 4 | 4 |
| qwen | replicated | inhouse | h0 | conference | 3 | 1 | 2 |
| qwen | replicated | inhouse | h0 | home_city | 6 | 6 | 6 |
| qwen | replicated | inhouse | h0 | manager | 4 | 0 | 0 |
| qwen | replicated | inhouse | h0 | offsite_city | 4 | 0 | 2 |
| qwen | replicated | inhouse | h0 | one_on_one | 3 | 2 | 2 |
| qwen | replicated | inhouse | h0 | teammate | 6 | 1 | 1 |
| qwen | replicated | mem0 | h0 | client | 4 | 2 | 3 |
| qwen | replicated | mem0 | h0 | conference | 3 | 2 | 3 |
| qwen | replicated | mem0 | h0 | home_city | 6 | 5 | 6 |
| qwen | replicated | mem0 | h0 | manager | 4 | 0 | 2 |
| qwen | replicated | mem0 | h0 | offsite_city | 4 | 0 | 1 |
| qwen | replicated | mem0 | h0 | one_on_one | 3 | 2 | 3 |
| qwen | replicated | mem0 | h0 | teammate | 6 | 3 | 4 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | recency | 4 | 0 | 26 | 8 |
| qwen | kernel | inhouse | h0 | contradiction | 14 | 4 | 16 | 10 |
| qwen | kernel | mem0 | h0 | recency | 2 | 0 | 28 | 9 |
| qwen | kernel | mem0 | h0 | contradiction | 16 | 7 | 14 | 8 |
| qwen | native | inhouse | h0 | recency | 4 | 1 | 26 | 12 |
| qwen | native | inhouse | h0 | contradiction | 10 | 1 | 20 | 10 |
| qwen | native | mem0 | h0 | recency | 1 | 0 | 29 | 0 |
| qwen | native | mem0 | h0 | contradiction | 3 | 0 | 27 | 1 |
| qwen | replicated | inhouse | h0 | recency | 4 | 0 | 26 | 8 |
| qwen | replicated | inhouse | h0 | contradiction | 14 | 4 | 16 | 10 |
| qwen | replicated | mem0 | h0 | recency | 2 | 0 | 28 | 9 |
| qwen | replicated | mem0 | h0 | contradiction | 12 | 3 | 18 | 11 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 30 | 4.63 | 2.80 | 1.83 | 27 | 9 | 5 | 1 | 2.11 | 1.62 |
| qwen | kernel | mem0 | h0 | 30 | 10.00 | 4.23 | 5.77 | 0 | 30 | 23 | 23 | 3.33 |  |
| qwen | native | inhouse | h0 | 30 | 9.60 | 4.73 | 4.87 |  | 23 | 20 | 13 | 3.17 | 2.00 |
| qwen | native | mem0 | h0 | 30 | 9.83 | 4.17 | 5.67 |  | 28 | 25 | 24 | 2.89 | 3.50 |
| qwen | replicated | inhouse | h0 | 30 | 4.63 | 2.80 | 1.83 | 27 | 9 | 5 | 1 | 2.11 | 1.67 |
| qwen | replicated | mem0 | h0 | 30 | 10.00 | 4.27 | 5.73 | 0 | 30 | 22 | 22 | 3.13 |  |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score |
|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | h0 | 0 | 17 | 1.53 |
| qwen | kernel | inhouse | h0 | 1 | 12 | 1.92 |
| qwen | kernel | inhouse | h0 | 2 | 1 | 4.00 |
| qwen | kernel | mem0 | h0 | 1 | 7 | 3.00 |
| qwen | kernel | mem0 | h0 | 2 | 23 | 3.43 |
| qwen | native | inhouse | h0 | 1 | 17 | 2.35 |
| qwen | native | inhouse | h0 | 2 | 13 | 3.62 |
| qwen | native | mem0 | h0 | 0 | 1 | 4.00 |
| qwen | native | mem0 | h0 | 1 | 5 | 2.60 |
| qwen | native | mem0 | h0 | 2 | 24 | 2.96 |
| qwen | replicated | inhouse | h0 | 0 | 17 | 1.59 |
| qwen | replicated | inhouse | h0 | 1 | 12 | 1.92 |
| qwen | replicated | inhouse | h0 | 2 | 1 | 4.00 |
| qwen | replicated | mem0 | h0 | 1 | 8 | 2.12 |
| qwen | replicated | mem0 | h0 | 2 | 22 | 3.50 |

