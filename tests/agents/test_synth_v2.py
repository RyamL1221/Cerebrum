"""Benchmark v2's generator (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Generation"): determinism, ground truth that
agrees with the script, and the paraphrase rules.

The ground-truth checks re-derive each rule from the script itself
rather than calling the generator's own validator, then also run that
validator on every user.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.shared_memory import dataset, synth_v2
from benchmarks.shared_memory.probes import match_any, value_in

REPO = Path(__file__).resolve().parents[2]
BASE = dataset.load("users_v1")
WRITERS = ("profile_agent", "task_agent", "calendar_agent")
ROLES = ("recall", "recency", "contradiction", "deletion", "privacy")


@pytest.fixture(scope="module")
def users():
    """All 150 users in template mode (no network)."""
    return [synth_v2.build_user(i, BASE.users[i]) for i in range(150)]


def events_of(user):
    return [e for s in user["sessions"] for e in s["events"]]


def session_of(user, event_id):
    for s in user["sessions"]:
        for e in s["events"]:
            if e["event_id"] == event_id:
                return s
    raise KeyError(event_id)


def probe(user, kind):
    (found,) = [p for p in user["probes"] if p["type"] == kind]
    return found


def values(entries):
    return [e["value"] for e in entries]


# -- determinism ----------------------------------------------------------

def test_the_same_seed_gives_the_same_scripts(users):
    again = [synth_v2.build_user(i, BASE.users[i]) for i in range(150)]
    assert again == users
    other = synth_v2.build_user(0, BASE.users[0], seed=synth_v2.SEED + 1)
    assert other["sessions"] != users[0]["sessions"]


def test_template_generation_is_byte_identical(tmp_path):
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    synth_v2.generate(first, n=6)
    synth_v2.generate(second, n=6)
    a = first.read_text().splitlines()
    b = second.read_text().splitlines()
    assert a[1:] == b[1:]  # the users; the header names its path
    assert json.loads(a[0])["users"] == 6


def test_scripts_do_not_depend_on_the_hash_seed():
    code = ("import json; from benchmarks.shared_memory import dataset, "
            "synth_v2; b = dataset.load('users_v1'); print(json.dumps("
            "[synth_v2.build_user(i, b.users[i]) for i in range(4)]))")
    outputs = []
    for hash_seed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed)
        done = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                              env=env, capture_output=True, text=True,
                              timeout=300)
        assert done.returncode == 0, done.stderr[-2000:]
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1]


# -- ground truth ---------------------------------------------------------

def test_every_user_passes_the_generators_own_validation(users):
    problems = [p for i, u in enumerate(users)
                for p in synth_v2.validate_user(u, BASE.users[i])]
    assert problems == []


def test_sessions_and_writers_follow_the_layout(users):
    for user in users:
        sessions = user["sessions"]
        assert [s["session"] for s in sessions] == [1, 2, 3, 4, 5, 6]
        assert [s["writer"] for s in sessions[:3]] == list(WRITERS)
        assert sorted(s["writer"] for s in sessions[3:]) == sorted(WRITERS)
        for s in sessions:
            assert 2 <= len(s["events"]) <= 4
        types = [e["type"] for e in events_of(user)]
        assert types.count("base") == 2
        assert [e["fact_key"] for e in sessions[0]["events"]][0] == \
            "base_profile"
        assert [e["fact_key"] for e in sessions[1]["events"]][0] == \
            "base_task"
        assert [p["type"] for p in user["probes"]] == [
            "deletion", "privacy", "recall", "recency", "contradiction",
            "integration"]


def test_roles_belong_to_the_rotating_writer(users):
    for i, user in enumerate(users):
        for k, role in enumerate(ROLES):
            p = probe(user, role)
            want = WRITERS[(i + k) % 3]
            if role == "contradiction":
                # The role's owner states it first; another contradicts.
                first = [e for e in events_of(user)
                         if e["fact_key"] == p["slot"]
                         and e["type"] == "add"]
                assert session_of(user, first[0]["event_id"])[
                    "writer"] == want
            else:
                assert p["target_writer"] == want, (i, role)
    assert probe(users[4], "privacy")["target_writer"] == "calendar_agent"


def test_a_revoked_value_is_never_expected(users):
    for user in users:
        deletion = probe(user, "deletion")
        revoked = set(values(deletion["forbidden"]))
        assert len(revoked) == 1
        for p in user["probes"]:
            assert not revoked & set(values(p["expected"]))
        revokes = [e for e in events_of(user) if e["type"] == "revoke"]
        assert len(revokes) == 1
        assert revokes[0]["fact_key"] == deletion["slot"]
        adds = [e for e in events_of(user)
                if e["fact_key"] == deletion["slot"] and e["type"] == "add"]
        assert values(deletion["forbidden"]) == [adds[0]["value"]]
        # The add is in the owner's first session, the revoke after it.
        add_s = session_of(user, adds[0]["event_id"])
        rev_s = session_of(user, revokes[0]["event_id"])
        assert add_s["writer"] == rev_s["writer"]
        assert add_s["session"] <= 3 < rev_s["session"]


def test_a_contradicted_value_is_forbidden_and_the_later_one_expected(users):
    for user in users:
        p = probe(user, "contradiction")
        stated = [e for e in events_of(user) if e["fact_key"] == p["slot"]
                  and e["type"] in ("add", "contradict")]
        first, later = stated[0], stated[-1]
        assert (first["type"], later["type"]) == ("add", "contradict")
        assert values(p["forbidden"]) == [first["value"]]
        assert values(p["expected"]) == [later["value"]]
        assert later["target_event"] == first["event_id"]
        s_first = session_of(user, first["event_id"])
        s_later = session_of(user, later["event_id"])
        assert s_first["writer"] != s_later["writer"]
        assert s_first["session"] < s_later["session"]


def test_an_updated_value_is_forbidden_and_the_new_one_expected(users):
    for user in users:
        p = probe(user, "recency")
        stated = [e for e in events_of(user) if e["fact_key"] == p["slot"]
                  and e["type"] in ("add", "update")]
        old, new = stated[0], stated[-1]
        assert (old["type"], new["type"]) == ("add", "update")
        assert values(p["forbidden"]) == [old["value"]]
        assert values(p["expected"]) == [new["value"]]
        assert new["old_value"] == old["value"]
        # The update states only the new value.
        assert not match_any(new["utterance"], old["value"], old["aliases"])
        assert session_of(user, old["event_id"])["writer"] == \
            session_of(user, new["event_id"])["writer"]


def test_a_private_fact_is_forbidden_and_written_last(users):
    for user in users:
        p = probe(user, "privacy")
        (private,) = [e for e in events_of(user) if e["type"] == "private"]
        assert private["sharing"] == "private"
        assert values(p["forbidden"]) == [private["value"]]
        session = session_of(user, private["event_id"])
        assert session["session"] >= 4
        assert session["events"][-1]["event_id"] == private["event_id"]


def test_the_recall_fact_is_never_changed(users):
    for user in users:
        p = probe(user, "recall")
        changes = [e for e in events_of(user) if e["fact_key"] == p["slot"]
                   and e["type"] in ("update", "contradict", "revoke")]
        assert changes == []
        assert values(p["expected"]) and not p["forbidden"]


def test_echoes_carry_the_revoked_value_between_add_and_revoke(users):
    for i, user in enumerate(users):
        echoes = [e for e in events_of(user) if e.get("echo_of")]
        deletion = probe(user, "deletion")
        assert bool(echoes) == (i % 9 in (0, 4, 8)), i
        if not echoes:
            assert deletion["echo_event"] is None
            continue
        (echo,) = echoes
        assert deletion["echo_event"] == echo["event_id"]
        assert echo["value"] == deletion["forbidden"][0]["value"]
        assert value_in(echo["utterance"], echo["value"])
        add = next(e for e in events_of(user)
                   if e["event_id"] == echo["echo_of"])
        revoke = next(e for e in events_of(user) if e["type"] == "revoke")
        s_echo = session_of(user, echo["event_id"])
        assert s_echo["writer"] != session_of(user, add["event_id"])[
            "writer"]
        order = [e["event_id"] for e in events_of(user)]
        assert order.index(add["event_id"]) < order.index(
            echo["event_id"]) < order.index(revoke["event_id"])


def test_questions_and_revokes_name_no_value(users):
    for user in users:
        entries = [(e["value"], e["aliases"]) for e in events_of(user)
                   if e.get("value")]
        for p in user["probes"]:
            for value, aliases in entries:
                assert not match_any(p["question"], value, aliases), (
                    p["question"], value)
        (revoke,) = [e for e in events_of(user) if e["type"] == "revoke"]
        for value, aliases in entries:
            assert not match_any(revoke["utterance"], value, aliases)


def test_values_are_distinct_under_the_matcher(users):
    for user in users:
        facts = {}
        for e in events_of(user):
            if e.get("value") and not e.get("echo_of"):
                facts.setdefault(e["value"], set(e["aliases"]))
        forms = [(v, f) for v, aliases in facts.items()
                 for f in [v, *aliases]]
        for value, form in forms:
            for other, other_form in forms:
                if other != value:
                    assert not value_in(other_form, form), (form, other)
        name_tokens = user["base"]["profile"]["user_name"].split()
        for _, form in forms:
            for token in name_tokens:
                assert not value_in(token, form)
                assert not value_in(form, token)


# -- paraphrase -----------------------------------------------------------

def scripted(answers):
    """A paraphraser that answers from ``answers(request)``."""
    calls = []

    def paraphrase(request):
        calls.append(request)
        return answers(request)
    paraphrase.calls = calls
    return paraphrase


def test_a_good_paraphrase_is_kept():
    para = scripted(lambda r: "Honestly, " + r.text)
    user = synth_v2.build_user(0, BASE.users[0], paraphraser=para)
    kept = [e for e in events_of(user) if e["type"] == "add"]
    assert all(e["paraphrased"] for e in kept)
    assert kept[0]["utterance"] == "Honestly, " + kept[0]["template"]
    bases = [e for e in events_of(user) if e["type"] == "base"]
    assert not any(e["paraphrased"] for e in bases)
    assert user["generation"]["fallbacks"] == []


def test_a_paraphrase_without_its_value_is_retried_then_falls_back():
    para = scripted(lambda r: "I mentioned something earlier.")
    user = synth_v2.build_user(0, BASE.users[0], paraphraser=para)
    adds = [e for e in events_of(user) if e["type"] == "add"]
    assert not any(e["paraphrased"] for e in adds)
    assert all(e["utterance"] == e["template"] for e in adds)
    assert adds[0]["event_id"] in user["generation"]["fallbacks"]
    attempts = user["generation"]["paraphrase_attempts"]
    assert attempts[adds[0]["event_id"]] == synth_v2.PARAPHRASE_RETRIES + 1
    # Each retry gets a fresh seed and the reason it was rejected.
    retries = [c for c in para.calls if c.text == adds[0]["template"]]
    assert len({c.seed for c in retries}) == len(retries)
    assert retries[1].feedback and "does not contain" in retries[1].feedback


def test_a_paraphrase_naming_another_fact_or_too_long_is_rejected():
    user0 = synth_v2.build_user(0, BASE.users[0])
    values_ = [(e["value"], tuple(e["aliases"])) for e in events_of(user0)
               if e.get("value")]
    own, other = values_[0], values_[1]
    assert synth_v2.paraphrase_problems(
        f"About {own[0]}.", own, [other]) == []
    assert synth_v2.paraphrase_problems(
        f"About {own[0]} and {other[0]}.", own, [other])
    long = " ".join(["word"] * 41) + f" {own[0]}"
    assert synth_v2.paraphrase_problems(long, own, [other])
    # A revoke must name no value at all.
    assert synth_v2.paraphrase_problems(
        f"Forget {own[0]}.", None, [own, other])
    assert synth_v2.paraphrase_problems(
        "Please forget my pet's name.", None, [own, other]) == []


def test_an_echo_paraphrase_must_keep_the_revoked_value():
    i = 0  # an echo user
    user = synth_v2.build_user(i, BASE.users[i])
    (echo,) = [e for e in events_of(user) if e.get("echo_of")]

    def answers(request):
        if request.text == echo["template"]:
            return "I booked something for my pet."  # drops the value
        return request.text
    para = scripted(answers)
    again = synth_v2.build_user(i, BASE.users[i], paraphraser=para)
    (echo2,) = [e for e in events_of(again) if e.get("echo_of")]
    assert echo2["paraphrased"] is False
    assert echo2["utterance"] == echo2["template"]
    assert echo2["event_id"] in again["generation"]["fallbacks"]


def test_the_header_records_the_seed_and_rules(tmp_path):
    out = tmp_path / "v2.jsonl"
    header = synth_v2.generate(out, n=3)
    for key in ("format_version", "seed", "sessions", "writers", "probes",
                "base", "paraphrase", "generator_sha256", "pilot"):
        assert key in header
    assert header["format_version"] == 2 and header["seed"] == 20261108
    assert header["pilot"] == {"pilot_v2": 30}
    assert header["base"]["sha256"] == BASE.sha256
