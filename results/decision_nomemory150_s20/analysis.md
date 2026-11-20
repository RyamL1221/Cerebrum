# Benchmark v2 analysis

1 cells, 150 user-trials, 0 failed.

Every table but the criteria ends with `block_tokens` and `block_rows`: the mean block, in tokens and in rows, of a set of the row's cell's probes. In the pass matrix, the row's own probes (a deletion row split by echo, its split's); in the kernel-against-replicated table, the row's probe type, per locus (all probes for `identical blocks`); in the integration table and the integration readings, the cell's integration probes; elsewhere, the row's probe type where the row names one, else all of the cell's probes. A reading's row that splits a cell's probes further (a slot, a carrier, a count of base rows) shows its set's mean, not its own.

## Per-probe pass matrix

Pass rates with 95% Wilson intervals; recency and contradiction also give the lenient rate (the new value named, stale or not), how many answers named both values and how many of those named the stale one as past. `contaminated`: a value reached the block only through the consumer's own conversation rows.

| model | locus | backend | condition | probe | passed | n | rate | ci_low | ci_high | lenient | names_both | named_as_past | in_block | in_answer | contaminated | cap_bound | budget_bound | probes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | deletion | 150 | 150 | 1.00 | 0.98 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 150 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | privacy | 150 | 150 | 1.00 | 0.98 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 150 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | recall | 0 | 150 | 0.00 | 0.00 | 0.02 |  |  |  |  |  | 0 | 0 | 0 | 150 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | recency | 0 | 150 | 0.00 | 0.00 | 0.02 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 150 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | contradiction | 0 | 150 | 0.00 | 0.00 | 0.02 | 0.00 | 0 | 0 |  |  | 0 | 0 | 0 | 150 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | deletion (echo) | 50 | 50 | 1.00 | 0.93 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 50 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | deletion (no echo) | 100 | 100 | 1.00 | 0.96 | 1.00 |  |  |  | 0 | 0 | 0 | 0 | 0 | 100 | 0.00 | 0.00 |

## Cap and budget

| model | locus | backend | condition | probes | cap_bound | budget_bound | tokens_median | tokens_max | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | 900 | 0 | 0 | 0.00 | 0 | 0.00 | 0.00 |

## Revokes and the forget (Amendment 4)

Per kernel and replicated cell: revokes, those that went through the forget, the rows the forgets deleted (by reason: the slot's `fact_key`, a `value` or an `alias`, or an `entity`: a Graphiti scrub deleted it with an entity a form names, or `derived`: an A-MEM scrub deleted it because its derived text carried a form; `other_agents`: rows of agents other than the revoking writer; `same_writer`: rows of the revoking writer deleted by a value or an alias, rows of its other facts, as a Mem0 fold is), forgets that found no value, the history scrub (Mem0: `messages` deleted, `history` records cleared; A-MEM: `history` counts the carrier notes it deleted, as `derived` does), rows later writes `swept` and writes `suppressed`, and `scoped`: revokes through a forget the kernel ran under an ablated scope (no_delete, writer_scoped since Subtask 19; counted in no other column).

| model | locus | backend | condition | revokes | forget | deleted | fact_key | value | alias | entity | derived | other_agents | same_writer | no_values | messages | history | swept | suppressed | scoped | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 |

## Supersession (Amendment 4)

`retired`: rows writes marked retired; `earlier_rows`: the earlier statements' rows after the history (from the dataset) and how many carry a mark (`marked`); probes whose block held a retired row; rows the selection excluded as retired.

| model | locus | backend | condition | retired | earlier_rows | marked | probes | retired_in_block | excluded | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | 0 | 0 | 0 | 900 | 0 | 0 | 0.00 | 0.00 |

## Trial-level exposure (deletion, privacy)

A probe checks only its own block and answer. `exposed`: trials whose forbidden value appears in any probe's block or answer; `passed_exposed`: passes among them.

| model | locus | backend | condition | probe | n | passed | exposed | passed_exposed | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | deletion | 150 | 150 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | privacy | 150 | 150 | 0 | 0 | 0.00 | 0.00 |

## Deletion probes by what the store kept

The sources of the rows that still held the revoked value after the history, right before the probes (`revoked_value_rows`), or `none`. A pass with a stored carrier is one whose selection left it out of the block: the fetch did not return it, or a later stage, such as the cap, dropped it.

| model | locus | backend | condition | stored | failures | passes | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | none | 0 | 150 | 0.00 | 0.00 |

## Failures: where the expected value was

Failed recall, recency and contradiction probes by where the expected value was: `target_forgotten` (not in the block, and a forget or a sweep deleted every row the target event stored, as when Mem0 folded a forgotten value into it), `not_in_block` (any other failure outside the block: never stored, or selection lost it), `in_block_no_row` (the block text holds it, no injected row does), `conversation_only` (only the consumer's own earlier answers held it), `in_writer_row` (a writer's row held it). `named`: failures whose answer named the expected value too (they failed on the stale value).

| model | locus | backend | condition | probe | failed | named | target_forgotten | not_in_block | in_block_no_row | conversation_only | in_writer_row | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | recall | 150 | 0 | 0 | 150 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | recency | 150 | 0 | 0 | 150 | 0 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | contradiction | 150 | 0 | 0 | 150 | 0 | 0 | 0 | 0.00 | 0.00 |

## Contradiction by slot

`lenient`: answers that name the later value.

| model | locus | backend | condition | slot | n | passed | lenient | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | client | 26 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | conference | 10 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | home_city | 31 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | manager | 19 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | offsite_city | 21 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | one_on_one | 19 | 0 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | teammate | 24 | 0 | 0 | 0.00 | 0.00 |

## Recency and contradiction: the stale value in an earlier answer

Split by whether one of the consumer's earlier answers in the block carries the stale value.

| model | locus | backend | condition | probe | with_stale_answer | passed_with | without | passed_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | recency | 0 | 0 | 150 | 0 | 0.00 | 0.00 |
| qwen | kernel | inhouse | no_memory | contradiction | 0 | 0 | 150 | 0 | 0.00 | 0.00 |

## The integration probe's block

Means per probe: rows, the consumer's own rows (its earlier answers) and writer rows. Probes whose block holds a row of the user's base task context, of its base profile, and of both; the mean score with and without a base task row.

| model | locus | backend | condition | n | rows | own_rows | writer_rows | budget_bound | base_task_in_block | base_profile_in_block | both_in_block | score_with | score_without | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | 150 | 0.00 | 0.00 | 0.00 | 0 | 0 | 0 | 0 |  |  | 0.00 | 0.00 |

## Integration score by the base rows in the block

The judge scores the answer against the base profile and the base task context. `base_rows`: how many of the two have a row in the block.

| model | locus | backend | condition | base_rows | n | score | block_tokens | block_rows |
|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | 0 | 150 |  | 0.00 | 0.00 |

## Decision probe (Amendment 10)

Two items per user, four options each (chance 0.25), scored exactly from the letter named. Accuracy with its 95% Wilson interval; each error as its count and (its share of the items scored); `turn_errors`, items with a turn error (recorded, not scored); `echo_d1`, echo users' d1 items, and how many picked the revoked option.

| model | locus | backend | condition | items | correct | accuracy | ci_low | ci_high | stale | revoked | private | foreign | no_letter | multiple_letters | turn_errors | echo_d1 | echo_d1_revoked |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | 300 | 54 | 0.18 | 0.14 | 0.23 | 60 (0.20) | 47 (0.16) | 27 (0.09) | 112 (0.37) | 0 (0.00) | 0 (0.00) | 0 | 50 | 14 |

### Functional criteria D1-D5

| criterion | holds | evidence |
|---|---|---|
| D1 full system: pooled accuracy >= 0.6 |  | 0 of 0 over 0 cells |
| D2 no_memory: pooled accuracy in [0.10, 0.45] | True | 54 of 300 over 1 cells |
| D3 no_supersession: more stale errors than the same loci's full system |  | stale 0 of 0 vs 0 of 0 |
| D4 writer_scoped: >= 1 revoked error among echo users' d1 items, 0 in the full system |  | revoked 0 of 0 vs 0 of 0 |
| D5 wrong_user: >= 1 foreign error in the replicated and native cells, 0 in the kernel's |  | foreign 0 of 0 vs 0 of 0 |

### Picks by option kind and letter

Of the items scored, those that named one letter (`picked`), by the kind of the option named (chance 0.25 each): count (share) [95% Wilson interval]; `must_not_use` is `revoked` on d1 and `private` on d2. Letters picked and the items' correct letters as A/B/C/D, each with a chi-square test's p against uniform.

| model | locus | backend | condition | item | items | picked | correct | stale | must_not_use | foreign | letters | letters_p | correct_letters | correct_letters_p | no_letter | multiple_letters | turn_errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen | kernel | inhouse | no_memory | d1 | 150 | 150 | 28 (0.19) [0.13, 0.26] | 22 (0.15) [0.10, 0.21] | 47 (0.31) [0.24, 0.39] | 53 (0.35) [0.28, 0.43] | 33/46/38/33 | 0.39 | 37/37/34/42 | 0.83 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | d2 | 150 | 150 | 26 (0.17) [0.12, 0.24] | 38 (0.25) [0.19, 0.33] | 27 (0.18) [0.13, 0.25] | 59 (0.39) [0.32, 0.47] | 33/51/34/32 | 0.09 | 48/29/46/27 | 0.02 | 0 | 0 | 0 |
| qwen | kernel | inhouse | no_memory | pooled | 300 | 300 | 54 (0.18) [0.14, 0.23] | 60 (0.20) [0.16, 0.25] | 74 (0.25) [0.20, 0.30] | 112 (0.37) [0.32, 0.43] | 66/97/72/65 | 0.03 | 85/66/80/69 | 0.36 | 0 | 0 | 0 |

