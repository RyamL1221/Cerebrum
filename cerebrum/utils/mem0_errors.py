"""The failures Mem0 logs and swallows during a write (AIOS
docs/BENCHMARK_V2.md, Amendment 9).

Mem0 2.0.2's ``Memory.add`` with extraction catches the errors of its
extraction LLM call, of parsing that call's reply, of embedding the
extracted facts and of inserting them, logs each on
``mem0.memory.main`` and goes on (``_add_to_vector_store``): a write
that hit one returns with fewer rows, or none, as a write whose
extraction found no fact does. ``swallowed_errors`` collects those log
lines while it is open, so a caller can tell the two apart. Mem0's
synchronous ``add`` runs on the caller's thread, so the lines collected
are those of the calls made on this thread.

The kernel's and the replicated agents' Mem0 provider
(``aios/memory/providers/mem0.py``) and the native agents
(``cerebrum/example/agents/native/agents.py``) use it.
"""
import contextlib
import logging
import threading
from typing import Iterator, List

MEM0_LOGGER = "mem0.memory.main"
# How the swallowed failures' messages begin (mem0/memory/main.py,
# ``_add_to_vector_store``; the asynchronous variants add "(async)").
SWALLOWED = (
    "LLM extraction failed",
    "Error parsing extraction response",
    "Failed to embed memory text",
    "Failed to insert memory",
)

_local = threading.local()
_lock = threading.Lock()


class _Collector(logging.Handler):
    """Appends a swallowed failure's message to the list open on the
    thread that logged it, if any."""

    def emit(self, record: logging.LogRecord) -> None:
        errors = getattr(_local, "errors", None)
        if errors is None:
            return
        try:
            message = record.getMessage()
        except Exception:  # a malformed record is not ours to report
            return
        if message.startswith(SWALLOWED):
            errors.append(message)


_collector = _Collector(level=logging.WARNING)


def _install() -> None:
    """Attach the collector once. It sees what Mem0's logger emits: a
    logger set above WARNING would hide an embedding failure (nothing in
    AIOS or Cerebrum sets it), and the collector leaves its level as it
    is."""
    logger = logging.getLogger(MEM0_LOGGER)
    with _lock:
        if _collector not in logger.handlers:
            logger.addHandler(_collector)


@contextlib.contextmanager
def swallowed_errors() -> Iterator[List[str]]:
    """Collect, into the list yielded, the messages of the failures Mem0
    logs and swallows on this thread while the block runs. A block
    nested in another hands its messages to the outer one too."""
    _install()
    outer = getattr(_local, "errors", None)
    errors: List[str] = []
    _local.errors = errors
    try:
        yield errors
    finally:
        _local.errors = outer
        if outer is not None:
            outer.extend(errors)
