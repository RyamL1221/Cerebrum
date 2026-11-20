# decision_functional_s20: provenance

Amendment 10's functional check of the decision probe, in-house cells
(NeurIPS Subtask 20; AIOS `docs/BENCHMARK_V2.md`, Amendment 10, "The
functional check"). Judge-free. Result: AIOS `docs/DEV_STATUS.md`,
Subtask 20, and Amendment 10, "The functional check's result".

- **Run**: AIOS `scripts/run_bench_v2.sh`, `MODE=decision`, Qwen
  (`qwen2.5:7b` on Ollama), `pilot_v2` users 0 to 4 (`users_v2`
  revision 4, sha256 `64d5e4fc…`), H = 0, `--no-judge`, `PHASES="kinh
  agent kinh_ns agent_ns"`, `METHODS="kernel_shared replicated_inhouse
  native_inhouse"`, `RUN_PREFIX=d20a`. 2026-11-19 13:46 to 15:19 EST.
- **Code**: every cell records harness `87e5aa0` and kernel `849fd09`
  (clean trees).
- **Cells** (13): h0 and no_memory in the three loci; writer_scoped in
  the kernel and replicated loci; wrong_user (`--heterogeneity 0
  --fault wrong_user`) in the three loci; no_supersession in the kernel
  and replicated loci (the `_ns` phases). Every trial finished (65 of
  65), no decision turn had an error; the driver's checks passed
  (stored conversation turns 0, guard warnings 0, kernel memory ops in
  the agent phases 0).
- **Mem0 cells**: not run (Mem0's extraction uses the Azure deployment,
  refused with HTTP 403 from this machine on 2026-11-19).

## Result

`bench_v2_analysis results/decision_functional_s20 --no-criteria`
(`analysis.md` / `analysis.json`, rendered at Cerebrum `fae6ce1`, which
adds the picks by option kind and letter):

| Criterion | Met | Evidence |
|---|---|---|
| D1 full system accuracy >= 0.6 | yes | 23 of 30 over 3 cells |
| D2 no_memory accuracy in [0.10, 0.45] | **no** | 0 of 30 over 3 cells |
| D3 no_supersession more stale | yes | 10 of 20 vs 0 of 20 |
| D4 writer_scoped revoked on echo d1 | yes | 2 of 4 vs 0 of 4 |
| D5 wrong_user foreign, none in the kernel | yes | 6 of 20 vs 0 of 10 |

D2 is a deviation: the three no_memory cells gave the same ten answers
(no memory, greedy decoding), so they are one sample of ten items; 0 of
10 has probability 0.056 under uniform guessing. The no-memory check
over all 150 users (Amendment 10, added after D2 failed) is
`results/decision_nomemory150_s20/`.

Per cell (items correct of 10): kernel h0 10, no_memory 0,
writer_scoped 9 (1 revoked), wrong_user 10, no_supersession 5 (5
stale); replicated h0 10, no_memory 0, writer_scoped 9 (1 revoked),
wrong_user 7 (3 foreign), no_supersession 5 (5 stale); native h0 3 (7
stale), no_memory 0, wrong_user 6 (3 foreign, 1 stale).

Every stale, revoked and foreign error of a cell with memory had the
picked option's value in the block (`options_in_block`; 26 of 26), so
D3 to D5 rest on what the block held. The no-memory cells' errors had
none (their blocks are empty).

## Archive

`../repo-artifacts/Cerebrum/decision_functional_s20_inhouse/` (results,
kernel and cell logs, the driver's log, `SHA256SUMS`), copied by the
driver through AIOS `scripts/archive_artifacts.py`: 33 files scanned,
none holds a key value.

Cerebrum
`tests/agents/test_decision_probe.py::test_the_v2_analysis_reproduces_the_recorded_decision_runs`
regenerates `analysis.md` and `analysis.json` from these records,
trimmed to the fields the analysis reads
(`tests/agents/fixtures/decision_runs/`).
