# s20_rejudge: provenance

The stored answers of three runs, judged again for direction agreement
and Subtask 11's verdict on the LLM score (NeurIPS Subtask 20; AIOS
`docs/METRICS.md`, "Agreement between the judges" and "Subtask 11's
verdict on each score"). No model or kernel run: `rejudge.py` reads each
results file and adds the judge's record. Result: AIOS
`docs/DEV_STATUS.md`, Subtask 20.

- **Inputs** (Cerebrum `results/`): `pilot_v1_hetero` (Subtask 11,
  1,080 v1 answers), `pilot_v1_amem` (Subtask 17, 180 v1 answers),
  `bench_v2_smoke_amem` (Subtask 17, 90 v2 integration probes).
- **Code**: `rejudge.py` as committed in Cerebrum `26d2bc5`; the files
  were produced from the working tree just before that commit (each
  records `harness_commit` `7d19bf4-dirty`), whose `rejudge.py` and
  judging path are the committed ones.

## `claude-sonnet-5.5/`

- `rejudge.py --judge claude-sonnet-5.5` with `--root results` and
  `--output results/s20_rejudge/claude-sonnet-5.5` over the three runs
  (each file's `experiment_metadata.rejudge` records the judge,
  `repeats` 1, the prompt and the decoding): the second judge at its k
  (1), all 1,350 answers in one Message
  Batches submission, `msgbatch_01UpXQs4GZ1aWZ5FSwGRTHJb` (submitted
  2026-11-19 18:11:37 UTC, ended 18:15:39; 1,350 succeeded, none
  failed). Model, decoding and credentials as in
  `results/judge_reliability_s20/PROVENANCE.md`.
- The stored scores (the hybrid) are kept; the judge's record is added
  beside them (`judges["claude-sonnet-5.5"]`: the LLM scores, the
  keyword scores, the hybrid, the batch and its times, the tokens). A
  v2 trial carries its integration probe's record on the probe and on
  the trial.
- Tokens: 2,261,458 in, 538,502 out; about $4.95 at the Batch API's
  rates ($1 / $5 per million tokens in / out).
- Readings so far: Subtask 11's verdict on this judge's LLM score is
  GO (`pilot_analysis --score llm --judge claude-sonnet-5.5`); every
  paired difference (`judge_reliability directions`) is computed.

## `pilot_report/`

Subtask 11's verdict on each score (AIOS `docs/METRICS.md`, "Subtask
11's verdict on each score"), rendered at Cerebrum `fae6ce1`:

- `hybrid.md` / `.json`: `pilot_analysis results/pilot_v1_hetero
  --score hybrid` (the stored scores, as registered);
- `keyword.md` / `.json`: `--score keyword` (recomputed from each
  record; no stored hybrid score is inconsistent with it);
- `llm_claude-sonnet-5.5.md` / `.json`: `pilot_analysis
  results/s20_rejudge/claude-sonnet-5.5/pilot_v1_hetero --score llm
  --judge claude-sonnet-5.5`.

The hybrid and keyword renderings from the re-judged tree are
byte-identical to these. Cerebrum
`tests/agents/test_metrics.py::test_the_pilot_report_reproduces_subtask_11_on_each_score`
regenerates all three from that tree's records, trimmed
(`tests/agents/fixtures/pilot_runs/`).

## Open

- `gpt-5.4/`: the primary judge's re-judge at its k, waiting on its
  Azure deployment (refused with HTTP 403 from this machine on
  2026-11-19); then the direction agreement between the two judges.

Every file here was scanned by AIOS `scripts/archive_artifacts.py
--check`: none holds a key value.

## Archive

`../repo-artifacts/Cerebrum/s20_rejudge/claude-sonnet-5.5/` (the
re-judged results files, `SHA256SUMS`), copied through AIOS
`scripts/archive_artifacts.py`: 45 files scanned, none holds a key
value. Committed here: this file and `pilot_report/`.
