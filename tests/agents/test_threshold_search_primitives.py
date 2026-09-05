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


# ---------------------------------------------------------------------------
# Coordinate search loop: control flow with mocked apply/run (no live kernel)
# ---------------------------------------------------------------------------

from benchmarks.shared_memory.threshold_search import (  # noqa: E402
    CandidateAttempt,
    CoordinateSearchState,
    DEFAULT_CANDIDATE_GRID,
    THRESHOLD_NAMES,
    search_one_threshold,
    search_one_model,
    run_full_search,
    select_winner,
    write_final_overrides,
)


def _attempt(threshold, value, score):
    return CandidateAttempt(
        threshold_name=threshold, value=value, batch_mean_score=score,
        num_trials_completed=(0 if score is None else 8),
        num_trials_failed=(8 if score is None else 0),
    )


def test_select_winner_highest_wins():
    attempts = [
        _attempt("novelty_threshold", 0.5, 2.0),
        _attempt("novelty_threshold", 0.6, 4.5),
        _attempt("novelty_threshold", 0.7, 3.0),
    ]
    value, score = select_winner(attempts)
    assert value == 0.6 and score == 4.5, (value, score)
    print("PASSED: select_winner picks highest score")


def test_select_winner_tie_breaks_to_first():
    """On a tie, the earliest-in-grid (lowest) candidate wins."""
    attempts = [
        _attempt("novelty_threshold", 0.5, 4.0),
        _attempt("novelty_threshold", 0.6, 4.0),   # tie — must NOT displace 0.5
        _attempt("novelty_threshold", 0.7, 4.0),
    ]
    value, score = select_winner(attempts)
    assert value == 0.5 and score == 4.0, (value, score)
    print("PASSED: select_winner tie-breaks to first/lowest")


def test_select_winner_none_treated_as_worst():
    """A None (all-failed) candidate never wins when a scored one exists."""
    attempts = [
        _attempt("novelty_threshold", 0.5, None),
        _attempt("novelty_threshold", 0.6, 1.0),
        _attempt("novelty_threshold", 0.7, None),
    ]
    value, score = select_winner(attempts)
    assert value == 0.6 and score == 1.0, (value, score)
    print("PASSED: select_winner treats None as worst")


def test_select_winner_all_none_degenerate():
    """Every candidate None → first candidate returned, score None (flagged)."""
    attempts = [
        _attempt("novelty_threshold", 0.5, None),
        _attempt("novelty_threshold", 0.6, None),
    ]
    value, score = select_winner(attempts)
    assert value == 0.5 and score is None, (value, score)
    print("PASSED: select_winner all-None degenerate falls back to first, score None")


class _FakeProc:
    """Stand-in for a kernel Popen handle; records terminate() calls."""
    def __init__(self):
        self.terminated = False
    def terminate(self):
        self.terminated = True
    def wait(self, timeout=None):
        return 0


def _make_mocks(score_map):
    """Build (apply_fn, run_fn, log) mocks.

    score_map maps (model, threshold, value) → batch_mean_score. apply_fn
    records the CandidateConfig it was called with and returns a _FakeProc;
    run_fn records its call and returns a CandidateTrialResult with the mapped
    score. The shared ``log`` list captures the exact call order for assertions.
    """
    log = []
    procs = []

    def apply_fn(candidate, config_path, aios_repo_dir, kernel_url="http://localhost:8000"):
        log.append(("apply", candidate.model_name, candidate.threshold_name,
                    candidate.value, dict(candidate.other_thresholds_at)))
        p = _FakeProc()
        procs.append(p)
        return p

    def run_fn(model_name, model_backend, threshold_name, value, num_trials,
               output_dir, run_id, kernel_url="http://localhost:8000",
               judge_model="x", **kw):
        score = score_map.get((model_name, threshold_name, value))
        log.append(("run", model_name, threshold_name, value, num_trials))
        completed = 0 if score is None else num_trials
        failed = num_trials if score is None else 0
        return CandidateTrialResult(
            model_name=model_name, threshold_name=threshold_name, value=value,
            num_trials_requested=num_trials, num_trials_completed=completed,
            num_trials_failed=failed, batch_mean_score=score,
            per_trial_rewards=[], results_json_path=str(Path(output_dir) / "r.json"),
            results_csv_path=None, output_dir=str(output_dir),
        )

    return apply_fn, run_fn, log, procs


def test_search_one_threshold_order_and_terminate():
    """Candidates tried in grid order; each candidate's proc is terminated."""
    scores = {("m", "novelty_threshold", v): v for v in DEFAULT_CANDIDATE_GRID}
    apply_fn, run_fn, log, procs = _make_mocks(scores)
    tmp = Path(tempfile.mkdtemp())
    winner, attempts = search_one_threshold(
        model_name="m", model_backend="ollama",
        threshold_name="novelty_threshold",
        other_thresholds_at={t: 0.7 for t in THRESHOLD_NAMES},
        config_path=tmp / "config.yaml", aios_repo_dir=tmp, output_root=tmp,
        apply_fn=apply_fn, run_fn=run_fn,
    )
    tried = [entry[3] for entry in log if entry[0] == "run"]
    assert tried == list(DEFAULT_CANDIDATE_GRID), tried
    assert winner == 0.9, winner  # highest score in this synthetic map
    assert all(p.terminated for p in procs), "every candidate proc terminated"
    assert len(attempts) == 5
    print("PASSED: search_one_threshold tries grid in order and cleans up procs")


def test_search_one_model_threads_winners():
    """Each step holds prior winners; not-yet-searched gates at baseline."""
    # Rig winners: novelty→0.6, similarity→0.8, redundancy→0.5.
    scores = {}
    for v in DEFAULT_CANDIDATE_GRID:
        scores[("m", "novelty_threshold", v)] = 10 if v == 0.6 else 1
        scores[("m", "similarity_threshold", v)] = 10 if v == 0.8 else 1
        scores[("m", "redundancy_threshold", v)] = 10 if v == 0.5 else 1
    apply_fn, run_fn, log, _ = _make_mocks(scores)
    tmp = Path(tempfile.mkdtemp())
    state = search_one_model(
        model_name="m", model_backend="ollama",
        config_path=tmp / "config.yaml", aios_repo_dir=tmp, output_root=tmp,
        apply_fn=apply_fn, run_fn=run_fn,
    )
    assert state.winners == {
        "novelty_threshold": 0.6, "similarity_threshold": 0.8, "redundancy_threshold": 0.5,
    }, state.winners
    assert state.completed and state.current_threshold is None

    # Inspect the held-defaults threaded into each step via apply calls.
    applies = [e for e in log if e[0] == "apply"]
    # similarity step (2nd group of 5) must hold novelty at its winner 0.6.
    sim_apply = next(e for e in applies if e[2] == "similarity_threshold")
    assert sim_apply[4]["novelty_threshold"] == 0.6, sim_apply[4]
    assert sim_apply[4]["redundancy_threshold"] == 0.7, "redundancy still baseline"
    # redundancy step must hold BOTH prior winners.
    red_apply = next(e for e in applies if e[2] == "redundancy_threshold")
    assert red_apply[4]["novelty_threshold"] == 0.6
    assert red_apply[4]["similarity_threshold"] == 0.8
    # 3 thresholds × 5 candidates = 15 runs.
    assert sum(1 for e in log if e[0] == "run") == 15
    print("PASSED: search_one_model threads winners forward correctly")


def test_run_full_search_independent_models_single_final_write():
    """Models independent; final config write happens exactly once, at the end."""
    grid = (0.5, 0.6)
    # Different winners per model to prove independence (no cross-leakage).
    scores = {}
    winners_target = {
        "A": {"novelty_threshold": 0.5, "similarity_threshold": 0.6, "redundancy_threshold": 0.5},
        "B": {"novelty_threshold": 0.6, "similarity_threshold": 0.5, "redundancy_threshold": 0.6},
    }
    for model, wmap in winners_target.items():
        for t in THRESHOLD_NAMES:
            for v in grid:
                scores[(model, t, v)] = 10 if v == wmap[t] else 1
    apply_fn, run_fn, log, _ = _make_mocks(scores)

    # Track final-write calls without touching a real config file.
    writes = []
    import benchmarks.shared_memory.threshold_search as ts

    orig_write = ts.write_final_overrides
    ts.write_final_overrides = lambda cfg, winners: writes.append(dict(winners))
    try:
        tmp = Path(tempfile.mkdtemp())
        states = run_full_search(
            config_path=tmp / "config.yaml", aios_repo_dir=tmp, output_root=tmp,
            search_run_id="ffs_test", progress_root=tmp / "progress", resume=False,
            models=("A", "B"),
            model_backends={"A": "ollama", "B": "ollama"},
            candidates=grid, trials_per_candidate=2,
            apply_fn=apply_fn, run_fn=run_fn, write_final=True,
        )
    finally:
        ts.write_final_overrides = orig_write

    assert states["A"].winners == winners_target["A"], states["A"].winners
    assert states["B"].winners == winners_target["B"], states["B"].winners
    # Exactly ONE final write, after both models, carrying both models' winners.
    assert len(writes) == 1, f"expected exactly one final write, got {len(writes)}"
    assert writes[0] == winners_target, writes[0]
    print("PASSED: run_full_search — independent models, single final write")


def test_run_full_search_no_write_when_disabled():
    """write_final=False performs no config write."""
    grid = (0.5, 0.6)
    scores = {("A", t, v): (10 if v == 0.5 else 1) for t in THRESHOLD_NAMES for v in grid}
    apply_fn, run_fn, _, _ = _make_mocks(scores)
    import benchmarks.shared_memory.threshold_search as ts
    writes = []
    orig = ts.write_final_overrides
    ts.write_final_overrides = lambda cfg, winners: writes.append(1)
    try:
        tmp = Path(tempfile.mkdtemp())
        run_full_search(
            config_path=tmp / "config.yaml", aios_repo_dir=tmp, output_root=tmp,
            search_run_id="ffs_nowrite", progress_root=tmp / "progress", resume=False,
            models=("A",), model_backends={"A": "ollama"},
            candidates=grid, trials_per_candidate=2,
            apply_fn=apply_fn, run_fn=run_fn, write_final=False,
        )
    finally:
        ts.write_final_overrides = orig
    assert writes == [], "no write should occur when write_final=False"
    print("PASSED: run_full_search honors write_final=False")


def test_write_final_overrides_multi_model():
    """Final write emits one wildcard per model per threshold, toggles set."""
    cfg = _write_temp_config()
    write_final_overrides(cfg, {
        "qwen2.5:7b": {"novelty_threshold": 0.6, "similarity_threshold": 0.7, "redundancy_threshold": 0.8},
        "gpt-4o": {"novelty_threshold": 0.5, "similarity_threshold": 0.9, "redundancy_threshold": 0.5},
    })
    text = cfg.read_text()
    assert "enabled: true       # master switch for this variant" in text
    assert "enabled: false       # master switch; false = frozen baseline" in text
    # novelty must carry both models' wildcard entries.
    assert '{llm_core: "qwen2.5:7b", value: 0.6}' in text
    assert '{llm_core: "gpt-4o", value: 0.5}' in text
    print("PASSED: write_final_overrides writes multi-model wildcard overrides")


# ---------------------------------------------------------------------------
# Resumability + crash-safe progress logging (no live kernel)
# ---------------------------------------------------------------------------

from benchmarks.shared_memory.threshold_search import (  # noqa: E402
    ProgressLog,
    load_progress,
    _read_jsonl_tolerant,
)


def _seed_attempts_jsonl(progress_root, run_id, records):
    """Write an attempts.jsonl fixture representing a partial run."""
    d = Path(progress_root) / run_id
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "attempts.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return d


def _rec(model, threshold, value, score, backend="ollama"):
    return {
        "model_name": model, "model_backend": backend,
        "threshold_name": threshold, "value": value,
        "batch_mean_score": score, "num_trials_completed": (0 if score is None else 8),
        "num_trials_failed": (8 if score is None else 0),
        "results_json_path": f"/tmp/{model}_{threshold}_{value}.json", "ts": 1.0,
    }


def test_progresslog_append_is_durable_and_readable():
    """append_attempt writes a parseable JSONL line per candidate."""
    tmp = Path(tempfile.mkdtemp())
    log = ProgressLog("run1", progress_root=tmp)
    log.append_attempt("m", "ollama", _attempt("novelty_threshold", 0.5, 3.0))
    log.append_attempt("m", "ollama", _attempt("novelty_threshold", 0.6, 4.0))
    recs = _read_jsonl_tolerant(log.attempts_path)
    assert len(recs) == 2 and recs[1]["value"] == 0.6
    print("PASSED: ProgressLog append is durable and readable")


def test_read_jsonl_tolerates_torn_final_line():
    """A hard-kill mid-write torn final line is dropped; prior lines survive."""
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "attempts.jsonl"
    good = json.dumps(_rec("m", "novelty_threshold", 0.5, 3.0))
    # Simulate a crash mid-write: valid line + newline, then a partial line.
    p.write_text(good + "\n" + '{"model_name": "m", "threshold_name": "nov', encoding="utf-8")
    recs = _read_jsonl_tolerant(p)
    assert len(recs) == 1 and recs[0]["value"] == 0.5, recs
    print("PASSED: torn final line tolerated, prior record recovered")


def test_summary_write_is_atomic_temp_then_replace():
    """write_summary leaves a complete summary.json and no leftover temp."""
    tmp = Path(tempfile.mkdtemp())
    log = ProgressLog("run2", progress_root=tmp)
    st = CoordinateSearchState(model_name="m", model_backend="ollama")
    st.winners = {"novelty_threshold": 0.6}
    log.write_summary({"m": st})
    assert log.summary_path.exists()
    assert not log.summary_path.with_suffix(".json.tmp").exists(), "temp cleaned up"
    data = json.loads(log.summary_path.read_text())
    assert data["models"]["m"]["winners"] == {"novelty_threshold": 0.6}
    print("PASSED: summary write is atomic (temp then replace)")


def test_load_progress_reconstructs_done_inprogress_pending():
    """load_progress: full grid → winner fixed; partial grid → in-progress."""
    tmp = Path(tempfile.mkdtemp())
    grid = (0.5, 0.6, 0.7, 0.8, 0.9)
    records = []
    # novelty fully attempted → winner should be the top score (0.7 here).
    for v in grid:
        records.append(_rec("m", "novelty_threshold", v, 5.0 if v == 0.7 else 1.0))
    # similarity: only 3/5 attempted → in-progress, no winner yet.
    for v in (0.5, 0.6, 0.7):
        records.append(_rec("m", "similarity_threshold", v, 2.0))
    _seed_attempts_jsonl(tmp, "runX", records)

    states = load_progress("runX", progress_root=tmp, candidates=grid)
    st = states["m"]
    assert st.winners.get("novelty_threshold") == 0.7, st.winners
    assert "similarity_threshold" not in st.winners, "similarity not done yet"
    assert st.current_threshold == "similarity_threshold", st.current_threshold
    assert not st.completed
    print("PASSED: load_progress reconstructs done/in-progress/pending")


def test_load_progress_partitions_by_model():
    """Two models interleaved in ONE attempts.jsonl are reconstructed
    independently — no cross-model leakage of attempts or winners."""
    tmp = Path(tempfile.mkdtemp())
    grid = (0.5, 0.6, 0.7, 0.8, 0.9)
    records = []
    # Interleave A and B records for the same threshold, different winners.
    for v in grid:
        records.append(_rec("A", "novelty_threshold", v, 5.0 if v == 0.5 else 1.0))
        records.append(_rec("B", "novelty_threshold", v, 5.0 if v == 0.9 else 1.0))
    _seed_attempts_jsonl(tmp, "partition", records)

    states = load_progress("partition", progress_root=tmp, candidates=grid)
    assert set(states.keys()) == {"A", "B"}
    # Each model only has its own 5 attempts, not the interleaved 10.
    assert len(states["A"].history) == 5, len(states["A"].history)
    assert len(states["B"].history) == 5, len(states["B"].history)
    assert all(a.threshold_name == "novelty_threshold" for a in states["A"].history)
    # Winners computed per model, independently.
    assert states["A"].winners["novelty_threshold"] == 0.5, states["A"].winners
    assert states["B"].winners["novelty_threshold"] == 0.9, states["B"].winners
    print("PASSED: load_progress partitions attempts by model (no leakage)")


def test_run_full_search_resume_skips_done_model_and_attempted_candidates():
    """The headline resume test.

    Fixture: model 'A' fully done (all 3 thresholds), model 'B' mid-way through
    similarity_threshold with 3/5 candidates attempted (novelty already done).
    run_full_search(resume=True) must:
      - skip model A entirely (0 runs for A),
      - skip B's already-done novelty step (0 runs),
      - skip B's 3 already-attempted similarity candidates,
      - run ONLY the 2 remaining similarity candidates + all 5 redundancy.
    """
    tmp = Path(tempfile.mkdtemp())
    grid = (0.5, 0.6, 0.7, 0.8, 0.9)
    records = []
    # Model A: fully complete (all three thresholds, full grid each).
    for t in THRESHOLD_NAMES:
        for v in grid:
            records.append(_rec("A", t, v, 5.0 if v == 0.5 else 1.0))
    # Model B: novelty done (full grid), similarity 3/5 attempted.
    for v in grid:
        records.append(_rec("B", "novelty_threshold", v, 5.0 if v == 0.6 else 1.0))
    for v in (0.5, 0.6, 0.7):
        records.append(_rec("B", "similarity_threshold", v, 2.0))
    _seed_attempts_jsonl(tmp, "resumeRun", records)

    # Mock scoring for anything actually run now. Make B's remaining similarity
    # candidate 0.8 the top so we can assert threading, and redundancy 0.9 top.
    scores = {}
    for v in grid:
        scores[("B", "similarity_threshold", v)] = 9.0 if v == 0.8 else 3.0
        scores[("B", "redundancy_threshold", v)] = 9.0 if v == 0.9 else 3.0
    apply_fn, run_fn, log, _ = _make_mocks(scores)

    import benchmarks.shared_memory.threshold_search as ts
    writes = []
    orig = ts.write_final_overrides
    ts.write_final_overrides = lambda cfg, winners: writes.append(dict(winners))
    try:
        states = run_full_search(
            config_path=tmp / "config.yaml", aios_repo_dir=tmp, output_root=tmp,
            search_run_id="resumeRun", progress_root=tmp,
            models=("A", "B"), model_backends={"A": "ollama", "B": "ollama"},
            candidates=grid, trials_per_candidate=8,
            apply_fn=apply_fn, run_fn=run_fn, resume=True, write_final=True,
        )
    finally:
        ts.write_final_overrides = orig

    runs = [e for e in log if e[0] == "run"]
    # Model A: zero runs (fully complete, skipped).
    assert all(e[1] != "A" for e in runs), "model A must not be re-run"
    # Model B similarity: only the 2 unattempted candidates (0.8, 0.9) run.
    b_sim = sorted(e[3] for e in runs if e[1] == "B" and e[2] == "similarity_threshold")
    assert b_sim == [0.8, 0.9], f"expected only 0.8,0.9 rerun for B similarity, got {b_sim}"
    # Model B novelty: zero runs (already done).
    assert not any(e[2] == "novelty_threshold" for e in runs if e[1] == "B"), (
        "B novelty already done — must not be re-run"
    )
    # Model B redundancy: full grid run (was pending).
    b_red = sorted(e[3] for e in runs if e[1] == "B" and e[2] == "redundancy_threshold")
    assert b_red == list(grid), f"B redundancy should run full grid, got {b_red}"

    # Winners: A recovered; B novelty recovered (0.6), similarity winner from
    # combining the 3 persisted (all 2.0) with the 2 new (0.8→9.0) → 0.8.
    assert states["A"].completed and states["A"].winners["novelty_threshold"] == 0.5
    assert states["B"].winners["novelty_threshold"] == 0.6
    assert states["B"].winners["similarity_threshold"] == 0.8
    assert states["B"].winners["redundancy_threshold"] == 0.9
    # Single final write, after both models.
    assert len(writes) == 1, f"expected one final write, got {len(writes)}"
    print("PASSED: resume skips done model + attempted candidates, runs only remaining")


def test_run_full_search_resume_no_prior_is_fresh():
    """resume=True with no prior log behaves like a fresh run."""
    tmp = Path(tempfile.mkdtemp())
    grid = (0.5, 0.6)
    scores = {("A", t, v): (9.0 if v == 0.5 else 1.0) for t in THRESHOLD_NAMES for v in grid}
    apply_fn, run_fn, log, _ = _make_mocks(scores)
    import benchmarks.shared_memory.threshold_search as ts
    orig = ts.write_final_overrides
    ts.write_final_overrides = lambda cfg, winners: None
    try:
        states = run_full_search(
            config_path=tmp / "config.yaml", aios_repo_dir=tmp, output_root=tmp,
            search_run_id="freshRun", progress_root=tmp,
            models=("A",), model_backends={"A": "ollama"},
            candidates=grid, trials_per_candidate=2,
            apply_fn=apply_fn, run_fn=run_fn, resume=True, write_final=True,
        )
    finally:
        ts.write_final_overrides = orig
    runs = [e for e in log if e[0] == "run"]
    assert len(runs) == 3 * len(grid), f"fresh run should run full grid, got {len(runs)}"
    assert states["A"].completed
    print("PASSED: resume=True with no prior log is a fresh run")


def test_incremental_logging_per_candidate():
    """Progress is appended per-candidate, not just per-threshold/model."""
    tmp = Path(tempfile.mkdtemp())
    grid = (0.5, 0.6, 0.7)
    scores = {("A", t, v): v for t in THRESHOLD_NAMES for v in grid}
    apply_fn, run_fn, _, _ = _make_mocks(scores)
    import benchmarks.shared_memory.threshold_search as ts
    orig = ts.write_final_overrides
    ts.write_final_overrides = lambda cfg, winners: None
    try:
        run_full_search(
            config_path=tmp / "config.yaml", aios_repo_dir=tmp, output_root=tmp,
            search_run_id="incRun", progress_root=tmp,
            models=("A",), model_backends={"A": "ollama"},
            candidates=grid, trials_per_candidate=2,
            apply_fn=apply_fn, run_fn=run_fn, resume=False, write_final=True,
        )
    finally:
        ts.write_final_overrides = orig
    recs = _read_jsonl_tolerant(tmp / "incRun" / "attempts.jsonl")
    # 3 thresholds × 3 candidates = 9 per-candidate records.
    assert len(recs) == 9, f"expected 9 incremental records, got {len(recs)}"
    print("PASSED: incremental per-candidate logging")


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
    test_select_winner_highest_wins()
    test_select_winner_tie_breaks_to_first()
    test_select_winner_none_treated_as_worst()
    test_select_winner_all_none_degenerate()
    test_search_one_threshold_order_and_terminate()
    test_search_one_model_threads_winners()
    test_run_full_search_independent_models_single_final_write()
    test_run_full_search_no_write_when_disabled()
    test_write_final_overrides_multi_model()
    test_progresslog_append_is_durable_and_readable()
    test_read_jsonl_tolerates_torn_final_line()
    test_summary_write_is_atomic_temp_then_replace()
    test_load_progress_reconstructs_done_inprogress_pending()
    test_load_progress_partitions_by_model()
    test_run_full_search_resume_skips_done_model_and_attempted_candidates()
    test_run_full_search_resume_no_prior_is_fresh()
    test_incremental_logging_per_candidate()
    print("\nAll threshold-search primitive tests passed.")
