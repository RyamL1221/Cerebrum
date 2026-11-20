"""Analyze benchmark v2 runs (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Functional check and smoke").

Reads ``<root>/<model>/<phase>/<condition>_<method>/results_<method>.json``
as AIOS ``scripts/run_bench_v2.sh`` writes them and reports:

- the per-probe pass matrix (locus x backend x condition x probe type),
  deletion split into echo and non-echo users, with 95% Wilson
  intervals, the lenient recency and contradiction rates, and how often
  the cap and the budget bound;
- the functional check's criteria, each with its evidence (since
  Amendment 4 the library's deletion, supersession and guard have
  criteria of their own; since Amendment 6 a limit, the budget or the
  cap, must bind in every kernel and replicated cell);
- for the smoke: the integration mean per cell with its 95%
  t-interval, kernel against replicated per probe type (paired over
  users, exact McNemar), and the share of identical in-house blocks;
- readings that explain the rates (AIOS ``DEV_STATUS.md``, known
  issues 38, 43 to 45): trial-level exposure for deletion and privacy,
  each deletion failure's carrier and what the store kept behind each
  deletion probe, where the expected value was in each failure,
  contradiction per slot, recency and contradiction split by whether an
  earlier answer in the block carries the stale value, and the
  integration probe's block, with its score by the base rows it holds.

    python -m benchmarks.shared_memory.bench_v2_analysis results/bench_v2_functional \\
        --markdown results/bench_v2_functional/analysis.md \\
        --json results/bench_v2_functional/analysis.json
"""
import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from benchmarks.shared_memory.models import EMPTY_WRITE_IS_LOSS
from benchmarks.shared_memory.probes import (
    match_entry, mcnemar_exact, row_source, t_interval,
)
from benchmarks.shared_memory.metrics import (
    BLOCK,
    DECISION_ERRORS,
    JUDGE_FREE,
    LETTERS,
    PICK_KINDS,
    decision_picks,
    decision_summary,
    block_size as _block_size,
    block_text as _block,
    pass_rate as _rate,
    probes_of as _probes,
)

REAL_CONDITIONS = ("h0", "h2")
CONTROL_OF = {"recall": "no_memory", "recency": "no_memory",
              "contradiction": "no_memory", "deletion": "no_delete",
              "privacy": "no_visibility"}
# method -> (locus, backend)
CELLS = {
    "kernel_shared": None,  # the backend comes from the phase
    "replicated_mem0": ("replicated", "mem0"),
    "replicated_inhouse": ("replicated", "inhouse"),
    "native_mem0": ("native", "mem0"),
    "native_inhouse": ("native", "inhouse"),
    "replicated_graphiti": ("replicated", "graphiti"),
    "native_graphiti": ("native", "graphiti"),
    "replicated_amem": ("replicated", "amem"),
    "native_amem": ("native", "amem"),
}
# The driver's kernel phases; "_ns" runs the no_supersession control
# in a kernel of its own (Amendment 4). "kgra" is Graphiti (Subtask 16),
# "kamem" A-MEM (Subtask 17).
PHASE_BACKEND = {"kmem0": "mem0", "kinh": "inhouse",
                 "kmem0_ns": "mem0", "kinh_ns": "inhouse",
                 "kgra": "graphiti", "kgra_ns": "graphiti",
                 "kamem": "amem", "kamem_ns": "amem"}
# The loci that run the library's forget and supersession.
LIBRARY_LOCI = ("kernel", "replicated")


def load(root: Path) -> Dict[tuple, dict]:
    """``{(model, locus, backend, condition): {"trials": [...],
    "metadata": {...}}}`` for every results file under ``root``."""
    cells = {}
    for path in sorted(root.glob("*/*/*/results_*.json")):
        model, phase, cell = path.parts[-4], path.parts[-3], path.parts[-2]
        # "<condition>_<method>"; conditions hold underscores themselves
        # (no_delete), so the method is matched as the suffix.
        method = next((m for m in CELLS if cell.endswith("_" + m)), None)
        if method is None:
            continue
        condition = cell[:-len(method) - 1]
        locus, backend = CELLS[method] or ("kernel", PHASE_BACKEND[phase])
        data = json.loads(path.read_text())
        cells[(model, locus, backend, condition)] = {
            "trials": data["conditions"][0]["trials"],
            "metadata": data["experiment_metadata"],
        }
    return cells


# Every table's standard columns (Subtask 17): the mean block a row's
# probes saw, in tokens and in rows, so a difference between loci can be
# read against what each injected.


def _cell_probes(cell: dict, kind: Optional[str] = None) -> List[dict]:
    """The probes of the cell's trials that did not fail; of ``kind``
    only, when given."""
    return [p for t in cell["trials"] if not t.get("failed")
            for p in t.get("probe_results") or []
            if kind is None or p["type"] == kind]


def with_block_size(rows: List[dict], cells: Dict[tuple, dict],
                    kind: Optional[str] = None) -> List[dict]:
    """``rows`` (keyed by cell) with the block columns: over the probes
    of the row's ``probe`` type when it names one, else of ``kind``
    (all of the cell's probes when None). A row that splits them further
    (a slot, a carrier, a count of base rows) gets its cell's mean, as
    the report's note says."""
    out = []
    for row in rows:
        cell = cells[(row["model"], row["locus"], row["backend"],
                      row["condition"])]
        probe = row.get("probe")
        out.append({**row, **_block_size(_cell_probes(
            cell, probe if probe in JUDGE_FREE + ("integration",)
            else kind))})
    return out


def cell_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """One row per cell and probe type (deletion also per echo split)."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        trials = cell["trials"]
        failed = sum(1 for t in trials if t.get("failed"))
        splits = [(kind, None) for kind in JUDGE_FREE]
        splits += [("deletion", True), ("deletion", False)]
        for kind, echo in splits:
            probes = _probes(trials, kind, echo)
            scored = [p for p in probes if p.get("passed") is not None]
            row = {
                "model": model, "locus": locus, "backend": backend,
                "condition": condition,
                "probe": kind if echo is None else
                f"deletion ({'echo' if echo else 'no echo'})",
                "trials": len(trials), "failed": failed,
                **_rate(sum(1 for p in scored if p["passed"]), len(scored)),
                "cap_bound": sum(1 for p in probes if p.get("cap_bound")),
                "budget_bound": (None if locus == "native" else sum(
                    1 for p in probes if p.get("budget_bound"))),
                "probes": len(probes),
                # A value reached the block only through the consumer's
                # own conversation rows (earlier probes' answers).
                "contaminated": sum(1 for p in probes
                                    if p.get("contaminated")),
                **_block_size(probes),
            }
            if kind in ("recency", "contradiction"):
                lenient = [p for p in probes
                           if p.get("expected_present") is not None]
                row["lenient"] = _rate(
                    sum(1 for p in lenient if p["expected_present"]),
                    len(lenient))["rate"]
                both = [p for p in probes if p.get("expected_present")
                        and p.get("stale_present")]
                row["names_both"] = len(both)
                row["named_as_past"] = sum(
                    1 for p in both if p.get("transition_marked"))
            if kind in ("deletion", "privacy"):
                row["in_block"] = sum(1 for p in probes
                                      if p.get("forbidden_in_block"))
                row["in_answer"] = sum(1 for p in probes
                                       if p.get("forbidden_in_answer"))
            rows.append(row)
    return rows


def binding_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per cell: the share of probes whose cap / budget bound, and the
    block sizes."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        probes = [p for t in cell["trials"] if not t.get("failed")
                  for p in t.get("probe_results") or []]
        tokens = [((p.get("diagnostics") or {}).get("tokens_estimated")
                   or 0) for p in probes]
        rows.append({
            "model": model, "locus": locus, "backend": backend,
            "condition": condition, "probes": len(probes),
            "cap_bound": sum(1 for p in probes if p.get("cap_bound")),
            "budget_bound": None if locus == "native" else sum(
                1 for p in probes if p.get("budget_bound")),
            "tokens_median": statistics.median(tokens) if tokens else None,
            "tokens_max": max(tokens) if tokens else None,
            **_block_size(probes),
        })
    return rows


def criteria(cells: Dict[tuple, dict]) -> List[dict]:
    """The functional check's pass conditions (docs/BENCHMARK_V2.md),
    each with its evidence."""
    out = []

    def probes_where(kind, pred, echo=None):
        return [p for key, cell in cells.items() if pred(*key)
                for p in _probes(cell["trials"], kind, echo)
                if p.get("passed") is not None]

    real = lambda m, l, b, c: c in REAL_CONDITIONS  # noqa: E731
    for kind in JUDGE_FREE:
        scored = probes_where(kind, real)
        passes = sum(1 for p in scored if p["passed"])
        fails = len(scored) - passes
        control = CONTROL_OF[kind]
        ctl = probes_where(kind, lambda m, l, b, c: c == control)
        ctl_fails = sum(1 for p in ctl if not p["passed"])
        out.append({
            "criterion": f"{kind} passes and fails in real conditions, "
                         f"and fails under {control}",
            "holds": passes > 0 and fails > 0 and ctl_fails > 0,
            "evidence": f"real: {passes} pass, {fails} fail; "
                        f"{control}: {ctl_fails} of {len(ctl)} fail",
        })
    inhouse_real = lambda m, l, b, c: (  # noqa: E731
        b == "inhouse" and c in REAL_CONDITIONS)
    non_echo = probes_where("deletion", inhouse_real, echo=False)
    nd = probes_where("deletion", lambda m, l, b, c: c == "no_delete")
    out.append({
        "criterion": "deletion passes among non-echo users in in-house "
                     "cells and fails under no_delete",
        "holds": bool(non_echo) and all(p["passed"] for p in non_echo)
        and any(not p["passed"] for p in nd),
        "evidence": f"non-echo in-house: "
                    f"{sum(p['passed'] for p in non_echo)} of "
                    f"{len(non_echo)} pass; no_delete: "
                    f"{sum(not p['passed'] for p in nd)} of {len(nd)} fail",
    })
    kernel_priv = [p for key, cell in cells.items() if key[1] == "kernel"
                   for p in _probes(cell["trials"], "privacy")]
    leaks = [p for p in kernel_priv if p.get("forbidden_in_block")
             or p.get("forbidden_in_answer")]
    out.append({
        "criterion": "the kernel's privacy probe never fails (block or "
                     "answer)",
        "holds": bool(kernel_priv) and not leaks,
        "evidence": f"{len(leaks)} of {len(kernel_priv)} kernel privacy "
                    "probes leaked",
    })
    # A cell is locus x backend (the spec's six cells), read over the
    # real conditions: no_memory skips the sessions, so its cap cannot
    # bind, and the controls are not what the check is about.
    bound: Dict[tuple, List[int]] = {}
    for (m, l, b, c), cell in cells.items():
        if l not in ("kernel", "replicated") or c not in REAL_CONDITIONS:
            continue
        counts = bound.setdefault((m, l, b), [0, 0, 0])
        for t in cell["trials"]:
            for p in t.get("probe_results") or []:
                counts[0] += 1
                counts[1] += bool(p.get("cap_bound"))
                counts[2] += bool(p.get("budget_bound"))
    # Amendment 6: since k is 30 the budget is meant to limit a block,
    # and the cap still can; a cell needs some probe one of them bound.
    unlimited = [key for key, (_, cap, budget) in sorted(bound.items())
                 if not cap and not budget]
    out.append({
        "criterion": "a limit (the budget or the cap) binds in some probe "
                     "of every kernel and replicated cell (H = 0 and "
                     "H = 2)",
        "holds": bool(bound) and not unlimited,
        "evidence": "; ".join(f"{l} {b}: budget {budget}, cap {cap} of {n}"
                              for (m, l, b), (n, cap, budget)
                              in sorted(bound.items()))
        + (f"; cells where no limit bound: {unlimited}"
           if unlimited else ""),
    })
    if any(key[1] in LIBRARY_LOCI for key in cells):
        out += library_criteria(cells)
    return out


def _trials(cells: Dict[tuple, dict], pred) -> List[tuple]:
    """``(key, trial)`` for every trial, failed ones included, of the
    cells whose key ``pred`` accepts."""
    return [(key, trial) for key, cell in sorted(cells.items())
            if pred(*key) for trial in cell["trials"]]


def _events(trial: dict, kind: Optional[str] = None) -> List[dict]:
    """The trial's session events (of type ``kind``), each with its
    session's writer as ``writer``."""
    return [dict(event, writer=session.get("writer"))
            for session in trial.get("sessions") or []
            for event in session.get("events") or []
            if kind is None or event.get("type") == kind]


def library_criteria(cells: Dict[tuple, dict]) -> List[dict]:
    """Amendment 4's criteria, in the kernel and replicated cells on
    both backends: at H = 0, deletion is complete and goes through the
    forget, no block holds a retired row, and every Mem0 forget
    scrubbed a message; writer_scoped fails some echo user, and
    no_supersession puts a retired row in some block; outside H = 2,
    the guard was armed and dropped nothing. A failed trial or an
    unscored probe counts against the deletion criterion; the others
    leave a failed trial out, and writer_scoped an unscored probe."""
    out = []
    ref = lambda m, l, b, c: l in LIBRARY_LOCI and c == "h0"  # noqa: E731
    h0_like = lambda m, l, b, c: (  # noqa: E731
        l in LIBRARY_LOCI and c != "h2")
    trials = _trials(cells, ref)

    passes = fails = unscored = failed = residue = 0
    revokes = not_forget = 0
    for _, trial in trials:
        if trial.get("failed"):
            failed += 1
            continue
        for probe in trial.get("probe_results") or []:
            if probe["type"] != "deletion":
                continue
            if probe.get("passed") is None:
                unscored += 1
            elif probe["passed"]:
                passes += 1
            else:
                fails += 1
        residue += bool(trial.get("revoked_value_rows"))
        for event in _events(trial, "revoke"):
            revokes += 1
            not_forget += event.get("revoke_path") != "forget"
    out.append({
        "criterion": "kernel and replicated delete completely at H = 0: "
                     "every deletion probe passes, no carrier is left "
                     "and every revoke went through the forget",
        "holds": bool(trials) and passes > 0 and not (
            fails or unscored or failed or residue or not_forget),
        "evidence": f"{len({k for k, _ in trials})} cells: {passes} pass, "
                    f"{fails} fail, {unscored} unscored, {failed} failed "
                    f"trials; {residue} trials with revoked_value_rows; "
                    f"{not_forget} of {revokes} revokes not through the "
                    "forget",
    })

    scoped = [p for key, cell in cells.items()
              if key[1] in LIBRARY_LOCI and key[3] == "writer_scoped"
              for p in _probes(cell["trials"], "deletion", echo=True)
              if p.get("passed") is not None]
    out.append({
        "criterion": "writer_scoped fails some echo user in a kernel or "
                     "replicated cell",
        "holds": any(not p["passed"] for p in scoped),
        "evidence": f"{sum(not p['passed'] for p in scoped)} of "
                    f"{len(scoped)} echo-user deletion probes fail",
    })

    def retired_counts(pred):
        probes = missing = holding = 0
        for _, trial in _trials(cells, pred):
            if trial.get("failed"):
                continue
            for probe in trial.get("probe_results") or []:
                probes += 1
                found = probe.get("retired_in_block")
                missing += found is None
                holding += bool(found)
        return probes, missing, holding

    probes, missing, holding = retired_counts(ref)
    _, _, ns_holding = retired_counts(
        lambda m, l, b, c: l in LIBRARY_LOCI and c == "no_supersession")
    out.append({
        "criterion": "no kernel or replicated block holds a retired row "
                     "at H = 0, and no_supersession puts one in some "
                     "block",
        "holds": probes > 0 and not missing and not holding
        and ns_holding > 0,
        "evidence": f"h0: {holding} of {probes} probes hold one "
                    f"({missing} unrecorded); no_supersession: "
                    f"{ns_holding} probes hold one",
    })

    probes = absent = dropped = unarmed = 0
    for _, trial in _trials(cells, h0_like):
        if trial.get("failed"):
            continue
        # A forget under an ablated scope (no_delete, writer_scoped since
        # Subtask 19) records no tombstone, so it arms no guard.
        forgot = any(event.get("revoke_path") == "forget"
                     and not (event.get("forget") or {}).get("forget_scope")
                     for event in _events(trial, "revoke"))
        for probe in trial.get("probe_results") or []:
            probes += 1
            diagnostics = probe.get("diagnostics") or {}
            if diagnostics.get("after_tombstone") is None:
                absent += 1
            dropped += bool(diagnostics.get("tombstoned_rows"))
            if forgot and not diagnostics.get("tombstoned_forms"):
                unarmed += 1
    out.append({
        "criterion": "the guard was armed and dropped nothing in the "
                     "kernel and replicated cells at H = 0",
        "holds": probes > 0 and not (absent or dropped or unarmed),
        "evidence": f"{probes} probes: {absent} without the guard's "
                    f"stage, {unarmed} unarmed after a forget, "
                    f"{dropped} with a dropped row",
    })

    scrubs = [((event.get("forget") or {}).get("scrubbed") or {})
              .get("messages") or 0
              for key, trial in trials if key[2] == "mem0"
              and not trial.get("failed")
              for event in _events(trial, "revoke")
              if event.get("revoke_path") == "forget"]
    out.append({
        "criterion": "every Mem0 forget at H = 0 scrubbed a message",
        "holds": bool(scrubs) and all(n > 0 for n in scrubs),
        "evidence": f"{sum(n > 0 for n in scrubs)} of {len(scrubs)} "
                    f"forgets ({sum(scrubs)} messages)",
    })
    # Graphiti's history is its episodes (Subtask 16): a forget blanks or
    # deletes every episode that held the value. Only with Graphiti
    # cells, so earlier runs' criteria are unchanged.
    graphiti = [((event.get("forget") or {}).get("scrubbed") or {})
                .get("messages") or 0
                for key, trial in trials if key[2] == "graphiti"
                and not trial.get("failed")
                for event in _events(trial, "revoke")
                if event.get("revoke_path") == "forget"]
    if any(key[2] == "graphiti" for key, _ in trials):
        out.append({
            "criterion": "every Graphiti forget at H = 0 scrubbed an "
                         "episode",
            "holds": bool(graphiti) and all(n > 0 for n in graphiti),
            "evidence": f"{sum(n > 0 for n in graphiti)} of "
                        f"{len(graphiti)} forgets ({sum(graphiti)} "
                        "episodes)",
        })
    return out


CONTRAST_BLOCK = [f"{locus}_{column}" for locus in ("kernel", "replicated")
                  for column in BLOCK]


def _locus_blocks(kernel: dict, replicated: dict,
                  kind: Optional[str] = None) -> dict:
    """The block columns of the kernel and the replicated cell, each
    prefixed with its locus."""
    return {f"{locus}_{column}": value
            for locus, cell in (("kernel", kernel),
                                ("replicated", replicated))
            for column, value in _block_size(
                _cell_probes(cell, kind)).items()}


def contrast_rows(cells: Dict[tuple, dict], model: str,
                  condition: str = "h0") -> List[dict]:
    """Kernel against replicated per backend and probe type, paired by
    user: exact McNemar on the discordant pairs."""
    rows = []
    for backend in ("mem0", "inhouse", "graphiti", "amem"):
        k = cells.get((model, "kernel", backend, condition))
        r = cells.get((model, "replicated", backend, condition))
        if not k or not r:
            continue
        by_user = lambda cell: {t["trial_index"]: t  # noqa: E731
                                for t in cell["trials"]
                                if not t.get("failed")}
        ku, ru = by_user(k), by_user(r)
        for kind in JUDGE_FREE:
            b = c = both = 0
            for i in sorted(set(ku) & set(ru)):
                kp = next((p for p in ku[i]["probe_results"]
                           if p["type"] == kind), None)
                rp = next((p for p in ru[i]["probe_results"]
                           if p["type"] == kind), None)
                if not kp or not rp or kp.get("passed") is None \
                        or rp.get("passed") is None:
                    continue
                both += 1
                b += kp["passed"] and not rp["passed"]
                c += rp["passed"] and not kp["passed"]
            rows.append({"model": model, "backend": backend, "probe": kind,
                         "pairs": both, "kernel_only": b,
                         "replicated_only": c,
                         "p_mcnemar": mcnemar_exact(b, c) if both else None,
                         **_locus_blocks(k, r, kind)})
        if backend == "inhouse":
            same = total = 0
            for i in sorted(set(ku) & set(ru)):
                for kp, rp in zip(ku[i]["probe_results"],
                                  ru[i]["probe_results"]):
                    total += 1
                    same += ((kp.get("diagnostics") or {}).get("block_text")
                             == (rp.get("diagnostics") or {}).get(
                                 "block_text"))
            rows.append({"model": model, "backend": backend,
                         "probe": "identical blocks", "pairs": total,
                         "kernel_only": same, "replicated_only": None,
                         "p_mcnemar": None, **_locus_blocks(k, r)})
    return rows


def integration_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per cell with judged integration scores (failed trials left
    out): ``n``, the ``mean`` with its 95% t-interval (``ci_low`` /
    ``ci_high``), ``sd`` (both None for n < 2, where neither is
    defined) and the share of scores of 4 or more."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        scores = [t.get("integration_score") for t in cell["trials"]
                  if not t.get("failed")
                  and t.get("integration_score") is not None]
        if not scores:
            continue
        # fmean: a float even when the scores average to a whole
        # number, so every mean prints with two decimals.
        mean = statistics.fmean(scores)
        sd = statistics.stdev(scores) if len(scores) > 1 else None
        low, high = t_interval(scores)
        rows.append({"model": model, "locus": locus, "backend": backend,
                     "condition": condition, "n": len(scores),
                     "mean": mean, "ci_low": low, "ci_high": high,
                     "sd": sd,
                     "share_ge_4": sum(s >= 4 for s in scores) / len(scores),
                     **_block_size(_cell_probes(cell, "integration"))})
    return rows


def _key(model, locus, backend, condition) -> dict:
    return {"model": model, "locus": locus, "backend": backend,
            "condition": condition}


def _carries(text: Optional[str], entries) -> bool:
    return any(match_entry(text, entry) for entry in entries or [])


def exposure_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Deletion and privacy at the trial level (known issue 43). A
    probe checks only its own block and answer, so a pass can hide the
    value elsewhere in the trial. Per cell and probe type, over scored
    probes: ``passed``; ``exposed``, the trials whose forbidden value
    appears in any probe's block or answer; and ``passed_exposed``, the
    passes among them."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        for kind in ("deletion", "privacy"):
            n = passed = exposed = passed_exposed = 0
            for trial in cell["trials"]:
                if trial.get("failed"):
                    continue
                probes = trial.get("probe_results") or []
                probe = next((p for p in probes if p["type"] == kind), None)
                if probe is None or probe.get("passed") is None:
                    continue
                forbidden = probe.get("forbidden") or []
                hit = any(_carries(_block(p), forbidden)
                          or _carries(p.get("observed"), forbidden)
                          for p in probes)
                n += 1
                passed += bool(probe["passed"])
                exposed += hit
                passed_exposed += bool(probe["passed"]) and hit
            if n:
                rows.append({**_key(model, locus, backend, condition),
                             "probe": kind, "n": n, "passed": passed,
                             "exposed": exposed,
                             "passed_exposed": passed_exposed})
    return rows


def carrier_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Each failed deletion probe by its carrier (known issue 38): the
    sources of the block rows that hold the revoked value (``target``,
    ``echo``, ``other_fact``, which is a Mem0 fold, ``conversation``,
    ``unknown``), joined with ``+``; ``block, no row`` when the block
    text holds the value but no injected row does; ``answer only`` when
    the block text does not hold it, or is missing (the answer does).
    :func:`stored_carrier_rows` gives what the store kept instead."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        counts = Counter()
        for probe in _probes(cell["trials"], "deletion"):
            if probe.get("passed") is not False:
                continue
            if probe.get("forbidden_in_block"):
                sources = sorted({row.get("source") or "unknown" for row
                                  in probe.get("rows_with_forbidden") or []})
                counts["+".join(sources) or "block, no row"] += 1
            else:
                counts["answer only"] += 1
        for carrier, n in sorted(counts.items()):
            rows.append({**_key(model, locus, backend, condition),
                         "carrier": carrier, "failures": n})
    return rows


def stored_carrier_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Each scored deletion probe, failed or passed, by what the store
    kept (known issue 38): the sources (:func:`probes.row_source`) of
    the rows that still held the revoked value in the listing after the
    history, right before the probes (``revoked_value_rows``, listing
    ``history``), joined with ``+``, or ``none``. A pass with a stored
    carrier is one whose selection left the carrier out of the block:
    the fetch did not return it, or a later stage, such as the cap,
    dropped it. A failure's block may hold fewer carriers than the
    store (:func:`carrier_rows`)."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        counts = defaultdict(lambda: {False: 0, True: 0})
        for trial in cell["trials"]:
            if trial.get("failed"):
                continue
            probe = next((p for p in trial.get("probe_results") or []
                          if p["type"] == "deletion"), None)
            if probe is None or probe.get("passed") is None:
                continue
            values = {entry.get("value") if isinstance(entry, dict)
                      else entry for entry in probe.get("forbidden") or []}
            sources = {row_source(row, probe)
                       for row in trial.get("revoked_value_rows") or []
                       if row.get("listing") == "history"
                       and row.get("value") in values}
            stored = "+".join(sorted(sources)) or "none"
            counts[stored][bool(probe["passed"])] += 1
        for stored, split in sorted(counts.items()):
            rows.append({**_key(model, locus, backend, condition),
                         "stored": stored, "failures": split[False],
                         "passes": split[True]})
    return rows


def _removed_ids(trial: dict) -> set:
    """The ids of the rows the trial's history removed: every row its
    revokes deleted (each session's ``deleted_ids``) and every row its
    writes swept (``swept_ids``)."""
    removed = set()
    for session in trial.get("sessions") or []:
        removed.update(str(i) for i in session.get("deleted_ids") or [])
        for event in session.get("events") or []:
            removed.update(str(i) for i in event.get("swept_ids") or [])
    return removed


def _target_removed(trial: dict, probe: dict, removed: set) -> bool:
    """Whether the history removed every row the probe's target event
    stored: the rows listed after its session (``memory_ids``) and the
    ids its reply named (``reported_ids``). False for a target that
    stored none."""
    target = str(probe.get("target_event"))
    for event in _events(trial):
        if str(event.get("event_id")) == target:
            ids = {str(i) for key in ("memory_ids", "reported_ids")
                   for i in event.get(key) or []}
            return bool(ids) and ids <= removed
    return False


def miss_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Failed recall, recency and contradiction probes by where the
    expected value was: ``target_forgotten`` (not in the block, and a
    forget or a sweep deleted every row the target event stored, as when
    Mem0 folded a forgotten value into the target's row),
    ``not_in_block`` (any other failure outside the block: never stored,
    or selection lost it),
    ``in_block_no_row`` (the block text holds it, no injected row does),
    ``conversation_only`` (only the consumer's own earlier answers held
    it) or ``in_writer_row`` (a writer's row held it). ``named``: the
    failures whose answer named the expected value too (recency and
    contradiction: they failed on the stale value)."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        for kind in ("recall", "recency", "contradiction"):
            probes = [(trial, p) for trial in cell["trials"]
                      if not trial.get("failed")
                      for p in _probes([trial], kind)
                      if p.get("passed") is False]
            if not probes:
                continue
            counts = Counter()
            for trial, probe in probes:
                sources = {row.get("source") for row
                           in probe.get("rows_with_expected") or []}
                if not probe.get("expected_in_block"):
                    removed = _target_removed(trial, probe,
                                              _removed_ids(trial))
                    counts["target_forgotten" if removed
                           else "not_in_block"] += 1
                elif not sources:
                    counts["in_block_no_row"] += 1
                elif sources == {"conversation"}:
                    counts["conversation_only"] += 1
                else:
                    counts["in_writer_row"] += 1
            rows.append({**_key(model, locus, backend, condition),
                         "probe": kind, "failed": len(probes),
                         "named": sum(1 for _, p in probes
                                      if p.get("expected_present")),
                         "target_forgotten": counts["target_forgotten"],
                         "not_in_block": counts["not_in_block"],
                         "in_block_no_row": counts["in_block_no_row"],
                         "conversation_only": counts["conversation_only"],
                         "in_writer_row": counts["in_writer_row"]})
    return rows


def slot_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Contradiction per slot (known issue 44). Under revision 3 each
    slot asks a question that leans to each statement, alternated
    between its users; the results do not record the lean (join
    ``users_v2`` by ``probe_id``). ``lenient``: the answers that name
    the later value."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        by_slot = defaultdict(list)
        for probe in _probes(cell["trials"], "contradiction"):
            if probe.get("passed") is not None:
                by_slot[probe.get("slot") or ""].append(probe)
        for slot, probes in sorted(by_slot.items()):
            rows.append({**_key(model, locus, backend, condition),
                         "slot": slot, "n": len(probes),
                         "passed": sum(1 for p in probes if p["passed"]),
                         "lenient": sum(1 for p in probes
                                        if p.get("expected_present"))})
    return rows


def earlier_answer_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Recency and contradiction, split by whether one of the
    consumer's earlier answers in the block carries the stale value (a
    ``conversation`` row among ``rows_with_stale``). The probes are asked
    in one session, and each answer is stored, so a later probe's block
    can hold an earlier answer that states the old value as current."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        for kind in ("recency", "contradiction"):
            split = {True: [0, 0], False: [0, 0]}
            for probe in _probes(cell["trials"], kind):
                if probe.get("passed") is None:
                    continue
                stale = any(row.get("source") == "conversation"
                            for row in probe.get("rows_with_stale") or [])
                split[stale][0] += 1
                split[stale][1] += bool(probe["passed"])
            if split[True][0] + split[False][0]:
                rows.append({**_key(model, locus, backend, condition),
                             "probe": kind,
                             "with_stale_answer": split[True][0],
                             "passed_with": split[True][1],
                             "without": split[False][0],
                             "passed_without": split[False][1]})
    return rows


BASE_EVENTS = ("base_profile", "base_task")


def _mean(values: List) -> Optional[float]:
    """The mean, or None when there is nothing to average or a value is
    missing."""
    if not values or None in values:
        return None
    return float(statistics.mean(values))


def _integration_probes(cell: dict):
    """``(trial, probe, injected rows, {base event: in the block},
    score)`` for each integration probe of a trial that did not fail.
    The base events are the user's ``base_profile`` and ``base_task``
    events, which the judge scores the answer against; a row counts
    when its ``provenance_event`` is one of them. The score is the
    probe's, else the trial's."""
    for trial in cell["trials"]:
        if trial.get("failed"):
            continue
        probe = next((p for p in trial.get("probe_results") or []
                      if p["type"] == "integration"), None)
        if probe is None:
            continue
        events = {kind: set() for kind in BASE_EVENTS}
        for session in trial.get("sessions") or []:
            for event in session.get("events") or []:
                if event.get("fact_key") in events:
                    events[event["fact_key"]].add(event.get("event_id"))
        injected = (probe.get("diagnostics") or {}).get(
            "injected_memories") or []
        in_block = {kind: any(row.get("provenance_event") in ids
                              for row in injected)
                    for kind, ids in events.items()}
        score = probe.get("integration_score")
        if score is None:
            score = trial.get("integration_score")
        yield trial, probe, injected, in_block, score


def integration_block_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """The integration probe's block per cell (known issue 45): the
    mean number of rows, of the consumer's own conversation rows (its
    earlier answers) and of writer rows; how often the budget bound;
    how often a row of the user's ``base_task`` event, of its
    ``base_profile`` event, and of both reached the block; and the mean
    integration score with and without a base task row
    (:func:`integration_base_rows` splits it by both)."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        sizes, own, budget, profile, both = [], [], 0, 0, 0
        scores = {True: [], False: []}
        for _, probe, injected, in_block, score in _integration_probes(
                cell):
            sizes.append(len(injected))
            own.append(sum(1 for row in injected
                           if row.get("memory_type") == "conversation"))
            budget += bool(probe.get("budget_bound"))
            profile += in_block["base_profile"]
            both += all(in_block.values())
            scores[in_block["base_task"]].append(score)
        if not sizes:
            continue
        rows.append({**_key(model, locus, backend, condition),
                     "n": len(sizes), "rows": _mean(sizes),
                     "own_rows": _mean(own),
                     "writer_rows": _mean(sizes) - _mean(own),
                     "budget_bound": None if locus == "native" else budget,
                     "base_task_in_block": len(scores[True]),
                     "base_profile_in_block": profile,
                     "both_in_block": both,
                     "score_with": _mean(scores[True]),
                     "score_without": _mean(scores[False])})
    return rows


def integration_base_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """The integration score per cell by ``base_rows``, how many of the
    user's two base events (profile, task context) have a row in the
    block (0, 1 or 2; known issue 45): ``n`` and the mean ``score``
    (None when a score is missing). Only the counts that occur."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        by_count = defaultdict(list)
        for _, _, _, in_block, score in _integration_probes(cell):
            by_count[sum(in_block.values())].append(score)
        for count, scores in sorted(by_count.items()):
            rows.append({**_key(model, locus, backend, condition),
                         "base_rows": count, "n": len(scores),
                         "score": _mean(scores)})
    return rows


def forget_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per kernel and replicated cell (Amendment 4): the revokes and how
    they went (through the forget or the owner), what the forgets
    deleted by reason, how many rows of other agents and how many of
    the revoking writer's rows other than the slot's (``same_writer``:
    deleted by a value or an alias, as a Mem0 fold of the value into
    another of its facts' rows is), the forgets that found no value,
    the history scrub's counts, and what later writes swept or had
    suppressed."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        if locus not in LIBRARY_LOCI:
            continue
        row = {**_key(model, locus, backend, condition), "revokes": 0,
               "forget": 0, "deleted": 0, "fact_key": 0, "value": 0,
               "alias": 0, "entity": 0, "derived": 0, "other_agents": 0,
               "same_writer": 0,
               "no_values": 0, "messages": 0, "history": 0, "swept": 0,
               "suppressed": 0, "scoped": 0}
        for trial in cell["trials"]:
            if trial.get("failed"):
                continue
            for event in _events(trial, "revoke"):
                row["revokes"] += 1
                report = event.get("forget")
                if event.get("revoke_path") != "forget" or not report:
                    continue
                if report.get("forget_scope"):
                    # The kernel's forget under an ablated scope (no_delete,
                    # writer_scoped since Subtask 19): counted apart.
                    row["scoped"] += 1
                    continue
                row["forget"] += 1
                for entry in report.get("deleted") or []:
                    row["deleted"] += 1
                    reason = entry.get("reason")
                    if reason in ("fact_key", "value", "alias", "entity",
                                  "derived"):
                        row[reason] += 1
                    other = entry.get("owner_agent") != event.get("writer")
                    row["other_agents"] += other
                    row["same_writer"] += (
                        not other and reason in ("value", "alias"))
                row["no_values"] += not report.get("values_count")
                scrubbed = report.get("scrubbed") or {}
                row["messages"] += scrubbed.get("messages") or 0
                row["history"] += scrubbed.get("history") or 0
            for event in _events(trial):
                row["swept"] += len(event.get("swept_ids") or [])
                row["suppressed"] += bool(event.get("suppressed"))
        rows.append(row)
    return rows


def supersession_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per cell (Amendment 4): the rows writes retired, the earlier
    statements' rows after the history (``retired_rows``, from the
    dataset) and how many carry a mark, the probes whose block held a
    retired row, and the rows the selection excluded as retired."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        row = {**_key(model, locus, backend, condition), "retired": 0,
               "earlier_rows": 0, "marked": 0, "probes": 0,
               "retired_in_block": 0, "excluded": 0}
        for trial in cell["trials"]:
            if trial.get("failed"):
                continue
            for event in _events(trial):
                row["retired"] += len(event.get("retired_ids") or [])
            for earlier in trial.get("retired_rows") or []:
                row["earlier_rows"] += 1
                row["marked"] += bool(earlier.get("superseded_by"))
            for probe in trial.get("probe_results") or []:
                row["probes"] += 1
                row["retired_in_block"] += bool(
                    probe.get("retired_in_block"))
                row["excluded"] += len(
                    (probe.get("diagnostics") or {}).get("superseded_rows")
                    or [])
        rows.append(row)
    return rows


def backend_invalidation_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per Graphiti cell (Subtask 16): Graphiti's own invalidations, kept
    apart from the kernel's supersession and credited to no locus: the
    rows after the history it marked invalid, and the probes whose block
    held one. No rows for the other backends."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        if backend != "graphiti":
            continue
        row = {**_key(model, locus, backend, condition),
               "invalidated_rows": 0, "probes": 0,
               "invalidated_in_block": 0}
        for trial in cell["trials"]:
            if trial.get("failed"):
                continue
            row["invalidated_rows"] += len(
                trial.get("backend_invalidated_rows") or [])
            for probe in trial.get("probe_results") or []:
                row["probes"] += 1
                row["invalidated_in_block"] += bool(
                    probe.get("backend_invalidated_in_block"))
        rows.append(row)
    return rows


def writes_without_fact_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per Graphiti, A-MEM and Mem0 cell (Amendments 5, 8 and 9): the
    scored trials, those with a write the backend stored no row from
    (``writes_without_fact``: a lost memory, not a failed trial), those
    writes, and the probes whose target was one, with their passes. No
    rows for the other backends."""
    rows = []
    for (model, locus, backend, condition), cell in sorted(cells.items()):
        if backend not in EMPTY_WRITE_IS_LOSS:
            continue
        row = {**_key(model, locus, backend, condition), "trials": 0,
               "with_one": 0, "writes_without_fact": 0,
               "probes_on_them": 0, "passed_on_them": 0}
        for trial in cell["trials"]:
            if trial.get("failed"):
                continue
            lost = set(trial.get("writes_without_fact") or [])
            row["trials"] += 1
            row["with_one"] += bool(lost)
            row["writes_without_fact"] += len(lost)
            for probe in trial.get("probe_results") or []:
                if probe.get("target_event") in lost:
                    row["probes_on_them"] += 1
                    row["passed_on_them"] += bool(probe.get("passed"))
        rows.append(row)
    return rows


def readings(cells: Dict[tuple, dict]) -> Dict[str, List[dict]]:
    """Every reading above, by name, each row with the block columns
    (of the integration probes for the integration readings)."""
    found = _readings(cells)
    return {name: with_block_size(
                rows, cells,
                "integration" if name.startswith("integration") else None)
            for name, rows in found.items()}


def _readings(cells: Dict[tuple, dict]) -> Dict[str, List[dict]]:
    return {"forgets": forget_rows(cells),
            "supersession": supersession_rows(cells),
            "backend_invalidations": backend_invalidation_rows(cells),
            "writes_without_fact": writes_without_fact_rows(cells),
            "exposure": exposure_rows(cells),
            "carriers": carrier_rows(cells),
            "stored_carriers": stored_carrier_rows(cells),
            "misses": miss_rows(cells),
            "slots": slot_rows(cells),
            "earlier_answers": earlier_answer_rows(cells),
            "integration_blocks": integration_block_rows(cells),
            "integration_base_rows": integration_base_rows(cells)}


CELL_KEYS = ["model", "locus", "backend", "condition"]
READING_SECTIONS = [
    ("forgets", "Revokes and the forget (Amendment 4)",
     "Per kernel and replicated cell: revokes, those that went through "
     "the forget, the rows the forgets deleted (by reason: the slot's "
     "`fact_key`, a `value` or an `alias`, or an `entity`: a Graphiti "
     "scrub deleted it with an entity a form names, or `derived`: an "
     "A-MEM scrub deleted it because its derived text carried a form; "
     "`other_agents`: rows of "
     "agents other than the revoking writer; `same_writer`: rows of the "
     "revoking writer deleted by a value or an alias, rows of its other "
     "facts, as a Mem0 fold is), forgets that found no value, the "
     "history scrub (Mem0: `messages` deleted, `history` records "
     "cleared; A-MEM: `history` counts the carrier notes it deleted, as "
     "`derived` does), "
     "rows later writes `swept` and writes `suppressed`, and `scoped`: "
     "revokes through a forget the kernel ran under an ablated scope "
     "(no_delete, writer_scoped since Subtask 19; counted in no other "
     "column).",
     ["revokes", "forget", "deleted", "fact_key", "value", "alias",
      "entity", "derived", "other_agents", "same_writer", "no_values",
      "messages",
      "history", "swept", "suppressed", "scoped"]),
    ("supersession", "Supersession (Amendment 4)",
     "`retired`: rows writes marked retired; `earlier_rows`: the "
     "earlier statements' rows after the history (from the dataset) and "
     "how many carry a mark (`marked`); probes whose block held a "
     "retired row; rows the selection excluded as retired.",
     ["retired", "earlier_rows", "marked", "probes", "retired_in_block",
      "excluded"]),
    ("backend_invalidations", "Graphiti's own invalidations (Subtask 16)",
     "Graphiti marks a fact invalid when it judges a later one "
     "contradicts it: its own supersession, kept apart from the "
     "kernel's above and credited to no locus. `invalidated_rows`: rows "
     "after the history it marked invalid; probes whose block held one.",
     ["invalidated_rows", "probes", "invalidated_in_block"]),
    ("writes_without_fact",
     "Writes that stored no fact (Amendments 5, 8, 9)",
     "Graphiti sometimes extracts a write's entities but no fact, and "
     "its search returns facts only: a write Graphiti stored no fact "
     "from is a lost memory, not a failed trial (and an A-MEM write "
     "that stored no note, Amendment 8, and a Mem0 write that stored "
     "nothing with no failure Mem0 swallowed, Amendment 9). `trials`: "
     "scored "
     "trials; `with_one`: scored trials with such a write; "
     "`writes_without_fact`: those writes; `probes_on_them`: probes "
     "whose target was one, and `passed_on_them`.",
     ["trials", "with_one", "writes_without_fact", "probes_on_them",
      "passed_on_them"]),
    ("exposure", "Trial-level exposure (deletion, privacy)",
     "A probe checks only its own block and answer. `exposed`: trials "
     "whose forbidden value appears in any probe's block or answer; "
     "`passed_exposed`: passes among them.",
     ["probe", "n", "passed", "exposed", "passed_exposed"]),
    ("carriers", "Deletion failures by carrier",
     "The sources of the block rows that held the revoked value "
     "(`other_fact` is a Mem0 fold); `block, no row`: the block text "
     "held it but no row did; `answer only`: the block text did not "
     "hold it (only the answer did).",
     ["carrier", "failures"]),
    ("stored_carriers", "Deletion probes by what the store kept",
     "The sources of the rows that still held the revoked value after "
     "the history, right before the probes (`revoked_value_rows`), or "
     "`none`. A pass with a stored carrier is one whose selection left "
     "it out of the block: the fetch did not return it, or a later "
     "stage, such as the cap, dropped it.",
     ["stored", "failures", "passes"]),
    ("misses", "Failures: where the expected value was",
     "Failed recall, recency and contradiction probes by where the "
     "expected value was: `target_forgotten` (not in the block, and a "
     "forget or a sweep deleted every row the target event stored, as "
     "when Mem0 folded a forgotten value into it), `not_in_block` (any "
     "other failure outside the block: never stored, or selection lost "
     "it), `in_block_no_row` (the block text holds it, no injected row "
     "does), `conversation_only` (only the consumer's own earlier "
     "answers held it), `in_writer_row` (a writer's row held it). "
     "`named`: failures whose answer named the expected value too (they "
     "failed on the stale value).",
     ["probe", "failed", "named", "target_forgotten", "not_in_block",
      "in_block_no_row", "conversation_only", "in_writer_row"]),
    ("slots", "Contradiction by slot",
     "`lenient`: answers that name the later value.",
     ["slot", "n", "passed", "lenient"]),
    ("earlier_answers",
     "Recency and contradiction: the stale value in an earlier answer",
     "Split by whether one of the consumer's earlier answers in the "
     "block carries the stale value.",
     ["probe", "with_stale_answer", "passed_with", "without",
      "passed_without"]),
    ("integration_blocks", "The integration probe's block",
     "Means per probe: rows, the consumer's own rows (its earlier "
     "answers) and writer rows. Probes whose block holds a row of the "
     "user's base task context, of its base profile, and of both; the "
     "mean score with and without a base task row.",
     ["n", "rows", "own_rows", "writer_rows", "budget_bound",
      "base_task_in_block", "base_profile_in_block", "both_in_block",
      "score_with", "score_without"]),
    ("integration_base_rows",
     "Integration score by the base rows in the block",
     "The judge scores the answer against the base profile and the "
     "base task context. `base_rows`: how many of the two have a row "
     "in the block.",
     ["base_rows", "n", "score"]),
]


# -- the decision probe (Amendment 10) -------------------------------------------

DECISION_KEYS = ["items", "correct", "accuracy", "ci_low", "ci_high",
                 *DECISION_ERRORS, "turn_errors", "echo_d1",
                 "echo_d1_revoked"]


def _echo_user(trial: dict) -> bool:
    """Whether the trial's user has an echo: its deletion probe names
    an echo event."""
    deletion = next((p for p in trial.get("probe_results") or []
                     if p["type"] == "deletion"), None)
    return bool((deletion or {}).get("echo_event"))


def decision_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per cell with decision items: items scored (of trials that did
    not fail, without a turn error), correct, accuracy with its 95%
    Wilson interval, the count of each error and its share of the
    items scored (``<error>_share``), the items with a turn error
    (recorded, not scored), and, for echo users' ``d1`` items, how many
    there are and how many picked the revoked option."""
    rows = []
    for key, cell in sorted(cells.items()):
        trials = [t for t in cell["trials"] if not t.get("failed")]
        items = [r for t in trials for r in t.get("decision_results") or []]
        if not items:
            continue
        summary = decision_summary(items)
        echo_d1 = [r for t in trials if _echo_user(t)
                   for r in t.get("decision_results") or []
                   if r["decision_id"].endswith("-d1")
                   and r.get("passed") is not None
                   and not r.get("turn_error")]
        ci = summary["ci"] or (None, None)
        rows.append({**_key(*key), "items": summary["n"],
                     "correct": summary["passed"],
                     "accuracy": summary["accuracy"],
                     "ci_low": ci[0], "ci_high": ci[1],
                     **{e: summary[e]["k"] for e in DECISION_ERRORS},
                     **{f"{e}_share": summary[e]["share"]
                        for e in DECISION_ERRORS},
                     "turn_errors": sum(1 for r in items
                                        if r.get("turn_error")),
                     "echo_d1": len(echo_d1),
                     "echo_d1_revoked": sum(1 for r in echo_d1
                                            if r.get("error") == "revoked")})
    return rows


def _with_shares(row: dict) -> dict:
    """A decision row for the table: each error as "k (share)"."""
    out = dict(row)
    for e in DECISION_ERRORS:
        share = row.get(f"{e}_share")
        out[e] = (f"{row[e]} ({share:.2f})" if share is not None
                  else row.get(e))
    return out


PICK_KEYS = ["item", "items", "picked", *PICK_KINDS, "letters",
             "letters_p", "correct_letters", "correct_letters_p"]


def pick_rows(cells: Dict[tuple, dict]) -> List[dict]:
    """Per cell with decision items, one row per item (``d1``, ``d2``)
    and one pooled: the picks by option kind and by letter
    (:func:`metrics.decision_picks`), with the cell's ``no_letter``,
    ``multiple_letters`` and turn errors on each row."""
    rows = []
    for key, cell in sorted(cells.items()):
        items = [r for t in cell["trials"] if not t.get("failed")
                 for r in t.get("decision_results") or []]
        if not items:
            continue
        picks = decision_picks(items)
        for group in ("d1", "d2", "pooled"):
            g = picks[group]
            rows.append({**_key(*key), "item": group, "items": g["items"],
                         "picked": g["picked"], "kinds": g["kinds"],
                         "letters": g["letters"],
                         "letters_p": g["letters_p"],
                         "correct_letters": g["correct_letters"],
                         "correct_letters_p": g["correct_letters_p"],
                         **{k: picks[k] for k in (
                             "no_letter", "multiple_letters",
                             "turn_errors")}})
    return rows


def _pick_cells(row: dict) -> dict:
    """A picks row for the table: each kind as "k (share) [low, high]",
    each letter count as "A/B/C/D"."""
    out = dict(row)
    for kind in PICK_KINDS:
        k = row["kinds"][kind]
        out[kind] = (f"{k['k']} ({k['share']:.2f}) "
                     f"[{k['ci'][0]:.2f}, {k['ci'][1]:.2f}]"
                     if k["share"] is not None else str(k["k"]))
    for name in ("letters", "correct_letters"):
        out[name] = "/".join(str(row[name][x]) for x in LETTERS)
    return out


def _pooled(rows: List[dict], pred) -> dict:
    picked = [r for r in rows if pred(r)]
    out = {k: sum(r[k] for r in picked)
           for k in ("items", "correct", *DECISION_ERRORS, "echo_d1",
                     "echo_d1_revoked")}
    out["cells"] = len(picked)
    out["accuracy"] = (out["correct"] / out["items"] if out["items"]
                       else None)
    return out


def decision_criteria(cells: Dict[tuple, dict]) -> List[dict]:
    """Amendment 10's functional criteria D1-D5 over the cells present:
    ``holds`` True or False, None when a criterion's cells are absent."""
    rows = decision_rows(cells)

    def loci_of(cond):
        return {(r["model"], r["locus"], r["backend"])
                for r in rows if r["condition"] == cond}

    def at(cond, loci=None, locus=None):
        return _pooled(rows, lambda r: r["condition"] == cond
                       and (loci is None or (r["model"], r["locus"],
                                             r["backend"]) in loci)
                       and (locus is None or r["locus"] in locus))

    out = []
    full = at("h0")
    out.append({"criterion": "D1 full system: pooled accuracy >= 0.6",
                "holds": None if not full["items"]
                else full["accuracy"] >= 0.6,
                "evidence": f"{full['correct']} of {full['items']} over "
                            f"{full['cells']} cells"})
    floor = at("no_memory")
    out.append({"criterion": "D2 no_memory: pooled accuracy in "
                             "[0.10, 0.45]",
                "holds": None if not floor["items"]
                else 0.10 <= floor["accuracy"] <= 0.45,
                "evidence": f"{floor['correct']} of {floor['items']} over "
                            f"{floor['cells']} cells"})
    ns_loci = loci_of("no_supersession")
    ns, ns_full = at("no_supersession"), at("h0", ns_loci)
    out.append({"criterion": "D3 no_supersession: more stale errors than "
                             "the same loci's full system",
                "holds": None if not ns["items"] or not ns_full["items"]
                else ns["stale"] > ns_full["stale"],
                "evidence": f"stale {ns['stale']} of {ns['items']} vs "
                            f"{ns_full['stale']} of {ns_full['items']}"})
    ws_loci = loci_of("writer_scoped")
    ws, ws_full = at("writer_scoped"), at("h0", ws_loci)
    out.append({"criterion": "D4 writer_scoped: >= 1 revoked error among "
                             "echo users' d1 items, 0 in the full system",
                "holds": None if not ws["echo_d1"] or not ws_full["echo_d1"]
                else ws["echo_d1_revoked"] >= 1
                and ws_full["echo_d1_revoked"] == 0,
                "evidence": f"revoked {ws['echo_d1_revoked']} of "
                            f"{ws['echo_d1']} vs "
                            f"{ws_full['echo_d1_revoked']} of "
                            f"{ws_full['echo_d1']}"})
    agents = at("wrong_user", locus=("replicated", "native"))
    kernel = at("wrong_user", locus=("kernel",))
    out.append({"criterion": "D5 wrong_user: >= 1 foreign error in the "
                             "replicated and native cells, 0 in the "
                             "kernel's",
                "holds": None if not agents["items"] or not kernel["items"]
                else agents["foreign"] >= 1 and kernel["foreign"] == 0,
                "evidence": f"foreign {agents['foreign']} of "
                            f"{agents['items']} vs {kernel['foreign']} of "
                            f"{kernel['items']}"})
    return out


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def table(rows: List[dict], keys: List[str]) -> str:
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(k)) for k in keys)
                     + " |")
    return "\n".join(lines)


def markdown(cells, rows, binding, checks, contrasts, integration,
             extra: Optional[Dict[str, List[dict]]] = None,
             decisions: Optional[List[dict]] = None,
             decision_checks: Optional[List[dict]] = None,
             picks: Optional[List[dict]] = None) -> str:
    """The report: the pass matrix and the cap and budget table, then
    the criteria, the contrasts, the integration rows, the readings
    (``extra``, as :func:`readings` returns them) and the decision
    probe's rows, criteria and picks, each when given."""
    out = ["# Benchmark v2 analysis", "",
           f"{len(cells)} cells, "
           f"{sum(len(c['trials']) for c in cells.values())} user-trials, "
           f"{sum(1 for c in cells.values() for t in c['trials'] if t.get('failed'))} failed.",
           "", "Every table but the criteria ends with `block_tokens` "
           "and `block_rows`: the mean block, in tokens and in rows, of "
           "a set of the row's cell's probes. In the pass matrix, the "
           "row's own probes (a deletion row split by echo, its "
           "split's); in the kernel-against-replicated table, the row's "
           "probe type, per locus (all probes for `identical blocks`); "
           "in the integration table and the integration readings, the "
           "cell's integration probes; elsewhere, the row's probe type "
           "where the row names one, else all of the cell's probes. A "
           "reading's row that splits a cell's probes further (a slot, "
           "a carrier, a count of base rows) shows its set's mean, not "
           "its own.",
           "", "## Per-probe pass matrix", "",
           "Pass rates with 95% Wilson intervals; recency and "
           "contradiction also give the lenient rate (the new value "
           "named, stale or not), how many answers named both values "
           "and how many of those named the stale one as past. "
           "`contaminated`: a value reached the block only through the "
           "consumer's own conversation rows.", "",
           table(rows, ["model", "locus", "backend", "condition", "probe",
                        "passed", "n", "rate", "ci_low", "ci_high",
                        "lenient", "names_both", "named_as_past",
                        "in_block", "in_answer", "contaminated",
                        "cap_bound", "budget_bound", "probes"] + BLOCK), "",
           "## Cap and budget", "",
           table(binding, ["model", "locus", "backend", "condition",
                           "probes", "cap_bound", "budget_bound",
                           "tokens_median", "tokens_max"] + BLOCK), ""]
    if checks:
        out += ["## Functional check criteria", "",
                table(checks, ["criterion", "holds", "evidence"]), ""]
    if contrasts:
        out += ["## Kernel against replicated (paired over users)", "",
                table(contrasts, ["model", "backend", "probe", "pairs",
                                  "kernel_only", "replicated_only",
                                  "p_mcnemar"] + CONTRAST_BLOCK), ""]
    if integration:
        out += ["## Integration (judge v2)", "",
                "The mean with its 95% t-interval (none for n < 2).", "",
                table(integration, ["model", "locus", "backend",
                                    "condition", "n", "mean", "ci_low",
                                    "ci_high", "sd", "share_ge_4"]
                      + BLOCK), ""]
    for name, title, note, keys in READING_SECTIONS:
        found = (extra or {}).get(name)
        if found:
            out += [f"## {title}", "", note, "",
                    table(found, CELL_KEYS + keys + BLOCK), ""]
    if decisions:
        out += ["## Decision probe (Amendment 10)", "",
                "Two items per user, four options each (chance 0.25), "
                "scored exactly from the letter named. Accuracy with its "
                "95% Wilson interval; each error as its count and (its "
                "share of the items scored); `turn_errors`, items with a "
                "turn error (recorded, not scored); `echo_d1`, echo "
                "users' d1 items, and how many picked the revoked "
                "option.", "",
                table([_with_shares(r) for r in decisions],
                      CELL_KEYS + DECISION_KEYS), "",
                "### Functional criteria D1-D5", "",
                table(decision_checks or [],
                      ["criterion", "holds", "evidence"]), ""]
    if picks:
        out += ["### Picks by option kind and letter", "",
                "Of the items scored, those that named one letter "
                "(`picked`), by the kind of the option named (chance "
                "0.25 each): count (share) [95% Wilson interval]; "
                "`must_not_use` is `revoked` on d1 and `private` on d2. "
                "Letters picked and the items' correct letters as "
                "A/B/C/D, each with a chi-square test's p against "
                "uniform.", "",
                table([_pick_cells(r) for r in picks],
                      CELL_KEYS + PICK_KEYS + ["no_letter",
                                               "multiple_letters",
                                               "turn_errors"]), ""]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--markdown")
    parser.add_argument("--json")
    parser.add_argument("--no-criteria", action="store_true",
                        help="skip the functional check's criteria")
    args = parser.parse_args(argv)
    cells = load(Path(args.root))
    rows, binding = cell_rows(cells), binding_rows(cells)
    checks = [] if args.no_criteria else criteria(cells)
    models = sorted({key[0] for key in cells})
    contrasts = [r for m in models for r in contrast_rows(cells, m)]
    integration = integration_rows(cells)
    extra = readings(cells)
    decisions = decision_rows(cells)
    decision_checks = decision_criteria(cells) if decisions else []
    picks = pick_rows(cells)
    text = markdown(cells, rows, binding, checks, contrasts, integration,
                    extra, decisions, decision_checks, picks)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text)
    if args.json:
        data = {
            "rows": rows, "binding": binding, "criteria": checks,
            "contrasts": contrasts, "integration": integration,
            "readings": extra,
        }
        if decisions:
            data.update(decisions=decisions,
                        decision_criteria=decision_checks,
                        decision_picks=picks)
        Path(args.json).write_text(json.dumps(data, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
