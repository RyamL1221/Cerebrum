"""Heterogeneity variants: realistic ways an agent is built differently
from the reference (NeurIPS Subtask 10, AIOS docs/HETEROGENEITY.md).

One module per variant (``v1_stale_version`` ... ``v5_raw_payload_writer``),
each applicable to any of the three agents in any of the kernel,
replicated and native loci through ``apply_variant``; ``schedule`` picks
which agents deviate per trial.
"""
from .base import (
    AGENTS,
    CONSUMER,
    LOCI,
    WRITERS,
    Variant,
    apply_variant,
    role_of,
)
from .schedule import VARIANT_CODES, cycle, schedule
from .v1_stale_version import VARIANT as V1
from .v2_identity_convention import VARIANT as V2
from .v3_missing_metadata import VARIANT as V3
from .v4_tuned_consumer import VARIANT as V4
from .v5_raw_payload_writer import VARIANT as V5

# Bumped when a variant's behavior changes; recorded in results.
CATALOG_VERSION = 1
CATALOG = {variant.code: variant for variant in (V1, V2, V3, V4, V5)}
assert tuple(CATALOG) == VARIANT_CODES


def variant(code: str) -> Variant:
    """The catalog's variant ``code`` (``"V1"`` ... ``"V5"``)."""
    try:
        return CATALOG[code]
    except KeyError:
        raise ValueError(f"unknown variant {code!r}") from None


__all__ = [
    "AGENTS", "CATALOG", "CATALOG_VERSION", "CONSUMER", "LOCI",
    "VARIANT_CODES", "WRITERS", "Variant", "apply_variant", "cycle",
    "role_of", "schedule", "variant",
]
