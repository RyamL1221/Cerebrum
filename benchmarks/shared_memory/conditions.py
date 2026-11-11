"""Condition names for the shared memory evaluation harness.

The one place that knows a condition's deprecated names. Everything else
resolves a name with ``canonical_condition`` and finds a results file with
``results_path``, so old invocations and old results directories still
work.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONDITIONS = ("kernel_shared", "naive_concat", "vanilla_rag", "kernel_private")

# Agents manage memory themselves (docs/NATIVE_USAGE.md in AIOS): the
# kernel must run with injection and extraction off.
NATIVE_CONDITIONS = ("native_mem0", "native_inhouse", "native_graphiti")

# Every agent runs the kernel's memory pipeline library itself
# (docs/REPLICATED_LOGIC.md in AIOS): the kernel must run with injection
# and extraction off, as for the native conditions.
REPLICATED_CONDITIONS = ("replicated_mem0", "replicated_inhouse",
                         "replicated_graphiti")

# Conditions whose agents manage memory themselves.
AGENT_MANAGED_CONDITIONS = NATIVE_CONDITIONS + REPLICATED_CONDITIONS

# Conditions that need the kernel to inject memories.
KERNEL_INJECTION_CONDITIONS = ("kernel_shared", "kernel_private")


def locus_of(condition: str) -> str:
    """Where a condition's memory logic runs: ``kernel``,
    ``replicated`` (the kernel's library, in each agent), ``native``
    (the backend's own SDK, in each agent), or ``none`` (no memory
    system: the context-in-prompt baselines)."""
    condition = canonical_condition(condition)
    if condition in KERNEL_INJECTION_CONDITIONS:
        return "kernel"
    if condition in REPLICATED_CONDITIONS:
        return "replicated"
    if condition in NATIVE_CONDITIONS:
        return "native"
    return "none"

# Deprecated name -> current name. ``mem0_default`` was the kernel pipeline
# with sharing off, not Mem0's own behavior.
CONDITION_ALIASES = {"mem0_default": "kernel_private"}


def canonical_condition(name: str) -> str:
    """Return a condition's current name, warning on a deprecated one."""
    current = CONDITION_ALIASES.get(name)
    if current is None:
        return name
    logger.warning(
        "condition %r is deprecated; using %r", name, current
    )
    return current


def legacy_names(name: str) -> list:
    """Return a condition's current name followed by its old names."""
    return [name] + [
        old for old, current in CONDITION_ALIASES.items() if current == name
    ]


def results_path(directory: Path, model: str, condition: str) -> Path:
    """Return one cell's results JSON, ``<model>_<name>/results_<name>.json``,
    under the current name or, for files written before a rename, an old
    one. Falls back to the current name's path when none exists."""
    for name in legacy_names(canonical_condition(condition)):
        path = Path(directory) / f"{model}_{name}" / f"results_{name}.json"
        if path.exists():
            return path
    name = canonical_condition(condition)
    return Path(directory) / f"{model}_{name}" / f"results_{name}.json"
