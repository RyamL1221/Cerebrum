"""Phase 2: Interactive CLI for rating blinded items.

Usage:
    python -m benchmarks.human_rating.rate \
        --queue human_rating_runs/gpt4o_human_eval/rater/rating_queue.json

This command:
1. Loads the blinded rating queue.
2. Presents items one at a time with the scoring rubric.
3. Records ratings to an append-only JSONL session file.
4. Supports resumption (skips already-rated items).

The rating command:
- Receives ONLY the queue path (ratings path is derived).
- Does NOT accept an answer-key argument.
- Does NOT import compilation code or the answer key.
- Does NOT scan parent directories.
- Does NOT print the private path.
- Operates correctly when the private directory is unavailable.
"""

import argparse


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for rate.

    Note: No --answer-key argument exists by design.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Rate blinded evaluation items on a 1–5 personalization "
        "scale. Ratings are append-only and cannot be edited.",
    )
    parser.add_argument(
        "--queue",
        type=str,
        required=True,
        help="Path to the blinded rating_queue.json file.",
    )
    return parser


def main() -> None:
    """Entry point for rate CLI."""
    parser = build_arg_parser()
    _args = parser.parse_args()
    # Implementation in a later subtask
    raise NotImplementedError("Rating CLI not yet implemented.")


if __name__ == "__main__":
    main()
