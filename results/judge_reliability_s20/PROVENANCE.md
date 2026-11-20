# judge_reliability_s20: provenance

The judge reliability study of NeurIPS Subtask 20 (AIOS
`docs/METRICS.md`, "Reliability protocol" and "The k rule"). Result:
AIOS `docs/DEV_STATUS.md`, Subtask 20.

- **Calibration set**: `benchmarks/shared_memory/data/calibration_v1.jsonl`
  (200 answers from 2,196 candidates in 60 cells, 2 to 4 per cell;
  bands high 76, mid 51, low 73; seed 20261120), built by
  `judge_reliability build` and committed in Cerebrum `26d2bc5`.
- **Code**: the judging path committed in Cerebrum `26d2bc5`; the files
  here were produced from the working tree on `7d19bf4` just before
  that commit (2026-11-19), whose judging code is the committed code. The report
  regenerated at `26d2bc5` from the same judgments is byte-identical to
  `report_claude_only.md` / `.json`. The primary judge's judgments and
  `report.md` / `.json` were produced at Cerebrum `6e912d1`, through a
  kernel at AIOS `d49afc9` (clean trees, 2026-11-20).

## The second judge, Claude Sonnet 5.5 (`claude-sonnet-5.5.jsonl`)

- Model `claude-sonnet-5-5` through the Anthropic Message Batches API,
  Anthropic Python SDK 2.10.0; OAuth bearer token from
  `ant auth print-credentials --access-token`, fetched at each call and
  never stored, with `anthropic-beta: oauth-2025-04-20`. Default
  sampling (the API takes no sampling parameter), `thinking:
  {type: "between_tools"}`, no tools, `max_tokens` 1024, judge prompt
  v2.
- 10 repeats of each of the 200 answers: 2,000 judgments, custom id
  `<item>-<repeat>`. Batch `msgbatch_01RXMLnHGjEkvJk8S5bqzW6e`; the two
  judgments whose first reply lacked a score (c064 repeat 10, c151
  repeat 4) were judged again in batch
  `msgbatch_01CQpZzdoRNffqr9vD6PSWST` (2,002 calls in all). Judged
  2026-11-19 18:03 to 18:10 UTC (each judgment records its batch,
  submission and collection times).
- Tokens: 3,421,511 in, 829,921 out (1,711 / 415 per judgment); about
  $7.57 at the Batch API's rates ($1 / $5 per million tokens in / out).
- The first results download failed three times ("Bad file
  descriptor": the SDK client was garbage-collected while its results
  streamed; fixed in `claude_batch_scores`, with a test); the batch was
  then collected with `judge --batch-id`, with no resubmission.
- A first submission with custom ids `<item>:<repeat>` was refused
  (HTTP 400, nothing billed); ids are now `<item>-<repeat>`.

## The primary judge, GPT-5.4 (`gpt-5.4.jsonl`)

- Model `azure/gpt-5.4` through the kernel's `/query`
  (`chat_with_json_output`; LiteLLM, Azure API version
  `2024-02-15-preview`, region East US): greedy (temperature 0.0), seed
  20261105, judge prompt v2. One kernel served the measurement, the
  study and the re-judge (`results/s20_rejudge/`).
- 10 repeats of each of the 200 answers, 8 workers: 2,000 judgments,
  each at its first attempt, none failed. Judged 2026-11-20 17:09:12
  to 17:37:39 UTC (each judgment records its time).
- Tokens: 2,074,860 in, 430,621 out (1,037 / 215 per judgment); about
  $11.65 at $2.50 / $15 per million tokens in / out (OpenAI's list
  price for GPT-5.4; Azure's own price was not read).
- The kernel's log (3,400 judge calls, with the measurement and the
  re-judge): no error, and no judge call fell back to a plain chat (no
  memory request of any kind).

## Before the study

- `measure50_claude-sonnet-5.5.jsonl`: the 50-call token measurement
  that preceded the projection (after a 1-token Messages call and a
  2-request batch, submitted and fetched with fresh tokens). The checks
  and this measurement cost about $0.19.
- `measure50_gpt-5.4_azure403.jsonl`: the primary judge's first
  50-call measurement (2026-11-19), every call refused by Azure
  ("Access denied due to Virtual Network/Firewall rules", HTTP 403).
  The cause, found on 2026-11-20: a second VPN held the machine's
  default route, so the calls left from an address outside the allowed
  network. The key and the calls were right.
- `measure50_gpt-5.4.jsonl`: the measurement again (2026-11-20 17:07
  UTC), before the study: 50 of 50 judged at the first attempt, 50,987
  tokens in, 10,227 out (1,020 / 205 per judgment), about $0.28.

## Reports

- `report_claude_only.md` / `.json`: the second judge alone. k by the
  rule: 1 (median-of-1 alpha Profile 0.966 [0.951, 0.977], Integration
  0.963 [0.947, 0.975]). Regenerated at Cerebrum `692319c` (the review's
  fix: the ordinal median-of-k alpha is the mean over every split, not
  every 42nd or 2nd): the markdown is byte-identical; in the JSON only
  `median_of_k.{3,5}.alpha_ordinal` moved, by at most 0.0006 (for
  example Integration k = 3, 0.9741 to 0.9738). The k rule reads the
  interval alpha, which did not change.
- `report.md` / `.json`: both judges (rendered at Cerebrum `6e912d1`).
  The primary judge's k by the rule: 1 (median-of-1 alpha Profile 0.864
  [0.827, 0.893], Integration 0.906 [0.876, 0.929]; exact
  self-agreement 0.815 and 0.841, within-1 0.924 and 0.960; Task alpha
  0.989). At k = 3 its Profile alpha is 0.907, at k = 5 0.935. The
  second judge's section equals `report_claude_only.md`'s.
- Agreement between the judges, each at k = 1 (second − primary):
  Profile alpha 0.498 [0.382, 0.597], Spearman 0.685, offset −0.69
  [−0.81, −0.56]; Task 0.876 [0.822, 0.911], 0.763, −0.36 [−0.43,
  −0.29]; Integration 0.683 [0.608, 0.741], 0.756, −0.34 [−0.46,
  −0.23].
- Read with the report: at its first repeat the primary judge's
  Profile score is 3 for 6 of the 200 answers (1, 2, 4 or 5 for the
  rest), and 46 answers have Profile repeats 2 or more points apart;
  the second judge's repeats never differ by more than 1.

Every file here was scanned by AIOS `scripts/archive_artifacts.py
--check`: none holds a key value.

## Archive

`../repo-artifacts/Cerebrum/judge_reliability_s20/` (both judges'
judgments, the batch ids, the three 50-call measurements, the primary
judge's kernel log and run log, `SHA256SUMS`), copied through AIOS
`scripts/archive_artifacts.py` in two passes: 4 files scanned, then 4,
none holds a key value. Committed here: this file and the reports.
Cerebrum
`tests/agents/test_judge_reliability.py::test_the_reliability_report_reproduces_the_second_judges_study`
regenerates `report_claude_only.md` and `.json` from the judgments
without their reasoning text (`tests/agents/fixtures/judge_runs/`).
