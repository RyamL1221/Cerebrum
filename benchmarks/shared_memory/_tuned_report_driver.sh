#!/bin/zsh
# kernel_shared_tuned reporting run — 3 assistant models, 150 trials each, gpt-5.4 judge.
# Runs sequentially against the already-running, gating-verified kernel (one kernel,
# one Ollama — sequential avoids resource contention). Detached-friendly; each model
# writes its own output dir + run-id so memory namespaces don't collide.
set -u
cd "/Users/ryan/Library/Mobile Documents/com~apple~CloudDocs/Documents/VSCode/Cerebrum" || exit 1
PY=".venv/bin/python"
JUDGE="gpt-5.4:azure"
KURL="http://localhost:8000"
TRIALS=150

run_one () {
  local model="$1" backend="$2" tag="$3"
  echo "=== [$(date '+%H:%M:%S')] START $model ($backend) — $TRIALS trials ==="
  "$PY" benchmarks/shared_memory/run_evaluation.py \
    --trials "$TRIALS" \
    --method kernel_shared_tuned \
    --assistant-model "${model}:${backend}" \
    --judge-model "$JUDGE" \
    --kernel-url "$KURL" \
    --output "results/tuned_report/${tag}/" \
    --run-id "tuned_report_${tag}" \
    --csv
  echo "=== [$(date '+%H:%M:%S')] DONE $model rc=$? ==="
}

# gpt-4o first (fast, cloud), then the two local models.
run_one "gpt-4o"      "azure"  "gpt4o"
run_one "llama3.1:8b" "ollama" "llama31_8b"
run_one "qwen2.5:7b"  "ollama" "qwen25_7b"

echo "=== [$(date '+%H:%M:%S')] ALL THREE TUNED RUNS COMPLETE ==="
