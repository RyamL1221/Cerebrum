# Guards shared by every Cerebrum test (NeurIPS Subtask 10).
#
# Live-kernel isolation (AIOS docs/DEV_STATUS.md, known issue 25): no
# test may open a connection to the AIOS kernel (localhost:8000, and the
# configured ``kernel.base_url``) unless it is marked ``live_kernel`` and
# ``CEREBRUM_LIVE_KERNEL_TESTS=1`` is set. On 2026-11-05 the suite wrote
# to the kernel that was running the 9d re-baseline.
#
# The guard patches ``socket.socket.connect``, so it covers ``requests``,
# ``httpx`` and ``urllib``. A blocked connect raises
# ``ConnectionRefusedError`` (as if no kernel were listening) and is
# recorded; the test then fails with a clear message even when the code
# under test swallows the error, as the agents do.
#
# Tests that need the public agent hub are marked ``online`` and run only
# with ``CEREBRUM_ONLINE_TESTS=1``.
#
# Ported by hand from the guard on feature/self-improving-memory.

import os
import socket
import threading
from urllib.parse import urlparse

import pytest

# pytester runs the guard's own tests (tests/test_live_kernel_guard.py).
pytest_plugins = ["pytester"]

LIVE_KERNEL_ENV = "CEREBRUM_LIVE_KERNEL_TESTS"
ONLINE_ENV = "CEREBRUM_ONLINE_TESTS"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _kernel_endpoints():
    """The (host, port) pairs that count as the kernel."""
    endpoints = {(h, 8000) for h in _LOCAL_HOSTS}
    try:
        from cerebrum.config.config_manager import config

        url = urlparse(config.get_kernel_url() or "")
        if url.hostname:
            port = url.port or (443 if url.scheme == "https" else 80)
            hosts = (
                _LOCAL_HOSTS if url.hostname in _LOCAL_HOSTS
                else {url.hostname}
            )
            endpoints |= {(h, port) for h in hosts}
    except Exception:
        pass
    return endpoints


_KERNEL_ENDPOINTS = _kernel_endpoints()
_attempts = []
_attempts_lock = threading.Lock()
_allow_live = False
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _is_kernel(address):
    if not isinstance(address, tuple) or len(address) < 2:
        return False
    return (str(address[0]).lower(), address[1]) in _KERNEL_ENDPOINTS


def _blocked(address):
    with _attempts_lock:
        _attempts.append(address)
    return ConnectionRefusedError(
        f"live-kernel guard: connection to {address[0]}:{address[1]} "
        "blocked (mark the test live_kernel and set "
        f"{LIVE_KERNEL_ENV}=1 to allow it)"
    )


def _guarded_connect(self, address):
    if not _allow_live and _is_kernel(address):
        raise _blocked(address)
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if not _allow_live and _is_kernel(address):
        _blocked(address)
        return 61  # ECONNREFUSED
    return _real_connect_ex(self, address)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_kernel: sends requests to a running AIOS kernel; runs only "
        f"with {LIVE_KERNEL_ENV}=1",
    )
    config.addinivalue_line(
        "markers",
        "online: needs a public network service (agent hub); runs only "
        f"with {ONLINE_ENV}=1",
    )
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex


def pytest_unconfigure(config):
    socket.socket.connect = _real_connect
    socket.socket.connect_ex = _real_connect_ex


def pytest_collection_modifyitems(config, items):
    live_ok = os.environ.get(LIVE_KERNEL_ENV) == "1"
    online_ok = os.environ.get(ONLINE_ENV) == "1"
    for item in items:
        if "live_kernel" in item.keywords and not live_ok:
            item.add_marker(pytest.mark.skip(
                reason=f"live_kernel test; set {LIVE_KERNEL_ENV}=1"))
        if "online" in item.keywords and not online_ok:
            item.add_marker(pytest.mark.skip(
                reason=f"online test; set {ONLINE_ENV}=1"))


def _start(item):
    """Allow kernel traffic only for an opted-in live_kernel test."""
    global _allow_live
    _allow_live = (
        "live_kernel" in item.keywords
        and os.environ.get(LIVE_KERNEL_ENV) == "1"
    )
    with _attempts_lock:
        _attempts.clear()


def _fail_if_attempted(item, phase):
    with _attempts_lock:
        hits = list(_attempts)
        _attempts.clear()
    if hits:
        host, port = hits[0][0], hits[0][1]
        pytest.fail(
            f"{item.nodeid} tried to reach the AIOS kernel at "
            f"{host}:{port} during {phase} ({len(hits)} connection "
            "attempt(s)). Unit tests must not talk to a live kernel: mock "
            "the client, or mark the test @pytest.mark.live_kernel (it "
            f"then runs only with {LIVE_KERNEL_ENV}=1).",
            pytrace=False,
        )


# Each phase reports its own attempts, also when the phase raised, so a
# test that lets the blocked connect propagate fails with the guard's
# message rather than a bare ConnectionRefusedError.
@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    _start(item)
    try:
        return (yield)
    finally:
        _fail_if_attempted(item, "setup")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    try:
        return (yield)
    finally:
        _fail_if_attempted(item, "the test")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    global _allow_live
    try:
        return (yield)
    finally:
        _allow_live = False
        _fail_if_attempted(item, "teardown")


@pytest.fixture(autouse=True)
def _no_kernel_config_snapshot(request, monkeypatch):
    """``ExperimentMetadata`` records the live kernel's ``/memory/config``
    by default; outside live_kernel tests it records ``{}`` without
    asking."""
    if "live_kernel" in request.keywords:
        return
    try:
        from benchmarks.shared_memory import models
    except Exception:
        return
    monkeypatch.setattr(models, "_config_snapshot", lambda: {})
