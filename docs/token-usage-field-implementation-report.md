# Implementation Report: `LLMResponse.token_usage` Field (Cerebrum SDK)

## Summary

This report closes out the Cerebrum-side work to add a `token_usage` field to
`LLMResponse`, providing the receiving slot for token accounting data that the
AIOS kernel will populate in a follow-up. The field is additive, `None`-safe by
default, and does not change any existing behavior. Two significant findings
surfaced during investigation and are reported plainly below rather than
silently worked around.

## What Changed (code diffs)

Only two subtasks produced diffs. They are listed here with precise
file + line references.

1. **`cerebrum/llm/apis.py` — field addition (Subtask 2)**
   - Added at line **214**, inside the `LLMResponse` class body, directly after
     `tool_calls`:
     ```python
     token_usage: Optional[Dict[str, Optional[int]]] = None
     ```
   - Matches the bare `Optional[...] = None` style of the sibling `tool_calls`
     (line 213) and `error` (line 216) fields — no `Field(default=...)`.
   - `Optional` and `Dict` were already imported (line 2), so no import change
     was needed.

2. **`tests/apis/llm/test_llm_response.py` — new test file (Subtask 5)**
   - New file with three `unittest.TestCase` cases covering the missing,
     populated, and partial-`None` payload shapes. Follows the existing
     `tests/apis/llm/` convention (`unittest.TestCase` + `unittest.main()`),
     with a `sys.path.insert(0, ".")` so it runs standalone with no kernel.

3. **`.kiro/steering/build-and-test.md` — steering doc edit (Subtask 5)**
   - Added a note that most `tests/apis/llm/` tests need a kernel, but the new
     `test_llm_response.py` is a pure model test that does not, plus its run
     command.

### Investigation-only subtasks (no diffs — called out explicitly)

- **Subtask 1** (locate `LLMResponse`, confirm field conventions) — read-only.
- **Subtask 3** (HTTP round-trip serialization verification) — read-only;
  verification was executed against constructed/mock payloads, no source edits.
- **Subtask 4** (benchmark trial-loop pass-through investigation) — deliberately
  **no diff**. Adding `token_usage` to the results path was found to be
  non-trivial (see Finding 2) and was intentionally not implemented, per the
  master prompt's guidance to stop and report rather than restructure the
  results schema.

## Significant Findings / Deviations

### Finding 1 — The SDK's live path never constructs `LLMResponse` from kernel JSON

`llm_chat` (and its siblings in `cerebrum/llm/apis.py`) are annotated
`-> LLMResponse`, but their bodies `return send_request(...)`. `send_request`
(`cerebrum/utils/communication.py`) calls `post()`, which does
`return response.json()` — i.e. it returns the **raw parsed JSON dict**. There
is no `LLMResponse(**...)` / `model_validate` / `parse_obj` call anywhere in the
live HTTP path. The `LLMResponse` model is currently a schema/documentation
artifact, not the runtime deserialization target.

Consequence for this task: `token_usage` was verified against **both** paths —
- the **raw-dict live path** (what actually runs today): a missing key yields
  `result.get("token_usage") is None` (None-safe); a present key returns the dict.
- the **`LLMResponse.model_validate` path** (the documented/eventual target):
  validates missing, populated, and partial-`None` shapes cleanly, and accepts
  unrecognized extra keys (no `extra="forbid"`), so it is forward-compatible.

This is a deviation from the master prompt's implicit assumption that a single
deserialization call site turns kernel JSON into an `LLMResponse`.

### Finding 2 — The benchmark trial loop does not record `finished`/`error` per trial, and drops `token_usage` before the results row

The master prompt suggested modeling a `token_usage` pass-through on how
`finished`/`error` are recorded per trial. Investigation (Subtask 4) found that
premise does not hold in this harness:

- `AssistantAgent.run()` (`cerebrum/example/agents/assistant_agent/agent.py`)
  reads only `response["response"]["response_message"]` and returns
  `{"agent_name", "result", "rounds"}`. It reads neither `finished` nor `error`,
  and **discards `token_usage`** at this boundary before the pipeline sees it.
- `AgentPipeline`/`MethodPipeline` (`benchmarks/shared_memory/pipeline.py`) read
  only `assistant_result.get("result", "")`. `PipelineResult` (dataclass) has no
  token field.
- `TrialResult` (`benchmarks/shared_memory/models.py`) is a **strict Pydantic
  model** with no token/cost field. Its `failed`/`error_message` fields
  (`run_evaluation.py`, e.g. lines 340/353/632) are set only from Python
  exceptions — **not** from the LLM response's `error` field.

A real pass-through would therefore require changes across three layers (agent
return contract, `PipelineResult` dataclass, `TrialResult` schema + all
construction sites), i.e. a results-schema restructure. Per the prompt's
instruction, this was **not implemented**; it is reported here as remaining work.

## Test Evidence (captured verbatim)

Command:
```bash
python tests/apis/llm/test_llm_response.py -v
```

Output:
```
test_token_usage_absent_defaults_to_none (__main__.TestLLMResponseTokenUsage.test_token_usage_absent_defaults_to_none)
A payload with no token_usage key validates with token_usage=None. ... ok
test_token_usage_partial_none_validates (__main__.TestLLMResponseTokenUsage.test_token_usage_partial_none_validates)
A partial-None token_usage dict validates and preserves the Nones. ... ok
test_token_usage_populated_round_trips (__main__.TestLLMResponseTokenUsage.test_token_usage_populated_round_trips)
A well-formed token_usage dict validates and round-trips exactly. ... ok
----------------------------------------------------------------------
Ran 3 tests in 0.001s
OK
```

## Non-Goals Respected

- **`LLMQuery` was not touched.** Only the `LLMResponse` class body was modified.
- **Nothing outside the Cerebrum repo was touched.** No AIOS kernel files were
  modified. (Verification in Subtask 3 used constructed/mock payloads, not a
  live kernel.)

## Acceptance Criteria (per-criterion confirmation)

1. **`token_usage: Optional[Dict[str, Optional[int]]] = None` present in
   `LLMResponse`, matching `tool_calls`/`error` style.**
   ✅ Met — `cerebrum/llm/apis.py` line 214, bare `Optional[...] = None` style.

2. **Field is `None`-safe by default; class constructs with no `token_usage`
   argument.**
   ✅ Met — default `None`; verified by executed code and by
   `test_token_usage_absent_defaults_to_none`.

3. **Missing-`token_usage` payload → `token_usage=None`; populated payload →
   correct dict; partial-`None` payload validates cleanly (HTTP round-trip).**
   ✅ Met — verified in Subtask 3 against both the raw-dict live path and
   `LLMResponse.model_validate`, and locked in by the three passing tests above.
   ⚠️ Deviation noted: the live path returns a raw dict, not an `LLMResponse`
   (Finding 1) — both paths were verified.

4. **Benchmark per-trial results can capture `token_usage` (add if trivial;
   report if not).**
   ⚠️ Reported, not implemented — Finding 2. The pass-through is non-trivial
   (requires an agent + pipeline + `TrialResult` schema change); intentionally
   not done, consistent with the prompt's stop-and-report guidance.

5. **Tests added for the new field; full test file run and output captured.**
   ✅ Met — `tests/apis/llm/test_llm_response.py`, three cases, full run output
   captured verbatim above (3 passed).

6. **No other class in `apis.py` modified; declaration style matches siblings.**
   ✅ Met — only `LLMResponse` changed; `LLMQuery` untouched.

7. **Any deviation reported explicitly rather than resolved silently.**
   ✅ Met — Findings 1 and 2 above.

## What Remains (end-to-end)

1. **AIOS-side follow-up (next step, now unblocked):** wire
   `syscall.get_token_usage()` into the outgoing kernel `LLMResponse` payload.
   The receiving field now exists in the SDK, so this can proceed. Because the
   SDK tolerates the field's absence today and unrecognized extra keys, this can
   ship without coordination risk.

2. **Benchmark harness (still required for token usage to reach results
   files):** even after the AIOS-side follow-up ships, token usage will **not**
   appear in the benchmark JSON until the Subtask 4 changes land —
   `AssistantAgent.run()` surfacing `token_usage`, `PipelineResult` carrying it,
   and `TrialResult` gaining a field to store it. Until then the data is dropped
   at the `AssistantAgent.run()` boundary.
