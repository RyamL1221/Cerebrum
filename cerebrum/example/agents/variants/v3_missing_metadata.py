"""V3 missing-metadata: the agent omits ``owner_agent`` and
``sharing_policy`` on every write it makes, and as the consumer applies
no visibility rule of its own (AIOS docs/HETEROGENEITY.md).

Grounding: agents that skip access control (the motivation of
Collaborative Memory and SSGM). Provenance fields are kept: they are
the benchmark's instrumentation, not the agent's metadata.
"""
from typing import Any, Dict, Tuple

from .base import Variant

OMITTED = ("owner_agent", "sharing_policy")


class MissingMetadata(Variant):
    code = "V3"
    title = "missing-metadata"
    aspects = frozenset({"write", "access_control"})

    def write(
        self, content: str, metadata: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return content, {
            key: value for key, value in metadata.items()
            if key not in OMITTED
        }

    def access_control(self) -> bool:
        return False


VARIANT = MissingMetadata()
