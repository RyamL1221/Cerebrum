# Subtask 1 findings: `policy_trials.jsonl` existence and schema

Ground-truth investigation performed before any code changes, per the master
prompt's requirement that the adaptive-policy trial log be checked, not assumed.
All findings below come from real inspection of the on-disk file and the AIOS
source that writes it. Nothing in the schema was invented.

## Environment note

The adaptive-policy trial log is written by the **AIOS kernel repo**, which on
this machine is a sibling of the Cerebrum workspace:

- AIOS repo root: `.../VSCode/AIOS`
- Cerebrum workspace root: `.../VSCode/Cerebrum`

Inspection of the AIOS repo was read-only (no edits), consistent with the
AIOS-repo non-goal.

## (a) Does the file exist?

**Yes.** The configured path was confirmed from source, not hardcoded.

- `aios/config/config.yaml` → `memory.adaptive_policy.trial_log: "logs/policy_trials.jsonl"`
  (relative to the AIOS repo root).
- `memory.adaptive_policy.enabled: true` and `alpha: 1.0` are set, so the
  logger is active (it is inert whenever `trial_log` is unset).
- The file exists on disk at `<AIOS repo root>/logs/policy_trials.jsonl`.

## (b) Is it populated?

**Yes.** The file contains **324 JSONL records** (one trailing newline).

Breakdown by record type (`event` field):

| `event`  | count |
|----------|-------|
| `select` | 133   |
| `reward` | 191   |

- `reward` values observed range **0.9 – 5.0** (distinct values include 0.9,
  1.0, 3.333…, 3.666…, 4.333…, 5.0), i.e. the 1–5 judge scale plus early
  probe/verification writes.
- `trial_id` appears as three JSON types across records: integer (180),
  `null` (125), and string (19). Distinct values include the benchmark trial
  indices `0`–`14`, plus the manual markers `"probe"` and
  `"trial-subtask3-verify"`. `null` corresponds to selections/rewards made with
  no benchmark trial id supplied by the caller.

The presence of integer, string, and `null` `trial_id` values matters for
Subtask 2: any join/parse logic must treat `trial_id` as a **heterogeneously
typed, nullable** join key (normalize to string; skip `null`), not assume a
uniform type.

## (c) Actual field schema (from real data + source)

The real schema is a **discriminated union keyed on `event`**, not the flat
`{trial_id, bandit, arm, reward_value, timestamp}` shape assumed in the Subtask
1 brief. The authoritative writer is
`aios/memory/policy_log.py` (`PolicyTrialLogger.log_select` / `log_reward`,
serialized via `_write`, which also injects `ts` via `setdefault`).

### `event: "select"` — a bandit chose a threshold for a gate decision

Observed keys (exhaustive across all `select` records):
`event, trial_id, bandit, gate, value, arm_index, llm_core, task_type, context, ts`

| field       | type / meaning                                                        |
|-------------|-----------------------------------------------------------------------|
| `event`     | `"select"`                                                            |
| `trial_id`  | benchmark trial id (join key) — int, string, or `null`               |
| `bandit`    | bandit name: `novelty_threshold` / `similarity_threshold` / `redundancy_threshold` |
| `gate`      | decision role: `novelty` / `similarity` / `redundancy`               |
| `value`     | selected threshold value (float, e.g. 0.2, 0.5, 0.7)                 |
| `arm_index` | selected arm index (int)                                             |
| `llm_core`  | context feature — model name (e.g. `qwen2.5:7b`, `unknown`)          |
| `task_type` | context feature — `profile` / `task_context` / `""`                  |
| `context`   | context feature vector as a JSON list of floats (length 8 observed) |
| `ts`        | epoch seconds (float)                                                |

Example (real line):
```json
{"event": "select", "trial_id": "trial-subtask3-verify", "bandit": "similarity_threshold", "gate": "similarity", "value": 0.2, "arm_index": 0, "llm_core": "qwen2.5:7b", "task_type": "profile", "context": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0], "ts": 1788466238.253654}
```

### `event: "reward"` — a reward was applied to one bandit decision

Observed keys (exhaustive across all `reward` records):
`event, trial_id, bandit, arm_index, reward, memory_id, ts`

| field       | type / meaning                                                |
|-------------|---------------------------------------------------------------|
| `event`     | `"reward"`                                                   |
| `trial_id`  | benchmark trial id (join key) — int, string, or `null`      |
| `bandit`    | bandit name                                                 |
| `arm_index` | arm the reward was applied to (int)                         |
| `reward`    | scalar reward value (float; 1–5 judge scale in real trials) |
| `memory_id` | the `memory_id` whose decision this reward updated (string) |
| `ts`        | epoch seconds (float)                                       |

Example (real line):
```json
{"event": "reward", "trial_id": 14, "bandit": "redundancy_threshold", "arm_index": 0, "reward": 5.0, "memory_id": "731d994d-ef69-463d-bb0c-81f90dc103a2", "ts": 1788468234.464823}
```

## Reconciliation with the Subtask 1 assumption

The brief anticipated fields `trial_id, bandit, arm, reward_value, timestamp`.
Actual mapping:

- `arm` → **`arm_index`** (present in both event types).
- `reward_value` → **`reward`** (only on `reward` records).
- `timestamp` → **`ts`** (epoch-seconds float, present on all records).
- `trial_id`, `bandit` → present as expected, but `trial_id` is nullable and
  heterogeneously typed.
- **Extra fields not in the assumption:** `event` (the discriminator),
  `gate`, `value`, `llm_core`, `task_type`, `context` (on `select`), and
  `memory_id` (on `reward`).
- There is **no single flat record** carrying both a threshold and a reward;
  selections and rewards are separate records joined by `trial_id` (and, for
  rewards, `memory_id` / `bandit` / `arm_index`).

## Decision-gate inputs (for Task 7)

- File exists: **yes**.
- File populated: **yes** (324 records; 133 `select`, 191 `reward`).
- Real reward signal present: **yes** (values 0.9–5.0, including benchmark
  trials `0`–`14`).
- Schema source: real file inspection cross-checked against
  `aios/memory/policy_log.py` — **not invented**.
- Caveat for downstream code: `trial_id` is nullable and appears as int /
  string / `null`; the log is a discriminated union on `event`, so parsers must
  branch on `event` and normalize `trial_id`.

---

# Subtask 2 findings: `trial_id` compatibility between the benchmark and the policy log

Establishes whether the benchmark-side trial identifier and the `trial_id`
values in `policy_trials.jsonl` (int / string / `null`, per Subtask 1) can be
joined. This is the load-bearing check the `policy_action` feature depends on.
Every claim below is traced to code or to the real log data — not asserted.

## Correction to the brief: the benchmark field is `trial_index`, not `trial_id`

There is **no `trial_id` field on `TrialResult`**. The model
(`benchmarks/shared_memory/models.py`, `class TrialResult`) declares:

```python
class TrialResult(BaseModel):
    trial_index: int
    condition: str
    method: str = ""
    ...
```

So the benchmark-side identifier is `trial_index: int`. The name `trial_id`
only appears on the *wire* to the kernel (see below), where `trial_index` is
sent under the key `"trial_id"`.

## Where `trial_index` comes from (real format)

In `run_evaluation.py`, trials are enumerated by a bare zero-based loop counter,
not a composite string:

```python
for i in tqdm(range(self.trials), desc=f"Method: {method_name}"):
    result = self.run_single_trial(i, method_name, pipeline, ...)
```

`run_single_trial(trial_index=i, ...)` then stores it verbatim as
`TrialResult(trial_index=trial_index, ...)`. So for a run of N trials the
benchmark trial identifiers are exactly the integers `0, 1, ..., N-1`. There is
**no** `"gpt-4o-kernel_shared-task-014"`-style composite id anywhere; method and
condition are carried in separate fields (`method`, `condition`), not folded
into the id.

## How `trial_index` reaches the kernel (and becomes a policy-log `trial_id`)

Only **one** harness path sends a trial identifier to the kernel — the
`report_reward` call in `run_single_trial`:

```python
reward_metadata = {**trial_metadata, "trial_id": trial_index}
reward_response = requests.post(
    f"{config.get_kernel_url().rstrip('/')}/memory/report_reward",
    json={"agent_name": "assistant_agent",
          "memory_ids_involved": memory_ids_involved,
          "reward_value": reward_value,
          "trial_metadata": reward_metadata},
    timeout=30,
)
```

So the integer `trial_index` is what the kernel's PolicyManager receives as
`trial_metadata["trial_id"]`, and (per Subtask 1's read of
`aios/memory/policy_log.py`) it is written verbatim into **`reward`** records.

Critically, the **add/retrieve path does not send any trial id.** The pipeline's
`create_memory` / `search_memories` / `llm_chat` calls
(`benchmarks/shared_memory/pipeline.py`) pass metadata containing only
`owner_agent`, `memory_type`, `sharing_policy`, and `user_id` — never
`trial_id`. Since **`select`** records take their `trial_id` from the
add/retrieve query metadata, the harness leaves it unset → the kernel logs
`trial_id: null` for them.

## Cross-reference against the real log data

Grouping every record by `(event, python-type-of-trial_id)`:

| event    | trial_id type | count | source                                              |
|----------|---------------|-------|-----------------------------------------------------|
| `reward` | int           | 180   | benchmark `report_reward` (`trial_index` 0–14)      |
| `reward` | str           | 11    | manual markers (`probe`, `trial-subtask3-verify`)   |
| `select` | null          | 125   | harness add/retrieve — **no trial_id sent**         |
| `select` | str           | 8     | manual markers                                      |

The integer `reward` trial_ids are exactly `{0,1,...,14}` — i.e. the
`trial_index` values of a 15-trial benchmark run. **No integer ever appears on a
`select` record**, and **no `null` ever appears on a `reward` record.** This
matches the code paths above precisely and is strong evidence that the integers
in the log are the benchmark loop indices, not an unrelated namespace.

## Determination: joinable by DIRECT INTEGER MATCH, on `reward` records only

- **`reward` records ↔ `TrialResult`: DIRECT MATCH (no transform).**
  `TrialResult.trial_index` (int) equals the policy-log `reward.trial_id` (int)
  one-for-one within a run. Joining is `policy_reward.trial_id == trial.trial_index`.
  This is the join the `policy_action` reward-attribution feature needs, and it
  works directly.

  Caveat — **per-run only, not globally unique.** Because ids restart at 0 each
  run, joining across multiple runs requires an out-of-band run discriminator
  (the log has no run id / the ids collide between runs). Within a single run,
  or when the log is truncated/segmented per run, the direct match is exact.

- **`select` records ↔ `TrialResult`: NOT JOINABLE as-is (all `null`).**
  The harness never propagates `trial_index` onto add/retrieve queries, so all
  125 `select` records carry `trial_id: null`. There is no key to join a
  selection to a benchmark trial today. Joining `select`↔trial would require an
  upstream change (thread `trial_index` through the pipeline's add/retrieve
  metadata) — that is a code change on the harness+kernel boundary, not a
  transform of existing data.

- **String-marker records (`probe`, `trial-subtask3-verify`): EXCLUDE.**
  These are manual/non-benchmark writes and do not correspond to any
  `TrialResult`. Filter them out before joining (`trial_id` not an int, or not
  in the run's `trial_index` set).

## Caveats for Subtask 7's go/no-go decision gate

1. **The 125 `null`-trial_id records are all `select` events** and are **not
   joinable** to benchmark trials. If `policy_action` needs selection-time
   context (which threshold/arm was chosen for a given trial), that data cannot
   be attributed today without threading `trial_index` into add/retrieve
   metadata (upstream change). Reward attribution — the primary need — does
   **not** depend on the `select` records and is unaffected.

2. **Mixed-type `trial_id`.** Any join/parse must (a) branch on `event`,
   (b) treat `trial_id` as nullable, (c) accept only integer `trial_id` values
   for benchmark joins, and (d) drop string markers. Normalizing everything to
   `str()` would silently merge the `"probe"`/`"trial-subtask3-verify"` markers
   into the join space and is unsafe.

3. **Non-uniqueness across runs.** Integer ids restart per run; without a run
   discriminator in the log, a multi-run corpus cannot be joined unambiguously.
   Single-run joins are exact.

**Bottom line:** trial_id is **directly joinable (integer equality) for the
`reward` records** that carry the benchmark's `trial_index`, which is exactly
what reward attribution requires. It is **incompatible/unjoinable for the
`select` records** (all `null`) and for the manual string markers (excluded),
pending an upstream change to thread `trial_index` into add/retrieve metadata.

---

# Subtask 3 findings: re-confirming the `token_usage` drop point across the live call path

Re-verified against the current repo state, hop by hop, with the same
evidentiary bar as Subtasks 1–2. The master prompt's drop-point description
**holds**, with two clarifications where the code differs from its wording
(both flagged below). Every claim is traced to current code.

## Hop 1 — Kernel `/query` response shape (authoritative, from AIOS source)

Confirmed from the sibling AIOS repo (read-only), not from the prompt alone:

- `runtime/launch.py` `@app.post("/query")` → `handle_query` for `query_type ==
  "llm"` calls `execute_request(...)` and **returns `result_dict` directly**
  (FastAPI JSON-serializes it; no rewrapping).
- `aios/syscall/syscall.py` `execute_request` for `action_type == "chat"`
  returns the dict built by `execute_llm_syscall`, which is:
  ```python
  return {
      "response": completed_response,          # an LLMResponse object
      "token_usage": syscall.get_token_usage(),  # TOP-LEVEL SIBLING
      "start_times": ..., "end_times": ...,
      "waiting_times": ..., "turnaround_times": ...,
  }
  ```
  The inline comment states the intent explicitly: token usage rides on the
  `Syscall` object and is surfaced "as a sibling key so it reaches the HTTP
  body," precisely because the Cerebrum `LLMResponse` "is an external installed
  package and must not be edited."
- `get_token_usage()` returns either `None` or a dict
  `{"prompt_tokens", "completion_tokens", "total_tokens"}` (each value an int or
  `None`; `set_token_usage` leaves missing values as `None` rather than 0).

**Confirmed:** `token_usage` is a **top-level sibling** of `response` in the
`/query` body — NOT nested under `response`. When FastAPI serializes the
`LLMResponse` object under `"response"`, that nested object carries its own
`token_usage` field too (see Hop 3), but that nested one is the SDK model's
field, which the kernel does not populate — the populated value is the sibling.

## Hop 2 — `send_request()` returns the raw dict (confirmed)

`cerebrum/utils/communication.py`: `send_request` calls `post(...)`, which does
`response.raise_for_status(); return response.json()`. So `send_request` returns
the **raw parsed JSON dict**, not a deserialized `LLMResponse`. Confirmed.

## Hop 3 — `llm_chat()` return type (DRIFT from prompt, clarified)

`cerebrum/llm/apis.py`:
- `llm_chat(...)` is annotated `-> LLMResponse` but its body is
  `return send_request(agent_name, query, base_url)` — i.e. it returns the
  **raw dict**, not an `LLMResponse`. The annotation is misleading/aspirational.
- **DRIFT:** the master prompt says token_usage is "not populated on the SDK's
  `LLMResponse.token_usage`." In fact the SDK model **does declare the field**:
  `LLMResponse.token_usage: Optional[Dict[str, Optional[int]]] = None`
  (`apis.py`). The nuance the prompt gets slightly wrong: the field *exists on
  the model* but is irrelevant on the live path because `llm_chat` never
  constructs/validates an `LLMResponse` — it returns the raw dict. So at runtime
  the assistant sees a plain dict whose real per-call usage lives at the
  top-level sibling `response["token_usage"]`, exactly as the prompt concludes.
  Net effect is identical to the prompt's claim; the mechanism differs.

## Hop 4 — `AssistantAgent.run()` (confirmed, verbatim)

`cerebrum/example/agents/assistant_agent/agent.py`, `run()`:
```python
response = llm_chat(agent_name=..., messages=..., base_url=..., llms=..., user_id=...)
result_text = response["response"]["response_message"] if response else ""
...
return {"agent_name": self.agent_name, "result": result_text, "rounds": self.rounds}
```
**Confirmed literally:** it reads only `response["response"]["response_message"]`
and returns exactly `{"agent_name", "result", "rounds"}`. The top-level sibling
`response["token_usage"]` is **never read** — this is the drop point. The
`except` branch returns the same three keys with an error string.

## Hop 5 — `PipelineResult` (confirmed; carries the raw dict but nothing usable)

`benchmarks/shared_memory/pipeline.py`, `@dataclass PipelineResult` fields:
`profile_result, task_result, assistant_result, assistant_response,
latency_seconds, retrieval_log, injection_diagnostics, written_memories,
method, retrieved_context_count`. **No token field.**

Construction (three sites, one per method path):
`assistant_result = assistant_agent.run(...)` then
`assistant_response = assistant_result.get("result", "")`, and
`PipelineResult(..., assistant_result=assistant_result,
assistant_response=assistant_response, ...)`.

So `PipelineResult.assistant_result` retains the agent's **full return dict** —
but since `AssistantAgent.run()` already discarded `token_usage` upstream (Hop
4), there is nothing token-related to recover here. To surface token usage,
`AssistantAgent.run()` must be changed first (Hop 4), then threaded through
`PipelineResult`.

## Hop 6 — `TrialResult` construction sites (confirmed; NO token field; 4 sites)

`benchmarks/shared_memory/models.py`, `class TrialResult(BaseModel)` — full
field list: `trial_index, condition, method, profile_usage_score,
task_usage_score, integration_score, memory_counts, retrieved_context_count,
latency_seconds, follow_up_query, assistant_response, synthetic_profile,
synthetic_task_context, retrieval_log, injection_diagnostics, written_memories,
failed, error_message`. **No token field anywhere** (repo-wide grep for
`token` in `benchmarks/shared_memory/**/*.py` returns only an unrelated
model-name-parsing docstring).

**All four `TrialResult(...)` construction sites** (all in `run_evaluation.py`)
— every one needs updating in Subtask 6:

1. **`run_single_trial`, success path** (~line 505): the main
   `return TrialResult(...)` with scores, latency, retrieval_log, etc. — the one
   that would carry token usage from `pipeline_result`.
2. **`run_single_trial`, synthetic-data-generation failure** (~line 340):
   `failed=True, error_message=...` early return.
3. **`run_single_trial`, agent-pipeline failure** (~line 353):
   `failed=True, error_message=...` early return (also sets synthetic_profile /
   task_context / follow_up_query).
4. **`_run_method` (`--method all`), synthetic-data-generation failure**
   (~line 632): `trials.append(TrialResult(..., failed=True, error_message=...))`.

Sites 2–4 are error/exception paths with no `pipeline_result`, so any new token
field must default to `None`/absent there; only site 1 has a live
`pipeline_result` to read usage from.

## Drift summary vs. the master prompt

| Prompt claim | Actual code | Verdict |
|---|---|---|
| `AssistantAgent.run()` reads only `response["response"]["response_message"]`, discards token_usage, returns `{agent_name, result, rounds}` | Exactly so | **Confirmed** |
| Kernel emits `token_usage` as a top-level sibling of `response` in `/query`, not nested | Exactly so (`syscall.py` builds `{"response": ..., "token_usage": ...}`) | **Confirmed (from AIOS source)** |
| `token_usage` "not populated on the SDK's `LLMResponse.token_usage`" | The field **does exist** on the model, but is moot because `llm_chat` returns a raw dict, not an `LLMResponse` | **Minor drift — same net effect** |
| `send_request` returns raw JSON dict | Exactly so | **Confirmed** |
| (implied) `llm_chat -> LLMResponse` | Annotated as such but returns raw dict | **Annotation is misleading** |

**Bottom line:** the drop point is real and unchanged — the populated per-call
`token_usage` sibling in the `/query` body is discarded by
`AssistantAgent.run()` and never reaches `PipelineResult` or `TrialResult`.
Subtask 6 must update all four `TrialResult` sites (only site 1 has usage to
populate), after `AssistantAgent.run()` and `PipelineResult` are extended to
carry it. The single drift worth carrying forward: `LLMResponse.token_usage`
already exists as a field, so no SDK model change is needed to *hold* the value
— only the runtime read path (`AssistantAgent.run()`) needs to stop discarding it.
