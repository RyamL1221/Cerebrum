# decision_functional_s20: provenance

Amendment 10's functional check of the decision probe, on in-house and
on Mem0 (NeurIPS Subtask 20; AIOS `docs/BENCHMARK_V2.md`, Amendment
10, "The functional check"). Judge-free. Result: AIOS
`docs/DEV_STATUS.md`, Subtask 20, and Amendment 10, "The functional
check's result" (in-house) and "The functional check's Mem0 cells".

- **Runs**: AIOS `scripts/run_bench_v2.sh`, `MODE=decision`, Qwen
  (`qwen2.5:7b` on Ollama), `pilot_v2` users 0 to 4 (`users_v2`
  revision 4, sha256 `64d5e4fc…`), H = 0, `--no-judge`, in two runs
  into this one directory:
  - in-house: `PHASES="kinh agent kinh_ns agent_ns"`,
    `METHODS="kernel_shared replicated_inhouse native_inhouse"`,
    `RUN_PREFIX=d20a`, 2026-11-19 13:46 to 15:19 EST (`driver.log`);
  - Mem0: `PHASES="kmem0 agent kmem0_ns agent_ns"`,
    `METHODS="kernel_shared replicated_mem0 native_mem0"`,
    `RUN_PREFIX=d20m`, 2026-11-20 13:07 to 15:31 EST
    (`driver_mem0.log`). It waited for the Azure deployment, which
    Mem0's extraction uses: from 2026-11-19 every call was refused
    (HTTP 403), because a second VPN held this machine's default route.
- **Code**: the in-house cells record harness `87e5aa0` and kernel
  `849fd09`; the Mem0 cells harness `968029a` and kernel `d49afc9`
  (clean trees in both runs).
- **Cells** (13 per backend, 26): h0 and no_memory in the three loci;
  writer_scoped in the kernel and replicated loci; wrong_user
  (`--heterogeneity 0 --fault wrong_user`) in the three loci;
  no_supersession in the kernel and replicated loci (the `_ns`
  phases). Every trial finished (130 of 130), no decision turn had an
  error; both runs' driver checks passed (stored conversation turns 0,
  guard warnings 0, kernel memory ops in the agent phases 0).
- **Mem0's extraction** (Azure `gpt-4o`, summed over the Mem0 cells'
  trials): 6,982,522 tokens in, 55,668 out, 888 calls; about $18.01 at
  `prices.yaml`'s $2.50 / $10 per million tokens.

## Result

`bench_v2_analysis results/decision_functional_s20 --no-criteria`
(`analysis.md` / `analysis.json`), rendered at Cerebrum `968029a` over
the 26 cells. The in-house rendering of 2026-11-19 (13 cells, at
`fae6ce1`) is in `analysis.md`'s history (Cerebrum `3716e02`).

| Criterion | Met | Both backends | In-house alone (2026-11-19) |
|---|---|---|---|
| D1 full system accuracy >= 0.6 | yes | 47 of 60 over 6 cells | 23 of 30 over 3 cells |
| D2 no_memory accuracy in [0.10, 0.45] | **no** | 0 of 60 over 6 cells | 0 of 30 over 3 cells |
| D3 no_supersession more stale | yes | 22 of 40 vs 0 of 40 | 10 of 20 vs 0 of 20 |
| D4 writer_scoped revoked on echo d1 | yes | 4 of 8 vs 0 of 8 | 2 of 4 vs 0 of 4 |
| D5 wrong_user foreign, none in the kernel | yes | 10 of 40 vs 0 of 20 | 6 of 20 vs 0 of 10 |

D2 is a deviation: the six no_memory cells (three loci, two backends)
gave the same ten answers, DDCACBBDAB (no memory, greedy decoding), as
did users 0 to 4 of the 150-user no-memory check, so they are one
sample of ten items; 0 of 10 has probability 0.056 under uniform
guessing. The no-memory check over all 150 users (Amendment 10, added
after D2 failed) is `results/decision_nomemory150_s20/`.

Per cell (items correct of 10), in-house: kernel h0 10, no_memory 0,
writer_scoped 9 (1 revoked), wrong_user 10, no_supersession 5 (5
stale); replicated h0 10, no_memory 0, writer_scoped 9 (1 revoked),
wrong_user 7 (3 foreign), no_supersession 5 (5 stale); native h0 3 (7
stale), no_memory 0, wrong_user 6 (3 foreign, 1 stale).

Mem0: kernel h0 10, no_memory 0, writer_scoped 9 (1 revoked),
wrong_user 10, no_supersession 4 (6 stale); replicated h0 10,
no_memory 0, writer_scoped 9 (1 revoked), wrong_user 6 (3 foreign, 1
stale), no_supersession 4 (6 stale); native h0 4 (3 stale, 2 foreign,
1 revoked), no_memory 0, wrong_user 1 (6 stale, 2 revoked, 1 foreign).

What the blocks held (`options_in_block`, the scorer's matcher):
- in-house: every stale, revoked and foreign error of a cell with
  memory had the picked option's value in the block (26 of 26), so D3
  to D5 rest on what the block held;
- Mem0: 19 of 33 errors. The kernel's and replicated Mem0 blocks held
  the correct option's value on every item (80 of 80); 2 of replicated
  `wrong_user`'s 4 errors (a foreign and a stale pick) were of a value
  not in the block;
- native Mem0: the matcher found the correct option's value in none of
  its 20 blocks with memory (the native consumer's own search at its k
  of 10, over the facts Mem0's extraction stored), so its 5 right
  answers were guesses, and 12 of its 15 errors were of a value not in
  the block: guesses too, by `METRICS.md`'s reading, which no item's
  error kind names as a recency, deletion or identity failure. Under
  `wrong_user` its blocks did hold user i − 1's rows (users 1 to 4: 3
  to 7 of 9 or 10): the identity failure is in the blocks, and the
  items do not register it;
- of the 10 foreign errors that make D5, 8 had the foreign value in
  the block; the no-memory cells' errors had none (their blocks are
  empty).

Qwen answered alike wherever the prompt was the same: over the 26
cells, the 236 pairs of answers to one item with the same block text
name the same letter. 86 of them have a non-empty block, each pair
within one backend; the other 150 are the no_memory cells' empty
blocks (90 of them across the two backends).

## Archive

- in-house: `../repo-artifacts/Cerebrum/decision_functional_s20_inhouse/`
  (results, kernel and cell logs, the driver's log, `SHA256SUMS`): 33
  files scanned, none holds a key value;
- both: `../repo-artifacts/Cerebrum/decision_functional_s20_mem0/`
  (this directory at the Mem0 run's end: both halves' results, kernel
  and cell logs and both driver logs, `SHA256SUMS`): 69 files scanned,
  none holds a key value.

Each copied by the driver through AIOS `scripts/archive_artifacts.py`.

Cerebrum
`tests/agents/test_decision_probe.py::test_the_v2_analysis_reproduces_the_recorded_decision_runs`
regenerates `analysis.md` and `analysis.json` from these records,
trimmed to the fields the analysis reads
(`tests/agents/fixtures/decision_runs/`, rebuilt on 2026-11-20 with the
Mem0 cells).
