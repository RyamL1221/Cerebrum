# Harness Invocation and Output Schema for Trial Batches

**Track:** threshold-search
**Goal:** Nail down the exact, literal CLI invocation to run a fixed batch of
`kernel_shared_tuned` trials against one model, and confirm how to read back the
judge scores afterward. This is the concrete "unit of work" the orchestration
script (Subtask 4) will shell out to or call repeatedly.

> **Investigation only.** No Cerebrum or AIOS code was modified. The only file
> touched was the AIOS `aios/config/config.yaml` (gating toggles for the live
> test), restored to baseline afterward — same protocol as Subtask 1.

---

## 1. Exact, literal command line for N trials of `kernel_shared_tuned`

The command that was **actually executed** end-to-end (from the Cerebrum repo
root, using its venv):

```bash
.venv/bin/python benchmarks/shared_memory/run_evaluation.py \
    --trials 2 \
    --method kernel_shared_tuned \
    --assistant-model "qwen2.5:7b:ollama" \
    --judge-model "qwen2.5:7b:ollama" \
    --kernel-url http://localhost:8000 \
    --output /tmp/threshold_invocation_test/ \
    --run-id st3probe \
    --csv
```

Exit status: **0** (success). Both trials completed, 0 failed.

Generalized for the search's unit of work (swap in the per-iteration model,
trial count, and a unique output dir + run-id):

```bash
python benchmarks/shared_memory/run_evaluation.py \
    --trials <N> \
    --method kernel_shared_tuned \
    --assistant-model "<name>:<backend>" \
    --judge-model "gpt-5.4:azure" \
    --kernel-url http://localhost:8000 \
    --output <unique_dir>/ \
    --run-id <unique_run_id> \
    --csv
```

### Flag semantics (cited)

- `--method kernel_shared_tuned` selects the method. `--condition` must stay
  **unset** (it defaults to `None`, `run_evaluation.py:161`). `run()` dispatches
  to `_run_method()` only when `self.condition is None`
  (`run_evaluation.py:587` guard, `:593` dispatch); a set `--condition` diverts
  to the legacy
  phase1/phase2 path and would ignore `--method`.
- `--trials <N>` → `range(self.trials)` trial loop (`run_evaluation.py:779`,
  `:803`).
- `--assistant-model` / `--judge-model` pin the models (see §3).
- `--kernel-url` overrides the kernel URL (CLI arg > config default,
  `run_evaluation.py:277-279`).
- `--output <dir>` sets the output directory; `--csv` also writes a CSV.
- `--run-id <id>` namespaces the synthetic `user_id`s to avoid cross-run memory
  pollution (`run_evaluation.py:216-225`); when omitted a random UUID suffix is
  used (see Subtask 2's findings).

---

## 2. Pre-flight gating check fires for `kernel_shared_tuned` with NO extra flag

**Confirmed, by both code and a live run.** `_run_method()` runs the pre-flight
for any method in `_GATING_VERIFIED_METHODS` — which includes
`kernel_shared_tuned` (`run_evaluation.py:83-87`, entry at :85) — via
`if method_name in _GATING_VERIFIED_METHODS: self._verify_gating_status(method_name)`
(`run_evaluation.py:766-767`). No additional flag enables it; selecting the
method is sufficient.

Live proof from the executed run's stdout:

```
[INFO] __main__: Running method 'kernel_shared_tuned'.
[INFO] __main__: Pre-flight gating check passed for 'kernel_shared_tuned':
       adaptive_policy_enabled=False, static_thresholds_enabled=True.
```

The check is **verify-and-raise**: it issues `GET /memory/gating_status` once and
raises (zero trials run) if the live kernel state does not match the tier's
expectation (`_GATING_EXPECTATIONS["kernel_shared_tuned"]` =
`static_thresholds_enabled: True`, `adaptive_policy_enabled: False`,
`run_evaluation.py:98-101`). It does **not** configure the kernel — the operator
must set the kernel config and restart first (see §5).

---

## 3. Model flag semantics and non-GPT prerequisites

**`--assistant-model` / `--judge-model` accept a `"<name>:<backend>"` string**,
parsed by `_parse_model_arg` (`run_evaluation.py:108`): it `rsplit(":", 1)`s into
`[{"name": <name>, "backend": <backend>}]`. The name embeds its own colon fine
(e.g. `"qwen2.5:7b:ollama"` → `{"name": "qwen2.5:7b", "backend": "ollama"}`).

This list is threaded `assistant_llms` → `AssistantAgent(llms=...)` →
`llm_chat(..., llms=self.llms)` (`assistant_agent/agent.py:53-59`), i.e. the
model is selected **per query**. No prior `/user/select/llms` call is needed from
the harness.

**The `name` must match a model configured in the AIOS kernel's
`aios/config/config.yaml` under `llms.models`.** The currently-active entries are:

| Config entry | `--*-model` string |
|--------------|--------------------|
| `gpt-5.4` / `azure` | `gpt-5.4:azure` |
| `gpt-4o` / `azure` | `gpt-4o:azure` |
| `llama3.1:8b` / `ollama` | `llama3.1:8b:ollama` |
| `qwen2.5:7b` / `ollama` | `qwen2.5:7b:ollama` |

### Mapping the three target models

- **GPT-4o → `gpt-4o:azure`.** The `openai`-backend `gpt-4o` entry is commented
  out; the **azure** entry is the active one (`config.yaml:36-37`). Use `azure`,
  not `openai`.
- **Llama-3.1:8B → `llama3.1:8b:ollama`** (`config.yaml:57-58`).
- **Qwen-2.5:7B → `qwen2.5:7b:ollama`** (`config.yaml:61-62`).

### Prerequisites

- **Non-GPT models (Llama/Qwen) require a running Ollama server** at
  `http://localhost:11434` (the `hostname` in their config entries). This was
  confirmed up in Subtask 1's environment and is what the live run below used.
- **GPT-4o / GPT-5.4 (azure) require valid Azure credentials** in the kernel
  environment. The live run intentionally used the local `qwen2.5:7b` for both
  assistant and judge to avoid any external-credential dependency for this probe;
  the reporting run will use `gpt-5.4:azure` as judge per the default benchmark
  command.

---

## 4. Output artifact schema and the exact judge-score field(s)

A `--method` run writes two files into `--output`:

- **`results_<method>.json`** — here `results_kernel_shared_tuned.json`
  (`run_evaluation.py:823`, `output_filename = f"results_{self.method}.json"`).
  Full `ExperimentResults.model_dump()`.
- **`results.csv`** — fixed name (`results.py:125`), one row per trial.

### Where the judge score lives

The GPT-5.4 (or, here, qwen) judge produces a `JudgeScores` with three integer
(1–5) fields — `profile_usage_score`, `task_usage_score`, `integration_score`
(`judge.py:26-30`; HybridJudge averages keyword + LLM components,
`judge.py:443-445`). These are copied verbatim onto `TrialResult`
(`run_evaluation.py:556-558`; model fields at `models.py:160-162`,
each `Optional[int]`).

**JSON path to a score:**
`conditions[i].trials[j].profile_usage_score` (and `.task_usage_score`,
`.integration_score`). The run's metadata also carries gating provenance at
`experiment_metadata.gating_status_by_method["kernel_shared_tuned"]`.

**CSV columns** (in order, `results.py:126-142`): `condition, method,
retrieved_context_count, trial_index, profile_usage_score, task_usage_score,
integration_score, memory_total, memory_shared, memory_private,
shared_memory_count, cross_agent_found, latency_seconds, query, response`.
(Note: `token_usage` is in the JSON per trial but **not** in the CSV.)

### For judge-score averaging (what the orchestration script should extract)

Parse the three per-trial integer fields above. Per Subtask, average whichever
the search optimizes for. The harness's own per-trial reward is the **mean of
the three non-null scores** (`run_evaluation.py:462-469`, the `reward_value`
computation) — the orchestration script can either reuse that definition or
average a single dimension. The `ConditionSummary` in the JSON also pre-computes
per-metric `mean`/`std` (`results.py:84-92`), so a batch mean is available
without re-parsing every trial if the whole-batch mean suffices.

---

## 5. Real minimal invocation — captured evidence

**Kernel configuration for the test** (set on the AIOS side, then a full process
restart per Subtask 1's finding that `/core/refresh` does not apply these):
`memory.adaptive_policy.enabled: false` and `memory.static_thresholds.enabled:
true`. Verified live before running:

```
GET /memory/gating_status →
{"adaptive_policy_enabled":false,"static_thresholds_enabled":true,
 "static_thresholds_config":{"enabled":true,
   "novelty_threshold":{"default":0.7,"overrides":[]},
   "similarity_threshold":{"default":0.7,"overrides":[]},
   "redundancy_threshold":{"default":0.7,"overrides":[]}}}
```

**Command:** the §1 command. **Exit status:** 0.

**Resulting files:**
```
/tmp/threshold_invocation_test/results_kernel_shared_tuned.json
/tmp/threshold_invocation_test/results.csv
```

**Per-trial results (from the JSON):**
```
trial_index=0 profile=5 task=5 integration=5 failed=False
              token_usage={'prompt_tokens':322,'completion_tokens':582,'total_tokens':904}
trial_index=1 profile=5 task=5 integration=5 failed=False
              token_usage={'prompt_tokens':316,'completion_tokens':223,'total_tokens':539}
```

**CSV header + first data row (abbreviated):**
```
condition,method,retrieved_context_count,trial_index,profile_usage_score,task_usage_score,integration_score,memory_total,memory_shared,memory_private,shared_memory_count,cross_agent_found,latency_seconds,query,response
kernel_shared_tuned,kernel_shared_tuned,,0,5,5,5,0,0,0,2,True,27.39,"How should I prioritize my current tasks...","Given your current tasks..."
```

**Stdout summary line:**
```
kernel_shared_tuned   Profile 5.000  Task 5.000  Integration 5.000  Latency 19.751  Total 2  Failed 0
```

(Copies of the two artifacts are preserved at
`/tmp/threshold_reload_evidence/st3_results.csv` and
`/tmp/threshold_reload_evidence/st3_results_kernel_shared_tuned.json`.)

> Note: this minimal probe used qwen2.5:7b, which happily scored 5/5/5 on 2
> trials — that is not a quality claim, just proof the path runs end-to-end and
> produces the expected artifact/schema. Subtask 6 does the fuller dry run.

---

## Summary for the orchestration script (Subtask 4)

- **Unit of work:** one `run_evaluation.py --method kernel_shared_tuned` process
  per (model, batch), with a unique `--output` dir and `--run-id`.
- **Model selection:** `--assistant-model "<name>:<backend>"` where `<name>`
  matches an AIOS-configured model. GPT-4o = `gpt-4o:azure`, Llama = 
  `llama3.1:8b:ollama`, Qwen = `qwen2.5:7b:ollama`. Ollama up for the latter two.
- **Gating pre-flight:** fires automatically for `kernel_shared_tuned`; the
  kernel must already be running with static-on/adaptive-off (config edit + full
  restart — not `/core/refresh`), or the run raises with zero trials.
- **Read-back:** parse `results_kernel_shared_tuned.json` →
  `conditions[0].trials[*].{profile_usage_score,task_usage_score,integration_score}`
  (or the CSV columns of the same names), and average per the search objective.
