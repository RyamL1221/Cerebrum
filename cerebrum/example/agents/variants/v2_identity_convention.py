"""V2 identity-convention: the agent tags the user with another
convention in its writes and requests (AIOS docs/HETEROGENEITY.md).

``email`` (the catalog's form) is ``<user_id>@users.example``; ``case``
upper-cases the id. Grounding: identity bugs hit while building this
benchmark (user-less searches, the latest_user_id guess that mixed
users); cross-user contamination in multi-agent memory (Yang et al.
2026); services that key users by email or by handle.
"""
from typing import Optional

from .base import Variant

EMAIL_DOMAIN = "users.example"
CONVENTIONS = ("email", "case")


class IdentityConvention(Variant):
    code = "V2"
    title = "identity-convention"
    aspects = frozenset({"identity"})

    def __init__(self, convention: str = "email"):
        if convention not in CONVENTIONS:
            raise ValueError(f"unknown convention {convention!r}")
        self.convention = convention

    def user_id(self, user_id: Optional[str]) -> Optional[str]:
        if not user_id:
            return user_id
        if self.convention == "email":
            return f"{user_id}@{EMAIL_DOMAIN}"
        return user_id.upper()


VARIANT = IdentityConvention("email")
