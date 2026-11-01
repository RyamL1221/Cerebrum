"""Shared fixtures for the agent and benchmark tests."""
import pytest

from benchmarks.shared_memory.pipeline import AgentPipeline


@pytest.fixture(autouse=True)
def kernel_memory_config(monkeypatch):
    """Answer the harness's /memory/config read without a kernel."""
    monkeypatch.setattr(
        AgentPipeline,
        "_kernel_memory_config",
        staticmethod(lambda: {
            "relevance_threshold": 0.3,
            "max_injected_memories": 5,
            "max_memory_tokens": 1500,
        }),
    )
