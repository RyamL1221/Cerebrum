"""Phase 1: Sample trials from automated results and produce blinded queue.

Usage (explicit per-method paths):
    python -m benchmarks.human_rating.sample_and_blind \
        --naive-concat-results results/gpt4o_naive_concat/results_naive_concat.json \
        --vanilla-rag-results results/gpt4o_vanilla_rag/results_vanilla_rag.json \
        --mem0-default-results results/gpt4o_mem0_default/results_mem0_default.json \
        --kernel-shared-results results/gpt4o_kernel_shared/results_kernel_shared.json \
        --run-name gpt4o_human_eval \
        --seed 12345

Usage (auto-discovery from results root):
    python -m benchmarks.human_rating.sample_and_blind \
        --results-dir results/ \
        --run-name gpt4o_human_eval \
        --seed 12345

This command:
1. Loads automated evaluation results from one or more result directories.
2. Normalizes trials into SourceTrial objects.
3. Validates pool eligibility (all methods, both question types, min per cell).
4. (Later subtask) Stratified-samples trials across method × question_type cells.
5. (Later subtask) Inserts duplicate items for intra-rater consistency.
6. (Later subtask) Assigns blinded IDs and shuffles presentation order.
7. (Later subtask) Writes the blinded rating queue and answer key.

Output:
    human_rating_runs/<run_name>/rater/rating_queue.json
    human_rating_runs/<run_name>/private/answer_key.json
"""

import argparse
import sys


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for sample_and_blind.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Sample trials from automated results and produce a "
        "blinded rating queue for human evaluation.",
    )

    # --- Source result file arguments (explicit per-method) ---
    source_group = parser.add_argument_group(
        "source results (explicit per-method paths)"
    )
    source_group.add_argument(
        "--naive-concat-results",
        type=str,
        default=None,
        help="Path to naive_concat results JSON file.",
    )
    source_group.add_argument(
        "--vanilla-rag-results",
        type=str,
        default=None,
        help="Path to vanilla_rag results JSON file.",
    )
    source_group.add_argument(
        "--mem0-default-results",
        type=str,
        default=None,
        help="Path to mem0_default results JSON file.",
    )
    source_group.add_argument(
        "--kernel-shared-results",
        type=str,
        default=None,
        help="Path to kernel_shared results JSON file.",
    )

    # --- Auto-discovery alternative ---
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help=(
            "Root directory for auto-discovery of result files. "
            "Alternative to explicit per-method paths."
        ),
    )

    # --- Output configuration ---
    parser.add_argument(
        "--run-name",
        type=str,
        required=True,
        help="Name for this human-rating run (used as directory name).",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default=None,
        help="Base directory for human_rating_runs (default: human_rating_runs/).",
    )

    # --- Sampling parameters ---
    parser.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="Master seed for sampling reproducibility (default: 12345).",
    )
    parser.add_argument(
        "--total-items",
        type=int,
        default=30,
        help="Total items in the rating queue including duplicates (default: 30).",
    )
    parser.add_argument(
        "--duplicates",
        type=int,
        default=6,
        help="Number of duplicate items for consistency checks (default: 6).",
    )

    return parser


def main() -> None:
    """Entry point for sample_and_blind CLI."""
    parser = build_arg_parser()
    args = parser.parse_args()

    # Validate source arguments: either explicit paths or results-dir
    explicit_paths = {
        "naive_concat": args.naive_concat_results,
        "vanilla_rag": args.vanilla_rag_results,
        "mem0_default": args.mem0_default_results,
        "kernel_shared": args.kernel_shared_results,
    }
    has_explicit = any(v is not None for v in explicit_paths.values())

    if has_explicit and args.results_dir:
        parser.error(
            "Cannot use both explicit per-method paths and --results-dir. "
            "Choose one approach."
        )

    if not has_explicit and not args.results_dir:
        parser.error(
            "Must provide either explicit per-method result paths "
            "(--naive-concat-results, etc.) or --results-dir for auto-discovery."
        )

    if has_explicit:
        # Ensure ALL four are provided
        missing = [m for m, p in explicit_paths.items() if p is None]
        if missing:
            parser.error(
                f"When using explicit paths, all four methods must be provided. "
                f"Missing: {missing}"
            )

    # Sampling logic will be implemented in a later subtask
    print(f"Run name: {args.run_name}")
    print(f"Seed: {args.seed}")
    print(f"Total items: {args.total_items}")
    print(f"Duplicates: {args.duplicates}")

    if has_explicit:
        print("Mode: explicit per-method paths")
        for method, path in sorted(explicit_paths.items()):
            print(f"  {method}: {path}")
    else:
        print(f"Mode: auto-discovery from {args.results_dir}")

    # Implementation in a later subtask
    raise NotImplementedError("Sampling logic not yet implemented.")


if __name__ == "__main__":
    main()
