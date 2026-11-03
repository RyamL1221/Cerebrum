"""Replicated-logic conditions (AIOS docs/REPLICATED_LOGIC.md): the
agents' checks, run in a fresh interpreter, and the harness wiring."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import run_evaluation
from benchmarks.shared_memory.conditions import locus_of
from benchmarks.shared_memory.models import TrialResult

CHECKS = Path(__file__).with_name("_replicated_checks.py")
REPO = Path(__file__).resolve().parents[2]


def test_replicated_agent_checks_in_a_fresh_interpreter():
    """The agents import the kernel's aios package, which the aios/ stub
    other test modules import would shadow in this process."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(CHECKS), "-q",
         "-p", "no:cacheprovider", "-o", "python_files=_replicated_checks.py"],
        cwd=REPO, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-3000:]
    assert " passed" in result.stdout


@pytest.mark.parametrize("method", ["replicated_mem0", "replicated_inhouse"])
def test_preflight_refuses_replicated_with_kernel_memory_on(method):
    with patch.object(run_evaluation.requests, "get") as get:
        get.return_value.json.return_value = {
            "auto_inject": True, "auto_extract": True,
        }
        with pytest.raises(SystemExit, match=method):
            run_evaluation.check_kernel_mode("http://k", method)
        get.return_value.json.return_value = {
            "auto_inject": False, "auto_extract": False,
        }
        run_evaluation.check_kernel_mode("http://k", method)


def test_every_trial_records_its_locus():
    assert locus_of("kernel_shared") == "kernel"
    assert locus_of("mem0_default") == "kernel"
    assert locus_of("replicated_mem0") == "replicated"
    assert locus_of("native_inhouse") == "native"
    assert locus_of("naive_concat") == "none"
    failed = TrialResult(trial_index=0, condition="replicated_inhouse",
                         method="replicated_inhouse", failed=True)
    assert failed.locus == "replicated"
    assert TrialResult(trial_index=0, condition="kernel_private").locus == (
        "kernel"
    )
