"""No key value in the harness's logs or the tests' reports (NeurIPS
Subtask 17, Decision 3): a Subtask 16 mutation replay's test log held
the Azure key, a LiteLLM traceback's locals. ``cerebrum.utils.redact``
keeps AIOS ``aios/utils/redact.py``'s rules."""
import ast
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


LONG = "azure-test-key-0123456789abcdefGHIJKLMNOP"


@pytest.mark.parametrize("text, expected", [
    (f"Api Key:{LONG[:8]}***************",
     f"Api Key:{redact.REDACTED}***************"),
    (f"-H 'api-key: {LONG[:19]}...yyy",
     f"-H 'api-key: {redact.REDACTED}...yyy"),
    (f"xxx...{LONG[-13:]}' more", f"xxx...{redact.REDACTED}' more"),
    (f"api-key: {LONG[:4]}****{LONG[-4:]}",
     f"api-key: {redact.REDACTED}****{redact.REDACTED}"),
    (f"value {LONG[:7]} here", f"value {LONG[:7]} here"),
    ("we use shortsec here", "we use shortsec here"),
])
def test_a_fragment_of_a_long_secret_is_redacted(text, expected):
    """AIOS ``aios/utils/redact.py``'s rule: 8 consecutive characters of
    a secret of 20 or more, or a head or tail of 4 or more beside a
    mask."""
    values = (LONG, "shortsecret1")
    assert redact.redact_text(text, values) == expected
    assert redact.holds_secret(text, values) == (text != expected)


def test_the_harness_installs_the_redaction_first(monkeypatch):
    """``run_evaluation.main`` installs it (log records and the standard
    streams) before it parses its arguments, with the environment's
    secret values (the driver loads the kernel's .env into it)."""
    from benchmarks.shared_memory import run_evaluation

    monkeypatch.setenv("SOME_SERVICE_API_KEY", KEY)
    monkeypatch.setattr(sys, "argv", ["run_evaluation", "--help"])
    with patch.object(run_evaluation.redact,
                      "install_redaction") as install:
        with pytest.raises(SystemExit):
            run_evaluation.main()
    (values,), _ = install.call_args
    assert KEY in values


# A process's every text sink, each with a raised exception that carries
# the key: a print, a log record, a logged traceback, another thread's
# uncaught exception, LiteLLM's own traceback printed with its frames'
# locals (as a rich or a diagnose-mode handler prints it), and the main
# thread's uncaught exception; and LiteLLM's own debug log, on, whose
# Azure client logs the key's first 8 characters. Its stdout and stderr
# go to one file, as the drivers write a kernel's or the harness's log.
PROCESS = '''
import logging, os, sys, threading, traceback
from {module} import install_redaction, secret_values

if sys.argv[1] == "redact":
    install_redaction(secret_values())
KEY = os.environ["FAKE_SERVICE_API_KEY"]
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("sink")
print("sink-print", KEY)
log.warning("sink-log %s", KEY)
try:
    raise RuntimeError("sink-exception " + KEY)
except RuntimeError:
    log.exception("sink-logged-traceback")


def fail():
    raise RuntimeError("sink-thread " + KEY)


thread = threading.Thread(target=fail)
thread.start()
thread.join()


def call(api_key):
    import litellm

    litellm._turn_on_debug()
    return litellm.completion(
        model="azure/gpt-4o", api_key=api_key,
        api_base="http://127.0.0.1:9", api_version="2024-08-01-preview",
        num_retries=0, messages=[{{"role": "user", "content": "hi"}}])


try:
    call(KEY)
except Exception as error:
    print("sink-litellm", file=sys.stderr)
    sys.stderr.write("".join(traceback.TracebackException.from_exception(
        error, capture_locals=True).format()))
raise RuntimeError("sink-uncaught " + KEY)
'''
MARKERS = ("sink-print", "sink-log", "sink-exception",
           "sink-logged-traceback", "sink-thread", "sink-litellm",
           "sink-uncaught", "Initializing Azure OpenAI Client")


def fragments(text, key=None):
    """How many of the key's runs of 8 characters ``text`` holds: the
    whole key, or any part of it a mask or a cut left."""
    key = key or KEY
    return sum(key[i:i + 8] in text for i in range(len(key) - 7))


def run_process(tmp_path, module, mode):
    log = tmp_path / f"process_{mode}.log"
    env = {**os.environ, "FAKE_SERVICE_API_KEY": KEY,
           "LITELLM_LOCAL_MODEL_COST_MAP": "True",
           "PYTHONPATH": str(ROOT)}
    with open(log, "w") as out:
        code = subprocess.run(
            [sys.executable, "-c", PROCESS.format(module=module), mode],
            cwd=tmp_path, env=env, stdout=out, stderr=subprocess.STDOUT,
            timeout=120).returncode
    return code, log.read_text()


def test_a_process_log_carries_no_key_in_any_sink(tmp_path):
    """The harness's log (its stdout and stderr, which the driver writes
    to a cell's log): without the redaction every sink above prints the
    key; with it, none does."""
    code, text = run_process(tmp_path, "cerebrum.utils.redact", "plain")
    assert code == 1 and all(m in text for m in MARKERS)
    assert text.count(KEY) >= len(MARKERS) - 1
    # LiteLLM's own line: the head of the key, then asterisks.
    assert f"Api Key:{KEY[:8]}***************" in text
    code, text = run_process(tmp_path, "cerebrum.utils.redact", "redact")
    assert code == 1 and all(m in text for m in MARKERS), text[-2000:]
    assert not fragments(text)
    assert f"Api Key:{redact.REDACTED}***************" in text
    assert text.count(redact.REDACTED) >= len(MARKERS)


# Test sources whose report would print the key: a failing test's locals
# and captured output, an unmocked LiteLLM call (a long traceback prints
# each frame's arguments: the Subtask 16 replay log's leak), a module
# that raises while it is collected, and a long string local, which the
# report cuts at 240 characters, here through the key: its head stays.
SOURCES = {
    "locals": ('''
import logging
import os

def test_a_call_that_leaks():
    api_key = os.environ["FAKE_SERVICE_API_KEY"]
    print("captured", api_key)
    logging.getLogger("t").warning("logged %s", api_key)
    assert api_key == "something else"
''', "1 failed"),
    "litellm": ('''
import os

import litellm

def test_an_unmocked_litellm_call():
    litellm.completion(
        model="azure/gpt-4o", api_key=os.environ["FAKE_SERVICE_API_KEY"],
        api_base="http://127.0.0.1:9", api_version="2024-08-01-preview",
        num_retries=0, messages=[{"role": "user", "content": "hi"}])
''', "1 failed"),
    "collection": ('''
import os

raise RuntimeError("cannot import: " + os.environ["FAKE_SERVICE_API_KEY"])
''', "1 error"),
    "truncated": ('''
import os

def test_a_long_string_cut_through_the_key():
    command = ("curl " + "x" * 80 + " -H 'api-key: "
               + os.environ["FAKE_SERVICE_API_KEY"] + "' " + "y" * 300)
    raise RuntimeError("the call failed")
''', "1 failed"),
}


def run_pytest(tmp_path, source, *plugin):
    (tmp_path / "test_leak.py").write_text(source)
    xml = tmp_path / "report.xml"
    env = {**os.environ, "FAKE_SERVICE_API_KEY": KEY,
           "LITELLM_LOCAL_MODEL_COST_MAP": "True",
           "PYTHONPATH": str(ROOT)}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_leak.py", "-p",
         "no:cacheprovider", "--showlocals", f"--junitxml={xml}", *plugin],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    return result.stdout + result.stderr, xml.read_text()


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_a_test_report_carries_no_key(tmp_path, name):
    """The terminal (what a mutation replay log keeps) and the JUnit XML:
    without the plugin both print the key; with it, neither does."""
    source, outcome = SOURCES[name]
    terminal, xml = run_pytest(tmp_path, source)
    assert fragments(terminal) and fragments(xml)
    terminal, xml = run_pytest(tmp_path, source, "-p",
                               "cerebrum.utils.pytest_redact")
    assert outcome in terminal, terminal[-2000:]
    assert not fragments(terminal) and not fragments(xml)
    assert html.escape(redact.REDACTED) in xml


def test_the_suites_load_the_report_hooks():
    """tests/conftest.py imports both hooks, so every run of the suite
    (a mutation replay's included) loads them."""
    tree = ast.parse((ROOT / "tests" / "conftest.py").read_text())
    imported = {
        (n.module, alias.name) for n in tree.body
        if isinstance(n, ast.ImportFrom) for alias in n.names}
    assert {("cerebrum.utils.pytest_redact", "pytest_runtest_makereport"),
            ("cerebrum.utils.pytest_redact", "pytest_make_collect_report")
            } <= imported
