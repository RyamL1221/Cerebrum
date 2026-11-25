"""Human ratings of judged answers: the blinded sample, the raters'
file and the analysis (protocol: docs/HUMAN_RATING.md; the judges and
their statistics: AIOS docs/METRICS.md, "Judged measures").

    python -m benchmarks.shared_memory.human_rating sample \\
        --tree results/s20_rejudge/gpt-5.4 \\
        --tree results/s20_rejudge/claude-sonnet-5.5 \\
        --items <raters' directory>/items.json \\
        --key <private directory>/key.json
    python -m benchmarks.shared_memory.human_rating analyze \\
        --key <private directory>/key.json \\
        --ratings r1.csv r2.csv r3.csv --md report.md --json report.json

``sample`` draws the answers the raters score: the same number from
every cell (dataset version, locus, backend, model, H), seeded, no
answer twice, reading no score. It writes two files. The raters' file
holds the judge prompt's rubric and, per answer, what the judge prompt
prints of it (the profile and the task context line by line, the query,
the answer) under an id that says nothing; nothing else. The key, in a
directory of its own, holds each id's source trial, its cell and the
judges' scores; no rater gets it. The same trees, runs and seed give
the same two files, byte for byte.

``analyze`` reads the key and the raters' CSV files (the export of
``human_rating.html``, beside this file) and reports Krippendorff's
alpha across the raters, the agreement of the raters' median with each
judge, and the disagreements item by item. Without ``--ratings`` it
reports the sample and the judges' agreement on it. ``--informed
RATER ...`` names the raters who know the hypotheses; the report says
so.

The statistics are ``judge_reliability``'s (``alpha``, ``bootstrap``,
``agreement``, ``interval``, ``medians_at``, ``two_coder_alphas``), so
raters and judges are measured by one module. The module reads results
files only: it makes no kernel, model or network call.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from benchmarks.shared_memory import judge_reliability as jr
from benchmarks.shared_memory.conditions import locus_of
from benchmarks.shared_memory.judge import (
    JUDGE_PROMPT_VERSION,
    PRIMARY_JUDGE,
    SECOND_JUDGE,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    judge_prompt_sha256,
)
from benchmarks.shared_memory.metrics import DIMENSIONS, keyword_scores
from benchmarks.shared_memory.models import (
    SyntheticProfile,
    SyntheticTaskContext,
    TrialResult,
)

KIT = "human_rating"
FORMAT = 1

# -- the protocol's numbers (docs/HUMAN_RATING.md) ---------------------------

RATING_SEED = 20261122  # the draw's seed, fixed before any rating
PER_CELL = 3            # answers drawn from each cell
PRACTICE = 6            # warm-up answers, scored first, never analysed
RATERS = 3              # odd, so the raters' median is one of their scores
RESAMPLES = 2000        # bootstrap resamples, as METRICS.md's
JUDGE_NAMES = (PRIMARY_JUDGE, SECOND_JUDGE)
# The raters' alpha is read as a judge's is (METRICS.md, "The k rule"):
# 0.80 on Profile and Integration. From 0.667 a comparison with the
# judges is tentative; below it the raters' median is no reference.
ALPHA_RELIABLE = jr.K_RULE_ALPHA
ALPHA_TENTATIVE = 0.667
RULE_DIMENSIONS = jr.K_RULE_DIMENSIONS
# Scores this far apart (or further) are listed as a disagreement.
SPREAD = 2
# The judge-free score, compared with the raters as the judges are.
KEYWORD = "keyword"

# -- what the raters' file holds, and what it never holds --------------------

RATERS_FIELDS = ("kit", "kind", "format", "sample", "rubric", "items")
ITEM_FIELDS = ("item_id", "practice", "profile", "task_context", "query",
               "response")
# No key of the raters' file, at any depth, may bear one of these names:
# each names something a rater must not know (docs/HUMAN_RATING.md,
# "What a rater sees").
FORBIDDEN_FIELDS = (
    "run", "run_id", "runs", "tree", "trees", "file", "path", "source",
    "also", "trial", "trial_index", "condition", "condition_index",
    "method", "control", "ablation", "fault", "cell", "cells", "version",
    "locus", "backend", "model", "h", "heterogeneity_level",
    "variants_applied", "dataset", "user", "user_id", "input_sha256",
    "inputs_sha256", "seed", "per_cell", "judge", "judges", "score",
    "scores", "llm", "keyword", "hybrid", "stored", "reasoning", "band",
    "rater", "raters", "ratings", "memory", "block", "block_text",
    "injection_diagnostics", "person", "people", "informed",
)
PRACTICE_ID = re.compile(r"p\d{2,}")
ITEM_ID = re.compile(r"h\d{3,}")
# Names that would tell a rater the model, its maker or the memory
# system behind an answer. An answer that holds one its profile, task
# context and query do not is no candidate (an answer signed "Qwen").
HIDDEN_NAMES = tuple(re.compile(pattern, re.I) for pattern in (
    r"\bqwen", r"\bgpt|chatgpt", r"openai", r"\bllama", r"alibaba",
    r"\bmeta ai\b", r"anthropic", r"\bclaude\b", r"mem0", r"\ba-?mem\b",
    r"graphiti", r"\bzep\b", r"\baios\b", r"cerebrum"))

# The columns of a rater's CSV, in the order the page writes them.
CSV_COLUMNS = ("sample", "item_id", "rater", "profile", "task",
               "integration", "comment", "seconds", "rated_at", "position")
REQUIRED_COLUMNS = ("sample", "item_id", "rater") + DIMENSIONS

# Why a stored trial is not a candidate, in the order checked.
EXCLUSIONS = ("failed", "other_condition", "not_a_locus", "no_inputs",
              "names_hidden", "no_cell", "unjudged")
FACTORS = ("version", "locus", "backend", "model", "h")
# The plain condition's stress settings: the harness's defaults.
STRESS_DEFAULTS = {name: TrialResult.model_fields[name].default
                   for name in ("agents", "concurrency", "load", "fault")}


# -- the judge prompt, as the raters get it -----------------------------------

# The judge prompt's parts (``--- <title> ---``) and the item field each
# holds; and its rubric's titles and the dimension each scores.
PARTS = {"USER PROFILE": "profile", "TASK CONTEXT": "task_context",
         "FOLLOW-UP QUERY": "query", "ASSISTANT RESPONSE": "response"}
RUBRIC_TITLES = {"Profile Usage": "profile", "Task Usage": "task",
                 "Integration": "integration"}


def _prompt_parts() -> Dict[str, str]:
    """The judge's user template cut at its ``--- <title> ---`` lines:
    title -> the text under it, ``""`` -> the text before the first."""
    pieces = re.split(r"--- (.+?) ---\n", USER_PROMPT_TEMPLATE.template)
    return {"": pieces[0], **dict(zip(pieces[1::2], pieces[2::2]))}


def prompt_labels() -> Dict[str, List[Tuple[str, str]]]:
    """The profile's and the task context's lines in the judge prompt,
    in its order, as ``(label, field)``: ``("Preferred Tools",
    "preferred_tools")``."""
    parts = _prompt_parts()
    return {PARTS[title]: re.findall(r"^(.+?): \$(\w+)$", parts[title],
                                     re.M)
            for title in ("USER PROFILE", "TASK CONTEXT")}


PROFILE_FIELDS = tuple(field for _, field in prompt_labels()["profile"])
TASK_FIELDS = tuple(field for _, field in prompt_labels()["task_context"])


def rubric() -> Dict[str, Any]:
    """The rubric the raters score with, in the judge prompt's words
    (``judge.py``, prompt v2): ``intro`` (the prompt's first line),
    ``guidance`` (the two general sentences a judge gets: the system
    prompt's, after its format instructions, and the rubric's head),
    ``parts`` (each item field's title in the prompt) and
    ``dimensions`` (in the prompt's order, each with its CSV
    ``column``, its ``title`` and its five ``anchors``, ``[score,
    words]`` from 5 down). The raters' file carries it, so the page
    shows the judge's words and no others."""
    parts = _prompt_parts()
    body = parts["SCORING RUBRIC"].split("Respond with ONLY")[0].strip()
    head, *sections = re.split(r"\n\n(?=[A-Z][A-Za-z ]+ \(1-5\):\n)", body)
    dimensions = []
    for section in sections:
        title, *lines = section.strip().split("\n")
        anchors = [[int(score), words] for score, words in (
            line.strip().split(" = ", 1) for line in lines)]
        dimensions.append({"column": RUBRIC_TITLES[title[:-len(" (1-5):")]],
                           "title": title[:-1], "anchors": anchors})
    if [d["column"] for d in dimensions] != list(DIMENSIONS) or any(
            [a[0] for a in d["anchors"]] != [5, 4, 3, 2, 1]
            for d in dimensions):
        raise ValueError("the judge prompt's rubric is not three "
                         "dimensions scored 5 down to 1")
    return {"intro": parts[""].strip(),
            "guidance": [SYSTEM_PROMPT.split("Just the raw JSON object. ")[1],
                         " ".join(head.split())],
            "parts": {field: title for title, field in PARTS.items()},
            "dimensions": dimensions}


def _line(value: Any) -> str:
    """A value as the judge prompt prints it: a list joined with ", "
    (``judge.build_messages``), anything else as text."""
    return ", ".join(value) if isinstance(value, list) else str(value)


def judge_view(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """What the judge prompt prints of an answer's inputs: the profile
    and the task context as ``[label, text]`` lines in the prompt's
    order, then the query and the answer as they are."""
    view: Dict[str, Any] = {
        part: [[label, _line(inputs[part][field])]
               for label, field in lines]
        for part, lines in prompt_labels().items()}
    view["query"] = inputs["query"]
    view["response"] = inputs["response"]
    return view


# -- candidates ---------------------------------------------------------------

def is_copy(path: Path) -> bool:
    """An iCloud conflict copy (``results_x 2.json``), never a result."""
    return re.search(r" \d+$", path.stem) is not None


def result_files(tree: Path,
                 runs: Optional[Sequence[str]] = None
                 ) -> List[Tuple[str, Path]]:
    """``(run, path)`` of every results file under ``tree/<run>/``, for
    ``runs`` in their order (default: every run of the tree, by name)."""
    names = list(runs) if runs else sorted(
        p.name for p in tree.iterdir() if p.is_dir())
    return [(run, path) for run in names
            for path in sorted((tree / run).rglob("results_*.json"))
            if not is_copy(path)]


def judge_scores(trial: dict, judge: str) -> Optional[Dict[str, int]]:
    """``judge``'s LLM scores of a stored trial (``judges[<name>].llm``,
    the median of its k repeats). None without a complete record, and
    for a record made under another judge prompt than the one whose
    rubric the raters get (a record without a hash is taken as it is)."""
    record = (trial.get("judges") or {}).get(judge)
    if not record or record.get("failed"):
        return None
    if record.get("prompt_sha256") not in (None, judge_prompt_sha256()):
        return None
    llm = record.get("llm") or {}
    if any(llm.get(d) is None for d in DIMENSIONS):
        return None
    return {d: llm[d] for d in DIMENSIONS}


def _text(value: Any) -> bool:
    """Whether ``value`` is text with something in it."""
    return isinstance(value, str) and bool(value.strip())


def judge_inputs(trial: dict) -> Optional[Dict[str, Any]]:
    """What a judge sees of a stored trial (``rejudge.judge_inputs``; a
    v2 trial's are its integration probe's), as plain data with the
    judge prompt's fields only. None when the record lacks a part: a
    profile or task context field, the query or the answer (or holds a
    blank query or answer, which leaves a rater nothing to score)."""
    profile = trial.get("synthetic_profile") or {}
    task = trial.get("synthetic_task_context") or {}
    query = trial.get("follow_up_query")
    response = trial.get("assistant_response")
    if any(f not in profile for f in PROFILE_FIELDS) or any(
            f not in task for f in TASK_FIELDS) or not (
            _text(query) and _text(response)):
        return None
    return {"query": query, "response": response,
            "profile": {f: profile[f] for f in PROFILE_FIELDS},
            "task_context": {f: task[f] for f in TASK_FIELDS}}


def tells_hidden(inputs: Dict[str, Any]) -> bool:
    """Whether the answer names a model, its maker or a memory system
    (``HIDDEN_NAMES``) that its profile, task context and query do not:
    a rater would learn what the protocol hides."""
    seen = json.dumps([inputs["profile"], inputs["task_context"],
                       inputs["query"]], ensure_ascii=False)
    return any(name.search(inputs["response"]) and not name.search(seen)
               for name in HIDDEN_NAMES)


def person_sha256(inputs: Dict[str, Any]) -> str:
    """The person a rater sees: the profile, the task context and the
    query, hashed (all a judge sees but the answer). One person's
    answers share it across cells, runs and dataset versions, where a
    v2 user's inputs are its v1 user's."""
    text = json.dumps([inputs["query"], inputs["profile"],
                       inputs["task_context"]], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def stratum(rel: Path, trial: dict,
            check_level: bool = True) -> Optional[Dict[str, Any]]:
    """The answer's cell, ``judge_reliability.cell_of``: dataset
    version, locus, backend, model and H (H read from the path). None
    when the path names no model or backend, or the trial no locus.
    With ``check_level``, a trial whose own ``heterogeneity_level``
    contradicts its path is refused."""
    locus = trial.get("locus") or locus_of(
        trial.get("method") or trial.get("condition") or "")
    try:
        cell = jr.cell_of(rel, {**trial, "locus": locus})
    except StopIteration:
        return None
    if cell["locus"] not in jr.LOCI or cell["backend"] is None:
        return None
    level = trial.get("heterogeneity_level")
    if check_level and level is not None and level != cell["h"]:
        raise ValueError(
            f"{rel}: the path says H = {cell['h']}, trial "
            f"{trial.get('trial_index')} says {level}")
    return cell


def plain(trial: dict) -> bool:
    """Whether the trial is the plain condition: no negative control, no
    ablation switch, and the harness's default stress settings
    (``TrialResult``'s defaults: 4 agents, sequential, load 1, no
    fault; a field an older file lacks counts as its default). Another
    condition is no stratum of the rule: its answers would enter a cell
    under a factor the cell does not name."""
    if trial.get("control") or trial.get("ablation"):
        return False
    return all(trial.get(name) in (None, default)
               for name, default in STRESS_DEFAULTS.items())


def _entry(run: str, rel: Path, index: int, trial: dict) -> dict:
    """One trial of the answers' tree: its source, its cell (for every
    trial of the plain condition and a locus, so that a cell whose
    trials are all excluded is still seen), and either why it is no
    candidate (``reason``) or its person and inputs."""
    entry: Dict[str, Any] = {
        "source": {"run": run, "file": rel.as_posix(),
                   "condition_index": index,
                   "trial_index": trial["trial_index"],
                   "method": trial.get("method")},
        "judges": {}, "reason": None}
    inputs = judge_inputs(trial)
    locus_trial = plain(trial) and \
        trial.get("method") not in jr.EXCLUDED_METHODS
    # A failed trial's own H is not checked: the harness records some
    # failures without it (run_evaluation.py's synthetic-data and
    # agent-pipeline failures keep TrialResult's default 0). Its cell,
    # only counted, is its path's.
    cell = stratum(rel, trial, check_level=not trial.get("failed")) \
        if locus_trial else None
    if trial.get("failed"):
        entry["reason"] = "failed"
    elif not plain(trial):
        entry["reason"] = "other_condition"
    elif trial.get("method") in jr.EXCLUDED_METHODS:
        entry["reason"] = "not_a_locus"
    elif inputs is None:
        entry["reason"] = "no_inputs"
    elif tells_hidden(inputs):
        entry["reason"] = "names_hidden"
    elif cell is None:
        entry["reason"] = "no_cell"
    if inputs is not None:
        entry.update(inputs)
        entry["inputs_sha256"] = jr.inputs_sha256(inputs)
        entry["person"] = person_sha256(inputs)
    entry["cell"] = cell
    return entry


def candidates(trees: Sequence[Path],
               runs: Optional[Sequence[str]] = None,
               judges: Sequence[str] = JUDGE_NAMES,
               require: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Every answer a rater may be given, from the results files under
    ``trees`` (each ``<tree>/<run>/.../results_*.json``).

    The first tree gives the trials and their answers; every tree gives
    the ``judges``' records it holds (two re-judged trees of one run
    each hold one judge's). A trial is not a candidate when it failed,
    ran another condition than the plain one (``plain``), is a baseline
    (``judge_reliability.EXCLUDED_METHODS``, not a locus), lacks a part
    of what the judge sees, names what is hidden (``tells_hidden``),
    sits in no cell, or lacks a complete record of a judge in
    ``require`` (default: every one of ``judges``).

    Returns ``{candidates, trials, excluded, k, cells}``: the candidates
    in file order, the trials read, the count excluded per reason
    (``EXCLUSIONS``), the k each judge was used at, and every cell a
    trial of the plain condition and a locus sits in with its count of
    candidates (0 for a cell whose trials were all excluded). Refuses
    trees that hold different answers, or different scores of one
    judge, for one trial, and a judge used at two k."""
    require = tuple(judges) if require is None else tuple(require)
    unknown = sorted(set(require) - set(judges))
    if unknown:
        raise ValueError(f"required judges not among the judges: {unknown}")
    found: Dict[Tuple, dict] = {}
    ks: Dict[str, set] = {name: set() for name in judges}
    for position, tree in enumerate(Path(t) for t in trees):
        files = result_files(tree, runs)
        absent = sorted(set(runs or []) - {run for run, _ in files})
        if position == 0 and (absent or not files):
            raise ValueError(f"no results file under {tree}"
                             + (f" for {absent}" if absent else ""))
        for run, path in files:
            rel = path.relative_to(tree)
            data = json.loads(path.read_text())
            for index, condition in enumerate(data["conditions"]):
                for trial in condition["trials"]:
                    where = (rel.as_posix(), index, trial["trial_index"])
                    if position == 0:
                        found[where] = _entry(run, rel, index, trial)
                    if where in found:
                        _add_scores(found[where], tree, trial, judges, ks)
    kept, excluded, cells = [], Counter(), Counter()
    for entry in found.values():
        reason = entry.pop("reason") or next(
            ("unjudged" for name in require
             if entry["judges"].get(name) is None), None)
        if entry["cell"] is not None:
            cells[jr.cell_key(entry)] += 0 if reason else 1
        if reason:
            excluded[reason] += 1
        else:
            kept.append(entry)
    for name, values in ks.items():
        if len(values) > 1:
            raise ValueError(f"{name} was used at more than one k: "
                             f"{sorted(values, key=str)}")
    return {"candidates": kept, "trials": len(found),
            "excluded": {r: excluded.get(r, 0) for r in EXCLUSIONS},
            "k": {name: next(iter(values), None)
                  for name, values in ks.items()},
            "cells": dict(cells)}


def _add_scores(entry: dict, tree: Path, trial: dict,
                judges: Sequence[str], ks: Dict[str, set]) -> None:
    """Add to ``entry`` the judges' scores ``tree`` holds of its trial."""
    where = (f"{tree}/{entry['source']['file']}, trial "
             f"{entry['source']['trial_index']}")
    inputs = judge_inputs(trial)
    if inputs is not None and "inputs_sha256" in entry and \
            jr.inputs_sha256(inputs) != entry["inputs_sha256"]:
        raise ValueError(f"{where}: not the answer the first tree holds")
    for name in judges:
        scores = judge_scores(trial, name)
        if scores is None:
            continue
        if entry["judges"].get(name, scores) != scores:
            raise ValueError(f"{where}: two trees hold different scores "
                             f"of {name}")
        entry["judges"][name] = scores
        ks[name].add(trial["judges"][name].get("repeats"))


# -- the draw -----------------------------------------------------------------

def _where(candidate: dict) -> Tuple:
    source = candidate["source"]
    return (source["file"], source["condition_index"],
            source["trial_index"])


def draw(found: List[dict], per_cell: int = PER_CELL,
         practice: int = PRACTICE, seed: int = RATING_SEED) -> Dict[str, Any]:
    """The seeded draw (docs/HUMAN_RATING.md, "The sampling rule").

    Cells are visited in a seeded order. A cell gives ``per_cell`` of
    its candidates: each time the one whose person (``person_sha256``:
    profile, task context and query) has been drawn least so far, ties
    in a seeded order, passing over an answer whose inputs (query,
    answer, profile, task context) are those of an answer already
    drawn. Then the first ``practice`` cells of the order give one more
    each, the same way: the warm-up. No score is read.

    Returns ``{sample, practice, order}``: the sample in a seeded order
    of its own (so an item's place says nothing of its cell), the
    warm-up, and the cells as visited. A cell with too few answers
    gives what it has."""
    rng = random.Random(seed)
    pools: Dict[Tuple, List[dict]] = {}
    for candidate in sorted(found, key=_where):
        pools.setdefault(jr.cell_key(candidate), []).append(candidate)
    cells = sorted(pools)
    for cell in cells:
        rng.shuffle(pools[cell])
    order = list(cells)
    rng.shuffle(order)
    taken: set = set()
    per_person: Counter = Counter()

    def take(cell: Tuple) -> Optional[dict]:
        left = [c for c in pools[cell] if c["inputs_sha256"] not in taken]
        if not left:
            return None
        pick = min(left, key=lambda c: per_person[c["person"]])
        taken.add(pick["inputs_sha256"])
        per_person[pick["person"]] += 1
        return pick

    sample = [pick for cell in order for _ in range(per_cell)
              for pick in [take(cell)] if pick is not None]
    warm: List[dict] = []
    for cell in order:
        if len(warm) < practice:
            warm += [pick for pick in [take(cell)] if pick is not None]
    rng.shuffle(sample)
    return {"sample": sample, "practice": warm, "order": order}


# -- the two files ------------------------------------------------------------

def _keyed_item(item_id: str, practice: bool, candidate: dict,
                same: Dict[str, List[dict]]) -> dict:
    """The key's entry: the item's source trial, cell, person and scores
    (each judge's, and the keyword score recomputed from the inputs),
    and every other candidate trial with the same inputs (``also``)."""
    keyword = keyword_scores(
        candidate["response"], SyntheticProfile(**candidate["profile"]),
        SyntheticTaskContext(**candidate["task_context"]))
    return {"item_id": item_id, "practice": practice,
            "source": candidate["source"], "cell": candidate["cell"],
            "person": candidate["person"],
            "inputs_sha256": candidate["inputs_sha256"],
            "judges": candidate["judges"], KEYWORD: keyword,
            "also": [{"source": other["source"], "cell": other["cell"],
                      "judges": other["judges"]}
                     for other in same[candidate["inputs_sha256"]]
                     if other is not candidate]}


def make_sample(trees: Sequence[Path],
                runs: Optional[Sequence[str]] = None,
                judges: Sequence[str] = JUDGE_NAMES,
                require: Optional[Sequence[str]] = None,
                per_cell: int = PER_CELL, practice: int = PRACTICE,
                seed: int = RATING_SEED) -> Tuple[dict, dict]:
    """``(raters' document, key)`` for the stored results under
    ``trees``: ``candidates`` then ``draw``. Ids ``h001``... number the
    sample in its seeded order, ``p01``... the warm-up. Both documents
    carry ``sample``, a hash of the raters' rubric and items, so the
    ratings of one sample cannot be read against another's key."""
    found = candidates(trees, runs, judges, require)
    drawn = draw(found["candidates"], per_cell, practice, seed)
    same: Dict[str, List[dict]] = defaultdict(list)
    for candidate in found["candidates"]:
        same[candidate["inputs_sha256"]].append(candidate)
    # Every cell the trees hold, a cell without a candidate included.
    per_cell_found = found["cells"]
    width = max(3, len(str(len(drawn["sample"]))))
    picks = [(f"p{n:02d}", True, c)
             for n, c in enumerate(drawn["practice"], 1)]
    picks += [(f"h{n:0{width}d}", False, c)
              for n, c in enumerate(drawn["sample"], 1)]
    items = [{"item_id": item_id, "practice": warm, **judge_view(c)}
             for item_id, warm, c in picks]
    guide = rubric()
    sample = hashlib.sha256(json.dumps(
        {"rubric": guide, "items": items}, sort_keys=True).encode()
    ).hexdigest()[:12]
    per_cell_drawn = Counter(jr.cell_key(c) for c in drawn["sample"])
    per_cell_warm = Counter(jr.cell_key(c) for c in drawn["practice"])
    key = {
        "kit": KIT, "kind": "key", "format": FORMAT, "sample": sample,
        "seed": seed, "per_cell": per_cell, "practice": practice,
        "trees": [str(t) for t in trees],
        "runs": sorted({c["source"]["run"] for c in found["candidates"]}),
        "judges": found["k"],
        "required": list(judges if require is None else require),
        "prompt": {"version": JUDGE_PROMPT_VERSION,
                   "sha256": judge_prompt_sha256()},
        "trials": found["trials"], "excluded": found["excluded"],
        "candidates": len(found["candidates"]),
        "distinct_answers": len(same),
        "order": [dict(zip(FACTORS, cell)) for cell in drawn["order"]],
        "cells": [{"cell": dict(zip(FACTORS, cell)),
                   "candidates": per_cell_found[cell],
                   "items": per_cell_drawn[cell],
                   "practice": per_cell_warm[cell]}
                  for cell in sorted(per_cell_found)],
        "items": [_keyed_item(*pick, same) for pick in picks],
    }
    document = {"kit": KIT, "kind": "items", "format": FORMAT,
                "sample": sample, "rubric": guide, "items": items}
    return document, key


def short_cells(key: dict) -> List[dict]:
    """The cells that gave fewer answers than ``per_cell``, a cell that
    gave none (every trial of it excluded) included."""
    return [c for c in key["cells"] if c["items"] < key["per_cell"]]


def blind_problems(document: Any) -> List[str]:
    """Why ``document`` may not go to a rater; empty when it may. It
    holds the kit's fields, the judge prompt's rubric (``rubric()``)
    and, per item, an id, the warm-up flag and what the judge prompt
    prints of the answer (``judge_view``); no other key at any depth,
    none named in ``FORBIDDEN_FIELDS``; ids ``p01``... for the warm-up
    and ``h001``... for the rest, each once."""
    problems: List[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for name, inner in value.items():
                if str(name).lower() in FORBIDDEN_FIELDS:
                    problems.append(f"{path}{name}: a hidden field")
                walk(inner, f"{path}{name}.")
        elif isinstance(value, list):
            for inner in value:
                walk(inner, path)

    walk(document, "")
    if not isinstance(document, dict) or \
            sorted(document) != sorted(RATERS_FIELDS):
        return problems + ["the document's fields are not the kit's"]
    if (document["kit"], document["kind"], document["format"]) != (
            KIT, "items", FORMAT):
        problems.append("not this kit's raters' file")
    if document["rubric"] != rubric():
        problems.append("the rubric is not the judge prompt's")
    labels = {part: [label for label, _ in lines]
              for part, lines in prompt_labels().items()}
    seen: set = set()
    for item in document["items"]:
        name = item.get("item_id") if isinstance(item, dict) else item
        if not isinstance(item, dict) or sorted(item) != sorted(ITEM_FIELDS):
            problems.append(f"{name}: not an item's fields")
            continue
        pattern = PRACTICE_ID if item["practice"] is True else ITEM_ID
        if not isinstance(name, str) or not pattern.fullmatch(name) or \
                not isinstance(item["practice"], bool):
            problems.append(f"{name}: not an item id of its kind")
        if name in seen:
            problems.append(f"{name}: twice")
        seen.add(name)
        for part, expected in labels.items():
            lines = item[part]
            if not isinstance(lines, list) or [
                    line[0] if isinstance(line, list) and line else None
                    for line in lines] != expected or any(
                    len(line) != 2 or not isinstance(line[1], str)
                    for line in lines):
                problems.append(f"{name}: {part} is not the prompt's lines")
        if not all(isinstance(item[f], str) for f in ("query", "response")):
            problems.append(f"{name}: query or response not text")
    return problems


def _inside(path: Path, directory: Path) -> bool:
    """Whether ``path`` is ``directory`` or lies under it."""
    return path == directory or directory in path.parents


def write_sample(document: dict, key: dict, items_path: Path,
                 key_path: Path, force: bool = False) -> None:
    """Write the raters' file and the key. Refuses a raters' file that
    is not blind, a key in the raters' directory, under it or around
    it, and, without ``force``, to replace a file that holds another
    sample."""
    problems = blind_problems(document)
    if problems:
        raise ValueError("the raters' file is not blind: "
                         + "; ".join(problems))
    items_path, key_path = Path(items_path), Path(key_path)
    items_dir = items_path.resolve().parent
    key_dir = key_path.resolve().parent
    if _inside(key_dir, items_dir) or _inside(items_dir, key_dir):
        raise ValueError("the key goes in a directory of its own, apart "
                         "from the raters' file (not in, under or above "
                         "its directory)")
    texts = {items_path: json.dumps(document, indent=1, sort_keys=True),
             key_path: json.dumps(key, indent=1, sort_keys=True)}
    for path, text in texts.items():
        if path.exists() and path.read_text() != text + "\n" and not force:
            raise ValueError(f"{path} holds another sample (--force "
                             "replaces it)")
    for path, text in texts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")


# -- reading the key and the ratings ------------------------------------------

def load_key(path: Path) -> dict:
    key = json.loads(Path(path).read_text())
    if not isinstance(key, dict) or key.get("kit") != KIT \
            or key.get("kind") != "key" or key.get("format") != FORMAT:
        raise ValueError(f"{path} is not a key of this kit")
    return key


def _score(text: Optional[str], where: str) -> Optional[int]:
    text = (text or "").strip()
    if not text:
        return None
    if text not in ("1", "2", "3", "4", "5"):
        raise ValueError(f"{where}: a score is {text!r}, not 1 to 5")
    return int(text)


def _seconds(text: Optional[str], where: str) -> Optional[float]:
    text = (text or "").strip()
    try:
        return float(text) if text else None
    except ValueError:
        raise ValueError(f"{where}: seconds is {text!r}") from None


def read_ratings(paths: Sequence[Path],
                 key: dict) -> Dict[str, Dict[str, dict]]:
    """The raters' CSV files as rater -> item id -> ``{profile, task,
    integration, complete, comment, seconds, rated_at}`` (a score None
    where the cell is empty; ``complete`` when all three are given).

    Refuses a file without the kit's columns, a row of another sample
    or of an item the key does not hold, a row without a rater, a score
    that is not 1 to 5, and a rater's second row for one item (two
    exports of one rater, or two raters under one name)."""
    known = {item["item_id"] for item in key["items"]}
    out: Dict[str, Dict[str, dict]] = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in REQUIRED_COLUMNS
                       if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"{path}: no column {missing}")
            for row in reader:
                where = f"{path}, line {reader.line_num}"
                if (row["sample"] or "").strip() != key["sample"]:
                    raise ValueError(
                        f"{where}: sample {row['sample']!r}, the key is "
                        f"of {key['sample']!r}")
                item_id = (row["item_id"] or "").strip()
                rater = (row["rater"] or "").strip()
                if item_id not in known:
                    raise ValueError(f"{where}: no item {item_id!r}")
                if not rater:
                    raise ValueError(f"{where}: no rater")
                if item_id in out.setdefault(rater, {}):
                    raise ValueError(f"{where}: {rater}'s second row for "
                                     f"{item_id}")
                scores = {d: _score(row[d], where) for d in DIMENSIONS}
                out[rater][item_id] = {
                    **scores,
                    "complete": all(v is not None for v in scores.values()),
                    "comment": (row.get("comment") or "").strip(),
                    "seconds": _seconds(row.get("seconds"), where),
                    "rated_at": (row.get("rated_at") or "").strip() or None,
                }
    return out


# -- the analysis -------------------------------------------------------------

def reading(alpha: Optional[float]) -> str:
    """How the raters' alpha on a dimension is read (the protocol's
    threshold): ``reliable`` from 0.80, ``tentative`` from 0.667, ``not
    reliable`` below, ``undefined`` without an alpha."""
    if alpha is None:
        return "undefined"
    if alpha >= ALPHA_RELIABLE:
        return "reliable"
    return "tentative" if alpha >= ALPHA_TENTATIVE else "not reliable"


def pair_shares(units: Sequence[Sequence[Optional[int]]]) -> Dict[str, Any]:
    """Over every item and every pair of the raters who scored it: the
    share of pairs with equal scores and with scores at most one apart
    (METRICS.md's exact and within-1 agreement, raters for repeats)."""
    exact = within = pairs = 0
    for unit in units:
        for a, b in itertools.combinations(
                [v for v in unit if v is not None], 2):
            pairs += 1
            exact += a == b
            within += abs(a - b) <= 1
    return {"pairs": pairs,
            "exact": exact / pairs if pairs else None,
            "within_1": within / pairs if pairs else None}


def _resampled_alpha(units: Sequence[Sequence[Optional[int]]],
                     weights: Sequence[float]) -> float:
    """Interval alpha of ``units`` each taken ``weights`` times (a
    bootstrap resample); NaN where it is undefined."""
    value = jr.alpha([unit for unit, times in zip(units, weights)
                      for _ in range(int(times))], "interval")
    return float("nan") if value is None else value


def people_of(ids: Sequence[str],
              person: Dict[str, str]) -> Tuple[np.ndarray, int]:
    """Each item's person as an index into the people, and how many
    there are. A bootstrap over the people draws people with
    replacement and takes every item of each, so that a person's
    answers, which share their inputs, are not counted as independent.
    An item ``person`` does not name is a person of its own."""
    names = sorted({person.get(i, i) for i in ids})
    index = {name: n for n, name in enumerate(names)}
    return np.array([index[person.get(i, i)] for i in ids],
                    dtype=int), len(names)


def raters_alpha(units: Sequence[Sequence[Optional[int]]],
                 resamples: int = RESAMPLES,
                 people: Optional[Tuple[np.ndarray, int]] = None
                 ) -> Dict[str, Any]:
    """Krippendorff's alpha with the raters as coders (interval metric;
    ordinal beside) over ``units`` (per item, each rater's score or
    None), with the 95% percentile bootstrap over items
    (``judge_reliability.bootstrap``, seeded as METRICS.md's) and,
    beside it, over the people (``people``: each unit's person, from
    ``people_of``; without it each item is its own). A skipped rating
    is a missing value, as alpha allows; an item with fewer than two
    scores pairs nothing."""
    point = jr.alpha(units, "interval")
    out = {"items": sum(1 for unit in units
                        if sum(v is not None for v in unit) >= 2),
           "alpha": point, "alpha_ci": None, "alpha_ci_people": None,
           "alpha_ordinal": jr.alpha(units, "ordinal"),
           **pair_shares(units), "reading": reading(point)}
    if point is not None:
        member, count = people or (np.arange(len(units)), len(units))
        out["alpha_ci"] = jr.bootstrap(
            lambda weights: _resampled_alpha(units, weights), len(units),
            resamples)
        out["alpha_ci_people"] = jr.bootstrap(
            lambda weights: _resampled_alpha(units, weights[member]),
            count, resamples)
    return out


def agreement(a: Dict[str, Dict[str, int]], b: Dict[str, Dict[str, int]],
              resamples: int = RESAMPLES,
              person: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """``judge_reliability.agreement`` of ``b`` with ``a`` (each: scores
    by dimension, then by item id), per dimension, on the items both
    hold: interval alpha with its bootstrap interval, Spearman's rho,
    the mean offset b - a with its 95% t interval, exact agreement. The
    numbers are ``agreement``'s on the same items (it bootstraps each
    dimension from the same seed). Beside them, the 95% percentile
    bootstrap over the people (``person``: item id -> person) of the
    alpha and of the mean offset. A dimension with fewer than two such
    items, or one value only in both, gets its count only: its alpha is
    undefined, in the data and in every resample of it."""
    out: Dict[str, Any] = {}
    for d in DIMENSIONS:
        shared = sorted(set(a[d]) & set(b[d]))
        values = {a[d][i] for i in shared} | {b[d][i] for i in shared}
        if len(shared) < 2 or len(values) < 2:
            out[d] = {"units": len(shared)}
            continue
        rows_a = [{"item_id": i, "repeat": 1,
                   "scores": dict.fromkeys(DIMENSIONS, a[d][i])}
                  for i in shared]
        rows_b = [{"item_id": i, "repeat": 1,
                   "scores": dict.fromkeys(DIMENSIONS, b[d][i])}
                  for i in shared]
        out[d] = jr.agreement(rows_a, 1, rows_b, 1, resamples)[d]
        member, count = people_of(shared, person or {})
        x = np.array([[a[d][i] for i in shared]], dtype=float)
        y = np.array([[b[d][i] for i in shared]], dtype=float)
        offsets = (y - x)[0]
        out[d]["alpha_ci_people"] = jr.bootstrap(
            lambda w: float(jr.two_coder_alphas(x, y, w[member])[0]),
            count, resamples)
        out[d]["offset_ci_people"] = jr.bootstrap(
            lambda w: float((offsets * w[member]).sum() / w[member].sum()),
            count, resamples)
    return out


def two_coder_alpha(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, Any]:
    """Interval alpha between two coders' scores by item, on the items
    both scored (``judge_reliability.alpha``), with their count."""
    shared = sorted(set(a) & set(b))
    return {"units": len(shared),
            "alpha": jr.alpha([[a[i], b[i]] for i in shared], "interval")}


def _comments(item_id: str, raters: Sequence[str],
              rows: Dict[str, Dict[str, dict]]) -> Dict[str, str]:
    """Every rater's comment on the item, from every row (a skipped or
    incomplete rating's comment, which says why, included)."""
    return {r: rows[r][item_id]["comment"] for r in raters
            if item_id in rows[r] and rows[r][item_id]["comment"]}


def _listed(item: dict, dimension: str, raters: Sequence[str],
            complete: Dict[str, Dict[str, dict]],
            rows: Dict[str, Dict[str, dict]],
            medians: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """What a disagreement list shows of an item on a dimension: every
    rater's complete score, their median, every judge's score and the
    keyword score, the cell and the source trial, and every rater's
    comment on the item (``rows``: each rater's rows, complete or not)."""
    item_id = item["item_id"]
    rated = {r: complete[r][item_id] for r in raters
             if item_id in complete[r]}
    return {
        "item_id": item_id, "dimension": dimension,
        "raters": {r: row[dimension] for r, row in rated.items()},
        "median": medians.get(dimension, {}).get(item_id),
        "judges": {name: (scores or {}).get(dimension)
                   for name, scores in item["judges"].items()},
        KEYWORD: (item.get(KEYWORD) or {}).get(dimension),
        "cell": item["cell"], "source": item["source"],
        "comments": _comments(item_id, raters, rows),
    }


def _unmedianed(item: dict, raters: Sequence[str],
                rows: Dict[str, Dict[str, dict]]) -> Dict[str, Any]:
    """What the list of the items without a median shows of one: each
    rater's scores as given (None where a score or the row is missing),
    every rater's comment, every judge's scores and the keyword score,
    the cell and the source trial."""
    item_id = item["item_id"]
    return {
        "item_id": item_id,
        "raters": {r: {d: (rows[r].get(item_id) or {}).get(d)
                       for d in DIMENSIONS} for r in raters},
        "judges": {name: dict(scores or {})
                   for name, scores in item["judges"].items()},
        KEYWORD: item.get(KEYWORD),
        "cell": item["cell"], "source": item["source"],
        "comments": _comments(item_id, raters, rows),
    }


def analyze(key: dict, ratings: Dict[str, Dict[str, dict]],
            resamples: int = RESAMPLES,
            informed: Sequence[str] = ()) -> Dict[str, Any]:
    """The protocol's analysis (docs/HUMAN_RATING.md, "The agreement
    statistic" and "Disagreements") of ``ratings`` (``read_ratings``)
    against ``key``. The warm-up items are left out. A rating counts
    when it has all three scores, as a judgment does; an incomplete or
    missing one is a skipped item: alpha takes it as a missing value,
    and the raters' median exists where every rater scored the item (an
    odd number of raters, so it is one of the scores). Every item enters
    every statistic it can: the lists drop nothing. ``informed``: the
    raters who know the hypotheses, whom the report names."""
    items = [item for item in key["items"] if not item["practice"]]
    ids = [item["item_id"] for item in items]
    raters, sample = sorted(ratings), set(ids)
    unknown = sorted(set(informed) - set(raters))
    if unknown:
        raise ValueError(f"informed raters without ratings: {unknown}")
    rows = {r: {i: row for i, row in ratings[r].items() if i in sample}
            for r in raters}
    complete = {r: {i: row for i, row in rows[r].items()
                    if row["complete"]} for r in raters}
    # Each item's person (the key's ``person``; an older key's item is
    # its own), for the intervals over the people.
    person = {item["item_id"]: item.get("person") or item["item_id"]
              for item in items}
    out: Dict[str, Any] = {
        "sample": key["sample"], "items": len(ids), "raters": raters,
        "informed": sorted(informed),
        "people": len(set(person.values())),
        "judges": dict(key["judges"]), "resamples": resamples,
        "ratings": {r: _rater_summary(ratings[r], ids) for r in raters},
        "threshold": {"reliable": ALPHA_RELIABLE,
                      "tentative": ALPHA_TENTATIVE,
                      "dimensions": list(RULE_DIMENSIONS)},
    }

    # Between the raters.
    units = {d: [[complete[r][i][d] if i in complete[r] else None
                  for r in raters] for i in ids] for d in DIMENSIONS}
    people = people_of(ids, person)
    out["alpha"] = {d: raters_alpha(units[d], resamples, people)
                    if len(raters) > 1
                    else {"items": 0, "alpha": None, "alpha_ci": None,
                          "alpha_ci_people": None, "alpha_ordinal": None,
                          "pairs": 0, "exact": None, "within_1": None,
                          "reading": reading(None)}
                    for d in DIMENSIONS}
    out["threshold"]["met"] = len(raters) > 1 and all(
        out["alpha"][d]["reading"] == "reliable" for d in RULE_DIMENSIONS)

    # Each judge's scores, the keyword score's, and each rater's.
    names = jr.judge_order(key["judges"])
    scored = {name: {d: {item["item_id"]: item["judges"][name][d]
                         for item in items if item["judges"].get(name)}
                     for d in DIMENSIONS} for name in names}
    scored[KEYWORD] = {d: {item["item_id"]: item[KEYWORD][d]
                           for item in items if item.get(KEYWORD)}
                       for d in DIMENSIONS}
    by_rater = {r: {d: {i: row[d] for i, row in complete[r].items()}
                    for d in DIMENSIONS} for r in raters}
    out["pairs"] = {
        f"{a} vs {b}": {d: two_coder_alpha(first[d], second[d])
                        for d in DIMENSIONS}
        for a, b, first, second in (
            [(a, b, by_rater[a], by_rater[b])
             for a, b in itertools.combinations(raters, 2)]
            + [(name, r, scored[name], by_rater[r])
               for name in scored for r in raters])}

    # The raters' median, against each judge and the keyword score.
    rater_rows = [{"item_id": i, "repeat": n, "scores": row}
                  for n, r in enumerate(raters, 1)
                  for i, row in complete[r].items()]
    odd = len(raters) % 2 == 1
    medians = {d: jr.medians_at(rater_rows, d, len(raters))
               for d in DIMENSIONS} if odd else {}
    out["median"] = {
        "raters": len(raters), "defined": odd,
        "items": len(medians.get(DIMENSIONS[0], {})),
        "without": [i for i in ids if i not in medians[DIMENSIONS[0]]]
        if odd else [],
        # How each dimension's comparisons with the median are read
        # (docs/HUMAN_RATING.md, "What follows"): the raters' alpha.
        "reference": {d: out["alpha"][d]["reading"] for d in DIMENSIONS},
    }
    out["against"], out["by_stratum"] = {}, {}
    if odd:
        for name, scores in scored.items():
            out["against"][name] = agreement(medians, scores, resamples,
                                             person)
            out["by_stratum"][name] = _by_stratum(items, medians, scores)
    out["between_judges"] = {
        f"{a} vs {b}": agreement(scored[a], scored[b], resamples, person)
        for a, b in itertools.combinations(names, 2)}

    # The disagreements, item by item.
    def spread(item_id: str, d: str) -> Optional[int]:
        values = [complete[r][item_id][d] for r in raters
                  if item_id in complete[r]]
        return max(values) - min(values) if len(values) > 1 else None

    apart = [(spread(item["item_id"], d), item, d)
             for item in items for d in DIMENSIONS]
    out["disagreements"] = {
        "raters": [
            {**_listed(item, d, raters, complete, rows, medians),
             "spread": s}
            for s, item, d in sorted(
                (x for x in apart if x[0] is not None and x[0] >= SPREAD),
                key=lambda x: (-x[0], x[1]["item_id"],
                               DIMENSIONS.index(x[2])))],
        "judges": {},
        "without_median": [_unmedianed(item, raters, rows)
                           for item in items
                           if item["item_id"] in out["median"]["without"]],
    }
    for name, scores in scored.items():
        listed = []
        for item in items:
            for d in DIMENSIONS:
                median = medians.get(d, {}).get(item["item_id"])
                if median is None or item["item_id"] not in scores[d]:
                    continue
                difference = scores[d][item["item_id"]] - median
                if abs(difference) >= SPREAD:
                    listed.append({**_listed(item, d, raters, complete,
                                             rows, medians),
                                   "difference": difference})
        out["disagreements"]["judges"][name] = sorted(
            listed, key=lambda row: (-abs(row["difference"]),
                                     row["item_id"],
                                     DIMENSIONS.index(row["dimension"])))
    return out


def _rater_summary(rows: Dict[str, dict],
                   ids: Sequence[str]) -> Dict[str, Any]:
    """One rater's counts over the sample: complete ratings, incomplete
    ones (some scores, not all three), items without a row or a score,
    warm-up rows; the median time the page recorded on a complete
    rating of the sample, and the hours on every row (the warm-up and
    skipped items included); the mean score per dimension (a rater's
    leniency, for reading)."""
    sample = set(ids)
    mine = {i: row for i, row in rows.items() if i in sample}
    done = [row for row in mine.values() if row["complete"]]
    partial = sorted(i for i, row in mine.items() if not row["complete"]
                     and any(row[d] is not None for d in DIMENSIONS))
    seconds = [row["seconds"] for row in done if row["seconds"] is not None]
    every = [row["seconds"] for row in rows.values()
             if row["seconds"] is not None]
    return {
        "complete": len(done), "incomplete": partial,
        "not_rated": sorted(i for i in ids if i not in mine or not any(
            mine[i][d] is not None for d in DIMENSIONS)),
        "practice_rows": len(rows) - len(mine),
        "median_seconds": statistics.median(seconds) if seconds else None,
        "hours": sum(every) / 3600 if every else None,
        "mean": {d: statistics.fmean(row[d] for row in done) if done
                 else None for d in DIMENSIONS},
    }


def _by_stratum(items: List[dict], medians: Dict[str, Dict[str, int]],
                scores: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """Per factor of the cell and per level: the mean of (score - the
    raters' median) over the level's items with both, per dimension,
    with its 95% t interval (``judge_reliability.interval``)."""
    out: Dict[str, Any] = {}
    for factor in FACTORS:
        levels = sorted({item["cell"][factor] for item in items}, key=str)
        out[factor] = {str(level): {d: jr.interval([
            float(scores[d][item["item_id"]] - medians[d][item["item_id"]])
            for item in items if item["cell"][factor] == level
            and item["item_id"] in scores[d]
            and item["item_id"] in medians[d]]) for d in DIMENSIONS}
            for level in levels}
    return out


# -- the report ---------------------------------------------------------------

def _n(value: Any, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value:.{digits}f}"


def _ci(point: Any, ci: Any, digits: int = 3) -> str:
    if point is None or ci is None or None in tuple(ci):
        return _n(point, digits)
    return f"{_n(point, digits)} [{_n(ci[0], digits)}, {_n(ci[1], digits)}]"


def _bounds(ci: Any, digits: int = 3) -> str:
    if ci is None or None in tuple(ci):
        return "-"
    return f"[{_n(ci[0], digits)}, {_n(ci[1], digits)}]"


# How a comparison with the raters' median is read, by the raters' alpha
# on the dimension (docs/HUMAN_RATING.md, "What follows").
AS_REFERENCE = {"reliable": "a reference",
                "tentative": "a tentative reference",
                "not reliable": "no reference",
                "undefined": "no reference"}


def _agreement_table(rows: Dict[str, Any], offset: str,
                     reference: Optional[Dict[str, str]] = None
                     ) -> List[str]:
    """A table of ``agreement``'s rows; with ``reference`` (the raters'
    reading per dimension), a column saying how a row is read."""
    extra = " the median is |" if reference else ""
    lines = ["| dimension | items | alpha [95% CI] | over people | "
             f"Spearman | offset ({offset}) [95% CI] | over people | "
             "exact |" + extra,
             "|---|---|---|---|---|---|---|---|" + (
                 "---|" if reference else "")]
    for d in DIMENSIONS:
        r = rows[d]
        read = f" {AS_REFERENCE[reference[d]]} |" if reference else ""
        if "alpha" not in r:
            lines.append(f"| {d} | {r['units']} | - | - | - | - | - | - |"
                         + read)
            continue
        off = r["offset"]
        lines.append(
            f"| {d} | {r['units']} | {_ci(r['alpha'], r['alpha_ci'])} | "
            f"{_bounds(r.get('alpha_ci_people'))} | "
            f"{_n(r['spearman'])} | "
            f"{_ci(off['mean'], (off['ci_low'], off['ci_high']), 2)} | "
            f"{_bounds(r.get('offset_ci_people'), 2)} | "
            f"{_n(r['exact'])} |" + read)
    return lines


def _cell_text(cell: dict) -> str:
    return (f"{cell['version']} {cell['locus']} {cell['backend']} "
            f"{cell['model']} H{cell['h']}")


def _source_text(source: dict) -> str:
    return f"{source['file']} #{source['trial_index']}"


def markdown(result: Dict[str, Any]) -> str:
    """The analysis as a report. Its lists name items by id, cell and
    source trial, and quote the raters' comments; no answer text."""
    raters = result["raters"]
    informed = set(result.get("informed") or [])
    lines = [f"# Human ratings (sample {result['sample']}: "
             f"{result['items']} items, {result.get('people')} people, "
             f"{len(raters)} raters)", ""]
    if raters:
        lines += ["## Ratings", "",
                  "| rater | knows the hypotheses | complete | incomplete | "
                  "not rated | warm-up rows | median seconds per complete "
                  "rating | hours on every row | mean " + " / ".join(
                      DIMENSIONS) + " |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in raters:
            s = result["ratings"][r]
            lines.append(
                f"| {r} | {'yes' if r in informed else 'no'} | "
                f"{s['complete']} | {len(s['incomplete'])} | "
                f"{len(s['not_rated'])} | {s['practice_rows']} | "
                f"{_n(s['median_seconds'], 0)} | {_n(s['hours'], 1)} | "
                + " / ".join(_n(s["mean"][d], 2) for d in DIMENSIONS)
                + " |")
        lines += ["", "Knows the hypotheses: named with `--informed` "
                      "(docs/HUMAN_RATING.md, \"Who rates\"). "
                  + (f"Raters who know them: {', '.join(sorted(informed))}."
                     if informed else "No rater is named as knowing them.")]
        t = result["threshold"]
        lines += [
            "", "## Agreement between the raters", "",
            "Krippendorff's alpha, the raters as coders (interval "
            "metric; ordinal beside); 95% interval: percentile bootstrap "
            f"over items, {result['resamples']} resamples, and beside it "
            "over the people (a person's answers share their inputs, so "
            "the items are not independent).", "",
            "| dimension | items | alpha [95% CI] | over people | ordinal | "
            "exact | within 1 | reading |",
            "|---|---|---|---|---|---|---|---|"]
        for d in DIMENSIONS:
            a = result["alpha"][d]
            lines.append(
                f"| {d} | {a['items']} | {_ci(a['alpha'], a['alpha_ci'])} | "
                f"{_bounds(a.get('alpha_ci_people'))} | "
                f"{_n(a['alpha_ordinal'])} | {_n(a['exact'])} | "
                f"{_n(a['within_1'])} | {a['reading']} |")
        lines += ["", "One rater: no agreement to measure."
                  if len(raters) < 2 else
                  f"The threshold (alpha >= {t['reliable']:.2f} on "
                  f"{' and '.join(t['dimensions'])}): "
                  f"**{'met' if t['met'] else 'not met'}**."]
        if result["pairs"]:
            lines += ["", "### Pairs", "",
                      "Two-coder interval alpha on the items both scored.",
                      "", "| pair | items | " + " | ".join(
                          f"{d} alpha" for d in DIMENSIONS) + " |",
                      "|---|---|" + "---|" * len(DIMENSIONS)]
            for pair, values in result["pairs"].items():
                lines.append(
                    f"| {pair} | {values[DIMENSIONS[0]]['units']} | "
                    + " | ".join(_n(values[d]["alpha"])
                                 for d in DIMENSIONS) + " |")
        m = result["median"]
        lines += ["", "## The raters' median against each score", ""]
        if not m["defined"]:
            lines += [f"Not computed: {m['raters']} raters. The median of "
                      "an even number of scores need not be one of them.",
                      ""]
        else:
            lines += [f"The median of the {m['raters']} raters, on the "
                      f"{m['items']} of {result['items']} items that every "
                      "rater scored. The last column reads the raters' "
                      "alpha on the dimension (docs/HUMAN_RATING.md, "
                      "\"What follows\"): the median is a reference from "
                      f"{t['reliable']:.2f}, a tentative one from "
                      f"{t['tentative']:.3f}, and no reference below; a "
                      "row on no reference is reported and neither "
                      "supports nor counts against the score.", ""]
            for name, rows in result["against"].items():
                label = name if name == KEYWORD else (
                    f"{name} (k = {result['judges'].get(name)})")
                lines += [f"### {label}", ""] + _agreement_table(
                    rows, f"{name} - raters' median",
                    m["reference"]) + [""]
    lines += ["## The judges with each other, on the sample", ""]
    for pair, rows in result["between_judges"].items():
        first, second = pair.split(" vs ")
        lines += [f"### {pair}", ""] + _agreement_table(
            rows, f"{second} - {first}") + [""]
    if result["by_stratum"]:
        lines += ["## Offset by stratum", "",
                  "The mean of (score - raters' median) with its 95% t "
                  "interval, per level of each factor of the cell.", ""]
        for name, factors in result["by_stratum"].items():
            lines += [f"### {name}", "", "| factor | level | items | "
                      + " | ".join(DIMENSIONS) + " |",
                      "|---|---|---|" + "---|" * len(DIMENSIONS)]
            for factor, levels in factors.items():
                for level, dims in levels.items():
                    lines.append(
                        f"| {factor} | {level} | "
                        f"{dims[DIMENSIONS[0]]['n']} | " + " | ".join(
                            _ci(dims[d]["mean"], (dims[d]["ci_low"],
                                                  dims[d]["ci_high"]), 2)
                            for d in DIMENSIONS) + " |")
            lines.append("")
    if raters:
        lines += _disagreement_lines(result)
    return "\n".join(lines).rstrip("\n") + "\n"


def _disagreement_lines(result: Dict[str, Any]) -> List[str]:
    raters = result["raters"]
    judges = list(result["judges"])
    head = ("| item | dimension | " + " | ".join(raters) + " | median | "
            + " | ".join(judges) + f" | {KEYWORD} | cell | source |")
    rule = "|---|---|" + "---|" * (len(raters) + len(judges) + 4)

    def mark(value: Any) -> str:
        return "-" if value is None else str(value)

    def row(entry: dict) -> str:
        return (f"| {entry['item_id']} | {entry['dimension']} | "
                + " | ".join(mark(entry["raters"].get(r)) for r in raters)
                + f" | {mark(entry['median'])} | "
                + " | ".join(mark(entry["judges"].get(j)) for j in judges)
                + f" | {mark(entry[KEYWORD])} | "
                  f"{_cell_text(entry['cell'])} | "
                  f"{_source_text(entry['source'])} |")

    def comments(entries: List[dict]) -> List[str]:
        return [f"- {e['item_id']}, {r}: {' '.join(text.split())}"
                for e in {e["item_id"]: e for e in entries}.values()
                for r, text in e["comments"].items()]

    listed = result["disagreements"]["raters"]
    scored = result["items"] * len(DIMENSIONS)
    lines = ["## Disagreements", "",
             "Every item stays in every statistic above; the lists are "
             "for reading.", "",
             f"### Between the raters ({SPREAD} or more points apart): "
             f"{len(listed)} of {scored} item scores", ""]
    if listed:
        lines += [head, rule] + [row(e) for e in listed]
        lines += [""] + comments(listed)
    for name, entries in result["disagreements"]["judges"].items():
        lines += ["", f"### The raters' median against {name} ({SPREAD} or "
                      f"more points apart): {len(entries)} item scores", ""]
        if entries:
            lines += [head, rule] + [row(e) for e in entries]
            lines += [""] + comments(entries)
    without = result["disagreements"].get("without_median") or []
    if result["median"]["defined"] and without:

        def three(scores: Any) -> str:
            return "/".join(mark((scores or {}).get(d)) for d in DIMENSIONS)

        lines += ["", "### Without a median (a rater skipped the item or "
                      f"left a score out): {len(without)}", "",
                  "Scores as " + "/".join(DIMENSIONS) + ", - where none.",
                  "", "| item | " + " | ".join(raters) + " | "
                  + " | ".join(judges) + f" | {KEYWORD} | cell | source |",
                  "|---|" + "---|" * (len(raters) + len(judges) + 3)]
        lines += [f"| {e['item_id']} | "
                  + " | ".join(three(e["raters"].get(r)) for r in raters)
                  + " | " + " | ".join(three(e["judges"].get(j))
                                       for j in judges)
                  + f" | {three(e[KEYWORD])} | {_cell_text(e['cell'])} | "
                    f"{_source_text(e['source'])} |" for e in without]
        lines += [""] + comments(without)
    return lines


def _clean(value: Any) -> Any:
    """``value`` as strict JSON: NaN as null, tuples as lists."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


# -- command line -------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sample", help="draw the blinded sample and its key")
    s.add_argument("--tree", type=Path, action="append", required=True,
                   help="a directory of runs (<tree>/<run>/.../results_*"
                        ".json); the first gives the answers, each the "
                        "judges' records it holds")
    s.add_argument("--runs", nargs="+", default=None,
                   help="the runs to draw from (default: every run)")
    s.add_argument("--judges", nargs="+", default=list(JUDGE_NAMES))
    s.add_argument("--require-judges", nargs="*", default=None,
                   help="an answer is a candidate only with a complete "
                        "record of each (default: every judge)")
    s.add_argument("--per-cell", type=int, default=PER_CELL)
    s.add_argument("--practice", type=int, default=PRACTICE)
    s.add_argument("--seed", type=int, default=RATING_SEED)
    s.add_argument("--items", type=Path, required=True,
                   help="the raters' file (to write)")
    s.add_argument("--key", type=Path, required=True,
                   help="the key (to write, in another directory)")
    s.add_argument("--allow-short", action="store_true",
                   help="write the sample even when a cell gave fewer "
                        "answers than --per-cell")
    s.add_argument("--force", action="store_true",
                   help="replace files that hold another sample")
    a = sub.add_parser("analyze", help="the raters' agreement, with each "
                                       "other and with each judge")
    a.add_argument("--key", type=Path, required=True)
    a.add_argument("--ratings", type=Path, nargs="*", default=[],
                   help="one CSV per rater, as the page exports it")
    a.add_argument("--resamples", type=int, default=RESAMPLES)
    a.add_argument("--informed", nargs="*", default=[], metavar="RATER",
                   help="the raters who know the hypotheses (the report "
                        "names them)")
    a.add_argument("--md", type=Path)
    a.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if args.command == "sample":
        document, key = make_sample(
            args.tree, args.runs, args.judges, args.require_judges,
            args.per_cell, args.practice, args.seed)
        short = short_cells(key)
        if short and not args.allow_short:
            raise SystemExit(
                f"{len(short)} cells gave fewer than {args.per_cell} "
                f"answers (--allow-short writes the sample anyway): "
                + "; ".join(f"{_cell_text(c['cell'])} ({c['items']})"
                            for c in short))
        write_sample(document, key, args.items, args.key, args.force)
        drawn = Counter(item["person"] for item in key["items"])
        print(json.dumps({
            "sample": key["sample"], "seed": key["seed"],
            "items": sum(not i["practice"] for i in key["items"]),
            "practice": sum(i["practice"] for i in key["items"]),
            "cells": len(key["cells"]), "short_cells": len(short),
            "trials": key["trials"], "excluded": key["excluded"],
            "candidates": key["candidates"],
            "distinct_answers": key["distinct_answers"],
            "people": len(drawn),
            "most_items_of_a_person": max(drawn.values(), default=0),
            "judges": key["judges"]}))
    else:
        key = load_key(args.key)
        result = _clean(analyze(key, read_ratings(args.ratings, key),
                                args.resamples, args.informed))
        if args.json:
            args.json.write_text(json.dumps(result, indent=1) + "\n")
        text = markdown(result)
        if args.md:
            args.md.write_text(text)
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
