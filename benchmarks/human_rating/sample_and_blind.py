"""Phase 1: Sample trials from automated results and produce blinded queue.

Usage:
    python -m benchmarks.human_rating.sample_and_blind \
        --results-dir results/post_fix_gpt4o/ \
        --run-name gpt4o_human_eval \
        --seed 12345

This command:
1. Loads automated evaluation results from one or more result directories.
2. Normalizes trials into SourceTrial objects.
3. Stratified-samples trials across method × question_type cells.
4. Inserts duplicate items for intra-rater consistency measurement.
5. Assigns blinded IDs and shuffles presentation order.
6. Writes the blinded rating queue (rater-visible) and answer key (private).

Output:
    human_rating_runs/<run_name>/rater/rating_queue.json
    human_rating_runs/<run_name>/private/answer_key.json
"""

import argparse


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for sample_and_blind.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Sample trials from automated results and produce a "
        "blinded rating queue for human evaluation.",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        required=True,
        nargs="+",
        help="One or more directories containing automated evaluation results.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        required=True,
        help="Name for this human-rating run (used as directory name).",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help="Base directory for human_rating_runs (default: human_rating_runs/).",
    )
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
    _args = parser.parse_args()
    # Implementation in a later subtask
    raise NotImplementedError("Sampling logic not yet implemented.")


if __name__ == "__main__":
    main()
