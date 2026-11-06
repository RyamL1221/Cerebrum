"""Tests for the live-kernel guard in tests/conftest.py.

Each case runs a small test file in a pytester directory that uses a
copy of the real conftest, with a dummy HTTP server on a free port in
place of the kernel.
"""

import http.server
import pathlib
import socketserver
import threading

import pytest

CONFTEST = pathlib.Path(__file__).with_name("conftest.py").read_text()


@pytest.fixture
def dummy_kernel():
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            # Read the body first: closing with unread data sends a reset.
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        do_GET = do_POST

        def log_message(self, *args):
            pass

    # TCPServer: HTTPServer.server_bind does a reverse DNS lookup that
    # can stall on macOS.
    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1], hits
    server.shutdown()
    server.server_close()


def _setup(pytester, port, body):
    conftest = CONFTEST.replace(
        "endpoints = {(h, 8000) for h in _LOCAL_HOSTS}",
        f"endpoints = {{(h, {port}) for h in _LOCAL_HOSTS}}",
    )
    assert conftest != CONFTEST
    pytester.makeconftest(conftest)
    pytester.makepyfile(test_case=(
        "import requests, pytest\n"
        f"URL = 'http://127.0.0.1:{port}/query'\n" + body
    ))


def _run(pytester):
    return pytester.runpytest_inprocess("-q", "-p", "no:cacheprovider")


def test_unmarked_test_is_blocked_and_fails(pytester, dummy_kernel,
                                            monkeypatch):
    port, hits = dummy_kernel
    monkeypatch.delenv("CEREBRUM_LIVE_KERNEL_TESTS", raising=False)
    _setup(pytester, port, (
        "def test_swallows():\n"
        "    try:\n"
        "        requests.post(URL, json={})\n"
        "    except Exception:\n"
        "        pass\n"
    ))
    result = _run(pytester)
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*tried to reach the AIOS kernel*"])
    assert hits == []


def test_marked_test_skips_without_opt_in(pytester, dummy_kernel,
                                          monkeypatch):
    port, hits = dummy_kernel
    monkeypatch.delenv("CEREBRUM_LIVE_KERNEL_TESTS", raising=False)
    _setup(pytester, port, (
        "@pytest.mark.live_kernel\n"
        "def test_live():\n"
        "    requests.post(URL, json={})\n"
    ))
    _run(pytester).assert_outcomes(skipped=1)
    assert hits == []


def test_marked_test_runs_with_opt_in(pytester, dummy_kernel, monkeypatch):
    port, hits = dummy_kernel
    monkeypatch.setenv("CEREBRUM_LIVE_KERNEL_TESTS", "1")
    _setup(pytester, port, (
        "@pytest.mark.live_kernel\n"
        "def test_live():\n"
        "    assert requests.post(URL, json={}).status_code == 200\n"
    ))
    _run(pytester).assert_outcomes(passed=1)
    assert hits == ["/query"]


def test_opt_in_alone_does_not_unblock_unmarked(pytester, dummy_kernel,
                                                monkeypatch):
    port, hits = dummy_kernel
    monkeypatch.setenv("CEREBRUM_LIVE_KERNEL_TESTS", "1")
    _setup(pytester, port, (
        "def test_unmarked():\n"
        "    requests.post(URL, json={})\n"
    ))
    _run(pytester).assert_outcomes(failed=1)
    assert hits == []


def test_online_marker_skips_without_opt_in(pytester, dummy_kernel,
                                            monkeypatch):
    port, _ = dummy_kernel
    monkeypatch.delenv("CEREBRUM_ONLINE_TESTS", raising=False)
    _setup(pytester, port, (
        "@pytest.mark.online\n"
        "def test_hub():\n"
        "    raise AssertionError('must not run')\n"
    ))
    _run(pytester).assert_outcomes(skipped=1)


def test_other_ports_are_not_blocked(pytester, dummy_kernel, monkeypatch):
    """Only the kernel's endpoints are blocked (Ollama, Azure, ... are
    not)."""
    port, hits = dummy_kernel
    monkeypatch.delenv("CEREBRUM_LIVE_KERNEL_TESTS", raising=False)
    pytester.makeconftest(CONFTEST)  # guards 8000, not the dummy port
    pytester.makepyfile(test_case=(
        "import requests\n"
        f"def test_other():\n"
        f"    requests.post('http://127.0.0.1:{port}/x', json={{}})\n"
    ))
    _run(pytester).assert_outcomes(passed=1)
    assert hits == ["/x"]


def test_experiment_metadata_does_not_ask_the_kernel():
    """Under the guard, results metadata built in a unit test records an
    empty config snapshot instead of reaching for a kernel."""
    from benchmarks.shared_memory.models import ExperimentMetadata

    meta = ExperimentMetadata(
        trials_per_condition=1, timestamp="t", kernel_url="u",
        conditions_run=[],
    )
    assert meta.config_snapshot == {}
