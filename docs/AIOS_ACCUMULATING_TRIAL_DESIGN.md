# Accumulating / Evolving-Session Trial Design

Working document for the "accumulating trial" redesign of the shared-memory
benchmark: instead of each trial being a wholly independent one-shot
(fresh user, fresh task), a *session* would be one simulated user across
several coherent, evolving interactions that accumulate memory.

> **Status:** Subtask 1 (pipeline mapping) and Subtask 2 (design proposal)
> are both complete and committed together. Subtask 1 is read-only
> investigation output; Subtask 2 is a design proposal with **no
> implementation code**. Implementing the design and running the pilot are
> separate follow-up tasks.

---

## Subtask 1 — Current trial-construction pipeline (as-built)

Read-only map of how trial isolation and synthetic-data generation work
today, so the Subtask 2 design is grounded in real constraints. All paths
are in `benchmarks/shared_memory/` unless noted; the collection-name check
is in the sibling AIOS repo `aios/memory/providers/mem0.py`.

### (a) `user_id` is the SOLE isolation mechanism

Per-trial memory isolation is enforced **entirely** by a unique per-trial
`user_id`. There is no other reset point.

- **Generation.** `SyntheticDataGenerator.generate_trial_data(trial_index)`
  (`synth.py`, orchestrator ~end of file) derives:
  ```python
  base_name = profile.user_name.lower().replace(" ", "_")
  user_id = f"{base_name}_{self.run_id}_t{trial_index}"
  ```
  `run_id` is a per-run UUID4 short hex (or a caller-supplied value); the
  `_t{trial_index}` suffix is documented as guaranteeing uniqueness "even
  when the LLM generates duplicate names within a single run."
- **Method scoping.** `MethodPipeline.run_trial` (`pipeline.py` ~489) then
  appends the method: `method_user_id = f"{trial_data.user_id}__{self.method}"`
  and runs `AgentPipeline` with a `trial_data` copy whose `user_id` is that
  scoped value. So the fully-qualified per-trial identity is
  `{name}_{run_id}_t{idx}__{method}`.
- **Agents are fresh per trial, and only carry `user_id`.**
  `AgentPipeline.run_trial` (`pipeline.py` 81) instantiates
  `ProfileAgent` (111), `TaskAgent` (143), `AssistantAgent` (152) new for
  every trial and sets `agent.user_id = trial_data.user_id` on each. The
  agents hold no cross-trial state.
- **No provider reset / clear / wipe / restart per trial.** A repository
  grep over `benchmarks/shared_memory/*.py` for
  `reset|clear|delete_all|drop_collection|restart|reseed|flush|wipe`
  returned only: the docstring note to *manually* restart the kernel
  between the legacy phase1/phase2 runs, and the unrelated
  `threshold_search.py` kernel-restart cycle. Nothing clears memory
  between trials inside a run.
- **Kernel side.** The AIOS `Mem0Provider` is a long-lived singleton for
  the whole run; it routes each op to a **per-`user_id` ChromaDB
  collection** (`_get_client_for_user` → `_collection_name_for_user`). It
  never resets between trials either.

**Consequence for the redesign:** because `user_id` is the *only* thing
separating trials, simply **reusing one `user_id` across several
interactions would cause memory to accumulate in that one collection** —
no other machinery has to be defeated or added to get accumulation. The
uniqueness currently comes solely from the `_t{trial_index}` (and
`__{method}`) suffix.

### (b) Synthetic profile / task / query generation — no multi-interaction scaffolding

Generation today is **fully independent per trial**; `trial_index` is used
only to nudge diversity in prompts, never for continuity. `generate_trial_data`
runs a fixed one-shot chain:

1. `generate_profile(trial_index)` — LLM → `SyntheticProfile`
   (`user_name`, `preferred_tools`, `preferred_language`, `response_style`).
   `trial_index` appears only as "for trial #N" in the prompt.
2. `generate_task_context(trial_index, profile)` — LLM → `SyntheticTaskContext`
   (`current_project`, `active_experiment`, `goals`, `blockers`,
   `next_steps`). Informed by the profile, but a **wholly new** context
   each call; no prior state is passed in.
3. `generate_plausible_actions(profile, task_context)` — LLM → 3–4 actions.
4. `generate_vague_query(profile, task_context)` — LLM → one vague
   "what should I do next / how should I prioritize" query, with a
   validation loop that rejects queries leaking profile/task literals.

Key points:
- **No `session`, `interaction`, `history`, `prior`, or `evolve` concept
  exists** anywhere in `synth.py` or `models.py` (`SyntheticTrialData` has
  only `profile`, `task_context`, `follow_up_query`, `plausible_actions`,
  `user_id`).
- Task context is **LLM-generated, not template-driven**, and its fields
  (`goals` / `blockers` / `next_steps` / `active_experiment`) are exactly
  the shape you would evolve across interactions — so extending to "next
  step in an ongoing task" is plausible, but nothing does it today.
- The vague-query generator already asks "what next / how to prioritize,"
  which fits an evolving session with no change to its intent.

### (c) Truncation-collision fix is compatible with a shared session `user_id`

The AIOS collection-name fix has landed (commits `adfcaeb`, `a3da418`,
`196d893`). Current `_collection_name_for_user` is a **pure, stateless,
deterministic function of the full `user_id` string**:

- If the sanitized `user_id` fits the budget (`63 − len(prefix) − 1`), the
  name is byte-identical to the pre-fix behavior (no hash).
- If it would truncate, it appends `sha256(user_id)[:8]` computed over the
  **original, full, untruncated `user_id`**, so distinct ids stay distinct.
- `hashlib` is imported; verified the function returns the **same
  collection name on repeated calls** for the same `user_id`.

**Compatibility conclusion:** a `user_id` shared across N interactions in a
session maps to **one stable, correct collection on every call**. The fix
makes **no** one-`user_id`-per-call assumption — it has no per-call state,
counter, or trial index. A stable session `user_id` is exactly the input
it is designed to handle. (It also means the redesign should keep session
`user_id`s distinct in their *full* string; the hash guards accidental
prefix collisions but two sessions must still differ somewhere in the
full id.)

### (d) What `synth.py` (and the pipeline) would need for coherent evolving sessions

Concrete gaps, not just "possible in principle":

1. **A stable per-session `user_id` scheme.** Replace the
   uniqueness-via-`_t{trial_index}` suffix with a session identity that is
   *constant across a session's interactions* and *unique across sessions*,
   e.g. `{name}_{run_id}_s{session_idx}` reused for every interaction,
   with the interaction number kept **out** of the `user_id` (so all
   interactions share one collection). `MethodPipeline`'s `__{method}`
   append still works unchanged.
2. **An "evolve task context" generator.** Add a variant of
   `generate_task_context` that takes the **prior** `SyntheticTaskContext`
   (and optionally the prior interactions/responses) and emits the *next*
   state — e.g. some `goals` marked progressed/done, some `blockers`
   resolved and new ones introduced, `next_steps` advanced — rather than a
   fresh unrelated project. The current signature
   (`generate_task_context(trial_index, profile)`) has no parameter for
   prior state; this is the main new LLM-prompt work.
3. **Profile stays fixed per session (mostly).** `generate_profile` should
   run **once per session**, not per interaction; optionally allow small
   drift (a new tool adopted) but the identity/preferences must persist so
   accumulation is meaningful.
4. **A session-sequence orchestrator.** Add something like
   `generate_session(session_idx, num_interactions)` that returns an
   ordered list of per-interaction bundles sharing one `user_id` and a
   coherent evolving task thread. Today `generate_trial_data` returns a
   single bundle.
5. **Model/data-shape changes.** `SyntheticTrialData` (or a new
   `SessionInteraction`/`Session` model in `models.py`) needs
   `session_id` and `interaction_index` fields, and a way to carry prior
   state forward between interactions.
6. **Runner loop changes (`run_evaluation.py`).** The orchestrator
   currently loops `for i in range(self.trials): generate_trial_data(i)` →
   one `pipeline.run_trial` per `i`. For sessions it must loop
   **sessions → interactions**, reusing the one session `user_id` across
   the inner loop instead of minting a fresh id each iteration, and record
   results per (session, interaction). The `_trial_data_cache` reuse path
   for `--method all` would need an analogous per-session cache.
7. **Query generation: minimal change.** `generate_vague_query` already
   fits an evolving session; it only needs to (optionally) condition on the
   evolved task context, which it already accepts.

Nothing in the current pipeline structurally *blocks* accumulation — the
single-`user_id`-per-collection routing and the landed truncation fix
already support a shared session id. The work is additive: a
prior-state-aware task generator, a session identity/loop, and small
model/runner changes. No existing isolation guarantee has to be removed;
the redesign is opt-in alongside the current per-trial mode.

---

## Subtask 2 — Design proposal: parameterized accumulating-trial sessions

Concrete, reviewable design for `users × interactions_per_user` sessions,
grounded in Subtask 1's map. **No implementation** — this specifies the
mechanism, the metric/statistics consequences, and a pilot config for a
later build task. File references are design targets, not changes made.

### 2.1 Session-construction mechanism (answers Subtask 1(d) as decisions)

**Terminology.** A **session** = one simulated user (a stable
`SyntheticProfile`) across an ordered list of **interactions**. A run is
`users × interactions_per_user` interactions total, grouped into `users`
sessions.

**Decision 1 — Stable per-session `user_id`.** Mint the `user_id` once per
session and reuse it for every interaction in that session:
```
session_user_id = f"{base_name}_{run_id}_s{session_idx}"
```
The interaction number is deliberately **kept out** of the `user_id` so all
interactions in a session route to the **same** ChromaDB collection and
memory accumulates (Subtask 1(a)). `MethodPipeline` still appends
`__{method}` unchanged. Uniqueness across sessions comes from `s{session_idx}`
+ `run_id`; the landed hash-suffix in `_collection_name_for_user` (Subtask
1(c)) guards accidental prefix collisions, but we still keep the full ids
distinct per session. **`interaction_index` lives in the data model and the
prompt/results, never in the `user_id`.**

**Decision 2 — How `generate_task_context` evolves.** Add a sibling method
(design name `evolve_task_context`) that takes the **prior**
`SyntheticTaskContext` plus a short digest of prior interactions (the
queries asked and, optionally, the assistant's own stated next-step) and
emits the *next* state of the same project — not a new project. The
evolution operators, expressed to the generator as explicit rules:
- **`goals`**: 0–1 prior goal marked *progressed* or *completed* (dropped
  or rephrased as done); occasionally 1 new goal added as the project
  matures. The project identity (`current_project`) stays fixed.
- **`blockers`**: 0–1 prior blocker *resolved* (removed); 0–1 *new* blocker
  introduced, ideally caused by the prior next_step (realistic churn).
- **`next_steps`**: the step the user plausibly "took" is removed/advanced;
  remaining steps re-prioritized; 1 new step appended.
- **`active_experiment`**: advances to the next phase when a goal completes,
  else unchanged.
Interaction 0 uses today's `generate_task_context` verbatim (cold start);
interactions 1..N-1 use `evolve_task_context(prior_ctx, history_digest)`.
This is the **main new LLM-prompt work** and the primary thing the pilot
must validate (does the chain stay coherent, or drift into a new project?).

**Decision 3 — `generate_profile` runs once per session (with optional
minor drift).** The profile is the *stable identity* whose persistence is
the whole point of accumulation, so it is generated **once per session**
and held fixed. We explicitly do **not** re-roll it per interaction.
Optional (flagged off for the pilot): allow a small, rare drift — e.g. one
new tool adopted mid-session — to test whether the memory system tracks
*preference change*. Recommendation: **keep profile fixed for the pilot**;
revisit drift only after the evolving-task mechanism is validated.

**Decision 4 — Data-model additions (`models.py`).** Introduce a
per-interaction bundle and a session wrapper (design names):
- Extend `SyntheticTrialData` with `session_id: str = ""` and
  `interaction_index: int = 0` (defaults preserve today's one-shot mode:
  `session_id=""`, `interaction_index=0`).
- Add `SyntheticSession` = `{ session_id, user_id, profile,
  interactions: List[SyntheticTrialData] }` where each interaction carries
  its own evolved `task_context`, `follow_up_query`, `plausible_actions`,
  and the **shared** session `user_id`.
- Result side: add `session_id` + `interaction_index` to `TrialResult` so
  per-interaction rows remain the atomic record and can be grouped by
  session downstream. No existing field is removed or redefined.

**Decision 5 — `generate_session(...)` orchestrator shape.**
```
generate_session(session_idx, interactions_per_user) -> SyntheticSession:
    profile = generate_profile(session_idx)          # once
    ctx = generate_task_context(0, profile)          # interaction 0 (cold)
    user_id = f"{base_name}_{run_id}_s{session_idx}"
    interactions = []
    history = []                                     # digest of prior turns
    for i in range(interactions_per_user):
        if i > 0:
            ctx = evolve_task_context(ctx, history)  # interaction i>0
        actions = generate_plausible_actions(profile, ctx)
        query   = generate_vague_query(profile, ctx) # already fits; may
                                                     # condition on ctx
        interactions.append(SyntheticTrialData(
            profile=profile, task_context=ctx, follow_up_query=query,
            plausible_actions=actions, user_id=user_id,
            session_id=user_id, interaction_index=i))
        history.append(digest(query, ctx))
    return SyntheticSession(...)
```
`generate_vague_query` needs no change beyond optionally seeing the evolved
`ctx` (which it already accepts) — Subtask 1(d.7).

**Runner change (`run_evaluation.py`), design-only.** Replace the flat
`for i in range(trials)` loop with a **sessions → interactions** double
loop: for each session, build the `SyntheticSession` once, then call
`pipeline.run_trial` per interaction **reusing the session `user_id`**, so
interaction `i` reads back the accumulated memory written by interactions
`0..i-1`. `--method all` gets a per-session data cache analogous to
today's `_trial_data_cache`, keyed by `session_idx` so every method
replays the identical session. New CLI: `--users` and
`--interactions-per-user` (with `--trials` retained as the one-shot legacy
mode, i.e. `interactions_per_user=1`).

### 2.2 Metrics: recommend PER-INTERACTION scoring

**Recommendation: score every interaction with the existing judge, keep
the atomic record per-interaction, and aggregate only in analysis.**

- **Why per-interaction.** It preserves the existing
  `profile_usage` / `task_usage` / `integration` metric definitions
  **unchanged** (no re-derivation, no new rubric), and — the real payoff —
  it lets us observe the **within-session trajectory**: does personalization
  quality *rise* from interaction 0 → N as memory accumulates? That
  trajectory is the whole hypothesis behind accumulating sessions, and it
  is only visible if each interaction is scored separately. It also keeps
  the judge, HybridJudge keyword logic, and results schema untouched.
- **Tradeoff vs. per-session aggregation.** A single per-session score
  (e.g. mean or final-interaction score) would give one number per user —
  which is convenient for the between-condition test (it *is* the
  user-level unit; see 2.3) — but it **discards the trajectory**, forces a
  choice of aggregation (mean? last? slope?) that redefines "the metric,"
  and throws away information the pilot specifically needs to see.
- **Resolution:** compute **per-interaction** scores as the stored atomic
  record; derive **per-session** summaries (mean, final, and 0→N slope) in
  `results.py`/analysis as *additional* columns, not as a replacement. This
  gives both the trajectory and a clean user-level unit for statistics
  without redefining anything.

### 2.3 Statistical-independence consequence (state plainly)

Once interactions share session state, **interactions within a session are
NOT independent** — later interactions are conditioned on the memory and
task evolution of earlier ones. Therefore:

> **Effective N for between-condition comparisons is ~`users`, not
> `users × interactions_per_user`.** Treating all interactions as
> independent trials would overstate N by a factor of
> `interactions_per_user` and produce anticonservative (too-small)
> p-values / too-narrow CIs.

**Required methodology for the eventual full run (specify now, not later):**
- **Primary between-condition test at the user level.** Reduce each session
  to one user-level statistic (per 2.2, e.g. mean or final-interaction
  score) and run the condition comparison across `users` — this is the
  honest, simplest correct analysis and should be the headline.
- **If reporting interaction-level effects** (e.g. the 0→N trajectory or a
  condition×interaction interaction), use a model that accounts for
  within-user clustering — a **mixed-effects model with `user` (session) as
  a random effect** (random intercept per session, optionally random slope
  over `interaction_index`), or GEE / **cluster-robust standard errors
  clustered on session**. Do **not** use a plain per-interaction t-test /
  Mann–Whitney across pooled interactions.
- **Report both** trial-level (per-interaction, descriptive) and user-level
  (per-session, inferential) statistics explicitly, and state the effective
  N = `users` next to any between-condition claim. This mirrors the
  existing repo caution against silently pooling non-comparable units
  (cf. the v1/v2 rubric no-pooling rule) — same discipline, applied to the
  independence unit.

### 2.4 Pilot configuration recommendation

**Recommended pilot: `users = 5`, `interactions_per_user = 4`  (20
interactions total), single model = `qwen2.5:7b` (local Ollama), single
method = `kernel_shared_adaptive`.**

Reasoning, grounded in Subtask 1's finding that the **evolving-task-context
generator is the main new work** and the pilot's job is to validate *that
mechanism*, not to power a statistical claim:
- **`interactions_per_user = 4` (not 2, not 10).** The pilot's core risk is
  coherence drift in `evolve_task_context`: 2 interactions barely exercises
  evolution; 4 is enough to see whether goals/blockers/next_steps stay on
  one coherent project across *several* evolution steps and whether
  accumulated memory visibly helps by interaction 3–4 — without paying for
  a long chain before the mechanism is proven.
- **`users = 5` (small).** The pilot is a *mechanism* check, not a powered
  comparison (effective N here is 5 — deliberately underpowered; we are not
  drawing inferential conclusions from the pilot). 5 distinct profiles is
  enough to confirm the session `user_id` scheme, collection stability
  under the truncation fix, and per-interaction scoring/aggregation
  plumbing across a few identities.
- **20 interactions total** ≈ the cost of a 20-trial one-shot run, which
  Subtask 1's cost notes put well within a cheap local qwen run (the
  expensive part is per-interaction assistant + judge LLM calls, unchanged
  per interaction). Cheap enough to iterate on the `evolve_task_context`
  prompt several times in a day.
- **Single model / single method.** Validate the evolving mechanism and the
  accumulation effect on the condition that *uses* adaptive gating first;
  fan out to GPT-4o / Llama and to the other conditions only after the
  generator is trusted. `qwen2.5:7b` local avoids API cost during
  prompt-iteration.

**Scale-up path (post-pilot, for reference — not the pilot):** once the
generator is validated, a powered run would target `users ≈ 30–50` per
condition (user-level N) × `interactions_per_user ≈ 5`, across the three
models and the six conditions, with the user-level analysis in 2.3 as the
headline.

### 2.5 Scope confirmation

No code was written in this subtask. All `synth.py` / `pipeline.py` /
`run_evaluation.py` / `models.py` references above are **design targets**
for a later implementation task. The pilot config (2.4) is a concrete
recommendation to act on, not an open question.
