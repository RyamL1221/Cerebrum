"""The stress dimensions' report (``stress_report``; NeurIPS Subtask 18):
trials paired with their reference by user, the across-N identity at
H = 0, cross-user rows from the injected rows' provenance, and the
concurrency and fault tables' counts, on hand-made trials."""
import json

import pytest

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
    # Outcomes of the judge-free probes only; every probe's block.
    assert row["users"] == 2
    assert row["outcomes"] == 2 * len(report.JUDGE_FREE)
    assert row["same_outcomes"] == 2 * len(report.JUDGE_FREE) - 1
    assert (row["blocks"], row["same_blocks"]) == (2 * len(KINDS),
                                                   len(KINDS))


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
        ("qwen", "replicated", "inhouse", "n6h0"): [
            trial(0, judge_free={"memories_missing": 1})],
        ("qwen", "replicated", "inhouse", "n6conc"): [
            trial(0, {"recency": False}, stress=stressed,
                  judge_free={"memories_missing": 3})],
        ("qwen", "replicated", "inhouse", "n6flood10"): [
            trial(0, stress=stressed,
                  judge_free={"profile_facts_in_block": 0.5})],
    }
    (conc,) = report.concurrency_rows(cells)
    assert (conc["with_late_writes"], conc["late_covered"],
            conc["timing_misses"], conc["memories_missing_timing"]) \
        == (1, 1, 1, 1)
    assert conc["recency"]["lost"] == 1
    assert conc["memories_missing"]["mean"] == 2  # paired: 3 - 1
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


def test_writes_without_row_are_writes_whose_reply_named_none():
    """A write whose reply named no row counts; a suppressed one, one
    the quota turned away, a revoke and a stored write do not."""
    t = trial(0)
    t["sessions"] = [{"writer": "w", "events": [
        {"event_id": "e1", "type": "add", "reported_ids": []},
        {"event_id": "e2", "type": "update", "reported_ids": [],
         "suppressed": True},
        {"event_id": "e3", "type": "add", "reported_ids": [],
         "quota_rejected": "quota"},
        {"event_id": "e4", "type": "revoke"},
        {"event_id": "e5", "type": "add", "reported_ids": ["m"]},
    ]}]
    assert report.writes_without_row(t) == ["e1"]
    cells = {("qwen", "kernel", "mem0", "n6h0"): [t]}
    (row,) = report.probe_rows(cells)
    assert row["writes_without_row"] == 1


def kernel_trial(index, *, stress=None, failed=False, error=None,
                 sessions=None, faulty=None):
    t = trial(index, stress=stress, failed=failed)
    t["error_message"] = error
    t["sessions"] = sessions or []
    t["faulty_agent"] = faulty
    return t


def checks_of(cells):
    return {row["check"]: row["holds"] for row in report.checks(cells)}


def test_the_checks_hold_and_each_fails_when_its_rule_breaks():
    conc = {"probes": {"p": {"late_covered": []}}, "barrier_timeouts": 0}
    faulty_sessions = [{"writer": "w", "events": [{}, {}],
                        "flood": [{}]}]
    wrong = {"misfiled_rows": 0, "identity_overridden_requests": 3}
    flood = {"flood_sessions_over_bound": 0,
             "quota_rejected_by_writer": {"w": 4}}
    good = {
        ("qwen", "kernel", "inhouse", "n6conc"): [
            kernel_trial(0, stress=conc)],
        ("qwen", "kernel", "inhouse", "n6wrong_user"): [
            kernel_trial(0, stress=wrong, sessions=faulty_sessions,
                         faulty="w")],
        ("qwen", "kernel", "inhouse", "n6flood10"): [
            kernel_trial(0, stress=flood, faulty="w")],
        ("qwen", "replicated", "mem0", "n12h0"): [
            kernel_trial(0, failed=True,
                         error="backend_extraction_failed: stored no rows")],
    }
    held = checks_of(good)
    assert held and all(held.values())

    def broken(key, **stress):
        cells = {k: [dict(t, stress=dict(t["stress"], **stress))
                     for t in v] for k, v in good.items()}
        return checks_of({**good, key: cells[key]})

    late = {"p": {"late_covered": ["e1"]}}
    assert not all(broken(("qwen", "kernel", "inhouse", "n6conc"),
                          probes=late).values())
    assert not all(broken(("qwen", "kernel", "inhouse", "n6conc"),
                          barrier_timeouts=1).values())
    assert not all(broken(("qwen", "kernel", "inhouse", "n6wrong_user"),
                          misfiled_rows=1).values())
    assert not all(broken(("qwen", "kernel", "inhouse", "n6wrong_user"),
                          identity_overridden_requests=2).values())
    assert not all(broken(("qwen", "kernel", "inhouse", "n6flood10"),
                          flood_sessions_over_bound=1).values())
    assert not all(broken(("qwen", "kernel", "inhouse", "n6flood10"),
                          quota_rejected_by_writer={"x": 1}).values())
    # A failed trial for any other reason fails the first check, and an
    # N = 12 one the N = 12 check.
    other = dict(good)
    other[("qwen", "replicated", "mem0", "n12h0")] = [
        kernel_trial(0, failed=True, error="writer_failed: boom")]
    held = checks_of(other)
    assert not held["every failed trial is a write the backend stored "
                    "nothing for"]
    assert not held["N = 12 runs end to end"]
    # A backend that made no LLM call is no write that stored nothing.
    other[("qwen", "replicated", "mem0", "n12h0")] = [kernel_trial(
        0, failed=True,
        error="backend_extraction_failed: no backend LLM calls recorded")]
    assert not checks_of(other)["every failed trial is a write the "
                                "backend stored nothing for"]


def agent_check(cells):
    (row,) = [r for r in report.checks(cells)
              if r["check"].startswith("in-house H = 0")]
    return row["holds"]


def test_the_in_house_agent_count_check_reads_outcomes_and_blocks():
    cells = {("qwen", "replicated", "inhouse", f"n{n}h0"): [trial(0)]
             for n in (3, 6, 12)}
    assert agent_check(cells) is True
    cells[("qwen", "replicated", "inhouse", "n12h0")] = [trial(0, block="C")]
    assert agent_check(cells) is False
    cells[("qwen", "replicated", "inhouse", "n12h0")] = [
        trial(0, {"recall": False})]
    assert agent_check(cells) is False
    # Native blocks need not be byte-equal; its outcomes must agree.
    native = {("qwen", "native", "inhouse", f"n{n}h0"):
              [trial(0, block=str(n))] for n in (3, 6, 12)}
    assert agent_check(native) is True
    native[("qwen", "native", "inhouse", "n6h0")] = [
        trial(0, {"recall": False})]
    assert agent_check(native) is False


def test_the_markdown_shows_both_agent_count_tables():
    cells = {("qwen", "kernel", "inhouse", c): [trial(0)]
             for c in ("n3h0", "n6h0", "n12h0", "n3h2")}
    cells[("qwen", "kernel", "inhouse", "n3h2")] = [
        trial(0, {"recall": False})]
    text = report.markdown(report.report_cells(cells))
    assert "## Agent count: H = 0 across N" in text
    h2 = text.split("## Agent count: H = 2 against H = 0")[1]
    assert "-1/+0" in h2.split("##")[0]
    assert "## Checks that must hold" in text


def test_a_pass_rate_prints_with_its_wilson_interval():
    rate = report._rate([True, True, True, False])
    assert report._fmt(rate) == (
        f"3/4 [{rate['ci'][0]:.2f}, {rate['ci'][1]:.2f}]")
    assert 0 < rate["ci"][0] < 0.75 < rate["ci"][1] <= 1
    assert report._fmt(report._rate([])) == "-"


def test_writes_without_row_count_the_failed_trials_too():
    """``probe_rows`` (DEV_STATUS.md, Subtask 18, "After the runs"): each
    write a backend stored nothing for is counted over every trial, the
    failed included: a Mem0 write that stored nothing fails its trial by
    the extraction check (BENCHMARK_V2.md, "Failures")."""
    failed = trial(0, failed=True)
    failed["sessions"] = [{"writer": "w", "events": [
        {"event_id": "e1", "type": "add", "reported_ids": []}]}]
    (row,) = report.probe_rows({("qwen", "native", "mem0", "n12h0"):
                                [failed, trial(1)]})
    assert (row["failed"], row["writes_without_row"]) == (1, 1)


def test_the_across_n_comparison_leaves_out_a_user_with_a_failed_trial():
    """``agent_count_rows`` (DEV_STATUS.md, Subtask 18, functional check:
    "the users with a failed trial left out"): only users with a passing
    trial at N = 3, 6 and 12 are compared."""
    cells = {("qwen", "native", "mem0", f"n{n}h0"): [trial(0), trial(1)]
             for n in (3, 6)}
    cells[("qwen", "native", "mem0", "n12h0")] = [trial(0),
                                                  trial(1, failed=True)]
    (row,) = [r for r in report.agent_count_rows(cells)
              if r["level"] == "H0 across N"]
    assert row["users"] == 1
    assert row["outcomes"] == row["same_outcomes"] == len(report.JUDGE_FREE)


def test_h2_is_paired_with_h0_at_the_same_n():
    """STRESS_DIMENSIONS.md, Agent count, "What is measured" (lines
    204-206): each probe type "paired against the same user at H = 0 and
    the same N"."""
    cells = {("qwen", "kernel", "inhouse", c): [trial(0)]
             for c in ("n6h0", "n12h0")}
    cells[("qwen", "kernel", "inhouse", "n3h0")] = [
        trial(0, {"recall": False})]
    cells[("qwen", "kernel", "inhouse", "n3h2")] = [
        trial(0, {"recall": False})]
    (row,) = [r for r in report.agent_count_rows(cells)
              if r["level"] == "N3 H2 vs H0"]
    assert (row["recall"]["lost"], row["recall"]["same"]) == (0, 1)


def concurrent_probe(**fields):
    return dict({"writes_in_flight": [], "late_writes": [],
                 "late_covered": [], "late_rows": 0, "uncovered_writes": [],
                 "barrier_wait_ms": 3.0}, **fields)


def test_the_concurrency_table_counts_the_passing_trials_probes():
    """STRESS_DIMENSIONS.md, Concurrency, "What is measured" (lines
    297-298): writes_in_flight are "writes issued before the probe that
    had not completed when it was issued", late or not; a failed user's
    probes are not scored (BENCHMARK_V2.md, "Failures")."""
    in_flight = concurrent_probe(writes_in_flight=["e1"])
    failed = concurrent_probe(writes_in_flight=["e2"], late_writes=["e2"],
                              late_covered=["e2"], late_rows=1)
    cells = {
        ("qwen", "replicated", "inhouse", "n6h0"): [trial(0), trial(1)],
        ("qwen", "replicated", "inhouse", "n6conc"): [
            trial(0, stress={"probes": {"p": in_flight}}),
            trial(1, failed=True, stress={"probes": {"p": failed}})],
    }
    (row,) = report.concurrency_rows(cells)
    assert (row["probes"], row["with_writes_in_flight"],
            row["with_late_writes"], row["late_writes"]) == (1, 1, 0, 0)


def load_trial(index, started, finished, probes):
    """A load-mode trial: its start and finish, and per probe
    ``(latency_seconds, llm_ms, completion_tokens)``."""
    t = trial(index, stress={
        "started_at": started, "finished_at": finished,
        "barrier_timeouts": 0,
        "probes": {f"p{k}": {"latency_seconds": latency, "llm_ms": ms,
                             "barrier_wait_ms": 1.0}
                   for k, (latency, ms, _) in enumerate(probes)}})
    t["probe_results"] = [
        {"type": "recall", "passed": True, "diagnostics": {},
         "token_usage": {"completion_tokens": tokens}}
        for _, _, tokens in probes]
    return t


def test_the_load_table_gives_throughput_latency_and_ms_per_token():
    """STRESS_DIMENSIONS.md, The load mode (lines 334-338): throughput
    in users per minute, each probe's latency (p50 and p95) and the
    stage times, and the cell's milliseconds per completion token."""
    cells = {("qwen", "kernel", "inhouse", "n6load4"): [
        load_trial(0, 0.0, 60.0, [(1, 100, 10), (2, 200, 10),
                                  (3, 300, 10)]),
        load_trial(1, 60.0, 120.0, [(4, 400, 10), (5, 500, 10)]),
    ]}
    (row,) = report.load_rows(cells)
    assert (row["load"], row["users"]) == (4, 2)
    assert row["users_per_minute"] == pytest.approx(1.0)  # 2 in 120 s
    assert row["latency_p50_s"] == pytest.approx(3.0)
    assert row["latency_p95_s"] == pytest.approx(4.8)
    assert row["llm_ms_p95"] == pytest.approx(480.0)
    assert row["ms_per_completion_token"] == pytest.approx(30.0)


def test_flood_rows_in_block_are_averaged_over_the_cells_probes():
    """STRESS_DIMENSIONS.md, flood10 and flood50, "Measured" (lines
    527-528): flood_rows_in_block per probe, reported as its mean over
    the cell's probes."""
    stressed = {"probes": {"p1": {"flood_rows_in_block": 1},
                           "p2": {"flood_rows_in_block": 3}}}
    cells = {
        ("qwen", "replicated", "inhouse", "n6h0"): [trial(0)],
        ("qwen", "replicated", "inhouse", "n6flood10"): [
            trial(0, stress=stressed)],
    }
    (row,) = report.fault_rows(cells)
    assert row["flood_rows_in_block_per_probe"] == 2


def test_the_checks_that_must_hold_read_kernel_cells_only():
    """STRESS_DIMENSIONS.md, the checks that must hold (lines 633-640):
    no covered late write, no misfiled row and the flood bound are the
    kernel's; the agent-managed loci are predicted to break them."""
    cells = {
        ("qwen", "replicated", "inhouse", "n6conc"): [kernel_trial(
            0, stress={"probes": {"p": {"late_covered": ["e1"]}},
                       "barrier_timeouts": 0})],
        ("qwen", "native", "inhouse", "n6wrong_user"): [kernel_trial(
            0, stress={"misfiled_rows": 4}, faulty="w")],
        ("qwen", "replicated", "inhouse", "n6flood10"): [kernel_trial(
            0, stress={"flood_sessions_over_bound": 2}, faulty="w")],
    }
    assert [row["check"] for row in report.checks(cells)] == [
        "every failed trial is a write the backend stored nothing for"]


def test_the_quota_phases_keep_their_backend(tmp_path):
    """STRESS_DIMENSIONS.md, Harness (lines 609-611): the report
    tabulates per locus and backend; the kernel's quota phases are
    ``kinh_q`` (in-house) and ``kmem0_q`` (Mem0)."""
    for phase in ("kinh", "kinh_q", "kmem0", "kmem0_q"):
        cell = "n6flood10" if phase.endswith("_q") else "n6h0"
        path = tmp_path / "qwen" / phase / f"{cell}_kernel_shared"
        path.mkdir(parents=True)
        (path / "results_kernel_shared.json").write_text(json.dumps(
            {"conditions": [{"trials": [trial(0)]}]}))
    assert set(report.load(tmp_path)) == {
        ("qwen", "kernel", backend, cell)
        for backend in ("inhouse", "mem0")
        for cell in ("n6h0", "n6flood10")}


def test_every_judge_free_probe_type_has_its_pass_rate():
    """BENCHMARK_V2.md, Scoring (lines 216-219): "Each probe type is
    reported separately, as a pass rate"; the judge-free ones are
    deletion, privacy, recall, recency and contradiction."""
    kinds = ("deletion", "privacy", "recall", "recency", "contradiction")
    t = {"trial_index": 0, "user_id": "u0", "failed": False,
         "stress": {}, "judge_free": {},
         "probe_results": [{"type": k, "passed": k != "privacy",
                            "diagnostics": {}}
                           for k in kinds + ("integration",)]}
    (row,) = report.probe_rows({("qwen", "kernel", "inhouse", "n6h0"): [t]})
    assert {k: (row[k]["k"], row[k]["n"]) for k in kinds} == {
        k: (int(k != "privacy"), 1) for k in kinds}


def test_the_across_n_check_is_in_house_only():
    """STRESS_DIMENSIONS.md, the checks that must hold (lines 630-632):
    "in-house at H = 0, every judge-free outcome is the same at N = 3, 6
    and 12"; on Mem0 small differences are predicted (lines 165-170)."""
    cells = {("qwen", "kernel", "mem0", f"n{n}h0"): [
        trial(0, {"recall": n != 12}, block=str(n))] for n in (3, 6, 12)}
    assert not [row for row in report.checks(cells)
                if row["check"].startswith("in-house")]
