"""V1 stale-version: the agent runs the pipeline library one version
back (N-1), emulated (AIOS docs/HETEROGENEITY.md).

As a writer it keeps the old default sharing policy and writes
``private``; as the consumer it builds the legacy block (the kernel's
format before Subtask 9d). Grounding: version skew between separately
deployed services; this codebase's writers defaulted to private
(``share_memory`` False, since 2026-04-18), and the legacy block was the
kernel's format until 2026-11-05.
"""
from typing import Any, Dict

from .base import Variant


class StaleVersion(Variant):
    code = "V1"
    title = "stale-version"
    aspects = frozenset({"sharing", "retrieval"})

    def share_memory(self, reference: bool) -> bool:
        return False  # the N-1 default: private

    def retrieval(self, role: str) -> Dict[str, Any]:
        return {"block_format": "legacy"} if role == "consumer" else {}


VARIANT = StaleVersion()
