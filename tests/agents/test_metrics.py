"""The judge's score arithmetic and the judge-free answer measure
(NeurIPS Subtask 20, AIOS docs/METRICS.md)."""
import pytest

from benchmarks.shared_memory import judge, metrics
from benchmarks.shared_memory.metrics import (
    hybrid_score,
    keyword_scores,
    median_score,
    profile_facts_in_answer,
)
from tests.agents.test_judge_prompt_v2 import PROFILE, TASK


def test_the_keyword_score_lives_in_metrics_and_judge_reexports_it():
    assert judge.keyword_score is metrics.keyword_score
    assert judge._extract_keywords is metrics._extract_keywords


def test_keyword_integration_is_the_lower_of_profile_and_task():
    # Profile keywords: ana, vim, git, go (Li is too short): all hit.
    # Task keywords: web, server, load, test, handle, connections,
    # tail, latency: "server" alone hits, 1 of 8.
    answer = "Ana: use vim, git and Go on the server."
    scores = keyword_scores(answer, PROFILE, TASK)
    assert scores == {"profile": 5, "task": 2, "integration": 2}


@pytest.mark.parametrize("keyword, llm, hybrid", [
    (2, 3, 2),   # 2.5 rounds to even
    (3, 4, 4),   # 3.5 rounds to even
    (1, 2, 2),   # 1.5 rounds to even
    (4, 5, 4),   # 4.5 rounds to even
    (5, 5, 5),
    (1, 1, 1),
])
def test_the_hybrid_rounds_halves_to_even(keyword, llm, hybrid):
    assert hybrid_score(keyword, llm) == hybrid
    assert judge.HybridJudge.combine(
        "", PROFILE, TASK, judge.JudgeScores(
            profile_usage_score=llm, task_usage_score=llm,
            integration_score=llm)
    ).profile_usage_score == hybrid_score(1, llm)


def test_the_median_of_an_odd_number_of_scores():
    assert median_score([4]) == 4
    assert median_score([2, 5, 3]) == 3
    assert median_score([1, 1, 5, 5, 3]) == 3
    with pytest.raises(ValueError, match="odd"):
        median_score([2, 4])


def test_profile_facts_in_answer_counts_named_items_not_the_style():
    # Items: Ana Li, Go, vim, git (the style "terse" is not one).
    assert profile_facts_in_answer(PROFILE, "Ana Li, use vim.") == 0.5
    assert profile_facts_in_answer(PROFILE, "Be terse.") == 0.0
    # Whole words only: "Go" is not in "algorithm".
    assert profile_facts_in_answer(PROFILE, "the algorithm") == 0.0
    assert profile_facts_in_answer(PROFILE, None) is None


def test_a_run_records_profile_facts_in_answer_with_the_other_measures():
    from benchmarks.shared_memory import judge_free

    with_answer = judge_free.measure(PROFILE, "u", None, [],
                                     answer="Ana Li, use vim.")
    assert with_answer.profile_facts_in_answer == 0.5
    assert judge_free.measure(PROFILE, "u", None, []
                              ).profile_facts_in_answer is None


def test_a_stored_trial_without_the_field_gets_it_from_its_record():
    profile = PROFILE.model_dump()
    old = {"synthetic_profile": profile, "assistant_response": "Ana: Go.",
           "judge_free": {"profile_facts_in_block": 1.0}}
    # Ana Li (whole name only), Go, vim, git: Go alone.
    assert metrics.trial_profile_facts_in_answer(old) == 0.25
    new = {**old, "judge_free": {"profile_facts_in_answer": None}}
    assert metrics.trial_profile_facts_in_answer(new) is None
    cell = metrics.cell_judge_free([
        old, {**old, "assistant_response": "Ana Li: vim, git, Go."},
        {**old, "failed": True}])
    assert cell["n"] == 2
    assert cell["facts_in_answer"] == pytest.approx((0.25 + 1.0) / 2)
