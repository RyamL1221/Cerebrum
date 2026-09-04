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
