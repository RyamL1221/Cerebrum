"""Benchmark v2's pre-flight (AIOS docs/BENCHMARK_V2.md, "Harness",
"Pre-flight", and Amendment 3): the kernel's memory settings a v2 run
needs, read from ``/memory/config``."""
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import run_evaluation


def kernel_config(auto_inject=True, auto_extract=False, **pipeline):
    """A ``/memory/config`` body that passes the v2 pre-flight for a
    kernel method, with ``pipeline`` changes."""
    settings = {"max_injected_memories": 10, "max_memory_tokens": 300,
                "relevance_threshold": 0.0, "block_format": "compact",
                "block_recency": True, "block_recency_unit": "session",
                "write_barrier": {"enabled": True, "timeout_ms": 60000}}
    settings.update(pipeline)
    return {"pipeline": settings, "auto_inject": auto_inject,
            "auto_extract": auto_extract, "pipeline_version": "v"}


def preflight(body, method="kernel_shared"):
    with patch.object(run_evaluation.requests, "get") as get:
        get.return_value.json.return_value = body
        return run_evaluation.check_v2_settings("http://kernel", method)


def test_a_kernel_v2_run_needs_injection_on_and_extraction_off():
    checked = preflight(kernel_config())
    assert (checked["auto_inject"], checked["auto_extract"]) == (True, False)
    with pytest.raises(SystemExit, match="auto_extract off"):
        preflight(kernel_config(auto_extract=True))
    with pytest.raises(SystemExit, match="auto_inject on"):
        preflight(kernel_config(auto_inject=False))


def test_the_v2_budget_is_300_tokens():
    assert run_evaluation.V2_SETTINGS["max_memory_tokens"] == 300
    with pytest.raises(SystemExit,
                       match="max_memory_tokens is 500, not 300"):
        preflight(kernel_config(max_memory_tokens=500))
    # An agent-managed method reads the same settings; the kernel's own
    # memory is off for it (check_kernel_mode checks that).
    native = kernel_config(auto_inject=False)
    assert preflight(native, "native_mem0")["pipeline"][
        "max_memory_tokens"] == 300
