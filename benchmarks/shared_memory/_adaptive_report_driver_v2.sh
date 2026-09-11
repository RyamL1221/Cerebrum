#!/bin/zsh
# kernel_shared_adaptive ACCUMULATING-SESSION run — V2 DECOMPOSED JUDGE.
# Per-model isolated bandit run: single 15-interactions/user condition across
# all 3 assistant models, gpt-5.4 judge throughout.
#
#   10 users x 15 interactions = 150 trials per model
#   3 models (gpt-4o, llama3.1:8b, qwen2.5:7b) = 450 trials total
#   => 3 INDEPENDENT bandit-learning runs (one per model).
#
# WHY THE PER-MODEL RESTART STRUCTURE:
# A kernel restart clears the adaptive policy's in-memory bandit state. To make
# each model's learning curve independently observable, we restart the kernel
# AT EACH MODEL BOUNDARY (not just once at the top) so model N+1 does not
# inherit model N's converged arms. Each restart is followed by a gating-status
# verification BEFORE that model's trials begin, so a restart that silently
# failed to pick up config is caught immediately rather than surfacing later as
# bad results. The persistent per-run artifacts (kernel stdout log and the
# separate policy_trials.jsonl) are ALSO scoped per model, since a restart does
# not rotate those files — without scoping, models 2 and 3 would pile into the
# same file and undermine the independent-learning-curve goal.
#
# This structure is scripted (not manual between runs) on purpose: manual steps
# between multi-hour model runs risk being missed or mistimed.
#
# NOTE: the 15-interactions/user condition exceeds this project's own
# ceiling-probe finding (~12+ interactions before drift concern becomes live).
# Treat interactions 13-15 as the drift-risk zone when reading results.
#
# Sequential against a kernel this script itself restarts+verifies at each
# boundary. Requires: adaptive_policy.enabled=true, static_thresholds.enabled=
# false in the AIOS config.yaml (this script asserts, it does NOT set them).
set -u

CEREBRUM_DIR="/Users/ryan/Library/Mobile Documents/com~apple~CloudDocs/Documents/VSCode/Cerebrum"
AIOS_DIR="/Users/ryan/Library/Mobile Documents/com~apple~CloudDocs/Documents/VSCode/AIOS"
cd "$CEREBRUM_DIR" || exit 1

PY=".venv/bin/python"
AIOS_PY="${AIOS_DIR}/.venv/bin/python"
JUDGE="gpt-5.4:azure"
KURL="http://localhost:8000"
KPORT=8000
TOTAL_TRIALS=150          # per model = users * interactions
INTERACTIONS=15
USERS=$(( TOTAL_TRIALS / INTERACTIONS ))   # 150 / 15 = 10
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"

# ---------------------------------------------------------------------------
# Kernel lifecycle helpers (mirror threshold_search.restart_kernel_and_wait:
# SIGTERM the PID bound to the port, relaunch `python -m runtime.launch` with
# AIOS as cwd, poll /status until ok).
# ---------------------------------------------------------------------------
stop_kernel () {
  local pid
  pid="$(lsof -ti "tcp:${KPORT}" 2>/dev/null | head -1)"
  if [[ -n "$pid" ]]; then
    echo "  [kernel] SIGTERM pid=$pid"
    kill "$pid" 2>/dev/null
    for _ in $(seq 1 15); do
      lsof -ti "tcp:${KPORT}" >/dev/null 2>&1 || break
      sleep 1
    done
    if lsof -ti "tcp:${KPORT}" >/dev/null 2>&1; then
      echo "  [kernel] still listening after SIGTERM; SIGKILL"
      kill -9 "$(lsof -ti "tcp:${KPORT}" 2>/dev/null | head -1)" 2>/dev/null
      sleep 2
    fi
  else
    echo "  [kernel] nothing listening on :${KPORT}"
  fi
}

# start_kernel <kernel_log_path>
start_kernel () {
  local klog="$1"
  echo "  [kernel] launching (log -> $klog)"
  ( cd "$AIOS_DIR" && nohup "$AIOS_PY" -m runtime.launch >> "$klog" 2>&1 & )
  # Poll /status until ok (max ~60s).
  for _ in $(seq 1 30); do
    if curl -s -m 3 "${KURL}/status" 2>/dev/null | grep -q '"status":"ok"'; then
      echo "  [kernel] /status ok"
      return 0
    fi
    sleep 2
  done
  echo "  [kernel] ERROR: /status not ok within timeout" >&2
  return 1
}

# verify_gating: assert adaptive_policy_enabled=True AND static_thresholds_enabled=False.
# Exits the whole script non-zero on mismatch (a silently-unapplied config must
# stop the run before any trials execute).
verify_gating () {
  local model="$1"
  local js
  js="$(curl -s -m 5 "${KURL}/memory/gating_status" 2>/dev/null)"
  # NOTE: the JSON is passed via env var (GATING_JSON), NOT stdin — stdin here
  # is consumed by the heredoc that supplies the Python source, so a piped
  # payload would be read as empty.
  GATING_JSON="$js" "$PY" - "$model" <<'PYEOF'
import os, sys, json
model = sys.argv[1]
raw = os.environ.get("GATING_JSON", "")
try:
    d = json.loads(raw)
except Exception as e:
    print(f"  [gating] FAIL ({model}): unparseable gating_status response: {e}", file=sys.stderr)
    sys.exit(1)
adaptive = d.get("adaptive_policy_enabled")
static = d.get("static_thresholds_enabled")
if adaptive is True and static is False:
    print(f"  [gating] OK ({model}): adaptive=True static=False")
    sys.exit(0)
print(f"  [gating] FAIL ({model}): expected adaptive=True static=False, "
      f"got adaptive={adaptive} static={static}", file=sys.stderr)
sys.exit(1)
PYEOF
  return $?
}

# snapshot_policy_trials <tag>: rotate the persistent policy_trials.jsonl aside
# so each model's bandit decisions land in a fresh file (independent curve).
snapshot_policy_trials () {
  local tag="$1"
  local ptl="${AIOS_DIR}/logs/policy_trials.jsonl"
  if [[ -f "$ptl" ]]; then
    local dest="${AIOS_DIR}/logs/policy_trials.${RUN_STAMP}.pre_${tag}.jsonl"
    mv "$ptl" "$dest"
    echo "  [policy_trials] rotated aside -> $(basename "$dest")"
  else
    echo "  [policy_trials] none present (fresh)"
  fi
}

# ---------------------------------------------------------------------------
# run_one <model> <backend> <tag>
#   Restart kernel (fresh bandit state) -> verify gating -> snapshot
#   policy_trials aside -> run 150 trials with a per-model kernel log +
#   output dir + run-id + --kernel-logs pointing at that model's kernel log.
# ---------------------------------------------------------------------------
run_one () {
  local model="$1" backend="$2" tag="$3"
  local klog="${AIOS_DIR}/kernel_450run_${tag}.log"
  local outtag="${tag}_i${INTERACTIONS}"

  echo ""
  echo "############################################################"
  echo "### [$(date '+%H:%M:%S')] MODEL BOUNDARY: ${model} (${backend})"
  echo "############################################################"

  # 1. Fresh kernel (clears in-memory bandit state for an independent curve).
  echo "--- MODEL ${tag} RESTART $(date '+%Y-%m-%dT%H:%M:%S') ---" >> "$klog"
  stop_kernel
  start_kernel "$klog" || { echo "=== ABORT: kernel start failed for ${model} ==="; return 20; }

  # 2. Gating verification BEFORE any trials for this model.
  if ! verify_gating "$model"; then
    echo "=== ABORT: gating verification failed for ${model}; no trials run ==="
    return 21
  fi

  # 3. Scope policy_trials aside so this model's decisions are isolated.
  snapshot_policy_trials "$tag"

  # 4. Run this model's 150 trials.
  echo "=== [$(date '+%H:%M:%S')] START ${model} (${backend}) — ${USERS} users x ${INTERACTIONS} interactions = $((USERS * INTERACTIONS)) trials [v2, accumulating] ==="
  "$PY" benchmarks/shared_memory/run_evaluation.py \
    --users "$USERS" \
    --interactions-per-user "$INTERACTIONS" \
    --method kernel_shared_adaptive \
    --rubric-version v2 \
    --assistant-model "${model}:${backend}" \
    --judge-model "$JUDGE" \
    --kernel-url "$KURL" \
    --kernel-logs "$klog" \
    --output "results/adaptive_report_v2_accum/${outtag}/" \
    --run-id "adaptive_report_v2_accum_${outtag}" \
    --csv
  local rc=$?
  echo "=== [$(date '+%H:%M:%S')] DONE ${model} rc=${rc} ==="
  return $rc
}

# ---------------------------------------------------------------------------
# Sequential per-model runs. Each fully completes (restart -> verify ->
# snapshot -> 150 trials) before the next model begins.
#   10 users x 15 interactions = 150/model x 3 models = 450 total.
# ---------------------------------------------------------------------------
run_one "gpt-4o"      "azure"  "gpt4o"
run_one "llama3.1:8b" "ollama" "llama31_8b"
run_one "qwen2.5:7b"  "ollama" "qwen25_7b"

echo ""
echo "=== [$(date '+%H:%M:%S')] ALL THREE PER-MODEL ADAPTIVE V2 RUNS COMPLETE (450 trials) ==="
