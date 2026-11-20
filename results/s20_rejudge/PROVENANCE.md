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
  judging path are the committed ones. The `gpt-5.4/` files,
  `directions.md` and `pilot_report/llm_gpt-5.4.md` were produced at
  Cerebrum `6e912d1` (each file records it, clean), through a kernel at
  AIOS `d49afc9`.

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
- Readings: Subtask 11's verdict on this judge's LLM score is GO
  (`pilot_analysis --score llm --judge claude-sonnet-5.5`); its paired
  differences are in `directions.md`.

## `gpt-5.4/`

- `rejudge.py --judge gpt-5.4 --repeats 1 --workers 8` with `--root
  results` and `--output results/s20_rejudge/gpt-5.4`, one invocation
  per results file (45: `rejudge.py` writes its outputs after its last
  input, so a file at a time keeps each finished file on disk). The
  primary judge at its k (1), through the kernel's `/query`; model,
  decoding and kernel as in
  `results/judge_reliability_s20/PROVENANCE.md`. One pass, the files in
  path order, 2026-11-20 17:38:59 to 18:00:15 UTC.
- 1,350 answers judged, each at its first attempt, none failed. The
  judge's record is added (`judges["gpt-5.4"]`) and, as before Subtask
  20, the trial's three stored scores are rewritten with the new
  hybrid.
- Tokens: 1,370,502 in, 284,410 out; about $7.69 at $2.50 / $15 per
  million tokens in / out (OpenAI's list price for GPT-5.4; Azure's
  own price was not read).
- A reading, not a registered measure: against the hybrid scores the
  pilot stored (the same judge, 2026-11-07 and 08), the new hybrid is
  the same for Profile on 893 of 1,080 answers (0.83), Task 1,077
  (1.00), Integration 973 (0.90); no mean moved by more than 0.05.

## `directions.md` / `.json`

`judge_reliability directions` over the two judges' trees of the three
runs (`--integration-only bench_v2_smoke_amem`), each judge at k = 1.
Differences the two judges give the same direction: `pilot_v1_hetero`
126 of 144, `pilot_v1_amem` 13 of 18, `bench_v2_smoke_amem` 0 of 2.
Among those where either judge's 95% interval excludes 0: 104 of 104,
12 of 12, and none to count. Every difference at H = 1 or H = 2 and
every H2 − H0 difference has one direction under both judges (108 of
108 and 12 of 12). The 25 disagreements are all at H = 0: both
intervals include 0 in each, no mean is further than 0.24 from zero,
and in 16 one judge's mean is exactly 0 (a zero mean is its own sign).

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

- `llm_gpt-5.4.md` / `.json`: `pilot_analysis
  results/s20_rejudge/gpt-5.4/pilot_v1_hetero --score llm --judge
  gpt-5.4`, rendered at Cerebrum `6e912d1`: **GO**. Qwen: H = 2 pooled
  kernel − replicated, Profile +0.95 [+0.48, +1.42], Integration +0.97
  [+0.54, +1.40]; H2 − H0, Profile +1.00 [+0.51, +1.49], Integration
  +0.93 [+0.47, +1.39]. GPT-4o: +1.18 [+0.58, +1.79], +1.20 [+0.60,
  +1.80]; +1.15 [+0.52, +1.78], +1.13 [+0.49, +1.77].

The hybrid and keyword renderings from the second judge's re-judged
tree are byte-identical to these (the primary judge's tree holds new
hybrid scores). Cerebrum
`tests/agents/test_metrics.py::test_the_pilot_report_reproduces_subtask_11_on_each_score`
regenerates all three from that tree's records, trimmed
(`tests/agents/fixtures/pilot_runs/`).

Every file here was scanned by AIOS `scripts/archive_artifacts.py
--check`: none holds a key value.

## Archive

`../repo-artifacts/Cerebrum/s20_rejudge/` (`claude-sonnet-5.5/` and
`gpt-5.4/`, the re-judged results files; the primary judge's run log
and its per-file script; `directions.json`; `SHA256SUMS`), copied
through AIOS `scripts/archive_artifacts.py` in two passes: 45 files
scanned, then 48, none holds a key value. The kernel's log is with the
reliability study's archive. Committed here: this file,
`directions.md` / `.json` and `pilot_report/`.
