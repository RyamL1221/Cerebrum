"""No key value in the harness's logs or the tests' reports (NeurIPS
Subtask 17, Decision 3): a Subtask 16 mutation replay's test log held
the Azure key, a LiteLLM traceback's locals. ``cerebrum.utils.redact``
keeps AIOS ``aios/utils/redact.py``'s rules."""
import html
import io
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cerebrum.utils import redact

KEY = "azure-test-key-0123456789abcdef"
ROOT = Path(__file__).resolve().parents[2]


def test_secret_values_are_the_environments_and_the_configs():
    environ = {"AZURE_API_KEY": KEY, "AZURE_API_BASE": "https://base.test",
               "NEO4J_PASSWORD": "neo4j-password-123", "HF_TOKEN": "short"}
    config = {"memory": {"mem0": {"api_key": "mem0-key-0123456789"}},
              "max_memory_tokens": 300}
    values = redact.secret_values(config, environ=environ)
    assert set(values) == {KEY, "neo4j-password-123", "mem0-key-0123456789"}


@pytest.fixture
def redacting():
    factory = logging.getLogRecordFactory()
    yield redact.install_log_redaction
    logging.setLogRecordFactory(factory)
    redact._REDACTION["values"] = ()


def test_log_records_carry_no_key_in_message_or_traceback(redacting):
    redacting([KEY])
    out = io.StringIO()
    handler = logging.StreamHandler(out)
    logger = logging.getLogger("test.redaction.cerebrum")
    logger.addHandler(handler)
    logger.propagate = False
    try:
        logger.warning("calling with api_key=%s", KEY)
        try:
            raise RuntimeError(f"auth failed for {KEY}")
        except RuntimeError:
            logger.exception("the call failed")
    finally:
        logger.removeHandler(handler)
    text = out.getvalue()
    assert KEY not in text
    assert text.count(redact.REDACTED) == 2
    assert "Traceback" in text


def test_the_harness_installs_the_log_redaction_first(monkeypatch):
    """``run_evaluation.main`` installs it before it parses its
    arguments, with the environment's secret values (the driver loads
    the kernel's .env into it)."""
    from benchmarks.shared_memory import run_evaluation

    monkeypatch.setenv("SOME_SERVICE_API_KEY", KEY)
    monkeypatch.setattr(sys, "argv", ["run_evaluation", "--help"])
    with patch.object(run_evaluation.redact,
                      "install_log_redaction") as install:
        with pytest.raises(SystemExit):
            run_evaluation.main()
    (values,), _ = install.call_args
    assert KEY in values


FAILING_TEST = '''
import os

def test_a_call_that_leaks():
    api_key = os.environ["FAKE_SERVICE_API_KEY"]
    assert api_key == "something else"
'''


def run_pytest(tmp_path, *plugin):
    (tmp_path / "test_leak.py").write_text(FAILING_TEST)
    xml = tmp_path / "report.xml"
    env = {**os.environ, "FAKE_SERVICE_API_KEY": KEY,
           "PYTHONPATH": str(ROOT)}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_leak.py", "-p",
         "no:cacheprovider", "--showlocals", f"--junitxml={xml}", *plugin],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    return result.stdout + result.stderr, xml.read_text()


def test_a_test_report_carries_no_key(tmp_path):
    """A failing test whose locals hold a key: without the plugin both
    the terminal and the JUnit XML print it; with it, neither does."""
    terminal, xml = run_pytest(tmp_path)
    assert KEY in terminal and KEY in xml
    terminal, xml = run_pytest(tmp_path, "-p",
                               "cerebrum.utils.pytest_redact")
    assert "1 failed" in terminal
    assert KEY not in terminal and KEY not in xml
    assert html.escape(redact.REDACTED) in xml
