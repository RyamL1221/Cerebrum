"""Phase 3: Compile ratings with the answer key and compute metrics.

Usage:
    python -m benchmarks.human_rating.compile_ratings \
        --run-dir human_rating_runs/gpt4o_human_eval/

This command:
1. Loads the answer key from private/.
2. Loads the completed ratings from rater/.
3. Joins them on blinded_id.
4. Computes human-judge agreement and intra-rater consistency.
5. Writes flat CSV and summary JSON outputs to compiled/.

Output:
    human_rating_runs/<run_name>/compiled/item_level_results.csv
    human_rating_runs/<run_name>/compiled/method_question_type_summary.csv
    human_rating_runs/<run_name>/compiled/human_judge_agreement.json
    human_rating_runs/<run_name>/compiled/intra_rater_consistency.json
"""

import argparse


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for compile_ratings.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Compile human ratings with the answer key and compute "
        "human-judge agreement and intra-rater consistency metrics.",
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        required=True,
        help="Path to the human-rating run directory.",
    )
    return parser


def main() -> None:
    """Entry point for compile_ratings CLI."""
    parser = build_arg_parser()
    _args = parser.parse_args()
    # Implementation in a later subtask
    raise NotImplementedError("Compilation logic not yet implemented.")


if __name__ == "__main__":
    main()
