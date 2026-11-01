"""Tests for the re-validation rule and the experiment metadata."""

from unittest.mock import patch

from benchmarks.shared_memory import models, revalidate
from benchmarks.shared_memory.models import ExperimentMetadata


def spread(center, width=1.0, n=150):
    """Return n scores evenly spread around center."""
    step = 2 * width / (n - 1)
    return [center - width + step * i for i in range(n)]


def cell(**fields):
    base = {"passed": True, "diff": 0.0}
    return {**base, **fields}


def test_identical_scores_pass():
    result = revalidate.compare_cell(spread(4.0), spread(4.0))
    assert result["in_ci"] and result["equivalent"] and result["passed"]
    assert result["diff"] == 0


def test_small_shift_outside_ci_passes_by_equivalence():
    result = revalidate.compare_cell(spread(4.15, 0.3), spread(4.0, 0.3))
    assert not result["in_ci"]
    assert result["equivalent"]
    assert result["passed"]


def test_large_shift_fails():
    result = revalidate.compare_cell(spread(4.6), spread(4.0))
    assert not result["passed"]
    assert result["welch_p"] < 0.05


def test_tost_is_symmetric():
    above = revalidate.tost_p(spread(4.1), spread(4.0))
    below = revalidate.tost_p(spread(3.9), spread(4.0))
    assert abs(above - below) < 1e-9


def test_constant_scores_do_not_crash():
    result = revalidate.compare_cell([5.0] * 150, [5.0] * 150)
    assert result["passed"]


def test_seven_of_nine_reproduces():
    cells = [cell() for _ in range(7)]
    cells += [cell(passed=False, diff=0.4) for _ in range(2)]
    assert revalidate.condition_verdict(cells)["reproduces"]


def test_six_of_nine_does_not_reproduce():
    cells = [cell() for _ in range(6)]
    cells += [cell(passed=False, diff=0.4) for _ in range(3)]
    assert not revalidate.condition_verdict(cells)["reproduces"]


def test_one_large_shift_vetoes():
    cells = [cell() for _ in range(8)]
    cells += [cell(passed=False, diff=-0.51)]
    assert not revalidate.condition_verdict(cells)["reproduces"]


def test_diagnostics_report_counts_cap_and_budget():
    diagnostics = {
        "scores_present": False,
        "after_visibility": 4,
        "injected_count": 2,
        "after_threshold": 12,
        "after_cap": 10,
        "after_budget": 8,
    }
    report = revalidate.diagnostics_report([
        {"injection_diagnostics": diagnostics,
         "retrieval_log": {"injection_status": "confirmed"}},
        {"injection_diagnostics": None, "failed": True},
    ])
    assert report["trials"] == 2
    assert report["failed"] == 1
    assert report["with_diagnostics"] == 1
    assert report["confirmed"] == 1
    assert report["cap_bound"] == 1
    assert report["budget_bound"] == 1
    assert report["after_budget"] == {8: 1}


def test_metadata_records_commits_and_config():
    with patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {"max_memory_tokens": 2000}
        metadata = ExperimentMetadata(
            trials_per_condition=1,
            timestamp="t",
            kernel_url="u",
            conditions_run=["c"],
        )
    assert len(metadata.git_commit.split("-")[0]) == 40
    assert metadata.config_snapshot == {"max_memory_tokens": 2000}
