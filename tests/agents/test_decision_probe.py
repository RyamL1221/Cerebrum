"""The decision probe (NeurIPS Subtask 20; AIOS docs/BENCHMARK_V2.md,
Amendment 10): the items revision 4 adds, their scoring, and the
history that asks them."""
import json
import random

import pytest

from benchmarks.shared_memory import dataset, history, synth_v2
from benchmarks.shared_memory.metrics import (
    decision_summary,
    letters_named,
    score_decision,
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
])
def test_a_decision_answer_is_scored_exactly(answer, choice, passed, error):
    out = score_decision(ITEM, answer, "- I live in Porto.\n- Slack it is")
    assert (out["choice"], out["passed"], out["error"]) == (
        choice, passed, error)
    assert out["options_in_block"] == ["correct", "revoked"]


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
    assert out["ci"][0] < 1 / 3 < out["ci"][1]


def test_the_history_asks_the_items_after_the_probes(records):
    record = records[0]
    user = V2UserData(
        index=0, user_id="u0__native_inhouse",
        profile=record["final"]["profile"],
        task_context=record["final"]["task_context"],
        follow_up_query=record["base"]["follow_up_query"],
        sessions=record["sessions"], probes=record["probes"],
        decisions=record["decisions"])
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
