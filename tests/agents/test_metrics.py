"""The judge's score arithmetic and the judge-free answer measure
(NeurIPS Subtask 20, AIOS docs/METRICS.md)."""
import json
import tarfile
from pathlib import Path

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


def test_the_keywords_follow_each_rule():
    """METRICS.md, "Keyword score": name parts longer than 2, each tool
    and the language (not the style); the project's words longer than
    2, the experiment's, goals' and blockers' longer than 3;
    lowercased, deduplicated."""
    from benchmarks.shared_memory.models import (
        SyntheticProfile,
        SyntheticTaskContext,
    )

    profile = SyntheticProfile(
        user_name="C. Ana Li", preferred_tools=["PyCharm", "git"],
        preferred_language="Rust", response_style="verbose")
    task = SyntheticTaskContext(
        current_project="API load balancer", active_experiment="run new soak",
        goals=["Reduce load latency"], blockers=["flaky DNS cache"],
        next_steps=["add pooling"])
    keywords = metrics._extract_keywords(profile, task)
    assert sorted(keywords["profile"]) == ["ana", "git", "pycharm", "rust"]
    assert sorted(keywords["task"]) == [
        "api", "balancer", "cache", "flaky", "latency", "load", "reduce",
        "soak"]


@pytest.mark.parametrize("hits, of, score", [
    (1, 2, 5),     # 0.5
    (7, 20, 4),    # 0.35
    (1, 5, 3),     # 0.2
    (1, 10, 2),    # 0.1
    (0, 10, 1),
    (0, 0, 1),     # no keyword
])
def test_the_keyword_score_at_each_cut(hits, of, score):
    keywords = [f"kw{n:02d}" for n in range(of)]
    assert metrics.keyword_score(" ".join(keywords[:hits]) or "none",
                                 keywords) == score


# -- the recorded pilot, on each score ------------------------------------------

PILOT_FIXTURE = (Path(__file__).resolve().parent / "fixtures" / "pilot_runs"
                 / "pilot_v1_hetero.tar.xz")
PILOT_REPORTS = (Path(__file__).resolve().parents[2] / "results"
                 / "s20_rejudge" / "pilot_report")


@pytest.mark.parametrize("name, args", [
    ("hybrid", ["--score", "hybrid"]),
    ("keyword", ["--score", "keyword"]),
    ("llm_claude-sonnet-5.5", ["--score", "llm",
                               "--judge", "claude-sonnet-5.5"]),
])
def test_the_pilot_report_reproduces_subtask_11_on_each_score(tmp_path,
                                                               name, args):
    """Subtask 11's pilot, its records trimmed to the fields the report
    reads (``fixtures/pilot_runs/make_fixtures.py``), gives the
    committed report on each score: every cell mean, gap, interval,
    leak and missing rate, facts_in_answer and the verdict, and (keyword)
    no stored hybrid score the recomputed keyword score cannot give (the
    report lists any as a problem)."""
    from benchmarks.shared_memory import pilot_analysis
    from tests.agents.test_ablation_report import same

    with tarfile.open(PILOT_FIXTURE) as archive:
        archive.extractall(tmp_path, **(
            {"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    out = tmp_path / "out"
    out.mkdir()
    pilot_analysis.main([str(tmp_path / "pilot_v1_hetero"), *args,
                         "--markdown", str(out / f"{name}.md"),
                         "--json", str(out / f"{name}.json")])
    assert ((out / f"{name}.md").read_text()
            == (PILOT_REPORTS / f"{name}.md").read_text())
    assert same(json.loads((out / f"{name}.json").read_text()),
                json.loads((PILOT_REPORTS / f"{name}.json").read_text()))


def probed(index, passed, kind="recency"):
    return {"trial_index": index,
            "probe_results": [{"type": kind, "passed": passed}]}


def test_an_unscored_outcome_or_missing_value_is_left_out():
    """METRICS.md: a None outcome is not scored and a missing value is
    left out of a mean (not counted as a failure or as 0); bench_v2's
    block size alone counts a missing ``tokens_estimated`` as 0."""
    assert metrics.flag_rate([True, None, False])["n"] == 2
    here = [probed(0, False), probed(1, None), probed(2, True)]
    there = [probed(0, True), probed(1, True), probed(2, True)]
    out = metrics.paired_outcomes(here, there, "recency")
    assert (out["lost"], out["gained"], out["same"]) == (1, 0, 1)
    paired = metrics.paired_mean(here, there,
                                 metrics.failed_outcome("recency"))
    assert (paired["n"], paired["mean"]) == (2, 0.5)
    assert metrics.mean_known([2, None, 4]) == 3
    probes = [{"diagnostics": {"tokens_estimated": 100}}, {"diagnostics": {}}]
    assert metrics.block_tokens_known({"probe_results": probes}) == 100
    assert metrics.block_size(probes)["block_tokens"] == 50
    assert metrics.pass_rate(3, 4)["rate"] == 0.75


def test_a_cells_judge_free_rates_read_each_rule():
    """A leak is another user's row or another agent's private row; the
    facts_in_answer mean leaves out a trial without an answer; the split
    of memories_missing reads the recorded lost writers."""
    leak = {"judge_free": {"private_rows_from_others": 1}}
    answered = {"judge_free": {"profile_facts_in_answer": 0.5}}
    unanswered = {"judge_free": {"profile_facts_in_answer": None}}
    out = metrics.cell_judge_free([leak, answered, unanswered])
    assert out["leak_rate"] == pytest.approx(1 / 3)
    assert out["facts_in_answer"] == 0.5
    split = {"judge_free": {"memories_missing_writers": ["a", "b"],
                            "memories_withheld_writers": ["a"],
                            "memories_lost_writers": ["b"]}}
    assert metrics.missing_split(split) == (["a"], ["b"])


def test_a_write_without_a_row_is_one_whose_reply_named_none():
    """Only a write whose recorded reply listed no id counts (not one
    with no recorded reply, a suppressed one or a quota rejection)."""
    events = [{"type": "add", "event_id": "e1", "reported_ids": []},
              {"type": "add", "event_id": "e2"},
              {"type": "add", "event_id": "e3", "reported_ids": [],
               "suppressed": True},
              {"type": "add", "event_id": "e4", "reported_ids": ["m1"]}]
    assert metrics.writes_without_row(
        {"sessions": [{"events": events}]}) == ["e1"]


def test_the_pilot_reports_defaults_are_the_hybrid_and_the_primary_judge(
        tmp_path):
    """``pilot_analysis`` reads the registered hybrid by default, and
    ``--score llm`` the primary judge's record (none in this fixture,
    which the second judge alone re-judged)."""
    from benchmarks.shared_memory import pilot_analysis

    with tarfile.open(PILOT_FIXTURE) as archive:
        archive.extractall(tmp_path, **(
            {"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    root = str(tmp_path / "pilot_v1_hetero")
    pilot_analysis.main([root, "--markdown", str(tmp_path / "d.md")])
    assert (tmp_path / "d.md").read_text() == \
        (PILOT_REPORTS / "hybrid.md").read_text()
    pilot_analysis.main([root, "--score", "llm",
                         "--json", str(tmp_path / "llm.json")])
    cells = json.loads((tmp_path / "llm.json").read_text())["cells"]
    assert cells and all(row["profile"] is None for row in cells)
