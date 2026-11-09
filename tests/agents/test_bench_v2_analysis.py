"""The benchmark v2 analysis (NeurIPS Subtask 14,
``bench_v2_analysis.py``) on synthetic results files with known answers:
the pass matrix, the echo split, binding counts, the functional check's
criteria and the paired kernel - replicated contrast."""
import json

from benchmarks.shared_memory import bench_v2_analysis as ba

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
