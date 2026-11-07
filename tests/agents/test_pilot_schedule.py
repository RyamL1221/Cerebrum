"""Subtask 11: the balanced pilot_v1 heterogeneity schedule (AIOS
docs/PILOT.md) and the orchestrator's ``--schedule``."""
from collections import Counter
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.shared_memory import pilot_schedule as ps
from benchmarks.shared_memory import run_evaluation
from cerebrum.example.agents.variants import (
    CONSUMER,
    VARIANT_CODES,
    WRITERS,
)
from tests.agents.test_heterogeneity import TRIAL, Recorder


@pytest.fixture(scope="module")
def committed():
    return ps.Schedule(str(ps.PATH))


def test_the_committed_file_is_the_generator_output():
    assert ps.PATH.read_text() == ps.dumps(ps.generate())


def test_shape(committed):
    levels = committed.data["levels"]
    assert committed.dataset == "pilot_v1"
    assert [len(levels[h]) for h in "012"] == [30, 30, 30]
    for h in (0, 1, 2):
        for i in range(30):
            deviating = committed.variants(h, i)
            assert len(deviating) == h  # H agents, one variant each
            assert set(deviating) <= set(WRITERS + (CONSUMER,))
            assert set(deviating.values()) <= set(VARIANT_CODES)


def test_h1_balances_every_variant_and_role(committed):
    pairs = Counter()
    for i in range(30):
        ((agent, code),) = committed.variants(1, i).items()
        pairs[("consumer" if agent == CONSUMER else "writer", code)] += 1
    assert set(pairs.values()) == {3} and len(pairs) == 10


def test_h2_strata_and_slots_are_balanced(committed):
    rows = [committed.variants(2, i) for i in range(30)]
    strata = Counter(committed.stratum(2, i) for i in range(30))
    assert strata == {"writer_only": 15, "one_of_each": 15}
    writer_only = [r for r in rows if CONSUMER not in r]
    mixed = [r for r in rows if CONSUMER in r]
    for agent in WRITERS:
        assert set(Counter(r[agent] for r in writer_only).values()) == {3}
    assert set(Counter(r[CONSUMER] for r in mixed).values()) == {3}
    mixed_writers = Counter(
        code for r in mixed for a, code in r.items() if a != CONSUMER
    )
    assert set(mixed_writers.values()) == {3}


def test_v5_writers_are_isolated_from_blanking_consumers(committed):
    rows = [committed.variants(2, i) for i in range(30)]
    v5 = [r for r in rows
          if any(a in WRITERS and c == "V5" for a, c in r.items())]
    blanked = [r for r in v5 if r.get(CONSUMER) in ps.BLANKING_CONSUMERS]
    assert blanked == [] and len(v5) - len(blanked) >= 6


def test_every_v3_consumer_has_a_private_writer(committed):
    rows = [committed.variants(2, i) for i in range(30)]
    v3 = [r for r in rows if r.get(CONSUMER) == "V3"]
    assert len(v3) == 3
    for row in v3:
        writer = [c for a, c in row.items() if a != CONSUMER]
        assert writer[0] in ps.PRIVATE_WRITERS


def orchestrator(level, method, judge=True, schedule=str(ps.PATH),
                 dataset="pilot_v1"):
    data = MagicMock()
    data.name = dataset
    data.__len__.return_value = 30
    with patch.object(run_evaluation, "load_dataset", return_value=data):
        return run_evaluation.EvaluationOrchestrator(
            trials=30, output_dir="/tmp", write_csv=False, condition=None,
            method=method, heterogeneity=level, judge=judge,
            schedule=schedule,
        )


def test_every_cell_gets_the_files_variants(committed):
    seen = {}
    for method in ("kernel_shared", "replicated_mem0", "native_inhouse"):
        runner = orchestrator(2, method)
        recorder = Recorder()
        for i in range(30):
            runner.run_single_trial(i, method, recorder, method=method,
                                    trial_data=TRIAL)
        seen[method] = recorder.seen
    expected = [committed.variants(2, i) for i in range(30)]
    assert seen["kernel_shared"] == seen["replicated_mem0"] \
        == seen["native_inhouse"] == expected
    meta = runner._heterogeneity_metadata()
    assert meta["schedule"] == "pilot_v1_schedule"
    assert meta["schedule_sha256"] == committed.sha256


def test_a_scored_heterogeneity_run_needs_the_schedule():
    with pytest.raises(ValueError, match="--schedule"):
        orchestrator(1, "kernel_shared", schedule=None)
    orchestrator(1, "kernel_shared")  # scored, with the schedule


def test_the_schedule_must_name_the_dataset():
    with pytest.raises(ValueError, match="pilot_v1"):
        orchestrator(1, "kernel_shared", dataset="users_v1")
