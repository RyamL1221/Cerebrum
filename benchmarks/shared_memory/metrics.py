"""Judge-free measures and the judge's score arithmetic (NeurIPS Subtask
20, AIOS docs/METRICS.md).

The judge-free measures the reports compute, and the judge's score
arithmetic, in one module; the reports import them from here. The
per-probe and per-trial measures recorded during a run are computed by
the run's own modules (``probes.score_probe``, ``judge_free``,
``stress``); this module computes everything the reports derive from
the records:
- the judge's score arithmetic: the keyword score (judge-free,
  deterministic), the hybrid every stored score before Subtask 20 was,
  the median of k LLM scores;
- ``profile_facts_in_answer`` of a stored trial (the run records it
  through ``judge_free``, whose function this module re-exports);
- the measures more than one report reads (probe pass rates, paired
  outcomes and means, ``cross_user_rows_all_probes``,
  ``writes_without_row``, block size, the stress, flood and identity
  counts per trial, a cell's leak and missing rates);
- the decision probe's scoring (Amendment 10).
Where two rules for one idea exist, both are here under distinct names
(METRICS.md), and recorded numbers do not change.
"""
import re
import statistics
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from benchmarks.shared_memory.judge_free import (  # noqa: F401 (re-exported)
    answer_profile_items,
    profile_facts_in_answer,
    split_missing,
)
from benchmarks.shared_memory.models import (
    SyntheticProfile,
    SyntheticTaskContext,
)
from benchmarks.shared_memory.probes import (
    match_any,
    mcnemar_exact,
    t_interval,
    wilson as _wilson,
)

# A judgment's dimensions, and the stored field of each.
DIMENSIONS = ("profile", "task", "integration")
SCORE_FIELD = {
    "profile": "profile_usage_score",
    "task": "task_usage_score",
    "integration": "integration_score",
}


def _extract_keywords(profile: SyntheticProfile,
                      task_context: SyntheticTaskContext) -> Dict[str, list]:
    """The keyword score's keywords (METRICS.md, "Keyword score"):
    profile, the user's name parts longer than 2 characters, each tool
    and the language; task, the project's words longer than 2 and the
    experiment's, goals' and blockers' words longer than 3. Lowercased,
    deduplicated."""
    profile_keywords = []
    for part in profile.user_name.split():
        if len(part) > 2:
            profile_keywords.append(part.lower())
    for tool in profile.preferred_tools:
        profile_keywords.append(tool.lower())
    if profile.preferred_language:
        profile_keywords.append(profile.preferred_language.lower())

    task_keywords = []
    for word in task_context.current_project.split():
        if len(word) > 2:
            task_keywords.append(word.lower())
    for word in task_context.active_experiment.split():
        if len(word) > 3:
            task_keywords.append(word.lower())
    for goal in task_context.goals:
        for word in goal.split():
            if len(word) > 3:
                task_keywords.append(word.lower())
    for blocker in task_context.blockers:
        for word in blocker.split():
            if len(word) > 3:
                task_keywords.append(word.lower())

    return {"profile": list(set(profile_keywords)),
            "task": list(set(task_keywords))}


def keyword_score(response: str, keywords: list) -> int:
    """1-5 from the share of ``keywords`` that are substrings of the
    lowercased response: 5 at 0.5 or more, 4 at 0.35, 3 at 0.2, 2 at
    0.1, else 1 (1 for no keyword or an empty response)."""
    if not keywords:
        return 1
    if not response:
        return 1
    response_lower = response.lower()
    hits = sum(1 for kw in keywords if kw in response_lower)
    ratio = hits / len(keywords)
    if ratio >= 0.5:
        return 5
    elif ratio >= 0.35:
        return 4
    elif ratio >= 0.2:
        return 3
    elif ratio >= 0.1:
        return 2
    else:
        return 1


def keyword_scores(response: str, profile: SyntheticProfile,
                   task_context: SyntheticTaskContext) -> Dict[str, int]:
    """The keyword score per dimension; integration is the lower of
    profile and task."""
    keywords = _extract_keywords(profile, task_context)
    kw_profile = keyword_score(response, keywords["profile"])
    kw_task = keyword_score(response, keywords["task"])
    return {"profile": kw_profile, "task": kw_task,
            "integration": min(kw_profile, kw_task)}


def hybrid_score(keyword: int, llm: int) -> int:
    """round((keyword + llm) / 2), halves to even, clamped to 1-5: the
    score every run before Subtask 20 stored."""
    return max(1, min(5, round((keyword + llm) / 2)))


def hybrid_scores(keyword: Dict[str, int],
                  llm: Dict[str, int]) -> Dict[str, int]:
    return {d: hybrid_score(keyword[d], llm[d]) for d in DIMENSIONS}


def median_score(scores: Iterable[int]) -> int:
    """The median of an odd number of scores (one of the scores)."""
    values = sorted(scores)
    if len(values) % 2 == 0:
        raise ValueError(
            f"the median of k scores needs an odd k, got {len(values)}")
    return values[len(values) // 2]


# -- judge-free measures the reports share --------------------------------------

# The judge-free probe types (v2), and a history's write events.
JUDGE_FREE = ("deletion", "privacy", "recall", "recency", "contradiction")
WRITE_EVENTS = ("base", "add", "update", "contradict", "private")
# A trial's leaks (``judge_free``): rows of another user, private rows of
# another agent.
LEAKS = ("cross_user_rows", "private_rows_from_others")
# The block columns of a table row (Subtask 17).
BLOCK = ["block_tokens", "block_rows"]


def probe_of(trial: dict, kind: str) -> Optional[dict]:
    """The trial's probe of type ``kind``, or None."""
    return next((p for p in trial.get("probe_results") or []
                 if p["type"] == kind), None)


def probes_of(trials: List[dict], kind: str,
              echo: Optional[bool] = None) -> List[dict]:
    """The ``kind`` probes of the trials that did not fail; of echo users
    only (``echo`` True) or of the others (False) when given."""
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


def by_user(trials: List[dict]) -> Dict[int, dict]:
    """The trials that did not fail, by trial index (the user)."""
    return {t["trial_index"]: t for t in trials if not t.get("failed")}


def block_text(probe: Optional[dict]) -> Optional[str]:
    """A probe's block text, or None."""
    return ((probe or {}).get("diagnostics") or {}).get("block_text")


def pass_rate(passed: int, n: int) -> dict:
    """``passed`` of ``n`` with its 95% Wilson interval, as
    ``{passed, n, rate, ci_low, ci_high}`` (``bench_v2_analysis``)."""
    if not n:
        return {"passed": passed, "n": n, "rate": None, "ci_low": None,
                "ci_high": None}
    low, high = _wilson(passed, n)
    return {"passed": passed, "n": n, "rate": passed / n, "ci_low": low,
            "ci_high": high}


def flag_rate(flags: Iterable[Optional[bool]]) -> dict:
    """The share of true flags among those not None, with its 95%
    Wilson interval, as ``{k, n, rate, ci}`` (``stress_report``)."""
    flags = [f for f in flags if f is not None]
    n, k = len(flags), sum(1 for f in flags if f)
    if not n:
        return {"k": 0, "n": 0, "rate": None, "ci": None}
    low, high = _wilson(k, n)
    return {"k": k, "n": n, "rate": k / n, "ci": [low, high]}


def paired_outcomes(trials: List[dict], reference: List[dict],
                    kind: str) -> dict:
    """Users whose ``kind`` outcome changed from the reference: ``lost``
    (passed there, failed here), ``gained``, and the exact McNemar p."""
    here, there = by_user(trials), by_user(reference)
    lost = gained = same = 0
    for user in sorted(set(here) & set(there)):
        a = (probe_of(there[user], kind) or {}).get("passed")
        b = (probe_of(here[user], kind) or {}).get("passed")
        if a is None or b is None:
            continue
        if a and not b:
            lost += 1
        elif b and not a:
            gained += 1
        else:
            same += 1
    return {"lost": lost, "gained": gained, "same": same,
            "p": mcnemar_exact(lost, gained)}


def paired_mean(trials: List[dict], reference: List[dict], value) -> dict:
    """The paired difference ``value(trial) - value(reference trial)``
    over the users both have it for: mean and 95% t interval."""
    here, there = by_user(trials), by_user(reference)
    diffs = []
    for user in sorted(set(here) & set(there)):
        a, b = value(there[user]), value(here[user])
        if a is not None and b is not None:
            diffs.append(b - a)
    if not diffs:
        return {"n": 0, "mean": None, "ci": None}
    low, high = t_interval(diffs)
    return {"n": len(diffs), "mean": statistics.mean(diffs),
            "ci": [low, high]}


def cross_user_rows_all_probes(trial: dict) -> int:
    """Injected rows, over every probe's block, written for another user
    (a leak), by the row's ``provenance_user``; a row without it is
    skipped. Not ``judge_free``'s ``cross_user_rows`` (one block, a row
    naming no user counts)."""
    count = 0
    for probe in trial.get("probe_results") or []:
        for row in (probe.get("diagnostics") or {}).get(
                "injected_memories") or []:
            owner = row.get("provenance_user")
            if owner and owner != trial.get("user_id"):
                count += 1
    return count


def writes_without_row(trial: dict) -> List[str]:
    """The trial's write events whose reply named no row: neither
    suppressed (a forgotten value) nor turned away by the write quota.
    On a backend that extracts, a write it stored nothing for (Mem0:
    "extracted no facts", known issue 32)."""
    out = []
    for record in trial.get("sessions") or []:
        for event in record.get("events") or []:
            if (event.get("type") in WRITE_EVENTS
                    and "reported_ids" in event
                    and not event.get("reported_ids")
                    and not event.get("suppressed")
                    and not event.get("quota_rejected")):
                out.append(event.get("event_id"))
    return out


def judge_free_of(trial: dict, key: str):
    """A ``judge_free`` measure recorded on the trial."""
    return (trial.get("judge_free") or {}).get(key)


def stress_of(trial: dict) -> dict:
    """The trial's ``stress`` record (Subtask 18), or {}."""
    return trial.get("stress") or {}


def probe_stress(trial: dict) -> List[dict]:
    """The per-probe stress records of a trial."""
    return list((stress_of(trial).get("probes") or {}).values())


def probe_diagnostics(trial: dict) -> List[dict]:
    """Each probe's injection diagnostics."""
    return [p.get("diagnostics") or {}
            for p in trial.get("probe_results") or []]


def mean_known(values: List[Optional[float]]) -> Optional[float]:
    """The mean of the values that are not None; None without one."""
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def block_size(probes: List[dict]) -> dict:
    """The mean block of ``probes``: ``block_tokens`` (the diagnostics'
    ``tokens_estimated``, a missing value counted as 0) and
    ``block_rows`` (injected rows); None for no probe."""
    if not probes:
        return dict.fromkeys(BLOCK)
    diagnostics = [p.get("diagnostics") or {} for p in probes]
    return {"block_tokens": statistics.fmean(
                d.get("tokens_estimated") or 0 for d in diagnostics),
            "block_rows": statistics.fmean(
                len(d.get("injected_memories") or []) for d in diagnostics)}


def block_tokens_known(trial: dict) -> Optional[float]:
    """A trial's mean ``tokens_estimated`` over its probes, a missing
    value left out (the ablation report's rule)."""
    return mean_known([d.get("tokens_estimated")
                       for d in probe_diagnostics(trial)])


def failed_outcome(kind: str) -> Callable[[dict], Optional[int]]:
    """A trial's ``kind`` probe as 1 (failed), 0 (passed) or None."""
    def value(trial):
        passed = (probe_of(trial, kind) or {}).get("passed")
        return None if passed is None else int(not passed)
    return value


def covered_late_writes(trial: dict) -> int:
    return sum(len(p.get("late_covered") or []) for p in probe_stress(trial))


def stale_reads(trial: dict) -> int:
    return sum(1 for p in probe_stress(trial) if p.get("stale_read"))


def timing_misses(trial: dict) -> int:
    return sum(1 for p in probe_stress(trial) if p.get("timing_miss"))


def misfiled_rows(trial: dict) -> int:
    return stress_of(trial).get("misfiled_rows") or 0


def stale_in_block(trial: dict) -> int:
    """Recency and contradiction probes whose block held the earlier
    statement's value."""
    return sum(1 for kind in ("recency", "contradiction")
               if (probe_of(trial, kind) or {}).get("stale_in_block"))


def carriers_left(trial: dict) -> int:
    return len(trial.get("revoked_value_rows") or [])


def flood_rows_per_probe(trial: dict) -> Optional[float]:
    return mean_known([p.get("flood_rows_in_block") or 0
                       for p in probe_stress(trial)])


def flood_writes_accepted(trial: dict) -> int:
    return stress_of(trial).get("flood_writes_accepted") or 0


def budget_bound_probes(trial: dict) -> int:
    return sum(1 for p in trial.get("probe_results") or []
               if p.get("budget_bound"))


def after_threshold(trial: dict) -> Optional[float]:
    return mean_known([d.get("after_threshold")
                       for d in probe_diagnostics(trial)])


def after_cap(trial: dict) -> Optional[float]:
    return mean_known([d.get("after_cap") for d in probe_diagnostics(trial)])


def missing_split(trial: dict) -> Tuple[List[str], List[str]]:
    """``(withheld, lost)`` writers of a trial's ``memories_missing``
    (``judge_free.split_missing``). Files written before Subtask 14 have
    no split, so it is recomputed from their written records."""
    free = trial.get("judge_free") or {}
    if "memories_withheld_writers" in free:
        return (list(free["memories_withheld_writers"]),
                list(free.get("memories_lost_writers") or []))
    return split_missing(free.get("memories_missing_writers") or [],
                         trial.get("written_memories") or [])


def trial_profile_facts_in_answer(trial: dict) -> Optional[float]:
    """The trial's ``profile_facts_in_answer``: recorded (from Subtask
    20), else computed from the record's answer and profile."""
    free = trial.get("judge_free") or {}
    if "profile_facts_in_answer" in free:
        return free["profile_facts_in_answer"]
    profile = trial.get("synthetic_profile")
    if not profile:
        return None
    return profile_facts_in_answer(SyntheticProfile(**profile),
                                   trial.get("assistant_response"))


def cell_judge_free(trials: List[dict]) -> dict:
    """A cell's v1 judge-free rates, over trials that did not fail and
    carry ``judge_free``: the leak rate (``LEAKS`` > 0), the missing,
    withheld and lost rates, and the means of ``profile_facts_in_block``
    and ``profile_facts_in_answer``."""
    done = [t for t in trials if not t.get("failed") and t.get("judge_free")]
    n = len(done)

    def rate(pred):
        return sum(1 for t in done if pred(t["judge_free"])) / n if n else None

    def split_rate(part):
        return (sum(1 for t in done if missing_split(t)[part]) / n
                if n else None)

    facts = [t["judge_free"].get("profile_facts_in_block") for t in done]
    facts = [f for f in facts if f is not None]
    in_answer = [trial_profile_facts_in_answer(t) for t in done]
    in_answer = [f for f in in_answer if f is not None]
    return {
        "n": n,
        "leak_rate": rate(lambda m: sum(m.get(k) or 0 for k in LEAKS) > 0),
        "missing_rate": rate(lambda m: (m.get("memories_missing") or 0) > 0),
        "withheld_rate": split_rate(0),
        "lost_rate": split_rate(1),
        "facts_in_block": statistics.mean(facts) if facts else None,
        "facts_in_answer": statistics.mean(in_answer) if in_answer else None,
    }


# -- the decision probe (Amendment 10) ------------------------------------------

DECISION_ERRORS = ("stale", "revoked", "private", "foreign", "no_letter",
                   "multiple_letters")
_LETTER = re.compile(r"(?<![A-Za-z])([A-D])(?![A-Za-z])")


def letters_named(answer: Optional[str], options: List[dict]) -> List[str]:
    """The option letters an answer names: each uppercase A-D standing
    alone (no letter on either side), once the options' own statements
    are removed from it (case-insensitive), in the order named."""
    text = answer or ""
    for option in options:
        text = re.sub(re.escape(option["statement"]), " ", text,
                      flags=re.IGNORECASE)
    named = []
    for letter in _LETTER.findall(text):
        if letter not in named:
            named.append(letter)
    return named


def score_decision(item: dict, answer: Optional[str],
                   block_text: Optional[str] = None) -> Dict[str, Any]:
    """A decision item's answer, scored exactly (BENCHMARK_V2.md,
    Amendment 10): one letter named passes if it is the correct one,
    else its error is the named option's kind; none is ``no_letter``,
    two or more ``multiple_letters``. Also which options' values the
    block holds (the matcher)."""
    named = letters_named(answer, item["options"])
    by_letter = {o["letter"]: o for o in item["options"]}
    if len(named) == 1:
        choice = named[0]
        passed = choice == item["correct"]
        error = None if passed else by_letter[choice]["kind"]
    else:
        choice, passed = None, False
        error = "no_letter" if not named else "multiple_letters"
    in_block = None
    if block_text is not None:
        in_block = [o["kind"] for o in item["options"]
                    if match_any(block_text, o["value"],
                                 o.get("aliases") or [])]
    return {"choice": choice, "letters": named, "passed": passed,
            "error": error, "options_in_block": in_block}


def decision_summary(results: Iterable[Any]) -> Dict[str, Any]:
    """A cell's decision items: accuracy (passes over the scored items)
    with its 95% Wilson interval, and the share of items per error."""
    rows = [r if isinstance(r, dict) else r.model_dump() for r in results]
    scored = [r for r in rows if r.get("passed") is not None
              and not r.get("turn_error")]
    n = len(scored)
    passed = sum(1 for r in scored if r["passed"])
    out: Dict[str, Any] = {"n": n, "passed": passed,
                           "accuracy": passed / n if n else None,
                           "ci": wilson(passed, n)}
    for error in DECISION_ERRORS:
        k = sum(1 for r in scored if r.get("error") == error)
        out[error] = {"k": k, "share": k / n if n else None}
    return out


def wilson(k: int, n: int) -> Optional[Tuple[float, float]]:
    """The 95% Wilson interval of k successes in n (``probes.wilson``);
    None for n = 0."""
    return _wilson(k, n) if n else None
