"""The decision probe (NeurIPS Subtask 20; AIOS docs/BENCHMARK_V2.md,
Amendment 10): the items revision 4 adds, their scoring, and the
history that asks them."""
import json
import random
import tarfile
from pathlib import Path

import pytest

from benchmarks.shared_memory import dataset, history, synth_v2
from benchmarks.shared_memory.metrics import (
    decision_picks,
    decision_summary,
    letters_named,
    score_decision,
    wilson,
)
from benchmarks.shared_memory.models import V2UserData
from tests.agents.test_history_v2 import managed, run

BASE = dataset.load("users_v1")


@pytest.fixture(scope="module")
def records():
    """150 template-mode users with their items."""
    users = [synth_v2.build_user(i, BASE.users[i]) for i in range(150)]
    return synth_v2.with_decisions(users, BASE.users)


def probe(record, kind):
    (found,) = [p for p in record["probes"] if p["type"] == kind]
    return found


def option(item, kind):
    (found,) = [o for o in item["options"] if o["kind"] == kind]
    return found


def test_each_user_has_two_items_by_the_rule(records):
    assert synth_v2.decision_problems(records, BASE.users) == []
    for record in records:
        d1, d2 = record["decisions"]
        i = record["index"]
        assert [d1["decision_id"], d2["decision_id"]] == [
            f"u{i:03d}-d1", f"u{i:03d}-d2"]
        assert {o["kind"] for o in d1["options"]} == {
            "correct", "stale", "revoked", "foreign"}
        assert {o["kind"] for o in d2["options"]} == {
            "correct", "stale", "private", "foreign"}
        recency, contra = probe(record, "recency"), probe(record,
                                                           "contradiction")
        assert option(d1, "correct")["statement"] == recency["fact_sentence"]
        assert option(d1, "stale")["value"] == contra["forbidden"][0]["value"]
        assert option(d1, "revoked")["statement"] == probe(
            record, "deletion")["fact_sentence"]
        assert option(d2, "correct")["statement"] == contra["fact_sentence"]
        assert option(d2, "stale")["value"] == recency["forbidden"][0][
            "value"]
        private = option(d2, "private")["statement"]
        assert private == synth_v2.neutral_statement(
            probe(record, "privacy")["fact_sentence"])
        for item in (d1, d2):
            assert option(item, "correct")["letter"] == item["correct"]
            assert [o["letter"] for o in item["options"]] == list("ABCD")
            assert item["question"].splitlines() == [
                synth_v2.DECISION_QUESTION, ""] + [
                f"{o['letter']}) {o['statement']}" for o in item["options"]
            ] + ["", synth_v2.DECISION_ANSWER]
            foreign = option(item, "foreign")
            mine = {e.get("slot") for s in record["sessions"]
                    for e in s["events"]}
            assert foreign["slot"] not in mine
            assert foreign["source"].get("user", (i - 1) % 150) == \
                (i - 1) % 150


@pytest.mark.parametrize("text, neutral", [
    ("Off the record: Ravelstone Security is trying to hire away our team "
     "lead.", "Ravelstone Security is trying to hire away our team lead."),
    ("Confidential: we're in early talks to be acquired by Acme.",
     "We're in early talks to be acquired by Acme."),
    ("Keep this private: I have a follow-up appointment with Dr. Okafor.",
     "I have a follow-up appointment with Dr. Okafor."),
    ("I live in Lyon.", "I live in Lyon."),
])
def test_a_private_statement_drops_its_marker(text, neutral):
    assert synth_v2.neutral_statement(text) == neutral


def test_foreign_facts_are_the_previous_users_current_facts(records):
    record, previous = records[5], records[4]
    events = {e["event_id"]: (s["writer"], e)
              for s in previous["sessions"] for e in s["events"]}
    targeted = {e.get("target_event") for _, e in events.values()}
    mine = {e.get("slot") for s in record["sessions"] for e in s["events"]}
    candidates = synth_v2.foreign_candidates(previous, record)
    assert candidates
    for writer, event in candidates:
        assert event["type"] == "add" and not event.get("echo_of")
        assert event["event_id"] not in targeted
        assert synth_v2.SLOTS[event["slot"]].kind in ("role", "filler")
        assert event["slot"] not in mine
        assert events[event["event_id"]][0] == writer


def test_two_items_take_facts_of_two_writers_where_they_can(records):
    by_id = {}
    for record in records:
        for s in record["sessions"]:
            for e in s["events"]:
                by_id[e["event_id"]] = s["writer"]
    two = sum(1 for record in records if len({
        by_id[option(item, "foreign")["source"]["event"]]
        for item in record["decisions"]}) == 2)
    assert two >= 140


def test_with_no_fact_to_give_the_foreign_option_comes_from_a_pool(records):
    users = [dict(r) for r in records]
    users[2] = {**users[2], "sessions": [
        {**s, "events": [e for e in s["events"] if e["type"] != "add"]}
        for s in users[2]["sessions"]]}
    items = synth_v2.decision_items(users, 3, BASE.users)
    sources = [option(item, "foreign")["source"] for item in items]
    assert all("pool" in source for source in sources)
    mine = {e.get("slot") for s in users[3]["sessions"] for e in s["events"]}
    assert all(option(item, "foreign")["slot"] not in mine
               for item in items)


def test_the_option_order_is_seeded(records):
    letters = [item["correct"] for r in records for item in r["decisions"]]
    assert set(letters) == set("ABCD")
    again = synth_v2.decision_items(records, 7, BASE.users)
    assert again == records[7]["decisions"]
    other = synth_v2.decision_items(records, 7, BASE.users, seed=1)
    assert [o["kind"] for i in other for o in i["options"]] != [
        o["kind"] for i in again for o in i["options"]]


def test_the_check_finds_a_changed_item(records):
    changed = [dict(r) for r in records]
    items = json.loads(json.dumps(changed[9]["decisions"]))
    items[0]["correct"] = "D" if items[0]["correct"] != "D" else "A"
    changed[9] = {**changed[9], "decisions": items}
    assert synth_v2.decision_problems(changed, BASE.users) == [
        "user 9: decisions differ from the rule"]


def test_revise_adds_the_items_and_changes_nothing_else(tmp_path):
    source = tmp_path / "r3.jsonl"
    synth_v2.generate(source, n=3)
    lines = [json.loads(line) for line in source.read_text().splitlines()]
    header = {k: v for k, v in lines[0].items() if k != "decisions"}
    header["revision"] = 3
    users = [{k: v for k, v in u.items() if k != "decisions"}
             for u in lines[1:]]
    source.write_text("\n".join(json.dumps(r) for r in [header] + users)
                      + "\n")
    out = tmp_path / "r4.jsonl"
    revised = synth_v2.revise(source, out)
    assert revised["revision"] == 4
    assert revised["revised_from"]["revision"] == 3
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [{k: v for k, v in u.items() if k != "decisions"}
            for u in rows[1:]] == users
    assert all(len(u["decisions"]) == 2 for u in rows[1:])
    assert synth_v2.check(str(out))["problems"] == []
    with pytest.raises(ValueError, match="revision 4"):
        synth_v2.revise(out, tmp_path / "r5.jsonl")


ITEM = {"decision_id": "u000-d1", "correct": "B", "options": [
    {"letter": "A", "kind": "stale", "statement": "I live in Lyon.",
     "value": "Lyon", "aliases": []},
    {"letter": "B", "kind": "correct", "statement": "I live in Porto.",
     "value": "Porto", "aliases": []},
    {"letter": "C", "kind": "revoked", "statement": "My team chats on Slack.",
     "value": "Slack", "aliases": []},
    {"letter": "D", "kind": "foreign",
     "statement": "Our logs go to Building D.", "value": "Building D",
     "aliases": []}]}


@pytest.mark.parametrize("answer, choice, passed, error", [
    ("B", "B", True, None),
    ("(B)", "B", True, None),
    ("Answer: B) I live in Porto.", "B", True, None),
    ("C", "C", False, "revoked"),
    ("A", "A", False, "stale"),
    ("D) Our logs go to Building D.", "D", False, "foreign"),
    ("I am not sure.", None, False, "no_letter"),
    ("B or C", None, False, "multiple_letters"),
    ("A good one is B", None, False, "multiple_letters"),
    ("b", None, False, "no_letter"),
    # a letter named twice is one letter
    ("B. Final answer: B", "B", True, None),
    # an option's statement is removed whatever its case
    ("B, not our logs go to building D.", "B", True, None),
    # a letter beside another letter is no letter
    ("BD", None, False, "no_letter"),
])
def test_a_decision_answer_is_scored_exactly(answer, choice, passed, error):
    out = score_decision(ITEM, answer, "- I live in Porto.\n- Slack it is")
    assert (out["choice"], out["passed"], out["error"]) == (
        choice, passed, error)
    assert out["options_in_block"] == ["correct", "revoked"]


def test_the_block_holds_an_option_by_its_value_or_an_alias():
    item = {**ITEM, "options": [
        dict(o, aliases=["Oporto"]) if o["kind"] == "correct" else o
        for o in ITEM["options"]]}
    out = score_decision(item, "B", "- I moved to Oporto.")
    assert out["options_in_block"] == ["correct"]


def test_letters_ignore_the_options_own_text():
    # "Building D" is an option's text, not a letter named.
    assert letters_named("A) Our logs go to Building D.",
                         ITEM["options"]) == ["A"]


def test_the_cell_summary_counts_errors_against_scored_items():
    rows = [{"passed": True}, {"passed": False, "error": "stale"},
            {"passed": False, "error": "stale"},
            {"passed": None, "turn_error": "raised"}]
    out = decision_summary(rows)
    assert (out["n"], out["passed"], out["accuracy"]) == (3, 1, 1 / 3)
    assert out["stale"] == {"k": 2, "share": 2 / 3}
    assert out["ci"] == wilson(1, 3)   # of the passes


def picked(item, kinds, choice, correct="A", **extra):
    """A scored decision row whose options are ``kinds`` at A-D."""
    options = [{"letter": x, "kind": k} for x, k in zip("ABCD", kinds)]
    kind = next((o["kind"] for o in options if o["letter"] == choice), None)
    return {"decision_id": f"u000-{item}", "options": options,
            "correct": correct, "choice": choice,
            "passed": choice == correct,
            "error": None if choice == correct else kind, **extra}


def test_the_picks_count_each_kind_and_letter_of_the_scored_items():
    d1 = ["correct", "stale", "revoked", "foreign"]
    d2 = ["foreign", "correct", "stale", "private"]
    rows = [picked("d1", d1, "D"), picked("d1", d1, "C"),
            picked("d1", d1, "A"), picked("d2", d2, "D", correct="B"),
            picked("d2", d2, "A", correct="B"),
            # named no letter: scored, not picked
            {**picked("d2", d2, None, correct="B"), "error": "no_letter"},
            # a turn error: not scored
            {**picked("d1", d1, "B"), "passed": None,
             "turn_error": "raised"}]
    out = decision_picks(rows)
    assert (out["items"], out["no_letter"], out["multiple_letters"],
            out["turn_errors"]) == (6, 1, 0, 1)
    one, two, pooled = out["d1"], out["d2"], out["pooled"]
    assert (one["items"], one["picked"]) == (3, 3)
    assert (two["items"], two["picked"]) == (3, 2)
    # revoked (d1) and private (d2) are both must-not-use
    assert one["kinds"]["must_not_use"]["k"] == 1
    assert two["kinds"]["must_not_use"]["k"] == 1
    assert {k: v["k"] for k, v in pooled["kinds"].items()} == {
        "correct": 1, "stale": 0, "must_not_use": 2, "foreign": 2}
    assert pooled["kinds"]["foreign"]["share"] == pytest.approx(2 / 5)
    low, high = pooled["kinds"]["foreign"]["ci"]
    assert low < 2 / 5 < high
    # each kind's interval over the items that named one letter
    assert two["kinds"]["foreign"]["ci"] == wilson(1, 2)
    # letters over the picks, correct letters over every scored item
    assert pooled["letters"] == {"A": 2, "B": 0, "C": 1, "D": 2}
    assert two["correct_letters"] == {"A": 0, "B": 3, "C": 0, "D": 0}
    # chi-square against uniform, 3 degrees of freedom: statistic 2.2
    assert pooled["letters_p"] == pytest.approx(0.53195, abs=1e-5)
    even = decision_picks([picked("d1", d1, x, correct=x) for x in "ABCD"])
    assert even["d1"]["letters_p"] == pytest.approx(1.0)
    assert even["d1"]["correct_letters_p"] == pytest.approx(1.0)
    assert even["d2"]["picked"] == 0
    assert even["d2"]["kinds"]["foreign"] == {"k": 0, "share": None,
                                              "ci": None}
    assert even["d2"]["letters_p"] is None


def test_the_v2_analysis_reports_the_picks():
    from benchmarks.shared_memory import bench_v2_analysis as ba

    d1 = ["correct", "stale", "revoked", "foreign"]
    trial = {"decision_results": [picked("d1", d1, "D"),
                                  picked("d1", d1, "A")]}
    failed = {"failed": True, "decision_results": [picked("d1", d1, "B")]}
    cells = {("qwen", "kernel", "inhouse", "no_memory"): {
        "trials": [trial, failed], "metadata": {}}}
    rows = ba.pick_rows(cells)
    assert [r["item"] for r in rows] == ["d1", "d2", "pooled"]
    assert rows[0]["picked"] == 2          # the failed trial left out
    assert rows[1]["picked"] == 0
    text = ba.markdown(cells, [], [], [], [], [], {},
                       ba.decision_rows(cells), [], rows)
    assert "### Picks by option kind and letter" in text
    assert "| 1 (0.50) [0.09, 0.91] |" in text   # wilson(1, 2)
    assert "| 1/0/0/1 |" in text


def user_of(record):
    return V2UserData(
        index=0, user_id="u0__native_inhouse",
        profile=record["final"]["profile"],
        task_context=record["final"]["task_context"],
        follow_up_query=record["base"]["follow_up_query"],
        sessions=record["sessions"], probes=record["probes"],
        decisions=record["decisions"])


def patched(locus, change):
    """``locus``'s consumer, its ``run`` wrapped by ``change(question,
    real_run, consumer)``."""
    consumer = locus.agents[history.CONSUMER]
    real = consumer.run
    consumer.run = lambda question: change(question, real, consumer)
    return consumer


def test_the_history_asks_the_items_after_the_probes(records):
    record = records[0]
    user = user_of(record)
    correct = {item["question"]: item["correct"]
               for item in record["decisions"]}
    locus = managed("native", answer=lambda q: correct.get(q, "an answer"))
    _, outcome = run(locus, user)
    assert outcome.failure is None
    assert [t.probe["probe_id"] for t in outcome.turns] == [
        p["probe_id"] for p in record["probes"]]
    assert [t.probe["decision_id"] for t in outcome.decision_turns] == [
        "u000-d1", "u000-d2"]
    # Asked after every probe, as fresh consumer turns.
    log = locus.agents[history.CONSUMER].log
    asked = [entry[2] for entry in log if entry[0] == "probe"]
    assert asked[-2:] == ["u000-d1", "u000-d2"]
    results = history.score_decisions(outcome)
    assert [r.passed for r in results] == [True, True]
    assert results[0].diagnostics is not None
    # which options' values the turn's block held
    assert all("correct" in r.options_in_block for r in results)


@pytest.mark.parametrize("raised", [RuntimeError, ConnectionError])
def test_a_decision_turns_error_is_recorded_and_fails_nothing(records,
                                                              raised):
    """An item whose consumer raises (any exception) and one whose
    answer is empty: both turns are recorded with their errors and
    latency, unscored, and the user does not fail (its probes are
    measured as without the items)."""
    record = records[0]
    user = user_of(record)
    first, second = record["decisions"]
    locus = managed("native",
                    answer=lambda q: "" if q == second["question"]
                    else "an answer")

    def run_turn(question, real, consumer):
        if question == first["question"]:
            raise raised("search failed")
        return real(question)
    patched(locus, run_turn)
    _, outcome = run(locus, user)
    assert outcome.failure is None
    assert len(outcome.turns) == len(record["probes"])
    assert all(t.error is None for t in outcome.turns)
    assert outcome.listings[-1]["after"] == "probes"
    failed, empty = outcome.decision_turns
    assert failed.error == (f"consumer raised {raised.__name__}: "
                            "search failed")
    assert failed.latency_seconds > 0
    assert empty.error == "consumer returned an empty answer"
    results = history.score_decisions(outcome)
    assert [r.turn_error for r in results] == [failed.error, empty.error]
    assert [r.passed for r in results] == [None, None]
    assert decision_summary(results)["n"] == 0


def test_a_decision_block_with_wrong_ages_is_a_turn_error(records):
    """A decision turn gets the probes' block-age check: a block built
    at another session is a turn error, not scored."""
    record = records[0]
    first = record["decisions"][0]["decision_id"]
    locus = managed("native")

    def run_turn(question, real, consumer):
        out = real(question)
        if consumer.probe_id == first:
            out["injection_diagnostics"] = dict(
                out["injection_diagnostics"], session=3)
        return out
    patched(locus, run_turn)
    _, outcome = run(locus, user_of(record))
    assert outcome.failure is None
    assert [t.error for t in outcome.decision_turns] == [
        "block built at session 3, not 7", None]
    assert history.score_decisions(outcome)[0].passed is None


def test_a_decision_turns_write_is_a_probe_write(records):
    """The probes' listing is taken after the decision turns, so a row
    a decision turn stored fails the user like a probe turn's."""
    record = records[0]
    decisions = {d["decision_id"] for d in record["decisions"]}
    locus = managed("native")

    def run_turn(question, real, consumer):
        consumer.store_conversation = consumer.probe_id in decisions
        return real(question)
    patched(locus, run_turn)
    _, outcome = run(locus, user_of(record))
    assert outcome.failure == (
        "probe_writes: probe turns stored 2 rows (2 assistant_agent)")


def test_an_agent_trials_backend_usage_counts_its_decision_turns(records):
    """Replicated and native trials' backend and embedding usage is
    their probe turns' and their decision turns'."""
    record = records[0]
    locus = managed("native")

    def run_turn(question, real, consumer):
        out = real(question)
        out["backend_usage"] = {
            "backend_llm_tokens": {"calls": 1, "total_tokens": 10},
            "embedding_tokens": {"calls": 1, "total_tokens": 3}}
        return out
    patched(locus, run_turn)
    _, outcome = run(locus, user_of(record))
    assert outcome.failure is None
    turns = len(record["probes"]) + len(record["decisions"])
    assert outcome.backend_llm_tokens.calls == turns
    assert outcome.embedding_tokens.total_tokens == 3 * turns


def decided(index, errors, echo=False, failed=False):
    """A trial with one decision result per entry of ``errors`` (None:
    correct), d1 first."""
    return {"trial_index": index, "failed": failed,
            "probe_results": [{"type": "deletion",
                               "echo_event": "e1" if echo else None}],
            "decision_results": [
                {"decision_id": f"u{index:03d}-d{n}",
                 "passed": error is None, "error": error}
                for n, error in enumerate(errors, 1)]}


def test_the_v2_analysis_reports_decisions_and_the_criteria():
    from benchmarks.shared_memory import bench_v2_analysis as ba

    def cell(*trials):
        return {"trials": list(trials), "metadata": {}}

    cells = {
        ("qwen", "kernel", "inhouse", "h0"): cell(
            decided(0, [None, None], echo=True), decided(1, [None, None])),
        ("qwen", "replicated", "inhouse", "h0"): cell(
            decided(0, [None, None], echo=True),
            decided(1, [None, "stale"])),
        ("qwen", "kernel", "inhouse", "no_memory"): cell(
            decided(0, ["stale", None]), decided(1, ["foreign", "private"])),
        ("qwen", "kernel", "inhouse", "no_supersession"): cell(
            decided(0, ["stale", None]), decided(1, ["stale", None])),
        ("qwen", "kernel", "inhouse", "writer_scoped"): cell(
            decided(0, ["revoked", None], echo=True),
            decided(1, [None, None])),
        ("qwen", "kernel", "inhouse", "wrong_user"): cell(
            decided(0, [None, None]), decided(1, [None, None])),
        ("qwen", "native", "inhouse", "wrong_user"): cell(
            decided(0, [None, None]), decided(1, ["foreign", None]),
            decided(2, ["stale", "stale"], failed=True)),
    }
    rows = {r["condition"] + "/" + r["locus"]: r
            for r in ba.decision_rows(cells)}
    native = rows["wrong_user/native"]
    assert (native["items"], native["correct"], native["foreign"]) == (
        4, 3, 1)   # the failed trial is left out
    assert (native["ci_low"], native["ci_high"]) == wilson(3, 4)
    assert rows["no_memory/kernel"]["private"] == 1
    assert rows["h0/kernel"]["echo_d1"] == 1
    assert rows["writer_scoped/kernel"]["echo_d1_revoked"] == 1
    checks = {c["criterion"][:2]: c for c in ba.decision_criteria(cells)}
    assert checks["D1"]["holds"] is True          # 7 of 8
    assert checks["D2"]["holds"] is True          # 1 of 4
    assert checks["D3"]["holds"] is True          # 2 stale vs 0 (kernel)
    assert checks["D4"]["holds"] is True          # 1 of 1 vs 0 of 1
    assert checks["D5"]["holds"] is True          # 1 vs 0
    assert checks["D1"]["evidence"] == "7 of 8 over 2 cells"
    # A criterion whose cells are absent is not judged.
    del cells[("qwen", "kernel", "inhouse", "wrong_user")]
    assert {c["criterion"][:2]: c["holds"]
            for c in ba.decision_criteria(cells)}["D5"] is None
    text = ba.markdown(cells, [], [], [], [], [], {},
                       ba.decision_rows(cells), ba.decision_criteria(cells))
    assert "## Decision probe (Amendment 10)" in text
    assert "### Functional criteria D1-D5" in text
    # Each error as its count and share of the items scored; a turn
    # error is counted apart, and not scored.
    assert native["foreign_share"] == pytest.approx(1 / 4)
    assert "| 1 (0.25) |" in text
    assert ("| stale | revoked | private | foreign | no_letter "
            "| multiple_letters | turn_errors | echo_d1 |") in text
    errored = cell(decided(0, [None, None]))
    errored["trials"][0]["decision_results"][1].update(
        passed=None, turn_error="consumer returned an empty answer")
    (row,) = ba.decision_rows({("qwen", "kernel", "inhouse", "h0"): errored})
    assert (row["items"], row["correct"], row["turn_errors"]) == (1, 1, 1)


K, N = (("qwen", locus, "inhouse") for locus in ("kernel", "native"))


def holds(cells):
    """D1-D5's ``holds`` over ``{key: [trial, ...]}``."""
    from benchmarks.shared_memory import bench_v2_analysis as ba

    return {c["criterion"][:2]: c["holds"] for c in ba.decision_criteria(
        {key: {"trials": trials, "metadata": {}}
         for key, trials in cells.items()})}


def test_each_decision_criterion_at_its_edge():
    """Amendment 10's D1-D5 at their bounds: D1 holds at 0.6; D2 fails
    below 0.10; D3 needs strictly more stale errors, against the same
    loci's full system only; D4 and D5 fail when the full system, or
    the kernel, has the error too, and D4 reads the same loci only."""
    ok, stale = [None, None], ["stale", "stale"]
    six_of_ten = [decided(i, ok) for i in range(3)] + [
        decided(3, stale), decided(4, stale)]
    assert holds({(*K, "h0"): six_of_ten})["D1"] is True
    assert holds({(*K, "no_memory"): [decided(0, ["stale", "foreign"])]}
                 )["D2"] is False
    one = [decided(0, ["stale", None])]
    assert holds({(*K, "h0"): one, (*K, "no_supersession"): one}
                 )["D3"] is False
    assert holds({(*K, "h0"): [decided(0, ok)],
                  (*K, "no_supersession"): one,
                  (*N, "h0"): [decided(0, stale)]})["D3"] is True
    revoked = [decided(0, ["revoked", None], echo=True)]
    assert holds({(*K, "h0"): revoked, (*K, "writer_scoped"): revoked}
                 )["D4"] is False
    assert holds({(*K, "h0"): [decided(0, ok, echo=True)],
                  (*K, "writer_scoped"): revoked,
                  (*N, "h0"): revoked})["D4"] is True
    foreign = [decided(0, ["foreign", None])]
    assert holds({(*N, "wrong_user"): foreign, (*K, "wrong_user"): foreign}
                 )["D5"] is False


def test_a_v2_trials_cost_counts_its_decision_turns(tmp_path, records):
    """A v2 trial's assistant tokens and latency are its probe turns'
    and its decision turns', the scope of its backend and embedding
    usage (the kernel's /memory/cost read takes the user's every
    call)."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from benchmarks.shared_memory import run_evaluation
    from benchmarks.shared_memory.pipeline import VariantRunner
    from tests.agents.test_history_v2 import USER_ID, FakeLocus, orchestrator

    path = tmp_path / "v2.jsonl"
    synth_v2.generate(path, n=1)
    o = orchestrator(dataset=str(path))
    o.generator.run_id = "r1"
    o._embed = False
    o.judge = MagicMock()
    o.judge.name = "gpt-5.4"
    record = {"llm": {"profile": 4, "task": 3, "integration": 5}}
    o.judge.evaluate.return_value = SimpleNamespace(
        profile_usage_score=4, task_usage_score=3, integration_score=5,
        judge_attempts=1, record=record)
    locus = FakeLocus()

    def run_history_trial(user, variants=None, *, control=None,
                          recency_session=True):
        user = user.model_copy(update={
            "user_id": USER_ID, "decisions": records[0]["decisions"]})
        outcome = history.run_history(
            user, locus, VariantRunner(None, "kernel"), control=control)
        outcome.backend_extraction = False
        return user, outcome, "kernel"

    pipeline = SimpleNamespace(run_history_trial=run_history_trial)
    with patch.object(run_evaluation, "read_backend_usage",
                      return_value={"backend_llm_tokens": None,
                                    "embedding_tokens": None}):
        trial = o.run_single_trial(0, "kernel_shared", pipeline,
                                   method="kernel_shared")
    assert trial.failed is False, trial.error_message
    assert len(trial.probe_results) == 6
    assert len(trial.decision_results) == 2
    assert trial.token_usage.calls == 8
    assert trial.token_usage.total_tokens == 8 * 15
    turns = [*trial.probe_results, *trial.decision_results]
    assert trial.latency_seconds == pytest.approx(
        sum(t.latency_seconds for t in turns))
    assert all(d.latency_seconds > 0 for d in trial.decision_results)
    # the integration probe's answer, measured (Subtask 20)
    assert trial.judge_free.profile_facts_in_answer is not None
    # the judge's record, on the trial and its integration probe
    assert trial.judges == {"gpt-5.4": record}
    (integration,) = [p for p in trial.probe_results
                      if p.type == "integration"]
    assert integration.judges == {"gpt-5.4": record}


# -- the recorded runs ---------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "decision_runs"
RESULTS = Path(__file__).resolve().parents[2] / "results"


@pytest.mark.parametrize("run", ["decision_functional_s20",
                                 "decision_nomemory150_s20"])
def test_the_v2_analysis_reproduces_the_recorded_decision_runs(tmp_path,
                                                                run):
    """The functional check's and the no-memory check's records, trimmed
    to the fields the analysis reads
    (``fixtures/decision_runs/make_fixtures.py``), give the analysis
    committed with each run: every accuracy, interval, error count,
    pick, chi-square p and criterion."""
    from benchmarks.shared_memory import bench_v2_analysis as ba
    from tests.agents.test_ablation_report import same

    with tarfile.open(FIXTURES / f"{run}.tar.xz") as archive:
        archive.extractall(tmp_path, **(
            {"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    out = tmp_path / "out"
    out.mkdir()
    ba.main([str(tmp_path / run), "--no-criteria",
             "--markdown", str(out / "analysis.md"),
             "--json", str(out / "analysis.json")])
    assert ((out / "analysis.md").read_text()
            == (RESULTS / run / "analysis.md").read_text())
    assert same(json.loads((out / "analysis.json").read_text()),
                json.loads((RESULTS / run / "analysis.json").read_text()))
