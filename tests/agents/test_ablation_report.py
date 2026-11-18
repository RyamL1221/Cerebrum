"""The kernel ablations' report and contribution figure (NeurIPS Subtask
19, AIOS docs/ABLATION.md, "Analysis"), on cells written as AIOS
``scripts/run_ablation.sh`` lays them out."""
import json
import re

import pytest

from benchmarks.shared_memory import ablation_report as report
from benchmarks.shared_memory.ablation_figure import contribution_svg


def probe(kind, passed=True, block="b", **fields):
    return {"type": kind, "probe_id": kind, "passed": passed,
            "diagnostics": {"block_text": block,
                            "tokens_estimated": fields.pop("tokens", 100),
                            "after_threshold": fields.pop("after", 10),
                            "after_cap": fields.pop("cap", 10)},
            **fields}


def trial(i, probes=None, stress=None, judge_free=None, **fields):
    kinds = ("deletion", "privacy", "recall", "recency", "contradiction",
             "integration")
    given = {p["type"]: p for p in probes or []}
    return {"trial_index": i, "failed": False,
            "probe_results": [given.get(k) or probe(k) for k in kinds],
            "stress": stress or {}, "judge_free": judge_free or {},
            **fields}


def write(root, phase, condition, trials, method="kernel_shared"):
    path = root / "qwen" / phase / f"{condition}_{method}" / \
        f"results_{method}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"conditions": [{"trials": trials}]}))


def late(n):
    """A trial whose probes read ``n`` covered late writes in all."""
    return {"probes": {"p1": {"late_covered": ["w"] * n,
                              "stale_read": n > 1, "timing_miss": False}}}


def test_load_reads_the_full_kernel_the_switches_and_the_reference(
        tmp_path):
    write(tmp_path, "kinh", "n6conc", [trial(0)])
    write(tmp_path, "kinh_barrier", "n6conc", [trial(0)])
    write(tmp_path, "kinh_forget_scope", "n6h0", [trial(0)])
    write(tmp_path, "agent", "n6v4", [trial(0)], "replicated_inhouse")
    write(tmp_path, "kinh_cache", "n6h0", [trial(0)])  # no such switch
    assert set(report.load(tmp_path)) == {
        ("qwen", "inhouse", "barrier", "n6conc", "kernel_shared"),
        ("qwen", "inhouse", "forget_scope", "n6h0", "kernel_shared"),
        ("qwen", "inhouse", "replicated", "n6v4", "replicated_inhouse"),
        ("qwen", "inhouse", None, "n6conc", "kernel_shared"),
    }


def test_a_row_is_the_paired_difference_with_its_interval(tmp_path):
    """Ablated minus full, by trial index, over the users both have; a
    failed trial is left out."""
    write(tmp_path, "kinh", "n6conc",
          [trial(i, stress=late(0)) for i in range(4)])
    ablated = [trial(i, stress=late(n)) for i, n in enumerate((3, 5, 4))]
    ablated.append(dict(trial(3, stress=late(50)), failed=True))
    write(tmp_path, "kinh_barrier", "n6conc", ablated)
    rows = report.rows(report.load(tmp_path))
    (row,) = [r for r in rows if r["measure"].startswith("covered")]
    assert (row["n"], row["full"], row["ablated"], row["diff"]) == (
        3, 0, 4, 4)
    assert row["ci"][0] > 0 and row["confirmed"] is True
    assert all(type(v) is float for v in row["ci"] + [row["diff"]])
    assert row["switch"] == "barrier" and row["value"] == "off"


@pytest.mark.parametrize("diffs, direction, want", [
    ([2, 3, 2, 3, 2, 3], +1, True), ([1, 2, 3], +1, False),
    ([-1, 0, 1], +1, False), ([-3, -2, -4, -3, -2, -4], -1, True),
    ([2, 2, 2], +1, True), ([0, 0, 0], +1, False), ([1, 2], 0, None),
])
def test_a_prediction_is_confirmed_when_its_interval_excludes_0(
        diffs, direction, want):
    import statistics

    from benchmarks.shared_memory.probes import t_interval

    low, high = t_interval(diffs)
    row = {"direction": direction, "diff": statistics.mean(diffs),
           "ci": None if low is None else [low, high]}
    assert report.confirmed(row) is want


def test_the_functional_rules_on_each_switch(tmp_path):
    def cell(phase, condition, trials):
        write(tmp_path, phase, condition, trials)

    cell("kinh", "n6conc", [trial(0, stress=late(0))])
    cell("kinh_barrier", "n6conc", [trial(0, stress=late(2))])
    # forget_scope: users 0 and 4 echo; 0 keeps a carrier and fails.
    cell("kinh", "n6h0", [trial(i) for i in range(5)])
    cell("kinh_forget_scope", "n6h0", [
        trial(i, probes=[probe("deletion", passed=i not in (0, 4))],
              revoked_value_rows=[{"memory_id": "r"}] if i in (0, 4)
              else [])
        for i in range(5)])
    # quota: every flood write accepted, more flood rows.
    for level in ("n6flood10", "n6flood50"):
        cell("kinh", level, [trial(0, stress={
            "probes": {"p": {"flood_rows_in_block": 1}},
            "quota_rejected": {"flood": 9}})])
        cell("kinh_quota", level, [trial(0, stress={
            "probes": {"p": {"flood_rows_in_block": 6}}})])
    # consumer_config: the kernel's V4 blocks equal replicated's, and
    # the full kernel's V4 blocks equal its H = 0 blocks.
    cell("kinh", "n6v4", [trial(0)])
    cell("kinh_consumer_config", "n6v4",
         [trial(0, probes=[probe("recall", block="v4")])])
    write(tmp_path, "agent", "n6v4",
          [trial(0, probes=[probe("recall", block="v4")])],
          "replicated_inhouse")
    checks = {(c["switch"], c["rule"][:12]): c["held"]
              for c in report.functional_checks(report.load(tmp_path))}
    assert checks == {
        ("barrier", "a covered la"): True,
        ("forget_scope", "echo users k"): True,
        ("quota", "n6flood10: n"): True,
        ("quota", "n6flood50: n"): True,
        ("consumer_config", "the kernel's"): True,
        ("consumer_config", "on the full "): True,
    }


def test_a_rule_that_does_not_hold_is_reported_so(tmp_path):
    write(tmp_path, "kinh", "n6conc", [trial(0, stress=late(1))])
    write(tmp_path, "kinh_barrier", "n6conc", [trial(0, stress=late(2))])
    (check,) = report.functional_checks(report.load(tmp_path))
    assert check["held"] is False and check["seen"] == "2 ablated, 1 full"


def test_the_smoke_checks_are_the_primary_predictions(tmp_path):
    write(tmp_path, "kinh", "n6wrong_user",
          [trial(i, stress={"misfiled_rows": 0}) for i in range(3)])
    write(tmp_path, "kinh_identity", "n6wrong_user",
          [trial(i, stress={"misfiled_rows": 6 + i}) for i in range(3)])
    table = report.rows(report.load(tmp_path))
    checks = report.smoke_checks(table)
    assert [(c["switch"], c["measure"], c["held"]) for c in checks] == [
        ("identity", "misfiled rows per user", True)]


def test_the_report_writes_markdown_json_and_the_figure(tmp_path):
    write(tmp_path, "kinh", "n6conc",
          [trial(i, stress=late(0)) for i in range(3)])
    write(tmp_path, "kinh_barrier", "n6conc",
          [trial(i, stress=late(2 + i)) for i in range(3)])
    out = tmp_path / "out"
    out.mkdir()
    report.main([str(tmp_path), "--md", str(out / "a.md"),
                 "--json", str(out / "a.json"), "--svg", str(out / "a.svg")])
    text = (out / "a.md").read_text()
    assert "| barrier: off | n6conc | covered late writes per user " \
           "(primary) | 0.00 | 3.00 | +3.00 [" in text
    data = json.loads((out / "a.json").read_text())
    assert data["smoke_checks"][0]["held"] is True
    svg = (out / "a.svg").read_text()
    assert svg.count('class="bar"') == 1


def test_the_figure_draws_one_bar_per_primary_row_on_its_own_axis():
    rows = [
        {"primary": True, "switch": "barrier", "value": "off",
         "measure": "covered late writes per user", "condition": "n6conc",
         "n": 30, "full": 0.0, "ablated": 18.0, "diff": 18.0,
         "ci": [12.0, 24.0]},
        {"primary": True, "switch": "quota", "value": "off",
         "measure": "profile facts", "condition": "n6flood50", "n": 30,
         "full": 0.9, "ablated": 0.4, "diff": -0.5, "ci": [-0.7, -0.3]},
        {"primary": False, "switch": "quota", "value": "off",
         "measure": "memories_missing", "condition": "n6flood50", "n": 30,
         "full": 0.0, "ablated": 1.0, "diff": 1.0, "ci": [0.5, 1.5]},
        {"primary": True, "switch": "budget", "value": "off",
         "measure": "tokens", "condition": "n6h0", "n": 0, "full": None,
         "ablated": None, "diff": None, "ci": None},
    ]
    svg = contribution_svg(rows)
    assert svg.count('class="bar"') == 2       # the no-data row has none
    assert svg.count("no data") == 1
    assert svg.count("<title>") == 2           # a tooltip per bar
    # Each row on its own axis: the interval end farthest from 0 sits
    # the same distance from the zero line in both rows.
    from benchmarks.shared_memory import ablation_figure as figure

    zero = figure.LABEL_W + figure.PLOT_W / 2
    spans = [max(abs(float(a) - zero), abs(float(b) - zero))
             for a, b, y1, y2 in re.findall(
                 r'class="whisker" x1="([\d.]+)" x2="([\d.]+)" '
                 r'y1="([\d.]+)" y2="([\d.]+)"', svg) if y1 == y2]
    assert len(spans) == 2 and abs(spans[0] - spans[1]) < 0.2
    assert "+18.00 [+12.00, +24.00]" in svg and "-0.50 [-0.70, -0.30]" in svg
    assert "memories_missing" not in svg       # not a primary row
    assert "prefers-color-scheme: dark" in svg
