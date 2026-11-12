"""Subtask 16: the pilot_v1 smoke's analysis on Graphiti
(``graphiti_smoke``), on synthetic cells with known answers."""
import csv
import json

from benchmarks.shared_memory import graphiti_smoke as gs
from benchmarks.shared_memory import pilot_analysis as pa
from benchmarks.shared_memory.pilot_schedule import PATH, Schedule

SCHEDULE = Schedule(str(PATH))


def write_cells(root, scores, skip=()):
    """``scores(locus, H, i) -> (profile, integration)``; the loci in
    ``skip`` get no cell."""
    for locus in gs.CELLS:
        if locus in skip:
            continue
        for level in gs.LEVELS:
            trials = []
            for i in range(pa.USERS):
                p, g = scores(locus, level, i)
                trials.append({
                    "trial_index": i, "failed": False,
                    "profile_usage_score": p, "task_usage_score": 3.0,
                    "integration_score": g, "input_sha256": f"u{i}",
                    "variants_applied": SCHEDULE.variants(level, i),
                    "judge_free": {"cross_user_rows": 0,
                                   "private_rows_from_others": 0,
                                   "memories_missing": 0,
                                   "profile_facts_in_block": 1.0},
                    "backend_llm_tokens": {"calls": 4, "prompt_tokens": 1000,
                                           "completion_tokens": 100,
                                           "total_tokens": 1100,
                                           "models": ["azure/gpt-4o"]},
                })
            path = gs.cell_file(root, "qwen", locus, level)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "experiment_metadata": {
                    "git_commit": "c1", "kernel_git_commit": "k1",
                    "heterogeneity": {"schedule_sha256": SCHEDULE.sha256}},
                "conditions": [{"trials": trials}]}))


def reference(tmp_path, sign=1.0):
    path = tmp_path / "gaps.csv"
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "model", "vs", "scope", "dimension", "contrast", "n", "mean",
            "ci_low", "ci_high"])
        writer.writeheader()
        for vs in gs.OTHERS:
            for scope in ("pooled", "mem0", "inhouse"):
                for dimension in pa.DIMENSIONS:
                    writer.writerow({"model": "qwen", "vs": vs,
                                     "scope": scope, "dimension": dimension,
                                     "contrast": "H2", "n": 30,
                                     "mean": sign * 0.7, "ci_low": 0.2,
                                     "ci_high": 1.2})
    return str(path)


def grows(locus, level, i):
    """A tie at H = 0; at H = 2 the kernel is one point above the agent
    loci (with spread over users, so the intervals are not points)."""
    base = 4.0 + (i % 3) * 0.3
    if locus == "kernel" or level == 0:
        return base, base
    return base - 1.0, base - 1.0


def test_the_graphiti_cells_are_read_and_paired(tmp_path):
    write_cells(tmp_path, grows)
    cells, meta = gs.load(tmp_path)
    assert set(cells) == {("qwen", locus, "graphiti", level)
                          for locus in gs.CELLS for level in gs.LEVELS}
    assert pa.check_pairing(cells, meta, SCHEDULE) == []
    gaps = {(r["vs"], r["dimension"], r["contrast"]): r
            for r in gs.gap_rows(cells)}
    assert gaps[("replicated", "profile", "H0")]["mean"] == 0
    assert gaps[("native", "integration", "H2")]["mean"] == 1.0
    assert gaps[("replicated", "profile", "H2-H0")]["mean"] == 1.0
    assert gaps[("native", "profile", "H2")]["n"] == pa.USERS


def test_the_tie_and_the_direction_are_read_against_the_pilot(tmp_path):
    write_cells(tmp_path, grows)
    cells, _ = gs.load(tmp_path)
    gaps = gs.gap_rows(cells)
    reads = gs.readings(gaps, gs.read_reference(reference(tmp_path)))
    assert len(reads) == len(gs.OTHERS) * len(pa.PRIMARY)
    assert all(r["h0_tie"] and r["h2_sign"] == 1 and r["same_direction"]
               for r in reads)
    assert set(reads[0]["pilot_h2"]) == {"pooled", "mem0", "inhouse"}
    against = gs.readings(gaps, gs.read_reference(
        reference(tmp_path, sign=-1.0)))
    assert not any(r["same_direction"] for r in against)
    assert all(r["same_direction"] is None for r in gs.readings(gaps))


def test_a_gap_at_h0_is_no_tie(tmp_path):
    def apart(locus, level, i):
        base = 4.0 + (i % 3) * 0.3
        return (base, base) if locus == "kernel" else (base - 1, base - 1)
    write_cells(tmp_path, apart)
    cells, _ = gs.load(tmp_path)
    assert not any(r["h0_tie"] for r in gs.readings(gs.gap_rows(cells)))


def test_main_reports_a_missing_cell_and_writes_its_files(tmp_path):
    root = tmp_path / "root"
    write_cells(root, grows, skip=("native",))
    out = tmp_path / "out"
    out.mkdir()
    assert gs.main([str(root), "--reference", reference(tmp_path),
                    "--markdown", str(out / "analysis.md"),
                    "--json", str(out / "analysis.json"),
                    "--csv-dir", str(out)]) == 0
    data = json.loads((out / "analysis.json").read_text())
    assert data["problems"][0] == "4 of 6 cells present"
    cost = {(r["locus"], r["level"]): r for r in data["cost"]}
    assert cost[("kernel", 0)]["backend_calls"] == 4
    assert cost[("kernel", 0)]["backend_usd"] == (1000 * 2.5
                                                  + 100 * 10) / 1e6
    text = (out / "analysis.md").read_text()
    assert "### qwen: kernel − replicated" in text
    assert {p.name for p in out.iterdir()} >= {"cells.csv", "cost.csv",
                                               "gaps.csv"}


def test_agent_cells_report_their_v2_trials(tmp_path):
    """An agent cell recorded before Subtask 16's fix undercounts its V2
    trials' backend calls, so the cost table names how many it has; the
    kernel counts them."""
    write_cells(tmp_path, grows)
    cells, _ = gs.load(tmp_path)
    rows = {(r["locus"], r["level"]): r
            for r in gs.cost_rows(cells, gs.load_prices())}
    expected = sum(1 for i in range(pa.USERS)
                   if "V2" in SCHEDULE.variants(2, i).values())
    assert expected > 0
    assert rows[("replicated", 2)]["v2_trials"] == expected
    assert rows[("native", 2)]["v2_trials"] == expected
    assert rows[("replicated", 0)]["v2_trials"] == 0
    assert rows[("kernel", 2)]["v2_trials"] is None


def pilot_gaps(tmp_path, means):
    """A pilot ``gaps.csv`` with one H = 2 mean per (model, vs) in
    ``means``, the same in every scope and dimension."""
    path = tmp_path / "pilot_gaps.csv"
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "model", "vs", "scope", "dimension", "contrast", "n", "mean",
            "ci_low", "ci_high"])
        writer.writeheader()
        for (model, vs), mean in means.items():
            for scope in ("pooled", "mem0", "inhouse"):
                for dimension in pa.DIMENSIONS:
                    writer.writerow({"model": model, "vs": vs,
                                     "scope": scope, "dimension": dimension,
                                     "contrast": "H2", "n": 30,
                                     "mean": mean, "ci_low": mean - 0.5,
                                     "ci_high": mean + 0.5})
    return str(path)


def test_the_cells_are_read_where_the_driver_writes_them(tmp_path):
    """The smoke reads its cells at the paths AIOS
    ``scripts/run_pilot_v1_graphiti.sh`` writes (``cell_path``,
    ``<model>/<phase>/h<H>_<method>``): the kernel in phase ``kgra``,
    replicated and native in phase ``agent_gra``."""
    paths = {locus: str(gs.cell_file(tmp_path, "qwen", locus, 2)
                        .relative_to(tmp_path)) for locus in gs.CELLS}
    assert paths == {
        "kernel": "qwen/kgra/h2_kernel_shared/results_kernel_shared.json",
        "replicated": "qwen/agent_gra/h2_replicated_graphiti/"
                      "results_replicated_graphiti.json",
        "native": "qwen/agent_gra/h2_native_graphiti/"
                  "results_native_graphiti.json"}


def test_the_cost_table_gives_latency_in_seconds(tmp_path):
    """``latency_s`` is the cells' mean trial latency in seconds, from
    the trials' ``latency_seconds`` (GRAPHITI_BACKEND.md, "Measured in
    the smokes", gives latency per user in seconds)."""
    write_cells(tmp_path, grows)
    cells, _ = gs.load(tmp_path)
    for trials in cells.values():
        for index, found in trials.items():
            found["latency_seconds"] = 20.0 + index % 2
    rows = gs.cost_rows(cells, gs.load_prices())
    assert [r["latency_s"] for r in rows] == [20.5] * len(cells)


def test_the_direction_is_read_against_the_same_model_and_contrast(
        tmp_path):
    """A reading compares the H = 2 mean with the pilot's H = 2 means for
    the same model and the same contrast (kernel - replicated or kernel -
    native) in every scope (PILOT.md; the readings' note). The pilot's
    other contrast and other model, with other signs, do not count."""
    write_cells(tmp_path, grows)
    cells, _ = gs.load(tmp_path)
    reference = pilot_gaps(tmp_path, {
        ("qwen", "replicated"): 0.7, ("qwen", "native"): -0.4,
        ("gpt4o", "replicated"): -0.9, ("gpt4o", "native"): -0.9})
    reads = {(r["vs"], r["dimension"]): r for r in gs.readings(
        gs.gap_rows(cells), gs.read_reference(reference))}
    for dimension in pa.PRIMARY:
        replicated = reads[("replicated", dimension)]
        assert replicated["pilot_h2"] == dict.fromkeys(
            ("pooled", "mem0", "inhouse"), 0.7)
        assert replicated["same_direction"] is True
        native = reads[("native", dimension)]
        assert native["pilot_h2"] == dict.fromkeys(
            ("pooled", "mem0", "inhouse"), -0.4)
        assert native["same_direction"] is False


def test_the_gap_tables_give_h0_h2_and_their_difference(tmp_path):
    """Each gap table's row gives H0, H2 and H2−H0 under the header of
    each (the analysis.md tables DEV_STATUS.md, Subtask 16, reports)."""
    def widens(locus, level, i):
        base = 4.0 + (i % 3) * 0.3
        if locus == "kernel":
            return base, base
        apart = 0.5 if level == 0 else 1.5
        return base - apart, base - apart
    write_cells(tmp_path, widens)
    cells, _ = gs.load(tmp_path)
    prices = gs.load_prices()
    text = gs.markdown([], pa.cell_rows(cells, prices),
                       gs.cost_rows(cells, prices), gs.gap_rows(cells), [])
    assert text.count("| dimension | H0 | H2 | H2−H0 |") == 2
    assert text.count("| profile | +0.50 [+0.50, +0.50] | "
                      "+1.50 [+1.50, +1.50] | +1.00 [+1.00, +1.00] |") == 2
