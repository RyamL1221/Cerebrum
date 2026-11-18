"""The failures Mem0 logs and swallows during a write
(``cerebrum.utils.mem0_errors``; AIOS docs/BENCHMARK_V2.md, Amendment 9).
The kernel's provider, against a real Mem0 store, is tested in AIOS
``tests/modules/memory/test_mem0_infer.py``."""
import inspect
import logging
import threading

import pytest

from cerebrum.utils import mem0_errors
from cerebrum.utils.mem0_errors import MEM0_LOGGER, SWALLOWED, swallowed_errors

LOGGER = logging.getLogger(MEM0_LOGGER)


def test_each_swallowed_failure_is_one_mem0_logs_in_its_add():
    """The prefixes are Mem0's own lines, logged in ``_add_to_vector_store``
    (mem0ai 2.0.2): a Mem0 that rewords one would make it invisible."""
    from mem0.memory.main import Memory

    source = inspect.getsource(Memory._add_to_vector_store)
    for prefix in SWALLOWED:
        assert (f'logger.error(f"{prefix}' in source
                or f'logger.warning(f"{prefix}' in source), prefix


def test_collects_the_swallowed_failures_logged_in_the_block():
    with swallowed_errors() as errors:
        LOGGER.error("LLM extraction failed: refused")
        LOGGER.warning("Failed to embed memory text: down")
        LOGGER.warning("Entity upsert failed for 'x': no spaCy")
        LOGGER.error("Configuration validation error: x")
    assert errors == ["LLM extraction failed: refused",
                      "Failed to embed memory text: down"]


def test_collects_nothing_outside_a_block_or_from_another_thread():
    LOGGER.error("LLM extraction failed: before")
    with swallowed_errors() as errors:
        other = threading.Thread(
            target=LOGGER.error, args=("LLM extraction failed: other",))
        other.start()
        other.join()
    LOGGER.error("LLM extraction failed: after")
    assert errors == []


def test_a_nested_block_hands_its_failures_to_the_outer_one():
    with swallowed_errors() as outer:
        with swallowed_errors() as inner:
            LOGGER.error("Failed to insert memory m1: disk")
        LOGGER.error("Error parsing extraction response: bad")
    assert inner == ["Failed to insert memory m1: disk"]
    assert outer == ["Failed to insert memory m1: disk",
                     "Error parsing extraction response: bad"]


@pytest.fixture
def quiet_mem0():
    level = LOGGER.level
    LOGGER.setLevel(logging.ERROR)
    yield
    LOGGER.setLevel(level)


def test_the_collector_leaves_mem0s_logger_level_alone(quiet_mem0):
    """The collector changes no process-wide logging: a logger set to
    ERROR stays at ERROR, and then hides an embedding failure (a
    WARNING) from the collector too; its errors are still collected."""
    with swallowed_errors() as errors:
        LOGGER.warning("Failed to embed memory text: down")
        LOGGER.error("LLM extraction failed: refused")
    assert LOGGER.level == logging.ERROR
    assert errors == ["LLM extraction failed: refused"]
    assert mem0_errors._collector in LOGGER.handlers
