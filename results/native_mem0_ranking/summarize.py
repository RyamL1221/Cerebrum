"""Summarize ``replay.json`` (``replay.py``) as markdown.

For the recall, recency and contradiction probes of every user: where
Mem0 put the target's own row (rank, score) against its rank by cosine,
whether it reached the consumer's fetch, and how many rows Mem0 scored
1.0 above it. For the users given (default 0 to 4), the recall and
recency probes in full: every row Mem0 ranked above the target, with its
rank, Mem0 score, cosine and content, and what became of it: in the
block, hidden (fetched, but another agent's private row) or cut (below
the consumer's k).

    python3 results/native_mem0_ranking/summarize.py \\
        results/native_mem0_ranking/replay.json > summary.md
"""
import argparse
import json
import statistics
import textwrap

TYPES = ("recall", "recency", "contradiction")


def target(probe):
    """The target's own row ranked highest by Mem0, or None."""
    rows = [r for r in probe["order"] if r["target"]]
    return min(rows, key=lambda r: r["rank"]) if rows else None


def aggregate(probes):
    lines = [
        "| Probe | n | target nearest by cosine | target in the fetch "
        "| target's Mem0 rank, median (range) | rows at 1.0 above it, "
        "median (range) | target's cosine, range |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for kind in TYPES:
        group = [p for p in probes if p["type"] == kind]
        found = [(p, target(p)) for p in group]
        found = [(p, t) for p, t in found if t is not None]
        ranks = [t["rank"] for _, t in found]
        above = [sum(1 for r in p["order"][:t["rank"] - 1]
                     if r["mem0_score"] >= 1.0) for p, t in found]
        cosines = [t["cosine"] for _, t in found]
        lines.append(
            f"| {kind} | {len(group)} "
            f"| {sum(t['cosine_rank'] == 1 for _, t in found)} "
            f"| {sum(t['in_fetch'] for _, t in found)} "
            f"| {statistics.median(ranks):g} ({min(ranks)} to {max(ranks)}) "
            f"| {statistics.median(above):g} ({min(above)} to {max(above)}) "
            f"| {min(cosines):.2f} to {max(cosines):.2f} |")
        missing = len(group) - len(found)
        if missing:
            lines.append(f"| {kind}: no target row in Mem0's order "
                         f"| {missing} | | | | | |")
    return lines


def detail(probe):
    t = target(probe)
    head = (f"**User {probe['user']}, {probe['type']}** "
            f"(`{probe['probe_id']}`): \"{probe['question']}\", expected "
            f"{', '.join(probe['expected'])}")
    if probe["stale"]:
        head += f", stale {', '.join(probe['stale'])}"
    verdict = "passed" if probe["passed"] else "failed"
    if probe["contaminated"]:
        verdict += ", through an earlier probe's answer"
    head += f"; {verdict}. {probe['rows_at_probe']} rows in the store."
    lines = [textwrap.fill(head, 72), ""]
    if t is None:
        return lines + ["The target's row is not in Mem0's order.", ""]
    lines += [
        textwrap.fill(
            f"Target row: rank {t['rank']} of {len(probe['order'])}, Mem0 "
            f"score {t['mem0_score']:.3f}, cosine {t['cosine']:.3f} (rank "
            f"{t['cosine_rank']} by cosine): \"{t['content']}\"", 72),
        "",
        "| Rank | Score | Cosine | Seen | Row |",
        "|---:|---:|---:|---|---|",
    ]
    for row in probe["order"][:t["rank"] - 1]:
        seen = ("cut" if not row["in_fetch"]
                else "in block" if row["injected"] else "hidden")
        lines.append(
            f"| {row['rank']} | {row['mem0_score']:.3f} "
            f"| {row['cosine']:.3f} | {seen} "
            f"| {row['content']} |")
    return lines + [""]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("replay")
    parser.add_argument("--users", default="0,1,2,3,4")
    args = parser.parse_args()
    with open(args.replay) as handle:
        data = json.load(handle)
    probes = data["probes"]
    users = [int(u) for u in args.users.split(",")]
    clamped = sum(all(r["score_is_clamped_distance"] for r in p["order"])
                  for p in probes)
    lines = [
        "# Native Mem0's order in the smoke (s14b)",
        "",
        f"Replayed {len(probes)} probes; the replay reproduced "
        f"{data['reproduced']} recorded fetches (the row count, and the "
        "rows shown, their order and scores; a row the sharing rule hid "
        "is recorded only as a count). "
        f"In {clamped} of {len(probes)}, every row's Mem0 score is its "
        "squared L2 distance to the question, capped at 1.0. Mem0's "
        f"history: {data['history_events']}.",
        "",
    ] + aggregate(probes) + [""]
    for user in users:
        for kind in ("recall", "recency"):
            for probe in probes:
                if probe["user"] == user and probe["type"] == kind:
                    lines += detail(probe)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
