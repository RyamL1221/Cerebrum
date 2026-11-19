"""The judges' reliability (NeurIPS Subtask 20, AIOS docs/METRICS.md,
"Reliability protocol", "The k rule", "Agreement between the judges").

    python -m benchmarks.shared_memory.judge_reliability build \\
        --results results --out benchmarks/shared_memory/data/calibration_v1.jsonl
    python -m benchmarks.shared_memory.judge_reliability judge \\
        --set .../calibration_v1.jsonl --judge gpt-5.4 --repeats 10 \\
        --out results/judge_reliability_s20/gpt-5.4.jsonl
    python -m benchmarks.shared_memory.judge_reliability report \\
        --set .../calibration_v1.jsonl --judgments a.jsonl b.jsonl \\
        --md out.md --json out.json
    python -m benchmarks.shared_memory.judge_reliability directions \\
        --run NAME ORIGINAL_ROOT --rejudged JUDGE:K:ROOT ... --md --json

``build`` draws the calibration set from the judged runs, ``judge``
judges it (resumable: a judgment already in ``--out`` is not made
again), ``report`` computes each judge's reliability, the k rule and the
judges' agreement, ``directions`` the two judges' agreement on the
direction of every paired locus difference of a re-judged run.
"""
import argparse
import hashlib
import itertools
import json
import logging
import math
import random
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from benchmarks.shared_memory.judge import (
    JUDGES,
    ClaudeJudge,
    HybridJudge,
    JudgeFailed,
    batch_judgments,
    judgment,
)
from benchmarks.shared_memory.metrics import DIMENSIONS, SCORE_FIELD
from benchmarks.shared_memory.models import (
    SyntheticProfile,
    SyntheticTaskContext,
)
from benchmarks.shared_memory.probes import t_interval

logger = logging.getLogger(__name__)


def interval(values: List[float]) -> Dict[str, Any]:
    """``{n, mean, ci_low, ci_high}``: the mean with its 95% t interval
    (none for fewer than 2 values)."""
    low, high = t_interval(values)
    return {"n": len(values),
            "mean": statistics.fmean(values) if values else None,
            "ci_low": low, "ci_high": high}

# -- the calibration set ----------------------------------------------------

# The runs judged with prompt v2 and greedy decoding, in the order an
# answer found in several is credited (METRICS.md).
SOURCES = (
    "pilot_v1_hetero", "pilot_v1_amem", "pilot_v1_graphiti",
    "pilot_v1_graphiti_native_filter", "pilot_v1_9d_greedy",
    "bench_v2_smoke", "bench_v2_smoke_a4", "bench_v2_smoke_graphiti",
    "bench_v2_smoke_s17", "bench_v2_smoke_amem",
)
EXCLUDED_METHODS = ("kernel_private", "naive_concat", "vanilla_rag")
CALIBRATION_SEED = 20261120
CALIBRATION_SIZE = 200
BANDS = ("low", "mid", "high")
MODELS = ("qwen", "gpt4o", "llama")
KERNEL_PHASES = {"kinh": "inhouse", "kmem0": "mem0", "kgra": "graphiti",
                 "kamem": "amem"}
BACKENDS = ("inhouse", "mem0", "graphiti", "amem")


def band_of(score: Optional[int]) -> Optional[str]:
    """The stored hybrid integration score's band."""
    if score is None:
        return None
    return "low" if score <= 2 else "mid" if score == 3 else "high"


def cell_of(path: Path, trial: dict) -> Dict[str, Any]:
    """An answer's stratum from its file's path and trial: dataset
    version, locus, backend, model and H."""
    parts = path.parts
    model = next(m for m in MODELS for p in parts
                 if p == m or p.startswith(m + "_"))
    method = trial.get("method") or ""
    backend = next((KERNEL_PHASES[p] for p in parts if p in KERNEL_PHASES),
                   None) if method == "kernel_shared" else next(
        (b for b in BACKENDS if method.endswith("_" + b)), None)
    level = next((int(p[1]) for p in parts if len(p) > 2 and p[0] == "h"
                  and p[1].isdigit() and p[2] == "_"), 0)
    return {"version": "v2" if trial.get("probe_results") else "v1",
            "locus": trial.get("locus"), "backend": backend,
            "model": model, "h": level}


def inputs_sha256(item: dict) -> str:
    """The judge's inputs, hashed: two runs' identical answers to the
    same query for the same user are one candidate."""
    text = json.dumps([item["query"], item["response"], item["profile"],
                       item["task_context"]], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def candidates(results: Path, sources: Sequence[str] = SOURCES) -> List[dict]:
    """Every judged, completed answer of ``sources`` (under ``results``),
    deduplicated by the judge's inputs, in source order."""
    seen, out = set(), []
    for run in sources:
        for path in sorted((results / run).rglob("results_*.json")):
            data = json.loads(path.read_text())
            for condition in data["conditions"]:
                for trial in condition["trials"]:
                    if (trial.get("failed")
                            or trial.get("method") in EXCLUDED_METHODS
                            or trial.get("integration_score") is None):
                        continue
                    item = {
                        "source": {"run": run,
                                   "file": str(path.relative_to(results)),
                                   "trial_index": trial["trial_index"],
                                   "method": trial.get("method"),
                                   "run_id": trial.get("run_id")},
                        "cell": cell_of(path.relative_to(results), trial),
                        "stored": {d: trial.get(SCORE_FIELD[d])
                                   for d in DIMENSIONS},
                        "query": trial["follow_up_query"],
                        "response": trial["assistant_response"],
                        "profile": trial["synthetic_profile"],
                        "task_context": trial["synthetic_task_context"],
                    }
                    item["band"] = band_of(item["stored"]["integration"])
                    item["inputs_sha256"] = inputs_sha256(item)
                    if item["inputs_sha256"] in seen:
                        continue
                    seen.add(item["inputs_sha256"])
                    out.append(item)
    return out


def cell_key(item: dict) -> Tuple:
    c = item["cell"]
    return (c["version"], c["locus"], c["backend"], c["model"], c["h"])


def select(items: List[dict], n: int = CALIBRATION_SIZE,
           seed: int = CALIBRATION_SEED) -> List[dict]:
    """``n`` answers: cells visited round-robin in a seeded order, each
    visit taking one unused answer of the cell's next non-empty band
    (low, mid, high, cycling), drawn at random (seeded)."""
    rng = random.Random(seed)
    pools: Dict[Tuple, Dict[str, List[dict]]] = {}
    for item in items:
        pools.setdefault(cell_key(item), {b: [] for b in BANDS})[
            item["band"]].append(item)
    for bands in pools.values():
        for pool in bands.values():
            rng.shuffle(pool)
    cells = sorted(pools)
    rng.shuffle(cells)
    next_band = {cell: 0 for cell in cells}
    chosen: List[dict] = []
    while len(chosen) < n and any(any(p.values()) for p in pools.values()):
        for cell in cells:
            if len(chosen) == n:
                break
            bands = pools[cell]
            for step in range(len(BANDS)):
                band = BANDS[(next_band[cell] + step) % len(BANDS)]
                if bands[band]:
                    chosen.append(bands[band].pop())
                    next_band[cell] = (BANDS.index(band) + 1) % len(BANDS)
                    break
    for i, item in enumerate(chosen, 1):
        item["item_id"] = f"c{i:03d}"
    return chosen


def build(results: Path, out: Path, n: int = CALIBRATION_SIZE) -> dict:
    items = select(candidates(results), n)
    header = {"type": "header", "set": "calibration_v1", "size": len(items),
              "seed": CALIBRATION_SEED, "sources": list(SOURCES),
              "excluded_methods": list(EXCLUDED_METHODS),
              "bands": {"low": [1, 2], "mid": [3], "high": [4, 5]},
              "band_score": "stored hybrid integration score"}
    lines = [json.dumps(header, sort_keys=True)] + [
        json.dumps({"type": "item", **item}, sort_keys=True)
        for item in items]
    out.write_text("\n".join(lines) + "\n")
    return header


def load_set(path: Path) -> List[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip() and json.loads(line)["type"] == "item"]


def judge_input(item: dict) -> Dict[str, Any]:
    return {"query": item["query"], "response": item["response"],
            "profile": SyntheticProfile(**item["profile"]),
            "task_context": SyntheticTaskContext(**item["task_context"])}


# -- judging ------------------------------------------------------------------

def done_judgments(path: Path) -> Dict[Tuple[str, int], dict]:
    """The judgments already in ``path``, by (item, repeat)."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            out[(row["item_id"], row["repeat"])] = row
    return out


def _row(judge_name: str, item_id: str, outcome: Any) -> dict:
    if isinstance(outcome, JudgeFailed):
        return {"judge": judge_name, "item_id": item_id,
                "failed": True, "attempts": outcome.attempts}
    return {"judge": judge_name, "item_id": item_id, **outcome}


def judge_set(items: List[dict], judge_name: str, repeats: int, out: Path,
              workers: int = 8, limit: Optional[int] = None,
              batch=batch_judgments,
              batch_id: Optional[str] = None) -> int:
    """Judge ``items`` (the first ``limit``) ``repeats`` times with the
    named judge, appending one row per judgment to ``out``; returns the
    judgments made. The primary judge's calls run through the kernel,
    ``workers`` at a time; the second judge's go in one batch."""
    items = items[:limit] if limit else items
    have = done_judgments(out)
    todo = [(item, r) for item in items for r in range(1, repeats + 1)
            if (item["item_id"], r) not in have
            or have[(item["item_id"], r)].get("failed")]
    if not todo:
        return 0
    llm_judge = JUDGES[judge_name]()
    lock = threading.Lock()
    out.parent.mkdir(parents=True, exist_ok=True)

    def write(row):
        with lock, out.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    if isinstance(llm_judge, ClaudeJudge):
        wanted = {}
        for item, r in todo:
            wanted.setdefault(item["item_id"], (item, []))[1].append(r)
        batches = out.with_name(out.name + ".batches")

        def remember(new_id: str) -> None:
            with batches.open("a") as handle:
                handle.write(new_id + "\n")

        extra: Dict[str, Any] = {"on_submit": remember}
        if batch_id:
            extra["batch_id"] = batch_id
        got = batch(llm_judge, {i: judge_input(item)
                                for i, (item, _) in wanted.items()},
                    repeats, **extra)
        for item_id, (_, rs) in wanted.items():
            for r in rs:
                outcome = got[item_id][r]
                row = _row(judge_name, item_id, outcome)
                write({**row, "repeat": r})
        return len(todo)

    hybrid = HybridJudge(judge=llm_judge, name=judge_name)

    def one(pair):
        item, r = pair
        args = judge_input(item)
        try:
            scores, attempts, calls = hybrid.llm_scores(
                args["query"], args["response"], args["profile"],
                args["task_context"])
            outcome = judgment(r, scores, attempts, calls)
        except JudgeFailed as e:
            outcome = e
        write({**_row(judge_name, item["item_id"], outcome), "repeat": r})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    return len(todo)


def token_summary(rows: Iterable[dict]) -> dict:
    """Calls and tokens of judgment rows (failed attempts included)."""
    rows = list(rows)
    usage = [r.get("token_usage") or {} for r in rows]
    prompt = [u.get("prompt_tokens") or 0 for u in usage]
    completion = [u.get("completion_tokens") or 0 for u in usage]
    calls = sum(r.get("attempts") or 0 for r in rows)
    return {"judgments": len(rows), "calls": calls,
            "prompt_tokens": sum(prompt), "completion_tokens": sum(completion),
            "prompt_per_judgment": statistics.mean(prompt) if rows else None,
            "completion_per_judgment": (statistics.mean(completion)
                                        if rows else None)}


# -- Krippendorff's alpha -------------------------------------------------------

def alpha(units: Sequence[Sequence[Optional[float]]],
          metric: str = "interval") -> Optional[float]:
    """Krippendorff's alpha over ``units`` (each a list of coders'
    values, None for a missing one), by the coincidence matrix, for the
    ``nominal``, ``ordinal`` or ``interval`` metric. None when there is
    no disagreement to expect (one value only)."""
    values = sorted({v for u in units for v in u if v is not None})
    index = {v: i for i, v in enumerate(values)}
    o = np.zeros((len(values), len(values)))
    for unit in units:
        present = [v for v in unit if v is not None]
        m = len(present)
        if m < 2:
            continue
        for a, b in itertools.permutations(range(m), 2):
            o[index[present[a]], index[present[b]]] += 1 / (m - 1)
    n_c = o.sum(axis=1)
    n = n_c.sum()
    if n < 2 or len(values) < 2:
        return None
    delta = np.zeros_like(o)
    for c, k in itertools.product(range(len(values)), repeat=2):
        if metric == "nominal":
            delta[c, k] = 0.0 if c == k else 1.0
        elif metric == "interval":
            delta[c, k] = (values[c] - values[k]) ** 2
        elif metric == "ordinal":
            lo, hi = min(c, k), max(c, k)
            delta[c, k] = (n_c[lo:hi + 1].sum() - (n_c[lo] + n_c[hi]) / 2) ** 2
        else:
            raise ValueError(f"unknown metric {metric!r}")
    expected = (np.outer(n_c, n_c) * delta).sum()
    if expected == 0:
        return None
    return float(1 - (n - 1) * (o * delta).sum() / expected)


def two_coder_alphas(a: np.ndarray, b: np.ndarray,
                     weights: Optional[np.ndarray] = None) -> np.ndarray:
    """Interval alpha between coders ``a`` and ``b`` (arrays of shape
    (splits, units), no missing value), per split, with per-unit
    ``weights`` (a bootstrap's multiplicities)."""
    w = np.ones(a.shape[-1]) if weights is None else weights
    n = 2 * w.sum()
    mean = ((a + b) * w).sum(axis=-1, keepdims=True) / n
    ss = (((a - mean) ** 2 + (b - mean) ** 2) * w).sum(axis=-1)
    num = (((a - b) ** 2) * w).sum(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ss > 0, 1 - (n - 1) * num / (n * ss), np.nan)


def repeats_alpha(matrix: np.ndarray,
                  weights: Optional[np.ndarray] = None) -> float:
    """Interval alpha with every repeat a coder (units × repeats, no
    missing value), with per-unit ``weights``."""
    units, m = matrix.shape
    w = np.ones(units) if weights is None else weights
    n = m * w.sum()
    grand = (matrix * w[:, None]).sum() / n
    sst = (((matrix - grand) ** 2) * w[:, None]).sum()
    ssw = (((matrix - matrix.mean(axis=1, keepdims=True)) ** 2)
           * w[:, None]).sum()
    if sst == 0:
        return float("nan")
    return float(1 - (n - 1) * m * ssw / ((m - 1) * n * sst))


def disjoint_splits(repeats: int, k: int) -> List[Tuple[Tuple[int, ...],
                                                        Tuple[int, ...]]]:
    """Every unordered pair of disjoint k-sets of ``repeats`` repeats."""
    out = []
    for a in itertools.combinations(range(repeats), k):
        rest = [r for r in range(repeats) if r not in a]
        for b in itertools.combinations(rest, k):
            if a < b:
                out.append((a, b))
    return out


def split_medians(matrix: np.ndarray, k: int) -> Tuple[np.ndarray,
                                                      np.ndarray]:
    """The two medians of every disjoint split, shape (splits, units)."""
    splits = disjoint_splits(matrix.shape[1], k)
    a = np.stack([np.median(matrix[:, list(s)], axis=1) for s, _ in splits])
    b = np.stack([np.median(matrix[:, list(t)], axis=1) for _, t in splits])
    return a, b


def bootstrap(stat, units: int, resamples: int = 2000,
              seed: int = CALIBRATION_SEED) -> Tuple[float, float]:
    """The 95% percentile interval of ``stat(weights)`` over resamples
    of the units with replacement."""
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(resamples):
        weights = np.bincount(rng.integers(0, units, units),
                              minlength=units).astype(float)
        values.append(stat(weights))
    values = np.array(values)
    values = values[~np.isnan(values)]
    return (float(np.percentile(values, 2.5)),
            float(np.percentile(values, 97.5)))


# -- reliability --------------------------------------------------------------

K_VALUES = (1, 3, 5)
K_RULE_ALPHA = 0.80
K_RULE_DIMENSIONS = ("profile", "integration")


def score_matrix(rows: Iterable[dict], dimension: str,
                 repeats: int) -> Tuple[List[str], np.ndarray, int]:
    """Units × repeats LLM scores; units with a failed or missing repeat
    are dropped (their count returned)."""
    by_item: Dict[str, Dict[int, int]] = {}
    for row in rows:
        if not row.get("failed"):
            by_item.setdefault(row["item_id"], {})[row["repeat"]] = \
                row["scores"][dimension]
    ids, matrix, dropped = [], [], 0
    for item_id in sorted(by_item):
        scores = by_item[item_id]
        if all(r in scores for r in range(1, repeats + 1)):
            ids.append(item_id)
            matrix.append([scores[r] for r in range(1, repeats + 1)])
        else:
            dropped += 1
    return ids, np.array(matrix, dtype=float), dropped


def pair_agreement(matrix: np.ndarray) -> Tuple[float, float]:
    """Exact and within-1 agreement over every pair of repeats."""
    exact, within, pairs = 0, 0, 0
    for i, j in itertools.combinations(range(matrix.shape[1]), 2):
        diff = np.abs(matrix[:, i] - matrix[:, j])
        exact += (diff == 0).sum()
        within += (diff <= 1).sum()
        pairs += len(diff)
    return exact / pairs, within / pairs


def reliability(rows: List[dict], repeats: int,
                resamples: int = 2000) -> Dict[str, Any]:
    """METRICS.md's measures for one judge's judgments, per dimension."""
    out: Dict[str, Any] = {}
    for dimension in DIMENSIONS:
        ids, matrix, dropped = score_matrix(rows, dimension, repeats)
        units = len(ids)
        exact, within = pair_agreement(matrix)
        row: Dict[str, Any] = {
            "units": units, "dropped": dropped,
            "exact": exact, "within_1": within,
            "alpha_repeats": repeats_alpha(matrix),
            "alpha_repeats_ci": bootstrap(
                lambda w: repeats_alpha(matrix, w), units, resamples),
            "alpha_repeats_ordinal": alpha(matrix.tolist(), "ordinal"),
            "median_of_k": {},
        }
        for k in K_VALUES:
            if 2 * k > repeats:
                continue
            a, b = split_medians(matrix, k)
            row["median_of_k"][k] = {
                "splits": a.shape[0],
                "alpha": float(np.nanmean(two_coder_alphas(a, b))),
                "alpha_ci": bootstrap(
                    lambda w: float(np.nanmean(two_coder_alphas(a, b, w))),
                    units, resamples),
                "alpha_ordinal": statistics.mean(
                    v for v in (alpha(list(zip(a[s], b[s])), "ordinal")
                                for s in range(0, a.shape[0],
                                               max(1, a.shape[0] // 50)))
                    if v is not None),
                "exact": float((a == b).mean()),
                "within_1": float((np.abs(a - b) <= 1).mean()),
            }
        out[dimension] = row
    return out


def k_rule(stats: Dict[str, Any]) -> Optional[int]:
    """The smallest k whose median-of-k alpha (point estimate) is at
    least 0.80 on Profile and Integration; None if no k <= 5 does."""
    for k in K_VALUES:
        if all(stats[d]["median_of_k"].get(k, {}).get("alpha", -1)
               >= K_RULE_ALPHA for d in K_RULE_DIMENSIONS):
            return k
    return None


def medians_at(rows: List[dict], dimension: str, k: int) -> Dict[str, int]:
    """Each item's median of its first k repeats (complete ones only)."""
    by_item: Dict[str, Dict[int, int]] = {}
    for row in rows:
        if not row.get("failed"):
            by_item.setdefault(row["item_id"], {})[row["repeat"]] = \
                row["scores"][dimension]
    return {i: int(np.median([s[r] for r in range(1, k + 1)]))
            for i, s in by_item.items()
            if all(r in s for r in range(1, k + 1))}


def agreement(rows_a: List[dict], k_a: int, rows_b: List[dict], k_b: int,
              resamples: int = 2000) -> Dict[str, Any]:
    """Two judges at their own k, per dimension: interval alpha (the
    judges as coders), Spearman's rho and the mean offset b - a."""
    from scipy import stats as sstats

    out = {}
    for dimension in DIMENSIONS:
        a = medians_at(rows_a, dimension, k_a)
        b = medians_at(rows_b, dimension, k_b)
        ids = sorted(set(a) & set(b))
        x = np.array([[a[i] for i in ids]], dtype=float)
        y = np.array([[b[i] for i in ids]], dtype=float)
        rho = sstats.spearmanr(x[0], y[0]).statistic if len(ids) > 2 \
            else None
        out[dimension] = {
            "units": len(ids),
            "alpha": float(two_coder_alphas(x, y)[0]),
            "alpha_ci": bootstrap(
                lambda w: float(two_coder_alphas(x, y, w)[0]), len(ids),
                resamples),
            "spearman": None if rho is None or math.isnan(rho)
            else float(rho),
            "offset": interval([float(v) for v in (y - x)[0]]),
            "exact": float((x == y).mean()),
        }
    return out


def report(items: List[dict], judged: Dict[str, List[dict]],
           repeats: int, resamples: int = 2000) -> Dict[str, Any]:
    """Every judge's reliability and k, and each pair's agreement."""
    out: Dict[str, Any] = {"items": len(items), "repeats": repeats,
                           "judges": {}, "agreement": {}}
    for name, rows in judged.items():
        stats = reliability(rows, repeats, resamples)
        out["judges"][name] = {"reliability": stats, "k": k_rule(stats),
                               "tokens": token_summary(rows)}
    names = sorted(judged)
    for a, b in itertools.combinations(names, 2):
        k_a = out["judges"][a]["k"] or max(K_VALUES)
        k_b = out["judges"][b]["k"] or max(K_VALUES)
        out["agreement"][f"{a} vs {b}"] = {
            "k": {a: k_a, b: k_b},
            **agreement(judged[a], k_a, judged[b], k_b, resamples)}
    return out


def _f(value, digits=3) -> str:
    return "-" if value is None or (isinstance(value, float)
                                    and math.isnan(value)) \
        else f"{value:.{digits}f}"


def markdown(result: Dict[str, Any]) -> str:
    lines = [f"# Judge reliability ({result['items']} answers, "
             f"{result['repeats']} repeats per judge)", ""]
    for name, j in result["judges"].items():
        lines += [f"## {name}", "",
                  f"k by the rule: **{j['k'] if j['k'] else 'none <= 5'}**",
                  "",
                  "| dimension | units | exact | within 1 | alpha (repeats) "
                  "[95% CI] | ordinal | " + " | ".join(
                      f"median of {k}: alpha [95% CI], exact"
                      for k in K_VALUES) + " |",
                  "|---|---|---|---|---|---|" + "---|" * len(K_VALUES)]
        for d, r in j["reliability"].items():
            cells = []
            for k in K_VALUES:
                m = r["median_of_k"].get(k)
                cells.append("-" if not m else
                             f"{_f(m['alpha'])} [{_f(m['alpha_ci'][0])}, "
                             f"{_f(m['alpha_ci'][1])}], {_f(m['exact'])}")
            lines.append(
                f"| {d} | {r['units']} | {_f(r['exact'])} | "
                f"{_f(r['within_1'])} | {_f(r['alpha_repeats'])} "
                f"[{_f(r['alpha_repeats_ci'][0])}, "
                f"{_f(r['alpha_repeats_ci'][1])}] | "
                f"{_f(r['alpha_repeats_ordinal'])} | " + " | ".join(cells)
                + " |")
        t = j["tokens"]
        lines += ["", f"Judgments {t['judgments']}, calls {t['calls']}, "
                      f"tokens {t['prompt_tokens']} in / "
                      f"{t['completion_tokens']} out "
                      f"({_f(t['prompt_per_judgment'], 0)} / "
                      f"{_f(t['completion_per_judgment'], 0)} per "
                      "judgment).", ""]
    for pair, a in result["agreement"].items():
        lines += [f"## {pair}", "", f"At k = {a['k']}.", "",
                  "| dimension | units | alpha [95% CI] | Spearman | "
                  "offset (2nd - 1st) [95% CI] | exact |",
                  "|---|---|---|---|---|---|"]
        for d in DIMENSIONS:
            r = a[d]
            off = r["offset"]
            lines.append(
                f"| {d} | {r['units']} | {_f(r['alpha'])} "
                f"[{_f(r['alpha_ci'][0])}, {_f(r['alpha_ci'][1])}] | "
                f"{_f(r['spearman'])} | {_f(off['mean'], 2)} "
                f"[{_f(off['ci_low'], 2)}, {_f(off['ci_high'], 2)}] | "
                f"{_f(r['exact'])} |")
        lines.append("")
    return "\n".join(lines)


# -- direction agreement -------------------------------------------------------

LOCI = ("kernel", "replicated", "native")


def load_run(root: Path) -> Dict[Tuple, Dict[int, dict]]:
    """A run's trials: (model, locus, backend, H) -> trial index ->
    trial."""
    cells: Dict[Tuple, Dict[int, dict]] = {}
    for path in sorted(root.rglob("results_*.json")):
        data = json.loads(path.read_text())
        for condition in data["conditions"]:
            for trial in condition["trials"]:
                c = cell_of(path.relative_to(root), trial)
                key = (c["model"], c["locus"], c["backend"], c["h"])
                cells.setdefault(key, {})[trial["trial_index"]] = trial
    return cells


def llm_score(trial: Optional[dict], judge: str,
              dimension: str) -> Optional[float]:
    if not trial or trial.get("failed"):
        return None
    record = (trial.get("judges") or {}).get(judge)
    if not record or record.get("failed"):
        return None
    return record["llm"][dimension]


def paired(cells, judge, dimension, model, other, level,
           backends) -> List[float]:
    """Per user, kernel - other on the judge's LLM score, averaged over
    ``backends`` (the pilot's gap; a user missing in any is dropped)."""
    return list(_by_user(cells, judge, dimension, model, other, level,
                         backends).values())


def _by_user(cells, judge, dimension, model, other, level,
             backends) -> Dict[int, float]:
    groups = [set(cells.get((model, locus, b, level), {}))
              for b in backends for locus in ("kernel", other)]
    users = sorted(set.intersection(*groups)) if groups else []
    out = {}
    for index in users:
        diffs = []
        for b in backends:
            k = llm_score(cells[(model, "kernel", b, level)].get(index),
                          judge, dimension)
            o = llm_score(cells[(model, other, b, level)].get(index),
                          judge, dimension)
            if k is None or o is None:
                break
            diffs.append(k - o)
        else:
            out[index] = statistics.mean(diffs)
    return out


def differences(cells, judge: str, dimensions=DIMENSIONS) -> Dict[str, dict]:
    """Every paired locus difference of a run on the judge's LLM score:
    per model, backend and H, kernel - replicated and kernel - native;
    pooled over the backends when there are several; and the H2 - H0
    difference-in-differences over the same backends. Each the mean
    over users with its 95% t interval."""
    out: Dict[str, dict] = {}
    models = sorted({k[0] for k in cells})
    backends = sorted({k[2] for k in cells})
    levels = sorted({k[3] for k in cells})
    groups = [[b] for b in backends] + ([backends] if len(backends) > 1
                                        else [])
    for model, other, dim in itertools.product(
            models, ("replicated", "native"), dimensions):
        for group in groups:
            label = "pooled" if len(group) > 1 else group[0]
            for level in levels:
                d = paired(cells, judge, dim, model, other, level, group)
                if d:
                    out[f"{model} {label} H{level} kernel-{other} {dim}"] \
                        = interval(d)
            if 0 in levels and 2 in levels:
                hi = _by_user(cells, judge, dim, model, other, 2, group)
                lo = _by_user(cells, judge, dim, model, other, 0, group)
                users = sorted(set(hi) & set(lo))
                if users:
                    out[f"{model} {label} H2-H0 kernel-{other} {dim}"] = \
                        interval([hi[u] - lo[u] for u in users])
    return out


def sign(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return 0 if value == 0 else (1 if value > 0 else -1)


def excludes_zero(row: dict) -> bool:
    return (row.get("ci_low") is not None
            and (row["ci_low"] > 0 or row["ci_high"] < 0))


def direction_agreement(a: Dict[str, dict], b: Dict[str, dict]) -> dict:
    """How many differences the two judges give the same sign, overall
    and where either judge's interval excludes 0; the disagreements."""
    keys = sorted(set(a) & set(b))
    same = [k for k in keys if sign(a[k]["mean"]) == sign(b[k]["mean"])]
    decisive = [k for k in keys if excludes_zero(a[k]) or excludes_zero(b[k])]
    return {"differences": len(keys), "same_direction": len(same),
            "decisive": len(decisive),
            "decisive_same_direction": len([k for k in decisive
                                            if k in same]),
            "disagreements": [{"difference": k, "a": a[k], "b": b[k]}
                              for k in keys if k not in same]}


def directions_report(runs: Dict[str, Dict[str, Tuple[str, Path]]],
                      dimensions_of: Dict[str, Sequence[str]]) -> dict:
    """``runs``: run name -> {judge: (judge, re-judged root)}."""
    out = {}
    for run, judged in runs.items():
        per_judge = {judge: differences(load_run(root), judge,
                                        dimensions_of.get(run, DIMENSIONS))
                     for judge, (_, root) in judged.items()}
        names = sorted(per_judge)
        out[run] = {"differences": per_judge, "agreement": {
            f"{x} vs {y}": direction_agreement(per_judge[x], per_judge[y])
            for x, y in itertools.combinations(names, 2)}}
    return out


def directions_markdown(result: dict) -> str:
    lines = ["# Direction agreement", ""]
    for run, r in result.items():
        lines += [f"## {run}", ""]
        judges = sorted(r["differences"])
        keys = sorted(set().union(*(r["differences"][j] for j in judges)))
        if keys:
            lines += ["| difference | " + " | ".join(
                f"{j} mean [95% CI]" for j in judges) + " |",
                "|---|" + "---|" * len(judges)]
            for key in keys:
                cells = []
                for j in judges:
                    row = r["differences"][j].get(key)
                    cells.append("" if row is None else (
                        f"{_f(row['mean'], 2)} [{_f(row['ci_low'], 2)}, "
                        f"{_f(row['ci_high'], 2)}]"))
                lines.append(f"| {key} | " + " | ".join(cells) + " |")
            lines.append("")
        for pair, a in r["agreement"].items():
            lines.append(
                f"{pair}: {a['same_direction']} of {a['differences']} "
                f"differences in the same direction; "
                f"{a['decisive_same_direction']} of {a['decisive']} where "
                "either judge's 95% interval excludes 0.")
            for d in a["disagreements"]:
                lines.append(
                    f"- {d['difference']}: {_f(d['a']['mean'], 2)} vs "
                    f"{_f(d['b']['mean'], 2)}")
        lines.append("")
    return "\n".join(lines)


# -- command line ------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--results", type=Path, default=Path("results"))
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--size", type=int, default=CALIBRATION_SIZE)
    j = sub.add_parser("judge")
    j.add_argument("--set", type=Path, required=True)
    j.add_argument("--judge", choices=sorted(JUDGES), required=True)
    j.add_argument("--repeats", type=int, default=10)
    j.add_argument("--out", type=Path, required=True)
    j.add_argument("--workers", type=int, default=8)
    j.add_argument("--limit", type=int, default=None)
    j.add_argument("--batch-id", default=None,
                   help="the second judge: collect this batch, already "
                        "submitted for every judgment wanted, instead of "
                        "submitting one (its id is in <out>.batches)")
    r = sub.add_parser("report")
    r.add_argument("--set", type=Path, required=True)
    r.add_argument("--judgments", type=Path, nargs="+", required=True)
    r.add_argument("--repeats", type=int, default=10)
    r.add_argument("--resamples", type=int, default=2000)
    r.add_argument("--md", type=Path)
    r.add_argument("--json", type=Path)
    t = sub.add_parser("tokens")
    t.add_argument("judgments", type=Path)
    d = sub.add_parser("directions")
    d.add_argument("--rejudged", nargs="+", required=True,
                   metavar="RUN:JUDGE:ROOT")
    d.add_argument("--integration-only", nargs="*", default=[],
                   metavar="RUN")
    d.add_argument("--md", type=Path)
    d.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: "
                               "%(message)s")
    if args.command == "build":
        print(json.dumps(build(args.results, args.out, args.size)))
    elif args.command == "judge":
        made = judge_set(load_set(args.set), args.judge, args.repeats,
                         args.out, args.workers, args.limit,
                         batch_id=args.batch_id)
        rows = list(done_judgments(args.out).values())
        print(json.dumps({"made": made, **token_summary(rows)}))
    elif args.command == "tokens":
        print(json.dumps(token_summary(done_judgments(args.judgments)
                                       .values())))
    elif args.command == "report":
        items = load_set(args.set)
        judged = {}
        for path in args.judgments:
            rows = list(done_judgments(path).values())
            judged[rows[0]["judge"]] = rows
        result = report(items, judged, args.repeats, args.resamples)
        if args.json:
            args.json.write_text(json.dumps(result, indent=1, default=str))
        text = markdown(result)
        if args.md:
            args.md.write_text(text)
        print(text)
    elif args.command == "directions":
        runs: Dict[str, Dict[str, Tuple[str, Path]]] = {}
        for spec in args.rejudged:
            run, judge, root = spec.split(":", 2)
            runs.setdefault(run, {})[judge] = (judge, Path(root))
        result = directions_report(runs, {
            run: ("integration",) for run in args.integration_only})
        if args.json:
            args.json.write_text(json.dumps(result, indent=1, default=str))
        text = directions_markdown(result)
        if args.md:
            args.md.write_text(text)
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
