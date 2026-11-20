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
  `report_claude_only.md` / `.json`.

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

## Before the study

- `measure50_claude-sonnet-5.5.jsonl`: the 50-call token measurement
  that preceded the projection (after a 1-token Messages call and a
  2-request batch, submitted and fetched with fresh tokens). The checks
  and this measurement cost about $0.19.
- `measure50_gpt-5.4_azure403.jsonl`: the primary judge's 50-call
  measurement, every call refused by Azure ("Access denied due to
  Virtual Network/Firewall rules", HTTP 403). No GPT-5.4 judgment is in
  this directory yet.

## Reports

- `report_claude_only.md` / `.json`: the second judge alone. k by the
  rule: 1 (median-of-1 alpha Profile 0.966 [0.951, 0.977], Integration
  0.963 [0.947, 0.975]). Regenerated at Cerebrum `692319c` (the review's
  fix: the ordinal median-of-k alpha is the mean over every split, not
  every 42nd or 2nd): the markdown is byte-identical; in the JSON only
  `median_of_k.{3,5}.alpha_ordinal` moved, by at most 0.0006 (for
  example Integration k = 3, 0.9741 to 0.9738). The k rule reads the
  interval alpha, which did not change.
- Open: the primary judge's calibration, the combined report (both
  judges, each at its own k, and their agreement).

Every file here was scanned by AIOS `scripts/archive_artifacts.py
--check`: none holds a key value.

## Archive

`../repo-artifacts/Cerebrum/judge_reliability_s20/` (the judgments,
the batch ids and both 50-call measurements, `SHA256SUMS`), copied
through AIOS `scripts/archive_artifacts.py`: 4 files scanned, none
holds a key value. Committed here: this file and the reports. Cerebrum
`tests/agents/test_judge_reliability.py::test_the_reliability_report_reproduces_the_second_judges_study`
regenerates `report_claude_only.md` and `.json` from the judgments
without their reasoning text (`tests/agents/fixtures/judge_runs/`).
