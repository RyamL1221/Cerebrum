"""Import the kernel's memory pipeline library from the AIOS checkout.

The library is ``aios.memory.pipeline`` in the AIOS repo. This Cerebrum
checkout has its own ``aios/`` package (a development stub some tests
import), which shadows the kernel's when Python runs from the Cerebrum
directory. So the kernel's package is imported from ``AIOS_ROOT``
(default: the sibling ``AIOS`` checkout) before anything imports the
stub; in the kernel's own environment it is already importable.
"""
import importlib
import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[4].parent / "AIOS"


def aios_root() -> Path:
    return Path(os.environ.get("AIOS_ROOT") or DEFAULT_ROOT)


def load():
    """The ``aios.memory.pipeline`` module of the kernel."""
    if "aios" not in sys.modules:
        root = str(aios_root())
        sys.path.insert(0, root)
        try:
            importlib.import_module("aios.memory.pipeline")
        finally:
            sys.path.remove(root)
    try:
        return importlib.import_module("aios.memory.pipeline")
    except ImportError as e:
        raise ImportError(
            f"aios resolves to {sys.modules['aios'].__file__}, not the "
            "kernel's package with aios.memory.pipeline: this process "
            "imported the Cerebrum aios/ stub first. Set AIOS_ROOT to the "
            "AIOS checkout and load the replicated agents before anything "
            "imports aios."
        ) from e
