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
        "--preview-blinded-plan",
        action="store_true",
        help="Preview the full 30-item blinded plan without writing files.",
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

    if args.preview_blinded_plan:
        from benchmarks.human_rating.blinding import build_blinded_plan, validate_blinded_plan
        blinding_seed = protocol["blinding_seed"]
        min_sep = protocol.get("minimum_duplicate_separation", 3)
        plan = build_blinded_plan(
            selected, seed=blinding_seed,
            duplicate_count=protocol["duplicate_count"],
            min_duplicate_separation=min_sep,
        )
        validate_blinded_plan(plan, minimum_duplicate_separation=min_sep)
        # Print private preview table
        print(f"{'Pos':<4} {'Blinded ID':<12} {'Method':<16} {'Trial':<6} {'Dup Of':<12} {'Dist':<5}")
        print("-" * 60)
        # Build position lookup for distance calculation
        id_to_pos = {item.blinded_id: item.appearance_index for item in plan.items}
        for item in sorted(plan.items, key=lambda x: x.appearance_index):
            dup_of = item.duplicate_of_blinded_id or "—"
            dist = ""
            if item.duplicate_of_blinded_id:
                orig_pos = id_to_pos.get(item.duplicate_of_blinded_id, -1)
                if orig_pos >= 0:
                    dist = str(abs(item.appearance_index - orig_pos))
            print(
                f"{item.appearance_index + 1:<4} {item.blinded_id:<12} "
                f"{item.source_trial.source_method:<16} "
                f"{item.source_trial.original_trial_id:<6} "
                f"{dup_of:<12} {dist:<5}"
            )
        print(f"\nDuplicated sources: {plan.duplicated_source_identities}")
        return

    if not args.run_name:
        parser.error("--run-name is required when not using --preview-selection")

    # Full pipeline (blinding, duplicates, queue writing) — later subtask
    raise NotImplementedError(
        "Full sampling pipeline not yet implemented. Use --preview-selection."
    )


if __name__ == "__main__":
    main()
