"""Permanent tests for the v2 decomposed judge path.

Consolidates the ad hoc verification used while building the v2 judge
(subtasks 3-6) into a discoverable, CI-runnable suite. Covers:

- ``_clamp_score`` bounds for v1 ([1,5]) and v2 (min_value=0 → [0,5]),
  including non-integer fallback for both.
- ``LLMJudge.evaluate`` under rubric_version="v2": criteria summing, the
  recomputed-sum-wins rule when the reported score disagrees, malformed
  dimension → None for that dimension only, and correct rubric_version on the
  happy path and EVERY failure path (fallback-None, non-JSON, non-dict,
  outer-except).
- ``criteria_breakdown``: populated for v2, None for v1 on every path, and
  preserved through TrialResult JSON round-trip.
- ``HybridJudge`` v2-awareness: keyword_score floor (v1=1, v2=0), the _avg
  clamp difference, and None LLM sub-score → keyword-only fallback for both.

v1 behavior is pinned against FIXED expected values (the actual v1 contract),
NOT against a git ref — so this stays meaningful as a long-term regression test.

No running AIOS kernel needed (the LLM call is mocked). Run directly:
    python tests/agents/test_judge_v2.py
"""

import sys
sys.path.insert(0, ".")

import json
from unittest.mock import patch

from benchmarks.shared_memory.judge import (
    LLMJudge,
    HybridJudge,
    _clamp_score,
    keyword_score,
)
from benchmarks.shared_memory.models import (
    JudgeScores,
    TrialResult,
    SyntheticProfile,
    SyntheticTaskContext,
)

_JUDGE_MOD = "benchmarks.shared_memory.judge"

PROFILE = SyntheticProfile(
    user_name="Ada Lovelace",
    preferred_tools=["pytest", "ruff"],
    preferred_language="Python",
    response_style="concise",
)
TASK = SyntheticTaskContext(
    current_project="Cerebrum SDK",
    active_experiment="v2 judge experiment",
    goals=["ship the v2 rubric"],
    blockers=["parsing gap"],
    next_steps=["land subtask eight"],
)


def _run_evaluate(judge, response_message, token_usage=None, response_text="r"):
    """Call judge.evaluate() with a mocked kernel response_message."""
    fake = {"response": {"response_message": response_message}, "token_usage": token_usage}
    with patch(f"{_JUDGE_MOD}.llm_chat_with_json_output", return_value=fake):
        return judge.evaluate("q", response_text, PROFILE, TASK, None)


# ---------------------------------------------------------------------------
# _clamp_score bounds
# ---------------------------------------------------------------------------

def test_clamp_score_v1_default_bounds():
    assert _clamp_score(3, "x") == 3
    assert _clamp_score(0, "x") == 1          # v1 floors at 1
    assert _clamp_score(9, "x") == 5          # ceiling 5
    assert _clamp_score("nope", "x") == 1     # non-int → v1 default 1
    print("PASSED: _clamp_score v1 default [1,5] floor/ceiling/non-int")


def test_clamp_score_v2_min_value_zero():
    assert _clamp_score(0, "x", min_value=0) == 0    # v2 allows a genuine 0
    assert _clamp_score(3, "x", min_value=0) == 3
    assert _clamp_score(9, "x", min_value=0) == 5    # ceiling still 5
    assert _clamp_score("nope", "x", min_value=0) == 0  # non-int → v2 default 0
    print("PASSED: _clamp_score v2 [0,5] floor/ceiling/non-int")


# ---------------------------------------------------------------------------
# v2 parsing via LLMJudge.evaluate
# ---------------------------------------------------------------------------

def _v2_payload(p, t, i, p_score=None, t_score=None, i_score=None):
    """Build a v2-shaped response; scores default to the criteria sum."""
    def blk(crit, score):
        return {"criteria": {str(k + 1): v for k, v in enumerate(crit)},
                "score": sum(crit) if score is None else score,
                "justification": {}}
    return json.dumps({
        "profile_usage": blk(p, p_score),
        "task_usage": blk(t, t_score),
        "integration": blk(i, i_score),
    })


def test_v2_happy_path_sums_criteria():
    j = LLMJudge(rubric_version="v2")
    resp = _v2_payload([1, 1, 0, 1, 0], [1, 1, 1, 1, 1], [0, 0, 0, 0, 0])
    s = _run_evaluate(j, resp, token_usage={"total_tokens": 10})
    assert (s.profile_usage_score, s.task_usage_score, s.integration_score) == (3, 5, 0)
    assert s.rubric_version == "v2"
    assert s.token_usage == {"total_tokens": 10}
    for v in (s.profile_usage_score, s.task_usage_score, s.integration_score):
        assert 0 <= v <= 5
    print("PASSED: v2 happy path sums criteria into [0,5], rubric_version=v2")


def test_v2_recomputed_sum_wins_over_reported_score():
    j = LLMJudge(rubric_version="v2")
    # reported scores 2/5/99 disagree with sums 5/0/2 → recomputed must win
    resp = _v2_payload([1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [1, 0, 1, 0, 0],
                       p_score=2, t_score=5, i_score=99)
    s = _run_evaluate(j, resp)
    assert (s.profile_usage_score, s.task_usage_score, s.integration_score) == (5, 0, 2)
    print("PASSED: v2 recomputed criteria sum overrides disagreeing reported score")


def test_v2_malformed_dimension_none_only_for_that_dim():
    j = LLMJudge(rubric_version="v2")
    resp = json.dumps({
        "profile_usage": {"criteria": {"1": 1, "2": 1, "3": 0, "4": 0, "5": 0}, "score": 2},
        "task_usage": {"score": 4},  # missing criteria entirely
        "integration": {"criteria": {"1": 1, "2": 1, "3": 1, "4": 0, "5": 0}},  # no score
    })
    s = _run_evaluate(j, resp)
    assert s.profile_usage_score == 2
    assert s.task_usage_score is None          # malformed → None
    assert s.integration_score == 3            # score absent → recomputed
    assert s.rubric_version == "v2"
    print("PASSED: v2 malformed dimension → None for that dim only")


def test_v2_rubric_version_on_all_failure_paths():
    j = LLMJudge(rubric_version="v2")

    # non-JSON text (json.loads fails, extraction fails)
    s = _run_evaluate(j, "this is not json at all {oops")
    assert s.rubric_version == "v2" and s.profile_usage_score is None

    # non-dict JSON (a list)
    s = _run_evaluate(j, json.dumps([1, 2, 3]))
    assert s.rubric_version == "v2" and s.profile_usage_score is None

    # fallback-None: primary returns None response_message; fallback llm_chat
    # also returns None → early return
    primary = {"response": {"response_message": None}, "token_usage": None}
    fallback = {"response": {"response_message": None}, "token_usage": None}
    with patch(f"{_JUDGE_MOD}.llm_chat_with_json_output", return_value=primary), \
         patch("cerebrum.llm.apis.llm_chat", return_value=fallback):
        s = j.evaluate("q", "r", PROFILE, TASK, None)
    assert s.rubric_version == "v2" and s.profile_usage_score is None

    # outer-except: the LLM call raises
    with patch(f"{_JUDGE_MOD}.llm_chat_with_json_output", side_effect=RuntimeError("boom")):
        s = j.evaluate("q", "r", PROFILE, TASK, None)
    assert s.rubric_version == "v2" and s.profile_usage_score is None

    print("PASSED: v2 rubric_version stamped on happy + all failure paths")


# ---------------------------------------------------------------------------
# criteria_breakdown
# ---------------------------------------------------------------------------

def test_v2_criteria_breakdown_populated_and_exact():
    j = LLMJudge(rubric_version="v2")
    resp = json.dumps({
        "profile_usage": {"criteria": {"1": 1, "2": 0, "3": 1, "4": 1, "5": 0},
                          "score": 3, "justification": {"2": "no lang", "5": "not tied"}},
        "task_usage": {"criteria": {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1},
                       "score": 5, "justification": {}},
        "integration": {"criteria": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                        "score": 0, "justification": {"1": "no joint ref"}},
    })
    s = _run_evaluate(j, resp)
    cb = s.criteria_breakdown
    assert cb is not None
    assert cb["profile_usage"]["criteria"] == {"1": 1, "2": 0, "3": 1, "4": 1, "5": 0}
    assert cb["profile_usage"]["justification"] == {"2": "no lang", "5": "not tied"}
    assert cb["integration"]["justification"] == {"1": "no joint ref"}
    print("PASSED: v2 criteria_breakdown populated with exact criteria/justification")


def test_v2_criteria_breakdown_round_trip_through_trialresult():
    j = LLMJudge(rubric_version="v2")
    resp = _v2_payload([1, 0, 1, 0, 1], [1, 1, 0, 0, 0], [0, 1, 0, 0, 0])
    s = _run_evaluate(j, resp)
    tr = TrialResult(
        trial_index=0, condition="kernel_shared",
        profile_usage_score=s.profile_usage_score,
        task_usage_score=s.task_usage_score,
        integration_score=s.integration_score,
        rubric_version=s.rubric_version,
        criteria_breakdown=s.criteria_breakdown,
    )
    dumped = json.loads(json.dumps(tr.model_dump()))
    assert dumped["criteria_breakdown"] == s.criteria_breakdown
    reparsed = TrialResult(**dumped)
    assert reparsed.criteria_breakdown == s.criteria_breakdown
    assert reparsed.rubric_version == "v2"
    print("PASSED: criteria_breakdown survives TrialResult JSON round-trip")


def test_v1_criteria_breakdown_none_on_every_path():
    j = LLMJudge(rubric_version="v1")
    # happy
    ok = _run_evaluate(j, json.dumps({
        "profile_usage_score": 4, "task_usage_score": 3, "integration_score": 5,
        "profile_usage_reasoning": "p", "task_usage_reasoning": "t", "integration_reasoning": "i",
    }))
    assert ok.criteria_breakdown is None and ok.rubric_version == "v1"
    # incomplete
    assert _run_evaluate(j, json.dumps({"profile_usage_score": 4})).criteria_breakdown is None
    # non-dict
    assert _run_evaluate(j, json.dumps([1, 2])).criteria_breakdown is None
    # outer-except
    with patch(f"{_JUDGE_MOD}.llm_chat_with_json_output", side_effect=RuntimeError("boom")):
        exc = j.evaluate("q", "r", PROFILE, TASK, None)
    assert exc.criteria_breakdown is None and exc.rubric_version == "v1"
    print("PASSED: v1 criteria_breakdown None on happy + all failure paths")


# ---------------------------------------------------------------------------
# v1 contract pinned to FIXED expected values (no git ref)
# ---------------------------------------------------------------------------

def test_v1_contract_fixed_expected():
    j = LLMJudge(rubric_version="v1")
    resp = json.dumps({
        "profile_usage_score": 4, "task_usage_score": 3, "integration_score": 5,
        "profile_usage_reasoning": "pr", "task_usage_reasoning": "tr", "integration_reasoning": "ir",
    })
    s = _run_evaluate(j, resp, token_usage={"total_tokens": 7})
    # The actual v1 contract, hardcoded:
    assert s.model_dump() == {
        "profile_usage_score": 4,
        "task_usage_score": 3,
        "integration_score": 5,
        "rubric_version": "v1",
        "criteria_breakdown": None,
        "generic_penalty": None,
        "profile_usage_reasoning": "pr",
        "task_usage_reasoning": "tr",
        "integration_reasoning": "ir",
        "token_usage": {"total_tokens": 7},
    }
    print("PASSED: v1 flat-6-key contract pinned to fixed expected values")


def test_v1_out_of_range_clamped_to_1_5():
    j = LLMJudge(rubric_version="v1")
    # 0 must floor to 1 (v1), 9 must cap to 5
    resp = json.dumps({
        "profile_usage_score": 0, "task_usage_score": 9, "integration_score": 3,
    })
    s = _run_evaluate(j, resp)
    assert s.profile_usage_score == 1 and s.task_usage_score == 5 and s.integration_score == 3
    print("PASSED: v1 scores clamped to [1,5]")


# ---------------------------------------------------------------------------
# HybridJudge v2-awareness
# ---------------------------------------------------------------------------

def test_keyword_score_floor_v1_v2():
    assert keyword_score("", ["a", "b"]) == 1                      # empty kw → v1 floor 1
    assert keyword_score("", ["a", "b"], min_value=0) == 0         # v2 floor 0
    assert keyword_score("nothing", ["zzz", "qqq"]) == 1           # ratio 0 → floor 1
    assert keyword_score("nothing", ["zzz", "qqq"], min_value=0) == 0
    assert keyword_score("aaa bbb", ["aaa", "bbb"]) == 5           # top bucket same
    assert keyword_score("aaa bbb", ["aaa", "bbb"], min_value=0) == 5
    print("PASSED: keyword_score floor v1=1 / v2=0, top buckets unchanged")


def _run_hybrid(hj, llm_kwargs, response):
    canned = JudgeScores(**llm_kwargs)
    with patch.object(hj.llm_judge, "evaluate", return_value=canned):
        return hj.evaluate("q", response, PROFILE, TASK, None)


def test_hybrid_v2_genuine_zero_survives():
    hj = HybridJudge(rubric_version="v2")
    s = _run_hybrid(
        hj,
        dict(profile_usage_score=0, task_usage_score=5, integration_score=2, rubric_version="v2"),
        response="completely generic text with no matches whatsoever",
    )
    for v in (s.profile_usage_score, s.task_usage_score, s.integration_score):
        assert 0 <= v <= 5
    # kw=0 (no matches, v2 floor) averaged with llm=0 → 0, NOT floored to 1
    assert s.profile_usage_score == 0
    assert s.rubric_version == "v2"
    print("PASSED: hybrid v2 in [0,5], genuine 0 not floored to 1")


def test_hybrid_v1_avg_clamp_floors_at_1():
    hj = HybridJudge(rubric_version="v1")
    # even with no keyword matches, v1 keyword floor is 1 and _avg clamps at 1
    s = _run_hybrid(
        hj,
        dict(profile_usage_score=1, task_usage_score=1, integration_score=1, rubric_version="v1"),
        response="completely generic text with no matches whatsoever",
    )
    for v in (s.profile_usage_score, s.task_usage_score, s.integration_score):
        assert 1 <= v <= 5
    print("PASSED: hybrid v1 _avg clamp floors at 1")


def test_hybrid_none_llm_subscore_falls_back_to_keyword_only():
    from benchmarks.shared_memory.judge import _extract_keywords, keyword_score as kws
    response = ("pytest ruff Python Cerebrum SDK v2 judge experiment ship "
                "rubric parsing land subtask")

    # v2: None LLM sub-score → keyword-only (floor 0)
    hj2 = HybridJudge(rubric_version="v2")
    s2 = _run_hybrid(
        hj2,
        dict(profile_usage_score=None, task_usage_score=4, integration_score=None, rubric_version="v2"),
        response=response,
    )
    kw = _extract_keywords(PROFILE, TASK)
    exp_profile = kws(response, kw["profile"], min_value=0)
    exp_integration = min(kws(response, kw["profile"], min_value=0),
                          kws(response, kw["task"], min_value=0))
    assert s2.profile_usage_score == exp_profile
    assert s2.integration_score == exp_integration

    # v1: None LLM sub-score → keyword-only (floor 1)
    hj1 = HybridJudge(rubric_version="v1")
    s1 = _run_hybrid(
        hj1,
        dict(profile_usage_score=None, task_usage_score=4, integration_score=None, rubric_version="v1"),
        response=response,
    )
    exp_profile_v1 = kws(response, kw["profile"], min_value=1)
    assert s1.profile_usage_score == exp_profile_v1
    print("PASSED: hybrid None LLM sub-score → keyword-only for v1 and v2")


def main():
    print("=== Judge v2 Tests ===\n")
    test_clamp_score_v1_default_bounds()
    test_clamp_score_v2_min_value_zero()
    test_v2_happy_path_sums_criteria()
    test_v2_recomputed_sum_wins_over_reported_score()
    test_v2_malformed_dimension_none_only_for_that_dim()
    test_v2_rubric_version_on_all_failure_paths()
    test_v2_criteria_breakdown_populated_and_exact()
    test_v2_criteria_breakdown_round_trip_through_trialresult()
    test_v1_criteria_breakdown_none_on_every_path()
    test_v1_contract_fixed_expected()
    test_v1_out_of_range_clamped_to_1_5()
    test_keyword_score_floor_v1_v2()
    test_hybrid_v2_genuine_zero_survives()
    test_hybrid_v1_avg_clamp_floors_at_1()
    test_hybrid_none_llm_subscore_falls_back_to_keyword_only()
    print("\n=== ALL JUDGE V2 TESTS PASSED ===")


if __name__ == "__main__":
    main()
