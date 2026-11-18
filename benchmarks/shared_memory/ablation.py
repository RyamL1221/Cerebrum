"""Kernel ablation switches in the harness (NeurIPS Subtask 19, AIOS
docs/ABLATION.md).

The switches, their values and the old controls' aliases are the AIOS
memory library's (``aios/memory/pipeline/ablation.py``), loaded from the
AIOS checkout by file path, as the scorer loads the library's matcher
(``probes.py``): the harness and the kernel read one definition.

A run's ablation is a dict of the switches that differ from the full
kernel (``{}`` for the full kernel): what ``--ablate`` and an aliased
``--control`` name, what the pre-flight compares with the kernel's
``/memory/config`` ``pipeline.ablate``, and what every ``TrialResult``
records as ``ablation``.
"""
import importlib.util
import sys
from typing import Any, Dict, Iterable, List, Optional

from cerebrum.example.agents.replicated.library import aios_root

ABLATION_PATH = (aios_root() / "aios" / "memory" / "pipeline"
                 / "ablation.py")
_MODULE = "benchmarks.shared_memory._library_ablation"


def _library_ablation():
    """The library's ablation module, loaded once from ``ABLATION_PATH``."""
    if _MODULE in sys.modules:
        return sys.modules[_MODULE]
    spec = importlib.util.spec_from_file_location(_MODULE, ABLATION_PATH)
    if spec is None or not ABLATION_PATH.is_file():
        raise ImportError(
            f"the memory library's ablation switches are not at "
            f"{ABLATION_PATH}: set AIOS_ROOT to the AIOS checkout"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = module  # dataclasses resolves it by name
    spec.loader.exec_module(module)
    return module


_library = _library_ablation()
Ablation = _library.Ablation
SWITCHES = _library.SWITCHES
ALIASES = _library.ALIASES
parse_switch = _library.parse_switch

# Where each locus implements a switch (ABLATION.md, "The mechanism"):
# the kernel all of them; a replicated agent those of the library it
# links, copied from the kernel's settings (it has no session binding,
# no canonicalization and no channel for another consumer's config);
# native agents those their own code has, visibility in the consumer
# and the writers' delete (``forget_scope: none``). Native revokes by
# owner and retires nothing, so a writer scope or supersession has no
# native counterpart.
LIBRARY_SWITCHES = frozenset(SWITCHES) - {"identity", "consumer_config"}
NATIVE_SWITCHES = {"visibility": ("off",), "forget_scope": ("none",)}


def run_ablation(ablate: Iterable[str] = (),
                 control: Optional[str] = None) -> Dict[str, Any]:
    """The switches a run turns off: each ``--ablate SWITCH[=VALUE]``
    and an aliased ``--control``. Raises ``ValueError`` for an unknown
    switch or value, or a switch named twice (by the flag or the
    alias)."""
    switches: Dict[str, Any] = {}
    for text in ablate or ():
        name, value = parse_switch(text)
        if name in switches:
            raise ValueError(f"--ablate names {name} twice")
        switches[name] = value
    for name, value in ALIASES.get(control, {}).items():
        if name in switches:
            raise ValueError(f"--control {control} already sets {name}")
        switches[name] = value
    return Ablation.from_config(switches).changed()


def locus_problems(ablation: Dict[str, Any], locus: str) -> List[str]:
    """Why ``locus`` cannot run ``ablation`` ([] when it can)."""
    problems = []
    for name, value in ablation.items():
        if locus == "kernel":
            continue
        if locus == "replicated" and name not in LIBRARY_SWITCHES:
            problems.append(f"{name}: a replicated agent has no "
                            "kernel to remove it from")
        if locus == "native" and value not in NATIVE_SWITCHES.get(name, ()):
            problems.append(f"{name}: {value} has no native counterpart")
    return problems


def kernel_problems(reported: Optional[Dict[str, Any]],
                    ablation: Dict[str, Any]) -> List[str]:
    """How the kernel's ``pipeline.ablate`` differs from ``ablation``
    ([] when they match in every switch). A kernel that reports no
    block predates the switches."""
    if reported is None:
        return ["the kernel reports no pipeline.ablate (it predates "
                "the ablation switches)"]
    try:
        kernel = Ablation.from_config(reported).changed()
    except ValueError as e:
        return [f"the kernel's pipeline.ablate is invalid: {e}"]
    if kernel == ablation:
        return []
    names = sorted(set(kernel) | set(ablation))
    return [f"ablate.{name} is {kernel.get(name, SWITCHES[name][0])!r}, "
            f"not {ablation.get(name, SWITCHES[name][0])!r}"
            for name in names if kernel.get(name) != ablation.get(name)]


def trial_ablation(trial: Dict[str, Any]) -> Dict[str, Any]:
    """A trial's ablation: its ``ablation``, or, for a trial written
    before Subtask 19, the alias of its ``control`` ({} for none)."""
    recorded = trial.get("ablation")
    if recorded is not None:
        return dict(recorded)
    return dict(ALIASES.get(trial.get("control"), {}))
