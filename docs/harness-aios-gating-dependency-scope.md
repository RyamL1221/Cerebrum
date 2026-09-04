# AIOS Memory-Gating Dependency Scope per Condition

**Subtask 1 — investigation only. No code was modified.**

Goal: establish, from the live repo, exactly which `_run_*` condition methods route
through AIOS kernel endpoints where memory-gating state (`auto_inject` / `auto_extract`,
the concept a `/memory/gating_status` reading would report) is relevant — so a pre-flight
gating check is added only where it belongs.

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
what makes gating state relevant. What matters is whether the kernel's memory-gating logic
has anything to *act on* for that condition — i.e. whether shared/injectable memories were
written to the kernel's Mem0 store under the trial's `user_id` earlier in the same path.

Important repo fact: **there is no `/memory/gating_status` endpoint anywhere in the current
codebase.** The only memory-gating concept present is the kernel config pair
`auto_inject` / `auto_extract` (`aios/config/config_loader.py:66-68`, exercised via `/query`).
Any pre-flight "gating status" check would be reading that kernel-side state, which is only
meaningful for a condition that relies on kernel-managed memory injection.

## Per-condition call path and gating dependency

| Condition | What it calls | Gating state applies? | Why |
|-----------|---------------|-----------------------|-----|
| `kernel_shared` | `_run_kernel_shared` → `AgentPipeline(share_memory=True).run_trial()` → ProfileAgent + TaskAgent write **shared** memories via `create_memory` to the kernel, then AssistantAgent `llm_chat`→`/query`. Relies on kernel `auto_inject` to surface cross-agent shared memories, and reads `injection_diagnostics` from the response. | **YES** | This is the only condition whose *result depends on* the kernel's memory-gating behavior. Writes go to the kernel store with `sharing_policy="shared"`; correct behavior requires kernel `auto_inject` ON so those memories are injected into the AssistantAgent prompt. A gating-status pre-flight is meaningful here. |
| `mem0_default` | `_run_mem0_default` → `AgentPipeline(share_memory=False).run_trial()` → same 3-agent pipeline, but ProfileAgent/TaskAgent write **private** memories (`sharing_policy="private"`); AssistantAgent `llm_chat`→`/query`. | **BORDERLINE — see deviation note** | It uses the *same kernel pipeline* as `kernel_shared` and writes to the kernel memory store, but with `sharing_policy="private"`, so `auto_inject` is expected to find nothing cross-agent to inject. Its correctness is defined by the *absence* of injection. It still routes through the kernel's memory path, so kernel gating config is not irrelevant to it the way it is for the two purely local baselines. |
| `naive_concat` | `_run_naive_concat` builds a plain-text context block from synthetic profile+task, prepends it to the query, and calls `AssistantAgent.run()`. **No `create_memory`, no `search_memories`, no memory endpoint.** `written_memories=[]`, `retrieved_context_count=0`. | **NO** | Pure string concatenation. It hits `/query` only to run the LLM; nothing is written to or retrieved from the kernel memory store, so `auto_inject`/`auto_extract` gating has nothing to act on. |
| `vanilla_rag` | `_run_vanilla_rag` builds context chunks, runs a **local scikit-learn TF-IDF + cosine similarity** retrieval (`TfidfVectorizer`, `cosine_similarity`), injects top-k chunks into the prompt, then calls `AssistantAgent.run()`. **No kernel memory or Mem0 API is called.** | **NO** | Retrieval is entirely local/in-process against an in-memory TF-IDF index with no relationship to AIOS's gating config. It hits `/query` only for the LLM call. |

## Non-goal assumption: confirmed with one caveat

The assumption *"naive_concat / vanilla_rag / mem0_default don't talk to AIOS's
memory-gating logic"* is:

- **Confirmed for `naive_concat` and `vanilla_rag`.** Neither writes to nor reads from any
  kernel memory endpoint. `naive_concat` is plain concatenation; `vanilla_rag` retrieves
  from a local TF-IDF index. Their only kernel contact is the `/query` LLM call, which
  carries no memory-gating dependency. A gating pre-flight would be pointless (and
  misleading) for these two.

- **Flagged as an explicit deviation for `mem0_default`.** It does **not** match the "doesn't
  talk to AIOS memory logic" description. It runs the identical kernel-backed `AgentPipeline`
  as `kernel_shared` (the only difference is `share_memory=False` →
  `sharing_policy="private"`; pipeline.py:737-739), writing memories to the kernel store and
  going through the kernel's `auto_inject`/`auto_extract` path. Its expected behavior is
  "gating is ON but finds nothing cross-agent to inject." So it *is* coupled to AIOS memory
  gating — just as the negative/baseline arm of the same mechanism.

## Scope recommendation (for subtask 4/5)

- **Definitely in scope:** `kernel_shared` — its correctness depends on kernel `auto_inject`
  being ON; a `/memory/gating_status`-style pre-flight is meaningful here.
- **Decision required (do not silently fold in):** `mem0_default`. Because it shares the exact
  kernel pipeline as `kernel_shared`, a gating pre-flight would run identically for it. Whether
  it *should* be gated depends on the intent: if the pre-flight is asserting kernel config is
  in a known state before any kernel-memory-backed condition runs, `mem0_default` qualifies; if
  it is asserting that injection *will happen*, `mem0_default` deliberately expects none.
- **Out of scope (confirmed):** `naive_concat`, `vanilla_rag` — no kernel memory path, gating
  state has nothing to act on.

## Line references

- `MethodPipeline.run_trial` dispatch: `benchmarks/shared_memory/pipeline.py:~500-515`
- `_run_kernel_shared`: pipeline.py:517-539 (`AgentPipeline(share_memory=True)`, pipeline.py:537)
- `_run_naive_concat`: pipeline.py:540-608 (`written_memories=[]`, `retrieved_context_count=0`, pipeline.py:600-606)
- `_run_vanilla_rag`: pipeline.py:609-715 (TF-IDF import pipeline.py:~628-629; "No kernel memory or Mem0 API is called" docstring pipeline.py:~615-621)
- `_run_mem0_default`: pipeline.py:716-742 (`AgentPipeline(share_memory=False)`, pipeline.py:737)
- Shared terminal call: `AssistantAgent.run` → `llm_chat` at agent.py:56; `send_request`→`/query` at `cerebrum/llm/apis.py:298` and `cerebrum/utils/communication.py:71`
- Gating config (only gating concept in repo): `aios/config/config_loader.py:66-68` (`auto_inject`, `auto_extract`)
- No `/memory/gating_status` endpoint exists in the repo (grep: no matches for `gating_status`)
