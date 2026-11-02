"""The harness checks the kernel's memory provider and records the
retrieval threshold it used."""

from unittest.mock import patch

import pytest

from benchmarks.shared_memory import run_evaluation
from benchmarks.shared_memory.pipeline import AgentPipeline


def kernel_config(provider):
    response = patch.object(run_evaluation.requests, "get").start()
    response.return_value.json.return_value = {"provider": provider}
    return response


@pytest.fixture(autouse=True)
def stop_patches():
    yield
    patch.stopall()


def test_matching_provider_passes():
    get = kernel_config("in-house")
    run_evaluation.check_kernel_provider("http://k", "in-house")
    assert get.call_args.args[0] == "http://k/memory/config"


def test_other_provider_stops_the_run():
    kernel_config("mem0")
    with pytest.raises(SystemExit, match="'mem0'"):
        run_evaluation.check_kernel_provider("http://k", "in-house")


def test_cli_takes_provider():
    args = run_evaluation.build_arg_parser().parse_args(
        ["--provider", "in-house"]
    )
    assert args.provider == "in-house"


def test_threshold_used_is_recorded():
    diagnostics = AgentPipeline(share_memory=True)._extract_injection_diagnostics(
        {"injection_diagnostics": {
            "injected_count": 0, "scores_present": True,
            "threshold_used": 0.0,
        }}
    )
    assert diagnostics.threshold_used == 0.0
    assert diagnostics.scores_present is True
