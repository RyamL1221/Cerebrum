# Kernel Context Injector — Bug Fixes Required for Cross-Agent Shared Memory

## Summary

The AIOS kernel's context injector has several bugs that prevent cross-agent shared memory from working. When an agent (e.g., `assistant_agent`) calls `llm_chat`, the kernel's `auto_inject` feature should find and prepend relevant shared memories written by other agents (e.g., `profile_agent`, `task_agent`) for the same user. Currently, this fails silently — no memories are injected.

## Evidence

Running the Cerebrum SDK benchmark with `method=kernel_shared` (150 trials, qwen2.5:7b assistant, gpt-5.4 judge):
- **Every trial** reports `shared_memory_count: 0` and `injection_status: "unknown"`
- ProfileAgent and TaskAgent successfully call `create_memory` with `sharing_policy: "shared"` and a specific `user_id` in metadata
- AssistantAgent receives no injected context — responses are entirely generic
- Scores: Profile 1.02, Task 1.72, Integration 1.00 (floor-level, identical to no-memory baseline)

## Bug 1: user_id Resolution in Context Injector

### Current (broken) behavior

When `assistant_agent` calls `llm_chat`, the context injector resolves `user_id` from the **agent name** (`"assistant_agent"`) rather than from the **metadata** of stored memories. It then searches for memories with `user_id = "assistant_agent"` — which finds nothing, because ProfileAgent wrote memories with `user_id = "alice__kernel_shared"` (or whatever the actual user identifier is).

### Expected behavior

The context injector should resolve `user_id` from the memory metadata written by other agents. Specifically:

1. When `assistant_agent` calls `llm_chat`, the kernel should determine the current user's identity from the request context (e.g., a `user_id` field passed in the LLM query, or resolved from the agent's session)
2. Search for **all shared memories** where `metadata.user_id` matches this resolved user_id, regardless of which agent wrote them
3. Filter by `metadata.sharing_policy == "shared"` to exclude private memories

### How the SDK writes memories

```python
# ProfileAgent writes:
metadata = {
    "owner_agent": "profile_agent",
    "user_id": "alice__kernel_shared",  # the actual user identifier
    "memory_type": "profile",
    "sharing_policy": "shared"
}
create_memory(agent_name="profile_agent", content=json_content, metadata=metadata)

# TaskAgent writes:
metadata = {
    "owner_agent": "task_agent",
    "user_id": "alice__kernel_shared",
    "memory_type": "task_context",
    "sharing_policy": "shared"
}
create_memory(agent_name="task_agent", content=json_content, metadata=metadata)
```

### What the injector should do when AssistantAgent calls llm_chat

```
1. Resolve user_id from the request (e.g., "alice__kernel_shared")
2. Query: find memories WHERE metadata.user_id = "alice__kernel_shared"
                          AND metadata.sharing_policy = "shared"
                          AND metadata.owner_agent != "assistant_agent"  (cross-agent only)
3. Rank by relevance to the current query
4. Format as natural language and prepend to messages
```

## Bug 2: Sharing Policy Filter Never Invoked

### Current (broken) behavior

The `_apply_sharing_filter()` method exists in the Mem0Provider but is never called because `agent_name` is not passed in the query params from the ContextInjector. Without `agent_name`, the filter cannot distinguish "own" memories from "other agent" memories, so it skips filtering entirely.

### Fix

Include `agent_name` in both the own-memories and shared-memories query params passed to the memory provider. The sharing filter logic should be:

- **Own memories** (same agent): Always visible regardless of sharing_policy
- **Other agent memories**: Only visible if `sharing_policy == "shared"`

## Bug 3: Conversation Extractor user_id Propagation

### Current (broken) behavior

The kernel's `auto_extract` stores conversation memories under `user_id = "assistant_agent"` (the agent name) instead of the resolved user_id from the session. This causes namespace mismatches — memories written by ProfileAgent under `user_id = "alice"` are in a different namespace than conversation memories stored under `user_id = "assistant_agent"`.

### Fix

The conversation extractor should propagate the resolved `user_id` from the injection context (the same user_id used for retrieval) when storing auto-extracted conversation memories.

## Bug 4: Natural Language Formatting at Inject Time

### Current (broken) behavior

The kernel injects raw JSON content into the LLM prompt. With qwen2.5:7b, raw JSON produces worse responses than no context at all (the model gets confused by the structured format).

### Fix

Convert JSON memory content to natural language at inject time. Example:

**Raw JSON stored:**
```json
{"user_name": "Alice", "preferred_tools": ["VS Code", "Git"], "preferred_language": "Python", "response_style": "casual"}
```

**Injected as natural language:**
```
The user's name is Alice. They prefer using VS Code and Git as their tools. Their preferred programming language is Python. They prefer a casual response style.
```

This formatting should happen in the context injector, not at write time (keep storage as JSON for structured queries).

## Verification

After applying these fixes, the Cerebrum benchmark should show:

1. `injection_status: "confirmed"` (if diagnostics are exposed) or at minimum the audit query should find shared memories
2. Assistant responses should reference specific profile attributes (user name, tools, language) and task context (project name, goals, blockers)
3. Personalization scores should be significantly above the 1.0-1.2 baseline

## Recommended Kernel Config

```yaml
memory:
  auto_inject: true
  auto_extract: true
  relevance_threshold: 0.3
  max_injected_memories: 10
  max_memory_tokens: 2000
```

- `relevance_threshold: 0.3` — lowered from default because synthetic benchmark queries score low against structured memories
- `max_injected_memories: 10` — prevents profile/task memories from being crowded out by conversation memories
- `max_memory_tokens: 2000` — accommodates natural language formatted memories which are longer than raw JSON
