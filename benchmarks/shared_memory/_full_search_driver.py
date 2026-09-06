"""Full 360-trial threshold-search driver (invocation shell only — no search logic).

Calls the confirmed single entry point run_full_search(...) with all defaults:
  3 models (DEFAULT_SEARCH_MODELS) x 3 thresholds (_SEARCH_ORDER)
  x 5 candidates (DEFAULT_CANDIDATE_GRID) x 8 trials (DEFAULT_TRIALS_PER_CANDIDATE)
  = 360 trials. Judge = DEFAULT_SEARCH_JUDGE_MODEL (gpt-5.4:azure).

Intended to be launched detached (nohup/disown) so it survives disconnects.
Resume: re-running this with the same search_run_id continues a crashed run
(resume=True), skipping completed candidates (proven crash-safe separately).

This file is a thin invocation shell; it does NOT modify search behavior.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.shared_memory.threshold_search import run_full_search  # noqa: E402

AIOS_REPO = "/Users/ryan/Library/Mobile Documents/com~apple~CloudDocs/Documents/VSCode/AIOS"
CONFIG_PATH = f"{AIOS_REPO}/aios/config/config.yaml"
OUTPUT_ROOT = "results/threshold_search_full/"
SEARCH_RUN_ID = "full-search-360"


def main() -> None:
    logging.info("Launching full threshold search: search_run_id=%s", SEARCH_RUN_ID)
    states = run_full_search(
        config_path=CONFIG_PATH,
        aios_repo_dir=AIOS_REPO,
        output_root=OUTPUT_ROOT,
        search_run_id=SEARCH_RUN_ID,
        kernel_url="http://localhost:8000",
        write_final=True,
        resume=True,
    )
    logging.info("FULL SEARCH COMPLETE. Winners by model:")
    for model, state in states.items():
        logging.info("  %s -> %s", model, state.winners)


if __name__ == "__main__":
    main()
