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

from cerebrum.utils.redact import redact_report, secret_values

DEFAULT_AIOS = Path(__file__).resolve().parents[3] / "AIOS"


@lru_cache(maxsize=1)
def _file_configs() -> tuple:
    """The kernel checkout's ``.env`` and ``aios/config/config.yaml``
    (``AIOS_ROOT``, default the sibling ``AIOS``; each when it exists),
    read once a session."""
    root = Path(os.environ.get("AIOS_ROOT") or DEFAULT_AIOS)
    configs = []
    env_file = root / ".env"
    if env_file.is_file():
        from dotenv import dotenv_values

        configs.append({name.lower(): value for name, value
                        in dotenv_values(env_file).items()})
    config_file = root / "aios" / "config" / "config.yaml"
    if config_file.is_file():
        import yaml

        try:
            configs.append(yaml.safe_load(config_file.read_text()) or {})
        except yaml.YAMLError:
            pass
    return tuple(configs)


def report_secrets() -> tuple:
    """The environment's secret values (read at each report), and the
    kernel checkout's ``.env`` and ``config.yaml``'s."""
    return secret_values(*_file_configs())


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    redact_report(outcome.get_result(), report_secrets())
