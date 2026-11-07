"""The balanced heterogeneity schedule for pilot_v1 (NeurIPS Subtask 11,
AIOS docs/PILOT.md, "Schedule").

The seeded cycle schedule (``variants.schedule``) leaves pairings to
chance over a few users: in Subtask 10 the first 5 users never gave a
V3 consumer a private writer to leak, and V5 writers appeared outside
the kernel only next to a consumer that empties the block (known issue
34). This schedule is stratified over pilot_v1's 30 users instead and
committed as data (``data/pilot_v1_schedule.json``); every cell of the
pilot reads the same file, so cells pair by user.

- H = 1: each (variant x role) pairing, role writer or consumer, occurs
  3 times (10 pairings x 3 = 30 users). A writer slot alternates
  between ProfileAgent and TaskAgent.
- H = 2: two agents deviate, one variant each. With one consumer,
  "consumer-only" cannot occur, so the strata are writer-only (both
  writers; 15 users) and one-of-each (a writer and the consumer; 15
  users). In each stratum each variant fills each slot equally often.
  One-of-each never pairs a V5 writer with a consumer that empties the
  block (V2, V4), so V5 writers are isolated from blanking consumers in
  all 9 of their users; every V3 consumer gets a V1 or V3 writer, the
  pairing that lets a consumer that ignores visibility leak.

Regenerate (the test checks the committed file equals it):

    python -m benchmarks.shared_memory.pilot_schedule --write
"""
import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from cerebrum.example.agents.variants import (
    CATALOG_VERSION,
    CONSUMER,
    VARIANT_CODES,
    WRITERS,
)

NAME = "pilot_v1_schedule"
VERSION = 1
DATASET = "pilot_v1"
USERS = 30
SEED = 20261106
PATH = Path(__file__).resolve().parent / "data" / f"{NAME}.json"
# Consumers whose settings or identity empty the block outside the
# kernel (Subtask 10): a V5 writer next to them is not observed.
BLANKING_CONSUMERS = ("V2", "V4")
# Writers whose memories are not shared: a V3 consumer, which skips the
# visibility check, can leak them.
PRIVATE_WRITERS = ("V1", "V3")
COPIES = USERS // (2 * len(VARIANT_CODES))  # 3


def _alternate_writers(codes: List[str]) -> List[str]:
    """A writer agent for each writer slot: slots grouped by variant,
    alternating ProfileAgent / TaskAgent across the whole list."""
    order = sorted(range(len(codes)), key=lambda i: (codes[i], i))
    agents = [""] * len(codes)
    for n, i in enumerate(order):
        agents[i] = WRITERS[n % 2]
    return agents


def _level1(rng: random.Random) -> List[dict]:
    slots = [(role, code) for role in ("writer", "consumer")
             for code in VARIANT_CODES for _ in range(COPIES)]
    rng.shuffle(slots)
    writer_slots = [i for i, (role, _) in enumerate(slots)
                    if role == "writer"]
    agents = _alternate_writers([slots[i][1] for i in writer_slots])
    out = []
    agent_of = dict(zip(writer_slots, agents))
    for i, (role, code) in enumerate(slots):
        agent = agent_of.get(i, CONSUMER)
        out.append({"stratum": role, "variants": {agent: code}})
    return out


def _writer_only(rng: random.Random) -> List[dict]:
    """15 users: ProfileAgent Vi with TaskAgent V(i+k), k = 1, 2, 3."""
    codes = list(VARIANT_CODES)
    rows = []
    for shift in range(1, COPIES + 1):
        for i, code in enumerate(codes):
            rows.append({WRITERS[0]: code,
                         WRITERS[1]: codes[(i + shift) % len(codes)]})
    return [{"stratum": "writer_only", "variants": v} for v in rows]


def _allowed(writer: str, consumer: str) -> bool:
    if writer == "V5" and consumer in BLANKING_CONSUMERS:
        return False
    if consumer == "V3" and writer not in PRIVATE_WRITERS:
        return False
    return True


def _one_of_each(rng: random.Random) -> List[dict]:
    """15 users: consumer Vc with a writer Vw, each variant 3 times in
    each slot, under ``_allowed``; found by seeded backtracking."""
    consumers = [c for c in VARIANT_CODES for _ in range(COPIES)]
    pool = [w for w in VARIANT_CODES for _ in range(COPIES)]
    rng.shuffle(pool)
    chosen: List[Optional[str]] = [None] * len(consumers)

    def place(k: int, left: List[str]) -> bool:
        if k == len(consumers):
            return True
        for j, writer in enumerate(left):
            if writer in left[:j]:
                continue  # the same writer code again: same branch
            if _allowed(writer, consumers[k]):
                chosen[k] = writer
                if place(k + 1, left[:j] + left[j + 1:]):
                    return True
        return False

    if not place(0, pool):
        raise RuntimeError("no balanced one-of-each pairing")
    agents = _alternate_writers(list(chosen))
    return [
        {"stratum": "one_of_each",
         "variants": {agent: writer, CONSUMER: consumer}}
        for agent, writer, consumer in zip(agents, chosen, consumers)
    ]


def generate(seed: int = SEED) -> dict:
    """The schedule: ``levels[H][i]`` is user i's
    ``{stratum, variants: {agent: code}}``."""
    rng = random.Random(seed)
    level1 = _level1(rng)
    level2 = _writer_only(rng) + _one_of_each(rng)
    rng.shuffle(level2)
    return {
        "name": NAME,
        "version": VERSION,
        "dataset": DATASET,
        "users": USERS,
        "seed": seed,
        "catalog_version": CATALOG_VERSION,
        "levels": {
            "0": [{"stratum": "reference", "variants": {}}] * USERS,
            "1": level1,
            "2": level2,
        },
    }


def dumps(schedule: dict) -> str:
    return json.dumps(schedule, indent=1, sort_keys=True) + "\n"


class Schedule:
    """A schedule file loaded for a run."""

    def __init__(self, path: str):
        text = Path(path).read_text()
        self.path = str(path)
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.data = json.loads(text)
        self.name = self.data["name"]
        self.dataset = self.data["dataset"]

    def variants(self, level: int, trial_index: int) -> Dict[str, str]:
        rows = self.data["levels"][str(level)]
        if not 0 <= trial_index < len(rows):
            raise ValueError(
                f"{self.name} has no user {trial_index} at H = {level}"
            )
        return dict(rows[trial_index]["variants"])

    def stratum(self, level: int, trial_index: int) -> str:
        return self.data["levels"][str(level)][trial_index]["stratum"]

    def metadata(self) -> dict:
        return {"schedule": self.name, "schedule_sha256": self.sha256,
                "schedule_version": self.data["version"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true",
                        help=f"write {PATH.name}; else print it")
    args = parser.parse_args(argv)
    text = dumps(generate())
    if args.write:
        PATH.write_text(text)
        print(f"wrote {PATH}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
