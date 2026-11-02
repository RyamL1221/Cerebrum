"""Tests for the per-trial comparison of two judgings."""

import pytest

from benchmarks.shared_memory.judge_compare import compare, paired


def trial(index, score, failed=False):
    return {"trial_index": index, "s": score, "failed": failed}


def test_pairs_by_trial_index_and_skips_failures():
    old = [trial(0, 1), trial(1, 2), trial(2, 3, failed=True)]
    new = [trial(1, 4), trial(0, 5), trial(2, 1)]
    assert paired(old, new, "s") == [(1, 5), (2, 4)]


def test_identical_scores():
    result = compare([(1, 1), (3, 3), (5, 5)])
    assert result["diff"] == 0
    assert result["rho"] == pytest.approx(1.0)
    assert result["changed_over_1"] == 0
    assert result["exact_agreement"] == 1


def test_changes_over_one_point_and_mean_shift():
    result = compare([(1, 3), (2, 3), (5, 5), (4, 3)])
    assert result["changed_over_1"] == 0.25
    assert result["diff"] == pytest.approx(0.5)


def test_rho_is_none_for_a_constant_side():
    assert compare([(5, 5), (5, 4)])["rho"] is None
