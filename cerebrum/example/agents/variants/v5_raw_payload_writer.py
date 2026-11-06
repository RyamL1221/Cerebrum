"""V5 raw-payload-writer: the agent writes the structured JSON instead
of the plain-language rendering (AIOS docs/HETEROGENEITY.md).

A writer's memory text becomes its validated fields as JSON (what it
already keeps in ``metadata.structured``); the consumer's conversation
write becomes the turn as JSON. Grounding: frameworks differ on whether
a memory is a record or a sentence; Subtask 6 observed writers whose
stored outputs were JSON.
"""
import json
from typing import Any, Dict, Tuple

from .base import Variant


class RawPayloadWriter(Variant):
    code = "V5"
    title = "raw-payload-writer"
    aspects = frozenset({"write"})

    def write(
        self, content: str, metadata: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        if content is None:
            return content, metadata
        if metadata.get("structured"):
            return metadata["structured"], metadata
        if (metadata.get("memory_type") == "conversation"
                and content.startswith("User: ")
                and "\nAssistant: " in content):
            user, _, assistant = content[len("User: "):].partition(
                "\nAssistant: "
            )
            return json.dumps(
                {"user": user, "assistant": assistant}, sort_keys=True
            ), metadata
        return content, metadata


VARIANT = RawPayloadWriter()
