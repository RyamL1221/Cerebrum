"""The heterogeneity schedule (AIOS docs/HETEROGENEITY.md, "Schedule").

Which agents deviate, and with which variant, is a pure function of
``(variant_seed, level, trial_index)``: never of the locus, backend,
model or run, so the cells of a sweep stay paired.

The 15 (agent, variant) pairs sit on a cycle: position k belongs to agent
``order[k % 3]`` (a seeded order of the three agents), and an agent's
five positions carry the five variants in a seeded order of its own, so
adjacent positions (14 and 0 included) are different agents. Level 1
gives user i position ``i % 15``; level 2 gives positions
``(5 + 2i) % 15`` and ``(6 + 2i) % 15``. The first five users of levels 1
and 2 together apply every pair once.
"""
import random
from typing import Dict, List, Tuple

from .base import AGENTS

VARIANT_CODES = ("V1", "V2", "V3", "V4", "V5")
LEVELS = (0, 1, 2)
CYCLE = len(AGENTS) * len(VARIANT_CODES)  # 15
OFFSETS = {1: 0, 2: 5}


def cycle(variant_seed: int) -> List[Tuple[str, str]]:
    """The seeded cycle of (agent, variant) pairs."""
    rng = random.Random(int(variant_seed))
    order = list(AGENTS)
    rng.shuffle(order)
    per_agent = {}
    for agent in order:
        per_agent[agent] = rng.sample(VARIANT_CODES, len(VARIANT_CODES))
    return [
        (order[k % len(order)], per_agent[order[k % len(order)]][
            k // len(order)])
        for k in range(CYCLE)
    ]


def schedule(variant_seed: int, level: int, trial_index: int) -> Dict[str, str]:
    """``{agent: variant}`` for trial ``trial_index`` at ``level``."""
    if level not in LEVELS:
        raise ValueError(f"heterogeneity level must be one of {LEVELS}")
    if trial_index < 0:
        raise ValueError("trial_index must be >= 0")
    if level == 0:
        return {}
    pairs = cycle(variant_seed)
    start = OFFSETS[level] + level * trial_index
    chosen = [pairs[(start + j) % CYCLE] for j in range(level)]
    out = dict(chosen)
    assert len(out) == level, chosen  # adjacent positions: distinct agents
    return out
