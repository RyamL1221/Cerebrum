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
