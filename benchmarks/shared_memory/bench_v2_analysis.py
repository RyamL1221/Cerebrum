"""Analyze benchmark v2 runs (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Functional check and smoke").

Reads ``<root>/<model>/<phase>/<condition>_<method>/results_<method>.json``
as AIOS ``scripts/run_bench_v2.sh`` writes them and reports:

- the per-probe pass matrix (locus x backend x condition x probe type),
  deletion split into echo and non-echo users, with 95% Wilson
  intervals, the lenient recency and contradiction rates, and how often
  the cap and the budget bound;
- the functional check's criteria, each with its evidence (since
  Amendment 4 the budget's binding is reported, not required, and the
  library's deletion, supersession and guard have criteria of their
  own);
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

from benchmarks.shared_memory.probes import (
    match_entry, mcnemar_exact, row_source, t_interval, wilson,
)

JUDGE_FREE = ("deletion", "privacy", "recall", "recency", "contradiction")
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
}
# The driver's kernel phases; "_ns" runs the no_supersession control
# in a kernel of its own (Amendment 4).
PHASE_BACKEND = {"kmem0": "mem0", "kinh": "inhouse",
                 "kmem0_ns": "mem0", "kinh_ns": "inhouse"}
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


def _rate(passed: int, n: int) -> dict:
    if not n:
        return {"passed": passed, "n": n, "rate": None, "ci_low": None,
                "ci_high": None}
    low, high = wilson(passed, n)
    return {"passed": passed, "n": n, "rate": passed / n, "ci_low": low,
            "ci_high": high}


def _probes(trials: List[dict], kind: str, echo: Optional[bool] = None):
    out = []
    for trial in trials:
        if trial.get("failed"):
            continue
        for probe in trial.get("probe_results") or []:
            if probe["type"] != kind:
                continue
            if echo is not None and bool(probe.get("echo_event")) != echo:
                continue
            out.append(probe)
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
    no_cap = [key for key, (_, cap, _) in sorted(bound.items()) if not cap]
    out.append({
        "criterion": "the cap binds in some probe of every kernel and "
                     "replicated cell (H = 0 and H = 2)",
        "holds": bool(bound) and not no_cap,
        "evidence": "; ".join(f"{l} {b}: {cap} of {n}"
                              for (m, l, b), (n, cap, _)
                              in sorted(bound.items()))
        + (f"; cells without a binding cap: {no_cap}" if no_cap else ""),
    })
    budget = sum(budget for (m, l, b), (_, _, budget) in bound.items()
                 if b == "inhouse")
    # Amendment 4: reported, not required ("holds" is None).
    out.append({
        "criterion": "the budget's binding in kernel and replicated "
                     "in-house cells (H = 0 and H = 2): reported, not "
                     "required",
        "holds": None,
        "evidence": f"{budget} probes with a binding budget",
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
    """Amendment 4's criteria, at H = 0 in the kernel and replicated
    cells on both backends: deletion is complete and goes through the
    forget, and writer_scoped fails some echo user; no block holds a
    retired row, and no_supersession puts one in some block; the guard
    was armed and dropped nothing; every Mem0 forget scrubbed a
    message. A failed trial or an unscored probe counts against a
    criterion, never for it."""
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
        forgot = any(event.get("revoke_path") == "forget"
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
    return out


def contrast_rows(cells: Dict[tuple, dict], model: str,
                  condition: str = "h0") -> List[dict]:
    """Kernel against replicated per backend and probe type, paired by
    user: exact McNemar on the discordant pairs."""
    rows = []
    for backend in ("mem0", "inhouse"):
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
                         "p_mcnemar": mcnemar_exact(b, c) if both else None})
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
                         "p_mcnemar": None})
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
                     "share_ge_4": sum(s >= 4 for s in scores) / len(scores)})
    return rows


def _key(model, locus, backend, condition) -> dict:
    return {"model": model, "locus": locus, "backend": backend,
            "condition": condition}


def _carries(text: Optional[str], entries) -> bool:
    return any(match_entry(text, entry) for entry in entries or [])


def _block(probe: dict) -> Optional[str]:
    return (probe.get("diagnostics") or {}).get("block_text")


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
    """Contradiction per slot (known issue 44): in some slots the
    question repeats the earlier statement's words. ``lenient``: the
    answers that name the later value."""
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
               "alias": 0, "other_agents": 0, "same_writer": 0,
               "no_values": 0, "messages": 0, "history": 0, "swept": 0,
               "suppressed": 0}
        for trial in cell["trials"]:
            if trial.get("failed"):
                continue
            for event in _events(trial, "revoke"):
                row["revokes"] += 1
                report = event.get("forget")
                if event.get("revoke_path") != "forget" or not report:
                    continue
                row["forget"] += 1
                for entry in report.get("deleted") or []:
                    row["deleted"] += 1
                    reason = entry.get("reason")
                    if reason in ("fact_key", "value", "alias"):
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


def readings(cells: Dict[tuple, dict]) -> Dict[str, List[dict]]:
    """Every reading above, by name."""
    return {"forgets": forget_rows(cells),
            "supersession": supersession_rows(cells),
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
     "`fact_key`, a `value` or an `alias`; `other_agents`: rows of "
     "agents other than the revoking writer; `same_writer`: rows of the "
     "revoking writer deleted by a value or an alias, rows of its other "
     "facts, as a Mem0 fold is), forgets that found no value, the Mem0 "
     "history scrub (`messages` deleted, `history` records cleared), and "
     "rows later writes `swept` and writes `suppressed`.",
     ["revokes", "forget", "deleted", "fact_key", "value", "alias",
      "other_agents", "same_writer", "no_values", "messages", "history",
      "swept", "suppressed"]),
    ("supersession", "Supersession (Amendment 4)",
     "`retired`: rows writes marked retired; `earlier_rows`: the "
     "earlier statements' rows after the history (from the dataset) and "
     "how many carry a mark (`marked`); probes whose block held a "
     "retired row; rows the selection excluded as retired.",
     ["retired", "earlier_rows", "marked", "probes", "retired_in_block",
      "excluded"]),
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
             extra: Optional[Dict[str, List[dict]]] = None) -> str:
    """The report: the pass matrix and the cap and budget table, then
    the criteria, the contrasts, the integration rows and the readings
    (``extra``, as :func:`readings` returns them) when given."""
    out = ["# Benchmark v2 analysis", "",
           f"{len(cells)} cells, "
           f"{sum(len(c['trials']) for c in cells.values())} user-trials, "
           f"{sum(1 for c in cells.values() for t in c['trials'] if t.get('failed'))} failed.",
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
                        "cap_bound", "budget_bound", "probes"]), "",
           "## Cap and budget", "",
           table(binding, ["model", "locus", "backend", "condition",
                           "probes", "cap_bound", "budget_bound",
                           "tokens_median", "tokens_max"]), ""]
    if checks:
        out += ["## Functional check criteria", "",
                table(checks, ["criterion", "holds", "evidence"]), ""]
    if contrasts:
        out += ["## Kernel against replicated (paired over users)", "",
                table(contrasts, ["model", "backend", "probe", "pairs",
                                  "kernel_only", "replicated_only",
                                  "p_mcnemar"]), ""]
    if integration:
        out += ["## Integration (judge v2)", "",
                "The mean with its 95% t-interval (none for n < 2).", "",
                table(integration, ["model", "locus", "backend",
                                    "condition", "n", "mean", "ci_low",
                                    "ci_high", "sd", "share_ge_4"]), ""]
    for name, title, note, keys in READING_SECTIONS:
        found = (extra or {}).get(name)
        if found:
            out += [f"## {title}", "", note, "",
                    table(found, CELL_KEYS + keys), ""]
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
    text = markdown(cells, rows, binding, checks, contrasts, integration,
                    extra)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text)
    if args.json:
        Path(args.json).write_text(json.dumps({
            "rows": rows, "binding": binding, "criteria": checks,
            "contrasts": contrasts, "integration": integration,
            "readings": extra,
        }, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
