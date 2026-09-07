#!/bin/zsh
# kernel_shared_adaptive reporting run — V2 DECOMPOSED JUDGE.
# Identical to _adaptive_report_driver.sh except it scores with the v2 rubric
# (--rubric-version v2) and writes to a separate output dir + run-id so the v1
# and v2 artifacts/memory namespaces never collide (never-pool-v1/v2 rule).
# 3 assistant models, 150 trials each, gpt-5.4 judge.
# Sequential against the already-running, gating-verified kernel (adaptive on, static off).
set -u
cd "/Users/ryan/Library/Mobile Documents/com~apple~CloudDocs/Documents/VSCode/Cerebrum" || exit 1
PY=".venv/bin/python"
JUDGE="gpt-5.4:azure"
KURL="http://localhost:8000"
TRIALS=150

run_one () {
  local model="$1" backend="$2" tag="$3"
  echo "=== [$(date '+%H:%M:%S')] START $model ($backend) — $TRIALS trials [v2] ==="
  "$PY" benchmarks/shared_memory/run_evaluation.py \
    --trials "$TRIALS" \
    --method kernel_shared_adaptive \
    --rubric-version v2 \
    --assistant-model "${model}:${backend}" \
    --judge-model "$JUDGE" \
    --kernel-url "$KURL" \
    --output "results/adaptive_report_v2/${tag}/" \
    --run-id "adaptive_report_v2_${tag}" \
    --csv
  echo "=== [$(date '+%H:%M:%S')] DONE $model rc=$? ==="
}

run_one "gpt-4o"      "azure"  "gpt4o"
run_one "llama3.1:8b" "ollama" "llama31_8b"
run_one "qwen2.5:7b"  "ollama" "qwen25_7b"

echo "=== [$(date '+%H:%M:%S')] ALL THREE ADAPTIVE V2 RUNS COMPLETE ==="
