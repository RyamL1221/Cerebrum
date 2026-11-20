# decision_nomemory150_s20: provenance

Amendment 10's no-memory check over every user (NeurIPS Subtask 20;
AIOS `docs/BENCHMARK_V2.md`, Amendment 10, "The no-memory check over
every user", added after the functional check's D2 failed and written
before this run). Judge-free. Result: Amendment 10, "The no-memory
check's result"; AIOS `docs/METRICS.md`, "The items without memory";
AIOS `docs/DEV_STATUS.md`, Subtask 20.

- **Run**: AIOS `scripts/run_bench_v2.sh` with `MODE=decision
  DATASET=users_v2 TRIALS=150 CONDITIONS=no_memory PHASES=kinh
  RUN_PREFIX=dn150`: one cell, kernel locus (`kernel_shared`), in-house,
  Qwen (`qwen2.5:7b` on Ollama), all 150 users of `users_v2` revision 4
  (sha256 `64d5e4fc…`), H = 0, `--no-judge`. 2026-11-19 17:37 to 18:55
  EST.
- **Code**: the cell records harness `692319c` and kernel `20f2447`
  (both trees without a tracked change at launch).
- 150 of 150 trials finished; 300 items scored, none with a turn error,
  `no_letter` or `multiple_letters`. The driver's checks passed (stored
  conversation turns 0, guard warnings 0).

## Result

`analysis.md` / `analysis.json`: `python -m
benchmarks.shared_memory.bench_v2_analysis
results/decision_nomemory150_s20 --no-criteria`, at Cerebrum
`fae6ce1`, the commit that added the picks (`metrics.decision_picks`,
"Picks by option kind and letter").

- Accuracy 54 of 300, 0.18 [0.14, 0.23] (95% Wilson): below chance.
- Picks by kind (count, share [95% Wilson]):

  | item | correct | stale | must_not_use | foreign |
  |---|---|---|---|---|
  | d1 | 28, 0.19 [0.13, 0.26] | 22, 0.15 [0.10, 0.21] | 47 (revoked), 0.31 [0.245, 0.39] | 53, 0.35 [0.28, 0.43] |
  | d2 | 26, 0.17 [0.12, 0.24] | 38, 0.25 [0.19, 0.33] | 27 (private), 0.18 [0.13, 0.249] | 59, 0.39 [0.32, 0.47] |
  | pooled | 54, 0.18 [0.14, 0.23] | 60, 0.20 [0.16, 0.249] | 74, 0.25 [0.20, 0.30] | 112, 0.37 [0.32, 0.43] |

- Letters picked (A/B/C/D): `d1` 33/46/38/33 (chi-square p = 0.39);
  `d2` 33/51/34/32 (p = 0.09); pooled 66/97/72/65 (p = 0.03). Correct
  letters: `d1` 37/37/34/42 (p = 0.83), `d2` 48/29/46/27 (p = 0.021),
  pooled 85/66/80/69 (p = 0.36).
- Not stated before the run, checked in reading: the foreign option is
  picked at a similar rate at each letter it sits at (A 26 of 66, B 32
  of 76, C 33 of 85, D 21 of 73).

Read by Amendment 10's rules: the correct option is the least
plausible-sounding without memory (harmless for paired comparisons;
recorded in `METRICS.md`); no cue toward the answer; `foreign` options
more plausible on both items, `d1`'s stale and `d2`'s correct and
private options less (recorded with their direction); a position lean
to B that costs accuracy (B is correct least often) and does not make
the kinds' lean. 0 of 10 at 0.18 has probability 0.14: the functional
check's D2 result fits the five users' draw; D2 stays recorded as not
met.

## Archive

`../repo-artifacts/Cerebrum/decision_nomemory150_s20/` (results,
kernel and cell logs, the driver's log, `SHA256SUMS`), copied by the
driver through AIOS `scripts/archive_artifacts.py`: 4 files scanned,
none holds a key value.

Cerebrum
`tests/agents/test_decision_probe.py::test_the_v2_analysis_reproduces_the_recorded_decision_runs`
regenerates `analysis.md` and `analysis.json` from these records,
trimmed to the fields the analysis reads
(`tests/agents/fixtures/decision_runs/`).
