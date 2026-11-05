# Shared Memory Benchmark — Personalization Baselines

## Overview

Compares four personalization methods using the same synthetic trial data,
HybridJudge scoring, and qwen2.5:7b as the assistant model with GPT-5.4 as
the judge.

## Methods

| # | Method | Description | Kernel Config |
|---|--------|-------------|---------------|
| 1 | naive_concat | Full context concatenation into prompt | auto_inject: false, auto_extract: false |
| 2 | vanilla_rag | TF-IDF retrieval over context chunks | auto_inject: false, auto_extract: false |
| 3 | kernel_private | The kernel pipeline of method 4 with sharing off: the agents write private memories, so the assistant sees none | auto_inject: true, auto_extract: true |
| 4 | kernel_shared | AIOS kernel shared memory (auto_inject) | auto_inject: true, auto_extract: true |

## Fixed users and paired comparisons (NeurIPS Subtask 9)

Reported results use the fixed dataset `data/users_v1.jsonl` (150 users
generated once with `synth.py`'s prompts, GPT-4o, seed 20261104; the
header record holds the generation details). `--dataset users_v1` runs
all 150, `--dataset pilot_v1` the first 30; trial `i` is user `i`, so
every cell scores the same users and two cells pair by trial index.
`--dataset random` (the default) generates each trial's user and is
never used for reported results. Compare two cells with
`python -m benchmarks.shared_memory.compare <a> <b>` (paired t,
Wilcoxon, 95% CI, TOST ±0.25); the pilot table comes from
`python -m benchmarks.shared_memory.pilot_report results/pilot_v1`.
Never edit a dataset file; make a new version (`dataset.py generate`).

Writers validate their extraction against the profile / task schema and
retry twice; a writer that still fails stores nothing, and its trial is
recorded with `writer_failed` and not scored. The judge retries three
times, then fails the trial (no keyword-only scores).

## Run Commands

Run sequentially in this order. Restart the kernel between each method to
clear the memory store.

```bash
# ============================================================
# 1. Naive Concat
# ============================================================
# Kernel config: auto_inject: false, auto_extract: false
# Restart kernel, then run:
python benchmarks/shared_memory/run_evaluation.py --trials 150 --output results/naive_concat/ --method naive_concat --assistant-model "qwen2.5:7b:ollama" --judge-model "gpt-5.4:openai" --csv

# ============================================================
# 2. Vanilla RAG
# ============================================================
# Kernel config: auto_inject: false, auto_extract: false
# Restart kernel, then run:
python benchmarks/shared_memory/run_evaluation.py --trials 150 --output results/vanilla_rag/ --method vanilla_rag --assistant-model "qwen2.5:7b:ollama" --judge-model "gpt-5.4:openai" --csv

# ============================================================
# 3. Kernel Private
# ============================================================
# Kernel config: auto_inject: true, auto_extract: true
# Restart kernel, then run:
python benchmarks/shared_memory/run_evaluation.py --trials 150 --output results/kernel_private/ --method kernel_private --assistant-model "qwen2.5:7b:ollama" --judge-model "gpt-5.4:openai" --csv

# ============================================================
# 4. Kernel Shared (AIOS shared memory system)
# ============================================================
# Kernel config: auto_inject: true, auto_extract: true
# Restart kernel, then run:
python benchmarks/shared_memory/run_evaluation.py --trials 150 --output results/kernel_shared/ --method kernel_shared --assistant-model "qwen2.5:7b:ollama" --judge-model "gpt-5.4:openai" --csv
```

## Kernel Config Changes

In the AIOS kernel's `config.yaml`, toggle these fields under `memory:`:

```yaml
# For methods 1-2 (naive_concat, vanilla_rag):
auto_extract: false
auto_inject: false

# For methods 3-4 (kernel_private, kernel_shared):
auto_extract: true
auto_inject: true
```

All other config fields stay the same across all runs.

## Condition names

`kernel_private` was called `mem0_default` until Subtask 4 of the
NeurIPS plan; it was always the kernel pipeline with sharing off, not
Mem0's own behavior. The old name still works as a deprecated alias
with a warning (`conditions.py`, `CONDITION_ALIASES`), and readers find
results directories written under it (`conditions.results_path`).

## Judge prompt

`judge.py` holds the judge prompt. `JUDGE_PROMPT_VERSION` and
`judge_prompt_sha256()` are recorded in every results file's
`experiment_metadata`; files without them used version 1. Version 2
names no memory mechanism and drops the plausible-actions section.
`rejudge.py` re-scores the stored responses of a results file with the
current prompt, making judge calls only.

## Notes

- Assistant model: qwen2.5:7b via Ollama (the model being evaluated)
- Judge model: GPT-5.4 via Azure OpenAI (scores responses on 1-5 rubric)
- Restart the kernel between each method to clear the memory store
- Results are written to `results/<method_name>/`
- Each run takes approximately 80-90 minutes (150 trials × ~35s/trial)
