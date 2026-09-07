#!/bin/zsh
# kernel_shared_adaptive reporting run — 3 assistant models, 150 trials each, gpt-5.4 judge.
# Sequential against the already-running, gating-verified kernel (adaptive on, static off).
# Mirrors the tuned run for apples-to-apples comparison.
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
    --method kernel_shared_adaptive \
    --assistant-model "${model}:${backend}" \
    --judge-model "$JUDGE" \
    --kernel-url "$KURL" \
    --output "results/adaptive_report/${tag}/" \
    --run-id "adaptive_report_${tag}" \
    --csv
  echo "=== [$(date '+%H:%M:%S')] DONE $model rc=$? ==="
}

run_one "gpt-4o"      "azure"  "gpt4o"
run_one "llama3.1:8b" "ollama" "llama31_8b"
run_one "qwen2.5:7b"  "ollama" "qwen25_7b"

echo "=== [$(date '+%H:%M:%S')] ALL THREE ADAPTIVE RUNS COMPLETE ==="
