"""The human-rating kit (docs/HUMAN_RATING.md): the blinded sample, the
raters' file, the key and the analysis.

Written with the kit and not run when it was committed: the first run
of this file is still to come."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from benchmarks.shared_memory import human_rating as hr
from benchmarks.shared_memory import judge_reliability as jr
from benchmarks.shared_memory.judge import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    build_messages,
    judge_prompt_sha256,
)
from benchmarks.shared_memory.models import (
    SyntheticProfile,
    SyntheticTaskContext,
)

PAGE = Path(hr.__file__).with_name("human_rating.html")
JUDGES = (hr.PRIMARY_JUDGE, hr.SECOND_JUDGE)
DIMS = hr.DIMENSIONS

# -- stored results, made up --------------------------------------------------

PROFILE = {"user_name": "Ana Li", "preferred_tools": ["vim", "git"],
           "preferred_language": "Go", "response_style": "terse"}
TASK = {"current_project": "web", "active_experiment": "load",
        "goals": ["ship"], "blockers": ["flaky ci"], "next_steps": ["fix"]}
RUN = "pilot_v1_hetero"
# A results file's path under its run -> (method, locus): four cells.
CELLS = {
    "qwen/kmem0/h0_kernel_shared/results_kernel_shared.json":
        ("kernel_shared", "kernel"),
    "qwen/kmem0/h2_kernel_shared/results_kernel_shared.json":
        ("kernel_shared", "kernel"),
    "qwen/agent/h0_replicated_mem0/results_replicated_mem0.json":
        ("replicated_mem0", "replicated"),
    "qwen/agent/h0_native_mem0/results_native_mem0.json":
        ("native_mem0", "native"),
}


def record(judge, scores=(3, 4, 2), **extra):
    """A judge's record of a stored trial (``judges[<name>]``)."""
    return {"judge": judge, "repeats": 1, "prompt_version": 2,
            "prompt_sha256": judge_prompt_sha256(),
            "llm": dict(zip(DIMS, scores)), **extra}


def trial(index, method, locus, answer, user=0, judges=JUDGES, **extra):
    """A stored v1 trial of user ``user``, with each judge's record."""
    return {"trial_index": index, "method": method, "locus": locus,
            "failed": False, "follow_up_query": f"question of user {user}",
            "assistant_response": answer,
            "synthetic_profile": {**PROFILE, "user_name": f"User {user}"},
            "synthetic_task_context": TASK,
            "input_sha256": f"inputs of user {user}",
            "judges": {name: record(name) for name in judges}, **extra}


def write_run(root, files):
    for rel, trials in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"conditions": [{"trials": trials}]}))


def grid(tree, users, judges=JUDGES):
    """A run of the four cells: user i in every cell, a different answer
    in each."""
    write_run(tree / RUN, {
        rel: [trial(i, method, locus, f"answer {c}.{i}", user=i,
                    judges=judges) for i in range(users)]
        for c, (rel, (method, locus)) in enumerate(CELLS.items())})
    return tree


def drawn(key):
    return [(i["source"]["file"], i["source"]["trial_index"])
            for i in key["items"]]


def keys_of(value):
    """Every key of a JSON value, at any depth."""
    if isinstance(value, dict):
        for name, inner in value.items():
            yield name
            yield from keys_of(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from keys_of(inner)


# -- the sampler --------------------------------------------------------------

def test_the_same_seed_draws_the_same_sample_and_another_seed_another(
        tmp_path):
    tree = grid(tmp_path / "tree", users=8)
    doc, key = hr.make_sample([tree], per_cell=2, practice=2, seed=11)
    assert hr.make_sample([tree], per_cell=2, practice=2, seed=11) == (
        doc, key)
    for where in ("a", "b"):
        hr.write_sample(doc, key, tmp_path / where / "raters" / "items.json",
                        tmp_path / where / "private" / "key.json")
    for name in ("raters/items.json", "private/key.json"):
        assert (tmp_path / "a" / name).read_bytes() == (
            tmp_path / "b" / name).read_bytes()
    other_doc, other_key = hr.make_sample([tree], per_cell=2, practice=2,
                                          seed=12)
    assert drawn(other_key) != drawn(key)
    assert other_doc["sample"] != doc["sample"]


def test_each_cell_gives_its_count_and_the_warm_up_one_each(tmp_path):
    tree = grid(tmp_path, users=6)
    doc, key = hr.make_sample([tree], per_cell=3, practice=2, seed=5)
    main = [i for i in key["items"] if not i["practice"]]
    warm = [i for i in key["items"] if i["practice"]]
    per_cell = Counter(jr.cell_key(i) for i in main)
    assert len(per_cell) == 4 and set(per_cell.values()) == {3}
    assert [c["items"] for c in key["cells"]] == [3, 3, 3, 3]
    # The warm-up: one answer from each of the first cells visited.
    first = [tuple(c[f] for f in hr.FACTORS) for c in key["order"][:2]]
    assert [jr.cell_key(i) for i in warm] == first
    assert [i["item_id"] for i in key["items"]] == ["p01", "p02"] + [
        f"h{n:03d}" for n in range(1, 13)]
    assert [i["item_id"] for i in doc["items"]] == [
        i["item_id"] for i in key["items"]]
    assert [i["practice"] for i in doc["items"]] == [True] * 2 + [False] * 12


def test_a_short_cell_gives_what_it_has_and_the_command_refuses_it(
        tmp_path):
    tree = grid(tmp_path / "tree", users=2)
    doc, key = hr.make_sample([tree], per_cell=3, practice=0, seed=1)
    assert len(key["items"]) == 8
    assert len(hr.short_cells(key)) == 4
    with pytest.raises(SystemExit):
        hr.main(["sample", "--tree", str(tree), "--per-cell", "3",
                 "--practice", "0", "--items",
                 str(tmp_path / "raters" / "items.json"), "--key",
                 str(tmp_path / "private" / "key.json")])
    assert not (tmp_path / "raters").exists()


def test_failed_trials_other_conditions_and_baselines_are_excluded(
        tmp_path):
    kernel = ("kernel_shared", "kernel")
    other_conditions = [
        {"control": "no_delete"}, {"ablation": {"barrier": "off"}},
        {"fault": "silent_writer"}, {"agents": 8},
        {"concurrency": "parallel"}, {"load": 10},
    ]
    trials = [trial(0, *kernel, "kept"),
              trial(1, *kernel, "failed", failed=True)]
    trials += [trial(n, *kernel, f"condition {n}", **extra)
               for n, extra in enumerate(other_conditions, 2)]
    trials.append(trial(8, "naive_concat", "none", "baseline"))
    trials.append(trial(9, *kernel, "no profile", synthetic_profile=None))
    trials.append(trial(10, *kernel, "unjudged", judges=()))
    second_failed = trial(11, *kernel, "second failed")
    second_failed["judges"][hr.SECOND_JUDGE] = {
        "judge": hr.SECOND_JUDGE, "failed": True, "attempts": 3}
    other_prompt = trial(12, *kernel, "other prompt")
    other_prompt["judges"][hr.PRIMARY_JUDGE]["prompt_sha256"] = "0" * 64
    trials += [second_failed, other_prompt]
    write_run(tmp_path / "pilot_extra", {
        "qwen/kmem0/h0_kernel_shared/results_kernel_shared.json": trials,
        # No model in the path: no cell.
        "misc/kmem0/h0_kernel_shared/results_kernel_shared.json": [
            trial(0, *kernel, "no model")],
    })
    found = hr.candidates([tmp_path])
    assert [c["response"] for c in found["candidates"]] == ["kept"]
    assert found["trials"] == 14
    assert found["excluded"] == {
        "failed": 1, "other_condition": 6, "not_a_locus": 1,
        "no_inputs": 1, "no_cell": 1, "unjudged": 3}
    # Requiring the primary judge only keeps the answer whose second
    # judgment failed.
    primary = hr.candidates([tmp_path], require=[hr.PRIMARY_JUDGE])
    assert [c["response"] for c in primary["candidates"]] == [
        "kept", "second failed"]


def test_an_answer_found_in_two_cells_is_drawn_once(tmp_path):
    # Two cells hold the same three answers (the same query, answer,
    # profile and task context).
    write_run(tmp_path / RUN, {
        rel: [trial(i, method, locus, f"answer {i}", user=i)
              for i in range(3)]
        for rel, (method, locus) in list(CELLS.items())[2:]})
    doc, key = hr.make_sample([tmp_path], per_cell=2, practice=0, seed=4)
    assert key["candidates"] == 6 and key["distinct_answers"] == 3
    hashes = [i["inputs_sha256"] for i in key["items"]]
    assert len(hashes) == len(set(hashes)) == 3
    assert sorted(c["items"] for c in key["cells"]) == [1, 2]
    assert len(hr.short_cells(key)) == 1
    # The key names each drawn answer's twin in the other cell.
    assert [len(i["also"]) for i in key["items"]] == [1, 1, 1]
    assert all(i["also"][0]["cell"] != i["cell"] for i in key["items"])


def test_the_draw_spreads_the_users(tmp_path):
    # Every cell holds the same six users; each pick takes a user drawn
    # least so far, so 12 picks give each user two.
    tree = grid(tmp_path, users=6)
    doc, key = hr.make_sample([tree], per_cell=3, practice=0, seed=9)
    assert sorted(Counter(i["user"] for i in key["items"]).values()) == [
        2] * 6
    for cell in key["cells"]:
        users = [i["user"] for i in key["items"] if i["cell"] == cell["cell"]]
        assert len(users) == len(set(users)) == 3


def test_the_sample_is_numbered_in_an_order_of_its_own(tmp_path):
    tree = grid(tmp_path, users=6)
    doc, key = hr.make_sample([tree], per_cell=3, practice=0, seed=9)
    visited = [tuple(c[f] for f in hr.FACTORS) for c in key["order"]]
    grouped = [cell for cell in visited for _ in range(3)]
    assert [jr.cell_key(i) for i in key["items"]] != grouped
    assert [i["item_id"] for i in doc["items"]] == [
        f"h{n:03d}" for n in range(1, 13)]


def test_a_trial_whose_level_is_not_its_paths_is_refused(tmp_path):
    write_run(tmp_path / RUN, {
        "qwen/kmem0/h2_kernel_shared/results_kernel_shared.json": [
            trial(0, "kernel_shared", "kernel", "a", heterogeneity_level=1)]})
    with pytest.raises(ValueError, match="the path says H = 2"):
        hr.candidates([tmp_path])


def test_two_trees_give_a_judge_each_and_must_hold_one_answer(tmp_path):
    first = grid(tmp_path / "first", users=2, judges=(hr.PRIMARY_JUDGE,))
    second = grid(tmp_path / "second", users=2, judges=(hr.SECOND_JUDGE,))
    found = hr.candidates([first, second])
    assert len(found["candidates"]) == 8
    assert all(set(c["judges"]) == set(JUDGES) for c in found["candidates"])
    assert found["k"] == {hr.PRIMARY_JUDGE: 1, hr.SECOND_JUDGE: 1}
    assert hr.candidates([first])["excluded"]["unjudged"] == 8
    path = second / RUN / next(iter(CELLS))
    data = json.loads(path.read_text())
    data["conditions"][0]["trials"][0]["assistant_response"] = "changed"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="not the answer the first tree"):
        hr.candidates([first, second])


def test_a_judge_used_at_two_k_is_refused(tmp_path):
    tree = grid(tmp_path, users=2)
    path = tree / RUN / next(iter(CELLS))
    data = json.loads(path.read_text())
    data["conditions"][0]["trials"][0]["judges"][hr.PRIMARY_JUDGE][
        "repeats"] = 3
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="more than one k"):
        hr.candidates([tree])


# What a rater must not learn: an explicit list, apart from the module's.
HIDDEN = (
    "run", "file", "path", "source", "trial", "trial_index", "condition",
    "condition_index", "method", "cell", "cells", "order", "version",
    "locus", "backend", "model", "h", "heterogeneity_level", "dataset",
    "user", "user_id", "input_sha256", "inputs_sha256", "judge", "judges",
    "llm", "keyword", "hybrid", "score", "scores", "reasoning", "seed",
    "also", "control", "ablation", "block_text", "rater", "ratings",
)
# Every key the raters' file may hold.
RATERS_KEYS = {
    "kit", "kind", "format", "sample", "rubric", "items", "intro",
    "guidance", "parts", "dimensions", "column", "title", "anchors",
    "item_id", "practice", "profile", "task_context", "query", "response",
}


def test_the_raters_file_holds_no_hidden_field(tmp_path):
    tree = grid(tmp_path / "tree", users=3)
    doc, key = hr.make_sample([tree], per_cell=1, practice=1, seed=2)
    hr.write_sample(doc, key, tmp_path / "raters" / "items.json",
                    tmp_path / "private" / "key.json")
    text = (tmp_path / "raters" / "items.json").read_text()
    names = set(keys_of(json.loads(text)))
    assert names == RATERS_KEYS
    assert not names & set(HIDDEN)
    # Nor a value that tells a source, a cell, a user or a judge.
    for item in key["items"]:
        for value in (item["source"]["file"], item["source"]["method"],
                      item["user"], item["inputs_sha256"]):
            assert value not in text
    assert not re.search(r"gpt|claude|qwen|mem0|kernel|replicated|native"
                         r"|pilot_|results_", text)
    # A file with anything added or changed is refused.
    changes = (
        lambda d: d["items"][0].update(locus="kernel"),
        lambda d: d["rubric"].update(model="qwen"),
        lambda d: d.update(cells=[]),
        lambda d: d["items"][0]["profile"].append(["Backend", "mem0"]),
        lambda d: d["rubric"]["dimensions"][0]["anchors"][0].__setitem__(
            1, "Mentions the user"),
        lambda d: d["items"][1].update(item_id="kernel_1"),
    )
    for n, change in enumerate(changes):
        bad = json.loads(text)
        change(bad)
        assert hr.blind_problems(bad), n
        with pytest.raises(ValueError, match="not blind"):
            hr.write_sample(bad, key, tmp_path / f"r{n}" / "items.json",
                            tmp_path / f"k{n}" / "key.json")


def test_the_key_is_apart_and_complete(tmp_path):
    tree = grid(tmp_path / "tree", users=4)
    doc, key = hr.make_sample([tree], per_cell=1, practice=1, seed=3)
    raters, private = tmp_path / "raters", tmp_path / "private"
    hr.write_sample(doc, key, raters / "items.json", private / "key.json")
    assert sorted(p.name for p in raters.iterdir()) == ["items.json"]
    written = hr.load_key(private / "key.json")
    assert written["sample"] == doc["sample"]
    assert [i["item_id"] for i in written["items"]] == [
        i["item_id"] for i in doc["items"]]
    files = {f"{RUN}/{rel}" for rel in CELLS}
    for item in written["items"]:
        assert item["source"]["run"] == RUN
        assert item["source"]["file"] in files
        assert isinstance(item["source"]["trial_index"], int)
        assert set(item["cell"]) == set(hr.FACTORS)
        assert set(item["judges"]) == set(JUDGES)
        assert all(set(s) == set(DIMS) for s in item["judges"].values())
        assert set(item[hr.KEYWORD]) == set(DIMS)
    # No answer text in the key ("profile" is a dimension's name there).
    assert not set(keys_of(written)) & {"response", "query",
                                        "task_context"}
    assert all(json.dumps(i["response"]) not in json.dumps(written)
               for i in doc["items"])
    # The key never goes in the raters' directory, under it or above it.
    for where in (raters / "key.json", raters / "sub" / "key.json",
                  tmp_path / "key.json"):
        with pytest.raises(ValueError, match="directory of its own"):
            hr.write_sample(doc, key, raters / "items.json", where)
    # Another sample does not replace this one without --force.
    other = hr.make_sample([tree], per_cell=2, practice=1, seed=3)
    with pytest.raises(ValueError, match="another sample"):
        hr.write_sample(*other, raters / "items.json", private / "key.json")
    hr.write_sample(*other, raters / "items.json", private / "key.json",
                    force=True)
    assert hr.load_key(private / "key.json")["sample"] == other[0]["sample"]


def test_the_raters_see_the_judge_prompts_words(tmp_path):
    rubric = hr.rubric()
    template = USER_PROMPT_TEMPLATE.template
    assert [d["column"] for d in rubric["dimensions"]] == list(DIMS)
    for d in rubric["dimensions"]:
        assert d["title"] + ":\n" in template
        assert [a[0] for a in d["anchors"]] == [5, 4, 3, 2, 1]
        for score, words in d["anchors"]:
            assert f"  {score} = {words}\n" in template
    assert rubric["guidance"][0] in SYSTEM_PROMPT
    assert rubric["guidance"][1] in template
    assert rubric["intro"] == template.split("\n")[0]
    assert all(f"--- {title} ---" in template
               for title in rubric["parts"].values())
    # Each line of an item is a line of the judge's user message.
    tree = grid(tmp_path, users=2)
    doc, key = hr.make_sample([tree], per_cell=1, practice=0, seed=1)
    assert doc["rubric"] == rubric
    found = {c["inputs_sha256"]: c
             for c in hr.candidates([tree])["candidates"]}
    for view, keyed in zip(doc["items"], key["items"]):
        c = found[keyed["inputs_sha256"]]
        lines = build_messages(
            c["query"], c["response"], SyntheticProfile(**c["profile"]),
            SyntheticTaskContext(**c["task_context"]))[1]["content"].split(
            "\n")
        for part in ("profile", "task_context"):
            for label, text in view[part]:
                assert f"{label}: {text}" in lines
        assert view["query"] in lines and view["response"] in lines
    assert ["Preferred Tools", "vim, git"] in doc["items"][0]["profile"]


# -- the analysis -------------------------------------------------------------

CELL = {"version": "v1", "locus": "kernel", "backend": "mem0",
        "model": "qwen", "h": 0}


def make_key(n, judges=None, practice=0, cells=None):
    """A key of ``n`` items ``h001``... (and ``practice`` warm-up items):
    ``judges`` maps a judge to its score of each item, the same on every
    dimension; the keyword score is 3 throughout."""
    judges = judges or {}
    items = [{"item_id": f"p{i:02d}", "practice": True, "cell": CELL,
              "source": {"file": "w.json", "trial_index": i},
              "judges": {}, hr.KEYWORD: None}
             for i in range(1, practice + 1)]
    items += [{"item_id": f"h{i:03d}", "practice": False,
               "cell": (cells or [CELL] * n)[i - 1],
               "source": {"file": "f.json", "trial_index": i},
               "judges": {name: dict.fromkeys(DIMS, scores[i - 1])
                          for name, scores in judges.items()},
               hr.KEYWORD: dict.fromkeys(DIMS, 3)}
              for i in range(1, n + 1)]
    return {"kit": hr.KIT, "kind": "key", "format": hr.FORMAT,
            "sample": "s0", "judges": dict.fromkeys(judges, 1),
            "items": items}


def write_ratings(path, rater, scores, sample="s0", comments=None):
    """A rater's CSV, as the page writes it (a byte-order mark, CRLF,
    quoted where needed): ``scores`` maps an item id to its three scores,
    a shorter list, or None (a row with no score)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        out = csv.writer(handle, lineterminator="\r\n")
        out.writerow(hr.CSV_COLUMNS)
        for n, (item_id, given) in enumerate(scores.items(), 1):
            three = (list(given or []) + ["", "", ""])[:3]
            out.writerow([sample, item_id, rater, *three,
                          (comments or {}).get(item_id, ""), "12.5",
                          "2026-11-20T12:00:00.000Z", n])
    return path


def uniform(*per_item):
    """Scores by item id, the same on every dimension."""
    return {f"h{i:03d}": None if s is None else [s] * 3
            for i, s in enumerate(per_item, 1)}


# Krippendorff (2011), "Computing Krippendorff's alpha-reliability": four
# coders, twelve units, missing values; interval alpha 0.849, ordinal
# 0.815 (the same example as test_judge_reliability.py).
EXAMPLE = [
    [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None],
    [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3],
    [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None],
    [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None],
]


def test_the_raters_alpha_reproduces_krippendorffs_example(tmp_path):
    key = make_key(12)
    paths = [write_ratings(tmp_path / f"r{c}.csv", f"r{c}", uniform(*row))
             for c, row in enumerate(EXAMPLE, 1)]
    result = hr.analyze(key, hr.read_ratings(paths, key), resamples=200)
    for d in DIMS:
        a = result["alpha"][d]
        assert round(a["alpha"], 3) == 0.849
        assert round(a["alpha_ordinal"], 3) == 0.815
        assert a["items"] == 11        # the last unit has one value only
        assert a["reading"] == "reliable"
        low, high = a["alpha_ci"]
        assert low < a["alpha"] < high
    assert result["threshold"]["met"] is True
    # Four raters: the median of an even number is not computed.
    assert result["median"]["defined"] is False
    assert result["against"] == {}
    # The interval is seeded: the same twice.
    again = hr.analyze(key, hr.read_ratings(paths, key), resamples=200)
    assert again["alpha"]["profile"]["alpha_ci"] == result["alpha"][
        "profile"]["alpha_ci"]


def test_the_median_against_each_judge(tmp_path):
    # The raters agree on 1, 2, 3, 4; the primary judge scores one more,
    # the second judge the same.
    key = make_key(4, judges={hr.PRIMARY_JUDGE: [2, 3, 4, 5],
                              hr.SECOND_JUDGE: [1, 2, 3, 4]})
    paths = [write_ratings(tmp_path / f"{r}.csv", r, uniform(1, 2, 3, 4))
             for r in ("a", "b", "c")]
    result = hr.analyze(key, hr.read_ratings(paths, key), resamples=200)
    primary = result["against"][hr.PRIMARY_JUDGE]["profile"]
    assert primary["units"] == 4
    # Two coders, 1-4 against 2-5: 1 - (n - 1) * sum (a - b)^2 / (n * SS)
    # with n = 8 values, SS = 12 about their mean 3: 1 - 7 * 4 / 96.
    assert primary["alpha"] == pytest.approx(1 - 28 / 96)
    assert primary["spearman"] == pytest.approx(1.0)
    assert primary["offset"]["mean"] == pytest.approx(1.0)  # judge - median
    assert primary["exact"] == 0.0
    second = result["against"][hr.SECOND_JUDGE]["integration"]
    assert second["alpha"] == pytest.approx(1.0)
    assert second["offset"]["mean"] == pytest.approx(0.0)
    assert second["exact"] == 1.0
    # The judges with each other: second - primary.
    pair = result["between_judges"][f"{hr.PRIMARY_JUDGE} vs "
                                    f"{hr.SECOND_JUDGE}"]
    assert pair["task"]["offset"]["mean"] == pytest.approx(-1.0)


def test_the_median_needs_every_rater_and_is_one_of_their_scores(tmp_path):
    key = make_key(4, judges={hr.PRIMARY_JUDGE: [2, 5, 4, 3]})
    raters = {"a": uniform(1, None, 4, 3), "b": uniform(2, 3, 4, 5),
              "c": uniform(5, 4, 1, 3)}
    paths = [write_ratings(tmp_path / f"{r}.csv", r, s)
             for r, s in raters.items()]
    result = hr.analyze(key, hr.read_ratings(paths, key), resamples=200)
    assert result["median"]["items"] == 3
    assert result["median"]["without"] == ["h002"]
    primary = result["against"][hr.PRIMARY_JUDGE]["profile"]
    # The medians 2, 4, 3 of h001, h003, h004 are the judge's scores.
    assert primary["units"] == 3 and primary["exact"] == 1.0
    # Alpha takes h002's two scores, with a's as a missing value.
    units = [[1, 2, 5], [None, 3, 4], [4, 4, 1], [3, 5, 3]]
    a = result["alpha"]["profile"]
    assert a["alpha"] == pytest.approx(jr.alpha(units, "interval"))
    assert a["items"] == 4
    # Pairs: 10 in all, 2 equal, 4 at most one apart.
    assert (a["pairs"], a["exact"], a["within_1"]) == (10, 0.2, 0.4)
    assert result["pairs"]["a vs c"]["profile"]["alpha"] == pytest.approx(
        jr.alpha([[1, 5], [4, 1], [3, 3]], "interval"))
    assert result["pairs"][f"{hr.PRIMARY_JUDGE} vs b"]["profile"][
        "units"] == 4


def test_missing_and_incomplete_ratings(tmp_path):
    key = make_key(4, practice=1)
    full = uniform(1, 2, 3, 4)
    paths = [
        write_ratings(tmp_path / "a.csv", "a", {"p01": [3, 3, 3], **full}),
        # b: h002 with no score, h003 with one, no row for h004.
        write_ratings(tmp_path / "b.csv", "b", {
            "h001": [1, 1, 1], "h002": None, "h003": [3]}),
        write_ratings(tmp_path / "c.csv", "c", full),
    ]
    ratings = hr.read_ratings(paths, key)
    assert ratings["b"]["h003"]["complete"] is False
    result = hr.analyze(key, ratings, resamples=200)
    assert result["items"] == 4                 # the warm-up is left out
    b = result["ratings"]["b"]
    assert (b["complete"], b["incomplete"], b["not_rated"]) == (
        1, ["h003"], ["h002", "h004"])
    assert result["ratings"]["a"]["practice_rows"] == 1
    assert result["median"]["without"] == ["h002", "h003", "h004"]
    units = [[1, 1, 1], [2, None, 2], [3, None, 3], [4, None, 4]]
    assert result["alpha"]["task"]["alpha"] == pytest.approx(
        jr.alpha(units, "interval"))


def test_the_disagreement_lists(tmp_path):
    key = make_key(3, judges={hr.PRIMARY_JUDGE: [1, 3, 2]})
    raters = {"a": uniform(1, 2, 5), "b": uniform(3, 3, 5),
              "c": uniform(3, 3, 1)}
    comments = {"c": {"h003": 'too long, "generic"'}}
    paths = [write_ratings(tmp_path / f"{r}.csv", r, s,
                           comments=comments.get(r))
             for r, s in raters.items()]
    result = hr.analyze(key, hr.read_ratings(paths, key), resamples=200)
    lists = result["disagreements"]
    # Spread 4 on h003, 2 on h001, 1 on h002 (not listed).
    assert [(e["item_id"], e["dimension"], e["spread"])
            for e in lists["raters"]] == [
        ("h003", d, 4) for d in DIMS] + [("h001", d, 2) for d in DIMS]
    first = lists["raters"][0]
    assert first["raters"] == {"a": 5, "b": 5, "c": 1}
    assert first["median"] == 5
    assert first["judges"] == {hr.PRIMARY_JUDGE: 2}
    assert first[hr.KEYWORD] == 3
    assert first["cell"] == CELL and first["source"]["trial_index"] == 3
    assert first["comments"] == {"c": 'too long, "generic"'}
    # The judge against the median 3, 3, 5: -2 on h001, -3 on h003.
    assert [(e["item_id"], e["difference"])
            for e in lists["judges"][hr.PRIMARY_JUDGE]] == [
        ("h003", -3)] * 3 + [("h001", -2)] * 3
    # Nothing is dropped from the statistics.
    assert result["alpha"]["profile"]["items"] == 3
    assert result["against"][hr.PRIMARY_JUDGE]["profile"]["units"] == 3
    report = hr.markdown(hr._clean(result))
    assert "| h003 | profile | 5 | 5 | 1 | 5 | 2 | 3 |" in report
    assert 'h003, c: too long, "generic"' in report


def test_the_threshold_needs_profile_and_integration(tmp_path):
    assert hr.reading(0.80) == "reliable"
    assert hr.reading(0.7999) == "tentative"
    assert hr.reading(0.667) == "tentative"
    assert hr.reading(0.6669) == "not reliable"
    assert hr.reading(None) == "undefined"
    # Profile and task agree, integration does not.
    key = make_key(6)
    agreed = [1, 2, 3, 4, 5, 1]
    integration = {"a": [1, 2, 3, 4, 5, 1], "b": [5, 4, 3, 2, 1, 5],
                   "c": [3, 3, 3, 3, 3, 3]}
    paths = [write_ratings(tmp_path / f"{r}.csv", r, {
        f"h{i:03d}": [agreed[i - 1], agreed[i - 1], s]
        for i, s in enumerate(values, 1)})
        for r, values in integration.items()]
    result = hr.analyze(key, hr.read_ratings(paths, key), resamples=200)
    assert result["alpha"]["profile"]["reading"] == "reliable"
    assert result["alpha"]["integration"]["reading"] == "not reliable"
    assert result["threshold"]["met"] is False


def test_the_offset_by_stratum(tmp_path):
    native = {**CELL, "locus": "native"}
    key = make_key(4, judges={hr.PRIMARY_JUDGE: [4, 4, 3, 2]},
                   cells=[CELL, CELL, native, native])
    paths = [write_ratings(tmp_path / f"{r}.csv", r, uniform(3, 3, 3, 3))
             for r in ("a", "b", "c")]
    result = hr.analyze(key, hr.read_ratings(paths, key), resamples=200)
    locus = result["by_stratum"][hr.PRIMARY_JUDGE]["locus"]
    assert locus["kernel"]["profile"]["n"] == 2
    assert locus["kernel"]["profile"]["mean"] == pytest.approx(1.0)
    assert locus["native"]["profile"]["mean"] == pytest.approx(-0.5)
    # The median and the keyword score are 3 everywhere: one value in
    # both, so no alpha, only the count.
    assert result["against"][hr.KEYWORD]["profile"] == {"units": 4}


def test_reading_ratings_refuses_what_is_not_this_samples(tmp_path):
    key = make_key(2)
    cases = {
        "sample": write_ratings(tmp_path / "s.csv", "a", uniform(1, 2),
                                sample="other"),
        "no item": write_ratings(tmp_path / "i.csv", "a", {"h009": [1] * 3}),
        "not 1 to 5": write_ratings(tmp_path / "v.csv", "a",
                                    {"h001": [6, 1, 1]}),
        "no rater": write_ratings(tmp_path / "r.csv", "", uniform(1)),
    }
    for message, path in cases.items():
        with pytest.raises(ValueError, match=message):
            hr.read_ratings([path], key)
    once = write_ratings(tmp_path / "a1.csv", "a", uniform(1, 2))
    twice = write_ratings(tmp_path / "a2.csv", "a", uniform(1))
    with pytest.raises(ValueError, match="second row"):
        hr.read_ratings([once, twice], key)
    (tmp_path / "c.csv").write_text("item_id,rater,profile\nh001,a,3\n")
    with pytest.raises(ValueError, match="no column"):
        hr.read_ratings([tmp_path / "c.csv"], key)


def test_a_comment_survives_the_pages_quoting(tmp_path):
    key = make_key(1)
    path = tmp_path / "a.csv"
    path.write_bytes((
        "﻿" + ",".join(hr.CSV_COLUMNS) + "\r\n"
        's0,h001,a,4,5,3,"said ""vim, git""\r\nthen left ",61.5,'
        "2026-11-20T12:00:00.000Z,1\r\n").encode("utf-8"))
    row = hr.read_ratings([path], key)["a"]["h001"]
    assert row["comment"] == 'said "vim, git"\r\nthen left'
    assert (row["profile"], row["task"], row["integration"]) == (4, 5, 3)
    assert row["seconds"] == 61.5 and row["complete"] is True
    assert row["rated_at"] == "2026-11-20T12:00:00.000Z"


def test_the_page_is_self_contained_and_reads_the_rubric_from_the_file():
    page = PAGE.read_text()
    assert not re.search(r"https?:|<link\b|@import|url\(|<img\b|<iframe\b"
                         r"|<script[^>]+src=", page)
    assert "default-src 'none'" in page
    columns = re.search(r"const COLUMNS = \[([^\]]*)\]", page).group(1)
    assert re.findall(r'"([a-z_]+)"', columns) == list(hr.CSV_COLUMNS)
    dims = re.search(r"const DIMS = \[([^\]]*)\]", page).group(1)
    assert re.findall(r'"([a-z_]+)"', dims) == list(DIMS)
    # The page holds no copy of the rubric: it shows the file's.
    assert not any(words in page for d in hr.rubric()["dimensions"]
                   for _, words in d["anchors"])
    assert "localStorage" in page and "try {" in page


def test_the_command_line_draws_and_analyses(tmp_path, capsys):
    tree = grid(tmp_path / "tree", users=3)
    items = tmp_path / "raters" / "items.json"
    key_path = tmp_path / "private" / "key.json"
    assert hr.main(["sample", "--tree", str(tree), "--per-cell", "1",
                    "--practice", "1", "--items", str(items), "--key",
                    str(key_path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert (printed["items"], printed["practice"]) == (4, 1)
    key = hr.load_key(key_path)
    paths = [write_ratings(tmp_path / f"{r}.csv", r, {
        i["item_id"]: [3, 4, 2] for i in key["items"]}, sample=key["sample"])
        for r in ("a", "b", "c")]
    assert hr.main(["analyze", "--key", str(key_path), "--ratings",
                    *map(str, paths), "--resamples", "50", "--md",
                    str(tmp_path / "r.md"), "--json",
                    str(tmp_path / "r.json")]) == 0
    report = (tmp_path / "r.md").read_text()
    assert report.startswith(f"# Human ratings (sample {key['sample']}: "
                             "4 items, 3 raters)")
    assert json.loads((tmp_path / "r.json").read_text())["median"][
        "items"] == 4
