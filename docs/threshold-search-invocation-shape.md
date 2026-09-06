# Full-search invocation shape — confirmed from source

Read-only investigation of `benchmarks/shared_memory/threshold_search.py`
answering one question: to cover **all 3 thresholds × 3 models × 5 candidates ×
8 trials (= 360 trials)**, is the search **one** invocation or **N**? Every
claim below cites the actual code, not the dry-run reports (which only ever
exercised one threshold on one model at a time).

## Bottom line

**One call — but a Python function call, not a shell command.**
`threshold_search.py` has **no CLI**: no `main()`, no `if __name__ ==
"__main__"`, no `argparse`/`ArgumentParser`, and it is not registered as a
console-script entry point in `pyproject.toml`. The single call that spans
everything is `run_full_search(...)` (`threshold_search.py:1396`), invoked
programmatically (e.g. `python -c "..."` or a small driver script), because its
default `models` and `candidates` already cover all three models and the full
grid, and it internally loops all three thresholds per model.

There is **no** per-threshold or per-model command to run; splitting the search
across multiple invocations is neither required nor exposed by the code.

## Evidence

### 1. `run_full_search` spans all three models in one call

`run_full_search` (`threshold_search.py:1396`) signature defaults:

```python
def run_full_search(
    config_path, aios_repo_dir, output_root, search_run_id,
    models=DEFAULT_SEARCH_MODELS,              # all 3 models by default
    candidates=DEFAULT_CANDIDATE_GRID,         # all 5 candidates by default
    trials_per_candidate=DEFAULT_TRIALS_PER_CANDIDATE,  # 8 by default
    ...
)
```

Its body loops every model and calls `search_one_model` for each
(`threshold_search.py` ~1450–1480):

```python
for model_name in models:
    ...
    states[model_name] = search_one_model(model_name=model_name, ...)
```

So a single call iterates all of `models`.

### 2. `search_one_model` spans all three thresholds per model

`search_one_model` (`threshold_search.py:1296`) loops the fixed threshold order
and calls `search_one_threshold` for each
(`threshold_search.py` ~1355–1382):

```python
for threshold_name in _SEARCH_ORDER:      # novelty → similarity → redundancy
    ...
    winning_value, _attempts = search_one_threshold(..., threshold_name=threshold_name, ...)
    state.winners[threshold_name] = winning_value
```

`_SEARCH_ORDER` (`threshold_search.py:1014`) is exactly the three gates:
`("novelty_threshold", "similarity_threshold", "redundancy_threshold")`.

### 3. Defaults ARE used as the run's coverage, not just validation constants

- `DEFAULT_SEARCH_MODELS = ("gpt-4o", "llama3.1:8b", "qwen2.5:7b")`
  (`threshold_search.py:1027`) is the **default value of the `models`
  parameter** of `run_full_search` — so omitting `models` searches all three.
- `DEFAULT_CANDIDATE_GRID = (0.5, 0.6, 0.7, 0.8, 0.9)`
  (`threshold_search.py:1021`) is the **default of `candidates`**, threaded down
  to `search_one_model` → `search_one_threshold` — so omitting it searches all
  five per threshold.
- `DEFAULT_TRIALS_PER_CANDIDATE = 8` (`threshold_search.py:1022`) is the
  **default of `trials_per_candidate`** — 8 trials per candidate.
- `DEFAULT_MODEL_BACKENDS` (`threshold_search.py:1032`) maps each model to its
  backend (`gpt-4o→azure`, `llama3.1:8b→ollama`, `qwen2.5:7b→ollama`); used when
  `model_backends` is not supplied.

These are live defaults consumed by the search, not reference-only validation
constants. That is the code-level proof a single call covers 3×3×5×8 = 360
trials: 3 models (`DEFAULT_SEARCH_MODELS`) × 3 thresholds (`_SEARCH_ORDER`) × 5
candidates (`DEFAULT_CANDIDATE_GRID`) × 8 trials (`DEFAULT_TRIALS_PER_CANDIDATE`).

### 4. Progress/checkpoint logic assumes one continuous run (single `search_run_id`), and it also enables resume

`run_full_search` constructs **one** `ProgressLog(search_run_id, ...)`
(`threshold_search.py` ~1440) for the whole run and, when `write_final=True`
(the default), performs **exactly one** final `write_final_overrides(...)` call
only after **all** models finish (`threshold_search.py` ~1490):

```python
if write_final:
    winners_by_model = {m: s.winners for m, s in states.items()}
    write_final_overrides(config_path, winners_by_model)
```

`write_final_overrides` (`threshold_search.py:1499`) writes all nine winners
(3 models × 3 thresholds) as per-threshold wildcard-override lists in a single
config write — its docstring states it is "the ONE persisted write at the end of
`run_full_search`, never called per-candidate."

`write_candidate_config` (`threshold_search.py:272`) IS called fresh per
candidate (inside `search_one_threshold`) to stage each candidate's transient
config, but that is per-candidate config staging **within** the one run — not a
separate top-level invocation.

Resume is a first-class feature of the **same single call**: with `resume=True`
(default) `run_full_search` calls `load_progress(search_run_id, ...)`
(`threshold_search.py:1713`) to rebuild state from `attempts.jsonl`, skips
fully-completed models and already-won thresholds, and never re-runs a candidate
already on disk. So a crashed run is continued by **re-invoking the same
`run_full_search` with the same `search_run_id`** — still one logical call, not
N per-threshold/per-model commands.

## Definitive statement

**ONE call** covers all 360 trials. Because there is no CLI, it is a Python
function call. The exact minimal invocation (all defaults for models, grid,
trials, judge):

```bash
python -c '
from benchmarks.shared_memory.threshold_search import run_full_search
run_full_search(
    config_path="<AIOS repo>/aios/config/config.yaml",
    aios_repo_dir="<AIOS repo>",
    output_root="results/threshold_search_full/",
    search_run_id="full-search-360",
    kernel_url="http://localhost:8000",
    write_final=True,   # write the 9 winners to config.yaml once at the end
    resume=True,        # re-run with the same search_run_id to resume a crash
)
'
```

(Run from the Cerebrum repo root so `benchmarks.shared_memory` imports. `models`,
`candidates`, `trials_per_candidate`, and `judge_model` are omitted so the
defaults — 3 models, 5-candidate grid, 8 trials, `gpt-5.4:azure` judge — apply.)

- It is **NOT** N commands. There is no per-threshold or per-model command
  because the module exposes no CLI and `run_full_search` internally iterates
  `DEFAULT_SEARCH_MODELS` × `_SEARCH_ORDER` × `DEFAULT_CANDIDATE_GRID`.
- The dry runs called the lower-level `search_one_threshold` directly (one
  threshold, one model) to keep cost small; that is a testing entry point, not
  the shape required for the full search.
