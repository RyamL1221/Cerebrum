"""Tests for the kernel_private rename and its deprecated alias."""

import json
import logging

from benchmarks.shared_memory import revalidate
from benchmarks.shared_memory.conditions import (
    CONDITION_ALIASES,
    CONDITIONS,
    canonical_condition,
    results_path,
)
from benchmarks.shared_memory.pipeline import MethodPipeline
from benchmarks.shared_memory.run_evaluation import build_arg_parser

OLD = next(iter(CONDITION_ALIASES))


def test_alias_maps_to_kernel_private_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        assert canonical_condition(OLD) == "kernel_private"
    assert "deprecated" in caplog.text
    assert OLD not in CONDITIONS


def test_current_names_pass_through_silently(caplog):
    with caplog.at_level(logging.WARNING):
        for name in CONDITIONS:
            assert canonical_condition(name) == name
    assert caplog.text == ""


def test_cli_accepts_old_and_new_names():
    parser = build_arg_parser()
    assert parser.parse_args(["--method", OLD]).method == "kernel_private"
    assert parser.parse_args(
        ["--method", "kernel_private"]
    ).method == "kernel_private"


def test_pipeline_resolves_the_alias():
    assert MethodPipeline(method=OLD).method == "kernel_private"


def write_cell(directory, model, name, trials):
    cell = directory / f"{model}_{name}"
    cell.mkdir(parents=True)
    path = cell / f"results_{name}.json"
    path.write_text(json.dumps({"conditions": [{"trials": trials}]}))
    return path


def test_results_path_reads_an_old_directory(tmp_path):
    old = write_cell(tmp_path, "qwen", OLD, [])
    assert results_path(tmp_path, "qwen", "kernel_private") == old
    assert results_path(tmp_path, "qwen", OLD) == old


def test_results_path_prefers_the_current_name(tmp_path):
    write_cell(tmp_path, "qwen", OLD, [])
    new = write_cell(tmp_path, "qwen", "kernel_private", [])
    assert results_path(tmp_path, "qwen", "kernel_private") == new


def test_revalidate_loads_old_results_under_the_new_name(tmp_path):
    write_cell(tmp_path, "llama", OLD, [{"trial_index": 7}])
    assert "kernel_private" in revalidate.METHODS
    trials = revalidate.load_trials(tmp_path, "llama", "kernel_private")
    assert trials == [{"trial_index": 7}]
