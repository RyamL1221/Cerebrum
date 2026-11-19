"""The judges' reliability protocol (NeurIPS Subtask 20, AIOS
docs/METRICS.md, "Reliability protocol", "The k rule", "Agreement
between the judges")."""
import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.shared_memory import judge_reliability as jr
from benchmarks.shared_memory import pilot_analysis as pa
from benchmarks.shared_memory.judge import JudgeFailed

# Krippendorff (2011), "Computing Krippendorff's alpha-reliability": four
# coders, twelve units, missing values; the published alphas.
EXAMPLE = [
    [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None],
    [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3],
    [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None],
    [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None],
]


@pytest.mark.parametrize("metric, value", [
    ("nominal", 0.743), ("ordinal", 0.815), ("interval", 0.849)])
def test_alpha_reproduces_krippendorffs_example(metric, value):
    units = [list(unit) for unit in zip(*EXAMPLE)]
    assert round(jr.alpha(units, metric), 3) == value


def test_the_fast_forms_equal_the_general_alpha():
    rng = np.random.default_rng(0)
    m = rng.integers(1, 6, size=(40, 10)).astype(float)
    assert jr.repeats_alpha(m) == pytest.approx(
        jr.alpha(m.tolist(), "interval"))
    a, b = m[:, :1].T, m[:, 1:2].T
    assert jr.two_coder_alphas(a, b)[0] == pytest.approx(
        jr.alpha(np.column_stack([a[0], b[0]]).tolist(), "interval"))
    w = rng.integers(0, 3, size=40).astype(float)
    assert jr.repeats_alpha(m, w) == pytest.approx(jr.alpha(
        np.repeat(m, w.astype(int), axis=0).tolist(), "interval"))


@pytest.mark.parametrize("k, count", [(1, 45), (3, 2100), (5, 126)])
def test_disjoint_splits(k, count):
    splits = jr.disjoint_splits(10, k)
    assert len(splits) == count
    assert all(len(a) == len(b) == k and not set(a) & set(b)
               for a, b in splits)


def rows(matrix, judge="j", dims=("profile", "task", "integration")):
    return [{"judge": judge, "item_id": f"c{u:03d}", "repeat": r + 1,
             "scores": {d: int(matrix[u][r]) for d in dims},
             "attempts": 1,
             "token_usage": {"prompt_tokens": 10, "completion_tokens": 2}}
            for u in range(len(matrix)) for r in range(len(matrix[u]))]


def test_a_steady_judge_agrees_with_itself():
    truth = np.repeat(np.arange(1, 6), 8)[:, None]
    stats = jr.reliability(rows(np.repeat(truth, 10, axis=1)), 10, 50)
    p = stats["profile"]
    assert p["exact"] == 1 and p["alpha_repeats"] == pytest.approx(1)
    assert p["median_of_k"][5]["alpha"] == pytest.approx(1)


def test_the_median_of_more_repeats_is_more_reliable():
    rng = np.random.default_rng(1)
    truth = np.repeat(np.arange(1, 6), 20)[:, None].astype(float)
    noisy = np.clip(truth + rng.choice([-1, 0, 0, 0, 1], (100, 10)), 1, 5)
    stats = jr.reliability(rows(noisy), 10, 50)["profile"]
    k1, k3, k5 = (stats["median_of_k"][k]["alpha"] for k in (1, 3, 5))
    assert k1 < k3 < k5
    lo, hi = stats["median_of_k"][3]["alpha_ci"]
    assert lo <= k3 <= hi
    assert stats["units"] == 100 and stats["dropped"] == 0


def test_an_item_with_a_failed_repeat_is_dropped():
    data = rows(np.full((3, 10), 4))
    data[0] = {**data[0], "failed": True}
    _, matrix, dropped = jr.score_matrix(data, "profile", 10)
    assert matrix.shape == (2, 10) and dropped == 1


def stats_with(alphas):
    return {d: {"median_of_k": {k: {"alpha": a} for k, a in alphas[d]}}
            for d in alphas}


def test_the_k_rule_takes_the_smallest_k_reaching_0_80_on_both():
    assert jr.k_rule(stats_with({
        "profile": [(1, 0.79), (3, 0.85), (5, 0.9)],
        "integration": [(1, 0.95), (3, 0.97), (5, 0.98)]})) == 3
    assert jr.k_rule(stats_with({
        "profile": [(1, 0.80), (3, 0.85), (5, 0.9)],
        "integration": [(1, 0.80), (3, 0.97), (5, 0.98)]})) == 1
    assert jr.k_rule(stats_with({
        "profile": [(1, 0.5), (3, 0.6), (5, 0.79)],
        "integration": [(1, 0.95), (3, 0.97), (5, 0.98)]})) is None


def write_run(root: Path, files):
    for rel, trials in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"conditions": [{"trials": trials}]}))


def stored(i, method, locus, answer, score=4, **extra):
    return {"trial_index": i, "method": method, "locus": locus,
            "failed": False, "follow_up_query": "q",
            "assistant_response": answer,
            "synthetic_profile": {"user_name": "Ana Li",
                                  "preferred_tools": ["vim"],
                                  "preferred_language": "Go",
                                  "response_style": "terse"},
            "synthetic_task_context": {"current_project": "web",
                                       "active_experiment": "load",
                                       "goals": ["g"], "blockers": ["b"],
                                       "next_steps": ["n"]},
            "profile_usage_score": score, "task_usage_score": score,
            "integration_score": score, **extra}


def test_candidates_dedupe_exclude_and_place_each_answer(tmp_path):
    write_run(tmp_path / "pilot_v1_hetero", {
        "gpt4o/kmem0/h2_kernel_shared/results_kernel_shared.json": [
            stored(0, "kernel_shared", "kernel", "a", 2),
            stored(1, "kernel_shared", "kernel", "same", 3)],
        "gpt4o/agent/h1_replicated_inhouse/results_x.json": [
            stored(0, "replicated_inhouse", "replicated", "b", 5,
                   failed=True)],
    })
    write_run(tmp_path / "pilot_v1_9d_greedy", {
        "kinh/qwen_kernel_private/results_kernel_private.json": [
            stored(0, "kernel_private", "kernel", "c")],
        "agent/qwen_native_mem0/results_native_mem0.json": [
            stored(0, "native_mem0", "native", "same", 3),
            stored(1, "native_mem0", "native", "d", 5)],
    })
    found = jr.candidates(tmp_path)
    assert [c["response"] for c in found] == ["a", "same", "d"]
    assert found[0]["cell"] == {"version": "v1", "locus": "kernel",
                                "backend": "mem0", "model": "gpt4o", "h": 2}
    assert found[2]["cell"] == {"version": "v1", "locus": "native",
                                "backend": "mem0", "model": "qwen", "h": 0}
    assert [c["band"] for c in found] == ["low", "mid", "high"]


def test_selection_is_seeded_round_robin_over_cells_and_bands():
    items = [{"cell": {"version": "v1", "locus": "kernel", "backend": "x",
                       "model": "m", "h": c}, "band": band, "n": (c, band, i)}
             for c in range(4) for band in jr.BANDS for i in range(5)]
    chosen = jr.select([dict(i) for i in items], 24, seed=7)
    again = jr.select([dict(i) for i in items], 24, seed=7)
    assert [c["n"] for c in chosen] == [c["n"] for c in again]
    per_cell = [sum(1 for c in chosen if c["cell"]["h"] == h)
                for h in range(4)]
    assert per_cell == [6, 6, 6, 6]
    per_band = {b: sum(1 for c in chosen if c["band"] == b)
                for b in jr.BANDS}
    assert per_band == {"low": 8, "mid": 8, "high": 8}
    assert len({c["n"] for c in chosen}) == 24
    assert [c["item_id"] for c in chosen][:2] == ["c001", "c002"]


def item(i):
    s = stored(i, "kernel_shared", "kernel", f"answer {i}")
    return {"item_id": f"c{i:03d}", "query": "q", "response": s[
        "assistant_response"], "profile": s["synthetic_profile"],
        "task_context": s["synthetic_task_context"]}


def test_judging_resumes_and_redoes_failed_judgments(tmp_path, monkeypatch):
    from benchmarks.shared_memory import judge as jm

    calls = []

    class Fake:
        temperature = seed = None
        model = "azure/gpt-5.4"

        def evaluate(self, query, response, profile, task):
            calls.append(response)
            return jm.JudgeScores(profile_usage_score=4, task_usage_score=4,
                                  integration_score=4, model=self.model,
                                  token_usage={"prompt_tokens": 5,
                                               "completion_tokens": 1})

    monkeypatch.setitem(jm.JUDGES, "gpt-5.4", Fake)
    monkeypatch.setitem(jr.JUDGES, "gpt-5.4", Fake)
    out = tmp_path / "j.jsonl"
    out.write_text(json.dumps({"judge": "gpt-5.4", "item_id": "c001",
                               "repeat": 1, "failed": True,
                               "attempts": 3}) + "\n" + json.dumps({
        "judge": "gpt-5.4", "item_id": "c001", "repeat": 2,
        "scores": {"profile": 3, "task": 3, "integration": 3},
        "attempts": 1}) + "\n")
    made = jr.judge_set([item(1), item(2)], "gpt-5.4", 2, out, workers=2)
    assert made == 3                      # c001-1 (failed), c002-1, c002-2
    have = jr.done_judgments(out)
    assert not have[("c001", 1)].get("failed")
    assert have[("c001", 2)]["scores"]["profile"] == 3   # kept
    assert jr.judge_set([item(1), item(2)], "gpt-5.4", 2, out) == 0


def test_the_second_judge_judges_the_set_in_one_batch(tmp_path,
                                                      monkeypatch):
    from benchmarks.shared_memory import judge as jm

    monkeypatch.setitem(jr.JUDGES, "claude-sonnet-5.5",
                        lambda: jm.ClaudeJudge(client_factory=lambda: None))
    seen = []

    def batch(llm_judge, items, repeats, **extra):
        seen.append((sorted(items), repeats))
        extra["on_submit"]("msgbatch_x")
        assert extra.get("batch_id") == resume
        return {i: {r: (JudgeFailed(3) if (i, r) == ("c002", 2) else {
            "repeat": r, "scores": {"profile": 2, "task": 2,
                                    "integration": 2}, "attempts": 1})
            for r in range(1, repeats + 1)} for i in items}

    out = tmp_path / "c.jsonl"
    resume = None
    assert jr.judge_set([item(1), item(2)], "claude-sonnet-5.5", 2, out,
                        batch=batch) == 4
    assert seen == [(["c001", "c002"], 2)]
    # The batch id is kept beside the output, to collect it again.
    assert (tmp_path / "c.jsonl.batches").read_text() == "msgbatch_x\n"
    resume = "msgbatch_x"
    out.write_text("")
    assert jr.judge_set([item(1), item(2)], "claude-sonnet-5.5", 2, out,
                        batch=batch, batch_id=resume) == 4
    have = jr.done_judgments(out)
    assert have[("c002", 2)]["failed"] and have[("c002", 2)]["attempts"] == 3
    assert have[("c001", 1)]["judge"] == "claude-sonnet-5.5"


def test_agreement_at_each_judges_own_k():
    a = rows(np.array([[1, 1, 1], [3, 3, 3], [5, 5, 5], [4, 4, 4]]), "a")
    b = rows(np.array([[2, 2, 2], [4, 3, 4], [5, 5, 5], [5, 5, 5]]), "b")
    out = jr.agreement(a, 1, b, 3, resamples=50)["profile"]
    assert out["units"] == 4
    # a at k = 1: 1, 3, 5, 4; b at k = 3: 2, 4, 5, 5.
    assert out["offset"]["mean"] == pytest.approx(0.75)
    assert out["spearman"] == pytest.approx(0.9486833)
    assert 0 < out["alpha"] < 1


def rejudged(index, method, locus, value, judge="g"):
    return {"trial_index": index, "method": method, "locus": locus,
            "judges": {judge: {"llm": {"profile": value, "task": value,
                                       "integration": value}}}}


def test_direction_agreement_counts_signs_and_lists_disagreements(tmp_path):
    def run(root, judge, kernel, replicated, native):
        files = {}
        for h, (k, r, n) in enumerate(zip(kernel, replicated, native)):
            files[f"qwen/kinh/h{2 * h}_kernel_shared/results_kernel_shared"
                  ".json"] = [rejudged(i, "kernel_shared", "kernel", k[i],
                                       judge) for i in range(3)]
            files[f"qwen/agent/h{2 * h}_replicated_inhouse/results_r.json"] \
                = [rejudged(i, "replicated_inhouse", "replicated", r[i],
                            judge) for i in range(3)]
            files[f"qwen/agent/h{2 * h}_native_inhouse/results_n.json"] = [
                rejudged(i, "native_inhouse", "native", n[i], judge)
                for i in range(3)]
        write_run(root, files)
        return jr.differences(jr.load_run(root), judge, ("profile",))

    a = run(tmp_path / "a", "g", [[4, 4, 4], [5, 5, 5]],
            [[3, 3, 3], [2, 2, 2]], [[4, 4, 4], [4, 4, 4]])
    b = run(tmp_path / "b", "c", [[4, 4, 4], [5, 5, 4]],
            [[3, 3, 3], [2, 2, 3]], [[5, 5, 5], [4, 4, 4]])
    assert set(a) == {
        "qwen inhouse H0 kernel-replicated profile",
        "qwen inhouse H2 kernel-replicated profile",
        "qwen inhouse H2-H0 kernel-replicated profile",
        "qwen inhouse H0 kernel-native profile",
        "qwen inhouse H2 kernel-native profile",
        "qwen inhouse H2-H0 kernel-native profile"}
    out = jr.direction_agreement(a, b)
    assert out["differences"] == 6
    # kernel-native at H0: 0 for one judge, -1 for the other; every
    # other difference has one sign under both.
    assert [d["difference"] for d in out["disagreements"]] == [
        "qwen inhouse H0 kernel-native profile"]
    assert out["same_direction"] == 5
    md = jr.directions_markdown({"run": {
        "differences": {"g": a, "c": b},
        "agreement": {"c vs g": jr.direction_agreement(b, a)}}})
    assert "| difference | c mean [95% CI] | g mean [95% CI] |" in md
    assert "| qwen inhouse H2 kernel-replicated profile | 2.33 [" in md
    assert "c vs g: 5 of 6 differences in the same direction" in md


def test_the_pilot_verdict_reads_the_chosen_score():
    # Keyword scores: profile 5 (ana, vim, go), task 1 (neither "web"
    # nor "load"), integration 1. Stored: profile 4 (keyword 5 with LLM
    # 3 or 4), task and integration 1 (keyword 1 with LLM 1 or 2).
    trial = stored(0, "kernel_shared", "kernel", "Ana: vim, Go.", 1,
                   profile_usage_score=4,
                   judges={"gpt-5.4": {"llm": {"profile": 2, "task": 1,
                                               "integration": 3}}})
    cells = {("qwen", "kernel", "inhouse", 0): {0: trial}}
    keyword = pa.rescore(cells, "keyword")[("qwen", "kernel", "inhouse",
                                             0)][0]
    assert keyword["profile_usage_score"] == 5          # ana, vim, go
    llm = pa.rescore(cells, "llm", "gpt-5.4")[("qwen", "kernel",
                                                 "inhouse", 0)][0]
    assert (llm["profile_usage_score"], llm["task_usage_score"],
            llm["integration_score"]) == (2, 1, 3)
    assert pa.rescore(cells, "hybrid") is cells
    assert pa.keyword_consistency(cells) == {
        "checked": 3, "inconsistent": 0, "examples": []}
    # A stored profile 1 cannot come from keyword 5.
    bad = {k: {0: {**trial, "profile_usage_score": 1}}
           for k in cells}
    assert pa.keyword_consistency(bad)["inconsistent"] == 1
