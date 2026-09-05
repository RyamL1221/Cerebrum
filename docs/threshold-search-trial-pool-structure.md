# Trial Pool Structure and Disjointness Options for the Threshold Search

**Track:** threshold-search (offline static-threshold search + reporting runs)
**Question:** How does the Cerebrum shared-memory harness select which
question/task instances a trial run draws from — a fixed reused pool, a
seed/subset/offset mechanism, or fresh generation per run? And can the search's
~360 trials be kept strictly disjoint from the eventual ~150-trial/model
`kernel_shared_tuned` reporting run?

> **Investigation only. No Cerebrum or AIOS code was modified.** All findings
> below are cited to specific files and lines in the live repo.

---

## 1. Fixed pool vs. seeded subset vs. fresh generation

**Answer: FRESH GENERATION per trial, via live LLM calls. There is no fixed
pool, no dataset file, and no random seed.**

Each trial's data (profile, task context, plausible actions, vague follow-up
query) is produced at run time by `SyntheticDataGenerator` through
`llm_chat` / `llm_chat_with_json_output` SDK calls:

- `benchmarks/shared_memory/synth.py:464` —
  `generate_trial_data(self, trial_index)` orchestrates four LLM calls:
  `generate_profile` (`synth.py:116`), `generate_task_context` (`synth.py:188`),
  `generate_plausible_actions` (`synth.py:388`), `generate_vague_query`
  (`synth.py:278`). Each issues an SDK LLM call; none reads a file or dataset.
- There is **no dataset loader**. `pipeline.py` and `models.py` contain no
  `open()`, no `datasets`/`load_dataset`, no `.json`/`.csv` read, and no
  `random`/`numpy`/seed usage (grep over
  `benchmarks/shared_memory/{pipeline,models}.py` returned only comment-string
  matches, e.g. references to the kernel's `policy_trials.jsonl`, not any loader).
- `pipeline.py`'s `AgentPipeline.run_trial(...)` consumes a
  `SyntheticTrialData` object handed to it — it is purely fed by the generator
  (`pipeline.py:22-35` imports + dataclass; the pipeline holds no pool).

### `trial_index` is a prompt-flavor hint, not a content selector

`trial_index` is interpolated into the generation prompts purely "to encourage
diversity across trials":

- `synth.py:139` — profile prompt: `"Generate a realistic software developer
  profile for trial #{trial_index}..."`
- `synth.py:215` — task-context prompt: `"...for trial #{trial_index}..."`

No seed, temperature pin, or deterministic mapping ties `trial_index` to a
specific instance. The LLM is free to return different content for the same
`trial_index` on different runs.

### `run_id` affects only namespacing, not content

`SyntheticDataGenerator.__init__` sets
`self.run_id = run_id or uuid.uuid4().hex[:8]` (`synth.py:110`) — a **random**
default per run. `run_id` is used only to build the memory `user_id`:
`user_id = f"{base_name}_{self.run_id}_t{trial_index}"` (`synth.py:488`). It
isolates memory namespaces between runs; it does **not** seed or select the
question content. The `--run-id` CLI help confirms this scope
(`run_evaluation.py:216-225`: "discriminator appended to user_id for namespace
isolation … Prevents residual memories from prior runs from polluting current
run results").

---

## 2. Does `trial_id` map deterministically to a task instance?

**Answer: No. There is no `trial_id` at all — the harness identifier is
`trial_index`, and it does NOT map deterministically to a task instance.**

- The harness result model is `TrialResult` with a `trial_index: int` field
  (`models.py`; there is no `trial_id` field). The only `trial_id` references in
  `models.py` (`:146`, `:186`) describe the **kernel's** `policy_trials.jsonl`
  reward join (`reward.trial_id == trial_index`) — a kernel-side field, not a
  harness task identifier.
- Trials are always driven as `range(self.trials)`, i.e. indices `0..N-1`
  (`run_evaluation.py:779` and `:803` for `--method`; `:616` for the legacy
  `--condition` path). Every run starts at `trial_index = 0`.
- For each index, `run_single_trial` calls
  `self.generator.generate_trial_data(trial_index)` (`run_evaluation.py:384`)
  which, as shown above, generates fresh LLM content. So the same
  `trial_index` in two different runs yields **different** task instances.

Consequence: **`trial_index` is not a stable content key.** Two runs cannot be
made disjoint (or identical) by choosing index ranges, because the index does
not determine the content.

---

## 3. Pool size vs. total trial demand (360 + 450)

**Not applicable — there is no enumerable pool to size or slice.**

Because content is generated fresh from an LLM per trial (Section 1), there is
no finite corpus whose size could be compared against the demand of
~360 search trials + ~450 reporting trials (150 × 3 models). The generator can
produce an effectively unbounded number of instances; there is no
`offset`/`index`/`seed` argument to request a specific finite slice
(the full CLI surface is enumerated in Section 4).

---

## 4. Can an existing offset/seed mechanism guarantee disjointness? If not, how small is the addition?

**Answer: No existing mechanism can guarantee disjointness.** The full CLI flag
set (`build_arg_parser`, `run_evaluation.py:129-233`) is:

`--trials`, `--output`, `--csv`, `--condition`, `--method`, `--kernel-url`,
`--assistant-model`, `--judge-model`, `--run-id`, `--kernel-logs`.

There is **no `--seed`, no `--task-offset`, no `--task-index`, and no dataset
path** flag. `--run-id` only namespaces memory `user_id`s; it does not change
what questions are asked.

### Why current behavior already yields *probabilistic* disjointness (but not a guarantee)

Because every trial's content is freshly LLM-generated with a random `run_id`
and no seed, two separate runs will almost certainly produce different
profiles/tasks/queries — so search trials and reporting trials are, in
practice, drawn from different generated content. But this is a *statistical*
non-overlap, not a *guaranteed/auditable* one: nothing records the generated
questions in a way that enforces or proves disjointness, and duplicate content
across runs is possible (the LLM could coincidentally emit the same profile).

### What would need to be added (decision deferred to Subtask 4)

Two viable shapes, both small; **the choice is Subtask 4's, not made here:**

1. **Seed-based (small, ~a few lines):** add a `--task-seed` CLI flag, thread it
   into `SyntheticDataGenerator.__init__`, and pin the LLM sampling (e.g. seed +
   `temperature=0` where the backend supports it). Disjointness would then be
   "different seed ranges → different content," but LLM seeding is only as
   reliable as the backend's determinism — so this gives reproducibility more
   than a hard disjointness guarantee.
2. **Frozen-corpus (small-to-moderate):** generate the questions once, persist
   them to a JSON file, and add a `--task-file` + `--task-offset`/`--task-count`
   (or an explicit index range) so search draws `[0:360)` and reporting draws
   `[360:810)` from the *same frozen file*. This gives a **hard, auditable**
   disjointness guarantee (non-overlapping index slices over a fixed list) and
   is the only option that can *prove* no leakage. It is a localized addition —
   a loader branch in the generator/orchestrator plus two flags — not a harness
   redesign, since `run_single_trial` already accepts a pre-built `trial_data`
   parameter (`run_evaluation.py:382` is the `if trial_data is None:` branch;
   line 384 is the fallback generate call — so an externally-supplied instance
   path already exists).

Either way the addition is confined to `synth.py` + a couple of
`run_evaluation.py` CLI/plumbing lines. **Recommendation to carry into Subtask 4:
the frozen-corpus + index-slice option, because it is the only one that
*guarantees* (rather than merely probabilistically achieves) the master prompt's
"search trials must never overlap reporting trials" requirement.**

---

## 5. `static_thresholds.enabled` / `adaptive_policy.enabled` interaction for `kernel_shared_tuned`

**Answer: For `kernel_shared_tuned`, the kernel must have BOTH
`static_thresholds.enabled = true` AND `adaptive_policy.enabled = false`. These
are two independent server-side config toggles; the harness VERIFIES both but
does NOT set them.**

The tier's required gating state is declared in `_GATING_EXPECTATIONS`
(`run_evaluation.py:93-101`, the `kernel_shared_tuned` entry at lines 98-101):

```python
"kernel_shared_tuned": {
    "static_thresholds_enabled": True,
    "adaptive_policy_enabled": False,
},
```

- The pre-flight `_verify_gating_status(method_name)` (`run_evaluation.py:650`)
  issues `GET /memory/gating_status` once per gating method and **raises**
  (no trials run) if the live kernel state does not match — verify-and-raise,
  not auto-correct (call site `run_evaluation.py:766-767`).
- So `adaptive_policy.enabled` is a **separate config toggle the search script
  must also set** (to `false`) alongside turning `static_thresholds.enabled`
  on. It is not implied by enabling static thresholds.

### Cross-check with Subtask 1's observed kernel state

During Subtask 1, the live kernel reported **both**
`"adaptive_policy_enabled":true` and `"static_thresholds_enabled":true`
(see `docs/threshold-search-config-reload-mechanics.md`). That combination
would **fail** the `kernel_shared_tuned` pre-flight (which requires adaptive
OFF). Combined with Subtask 1's finding that `/core/refresh` does not apply
`static_thresholds` changes, the search harness must:

1. Edit the AIOS `config.yaml` to set `memory.static_thresholds.enabled: true`
   **and** `memory.adaptive_policy.enabled: false`, then
2. **Fully restart the AIOS process** (not `/core/refresh`) so the new state is
   live, before
3. The `kernel_shared_tuned` pre-flight will pass and trials will run.

---

## Summary

| Question | Finding |
|----------|---------|
| Pool vs. seed vs. fresh | **Fresh LLM generation per trial** (`synth.py:464`); no pool, no file, no seed. |
| `trial_id` → task instance deterministic? | **No** — identifier is `trial_index`; content is regenerated per run, index is a prompt-diversity hint only. |
| Pool size vs. 360 + 450 | **N/A** — no finite pool exists to size/slice. |
| Existing disjointness mechanism? | **None.** Only probabilistic non-overlap. A small addition (`--task-seed`, or a frozen corpus + `--task-offset`/index-slice) is needed; frozen-corpus is the only option that *guarantees* disjointness. Chosen in Subtask 4. |
| `kernel_shared_tuned` gating | Requires **static ON + adaptive OFF**, two independent kernel toggles; harness verifies (raises on mismatch), does not set. Search must set both server-side and restart the kernel. |
