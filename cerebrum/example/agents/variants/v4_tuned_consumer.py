"""V4 tuned-consumer: the agent uses its own retrieval config, k 5,
relevance threshold 0.5 and a 1500-token budget, against the kernel's
10 / 0.0 / 2000 (AIOS docs/HETEROGENEITY.md).

Grounding: per-agent tuning in multi-team deployments. The values are
this codebase's own documented ones: ``config.yaml.example`` shipped
``relevance_threshold: 0.5`` from 2026-04-12 to 2026-11-02 and still
ships k 5 / 1500.
"""
from typing import Any, Dict

from .base import Variant

TUNED = {"k": 5, "relevance_threshold": 0.5, "max_memory_tokens": 1500}


class TunedConsumer(Variant):
    code = "V4"
    title = "tuned-consumer"
    aspects = frozenset({"retrieval"})

    def retrieval(self, role: str) -> Dict[str, Any]:
        return dict(TUNED)


VARIANT = TunedConsumer()
