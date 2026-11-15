# Test reports without key values (Subtask 17, Decision 3).
"""A pytest plugin that removes key values from every test report.

Tests that reach the local Neo4j or a backend read the kernel's
``AIOS/.env``, so a call a test leaves unmocked can carry a key, and a
traceback's locals print it. Every report's failure text and captured
output are redacted before the terminal or a JUnit XML file prints
them. ``tests/conftest.py`` imports the hook; ``-p
cerebrum.utils.pytest_redact`` loads it elsewhere.
"""
import os
from functools import lru_cache
from pathlib import Path

import pytest

from cerebrum.utils.redact import (
    file_secret_configs,
    redact_report,
    secret_values,
)

DEFAULT_AIOS = Path(__file__).resolve().parents[3] / "AIOS"


@lru_cache(maxsize=1)
def _file_configs() -> tuple:
    """The kernel checkout's ``.env`` and ``aios/config/config.yaml``
    (``AIOS_ROOT``, default the sibling ``AIOS``), read once a
    session."""
    return file_secret_configs(os.environ.get("AIOS_ROOT") or DEFAULT_AIOS)


def report_secrets() -> tuple:
    """The environment's secret values (read at each report), and the
    kernel checkout's ``.env`` and ``config.yaml``'s."""
    return secret_values(*_file_configs())


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    redact_report(outcome.get_result(), report_secrets())


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    """A module that fails to import or raises while collected."""
    outcome = yield
    redact_report(outcome.get_result(), report_secrets())
