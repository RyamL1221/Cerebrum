"""The benchmark v2 analysis (NeurIPS Subtask 14,
``bench_v2_analysis.py``) on synthetic results files with known answers:
the pass matrix, the echo split, binding counts, the functional check's
criteria and the paired kernel - replicated contrast."""
import json

import pytest
from scipy import stats

from benchmarks.shared_memory import bench_v2_analysis as ba
from benchmarks.shared_memory import probes as pr

TYPES = ("deletion", "privacy", "recall", "recency", "contradiction",
         "integration")


def probe(kind, passed, echo=False, cap=True, budget=False, **extra):
    return {"probe_id": f"p-{kind}", "type": kind, "passed": passed,
            "echo_event": "e8" if echo else None, "cap_bound": cap,
            "budget_bound": budget,
            "diagnostics": {"tokens_estimated": 300,
                            "block_text": extra.pop("block", "- x")},
            **extra}


def trial(index, outcomes, echo=False, **extra):
    """``outcomes``: {type: passed} for the judge-free types."""
    probes = [probe(kind, outcomes.get(kind), echo=echo and kind ==
                    "deletion", **extra) for kind in TYPES]
    return {"trial_index": index, "failed": False, "probe_results": probes,
            "integration_score": 4}


def write(root, model, phase, cell, trials):
    method = next(m for m in ba.CELLS if cell.endswith("_" + m))
    path = root / model / phase / cell / f"results_{method}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"experiment_metadata": {},
                                "conditions": [{"trials": trials}]}))


ALL_PASS = {k: True for k in TYPES[:5]}


def build(root):
    # kernel in-house: everything passes at h0; a stale recency at h2.
    write(root, "qwen", "kinh", "h0_kernel_shared",
          [trial(0, ALL_PASS, budget=True), trial(1, ALL_PASS, echo=True)])
    write(root, "qwen", "kinh", "h2_kernel_shared",
          [trial(0, {**ALL_PASS, "recency": False}),
           trial(1, ALL_PASS)])
    write(root, "qwen", "kinh", "no_memory_kernel_shared",
          [trial(0, {**ALL_PASS, "recall": False, "recency": False,
                     "contradiction": False})])
    write(root, "qwen", "kinh", "no_delete_kernel_shared",
          [trial(0, {**ALL_PASS, "deletion": False})])
    write(root, "qwen", "agent", "h0_replicated_inhouse",
          [trial(0, ALL_PASS), trial(1, {**ALL_PASS, "deletion": False},
                                     echo=True)])
    write(root, "qwen", "agent", "h2_native_inhouse",
          [trial(0, {**ALL_PASS, "privacy": False, "recall": False})])
    write(root, "qwen", "agent", "no_visibility_native_inhouse",
          [trial(0, {**ALL_PASS, "privacy": False})])
    write(root, "qwen", "agent", "h0_native_inhouse",
          [trial(0, {**ALL_PASS, "contradiction": False})])


def test_load_names_cells_by_locus_backend_and_condition(tmp_path):
    build(tmp_path)
    cells = ba.load(tmp_path)
    assert ("qwen", "kernel", "inhouse", "h0") in cells
    assert ("qwen", "native", "inhouse", "no_visibility") in cells
    assert ("qwen", "replicated", "inhouse", "h0") in cells


def test_the_matrix_splits_deletion_by_echo(tmp_path):
    build(tmp_path)
    rows = {(r["locus"], r["condition"], r["probe"]): r
            for r in ba.cell_rows(ba.load(tmp_path))}
    split = rows[("replicated", "h0", "deletion (echo)")]
    assert (split["passed"], split["n"]) == (0, 1)
    plain = rows[("replicated", "h0", "deletion (no echo)")]
    assert (plain["passed"], plain["n"]) == (1, 1)
    whole = rows[("replicated", "h0", "deletion")]
    assert whole["n"] == 2 and whole["rate"] == 0.5
    assert 0 < whole["ci_low"] < 0.5 < whole["ci_high"] < 1
    # Native has no budget: not applicable, not zero.
    assert rows[("native", "h0", "recall")]["budget_bound"] is None


def test_the_criteria_hold_only_with_the_evidence(tmp_path):
    build(tmp_path)
    checks = {c["criterion"].split(" ")[0]: c
              for c in ba.criteria(ba.load(tmp_path))}
    for kind in ("deletion", "privacy", "recall", "recency",
                 "contradiction"):
        assert checks[kind]["holds"], checks[kind]
    by_text = {c["criterion"]: c for c in ba.criteria(ba.load(tmp_path))}
    privacy = next(c for t, c in by_text.items()
                   if t.startswith("the kernel's privacy"))
    assert privacy["holds"]
    budget = next(c for t, c in by_text.items() if "budget" in t)
    # budget=True marks all six probes of that trial.
    assert budget["holds"] and budget["evidence"].startswith("6 probes")
    deletion = next(c for t, c in by_text.items()
                    if t.startswith("deletion passes among"))
    assert deletion["holds"]


def test_a_kernel_privacy_leak_breaks_its_criterion(tmp_path):
    build(tmp_path)
    write(tmp_path, "qwen", "kmem0", "h0_kernel_shared",
          [trial(0, {**ALL_PASS, "privacy": False},
                 forbidden_in_block=True)])
    checks = ba.criteria(ba.load(tmp_path))
    privacy = next(c for c in checks
                   if c["criterion"].startswith("the kernel's privacy"))
    assert not privacy["holds"]


def cap_criterion(root):
    return next(c for c in ba.criteria(ba.load(root))
                if c["criterion"].startswith("the cap binds"))


def test_the_cap_criterion_reads_a_cell_as_locus_and_backend(tmp_path):
    """The spec's cells are locus x backend, over H = 0 and H = 2:
    no_memory skips the sessions, so its cap cannot bind, and that does
    not fail the kernel in-house cell."""
    build(tmp_path)
    write(tmp_path, "qwen", "kinh", "no_memory_kernel_shared",
          [trial(0, {}, cap=False)])
    cap = cap_criterion(tmp_path)
    assert cap["holds"], cap
    assert "kernel inhouse: 24 of 24" in cap["evidence"]
    # A real cell whose cap never binds, in either condition, fails it.
    for cell in ("h0_kernel_shared", "h2_kernel_shared"):
        write(tmp_path, "qwen", "kinh", cell, [trial(0, ALL_PASS,
                                                     cap=False)])
    cap = cap_criterion(tmp_path)
    assert not cap["holds"]
    assert "('qwen', 'kernel', 'inhouse')" in cap["evidence"]


def test_the_contrast_pairs_users_and_counts_identical_blocks(tmp_path):
    build(tmp_path)
    rows = ba.contrast_rows(ba.load(tmp_path), "qwen")
    deletion = next(r for r in rows if r["probe"] == "deletion")
    assert (deletion["pairs"], deletion["kernel_only"],
            deletion["replicated_only"]) == (2, 1, 0)
    assert deletion["p_mcnemar"] == 1.0
    same = next(r for r in rows if r["probe"] == "identical blocks")
    assert same["pairs"] == 12 and same["kernel_only"] == 12


def test_markdown_lists_every_section(tmp_path):
    build(tmp_path)
    cells = ba.load(tmp_path)
    text = ba.markdown(cells, ba.cell_rows(cells), ba.binding_rows(cells),
                       ba.criteria(cells), ba.contrast_rows(cells, "qwen"),
                       ba.integration_rows(cells))
    for heading in ("## Per-probe pass matrix", "## Cap and budget",
                    "## Functional check criteria",
                    "## Kernel against replicated", "## Integration"):
        assert heading in text


def test_the_matrix_counts_contamination_and_marked_transitions(tmp_path):
    """Recency and contradiction rows count the answers that name both
    values and, of those, the ones that name the stale value as past;
    every row counts the probes whose value came only from the
    consumer's own conversation rows."""
    write(tmp_path, "qwen", "kinh", "h0_kernel_shared", [
        trial(0, ALL_PASS),
        {"trial_index": 1, "failed": False, "probe_results": [
            probe("recency", False, expected_present=True,
                  stale_present=True, transition_marked=True,
                  contaminated=True),
            probe("contradiction", False, expected_present=True,
                  stale_present=True, transition_marked=False)]},
    ])
    rows = {r["probe"]: r for r in ba.cell_rows(ba.load(tmp_path))}
    assert (rows["recency"]["names_both"],
            rows["recency"]["named_as_past"],
            rows["recency"]["contaminated"]) == (1, 1, 1)
    assert (rows["contradiction"]["names_both"],
            rows["contradiction"]["named_as_past"],
            rows["contradiction"]["contaminated"]) == (1, 0, 0)
    assert rows["recall"]["contaminated"] == 0


def test_integration_rows_carry_the_t_interval_of_the_mean(tmp_path):
    """The integration mean comes with its 95% t-interval, none for a
    single score (Amendment 2), in the rows and in the markdown."""
    scored = [trial(i, ALL_PASS) for i in range(3)]
    for t, value in zip(scored, (5, 4, 2)):
        t["integration_score"] = value
    write(tmp_path, "qwen", "kinh", "h0_kernel_shared", scored)
    write(tmp_path, "qwen", "kmem0", "h0_kernel_shared",
          [trial(0, ALL_PASS)])
    cells = ba.load(tmp_path)
    integration = ba.integration_rows(cells)
    rows = {r["backend"]: r for r in integration}
    low, high = stats.t.interval(0.95, 2, loc=11 / 3,
                                 scale=stats.sem([5, 4, 2]))
    inhouse = rows["inhouse"]
    assert (inhouse["n"], inhouse["mean"]) == (3, pytest.approx(11 / 3))
    assert (inhouse["ci_low"], inhouse["ci_high"]) == pytest.approx(
        (low, high))
    single = rows["mem0"]
    assert single["n"] == 1
    assert single["ci_low"] is None and single["ci_high"] is None
    text = ba.markdown(cells, [], [], [], [], integration)
    assert ("| model | locus | backend | condition | n | mean | ci_low | "
            "ci_high | sd | share_ge_4 |") in text
    assert f"| 3.67 | {low:.2f} | {high:.2f} | 1.53 |" in text
    # One score: no interval and no standard deviation.
    assert single["sd"] is None
    assert "| 1 | 4 |  |  |  | 1.00 |" in text


def test_named_as_past_counts_what_the_scorer_marks(tmp_path):
    """The matrix reads ``transition_marked`` as the scorer records it:
    pilot user 4's answer, which names the stale room as past in a
    sentence of its own, counts; one that asserts both does not."""
    recency = {
        "probe_id": "u004-p4-recency", "type": "recency",
        "slot": "sync_room", "question": "Which room is the sync in?",
        "expected": [{"value": "Larch", "aliases": []}],
        "forbidden": [{"value": "Saffron", "aliases": []}],
        "target_event": "u004-e11", "source_events": ["u004-e07",
                                                      "u004-e11"],
    }
    answers = (
        "Your weekly team sync is now held in the Larch room. Previously, "
        "it was in the Saffron room, but it has been relocated.",
        "Your weekly team sync is in the Larch room or the Saffron room.",
    )
    trials = [{"trial_index": i, "failed": False, "probe_results": [
        pr.score_probe(recency, answer, {"block_text": ""}, user_values=[],
                       locus="kernel")]}
        for i, answer in enumerate(answers)]
    write(tmp_path, "qwen", "kinh", "h0_kernel_shared", trials)
    rows = {r["probe"]: r for r in ba.cell_rows(ba.load(tmp_path))}
    assert (rows["recency"]["names_both"],
            rows["recency"]["named_as_past"]) == (2, 1)
    assert (rows["recency"]["passed"], rows["recency"]["n"]) == (0, 2)


def one_cell(tmp_path, trials, phase="kinh", cell="h0_kernel_shared"):
    write(tmp_path, "qwen", phase, cell, trials)
    return ba.load(tmp_path)


def custom(index, probes, failed=False, **extra):
    return {"trial_index": index, "failed": failed, "probe_results": probes,
            **extra}


CODENAME = [{"value": "Larkspur", "aliases": ["Lark Spur"]}]
LAWYER = [{"value": "Ines Carvalho", "aliases": ["Carvalho"]}]


class Source(str):
    """A row source whose hash makes a set yield ``conversation``,
    ``target``, ``echo`` and ``other_fact`` in that order under any hash
    seed: sorted for some sets, reversed or neither for others, so a
    join in the set's order would read ``target+other_fact`` and one in
    its reverse ``other_fact+echo``."""

    def __hash__(self):
        return {"conversation": 0, "target": 1, "echo": 2,
                "other_fact": 3}.get(str(self), 4)


def test_exposure_counts_the_value_in_any_probe_of_the_trial(tmp_path):
    """Known issue 43: a deletion pass whose value shows in a later
    probe's block (by an alias here) is exposed; so is a privacy pass
    whose value shows in a later answer or an earlier probe's block; a
    failure, an echo user's too, is exposed by its own block or its own
    answer; a clean trial is not. A failed trial, unscored probes and a
    trial without the probe are not counted, and a type without a probe
    in a cell has no row."""
    def trial_of(index, deletion_passed, deletion_block, later_block,
                 later_answer, privacy_passed=True, failed=False):
        return custom(index, [
            probe("deletion", deletion_passed, forbidden=CODENAME,
                  block=deletion_block),
            probe("privacy", privacy_passed, forbidden=LAWYER),
            probe("recall", True, block=later_block),
            probe("integration", None, observed=later_answer),
        ], failed=failed)
    cells = one_cell(tmp_path, [
        trial_of(0, True, "- x", "- the Lark Spur project", "Done."),
        trial_of(1, True, "- x", "- x", "Ask Carvalho."),
        trial_of(2, False, "- Larkspur", "- x", "Done."),
        trial_of(3, True, "- x", "- x", "Done."),
        trial_of(4, False, "- Larkspur", "- Larkspur", "Ask Carvalho.",
                 failed=True),
        trial_of(5, None, "- x", "- Larkspur", "Ask Carvalho.",
                 privacy_passed=None),
        custom(6, [probe("recall", True, block="- Larkspur")]),
        # An echo user's failure, by its own answer.
        custom(7, [probe("deletion", False, echo=True, forbidden=CODENAME,
                         observed="It is Larkspur.")]),
        custom(8, [probe("deletion", True, forbidden=CODENAME,
                         block="- Ines Carvalho"),
                   probe("privacy", True, forbidden=LAWYER)]),
    ])
    rows = {r["probe"]: r for r in ba.exposure_rows(cells)}
    assert (rows["deletion"]["n"], rows["deletion"]["passed"],
            rows["deletion"]["exposed"],
            rows["deletion"]["passed_exposed"]) == (6, 4, 3, 1)
    assert (rows["privacy"]["n"], rows["privacy"]["passed"],
            rows["privacy"]["exposed"],
            rows["privacy"]["passed_exposed"]) == (5, 5, 2, 2)
    only = ba.exposure_rows(one_cell(
        tmp_path, [custom(0, [probe("deletion", True, forbidden=CODENAME)])],
        phase="kmem0"))
    assert [(r["backend"], r["probe"]) for r in only] == [
        ("inhouse", "deletion"), ("inhouse", "privacy"),
        ("mem0", "deletion")]


def test_carriers_name_the_rows_that_held_the_revoked_value(tmp_path):
    """Known issue 38: each failed deletion probe is classified by the
    sources of its block rows that hold the value (``unknown`` for a row
    without one); ``block, no row`` when the block text holds it but no
    row does; ``answer only`` when the block text does not (whatever the
    rows say); an echo user's failure counts like any other. Two or
    three sources join in sorted order, whether the set holds them in
    that order, in its reverse or in neither."""
    def fail(index, failed=False, **fields):
        return custom(index, [probe("deletion", False, **fields)],
                      failed=failed)
    cells = one_cell(tmp_path, [
        # An echo user's failure.
        fail(0, echo=True, forbidden_in_block=True,
             rows_with_forbidden=[{"source": "echo"}]),
        fail(1, forbidden_in_block=True,
             rows_with_forbidden=[{"source": "other_fact"},
                                  {"source": "echo"}]),
        fail(2, forbidden_in_block=False, forbidden_in_answer=True),
        custom(3, [probe("deletion", True)]),
        fail(4, forbidden_in_block=True,
             rows_with_forbidden=[{"source": "echo"}]),
        # In the block, in no row.
        fail(5, forbidden_in_block=True, rows_with_forbidden=[]),
        # The block text decides, not the rows.
        fail(6, forbidden_in_block=False, forbidden_in_answer=True,
             rows_with_forbidden=[{"source": "echo"}]),
        fail(7, forbidden_in_block=True,
             rows_with_forbidden=[{"source": "target"},
                                  {"source": "other_fact"}]),
        fail(8, forbidden_in_block=True,
             rows_with_forbidden=[{"source": "target"}, {"source": "echo"},
                                  {"source": "conversation"}]),
        # A row without a source.
        fail(9, forbidden_in_block=True, rows_with_forbidden=[{}]),
        # Not counted: unscored, and a failed trial.
        custom(10, [probe("deletion", None)]),
        fail(11, failed=True, forbidden_in_block=True,
             rows_with_forbidden=[{"source": "echo"}]),
    ])
    for cell in cells.values():
        for t in cell["trials"]:
            for p in t["probe_results"]:
                for r in p.get("rows_with_forbidden") or []:
                    if "source" in r:
                        r["source"] = Source(r["source"])
    rows = ba.carrier_rows(cells)
    carriers = {r["carrier"]: r["failures"] for r in rows}
    assert carriers == {"echo": 2, "echo+other_fact": 1,
                        "other_fact+target": 1,
                        "conversation+echo+target": 1, "unknown": 1,
                        "answer only": 2, "block, no row": 1}
    assert [r["carrier"] for r in rows] == sorted(carriers)


def test_stored_carriers_name_what_the_store_kept_behind_each_probe(
        tmp_path, monkeypatch):
    """Known issue 38: every scored deletion probe, failed or passed, by
    the rows that still held the revoked value after the history. A pass
    over a stored echo row or fold counts as a pass under the row's
    source; rows of the probes listing and of another revoked value do
    not count; a forbidden value may be a plain string. Sources join in
    sorted order, whether the set holds them in that order or in its
    reverse, and the rows are in sorted order. A user without an echo
    event counts too. An unscored probe, a failed trial and a trial
    without a deletion probe are not counted."""
    def deletion(index, passed, stored, failed=False):
        p = probe("deletion", passed, echo=True, slot="teammate",
                  target_event="e4", forbidden=CODENAME)
        return custom(index, [p], failed=failed,
                      revoked_value_rows=stored)

    def row(event, fact_key=None, listing="history", value="Larkspur"):
        return {"listing": listing, "memory_id": f"m-{event}",
                "owner_agent": "task_agent", "provenance_event": event,
                "fact_key": fact_key, "value": value}
    echo, fold = row("e8"), row("e5", "codename")
    answer = {**row("p2"), "owner_agent": "assistant_agent",
              "memory_type": "conversation"}
    cells = one_cell(tmp_path, [
        deletion(0, False, [echo, row("e5", "codename", listing="probes")]),
        deletion(1, True, [echo]),
        deletion(2, True, [fold]),
        deletion(3, False, [fold, echo]),
        deletion(4, False, [row("e4", "teammate")]),
        deletion(5, True, [row("p4", listing="probes")]),
        deletion(6, True, [row("e8", value="Ines Carvalho")]),
        deletion(7, False, [fold, row("e4", "teammate")]),
        deletion(8, False, [echo, answer]),
        # A forbidden value given as a plain string.
        custom(9, [probe("deletion", False, echo=True, slot="teammate",
                         target_event="e4", forbidden=["Larkspur"])],
               revoked_value_rows=[echo]),
        deletion(10, None, [echo]),
        deletion(11, False, [echo], failed=True),
        custom(12, [probe("recall", True)], revoked_value_rows=[echo]),
        # A user without an echo event, nothing stored.
        custom(13, [probe("deletion", True, slot="teammate",
                          target_event="e4", forbidden=CODENAME)],
               revoked_value_rows=[]),
    ])
    real = ba.row_source
    monkeypatch.setattr(ba, "row_source",
                        lambda row, probe: Source(real(row, probe)))
    rows = ba.stored_carrier_rows(cells)
    stored = {r["stored"]: (r["failures"], r["passes"]) for r in rows}
    assert stored == {"echo": (2, 1), "other_fact": (0, 1),
                      "echo+other_fact": (1, 0), "target": (1, 0),
                      "other_fact+target": (1, 0),
                      "conversation+echo": (1, 0), "none": (0, 3)}
    assert [r["stored"] for r in rows] == sorted(stored)


def test_misses_are_split_by_where_the_expected_value_was(tmp_path):
    """Each failure is filed by where the expected value was: outside
    the block, in the block text but no row, only in the consumer's own
    rows, or in a writer's row; ``named`` counts the failures whose
    answer named it too (they failed on the stale value)."""
    cells = one_cell(tmp_path, [
        custom(0, [
            probe("recall", False, expected_in_block=False),
            probe("recency", False, expected_in_block=True,
                  expected_present=True, stale_present=True,
                  rows_with_expected=[{"source": "conversation"}]),
            probe("contradiction", False, expected_in_block=True,
                  rows_with_expected=[{"source": "conversation"},
                                      {"source": "target"}]),
        ]),
        custom(1, [probe("recall", True, expected_in_block=True)]),
        # In the block text, in no row.
        custom(2, [probe("recency", False, expected_in_block=True,
                         rows_with_expected=[])]),
        # Not counted: unscored, and a failed trial.
        custom(3, [probe("recall", None, expected_in_block=False)]),
        custom(4, [probe("recall", False, expected_in_block=False)],
               failed=True),
        # Named only the stale value: not counted in ``named``.
        custom(5, [probe("contradiction", False, expected_in_block=True,
                         expected_present=False, stale_present=True,
                         rows_with_expected=[{"source": "target"}])]),
    ])
    rows = {r["probe"]: r for r in ba.miss_rows(cells)}
    assert (rows["recall"]["failed"], rows["recall"]["named"],
            rows["recall"]["not_in_block"]) == (1, 0, 1)
    recency = rows["recency"]
    assert (recency["failed"], recency["named"], recency["not_in_block"],
            recency["in_block_no_row"], recency["conversation_only"],
            recency["in_writer_row"]) == (2, 1, 0, 1, 1, 0)
    contradiction = rows["contradiction"]
    assert (contradiction["failed"], contradiction["named"],
            contradiction["in_writer_row"],
            contradiction["conversation_only"]) == (2, 0, 2, 0)


def test_contradiction_is_reported_per_slot(tmp_path):
    """Known issue 44: slots whose question repeats the earlier
    statement's words are read apart. ``lenient`` counts the answers
    that name the later value: a pass, and a failure that names both
    values; not a failure that names only the earlier value, or
    neither."""
    cells = one_cell(tmp_path, [
        # Named both values: lenient, not a pass.
        custom(0, [probe("contradiction", False, slot="manager",
                         expected_present=True, stale_present=True)]),
        # Named only the later value: a pass, and lenient.
        custom(1, [probe("contradiction", True, slot="home_city",
                         expected_present=True, stale_present=False)]),
        # Named only the earlier value, and neither: not lenient.
        custom(2, [probe("contradiction", False, slot="client",
                         expected_present=False, stale_present=True)]),
        custom(3, [probe("contradiction", False, slot="client",
                         expected_present=False, stale_present=False)]),
        # Not counted: unscored, and a failed trial.
        custom(4, [probe("contradiction", None, slot="manager",
                         expected_present=True)]),
        custom(5, [probe("contradiction", True, slot="manager",
                         expected_present=True)], failed=True),
    ])
    found = ba.slot_rows(cells)
    # slot: (n, passed, lenient)
    rows = {r["slot"]: (r["n"], r["passed"], r["lenient"]) for r in found}
    assert rows == {"manager": (1, 0, 1), "home_city": (1, 1, 1),
                    "client": (2, 0, 0)}
    assert [r["slot"] for r in found] == ["client", "home_city", "manager"]


def test_an_earlier_answer_with_the_stale_value_splits_the_rate(tmp_path):
    """A recency or contradiction probe is counted apart when one of the
    consumer's earlier answers in its block carries the stale value,
    whether or not a writer row, before or after it, carries it too; a
    writer's stale row alone does not count; a failure that names both
    values is not a pass; an unscored probe and a failed trial are not
    counted."""
    write(tmp_path, "qwen", "kinh", "h2_kernel_shared", [
        # An earlier answer, then a writer row.
        custom(0, [probe("recency", True,
                         rows_with_stale=[{"source": "conversation"},
                                          {"source": "target"}])]),
        custom(1, [probe("recency", False, expected_present=True,
                         stale_present=True)])])
    cells = one_cell(tmp_path, [
        custom(0, [probe("contradiction", False, expected_present=True,
                         stale_present=True,
                         rows_with_stale=[{"source": "conversation"}])]),
        custom(1, [probe("contradiction", True,
                         rows_with_stale=[{"source": "target"}])]),
        custom(2, [probe("contradiction", True)]),
        custom(3, [probe("contradiction", None,
                         rows_with_stale=[{"source": "conversation"}])]),
        custom(4, [probe("contradiction", True,
                         rows_with_stale=[{"source": "conversation"}])],
               failed=True),
        # A writer row, then an earlier answer.
        custom(5, [probe("contradiction", True,
                         rows_with_stale=[{"source": "target"},
                                          {"source": "conversation"}])]),
    ])
    found = ba.earlier_answer_rows(cells)
    # No recency probe in h0, no contradiction probe in h2: no row.
    assert [(r["condition"], r["probe"]) for r in found] == [
        ("h0", "contradiction"), ("h2", "recency")]
    assert [(r["with_stale_answer"], r["passed_with"], r["without"],
             r["passed_without"]) for r in found] == [(2, 1, 2, 2),
                                                       (1, 1, 1, 0)]


def test_the_integration_block_reports_its_rows_and_the_base_rows(tmp_path):
    """Known issue 45: the integration probe's block, by its rows, the
    consumer's own rows and the writer rows (every other row, a calendar
    row too), the budget, and whether rows of the user's base task and
    base profile events reached it (a later task or profile row does not
    count, not even beside a base task row); the score by how many of
    the two did. A probe's own score comes before the trial's, and only
    its own budget counts; a failed trial and a trial without the probe
    are left out; a probe without any score still counts, and a missing
    score blanks the mean. The scores are means, not medians."""
    sessions = [
        {"session": 1, "events": [
            {"event_id": "u000-e00", "fact_key": "base_profile"}]},
        {"session": 2, "events": [
            {"event_id": "u000-e01", "fact_key": "base_task"},
            {"event_id": "u000-e05", "fact_key": "launch_date"}]},
        {"session": 3, "events": [
            {"event_id": "u000-e09", "fact_key": "home_city"}]}]

    def with_rows(index, injected, score, budget, failed=False,
                  trial_score=None, others=()):
        p = probe("integration", None, budget=budget,
                  integration_score=score)
        p["diagnostics"]["injected_memories"] = injected
        return custom(index, [*others, p], failed=failed,
                      sessions=sessions, integration_score=trial_score)
    conversation = {"memory_type": "conversation",
                    "provenance_event": "u000-p3-recall"}
    task = {"memory_type": "task_context", "provenance_event": "u000-e01"}
    later_task = {"memory_type": "task_context",
                  "provenance_event": "u000-e05"}
    profile = {"memory_type": "profile", "provenance_event": "u000-e00"}
    later_profile = {"memory_type": "profile",
                     "provenance_event": "u000-e09"}
    calendar = {"memory_type": "calendar", "provenance_event": "u000-e07"}
    trials = [with_rows(0, [conversation, task, profile], 4, True,
                        trial_score=1),
              with_rows(1, [conversation, calendar], 3, False,
                        others=[probe("recall", True, budget=True)]),
              with_rows(2, [later_task, later_profile], None, False,
                        trial_score=3),
              with_rows(3, [task], 5, True, failed=True),
              with_rows(4, [profile], 3, False),
              with_rows(5, [task, later_profile], 1, False),
              with_rows(6, [profile], 5, False),
              custom(7, [probe("recall", True)], sessions=sessions)]
    cells = one_cell(tmp_path, trials)
    row = ba.integration_block_rows(cells)[0]
    assert (row["n"], row["rows"], row["own_rows"],
            row["writer_rows"]) == pytest.approx((6, 11 / 6, 2 / 6, 9 / 6))
    assert (row["budget_bound"], row["base_task_in_block"],
            row["base_profile_in_block"], row["both_in_block"]) == (
        1, 2, 3, 1)
    # Trials 0 and 5 are the only two whose scores average 2.5, so no
    # other split reads the same; the other four average 3.5, not their
    # median (3.0).
    assert (row["score_with"], row["score_without"]) == (2.5, 3.5)
    base_rows = ba.integration_base_rows(cells)
    by_rows = {r["base_rows"]: (r["n"], r["score"]) for r in base_rows}
    assert by_rows == {0: (2, 3.0), 1: (3, 3.0), 2: (1, 4.0)}
    assert [r["base_rows"] for r in base_rows] == [0, 1, 2]
    # A cell without the probe has no row.
    assert not ba.integration_block_rows(one_cell(
        tmp_path / "none", [custom(0, [probe("recall", True)])]))
    native = ba.integration_block_rows(one_cell(
        tmp_path, trials, phase="agent", cell="h0_native_inhouse"))
    assert next(r for r in native
                if r["locus"] == "native")["budget_bound"] is None
    unjudged = one_cell(
        tmp_path, [with_rows(0, [conversation], 4, False),
                   with_rows(1, [conversation], None, True),
                   with_rows(2, [task, profile], None, False)],
        phase="kmem0")
    mem0 = next(r for r in ba.integration_block_rows(unjudged)
                if r["backend"] == "mem0")
    assert (mem0["n"], mem0["rows"], mem0["own_rows"],
            mem0["writer_rows"], mem0["budget_bound"],
            mem0["base_task_in_block"], mem0["base_profile_in_block"],
            mem0["both_in_block"], mem0["score_with"],
            mem0["score_without"]) == (
        3, pytest.approx(4 / 3), pytest.approx(2 / 3),
        pytest.approx(2 / 3), 1, 1, 1, 1, None, None)
    assert {r["base_rows"]: (r["n"], r["score"])
            for r in ba.integration_base_rows(unjudged)
            if r["backend"] == "mem0"} == {0: (2, None), 2: (1, None)}
    # Means, not medians: three probes with a base task row, scored 1,
    # 1 and 4 (mean 2.0, median 1.0).
    mean = one_cell(tmp_path / "mean", [
        with_rows(i, [task], score, False)
        for i, score in enumerate((1, 1, 4))])
    assert (ba.integration_block_rows(mean)[0]["score_with"],
            ba.integration_base_rows(mean)[0]["score"]) == (2.0, 2.0)


def test_the_readings_reach_the_report_and_the_json(tmp_path):
    build(tmp_path)
    cells = ba.load(tmp_path)
    extra = ba.readings(cells)
    assert set(extra) == {"exposure", "carriers", "stored_carriers",
                          "misses", "slots", "earlier_answers",
                          "integration_blocks", "integration_base_rows"}
    # A probe type with no failure in a cell has no misses row.
    assert all(r["failed"] for r in extra["misses"])
    sections = (ba.cell_rows(cells), ba.binding_rows(cells),
                ba.criteria(cells), ba.contrast_rows(cells, "qwen"),
                ba.integration_rows(cells))
    before = ba.markdown(cells, *sections)
    full = ba.markdown(cells, *sections, extra)
    # The earlier sections are unchanged, byte for byte, and the
    # readings follow them, in order, each with the cell keys.
    assert "Trial-level" not in before
    assert full.startswith(before)
    # An empty reading prints nothing.
    assert ba.markdown(cells, *sections, {n: [] for n in extra}) == before
    at = [full.index(f"## {title}\n")
          for _, title, _, _ in ba.READING_SECTIONS]
    assert len(at) == len(extra) and len(before) <= at[0]
    assert at == sorted(at)
    assert ("| model | locus | backend | condition | probe | n | passed | "
            "exposed | passed_exposed |") in full
    # Each reading has rows, and each row exactly its section's columns.
    for name, _, _, keys in ba.READING_SECTIONS:
        assert extra[name] and all(
            set(r) == set(ba.CELL_KEYS + keys) for r in extra[name]), name
    # The report main writes holds each reading with its title, its note
    # and its columns. The titles and columns are pinned, in order. Of
    # each note, the phrases in `defined` are pinned, in any order, and
    # the rest of its text is not. The tests above check the rules of
    # the columns and labels those phrases define; what they say of the
    # scorer, the harness, the store, selection and the judge is pinned
    # as text only.
    out, md = tmp_path / "analysis.json", tmp_path / "analysis.md"
    assert ba.main([str(tmp_path), "--no-criteria", "--json",
                    str(out), "--markdown", str(md)]) == 0
    text = md.read_text()
    for name, title, note, keys in ba.READING_SECTIONS:
        assert (f"## {title}\n\n{note}\n\n| "
                + " | ".join(ba.CELL_KEYS + keys) + " |") in text, name
    assert [(name, title, keys)
            for name, title, _, keys in ba.READING_SECTIONS] == [
        ("exposure", "Trial-level exposure (deletion, privacy)",
         ["probe", "n", "passed", "exposed", "passed_exposed"]),
        ("carriers", "Deletion failures by carrier",
         ["carrier", "failures"]),
        ("stored_carriers", "Deletion probes by what the store kept",
         ["stored", "failures", "passes"]),
        ("misses", "Failures: where the expected value was",
         ["probe", "failed", "named", "not_in_block", "in_block_no_row",
          "conversation_only", "in_writer_row"]),
        ("slots", "Contradiction by slot",
         ["slot", "n", "passed", "lenient"]),
        ("earlier_answers",
         "Recency and contradiction: the stale value in an earlier answer",
         ["probe", "with_stale_answer", "passed_with", "without",
          "passed_without"]),
        ("integration_blocks", "The integration probe's block",
         ["n", "rows", "own_rows", "writer_rows", "budget_bound",
          "base_task_in_block", "base_profile_in_block", "both_in_block",
          "score_with", "score_without"]),
        ("integration_base_rows",
         "Integration score by the base rows in the block",
         ["base_rows", "n", "score"])]
    defined = {
        "exposure": [
            "A probe checks only its own block and answer.",
            "`exposed`: trials whose forbidden value appears in any "
            "probe's block or answer", "`passed_exposed`: passes among "
            "them"],
        "carriers": [
            "The sources of the block rows that held the revoked value "
            "(`other_fact` is a Mem0 fold)",
            "`block, no row`: the block text held it but no row did",
            "`answer only`: the block text did not hold it (only the "
            "answer did)"],
        "stored_carriers": [
            "The sources of the rows that still held the revoked value "
            "after the history, right before the probes "
            "(`revoked_value_rows`), or `none`.",
            "A pass with a stored carrier is one whose selection left it "
            "out of the block: the fetch did not return it, or a later "
            "stage, such as the cap, dropped it."],
        "misses": [
            "Failed recall, recency and contradiction probes by where the "
            "expected value was",
            "`not_in_block` (never stored, or selection lost it)",
            "`in_block_no_row` (the block text holds it, no injected row "
            "does)", "`conversation_only` (only the consumer's own earlier "
            "answers held it)", "`in_writer_row` (a writer's row held it)",
            "`named`: failures whose answer named the expected value too "
            "(they failed on the stale value)"],
        "slots": ["`lenient`: answers that name the later value"],
        "earlier_answers": [
            "Split by whether one of the consumer's earlier answers in the "
            "block carries the stale value."],
        "integration_blocks": [
            "Means per probe: rows, the consumer's own rows (its earlier "
            "answers) and writer rows.", "Probes whose block holds a row "
            "of the user's base task context, of its base profile, and of "
            "both", "the mean score with and without a base task row"],
        "integration_base_rows": [
            "The judge scores the answer against the base profile and the "
            "base task context.",
            "`base_rows`: how many of the two have a row in the block"]}
    notes = {name: note for name, _, note, _ in ba.READING_SECTIONS}
    assert set(defined) == set(notes)
    for name, phrases in defined.items():
        assert all(p in notes[name] for p in phrases), name
    assert json.loads(out.read_text())["readings"] == json.loads(
        json.dumps(extra, default=str))
