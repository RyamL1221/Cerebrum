"""One faulty agent (NeurIPS Subtask 18, AIOS docs/STRESS_DIMENSIONS.md,
"A faulty agent").

Faults reach an agent through ``apply_variant``, like variants:

- ``wrong_user``: a writer tags every memory request with another
  user's id, the victim's (``WrongUser``, the ``identity`` aspect);
- ``missing_metadata``: V3 of the catalog, unchanged;
- ``flood10``, ``flood50``: a writer stores F more rows after its own
  events in every session where it writes (``Flood``, the ``flood``
  aspect; ``shared_memory_utils.flood_writes`` makes the rows).

``faulty_agent`` picks the trial's faulty agent: a pure function of the
fault seed, the fault, the trial index and the candidates (the agents
the fault applies to that have something to do in the user's history,
in the dataset's agent order), never of the locus, so cells stay
paired.
"""
import random
from typing import List, Optional, Sequence

from .base import Variant
from .v3_missing_metadata import VARIANT as V3

FAULTS = ("none", "wrong_user", "missing_metadata", "flood10", "flood50")
FLOOD_ROWS = {"flood10": 10, "flood50": 50}
# The faults a writer only can have; missing_metadata reaches the
# consumer too (V3's consumer applies no visibility rule).
WRITER_FAULTS = ("wrong_user", "flood10", "flood50")


class WrongUser(Variant):
    code = "wrong_user"
    title = "wrong user id"
    aspects = frozenset({"identity"})

    def __init__(self, victim_id: str):
        if not victim_id:
            raise ValueError("wrong_user needs the victim's id")
        self.victim_id = victim_id

    def user_id(self, user_id: Optional[str]) -> Optional[str]:
        return self.victim_id


class Flood(Variant):
    title = "flooding writer"
    aspects = frozenset({"flood"})

    def __init__(self, rows: int):
        if rows < 1:
            raise ValueError("a flood needs at least one row")
        self.rows = rows
        self.code = f"flood{rows}"

    def flood_rows(self) -> int:
        return self.rows


def fault_variant(fault: str, victim_id: Optional[str] = None) -> Optional[Variant]:
    """The variant that applies ``fault`` (None for ``none``)."""
    if fault not in FAULTS:
        raise ValueError(f"fault must be one of {FAULTS}")
    if fault == "none":
        return None
    if fault == "wrong_user":
        return WrongUser(victim_id)
    if fault == "missing_metadata":
        return V3
    return Flood(FLOOD_ROWS[fault])


def faulty_agent(fault_seed: int, fault: str, trial_index: int,
                 candidates: Sequence[str]) -> Optional[str]:
    """The trial's faulty agent: the candidates rotated by a seeded
    offset per fault, user i taking candidate i mod their count."""
    if fault == "none":
        return None
    if fault not in FAULTS:
        raise ValueError(f"fault must be one of {FAULTS}")
    candidates: List[str] = list(candidates)
    if not candidates:
        raise ValueError(f"no agent can have {fault} in this history")
    offset = random.Random(f"{int(fault_seed)}:{fault}").randrange(
        len(candidates))
    return candidates[(trial_index + offset) % len(candidates)]
