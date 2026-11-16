"""The stress dimensions' report (``stress_report``; NeurIPS Subtask 18):
trials paired with their reference by user, the across-N identity at
H = 0, cross-user rows from the injected rows' provenance, and the
concurrency and fault tables' counts, on hand-made trials."""
import json

from benchmarks.shared_memory import stress_report as report

KINDS = report.JUDGE_FREE + ("integration",)


def trial(index, passed=None, block="B", user="u", injected=(),
          stress=None, judge_free=None, failed=False):
    passed = passed or {}
    return {
        "trial_index": index, "user_id": f"{user}{index}", "failed": failed,
        "probe_results": [
            {"type": kind, "passed": passed.get(kind, True),
             "diagnostics": {"block_text": block,
                             "injected_memories": list(injected)}}
            for kind in KINDS],
        "stress": stress or {}, "judge_free": judge_free or {},
    }


def test_paired_outcomes_count_lost_and_gained_users():
    reference = [trial(0), trial(1), trial(2, {"recall": False})]
    here = [trial(0, {"recall": False}), trial(1), trial(2)]
    paired = report.paired_outcomes(here, reference, "recall")
    assert (paired["lost"], paired["gained"], paired["same"]) == (1, 1, 1)
    # A failed trial is left out of the pairing.
    here[1]["failed"] = True
    assert report.paired_outcomes(here, reference, "recall")["same"] == 0


def test_cross_user_rows_are_rows_written_for_another_user():
    t = trial(0, injected=[{"provenance_user": "u0"},
                           {"provenance_user": "u7"},
                           {"provenance_user": None}])
    assert report.cross_user_rows(t) == len(KINDS)  # one per probe


def test_the_across_n_identity_compares_outcomes_and_blocks():
    cells = {
        ("qwen", "kernel", "inhouse", "n3h0"): [trial(0), trial(1)],
        ("qwen", "kernel", "inhouse", "n6h0"): [trial(0), trial(1)],
        ("qwen", "kernel", "inhouse", "n12h0"): [
            trial(0), trial(1, {"recency": False}, block="C")],
    }
    (row,) = report.agent_count_rows(cells)
    assert row["users"] == 2 and row["probes"] == 2 * len(KINDS)
    assert row["same_outcomes"] == 2 * len(KINDS) - 1
    assert row["same_blocks"] == len(KINDS)


def test_the_concurrency_and_fault_tables_count_their_measures():
    probe = {"writes_in_flight": ["e1"], "late_writes": ["e1"],
             "late_covered": ["e1"],
             "late_rows": 1, "uncovered_writes": [], "timing_miss": True,
             "stale_read": False, "late_forget": None,
             "barrier_wait_ms": 5.0, "flood_rows_in_block": 2}
    stressed = {"probes": {"p1": probe}, "barrier_timeouts": 0,
                "memories_missing_timing": ["w"], "misfiled_rows": 3,
                "identity_overridden_requests": 0,
                "flood_rows_stored": 4, "quota_rejected": {"quota": 2},
                "flood_writes_accepted": 3, "flood_sessions_over_bound": 1}
    cells = {
        ("qwen", "replicated", "inhouse", "n6h0"): [trial(0)],
        ("qwen", "replicated", "inhouse", "n6conc"): [
            trial(0, {"recency": False}, stress=stressed)],
        ("qwen", "replicated", "inhouse", "n6flood10"): [
            trial(0, stress=stressed,
                  judge_free={"profile_facts_in_block": 0.5})],
    }
    (conc,) = report.concurrency_rows(cells)
    assert (conc["with_late_writes"], conc["late_covered"],
            conc["timing_misses"], conc["memories_missing_timing"]) \
        == (1, 1, 1, 1)
    assert conc["recency"]["lost"] == 1
    (flood,) = report.fault_rows(cells)
    assert (flood["misfiled_rows"], flood["flood_rows_stored"],
            flood["flood_rows_in_block_per_probe"]) == (3, 4, 2)
    assert flood["quota_rejected"] == {"quota": 2}
    assert (flood["flood_writes_accepted"],
            flood["flood_sessions_over_bound"]) == (3, 1)


def test_the_report_reads_a_run_tree(tmp_path):
    for phase, cell, method in (("kinh", "n6h0", "kernel_shared"),
                                ("agent", "n6conc", "native_inhouse")):
        path = tmp_path / "qwen" / phase / f"{cell}_{method}"
        path.mkdir(parents=True)
        (path / f"results_{method}.json").write_text(json.dumps(
            {"conditions": [{"trials": [trial(0)]}]}))
    cells = report.load(tmp_path)
    assert set(cells) == {("qwen", "kernel", "inhouse", "n6h0"),
                          ("qwen", "native", "inhouse", "n6conc")}
    assert "## Concurrency" in report.markdown(report.report(tmp_path))
