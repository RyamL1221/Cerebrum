# AIOS Memory-Gating Dependency Scope per Condition

**Subtask 1 — investigation only. No code was modified.**

Goal: establish, from the live repo, exactly which `_run_*` condition methods route
through AIOS kernel endpoints where the new adaptive-vs-static memory-gating state
(the `GET /memory/gating_status` contract) is relevant — so a pre-flight gating check is
added only where it belongs.

## Terminology: two distinct mechanisms — do NOT conflate

This scope concerns the **new three-tier gating** work
(`kernel_shared` / `kernel_shared_tuned` / `kernel_shared_adaptive`), whose interface is the
AIOS server endpoint:

```
GET /memory/gating_status
  → {adaptive_policy_enabled, static_thresholds_enabled, static_thresholds_config: {...}}
```

That endpoint (and the adaptive-policy / reward-attribution plumbing behind it) lives
**server-side in AIOS**, which is out of scope to search or modify from this Cerebrum repo.
Per prior context the policy module isn't built yet; only the endpoint contract is defined.
**This contract is trusted as given.**

Separately, Cerebrum references a pre-existing, unrelated kernel config toggle pair,
`auto_inject` / `auto_extract` (`aios/config/config_loader.py:66-68`): whether the kernel
auto-injects retrieved memory into context / auto-writes new memory. That pair is **adjacent
context only** — it is NOT the adaptive-vs-static gating this subtask is about, and subtask 5's
verification must read `gating_status` fields (`adaptive_policy_enabled` /
`static_thresholds_enabled` / `static_thresholds_config`), **not** `auto_inject`/`auto_extract`.
Where this doc mentions `auto_inject` below, it is describing the *existing* kernel-memory
injection path a condition relies on — not the gating contract being verified.

## Where the `_run_*` methods live

All four condition methods are defined on `MethodPipeline` in
`benchmarks/shared_memory/pipeline.py`:

- `_run_kernel_shared` — line 517
- `_run_naive_concat` — line 540
- `_run_vanilla_rag` — line 609
- `_run_mem0_default` — line 716

Dispatch happens in `MethodPipeline.run_trial()` (pipeline.py ~500–515), which routes by
`self.method`. There are no other `_run_*` condition variants — the only other `_run_*`
hits in the repo are unrelated test helpers and `run_evaluation.py`'s
`_run_legacy_condition` / `_run_method` orchestration wrappers (the legacy path ultimately
runs the same `AgentPipeline`).

## The shared terminal call path (all four conditions)

Every condition ends by calling `AssistantAgent.run()`
(`cerebrum/example/agents/assistant_agent/agent.py`), which issues a single `llm_chat(...)`
(agent.py:56) →  `send_request(agent_name, LLMQuery, base_url)` (`cerebrum/llm/apis.py:298`)
→  `post(base_url, "/query", ...)` (`cerebrum/utils/communication.py:71`).

So **all four conditions hit the AIOS kernel `/query` endpoint.** That fact alone is not
what makes the gating contract relevant. What matters is whether a condition *claims to be a
gating-controlled condition* — i.e. whether the pre-flight has anything to verify against.
The verification trigger is the **requested condition name**
(`kernel_shared` / `kernel_shared_tuned` / `kernel_shared_adaptive`), not whether the
underlying transport happens to be shared code.

Note on the grep result: the earlier draft claimed "no `/memory/gating_status` endpoint
exists in the repo." That observation is **non-informative and has been removed as a
finding** — the endpoint lives server-side in AIOS (out of scope here), so its absence from
the Cerebrum repo is expected regardless of whether it exists, and it is not evidence about
the contract one way or the other.

## Per-condition call path and gating dependency

| Condition | What it calls | Gating state applies? | Why |
|-----------|---------------|-----------------------|-----|
| `kernel_shared` | `_run_kernel_shared` → `AgentPipeline(share_memory=True).run_trial()` → ProfileAgent + TaskAgent write **shared** memories via `create_memory` to the kernel, then AssistantAgent `llm_chat`→`/query`. Relies on kernel `auto_inject` to surface cross-agent shared memories, and reads `injection_diagnostics` from the response. | **YES** | This is the only condition whose *result depends on* the kernel's memory-gating behavior. Writes go to the kernel store with `sharing_policy="shared"`; correct behavior requires kernel `auto_inject` ON so those memories are injected into the AssistantAgent prompt. A gating-status pre-flight is meaningful here. |
| `mem0_default` | `_run_mem0_default` → `AgentPipeline(share_memory=False).run_trial()` → same 3-agent pipeline, but ProfileAgent/TaskAgent write **private** memories (`sharing_policy="private"`); AssistantAgent `llm_chat`→`/query`. | **NO (resolved — see below)** | Shares the kernel-backed transport with `kernel_shared`, but it does not *claim* to be a gating-controlled condition. The pre-flight is triggered by the requested condition name, and `mem0_default` isn't one of the three gating tiers — so there is nothing for it to verify against. The wire-path overlap is incidental. |
| `naive_concat` | `_run_naive_concat` builds a plain-text context block from synthetic profile+task, prepends it to the query, and calls `AssistantAgent.run()`. **No `create_memory`, no `search_memories`, no memory endpoint.** `written_memories=[]`, `retrieved_context_count=0`. | **NO** | Pure string concatenation. It hits `/query` only to run the LLM; nothing is written to or retrieved from the kernel memory store, so `auto_inject`/`auto_extract` gating has nothing to act on. |
| `vanilla_rag` | `_run_vanilla_rag` builds context chunks, runs a **local scikit-learn TF-IDF + cosine similarity** retrieval (`TfidfVectorizer`, `cosine_similarity`), injects top-k chunks into the prompt, then calls `AssistantAgent.run()`. **No kernel memory or Mem0 API is called.** | **NO** | Retrieval is entirely local/in-process against an in-memory TF-IDF index with no relationship to AIOS's gating config. It hits `/query` only for the LLM call. |

## Non-goal assumption: confirmed

The assumption *"naive_concat / vanilla_rag / mem0_default don't need a `gating_status`
pre-flight verification"* holds for all three, though for two different reasons:

- **`naive_concat` and `vanilla_rag`** — genuinely no kernel memory path at all. `naive_concat`
  is plain concatenation; `vanilla_rag` retrieves from a local TF-IDF index. Their only kernel
  contact is the `/query` LLM call. Nothing to gate, nothing to verify.

- **`mem0_default`** — shares the kernel-backed transport with `kernel_shared`
  (identical `AgentPipeline`, only `share_memory=False` → `sharing_policy="private"`;
  pipeline.py:737-739). This overlap was worth surfacing so it wasn't missed. But the wire-path
  overlap does **not** pull it into verification scope: the pre-flight is triggered by the
  requested condition name, and `mem0_default` does not claim to be a gating-controlled
  condition, so there is nothing for the check to verify against.

## Resolved decision: no `gating_status` verification for `mem0_default`

Recorded explicitly per the master prompt's "confirm or report" requirement:

- The pre-flight `GET /memory/gating_status` verification is scoped to runs targeting
  **`kernel_shared` / `kernel_shared_tuned` / `kernel_shared_adaptive`** — gated on the
  requested condition, not on shared transport code.
- `mem0_default` gets **no verification call**, even though it routes through the same
  kernel `/query` path, because it isn't asserting a gating tier. This is a deliberate
  resolution, not an open question.

## Scope recommendation (for subtask 4/5)

- **In scope:** the three gating tiers — `kernel_shared`, `kernel_shared_tuned`,
  `kernel_shared_adaptive`. The pre-flight reads `GET /memory/gating_status`
  (`adaptive_policy_enabled` / `static_thresholds_enabled` / `static_thresholds_config`) and
  verifies the kernel is in the state the requested tier expects.
- **Out of scope (confirmed):** `naive_concat`, `vanilla_rag` (no kernel memory path) and
  `mem0_default` (kernel transport, but not a gating-controlled condition — resolved above).
- **Do NOT** wire the verification to `auto_inject`/`auto_extract`; those are the pre-existing
  injection toggles, a separate mechanism from the adaptive/static gating contract.

## Line references

- `MethodPipeline.run_trial` dispatch: `benchmarks/shared_memory/pipeline.py:~500-515`
- `_run_kernel_shared`: pipeline.py:517-539 (`AgentPipeline(share_memory=True)`, pipeline.py:537)
- `_run_naive_concat`: pipeline.py:540-608 (`written_memories=[]`, `retrieved_context_count=0`, pipeline.py:600-606)
- `_run_vanilla_rag`: pipeline.py:609-715 (TF-IDF import pipeline.py:~628-629; "No kernel memory or Mem0 API is called" docstring pipeline.py:~615-621)
- `_run_mem0_default`: pipeline.py:716-742 (`AgentPipeline(share_memory=False)`, pipeline.py:737)
- Shared terminal call: `AssistantAgent.run` → `llm_chat` at agent.py:56; `send_request`→`/query` at `cerebrum/llm/apis.py:298` and `cerebrum/utils/communication.py:71`
- `auto_inject` / `auto_extract` (pre-existing injection toggles — **adjacent context, NOT the
  gating contract**): `aios/config/config_loader.py:66-68`
- `GET /memory/gating_status` is a server-side AIOS contract (out of scope to search/modify
  here); trusted as given. Its absence from the Cerebrum repo is expected and non-informative.

---

# Subtask 2 — Insertion points for tuned/adaptive conditions (re-confirmed)

**Investigation only. No source files were modified.** Line numbers verified against the
live repo on this pass (not carried over from the prior investigation). Where the prior pass's
assumptions drifted, it is called out explicitly.

## Category 1 — the valid-condition-names constant

- **Name / location:** `_ALL_METHODS`, `benchmarks/shared_memory/run_evaluation.py:66`
- **Current content:**
  ```python
  # All valid method names (excluding the meta-value "all")
  _ALL_METHODS = ["kernel_shared", "naive_concat", "vanilla_rag", "mem0_default"]
  ```
- **Used at:** `run_evaluation.py:607` (`methods_to_run = list(_ALL_METHODS)` when `--method all`).
- **Drift from prior assumption:** The prior investigation (subtask 1) said this constant
  lived in `pipeline.py`. **DRIFT — it does not.** `_ALL_METHODS` is defined in
  `run_evaluation.py:66`, module-level, not in `pipeline.py`. `pipeline.py` has no analogous
  constant — its `MethodPipeline` validates method names only via the dispatch chain (Category 3).
  Subtasks 4–6 must edit `run_evaluation.py:66`, not `pipeline.py`, for the constant.
- **Note for subtask 4:** the meta-value `"all"` is **not** in `_ALL_METHODS` (excluded by
  design, per the comment) but **is** in the `--method` argparse `choices` (Category 2). Adding
  the two new tiers means editing both the constant and the choices list — they are maintained
  separately.

## Category 2 — argparse `choices=` lists constraining condition/method selection

Two flags in the **same** parser (`build_arg_parser()` in
`benchmarks/shared_memory/run_evaluation.py`), and no others anywhere in the benchmark tooling:

- **`--method`** — `run_evaluation.py:132`
  ```python
  parser.add_argument(
      "--method",
      choices=["kernel_shared", "naive_concat", "vanilla_rag", "mem0_default", "all"],
      default="kernel_shared",
      ...
  ```
- **`--condition`** — `run_evaluation.py:122` (legacy)
  ```python
  parser.add_argument(
      "--condition",
      choices=["both", "phase1", "phase2"],
      default=None,
      ...
  ```
  Legacy: `phase1` → `kernel_shared` share_memory=False, `phase2` → share_memory=True. The
  new tuned/adaptive tiers belong on `--method`, not here — `--condition` should be left alone.

- **Confirmed flag names:** the master prompt's "`--condition`/`--method`" is accurate; both
  exist, both in `run_evaluation.py`.
- **Is the list duplicated in a separate analysis/reporting CLI? NO (with nuance).** The
  master prompt warned there may be a second CLI (e.g. a reporting tool) duplicating the list.
  Checked: `assert_injection_rate.py` (post-run gate) and the `benchmarks/human_rating/*` CLIs
  do **not** re-declare a method/condition `choices` list. The method names are, however,
  **hard-coded as literals in tests** — `tests/agents/test_unified_trial_data_props.py:225`,
  `tests/agents/test_results_writer.py:91`, and `tests/agents/test_results_writer.py` filename
  assertions. These are not `choices=` lists and are out of implementation scope, but new-tier
  work should expect some of these tests to need updating.
- **Drift:** none for the production CLI — single parser, two flags, exactly where expected.

## Category 3 — the dispatcher (name string → `_run_*` method)

- **Location:** `MethodPipeline.run_trial()`, `benchmarks/shared_memory/pipeline.py:502-513`
- **Current mapping (if/elif chain, not a dict):**
  ```python
  method_user_id = f"{trial_data.user_id}__{self.method}"   # line 502
  if self.method == "kernel_shared":                        # line 503
      return self._run_kernel_shared(trial_data, method_user_id)
  elif self.method == "naive_concat":                       # line 505
      return self._run_naive_concat(trial_data, method_user_id)
  elif self.method == "vanilla_rag":                        # line 507
      return self._run_vanilla_rag(trial_data, method_user_id)
  elif self.method == "mem0_default":                       # line 509
      return self._run_mem0_default(trial_data, method_user_id)
  else:                                                     # line 512
      raise ValueError(f"Unknown method: {self.method!r}. ...")
  ```
- **Drift from prior assumption:** subtask 1 said "likely a dict lookup or if/elif chain in
  pipeline.py's MethodPipeline." **Confirmed — it is an if/elif chain** (not a dict), in
  `MethodPipeline.run_trial`, at pipeline.py:502-513. Location matches; the "dict lookup"
  half of the guess does not apply.
- **Note for subtask 4/5:** adding tiers means new `elif` branches here plus the corresponding
  `_run_kernel_shared_tuned` / `_run_kernel_shared_adaptive` methods. The `method_user_id`
  namespacing pattern (`{user_id}__{method}`) at line 502 applies uniformly, so new tiers get
  isolated memory namespaces automatically.

## Category 4 — `ExperimentMetadata` and `TrialResult` (field collision check)

Both are Pydantic `BaseModel`s in `benchmarks/shared_memory/models.py`.

### `TrialResult` — models.py:154-188 (full current field list)
```
trial_index: int
condition: str
method: str = ""
profile_usage_score: Optional[int] = None
task_usage_score: Optional[int] = None
integration_score: Optional[int] = None
memory_counts: MemoryCounts = MemoryCounts()
retrieved_context_count: Optional[int] = None
latency_seconds: Optional[float] = None
follow_up_query: str = ""
assistant_response: str = ""
synthetic_profile: Optional[SyntheticProfile] = None
synthetic_task_context: Optional[SyntheticTaskContext] = None
retrieval_log: Optional[RetrievalLog] = None
injection_diagnostics: Optional[InjectionDiagnostics] = None
written_memories: List[WrittenMemoryRecord] = []
failed: bool = False
error_message: Optional[str] = None
token_usage: Optional[Dict[str, Optional[int]]] = None
policy_action: Optional[List[PolicyActionEntry]] = None
```

### `ExperimentMetadata` — models.py:219-225 (full current field list)
```
trials_per_condition: int
timestamp: str
kernel_url: str
conditions_run: List[str]
methods_run: List[str] = []
```

- **Drift from prior assumption — IMPORTANT.** `TrialResult` already carries **two fields the
  prior investigation likely predates**: `token_usage` (models.py:180) and
  `policy_action: Optional[List[PolicyActionEntry]]` (models.py:188). `ExperimentMetadata`
  already carries `methods_run` (models.py:225). If subtask 6 planned to add any of these
  names, they **already exist** — re-adding would collide. Confirm subtask 6's intended new
  field names against these lists before implementing.
- **Supporting type present:** `PolicyActionEntry` (models.py:137, fields `bandit`, `arm_index`,
  `reward`, `memory_id`) already exists — the adaptive-policy reward plumbing on the *data-model
  side* is partly in place via the standalone post-hoc join
  (`join_policy_actions.py`), per the field comment at models.py:181-188. This is consistent
  with prior context that only the join/model side exists, not the live adaptive policy.
- **Additivity guidance:** any subtask-6 additions should remain `Optional[...] = None` (or a
  default) to stay backward-compatible with existing serialized results, matching the pattern
  of `token_usage` / `policy_action` / `methods_run`.

## Summary of drift called out

| Item | Prior assumption | Actual (this pass) |
|------|------------------|--------------------|
| `_ALL_METHODS` location | `pipeline.py` | `run_evaluation.py:66` — **drift** |
| Dispatcher form | dict lookup *or* if/elif | if/elif chain, pipeline.py:502-513 — confirmed |
| CLI choices duplication | maybe a 2nd reporting CLI | only one parser (`run_evaluation.py`); method names also hard-coded in tests |
| `TrialResult` fields | (pre-`token_usage`/`policy_action`?) | already has `token_usage`, `policy_action` — **drift, collision risk** |
| `ExperimentMetadata` fields | (pre-`methods_run`?) | already has `methods_run` — **drift, collision risk** |

---

# Subtask 3 — Natural home for the `gating_status` pre-flight check (confirmed)

**Investigation only. No source files were modified.** Two checks from the prior discussion
were folded in and are resolved below before the main finding.

## Folded-in check A — does `EvaluationOrchestrator` actually exist?

**YES — verified by grep, not recollection.** `grep 'class \w*Orchestrator'` returns exactly
one match repo-wide: `class EvaluationOrchestrator:` at
`benchmarks/shared_memory/run_evaluation.py:192`. There is no other orchestrator class
anywhere, and it is **not** in a separate `orchestrator.py` / `pipeline.py`. So the prior
investigation's "EvaluationOrchestrator is the natural home" names a real class — the open
question was only *which method within it* (resolved below), not whether it exists.

## Folded-in check B — what populates the pre-existing scaffolding fields today?

Resolved by `grep 'policy_action|token_usage|methods_run'`:

- **`token_usage`** — LIVE, fully threaded: kernel response → `AssistantAgent.run()`
  (agent.py:66, :74) → `PipelineResult` (pipeline.py:194/606/713) → `TrialResult`
  (run_evaluation.py:522). Also a field on `LLMResponse` (cerebrum/llm/apis.py:214).
- **`methods_run`** — LIVE, written by the orchestrator at run_evaluation.py:678.
- **`policy_action`** — populated **only post-hoc** by the standalone
  `benchmarks/shared_memory/join_policy_actions.py:192`, joining the kernel's
  `policy_trials.jsonl` reward events on `reward.trial_id == trial_index`. **Not threaded
  through the live trial loop** (`AssistantAgent`/`PipelineResult` untouched, per models.py:183-188
  and the join script docstring). This is **outcome-side** (which bandit/arm was credited).
  The **decision-side `select` records are explicitly NOT joinable** (their `trial_id` is
  always null — models.py:145-146).

**Design consequence for subtask 6 (agreed):** gating provenance = *what tier/config was live
when the trial ran* = **decision-side, pre-trial**. `policy_action` = **outcome-side, post-hoc**.
They are different fields and must not be merged. Subtask 6's new gating-provenance field
should be a **distinct** `Optional[...] = None`, additive field on `TrialResult`, documented in
the same style as `policy_action` (explicit None-vs-empty semantics), but populated on the
live path (pre-trial), not by the post-hoc reward join.

## Main finding — where the pre-flight `GET /memory/gating_status` check belongs

`EvaluationOrchestrator` has two run paths (`run()` at run_evaluation.py:526 dispatches):

- `_run_legacy_condition()` — run_evaluation.py:548, the `--condition phase1/phase2` path.
- `_run_method()` — run_evaluation.py:603, the `--method` path (the one that reaches the new
  `kernel_shared` / `kernel_shared_tuned` / `kernel_shared_adaptive` tiers).

The per-method loop that constructs a pipeline and runs trials is in `_run_method()`:

```python
for method_name in methods_to_run:                                  # run_evaluation.py:613
    pipeline = MethodPipeline(method=method_name, ...)              # :614
    logger.info("Running method '%s'.", method_name)               # :615
    ...
    for i in tqdm(range(self.trials), ...):                        # per-trial loop
        result = self.run_single_trial(i, method_name, pipeline, ...)
```

**Recommended insertion point: inside `_run_method()`, at the top of the
`for method_name in methods_to_run:` loop body (run_evaluation.py:~613-615), immediately
after the `MethodPipeline` is constructed and before the per-trial loop begins.** Rationale:

1. **Right granularity — once per method, pre-trial.** The check should run before any trials
   for a gating-controlled method execute (a pre-flight), and only for the requested method.
   The top of the per-method loop is exactly that boundary. Putting it deeper (in
   `run_single_trial`, run_evaluation.py:311) would re-issue the check every trial — wasteful
   and wrong granularity for a config pre-flight.
2. **Condition-name gating is trivial here.** `method_name` is in scope, so gating the check to
   `method_name in {"kernel_shared", "kernel_shared_tuned", "kernel_shared_adaptive"}`
   (subtask 1's resolved scope — excludes `naive_concat`/`vanilla_rag`/`mem0_default`) is a
   one-line guard at this location.
3. **The HTTP-call pattern already exists in this file — mirror it, don't invent it.**
   `run_single_trial` already issues `requests.post(f"{config.get_kernel_url().rstrip('/')}/memory/report_reward", ...)`
   at run_evaluation.py:~465-470 (a dedicated `/memory/*` route, **not** `/query`). The
   `gating_status` pre-flight is the read-side analogue:
   `requests.get(f"{config.get_kernel_url().rstrip('/')}/memory/gating_status", timeout=...)`.
   `requests` (run_evaluation.py:36) and `config` (:61) are already imported — no new deps.
4. **`_run_legacy_condition()` is out of scope.** The legacy `phase1/phase2` path never targets
   the new tiers, so no pre-flight is added there. (Consistent with subtask 1: legacy maps to
   `kernel_shared` share_memory on/off, and the tuned/adaptive tiers live only on `--method`.)

### Natural home: confirmed with a refinement

- **Confirmed:** `EvaluationOrchestrator` (run_evaluation.py:192) is the correct home — not
  `MethodPipeline` in pipeline.py. `MethodPipeline` runs a single trial with no notion of
  "before the batch"; the orchestrator owns the per-method batch loop and already owns kernel
  HTTP calls (`report_reward`) and kernel URL resolution (`self.kernel_url`, :230).
- **Refinement:** the precise insertion point is the **`_run_method()` per-method loop head
  (run_evaluation.py:~613-615)**, not the orchestrator broadly and not `run_single_trial`.
  Optionally the check result is cached per method_name to avoid a redundant call under
  `--method all` (though `all` doesn't include the gating tiers today, so in practice the
  guard short-circuits for the four current methods).

## Drift / correction to my own subtask-2 note

- Subtask 2 mentioned `EvaluationOrchestrator.__init__` "at line ~194"; the **class** is at
  run_evaluation.py:192 and `__init__` begins shortly after — corrected here for precision.
- No other drift: `_ALL_METHODS` (:66), the two `choices` lists (:122 `--condition`, :132
  `--method`), and the `MethodPipeline` dispatcher (pipeline.py:502-513) are unchanged from the
  subtask-2 reading.

## Line references (this pass)

- `class EvaluationOrchestrator`: run_evaluation.py:192 (only `*Orchestrator` in repo)
- `run()` dispatch: run_evaluation.py:526 → `_run_legacy_condition` (:548) / `_run_method` (:603)
- **Recommended pre-flight insertion point:** `_run_method()` per-method loop head,
  run_evaluation.py:~613-615 (after `MethodPipeline(...)`, before the `tqdm` trial loop)
- Existing kernel HTTP pattern to mirror: `requests.post(.../memory/report_reward)` at
  run_evaluation.py:~465-470; `requests` import at :36, `config` import at :61
- `policy_action` sole writer (post-hoc, outcome-side): join_policy_actions.py:192
- `token_usage` live writers: agent.py:66/74, pipeline.py:194/606/713, run_evaluation.py:522
- `methods_run` writer: run_evaluation.py:678
