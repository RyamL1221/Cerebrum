# Re-validation provenance

Frozen 2026-11-01 before the first trial. Each results file
also records `git_commit`, `kernel_git_commit` and `config_snapshot`.

## Code

| | AIOS | Cerebrum |
|---|---|---|
| Tag `neurips-subtask-02` | `3ca3b271743f69835a45cb849a744e79bf625710` | `f9e91630bc8ab5179ba1432aebfdbaf45cc3c5f7` |
| Commit run | `19c3ea95d69a050e4ef080f19fecc17db4286964` | `956d54f4ad26acb4d8dea19942414cb264bb375f` plus this file's commit |

Kernel code is unchanged from the tag: `git diff neurips-subtask-02 HEAD
-- aios runtime` in AIOS is empty (confirmed). The only Cerebrum changes after the
tag are the `models.py` metadata fields and `revalidate.py`.

## Models

| Role | Model |
|---|---|
| Assistant | `gpt-4o` (backend `azure`) |
| Assistant | `llama3.1:8b` sha256-667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29  (ollama id 46e0c10c039e) |
| Assistant | `qwen2.5:7b` sha256-2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730  (ollama id 845dbda0ea48) |
| Judge | `gpt-5.4` (backend `azure`) |
| Embedder | `nomic-embed-text` sha256-970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6  (ollama id 0a109f422b47) |

## Judge prompt

Unchanged from the workshop: `judge.py` last changed in `9c83fc6`
(2026-05-28 11:39), before the first workshop run, and `git diff 9c83fc6
HEAD -- benchmarks/shared_memory/judge.py` is empty.

- Rubric sha256: `bfcc04c9547dc32df60128048daabfbc16bc07b29e4b158ff794671e6ffcb191` (the source text from `"--- SCORING RUBRIC ---`
  up to the next `return` in `judge.py`)
- `judge.py` sha256: `fbd3b9835e92f8a92e8386f8493691b3d01acf35b244ef08fe70ec25e7229865`

## Packages (kernel venv)

```
chromadb==1.5.8
litellm==1.83.0
llama-index-agent-openai==0.1.7
llama-index-embeddings-openai==0.1.11
llama-index-llms-openai==0.1.11
llama-index-multi-modal-llms-openai==0.1.9
llama-index-program-openai==0.1.6
llama-index-question-gen-openai==0.1.3
mem0ai==2.0.0
openai==2.32.0
```

## Memory config

`memory:` section of `aios/config/config.yaml`, 1 secret value(s)
redacted. On this branch the kernel reads only `provider`, `log_mode`,
`auto_extract`, `auto_inject`, `relevance_threshold`,
`max_injected_memories`, `max_memory_tokens`, `write_barrier` and the
provider sections. The gating keys belong to another branch.

```yaml
memory:
  log_mode: "console" # choose from [console, file]
  provider: "mem0"  # Options: in-house, mem0, zep

  # Gate policy selection (Subtask 6). Single control point for memory
  # gating. When omitted, the mode is DERIVED from the legacy
  # adaptive_policy.enabled / static_thresholds.enabled flags for
  # backward compatibility (both off -> none, static only -> static,
  # adaptive only -> linucb; both on with no mode -> startup error).
  #   none    = no gating (frozen baseline)
  #   static  = fixed thresholds from static_thresholds.*
  #   linucb  = adaptive LinUCB bandits from adaptive_policy.*
  #   learner = thresholds from the learner's batch loop (Subtask 16),
  #             starting at static_thresholds; needs gate_learner.
  #             fast_loop.enabled and gate_learner.batch_loop.enabled
  gate_policy:
    mode: "linucb"

  gate_trace:
    enabled: true      # S24 live-verify ONLY; revert after the run

  # Gate-learner sidecar store (Subtask 7). A persistent SQLite store,
  # OUTSIDE Mem0, that holds everything the future gate learner learns
  # (per-memory / per-fact-type / redundancy-pair statistics, the
  # retrieval-skip training set, and versioned parameter snapshots). It
  # is NOT wired into any request path yet — creating it has no effect
  # on gate behavior. `sidecar_path` is the SQLite file (its parent dir,
  # .aios_state/, is gitignored); `namespace` scopes every row so
  # multiple experiments can share one file without cross-contamination.
  gate_learner:
    sidecar_path: ".aios_state/gate_learner.sqlite"
    namespace: "default"
    # Fast loop (Subtask 14): after each trial, fold its episode events
    # into per-memory / per-fact-type / per-gate-bin statistics in the
    # sidecar. OBSERVATION ONLY (no gate decision, stored memory or
    # injected content changes); runs on a background worker. Each row
    # also keeps a discounted copy (x discount_gamma per trial).
    # bin_width: gate score bins over [0, 1.02). See docs/FAST_LOOP.md.
    fast_loop:
      enabled: false
      discount_gamma: 0.98
      bin_width: 0.02
    # Miss reliability weight per fact category = 1 - its decoy
    # false-relevance rate on pm_v1 (Subtask 15, docs/MISS_ATTRIBUTION.md);
    # profile_style is excluded (0.0). "default" applies to any other
    # category.
    miss_weights:
      profile_name: 0.888
      profile_tool: 0.625
      profile_language: 0.951
      profile_style: 0.0
      task_project: 0.549
      task_experiment: 0.592
      task_blocker: 0.373
      task_next_step: 0.304
      default: 0.475
    # Usage-labeler (v2) noise per memory type, used to correct usage
    # rates at read time (aios/memory/learner/estimators.py). Subtask-15
    # pm_v1 re-validation (docs/USAGE_LABELER.md), pooled
    # leave-one-user-out: fpr on same-user HARD negatives (stored, not
    # injected), fnr on injected memories a GPT-5.4 judge called used.
    # Negatives: conversation 564, profile 168, task_context 167 (all
    # >= 50). Positives behind the fnr: conversation 41 and profile 29
    # (FEWER THAN 50), task_context 55.
    labeler_noise:
      conversation: {fpr: 0.055, fnr: 0.171}
      profile: {fpr: 0.06, fnr: 0.138}
      task_context: {fpr: 0.024, fnr: 0.018}
      default: {fpr: 0.05, fnr: 0.096}
    # Batch loop (Subtask 16; used by gate_policy.mode learner). Every
    # batch_size trials of an llm_core it proposes ONE threshold move
    # (per gate x memory type; redundancy per model) from the fast-loop
    # statistics and keeps it only if the mean judge reward of the next
    # guard_window non-exploration trials is not worse than the last
    # reference_window (null = guard_window) trials under the accepted
    # settings by more than epsilon (bootstrap lower bound at
    # guard_level); else it restores the previous settings and holds the
    # parameter for cooldown batches. A move is at most max_step and
    # needs evidence n >= min_evidence whose interval supports it
    # (usage upper bound <= max_drop_usage to tighten, weighted miss
    # lower bound > max_drop_miss to loosen). explore_rate caps the
    # share of trials that run one parameter one step looser. With the
    # defaults below (40 vs 80 trials, epsilon 0.25: a 0.25-point
    # non-inferiority margin, about two batches per evaluated change)
    # and pm_v1-like reward noise the guardrail rolls back ~11% of
    # changes that have no effect (20 vs 20 / 0.15: ~67%). See
    # docs/BATCH_LOOP.md.
    batch_loop:
      enabled: false
      batch_size: 20
      min_evidence: 20
      max_step: 0.1
      max_drop_usage: 0.1
      max_drop_miss: 0.05
      guard_window: 40
      reference_window: 80
      epsilon: 0.25
      guard_level: 0.9
      cooldown: 3
      explore_rate: 0.05
      # Subtask 16 follow-up. proposer: cost_aware (default: proposes
      # token-saving tightenings, ranked by estimated tokens saved per
      # trial, and lets the guardrail judge quality; a loosening must
      # show a quality gain) or generic (tightens only where usage is
      # low; the first pilot's). min_traffic: items the gate scored in
      # the evidence window before a parameter is proposed.
      # min_token_saving: least estimated tokens per trial a cost-aware
      # tightening must save.
      proposer: "cost_aware"
      min_traffic: 1.0
      min_token_saving: 20.0
      # Cumulative anchor: every change must also be non-inferior
      # (lower bound >= -anchor_epsilon) to a FIXED window of trials
      # under the starting settings (up to 160, collected until the
      # first guarded change). anchor_update: fixed | best_mean |
      # significant (the moving variants, kept for the ablation);
      # anchor_epsilon null = epsilon. Chosen by the anchor study
      # (docs/BATCH_LOOP.md).
      anchor: true
      anchor_update: "fixed"
      anchor_epsilon: 0.35
      # Removal guard (known issue 34): a cost-aware tightening that
      # drops more than removal_share of a memory type's injected items
      # needs >= removal_min_saving tokens per trial saved, or the
      # type's usage upper bound <= max_drop_usage (cost_benefit);
      # usage_only: the usage bound only; off. Early stop: after
      # early_stop_trials trials under a change (0 = off), roll it back
      # if the lower bound of post - reference < -early_stop_margin.
      # Chosen by the removal-guard study (docs/BATCH_LOOP.md).
      removal_guard: "cost_benefit"
      removal_share: 0.5
      removal_min_saving: 150.0
      early_stop_trials: 10
      early_stop_margin: 1.0

  # Write-path tiers (Subtask 12). MECHANISM ONLY: with these defaults no
  # gate decision, stored memory, prompt or injected content changes.
  #   fact_typing — label each write with what it changes relative to its
  #     nearest memory (fact_type / fields_changed on the episode write
  #     event). Observation only.
  #   shadow — keep the text of every novelty-gate reject in the learner
  #     sidecar's shadow_memories table (never in Mem0, never retrieved,
  #     never injected), at most shadow_cap_per_user rows per user.
  #   probation_band — 0.0 = off. When > 0 under gate_policy.mode
  #     static (or the future learner mode), a write with
  #     T <= max_sim < min(T + probation_band, exact_duplicate_sim) is
  #     admitted with tier="probation" instead of rejected; a write with
  #     max_sim >= exact_duplicate_sim is still rejected. Under linucb
  #     the band is ignored (one startup WARNING). A probation memory is
  #     promoted the first time it is labeled used, and expires into the
  #     shadow store after probation_max_injections injections without
  #     being used or probation_max_trials of its user's trials without
  #     being kept by the similarity gate or injected (being a retrieval
  #     candidate does not count).
  # Invalid values fail kernel startup. See docs/WRITE_TIERS.md.
  write_tiers:
    fact_typing: true
    shadow: true
    probation_band: 0.0
    exact_duplicate_sim: 0.999
    probation_max_injections: 3
    probation_max_trials: 10
    shadow_cap_per_user: 500

  # Run-scoped episode log (Subtask 8). Append-only JSONL at
  # <dir>/<run_id>.jsonl, one line per event (write / retrieval /
  # injection / response / reward / store_count), separate from
  # kernel.log (which is overwritten on restart). Records everything the
  # learner + evaluation need per trial, with per-source token
  # accounting (fixed tiktoken cl100k_base primary; provider usage
  # secondary). Never affects the request path.
  episode_log:
    enabled: true
    dir: "logs/episodes"

  # Usage labeler (Subtask 9; v2 in Subtask 15). Post-response OBSERVER
  # that labels, for every injected memory, whether the response actually
  # drew on it. Runs off the request path and never changes
  # prompts/responses/gates. v2 scores what is SPECIFIC to the memory:
  # used = margin >= m OR specific_lexical >= x (per memory type), where
  # margin = how much better the memory explains its best response
  # sentence than the user's other memories or the query, and
  # specific_lexical = share of tokens only this memory has that appear in
  # the response. Thresholds from the pm_v1 re-validation (leave-one-user-
  # out vs a GPT-5.4 judge and same-user hard negatives,
  # docs/USAGE_LABELER.md). version: v1 keeps the old rule
  # (semantic_threshold / lexical_threshold).
  usage_labeler:
    enabled: true
    version: "v2"
    semantic_threshold: 0.70
    lexical_threshold: 0.35
    v2:
      conversation: {margin: 0.175, specific_lexical: 0.2}
      profile: {margin: 0.375, specific_lexical: 0.15}
      task_context: {margin: 0.3, specific_lexical: 0.3}
      default: {margin: 0.175, specific_lexical: 0.2}

  # Personalization settings (all opt-in, disabled by default)
  auto_extract: true          # Enable automatic conversation→memory extraction
  auto_inject: true            # Enable automatic memory→context injection
  relevance_threshold: 0.3     # Minimum similarity score for memory injection
  max_injected_memories: 10     # Max memories to inject per LLM call
  max_memory_tokens: 2000      # Token budget for injected memory block

  # Memory write barrier — holds user_id-scoped retrievals until in-flight
  # create_memory operations for the same user_id commit. Defaults are coded
  # in MemoryWriteBarrier.__init__, so omitting this section is safe.
  write_barrier:
    enabled: true        # set false to disable the barrier
    timeout_ms: 5000     # max wait per retrieval

  # Adaptive threshold policy (LinUCB bandits). When disabled (the
  # default), memory add/retrieve behavior is unchanged and the
  # PolicyManager is never instantiated. When enabled, add_memory
  # consults the novelty-threshold bandit to gate admission (and, in
  # later work, retrieve_memory consults similarity/redundancy
  # bandits). In-memory state only; no persistence in v1.
  adaptive_policy:
    enabled: true       # master switch; false = frozen baseline (OFF for kernel_shared_tuned)
    alpha: 1.0           # LinUCB exploration parameter
    # Novelty-gate REJECT reward (confidence-scaled percentile-rank of
    # the reject's max_sim within the arm's own reject history, mapped to
    # judge [1.0, 3.0]). This is the fallback/cold-start anchor value.
    reject_reward: 2.0
    # Fraction of rejects that produce a bandit UPDATE (subsampling).
    # Rejects fire on ~92% of writes (~11:1 reject:admit); without this
    # the constant-volume reject signal swamps the admit signal (prior
    # project S5). p=0.15 brings ~110 rejects:10 admits to ~1.6:1,
    # inside the <=~2:1 target. 1.0 disables subsampling. History is
    # still updated on every reject regardless of this rate.
    reject_reward_sample_rate: 0.15
    # Optional per-trial JSONL log of policy decisions + rewards,
    # joinable to the benchmark's per-trial JSON by trial_id. Unset =
    # no logging. Only active when enabled: true.
    trial_log: "logs/policy_trials.jsonl"

  # Static threshold gating (fixed thresholds; no learning). This is an
  # independent variant of the OFF-of-adaptive path: when enabled, the
  # novelty / similarity / redundancy gates run with FIXED thresholds
  # (optionally varying by (llm_core, task_type)) instead of the LinUCB
  # bandits. When disabled (the default), the gates are skipped entirely
  # and memory add/retrieve behave as the frozen baseline.
  #
  # NOTE: static_thresholds.enabled and adaptive_policy.enabled are NOT
  # meant to both be true. They are two mutually-exclusive gating
  # variants over the same three gates. Enforcement/validation is a
  # fast-follow; for now this is a documented convention only.
  #
  # Each of the three thresholds accepts EITHER form:
  #   (a) bare scalar shorthand:      novelty_threshold: 0.7
  #   (b) default + overrides table:  novelty_threshold:
  #                                     default: 0.7
  #                                     overrides:
  #                                       - {llm_core: "qwen2.5:7b",
  #                                          task_type: "profile",
  #                                          value: 0.8}
  # The loader (subtask 4) normalizes both into a lookup keyed on
  # (llm_core, task_type) with a mandatory `default`. An empty/absent
  # `overrides` list is scalar-equivalent behavior.
  # Per-model winners from the offline coordinate search
  # (Cerebrum: benchmarks/shared_memory/threshold_search_progress/full-search-360/summary.json).
  # NOTE: gpt-4o and llama3.1:8b searches completed; the qwen2.5:7b search is
  # marked completed=false in the summary, so its values are best-so-far, not final.
  static_thresholds:
    # Per-model overrides from the Subtask-15 re-search on pm_v1 (dev, 4 users
    # x 6, GPT-5.4 judge, session mode; docs/TUNED_BASELINE.md).
    enabled: false       # master switch for this variant; independent of adaptive_policy.enabled
    novelty_threshold:
      default: 0.7       # search baseline (fallback for unlisted models)
      overrides: [{llm_core: "gpt-4o", value: 1.01}, {llm_core: "llama3.1:8b", value: 0.967}, {llm_core: "qwen2.5:7b", value: 0.99}]      # list of {llm_core, task_type, value}; empty/absent = scalar-equivalent
    similarity_threshold:
      default: 0.7       # search baseline (fallback for unlisted models)
      overrides: [{llm_core: "gpt-4o", value: 0.0}, {llm_core: "llama3.1:8b", value: 0.0}, {llm_core: "qwen2.5:7b", value: 0.0}]
    redundancy_threshold:
      default: 0.7       # search baseline (fallback for unlisted models)
      overrides: [{llm_core: "gpt-4o", value: 0.771}, {llm_core: "llama3.1:8b", value: 1.01}, {llm_core: "qwen2.5:7b", value: 0.889}]

  # Mem0 provider configuration
  mem0:
    api_key: ""  # Optional: for Mem0 cloud
    user_id: "default"
    # Provider mode:
    #   "kernel" (default) — today's behavior byte-for-byte: writes use
    #     infer=False (raw content stored), retrieval uses get_all() plus
    #     a direct ChromaDB distance probe, and the kernel gates
    #     (novelty/similarity/redundancy, adaptive or static) apply.
    #   "native" — off-the-shelf Mem0: writes use infer=True (Mem0's own
    #     LLM fact extraction), retrieval uses Mem0 search() (returns
    #     Mem0's own score), all agents share one user_id scope, and ALL
    #     kernel gates are bypassed regardless of the gating flags (a
    #     startup WARNING is logged if any gating flag is on). The
    #     injector's relevance_threshold filter is also skipped (Mem0's
    #     score is real in native mode). Used by the mem0_native baseline.
    mode: "kernel"
    # Mem0 requires an LLM at init time even with infer=False.
    # Use Ollama so no external API key is needed.
    llm:
      provider: "ollama"
      config:
        model: "qwen2.5:7b"
        ollama_base_url: "http://localhost:11434"
    embedder:
      provider: "ollama"
      config:
        model: "nomic-embed-text"
        ollama_base_url: "http://localhost:11434"
    vector_store:
      provider: "chroma"
      config:
        collection_name: "mem0_memories"
        path: ".mem0/chroma"

  # Zep provider configuration
  zep:
    api_key: "<redacted>"
    # base_url omitted — using Zep Cloud
    session_id: "default"

```

## Amendment: GPT-4o re-run

Both GPT-4o cells of the first run were invalid (102 and 100 of 150
trials failed in synthetic data generation on fenced JSON replies). They
are re-run whole with run prefix `reval2` on later commits, which change
harness parsers, the analysis and the driver, not the kernel or judge.
The exact commits are in each results file's `git_commit` and
`kernel_git_commit`. Llama and Qwen stay on the commits above. See the
amendment in AIOS `docs/REVALIDATION.md`. Invalid files:
`repo-artifacts/Cerebrum/revalidation/invalid_first_run/`.
