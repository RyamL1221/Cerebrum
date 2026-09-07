"""Smoke test for benchmarks/shared_memory/rejudge.py.

Uses a small synthetic results-JSON fixture and a MOCKED judge — no real API
calls, no kernel. Verifies the re-judge script:
- counts trials / re-judgeable / skipped / judge-calls correctly (plan + dry-run)
- derives a v2 output path that never overwrites the v1 input
- re-scores only re-judgeable trials, preserves non-score fields, stamps v2 +
  criteria_breakdown, and honors --limit
- delegates to judge.py's evaluate() (does not build prompts itself)
- refuses to overwrite the input file

Run directly:
    python tests/agents/test_rejudge.py
"""

import sys
sys.path.insert(0, ".")

import json
import os
import tempfile
from unittest.mock import patch

from benchmarks.shared_memory import rejudge
from benchmarks.shared_memory.models import JudgeScores, SyntheticProfile, SyntheticTaskContext


def _trial(i, *, failed=False, response="a helpful personalized answer", profile=True, task=True):
    t = {
        "trial_index": i, "condition": "kernel_shared", "method": "kernel_shared",
        "profile_usage_score": 4, "task_usage_score": 3, "integration_score": 5,
        "follow_up_query": f"What next? ({i})",
        "assistant_response": response,
        "failed": failed,
        "memory_counts": {"total": 0, "shared": 0, "private": 0},
    }
    if profile:
        t["synthetic_profile"] = {"user_name": f"User {i}", "preferred_tools": ["Git"],
                                  "preferred_language": "Python", "response_style": "concise"}
    if task:
        t["synthetic_task_context"] = {"current_project": f"Proj {i}", "active_experiment": f"Exp {i}",
                                       "goals": [f"Goal {i}"], "blockers": [], "next_steps": [f"Step {i}"]}
    return t


def _payload(trials):
    return {
        "experiment_metadata": {"trials_per_condition": len(trials), "timestamp": "orig",
                                "kernel_url": "http://localhost:8000",
                                "conditions_run": ["kernel_shared"], "methods_run": ["kernel_shared"]},
        "conditions": [{"condition": "kernel_shared", "trials": trials, "summary": {}}],
    }


# Mixed pool: 3 re-judgeable, 1 failed, 1 empty-response, 1 missing-context = 6 total, 3 rejudgeable
def _mixed_payload():
    return _payload([
        _trial(0),
        _trial(1),
        _trial(2),
        _trial(3, failed=True),
        _trial(4, response="   "),
        _trial(5, profile=False, task=False),
    ])


def _fake_v2_scores():
    return JudgeScores(
        profile_usage_score=2, task_usage_score=5, integration_score=0,
        rubric_version="v2",
        criteria_breakdown={
            "profile_usage": {"criteria": {"1": 1, "2": 0, "3": 1, "4": 0, "5": 0}, "justification": {"2": "x"}},
            "task_usage": {"criteria": {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1}, "justification": {}},
            "integration": {"criteria": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}, "justification": {"1": "y"}},
        },
        token_usage={"total_tokens": 42},
    )


def test_default_output_path_never_collides():
    assert rejudge.default_output_path("results/x/results_kernel_shared.json") == \
        "results/x/results_kernel_shared_v2.json"
    # a path already ending _v2 doesn't silently overwrite
    p = rejudge.default_output_path("results/x/results_kernel_shared_v2.json")
    assert p != "results/x/results_kernel_shared_v2.json" and p.endswith(".json")
    print("PASSED: default_output_path derives a distinct v2 path")


def test_plan_counts():
    counts = rejudge.plan(_mixed_payload())
    assert counts == {"total_trials": 6, "rejudgeable": 3, "skipped": 3, "judge_calls": 3}, counts
    # limit caps the judge-call count only
    limited = rejudge.plan(_mixed_payload(), limit=2)
    assert limited["judge_calls"] == 2 and limited["rejudgeable"] == 3
    print("PASSED: plan counts total/rejudgeable/skipped/calls (+ limit)")


def test_rejudge_reScores_only_eligible_and_preserves_fields():
    class FakeJudge:
        def __init__(self):
            self.calls = []
        def evaluate(self, query, response, profile, task_context, plausible_actions=None):
            self.calls.append((query, response, profile, task_context, plausible_actions))
            return _fake_v2_scores()

    judge = FakeJudge()
    exp = rejudge.rejudge_payload(_mixed_payload(), judge)
    trials = exp.conditions[0].trials
    assert len(trials) == 6  # all carried through
    # exactly 3 judge calls (the re-judgeable ones)
    assert len(judge.calls) == 3
    # the judge received reconstructed model objects, not raw dicts
    q, resp, prof, task, pa = judge.calls[0]
    assert isinstance(prof, SyntheticProfile) and isinstance(task, SyntheticTaskContext)
    assert pa is None  # plausible_actions absent → None

    by_idx = {t.trial_index: t for t in trials}
    # re-judged trials got v2 scores + breakdown; non-score fields preserved
    for i in (0, 1, 2):
        t = by_idx[i]
        assert t.rubric_version == "v2"
        assert (t.profile_usage_score, t.task_usage_score, t.integration_score) == (2, 5, 0)
        assert t.criteria_breakdown is not None
        assert t.follow_up_query == f"What next? ({i})"       # preserved
        assert t.method == "kernel_shared"                     # preserved
    # skipped trials become uniform-v2 failed records (no v1 scores leak into a
    # v2 artifact); non-score fields still preserved
    for i in (3, 4, 5):
        t = by_idx[i]
        assert t.rubric_version == "v2"
        assert t.failed is True
        assert t.profile_usage_score is None and t.criteria_breakdown is None
        assert t.follow_up_query == f"What next? ({i})"  # preserved
    # the whole output is single-rubric v2 (never-pool guard would fire otherwise)
    assert {t.rubric_version for t in trials} == {"v2"}
    print("PASSED: rejudge re-scores only eligible trials, marks the rest as v2/failed")


def test_rejudge_honors_limit():
    class CountingJudge:
        def __init__(self):
            self.n = 0
        def evaluate(self, **kw):
            self.n += 1
            return _fake_v2_scores()

    judge = CountingJudge()
    exp = rejudge.rejudge_payload(_mixed_payload(), judge, limit=1)
    assert judge.n == 1, judge.n
    trials = exp.conditions[0].trials
    # whole file is v2; exactly 1 trial was actually re-scored (has a score)
    assert {t.rubric_version for t in trials} == {"v2"}
    scored = [t for t in trials if t.profile_usage_score is not None]
    assert len(scored) == 1
    print("PASSED: rejudge honors --limit (only N calls, N re-scored, rest v2/failed)")


def test_dry_run_makes_no_calls_and_no_output():
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "results_kernel_shared.json")
        with open(inp, "w") as f:
            json.dump(_mixed_payload(), f)
        # Patch both judge classes to blow up if instantiated/called.
        with patch.object(rejudge, "HybridJudge", side_effect=AssertionError("must not construct judge in dry-run")), \
             patch.object(rejudge, "LLMJudge", side_effect=AssertionError("must not construct judge in dry-run")):
            rc = rejudge.main(["--input", inp, "--dry-run"])
        assert rc == 0
        # no v2 output file written
        assert not os.path.exists(rejudge.default_output_path(inp))
    print("PASSED: --dry-run makes no judge calls and writes no output")


def test_end_to_end_with_mocked_hybridjudge_writes_v2_file():
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "results_kernel_shared.json")
        with open(inp, "w") as f:
            json.dump(_mixed_payload(), f)

        # Patch HybridJudge so no real API/kernel is touched; assert rubric_version wiring.
        constructed = {}
        class MockHybrid:
            def __init__(self, llms=None, rubric_version="v1"):
                constructed["rubric_version"] = rubric_version
            def evaluate(self, **kw):
                return _fake_v2_scores()
        with patch.object(rejudge, "HybridJudge", MockHybrid):
            rc = rejudge.main(["--input", inp, "--limit", "2"])
        assert rc == 0
        assert constructed["rubric_version"] == "v2"  # script forces v2
        out = rejudge.default_output_path(inp)
        assert os.path.exists(out) and os.path.abspath(out) != os.path.abspath(inp)
        written = json.load(open(out))
        # v2 scores present in the written file; original v1 input untouched
        wt = {t["trial_index"]: t for c in written["conditions"] for t in c["trials"]}
        assert wt[0]["rubric_version"] == "v2" and wt[0]["criteria_breakdown"] is not None
        orig = json.load(open(inp))
        assert "rubric_version" not in orig["conditions"][0]["trials"][0]  # input unchanged
    print("PASSED: end-to-end (mocked HybridJudge) writes distinct v2 file, forces rubric v2, leaves input intact")


def test_refuses_to_overwrite_input():
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "results_kernel_shared.json")
        with open(inp, "w") as f:
            json.dump(_mixed_payload(), f)
        rc = rejudge.main(["--input", inp, "--output", inp, "--dry-run"])
        assert rc == 2
    print("PASSED: refuses to overwrite the v1 input file")


def main():
    print("=== rejudge.py Smoke Tests ===\n")
    test_default_output_path_never_collides()
    test_plan_counts()
    test_rejudge_reScores_only_eligible_and_preserves_fields()
    test_rejudge_honors_limit()
    test_dry_run_makes_no_calls_and_no_output()
    test_end_to_end_with_mocked_hybridjudge_writes_v2_file()
    test_refuses_to_overwrite_input()
    print("\n=== ALL REJUDGE TESTS PASSED ===")


if __name__ == "__main__":
    main()
