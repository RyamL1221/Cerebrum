"""The harness, analysis and reports on A-MEM's cells (NeurIPS Subtask
17, AIOS docs/AMEM_BACKEND.md): the conditions and their dispatch,
Amendment 7 (an A-MEM write that stored no note is a lost memory), the
analysis's kamem phases, its ``derived`` forget reason and its
writes-without-a-row reading, the pilot report's ``--backend amem``,
and the heterogeneity report's cells."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import bench_v2_analysis as ba
from benchmarks.shared_memory import conditions
from benchmarks.shared_memory import graphiti_smoke as gs
from benchmarks.shared_memory import heterogeneity_report as hr
from benchmarks.shared_memory import pipeline as pl
from benchmarks.shared_memory.models import EMPTY_WRITE_IS_LOSS


def test_the_amem_conditions_are_agent_managed():
    assert "native_amem" in conditions.NATIVE_CONDITIONS
    assert "replicated_amem" in conditions.REPLICATED_CONDITIONS
    assert {"native_amem", "replicated_amem"} <= set(pl.MethodPipeline
                                                     .V2_METHODS)


@pytest.mark.parametrize("method,runner", [
    ("native_amem", "_run_native"), ("replicated_amem", "_run_replicated")])
def test_a_v1_amem_trial_runs_on_amem(method, runner):
    """v1 dispatches each A-MEM method to its locus on the ``amem``
    backend (a Mem0 or Graphiti backend would change every number)."""
    with patch.object(pl.MethodPipeline, runner,
                      return_value="ran") as run:
        result = pl.MethodPipeline(method=method).run_trial(
            SimpleNamespace(user_id="u"))
    assert result == "ran"
    assert run.call_args.args[1:] == (f"u__{method}", "amem")


def test_an_amem_write_that_stored_no_note_is_a_lost_memory():
    """Amendment 7: as on Graphiti (Amendment 5), not Mem0."""
    assert "amem" in EMPTY_WRITE_IS_LOSS
    assert "mem0" not in EMPTY_WRITE_IS_LOSS


def write(root, phase, cell, method, trials):
    path = root / "qwen" / phase / cell / f"results_{method}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"experiment_metadata": {},
                                "conditions": [{"trials": trials}]}))


def test_the_analysis_reads_the_amem_phases(tmp_path):
    for phase, cell, method in (
            ("kamem", "h0_kernel_shared", "kernel_shared"),
            ("kamem_ns", "no_supersession_kernel_shared", "kernel_shared"),
            ("agent_amem", "h0_replicated_amem", "replicated_amem"),
            ("agent_amem", "h0_native_amem", "native_amem")):
        write(tmp_path, phase, cell, method, [])
    assert set(ba.load(tmp_path)) == {
        ("qwen", "kernel", "amem", "h0"),
        ("qwen", "kernel", "amem", "no_supersession"),
        ("qwen", "replicated", "amem", "h0"),
        ("qwen", "native", "amem", "h0")}


def test_a_derived_deletion_is_counted_apart(tmp_path):
    """A row an A-MEM scrub deleted because its derived text carried a
    form counts as ``derived``, not as a fold of the revoking writer's."""
    revoke = {"type": "revoke", "writer": "profile_agent",
              "revoke_path": "forget", "forget": {
                  "values_count": 1, "scrubbed": {"messages": 0,
                                                  "history": 1},
                  "deleted": [
                      {"memory_id": "a", "owner_agent": "profile_agent",
                       "reason": "fact_key"},
                      {"memory_id": "b", "owner_agent": "profile_agent",
                       "reason": "derived"}]}}
    trial = {"trial_index": 0, "failed": False,
             "sessions": [{"events": [revoke]}], "probe_results": []}
    write(tmp_path, "kamem", "h0_kernel_shared", "kernel_shared", [trial])
    (row,) = ba.forget_rows(ba.load(tmp_path))
    assert (row["deleted"], row["fact_key"], row["derived"],
            row["same_writer"], row["history"]) == (2, 1, 1, 0, 1)


def test_amem_cells_have_a_writes_without_a_row_reading(tmp_path):
    trial = {"trial_index": 0, "failed": False, "probe_results": [],
             "writes_without_fact": ["u0-e01"]}
    write(tmp_path, "agent_amem", "h0_native_amem", "native_amem", [trial])
    write(tmp_path, "kmem0", "h0_kernel_shared", "kernel_shared", [trial])
    rows = ba.writes_without_fact_rows(ba.load(tmp_path))
    assert [(r["backend"], r["writes_without_fact"]) for r in rows] == [
        ("amem", 1)]


def test_the_pilot_report_reads_the_amem_cells(tmp_path):
    assert gs.cells_for("amem") == {
        "kernel": ("kamem", "kernel_shared"),
        "replicated": ("agent_amem", "replicated_amem"),
        "native": ("agent_amem", "native_amem")}
    path = gs.cell_file(tmp_path, "qwen", "native", 2, "amem")
    assert path == (tmp_path / "qwen" / "agent_amem" / "h2_native_amem"
                    / "results_native_amem.json")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"experiment_metadata": {"x": 1},
                                "conditions": [{"trials": [
                                    {"trial_index": 0}]}]}))
    cells, metadata = gs.load(tmp_path, "amem")
    assert list(cells) == [("qwen", "native", "amem", 2)]
    rows = gs.gap_rows(cells, "amem")
    assert {r["scope"] for r in rows} == {"amem"}


def test_the_heterogeneity_report_names_the_amem_cells():
    assert hr.cell_of({}, "replicated_amem") == ("replicated", "amem")
    assert hr.cell_of({}, "native_amem") == ("native", "amem")
    assert hr.cell_of({"config_snapshot": {"provider": "amem"}},
                      "kernel_shared") == ("kernel", "amem")
