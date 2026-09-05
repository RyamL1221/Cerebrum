"""Unit tests for the threshold-search config/verify primitives.

Covers the pure, kernel-free logic of
``benchmarks/shared_memory/threshold_search.py``:

- write_candidate_config performs a SURGICAL edit: it flips both gating
  toggles, sets the varied threshold's wildcard override, holds the other
  thresholds' defaults, clears stale overrides on the non-varied gates, and
  leaves unrelated lines/comments byte-for-byte intact.
- verify_gating_status raises GatingVerificationError (with expected-vs-actual
  detail) on toggle, default, and override mismatches, and returns the status
  dict on a full match. The ``status=`` injection avoids any live kernel call.

These need no running AIOS kernel. Run directly:
    python tests/agents/test_threshold_search_primitives.py
"""

import sys
sys.path.insert(0, ".")

import json
import tempfile
from pathlib import Path

from benchmarks.shared_memory.threshold_search import (
    CandidateConfig,
    ConfigEditError,
    GatingVerificationError,
    THRESHOLD_NAMES,
    verify_gating_status,
    write_candidate_config,
)


# A minimal but structurally faithful copy of the relevant config.yaml region,
# including the identical-looking default:/overrides: lines across the three
# thresholds (the case the surgical editor must disambiguate) and surrounding
# unrelated lines that must be preserved.
_SAMPLE_CONFIG = """\
memory:
  provider: "mem0"
  relevance_threshold: 0.3      # unrelated line — must be preserved

  adaptive_policy:
    enabled: true       # master switch; false = frozen baseline
    alpha: 1.0           # LinUCB exploration parameter

  static_thresholds:
    enabled: false       # master switch for this variant
    novelty_threshold:
      default: 0.7       # PLACEHOLDER
      overrides: []      # list of {llm_core, task_type, value}
    similarity_threshold:
      default: 0.7       # PLACEHOLDER
      overrides: []
    redundancy_threshold:
      default: 0.7       # PLACEHOLDER
      overrides: []

  mem0:
    user_id: "default"   # unrelated trailing line — must be preserved
"""


def _write_temp_config() -> Path:
    tmp = Path(tempfile.mkdtemp()) / "config.yaml"
    tmp.write_text(_SAMPLE_CONFIG, encoding="utf-8")
    return tmp


def test_write_candidate_flips_both_toggles():
    """static_thresholds.enabled→true and adaptive_policy.enabled→false."""
    cfg = _write_temp_config()
    write_candidate_config(
        cfg, model_name="qwen2.5:7b", threshold_name="novelty_threshold",
        value=0.6, other_thresholds_at={"similarity_threshold": 0.7, "redundancy_threshold": 0.7},
    )
    text = cfg.read_text()
    assert "enabled: true       # master switch for this variant" in text, (
        "static_thresholds.enabled should be flipped to true"
    )
    assert "enabled: false       # master switch; false = frozen baseline" in text, (
        "adaptive_policy.enabled should be flipped to false"
    )
    print("PASSED: both gating toggles flipped")


def test_write_candidate_sets_only_varied_override():
    """Varied threshold gets the wildcard override; others stay overrides: []."""
    cfg = _write_temp_config()
    write_candidate_config(
        cfg, model_name="gpt-4o", threshold_name="similarity_threshold",
        value=0.55, other_thresholds_at={},
    )
    text = cfg.read_text()
    # The varied threshold (similarity) must carry the wildcard override.
    assert 'overrides: [{llm_core: "gpt-4o", value: 0.55}]' in text, (
        f"similarity override not written surgically. Got:\n{text}"
    )
    # Exactly one override list should be non-empty (the varied one).
    non_empty = text.count('[{llm_core:')
    assert non_empty == 1, f"expected exactly 1 wildcard override, got {non_empty}"
    print("PASSED: only the varied threshold got a wildcard override")


def test_write_candidate_holds_and_preserves():
    """Non-varied defaults are held; unrelated lines preserved byte-for-byte."""
    cfg = _write_temp_config()
    write_candidate_config(
        cfg, model_name="llama3.1:8b", threshold_name="redundancy_threshold",
        value=0.8,
        other_thresholds_at={
            "novelty_threshold": 0.65,
            "similarity_threshold": 0.72,
            "redundancy_threshold": 0.7,
        },
    )
    text = cfg.read_text()
    # Held defaults on the two non-varied gates.
    assert "default: 0.65" in text, "novelty default should be held at 0.65"
    assert "default: 0.72" in text, "similarity default should be held at 0.72"
    # Unrelated lines preserved exactly.
    assert "relevance_threshold: 0.3      # unrelated line — must be preserved" in text
    assert 'user_id: "default"   # unrelated trailing line — must be preserved' in text
    # Inline comment on the varied default preserved.
    assert "# PLACEHOLDER" in text
    print("PASSED: non-varied defaults held and unrelated lines preserved")


def test_write_candidate_clears_stale_override_on_nonvaried():
    """A prior wildcard on a now-non-varied gate is reset to overrides: []."""
    cfg = _write_temp_config()
    # First candidate varies novelty.
    write_candidate_config(
        cfg, model_name="qwen2.5:7b", threshold_name="novelty_threshold",
        value=0.6, other_thresholds_at={},
    )
    # Second candidate varies similarity — novelty's override must be cleared.
    write_candidate_config(
        cfg, model_name="qwen2.5:7b", threshold_name="similarity_threshold",
        value=0.5, other_thresholds_at={},
    )
    text = cfg.read_text()
    assert text.count('[{llm_core:') == 1, "stale novelty override should be cleared"
    assert 'overrides: [{llm_core: "qwen2.5:7b", value: 0.5}]' in text
    print("PASSED: stale override on non-varied gate cleared")


def test_write_candidate_missing_block_raises():
    """A config without the expected block raises ConfigEditError, not silent."""
    tmp = Path(tempfile.mkdtemp()) / "config.yaml"
    tmp.write_text("memory:\n  provider: mem0\n", encoding="utf-8")
    try:
        write_candidate_config(
            tmp, model_name="m", threshold_name="novelty_threshold",
            value=0.6, other_thresholds_at={},
        )
    except ConfigEditError as e:
        assert "static_thresholds" in str(e)
        print("PASSED: missing block raises ConfigEditError")
        return
    raise AssertionError("expected ConfigEditError for a config missing the block")


def _good_status(novelty=0.6, model="qwen2.5:7b"):
    return {
        "adaptive_policy_enabled": False,
        "static_thresholds_enabled": True,
        "static_thresholds_config": {
            "enabled": True,
            "novelty_threshold": {
                "default": 0.7,
                "overrides": [{"llm_core": model, "value": novelty}],
            },
            "similarity_threshold": {"default": 0.7, "overrides": []},
            "redundancy_threshold": {"default": 0.7, "overrides": []},
        },
    }


def test_verify_passes_on_match():
    """A fully matching status returns the dict without raising."""
    out = verify_gating_status(
        expected_static_enabled=True,
        expected_adaptive_enabled=False,
        expected_thresholds={"novelty_threshold": 0.7, "similarity_threshold": 0.7},
        status=_good_status(),
        expected_override=("novelty_threshold", "qwen2.5:7b", 0.6),
    )
    assert out["static_thresholds_enabled"] is True
    print("PASSED: verify_gating_status passes on full match")


def test_verify_raises_on_toggle_mismatch():
    """Wrong adaptive toggle raises with expected-vs-actual detail."""
    bad = _good_status()
    bad["adaptive_policy_enabled"] = True
    try:
        verify_gating_status(
            expected_static_enabled=True, expected_adaptive_enabled=False,
            expected_thresholds={}, status=bad,
        )
    except GatingVerificationError as e:
        assert "adaptive_policy_enabled" in str(e)
        assert "expected False" in str(e) and "got True" in str(e)
        print("PASSED: toggle mismatch raises with detail")
        return
    raise AssertionError("expected GatingVerificationError on toggle mismatch")


def test_verify_raises_on_default_mismatch():
    """A held default that doesn't match raises."""
    try:
        verify_gating_status(
            expected_static_enabled=True, expected_adaptive_enabled=False,
            expected_thresholds={"novelty_threshold": 0.65},  # status has 0.7
            status=_good_status(),
        )
    except GatingVerificationError as e:
        assert "novelty_threshold.default" in str(e)
        assert "0.65" in str(e)
        print("PASSED: default mismatch raises with detail")
        return
    raise AssertionError("expected GatingVerificationError on default mismatch")


def test_verify_raises_on_override_mismatch():
    """A candidate override that didn't land raises."""
    try:
        verify_gating_status(
            expected_static_enabled=True, expected_adaptive_enabled=False,
            expected_thresholds={},
            status=_good_status(novelty=0.6),
            expected_override=("novelty_threshold", "qwen2.5:7b", 0.55),  # want 0.55, got 0.6
        )
    except GatingVerificationError as e:
        assert "novelty_threshold.overrides" in str(e)
        print("PASSED: override mismatch raises with detail")
        return
    raise AssertionError("expected GatingVerificationError on override mismatch")


def test_candidate_config_validation():
    """CandidateConfig rejects an unknown threshold name and empty model."""
    for bad in ("bogus_threshold", ""):
        try:
            CandidateConfig(model_name="m", threshold_name=bad, value=0.6)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for threshold_name={bad!r}")
    try:
        CandidateConfig(model_name="", threshold_name=THRESHOLD_NAMES[0], value=0.6)
    except ValueError:
        print("PASSED: CandidateConfig validates inputs")
        return
    raise AssertionError("expected ValueError for empty model_name")


# ---------------------------------------------------------------------------
# Candidate trial runner: score parsing + averaging (no kernel / no subprocess)
# ---------------------------------------------------------------------------

from benchmarks.shared_memory.threshold_search import (  # noqa: E402
    CandidateTrialResult,
    TrialRunError,
    aggregate_judge_scores,
    parse_candidate_results,
)


def _results_fixture(trials):
    """Wrap a list of trial dicts in the results_<method>.json structure."""
    return {
        "experiment_metadata": {"methods_run": ["kernel_shared_tuned"]},
        "conditions": [{"condition": "kernel_shared_tuned", "trials": trials}],
    }


def _trial(idx, p, t, i, failed=False):
    return {
        "trial_index": idx,
        "condition": "kernel_shared_tuned",
        "method": "kernel_shared_tuned",
        "profile_usage_score": p,
        "task_usage_score": t,
        "integration_score": i,
        "failed": failed,
    }


def test_aggregate_all_succeed():
    """All trials succeed: batch mean = mean of per-trial means."""
    data = _results_fixture([
        _trial(0, 5, 5, 5),   # per-trial reward 5.0
        _trial(1, 2, 3, 4),   # per-trial reward 3.0
    ])
    mean, rewards, completed, failed = aggregate_judge_scores(data)
    assert rewards == [5.0, 3.0], rewards
    assert completed == 2 and failed == 0
    assert abs(mean - 4.0) < 1e-9, mean
    print("PASSED: aggregate all-succeed → batch mean 4.0")


def test_aggregate_some_failed_excluded():
    """failed:true trials are excluded from the mean but counted."""
    data = _results_fixture([
        _trial(0, 4, 4, 4),                  # reward 4.0
        _trial(1, None, None, None, failed=True),  # failed → excluded
        _trial(2, 2, 2, 2),                  # reward 2.0
    ])
    mean, rewards, completed, failed = aggregate_judge_scores(data)
    assert rewards == [4.0, 2.0], rewards
    assert completed == 2 and failed == 1
    assert abs(mean - 3.0) < 1e-9, mean
    print("PASSED: aggregate some-failed excludes failed, mean over survivors")


def test_aggregate_null_scores_not_zero():
    """A non-failed trial with all-null scores is excluded, NOT counted as 0."""
    data = _results_fixture([
        _trial(0, 4, 4, 4),                        # reward 4.0
        _trial(1, None, None, None, failed=False), # all-null, not failed → excluded
    ])
    mean, rewards, completed, failed = aggregate_judge_scores(data)
    assert rewards == [4.0], rewards
    assert completed == 1 and failed == 1
    assert abs(mean - 4.0) < 1e-9, (
        "null scores must be excluded, not folded in as 0.0"
    )
    print("PASSED: all-null non-failed trial excluded (not 0.0)")


def test_aggregate_partial_null_averages_present():
    """A trial with some null scores averages only its non-null dimensions."""
    data = _results_fixture([
        # profile=4, task=None, integration=2 → reward mean(4,2)=3.0
        _trial(0, 4, None, 2),
    ])
    mean, rewards, completed, failed = aggregate_judge_scores(data)
    assert rewards == [3.0], rewards
    assert completed == 1 and failed == 0
    print("PASSED: partial-null trial averages only present dimensions")


def test_aggregate_all_failed_returns_none():
    """When every trial fails, batch mean is None (no signal), never 0.0."""
    data = _results_fixture([
        _trial(0, None, None, None, failed=True),
        _trial(1, None, None, None, failed=True),
    ])
    mean, rewards, completed, failed = aggregate_judge_scores(data)
    assert mean is None, "all-failed batch must yield None, not 0.0"
    assert rewards == [] and completed == 0 and failed == 2
    print("PASSED: all-failed batch → batch_mean None")


def test_parse_candidate_results_builds_struct(tmp_path=None):
    """parse_candidate_results loads a fixture file into CandidateTrialResult."""
    tmp = Path(tempfile.mkdtemp())
    jpath = tmp / "results_kernel_shared_tuned.json"
    jpath.write_text(json.dumps(_results_fixture([
        _trial(0, 5, 5, 5),
        _trial(1, 3, 3, 3),
        _trial(2, None, None, None, failed=True),
    ])), encoding="utf-8")

    res = parse_candidate_results(
        results_json_path=jpath,
        model_name="qwen2.5:7b",
        threshold_name="novelty_threshold",
        value=0.6,
        num_trials_requested=3,
        output_dir=tmp,
    )
    assert isinstance(res, CandidateTrialResult)
    assert res.model_name == "qwen2.5:7b"
    assert res.threshold_name == "novelty_threshold"
    assert res.value == 0.6
    assert res.num_trials_requested == 3
    assert res.num_trials_completed == 2
    assert res.num_trials_failed == 1
    assert abs(res.batch_mean_score - 4.0) < 1e-9
    assert res.results_json_path.endswith("results_kernel_shared_tuned.json")
    assert Path(res.results_json_path).is_absolute()
    print("PASSED: parse_candidate_results builds structured result")


def test_parse_candidate_results_missing_file_raises():
    """A missing results file raises TrialRunError, not a bare crash."""
    missing = Path(tempfile.mkdtemp()) / "nope.json"
    try:
        parse_candidate_results(
            results_json_path=missing,
            model_name="m", threshold_name="novelty_threshold",
            value=0.6, num_trials_requested=2,
        )
    except TrialRunError as e:
        assert "did not produce" in str(e)
        print("PASSED: missing results file raises TrialRunError")
        return
    raise AssertionError("expected TrialRunError for missing results file")


if __name__ == "__main__":
    test_write_candidate_flips_both_toggles()
    test_write_candidate_sets_only_varied_override()
    test_write_candidate_holds_and_preserves()
    test_write_candidate_clears_stale_override_on_nonvaried()
    test_write_candidate_missing_block_raises()
    test_verify_passes_on_match()
    test_verify_raises_on_toggle_mismatch()
    test_verify_raises_on_default_mismatch()
    test_verify_raises_on_override_mismatch()
    test_candidate_config_validation()
    test_aggregate_all_succeed()
    test_aggregate_some_failed_excluded()
    test_aggregate_null_scores_not_zero()
    test_aggregate_partial_null_averages_present()
    test_aggregate_all_failed_returns_none()
    test_parse_candidate_results_builds_struct()
    test_parse_candidate_results_missing_file_raises()
    print("\nAll threshold-search primitive tests passed.")
