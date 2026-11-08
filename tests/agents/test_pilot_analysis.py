"""Subtask 11: the pilot analysis on synthetic cells with known answers
(AIOS docs/PILOT.md, "Decision rule")."""
import json

import pytest

from benchmarks.shared_memory import pilot_analysis as pa
from benchmarks.shared_memory.pilot_schedule import PATH, Schedule

SCHEDULE = Schedule(str(PATH))


def write_cells(root, scores, free=None, commit="c1"):
    """``scores(model, locus, backend, H, i) -> (profile, integration)``;
    ``free(...) -> judge_free dict``."""
    free = free or (lambda *a: {"cross_user_rows": 0,
                                "private_rows_from_others": 0,
                                "memories_missing": 0,
                                "profile_facts_in_block": 1.0})
    for model in pa.MODELS:
        for (locus, backend) in pa.CELLS:
            for level in pa.LEVELS:
                trials = []
                for i in range(pa.USERS):
                    p, g = scores(model, locus, backend, level, i)
                    trials.append({
                        "trial_index": i, "failed": False,
                        "profile_usage_score": p, "task_usage_score": 3.0,
                        "integration_score": g,
                        "input_sha256": f"u{i}",
                        "variants_applied": SCHEDULE.variants(level, i),
                        "judge_free": free(model, locus, backend, level, i),
                    })
                path = pa.cell_file(root, model, locus, backend, level)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({
                    "experiment_metadata": {
                        "git_commit": commit, "kernel_git_commit": "k1",
                        "heterogeneity": {
                            "schedule_sha256": SCHEDULE.sha256},
                    },
                    "conditions": [{"trials": trials}],
                }))


def missing_outside_kernel(model, locus, backend, level, i):
    return {"cross_user_rows": 0, "private_rows_from_others": 0,
            "memories_missing": int(level > 0 and locus != "kernel"
                                    and i % 2 == 0),
            "profile_facts_in_block": 1.0}


def analyze(root):
    cells, meta = pa.load(root)
    return cells, pa.check_pairing(cells, meta, SCHEDULE), pa.verdict(cells)


def test_a_gap_that_grows_with_h_is_go(tmp_path):
    def scores(model, locus, backend, level, i):
        base = 4.0 + (i % 3) * 0.3
        if locus == "replicated":
            return base - 0.5 * level - (i % 2) * 0.1, base - 0.4 * level
        return base, base
    write_cells(tmp_path, scores, missing_outside_kernel)
    cells, problems, v = analyze(tmp_path)
    assert problems == []
    assert v["outcome"] == "GO"
    assert v["per_model"]["qwen"]["i_and_ii_dimensions"] == [
        "profile", "integration"]
    h2 = v["per_model"]["qwen"]["h2_gap"]["profile"]
    assert h2["mean"] == pytest.approx(1.05)


def test_a_kernel_leak_is_no_go(tmp_path):
    def scores(model, locus, backend, level, i):
        return (4.0 - (locus == "replicated") * level * (0.5 + i % 2 * 0.1),
                4.0)

    def leaky(model, locus, backend, level, i):
        row = missing_outside_kernel(model, locus, backend, level, i)
        if model == "gpt4o" and locus == "kernel" and i == 3:
            row["cross_user_rows"] = 1
        return row
    write_cells(tmp_path, scores, leaky)
    _, _, v = analyze(tmp_path)
    assert not v["per_model"]["gpt4o"]["iii"]["holds"]
    assert v["outcome"] == "NO-GO"


def test_a_small_positive_gap_is_conditional_go(tmp_path):
    def scores(model, locus, backend, level, i):
        noise = 1.0 if i % 2 else -1.0
        if locus == "replicated" and level == 2:
            return 4.0 - 0.1 - noise, 4.0 - 0.1 + noise
        return 4.0, 4.0
    write_cells(tmp_path, scores, missing_outside_kernel)
    _, _, v = analyze(tmp_path)
    assert v["outcome"] == "CONDITIONAL GO"


def test_ties_are_no_go(tmp_path):
    write_cells(tmp_path, lambda *a: (4.0, 4.0), missing_outside_kernel)
    _, _, v = analyze(tmp_path)
    assert v["outcome"] == "NO-GO"


def test_pairing_problems_are_reported(tmp_path):
    write_cells(tmp_path, lambda *a: (4.0, 4.0), commit="c1-dirty")
    path = pa.cell_file(tmp_path, "qwen", "native", "mem0", 1)
    data = json.loads(path.read_text())
    data["conditions"][0]["trials"][0]["variants_applied"] = {}
    data["conditions"][0]["trials"][1]["failed"] = True
    path.write_text(json.dumps(data))
    _, problems, _ = analyze(tmp_path)
    text = "\n".join(problems)
    assert "harness commit c1-dirty" in text
    assert "H1 user 0: variants differ" in text
    assert "trial 1 failed" in text


def test_did_is_per_user(tmp_path):
    def scores(model, locus, backend, level, i):
        if locus == "replicated":
            return 4.0 - (1.0 if level == 2 else 0.0) * (i % 2), 4.0
        return 4.0, 4.0
    write_cells(tmp_path, scores)
    cells, _, _ = analyze(tmp_path)
    d = pa.did(cells, "qwen", "replicated", 2, 0, "profile")
    assert d["mean"] == pytest.approx(0.5) and d["n"] == 30


def test_integer_means_print_with_two_decimals():
    text = pa.table([{"level": 2, "n": 30, "profile": 4, "gap": 0}],
                    ["level", "n", "profile", "gap"])
    assert text.splitlines()[-1] == "| 2 | 30 | 4.00 | 0.00 |"
