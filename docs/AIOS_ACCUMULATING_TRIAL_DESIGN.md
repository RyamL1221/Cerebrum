# Accumulating / Evolving-Session Trial Design

Working document for the "accumulating trial" redesign of the shared-memory
benchmark: instead of each trial being a wholly independent one-shot
(fresh user, fresh task), a *session* would be one simulated user across
several coherent, evolving interactions that accumulate memory.

> **Status:** Subtask 1 (pipeline mapping), Subtask 2 (design proposal), the
> Subtask 3 scoping-guidance addendum, Subtask 3's detailed build
> instructions, and the **§3.4 reward-attribution gate finding (RESOLVED)**
> all live in this single file (one source of truth — no separate scope
> doc). Everything here is documentation with **no implementation code**.
> The §3.4 gate is cleared: `trial_index` (global per-interaction integer)
> remains the reward key; `session_id`/`interaction_index` are additive
> descriptive fields. Build (Subtask 2) may proceed against §3 + §3.4.

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

---

## Subtask 3 scoping guidance (review addendum — added after Subtask 2 review)

Three refinements agreed in review, recorded here so Subtask 3 (which is
scoped from this file) inherits them in writing rather than from
conversation. None change the Subtask 2 design; they sharpen its handoff.

### A. Two pilots, explicitly split — Subtask 3 owns only the first

The single pilot in §2.4 actually serves **two different goals** that must
not be conflated:

1. **Mechanism pilot — `5 users × 4 interactions` (this is §2.4).** Goal:
   *does `evolve_task_context` produce coherent output, and does the
   session plumbing (stable `user_id`, per-interaction scoring,
   collection stability under the truncation fix) work?* Pass/fail is
   coherence-by-inspection + plumbing-correct, **not** any gate-behavior
   or metric-curve claim. Cheap on purpose so the evolution prompt can be
   iterated several times.
2. **Ramp-up pilot — `few users × long sessions`, config DEFERRED.** Goal
   (this is **Subtask 4's** job, per the master prompt): *at roughly which
   interaction index does the accumulated shared-memory set get large
   enough that the AIOS gates (novelty / similarity / redundancy) start
   receiving a materially larger comparison set and behaving differently?*
   Its `interactions_per_user` **cannot be sized now** — you do not know
   the inflection point until you have measured it, and you cannot trust a
   long run until coherence is known to hold that long. So its length is
   chosen **after** the mechanism pilot reveals the coherence ceiling.

**Why split, not one run.** 4 interactions almost certainly does **not**
reach the regime where gates behave differently (each interaction adds only
~2–3 shared memories; the comparison set is still tiny at interaction 4), so
a 5×4 run cannot answer the ramp-up question. And running a long ramp-up
pilot *before* coherence is trusted risks burning expensive compute on a
generator that has already drifted into a different project by, say,
interaction 6 — at which point the "accumulated memory" no longer matches
the query and the ramp-up data is meaningless. Mechanism first, then
ramp-up, is a cost-and-validity ordering, not just tidiness.

**Consequence for Subtask 3 (binding acceptance criteria):**
- Subtask 3 builds and validates against the **mechanism pilot (5×4)
  only**. Its acceptance criteria are mechanism + plumbing coherence; it is
  **NOT** responsible for observing gate-behavior change.
- Subtask 3 MUST make `interactions_per_user` a **first-class, fully
  parametric value** — no hard-coded `4`, no fixed-size arrays, no prompt
  text assuming a specific count; `evolve_task_context` must stay coherent
  for arbitrary N. This is what turns "two pilots" into "one build, two
  configs": the ramp-up pilot then becomes a config change
  (`--users 3 --interactions-per-user 20`, illustrative), not a re-scope.
- Subtask 4 gets its **own** longer pilot config, deliberately chosen later
  from the observed coherence ceiling — not guessed now and not inherited
  from the 5×4 mechanism pilot.

### B. Per-interaction SCORING is encouraged; per-interaction TESTING is forbidden

§2.2 and §2.3 concern two **different operations** and must not be
conflated by a future reader:
- **Scoring (per-interaction) — ENCOURAGED (§2.2).** Run the existing judge
  on every interaction and store the per-interaction score as the atomic
  record. This is how the within-session 0→N trajectory becomes
  observable; it changes no metric definition.
- **Between-condition statistical testing (per-interaction) — FORBIDDEN
  (§2.3).** Do **not** run a between-condition significance test over
  pooled per-interaction rows (e.g. a per-interaction t-test / Mann–Whitney
  across all interactions of all sessions). Interactions within a session
  are not independent, so the inferential unit is the **session/user**
  (effective N ≈ `users`), via a user-level statistic or a mixed-effects /
  cluster-robust model.

In short: **score per interaction, test per user.** Keeping per-interaction
scores is not in tension with the no-pooled-per-interaction-test rule — the
first is measurement, the second is inference, and only the inference unit
is constrained.

### C. Pre-implementation audit: does `trial_index` still map 1:1 to a reward-attribution identity?

This is a **data-model assumption audit Subtask 3 must perform BEFORE
building**, not a surface bug to find during implementation — and it is
**separate** from anything already addressed by the truncation-collision
fix (that fix was about collection *naming*; this is about *identity
cardinality* in the logging/reward path).

The concern: today the harness is one-shot, so `trial_index` ↔ `user_id` ↔
one collection is effectively 1:1:1, and the reward/logging path relies on
that. In a session structure, `user_id` becomes **per-session** while
`trial_index`/`interaction_index` becomes **per-interaction**, so **many
`trial_index` values now map to one `user_id`/collection**. Any downstream
logic that implicitly assumed one `trial_index` = one identity must be
audited explicitly:
- **`policy_trials.jsonl` + `join_policy_actions.py`.** From the earlier
  investigation: `trial_id` resets to 0 each run with **no run identifier**,
  the join is single-run-scoped by caller assumption, and reward events key
  on `reward.trial_id == TrialResult.trial_index`. Subtask 3 must decide and
  document what the reward-attribution key becomes under sessions — does the
  kernel-side policy log now need `(session_id, interaction_index)` (or the
  per-interaction `trial_index`) to attribute a reward to the right turn,
  and does the join still work when one `user_id` spans many `trial_index`
  values? Confirm whether per-interaction reward attribution is even
  well-defined when the gates operate over an accumulating set.
- **Any per-trial logging / results grouping** that assumed one
  `trial_index` per identity (result-file structure, CSV rows, the
  `_trial_data_cache` keying for `--method all`).

Deliverable for this point in Subtask 3: an explicit written finding —
"trial_index remains/does-not-remain a valid reward-attribution key under
sessions, and here is the key we will use instead" — produced **before**
implementation begins, so the data model is chosen correctly the first
time rather than retrofitted.

---

## Subtask 3 — Detailed build instructions (mechanism pilot)

The concrete implementation scope for the accumulating-trial redesign,
folded into this file (single source of truth — do not split into a
separate scope doc). Subtask 3 is bounded to the **mechanism pilot only**;
the ramp-up pilot and gate-behavior measurement are Subtask 4.

### 3.0 Goal (one line)

Build the parameterized `users × interactions_per_user` accumulating-session
mechanism and validate it at `5 × 4` on `kernel_shared_adaptive` /
`qwen2.5:7b` — proving `evolve_task_context` stays coherent and the session
plumbing works — **without** making any gate-behavior or metric-curve claim.

### 3.1 In scope

1. **Data model (`models.py`)** — but only after the §3.4 audit gate:
   - `session_id: str = ""` and `interaction_index: int = 0` on
     `SyntheticTrialData` (defaults preserve one-shot mode).
   - A `SyntheticSession` model: `{ session_id, user_id, profile,
     interactions: List[SyntheticTrialData] }`.
   - `session_id: str = ""` and `interaction_index: int = 0` on
     `TrialResult` (per-interaction row stays the atomic record).
   - Plus whatever reward-attribution key §3.4 concludes is needed. No
     existing field removed/redefined; all additions defaulted so existing
     one-shot result files still parse.
2. **Synthetic generation (`synth.py`)**:
   - `evolve_task_context(prior_ctx, history_digest, profile)` per §2.1
     Decision 2 (goals progress/complete, blockers resolve/appear,
     next_steps advance, `current_project` fixed, `active_experiment`
     advances on goal completion).
   - `generate_session(session_idx, interactions_per_user)` per §2.1
     Decision 5: profile once, interaction 0 cold-start via existing
     `generate_task_context`, interactions 1..N-1 via `evolve_task_context`,
     all sharing `user_id = {name}_{run_id}_s{session_idx}`.
   - `generate_profile` once per session; drift OFF (§2.1 Decision 3).
   - `interactions_per_user` fully parametric — see §3.3.
3. **Pipeline / runner (`pipeline.py`, `run_evaluation.py`)**:
   sessions→interactions double loop reusing the session `user_id`; new
   `--users` / `--interactions-per-user` CLI; `--trials` retained as
   one-shot legacy (`interactions_per_user=1`, `session_id=""`);
   `--method all` per-session cache keyed by `session_idx`.
4. **Scoring:** per-interaction with the **existing** judge — no rubric or
   metric-definition change (§2.2 / addendum B: score per interaction).
5. **§3.4 pre-implementation audit** (gate) and **§3.5 mechanism-pilot
   validation** including the **§3.6 exploratory ceiling probe**.

### 3.2 Out of scope (do NOT do in Subtask 3)

- No ramp-up / gate-behavior measurement (Subtask 4; config deferred).
- No between-condition statistical testing (pilot is N=5, underpowered by
  design — §2.3 / addendum B: testing is per-user, and not in this subtask
  at all).
- No profile drift, no multi-model fan-out, no other conditions, no
  scale-up run, no re-run of the existing per-trial benchmark, no change to
  the landed truncation-collision fix, no new metric definitions.

### 3.3 Binding requirement — `interactions_per_user` fully parametric

The single most important structural constraint (addendum A): no literal
`4` anywhere in generation, prompts, loops, arrays, or count-tied defaults;
`evolve_task_context` stays coherent for **arbitrary N** (evolves one step
from prior state regardless of horizon); the runner accepts any `--users` /
`--interactions-per-user` with no code change. **Acceptance check:**
`--users 3 --interactions-per-user 12` runs end-to-end with zero code edits
(smoke-run a couple of sessions).

### 3.4 Pre-implementation audit — GATE, not a checklist item (addendum C)

Complete **before** writing model/runner code, because it can change how
`SyntheticTrialData` / `TrialResult` must be shaped (build the data model
first and you risk the audit invalidating it).

**Question:** does `trial_index` still map 1:1 to a reward-attribution
identity once `user_id` is per-session and `interaction_index` is
per-interaction (many `trial_index` → one `user_id`/collection)?

**Examine:** `join_policy_actions.py` (reward join keys on
`reward.trial_id == TrialResult.trial_index`; `trial_id` resets per run,
no run id, single-run-scoped by caller assumption); the kernel-side
`report_reward` / `policy_trials.jsonl` path (does it need
`(session_id, interaction_index)` to attribute a reward to the right turn —
any kernel change is an AIOS follow-up, but the *requirement* is identified
here); any per-trial logging / results grouping / `_trial_data_cache`
keying assuming one `trial_index` per identity.

**Deliverable (produced before implementation):** an explicit written
statement — "`trial_index` remains / does not remain a valid
reward-attribution key under sessions; the key we will use is X" —
recorded in this doc. Separate from the truncation-collision fix (that was
collection *naming*; this is identity *cardinality*).

### 3.5 Mechanism-pilot validation (`5 × 4`)

Run `--users 5 --interactions-per-user 4 --method kernel_shared_adaptive`
on `qwen2.5:7b` (local Ollama), against a kernel with
`adaptive_policy.enabled=true` (gating pre-flight asserts this).

**Coherence judging method — MANUAL review, explicitly.** Coherence is
assessed by a human **reading the generated sessions** (the ~20
interactions), checking that within each session `current_project` stays
fixed and goals/blockers/next_steps evolve plausibly. Subtask 3 does
**not** build an automated coherence checker — this is a one-off manual
review step, not tooling to implement. (If a lightweight sanity assertion
is trivial — e.g. `current_project` string stable within a session — it may
be added, but the coherence *judgment* is manual.)

**Pass criteria (mechanism + plumbing only — NOT gate behavior):**
1. **Coherence (manual):** each 4-interaction session holds one project
   with plausible goal/blocker/next-step evolution.
2. **Accumulation plumbing:** interaction `i` reads back memory written by
   `0..i-1` in the same session (shared collection grows within a session;
   retrieved/`total_stored` set non-decreasing within a session).
3. **Collection stability:** the session `user_id` maps to one stable
   collection across all 4 interactions (consistent with the landed
   truncation fix — no per-interaction collection churn).
4. **Scoring plumbing:** each interaction yields a per-interaction
   `TrialResult` with `session_id`/`interaction_index` set and the three
   judge scores present.
5. **Parametric proof:** the §3.3 acceptance check passes.

**Explicitly NOT a pass criterion:** any statement about the gates
receiving a larger comparison set, or a metric-improvement curve (Subtask 4).

### 3.6 Exploratory ceiling probe (one long session — resolves the §3.7 handoff)

A strict `5 × 4` pilot can only **confirm coherence through interaction 4**;
it cannot discover where `evolve_task_context` starts drifting, which would
leave Subtask 4 with nothing concrete to size its ramp-up horizon from.
Subtask 3 therefore includes **one small, deliberate "push past 4"
exploratory run**: a **single** session (1 user) at a longer horizon
(≈12 interactions is a reasonable probe length) whose only purpose is to
observe, by the same **manual** coherence review, the approximate
interaction index at which the evolving task context starts to drift
(project changes, goals become incoherent, or evolution stalls/repeats).

Scope discipline for the probe:
- It is a **first, approximate** ceiling estimate from **one** session —
  deliberately cheap. It is **NOT** a full characterization (sweeping
  horizons, multiple seeds, per-model differences); that full
  characterization is **Subtask 4's job**.
- If coherence holds cleanly through the whole probe horizon, the reported
  ceiling is "≥ probe length (no drift observed at N=12)"; Subtask 4 then
  starts from there and pushes further.
- The probe uses the same code path (proving §3.3 parametricity again) — it
  is a config change, not new code.

### 3.7 Handoff to Subtask 4 (concrete deliverables)

On completion Subtask 3 hands Subtask 4 three **concrete** things:
1. A working, fully-parametric session mechanism.
2. An **approximate coherence ceiling** from the §3.6 exploratory long
   session — a concrete number (the interaction index where drift was first
   observed, or "≥N, no drift observed") — so Subtask 4 can pick a starting
   ramp-up horizon rather than guess. This is an *approximate first
   estimate from one session*, not a definitive ceiling; finding the true
   ceiling (multi-seed, multi-horizon, per-model) is Subtask 4's work.
3. The resolved reward-attribution key from §3.4, so Subtask 4's
   gate-behavior measurement attributes rewards to the correct turn.

### 3.8 Suggested task order (for the implementer)

1. §3.4 audit → write the finding (GATE — before any model code).
2. `models.py` additions (§3.1.1) + round-trip check that existing one-shot
   result files still parse.
3. `synth.py`: `evolve_task_context` + `generate_session` (§3.1.2), keeping
   `interactions_per_user` free (§3.3).
4. Runner: sessions→interactions loop + CLI + per-session cache (§3.1.3);
   one-shot legacy path unchanged.
5. Per-interaction scoring wired to `TrialResult` (§3.1.4).
6. `5 × 4` mechanism-pilot run + manual coherence / plumbing validation
   (§3.5); record results.
7. §3.6 exploratory `1 × ~12` ceiling probe; record the approximate ceiling.
8. §3.3 parametric smoke check (`3 × 12`).

---

## §3.4 RESOLVED — reward-attribution key under accumulating sessions (gate finding)

This is the committed decision from the §3.4 pre-implementation audit. It is a
**decision, not just an investigation** — implementation (Subtask 2 of the
build) must follow it. All claims traced to code:
`benchmarks/shared_memory/{run_evaluation.py,results.py,models.py}`,
`docs/policy-trials-jsonl-findings.md`, and (read-only) sibling AIOS
`aios/memory/manager.py`.

### How reward attribution works today (confirmed)

- **Join key:** `policy_reward.trial_id == TrialResult.trial_index`, direct
  integer equality, single-run only (`join_policy_actions.py`; the earlier
  `policy-trials-jsonl-findings.md` GO decision).
- **How `trial_id` reaches the kernel:** only via the `report_reward` POST in
  `run_single_trial`, `reward_metadata = {**trial_metadata, "trial_id":
  trial_index}` — sent **once per `run_single_trial`** (post-judging).
- **Kernel mechanism** (`aios/memory/manager.py::report_reward`, ~L1099):
  `_pending_reward_decisions` is `Dict[memory_id → list of (bandit, arm_index,
  context, trial_id)]`, recorded **at retrieve time**. `report_reward(
  memory_ids_involved, reward_value, trial_metadata)` **pops** the decisions for
  each involved `memory_id`, applies `reward_value` to each, and logs
  `reward.trial_id = decision_trial_id or trial_metadata["trial_id"]`. Consumed
  entries are removed (map stays bounded).
- **Neither artifact carries `run_id` / `user_id` / `session_id`;** `select`
  records already log `trial_id: null` (a pre-existing gap, unchanged by this
  work). Results/CSV are one row per `trial_index`; `_trial_data_cache` is keyed
  by the loop index (== `trial_index`).

### DECISION: `trial_index` REMAINS the reward-attribution key — as a global per-interaction integer

**`trial_index` stays the reward key. It must be a single, globally-monotonic,
per-interaction counter across the whole run (`0 .. users×interactions_per_user −1`),
NOT reset per session.** Each interaction is its own `run_single_trial` and
therefore emits exactly one `report_reward` with its own unique `trial_index`.
The join stays `reward.trial_id == TrialResult.trial_index`, integer equality,
**unchanged** — `join_policy_actions.py` needs no modification and the
single-run scoping constraint from the prior GO decision still holds.

Rationale: attribution today is `1 report_reward : 1 trial_index : 1 turn`.
Sessions add more turns, not a different attribution shape — as long as every
turn keeps a distinct `trial_index`, the existing integer join keeps working
turn-for-turn. Introducing `(session_id, interaction_index)` as the *join key*
would be a gratuitous, breaking change to a working mechanism; there is no
reason to.

**`session_id` and `interaction_index` are ADDITIVE descriptive/grouping fields,
NOT the reward key.** They exist so downstream analysis can group per-interaction
rows into sessions and locate a turn within a session (the 2-D coordinate
`(session, interaction)`), and so the user-level statistics in §2.3 can reduce
by `session_id`. They do **not** participate in reward attribution.

### The design doc's `session_id`/`interaction_index` sketch HOLDS — with one clarification

§2.1 Decision 4 and §3.1.1 stand as written. The one clarification this audit
adds, which Subtask 2 (build) MUST honor:

> `trial_index` is the **global per-interaction** integer (unique across the
> whole run) and remains the reward-attribution key. `interaction_index` is the
> **within-session** position (`0..interactions_per_user−1`) and is descriptive
> only. **Do NOT** conflate them and **do NOT** reset `trial_index` per session.
> A session's turns have, e.g., `trial_index = 8,9,10,11` while
> `interaction_index = 0,1,2,3` and one shared `session_id`.

No revision to the model *fields* is needed (the sketch already lists both
`session_id` and `interaction_index`); the revision is purely this semantic
constraint on how `trial_index` is generated by the runner.

### Per-interaction attribution IS well-defined (with a flagged subtlety)

Under accumulation, `memory_ids_involved` for interaction *i* can include
memories first written in an earlier interaction (that is the whole point). The
kernel mechanism makes attribution **well-defined at the bookkeeping level**:

- A pending decision is recorded **at the retrieve that actually happened in
  interaction *i***, tagged with *i*'s `trial_index`, and `report_reward` for
  interaction *i* applies **interaction *i*'s own judge score** to it. So the
  reward *value* never bleeds across interactions — each turn's reward is its
  own score, attributed to its own `trial_index`.
- A memory re-retrieved in a later interaction generates a **new** pending
  decision tagged with the later `trial_index`, so it attributes to whichever
  interaction actually retrieved it. Pop-on-reward keeps decisions from being
  double-counted.

**Flagged (NOT solved here — belongs to Subtask 4's interpretation):** the gate
*decision* being rewarded at interaction *i* was made against the **accumulated
memory set as it stood at interaction *i***. So while the reward is cleanly
attributed to one interaction, the *causal reading* ("this threshold was good")
is inherently conditioned on the accumulation state at that turn. That is
expected — it is exactly the effect the accumulating-session design exists to
study — and it is a measurement-interpretation caveat for Subtask 4, not a
bookkeeping bug and not something this build fixes.

### Consequences for the build (Subtask 2)

1. Runner emits a **global monotonic `trial_index`** per interaction; do not
   reset per session. `session_id` + `interaction_index` are recorded alongside.
2. `join_policy_actions.py`: **no change** (integer-equality reward join intact;
   single-run scoping intact).
3. `_trial_data_cache` becomes **session-scoped** (keyed by `session_idx`, since
   a session's data is generated once and its interactions replayed) — this is a
   caching change only and does **not** affect the reward key.
4. Results/CSV: add `session_id` + `interaction_index` columns; the per-row
   atomic unit stays one interaction (== one `trial_index`).

**Gate cleared.** The data model shape from the design doc is confirmed valid
with the one semantic clarification above; Subtask 2 may build against it.

---

## §3.5–3.7 RESULTS — mechanism pilot (executed)

Live execution of the mechanism pilot. Models: **GPT-4o assistant / GPT-5.4
judge (Azure)** (switched from the originally-planned local qwen2.5:7b for
speed/reliability during iteration). Method `kernel_shared_adaptive`, kernel
`adaptive_policy_enabled=true` (gating pre-flight passed). Results dirs:
`results/session_pilot_5x4_gpt/`, `results/session_pilot_3x12_gpt/`.

### Runs completed

| Run | Config | Interactions | Failed | Notes |
|-----|--------|-------------|--------|-------|
| Mechanism pilot | `--users 5 --interactions-per-user 4` | 20 | **0** | clean |
| Parametric verify | `--users 3 --interactions-per-user 12` | 36 | **0** | clean, zero code edits |

(An earlier 5×4 attempt on local qwen aborted mid-run when the AIOS kernel
process died — sessions 2–4 failed. The harness handled the crash gracefully:
it recorded failed `TrialResult`s with correct `session_id`/`interaction_index`
and kept `trial_index` monotonic, then finished cleanly. Kernel was restarted
and the run redone on GPT.)

### Parametric verification (§3.3 acceptance check) — PASS

`--users 3 --interactions-per-user 12` ran end-to-end with **zero code edits**,
producing 36 interactions across 3 sessions of 12 (`interaction_index` 0..11
each), `trial_index` monotonic 0..35. Confirms `interactions_per_user` is a
genuinely free parameter and `evolve_task_context` makes no session-length
assumption.

### Plumbing confirmations (concrete evidence)

- **Global-monotonic `trial_index`:** 5×4 → `trial_index` exactly `0..19`, NOT
  reset per session (session 1 starts at 4, session 2 at 8, …). 3×12 → `0..35`.
  Verified programmatically (`tidxs == list(range(N))`).
- **`session_id` / `interaction_index`:** correct in both runs — each session
  shares one stable `user_id` (e.g. `alexandra_carter_sess5x4gpt_s0`); interaction
  indices `0..3` (5×4) / `0..11` (3×12). Present in JSON and CSV.
- **Per-interaction scoring:** all interactions carry profile/task/integration
  scores (5×4 means ≈4.25/4.30/4.10). One atomic `TrialResult` row per
  interaction.
- **Per-session collection isolation:** each session's
  `injected_memory_ids` is a distinct pair, stable within the session and
  different across sessions — confirming the stable per-session `user_id` routes
  each session to its own collection.

### KEY FINDING (rough edge) — within-session memory does NOT accumulate

**`shared_memory_count` stays pinned at 2 for every interaction, at BOTH
horizons (interaction_index 0..3 and 0..11), and the physical
`total_stored_for_user` never exceeds 2** (confirmed from kernel logs for a
12-interaction session). The injected memory set is the *same two ids* across
all of a session's interactions.

Mechanism (traced in kernel logs): each interaction re-runs ProfileAgent +
TaskAgent, which write a `profile` and a `task_context` memory under the session
`user_id`, and the kernel's `auto_extract` writes a `conversation` memory — e.g.
session s0 issued **6 add attempts across 4 interactions** (1 profile + 1 task +
4 conversation). But Mem0's fact-extraction/dedup **collapses** these to ~2
persisted rows for the user: the fixed profile and the near-identical evolving
task context dedupe, and the conversation memories are either merged or (per the
recurring `Mem0 diagnostic: 0 results ... fact extraction may have failed
silently` warning) not landing as distinct retrievable rows. Net: the store does
not grow within a session.

**Interpretation.** This is exactly what a mechanism pilot is for. The harness
plumbing is correct and complete — sessions, stable ids, monotonic reward key,
per-interaction scoring, per-session isolation, graceful crash handling all work.
But the **accumulation premise itself does not hold under the current Mem0 write
path**: sharing a `user_id` across interactions is *necessary but not sufficient*
for accumulation, because Mem0 dedupes same-user/same-type writes rather than
appending. So the "does accumulation reach the regime where gates see a larger
comparison set" question (Subtask 4) **cannot be studied as-is** — the comparison
set stays at 2 no matter the horizon. This is an AIOS-side write/dedup behavior,
not a Cerebrum harness bug, and it is flagged (not fixed) here.

### Coherence review (§3.5 manual) — evolve_task_context is coherent, no drift

Read across sessions at both horizons. `evolve_task_context` produces genuinely
continuous, plausibly-evolving projects with **fixed project identity** and no
drift/repetition:

- **5×4 session s0 ("Data Pipeline Optimization"):** experiment arc *testing async
  queries → evaluating performance metrics → analyzing bottlenecks → testing
  optimization strategies*; `next_steps` advance causally (each step taken becomes
  the next premise); a bottleneck goal appears mid-session then resolves; a new
  blocker ("uncertainty on which optimization strategy") appears at i3, caused by
  the prior bottleneck analysis. Textbook of the intended operators.
- **5×4 session s3 ("Real-Time Collaboration Tool"):** WebSocket implementation →
  stress testing → versioning/conflict resolution → validating versioning.
- **3×12 session s0 ("Interactive Dashboard for Sales Analytics"):** coherent
  across ALL 12 interactions — dynamic chart rendering → perf refinement →
  batched DOM updates → evaluating/selecting a chart library → integrating → live
  testing. **Project identity stable across all 12; no drift.**

Minor observation: one long-horizon interaction scored task_usage=2 (3×12 tidx
21), a single dip rather than a trend — not drift.

### §3.6 ceiling probe → §3.7 handoff to Subtask 4

The 3×12 run doubles as the exploratory ceiling probe. **Approximate coherence
ceiling: ≥ 12 interactions — no drift observed at N=12** (project identity fixed,
experiment/next_step arc continuous through interaction 11). Subtask 4 can start
its ramp-up horizon at ≥12 and push further to find the true ceiling
(multi-seed / multi-model characterization is Subtask 4's job).

**Concrete handoff to Subtask 4:**
1. Working, fully-parametric session mechanism (verified 5×4 and 3×12, 0 failures).
2. Coherence ceiling estimate: **≥12, no drift at N=12** (from one long GPT-4o session).
3. Reward-attribution key (from §3.4): `trial_index` global-monotonic — confirmed
   live (0..19, 0..35), reward reports carry real `memory_ids` (`has_ids`).
4. **BLOCKER for Subtask 4's gate-behavior question:** within-session memory does
   not accumulate under the current Mem0 write/dedup path (`shared_memory_count`
   and `total_stored_for_user` pinned at 2 regardless of horizon). Subtask 4
   cannot observe "gates receiving a materially larger comparison set" until this
   AIOS-side accumulation behavior is addressed. This should be resolved (or the
   ramp-up question re-scoped) before Subtask 4's measurement pilot.
