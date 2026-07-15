"""Phase 1: Sample trials from automated results and produce blinded queue.

Usage (preview selection only):
    python -m benchmarks.human_rating.sample_and_blind \
        --manifest benchmarks/human_rating/config/evaluation_manifest.json \
        --preview-selection

Usage (full pipeline — later subtask):
    python -m benchmarks.human_rating.sample_and_blind \
        --manifest benchmarks/human_rating/config/evaluation_manifest.json \
        --run-name gpt4o_human_eval
"""

import argparse
import json
import os
import sys

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sample trials from automated results for human evaluation.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="benchmarks/human_rating/config/evaluation_manifest.json",
        help="Path to the evaluation manifest JSON.",
    )
    parser.add_argument(
        "--preview-selection",
        action="store_true",
        help="Preview the 24 unique trial selections without writing files.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this human-rating run (used as directory name).",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    # Load manifest
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    protocol = manifest["protocol"]
    sources = manifest["sources"]
    seed = protocol["sampling_seed"]
    items_per_method = protocol["unique_items_per_method"]

    # Build method_paths from manifest sources
    method_paths = {method: info["path"] for method, info in sources.items()}

    # Load eligible trials
    from benchmarks.human_rating.trial_loader import load_eligible_trials
    trials, exclusion_report = load_eligible_trials(
        method_paths=method_paths,
        min_per_method=items_per_method,
    )

    if exclusion_report.total_excluded > 0:
        print(exclusion_report.format_summary())
        print()

    # Sample unique trials
    from benchmarks.human_rating.sampling import sample_unique_trials
    selected, summary = sample_unique_trials(
        trials, seed=seed, items_per_method=items_per_method,
    )

    if args.preview_selection:
        print(summary.format_table())
        return

    if not args.run_name:
        parser.error("--run-name is required when not using --preview-selection")

    # Full pipeline (blinding, duplicates, queue writing) — later subtask
    raise NotImplementedError(
        "Full sampling pipeline not yet implemented. Use --preview-selection."
    )


if __name__ == "__main__":
    main()
