"""The kernel ablations' report and contribution figure (NeurIPS Subtask
19, AIOS docs/ABLATION.md, "Analysis"), on cells written as AIOS
``scripts/run_ablation.sh`` lays them out."""
import json
import math
import re
import tarfile
from pathlib import Path

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
    ([5], +1, None),  # one pair tests nothing
])
def test_a_prediction_is_confirmed_when_its_interval_excludes_0(
        diffs, direction, want):
    import statistics

    from benchmarks.shared_memory.probes import t_interval

    low, high = t_interval(diffs)
    row = {"direction": direction, "diff": statistics.mean(diffs),
           "ci": None if low is None else [low, high], "n": len(diffs)}
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


def test_the_threshold_rule_compares_probe_by_probe(tmp_path):
    """A probe whose ablated candidates exceed the full kernel's fails
    the rule even when the user's mean does not."""
    write(tmp_path, "kinh", "n6h0", [trial(0, probes=[
        probe("recall", after=4), probe("recency", after=9)])])
    write(tmp_path, "kinh_threshold", "n6h0", [trial(0, probes=[
        probe("recall", after=5), probe("recency", after=1)])])
    (check,) = report.functional_checks(report.load(tmp_path))
    assert check["held"] is False and "(0, 'recall')" in check["seen"]


def test_each_trial_must_record_its_cells_ablation(tmp_path):
    """``trial_ablation``: the ablated cell's trials record its switch,
    the full kernel's ``{}``, an older trial its control's alias; a
    wrong record, or a cell with no successful trial, is reported."""
    write(tmp_path, "kinh", "n6h0", [trial(0, ablation={}),
                                     trial(1, control="writer_scoped")])
    write(tmp_path, "kinh_forget_scope", "n6h0", [
        trial(0, ablation={"forget_scope": "writer"}),
        trial(1, control="writer_scoped")])
    write(tmp_path, "kinh_barrier", "n6conc",
          [dict(trial(0, ablation={"barrier": "off"}), failed=True)])
    held = {(r["switch"], r["condition"]): (r["held"], r["wrong_record"])
            for r in report.record_checks(report.load(tmp_path))}
    assert held == {("full", "n6h0"): (False, [1]),
                    ("forget_scope", "n6h0"): (True, []),
                    ("barrier", "n6conc"): (False, [])}


def test_the_quota_smoke_checks_flood_rows_and_profile_facts(tmp_path):
    for phase, flood, facts in (("kinh", 1, 0.9), ("kinh_quota", 6, 0.4)):
        for level in ("n6flood10", "n6flood50"):
            write(tmp_path, phase, level, [
                trial(i, stress={"probes": {"p": {
                    "flood_rows_in_block": flood + i}}},
                    judge_free={"profile_facts_in_block": facts - i / 10})
                for i in range(3)])
    checks = report.smoke_checks(report.rows(report.load(tmp_path)))
    assert sorted((c["condition"], c["measure"]) for c in checks) == [
        ("n6flood10", "flood rows in the block per probe"),
        ("n6flood10", "profile facts in the block"),
        ("n6flood50", "flood rows in the block per probe"),
        ("n6flood50", "profile facts in the block")]
    assert all(c["held"] for c in checks)


def test_the_deletion_outcome_is_split_by_echo_user(tmp_path):
    write(tmp_path, "kinh", "n6h0", [trial(i) for i in range(5)])
    write(tmp_path, "kinh_forget_scope", "n6h0", [
        trial(i, probes=[probe("deletion", passed=i not in (0, 4))])
        for i in range(5)])
    rows = {r["measure"]: r for r in report.rows(report.load(tmp_path))}
    echo = rows["deletion failed, echo users"]
    other = rows["deletion failed, other users"]
    assert (echo["n"], echo["full"], echo["ablated"]) == (2, 0.0, 1.0)
    assert (other["n"], other["ablated"]) == (3, 0.0)



# Each rule at the edge the recorded runs do not reach (ABLATION.md,
# "Functional check"): (switch, cells as (phase, condition, trials), held).
EDGES = [
    # One covered late write is enough.
    ("barrier", [("kinh", "n6conc", [trial(0, stress=late(0))]),
                 ("kinh_barrier", "n6conc", [trial(0, stress=late(1))])],
     True),
    # Misfiled rows without a cross-user row in a block do not hold.
    ("identity", [("kinh", "n6wrong_user", [trial(0)]),
                  ("kinh_identity", "n6wrong_user",
                   [trial(0, stress={"misfiled_rows": 2})])], False),
    # A privacy failure without its value in the block (the answer
    # alone) is not the switch's.
    ("visibility", [("kinh", "n6v3", [trial(0)]),
                    ("kinh_visibility", "n6v3", [trial(0, probes=[
                        probe("privacy", passed=False,
                              forbidden_in_block=False)])])], False),
    # An echo user failing deletion with no carrier left does not hold.
    ("forget_scope", [("kinh_forget_scope", "n6h0", [
        trial(i, probes=[probe("deletion", passed=i not in (0, 4))])
        for i in range(5)])], False),
    # A quota that still rejects is not off.
    ("quota", [("kinh", "n6flood10", [trial(0, stress={
                    "probes": {"p": {"flood_rows_in_block": 1}},
                    "quota_rejected": {"flood": 9}})]),
               ("kinh_quota", "n6flood10", [trial(0, stress={
                   "probes": {"p": {"flood_rows_in_block": 6}},
                   "quota_rejected": {"flood": 1}})])], False),
]


@pytest.mark.parametrize("switch, cells, held", EDGES,
                         ids=[e[0] for e in EDGES])
def test_each_functional_rule_at_its_edge(tmp_path, switch, cells, held):
    for phase, condition, trials in cells:
        write(tmp_path, phase, condition, trials)
    (check,) = [c for c in report.functional_checks(report.load(tmp_path))
                if c["switch"] == switch]
    assert check["held"] is held, check


def test_a_mem0_kernel_phase_is_the_mem0_backend(tmp_path):
    write(tmp_path, "kmem0", "n6conc", [trial(0)])
    write(tmp_path, "kmem0_barrier", "n6conc", [trial(0)])
    assert set(report.load(tmp_path)) == {
        ("qwen", "mem0", None, "n6conc", "kernel_shared"),
        ("qwen", "mem0", "barrier", "n6conc", "kernel_shared"),
    }


def test_after_threshold_and_after_cap_are_read_apart():
    """Once the cap binds (V4's k of 5 over 8 candidates) the two
    differ."""
    t = {"probe_results": [{"diagnostics": {"after_threshold": 8,
                                            "after_cap": 5}}]}
    assert (report.after_threshold(t), report.after_cap(t)) == (8, 5)

# -- the recorded runs ---------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ablation_runs"
RESULTS = Path(__file__).resolve().parents[2] / "results"


def same(a, b) -> bool:
    """``a`` equals ``b``, floats to a relative 1e-9: the JSON keeps
    every digit of an interval, and the last ones move with numpy's and
    scipy's versions (the Markdown and the figure print them rounded)."""
    if isinstance(a, float) or isinstance(b, float):
        return (isinstance(a, (int, float)) and isinstance(b, (int, float))
                and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(map(same, a, b))
    return a == b


@pytest.mark.parametrize("run", ["ablation_functional_f19b",
                                 "ablation_smoke_s19"])
def test_the_report_reproduces_the_recorded_analyses(tmp_path, run):
    """The functional check's and the smoke's records, trimmed to the
    fields the report reads (``fixtures/ablation_runs/make_fixtures.py``),
    give the table, the JSON and the figure committed with each run:
    every reported number, interval and verdict."""
    with tarfile.open(FIXTURES / f"{run}.tar.xz") as archive:
        archive.extractall(tmp_path, **(
            {"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    out = tmp_path / "out"
    out.mkdir()
    report.main([str(tmp_path / run), "--md", str(out / "analysis.md"),
                 "--json", str(out / "analysis.json"),
                 "--svg", str(out / "contribution.svg")])
    for name in ("analysis.md", "contribution.svg"):
        assert (out / name).read_text() == (RESULTS / run / name).read_text(), \
            name
    assert same(json.loads((out / "analysis.json").read_text()),
                json.loads((RESULTS / run / "analysis.json").read_text()))
