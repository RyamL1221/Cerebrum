"""The native agents' sharing convention (docs/NATIVE_USAGE.md in AIOS).

Shared by the three agents of a native condition, as one developer
writing them would share it. The kernel conditions enforce the same rule
in the kernel; here the agents enforce it themselves.
"""
from datetime import datetime, timezone
from typing import Any, Dict

SHARED = "shared"
PRIVATE = "private"


def memory_metadata(
    owner_agent: str, user_id: str, memory_type: str, sharing_policy: str
) -> Dict[str, Any]:
    """The metadata every native write carries."""
    return {
        "owner_agent": owner_agent,
        "user_id": user_id,
        "memory_type": memory_type,
        "sharing_policy": sharing_policy,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def in_partition(user_id: str, metadata: Dict[str, Any]) -> bool:
    """The memory belongs to the user being served."""
    return bool(user_id) and metadata.get("user_id") == user_id


def visible(agent_name: str, metadata: Dict[str, Any]) -> bool:
    """Agent A sees its own memories and memories shared exactly as
    ``"shared"``. Missing keys mean not visible."""
    return (
        metadata.get("owner_agent") == agent_name
        or metadata.get("sharing_policy") == SHARED
    )
