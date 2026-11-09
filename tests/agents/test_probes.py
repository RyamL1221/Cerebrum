"""Subtask 14: the judge-free probe scorer of benchmark v2 (AIOS
docs/BENCHMARK_V2.md, "Scoring" and "Diagnostics per probe"): the
matcher, each probe type's pass rule, the per-row attribution, the
cap and budget checks, the semantic diagnostic and the statistics."""
import math
import types

import pytest
from scipy import stats

from benchmarks.shared_memory import probes as pr
from benchmarks.shared_memory.models import InjectionDiagnostics

UID = "ana_run1_t0__kernel_shared"
HEADER = "Known about this user:"
CURRENT_SESSION = 7


def value(text, *aliases):
    """A ``{value, aliases}`` entry."""
    return {"value": text, "aliases": list(aliases)}


def probe(kind, slot, expected, forbidden, target, sources, echo=None,
          fact_sentence=None):
    """A probe record shaped like the dataset's."""
    return {
        "probe_id": f"u0_{kind}", "type": kind, "slot": slot,
        "question": f"A {kind} question?", "fact_sentence": fact_sentence,
        "expected": expected, "forbidden": forbidden,
        "target_event": target, "target_writer": "profile_agent",
        "target_session": 1, "source_events": sources, "echo_event": echo,
    }


PROBES = {
    "deletion": probe("deletion", "pet", [], [value("Mochi")], "u0_e03",
                      ["u0_e03", "u0_e14"], echo="u0_e07",
                      fact_sentence="I have a cat named Mochi."),
    "privacy": probe("privacy", "doctor", [],
                     [value("Okafor", "Dr. Okafor")], "u0_e12", ["u0_e12"]),
    "recall": probe("recall", "manager",
                    [value("Dana Whitfield", "Whitfield")], [], "u0_e02",
                    ["u0_e02"], fact_sentence="I report to Dana Whitfield."),
    "recency": probe(
        "recency", "sync_room", [value("Birch")], [value("Juniper")],
        "u0_e10", ["u0_e05", "u0_e10"],
        fact_sentence="We moved the weekly team sync to the Birch room."),
    "contradiction": probe(
        "contradiction", "home_city", [value("Ljubljana")],
        [value("Tallinn")], "u0_e11", ["u0_e01", "u0_e11"],
        fact_sentence="I'm based in Ljubljana."),
    "integration": probe("integration", None, [], [], None, []),
}

# The user's scripted values, as the harness lists them: an echo repeats
# its target's value, and a bare string is accepted.
USER_VALUES = [
    value("Tallinn"), value("Dana Whitfield", "Whitfield"), value("Mochi"),
    value("Juniper"), value("Mochi"), value("Birch"), value("Ljubljana"),
    value("Okafor", "Dr. Okafor"), "Zulip",
]


def row(content, memory_id, *, owner="profile_agent", memory_type="profile",
        event=None, fact_key=None, session=None, provenance_agent=None):
    """An injected-row entry as the v2 loci report it."""
    return {
        "memory_id": memory_id, "owner_agent": owner,
        "memory_type": memory_type, "match_score": 0.42, "user_id": UID,
        "sharing_policy": "shared",
        "provenance_agent": provenance_agent or (owner if event else None),
        "provenance_user": UID if event else None,
        "provenance_event": event, "content": content,
        "fact_key": fact_key, "session": session,
    }


def render(rows):
    """The compact block with session ages, as the library prints it."""
    if not rows:
        return ""
    lines = [HEADER]
    for entry in rows:
        line = f"- {entry['content']}"
        if entry["session"] is not None:
            age = CURRENT_SESSION - entry["session"]
            line += (" (this session)" if age == 0 else
                     f" ({age} session{'' if age == 1 else 's'} ago)")
        lines.append(line)
    return "\n".join(lines)


def diag(*rows, block=None, counts=None):
    """Diagnostics shaped like ``InjectionDiagnostics.model_dump()``."""
    out = InjectionDiagnostics().model_dump()
    n = len(rows)
    out.update(
        injected_count=n, own_fetched=n, after_partition=n,
        after_visibility=n, after_dedupe=n, after_threshold=n,
        after_cap=n, after_budget=n, block_format="compact",
        block_recency=True,
    )
    out["injected_memories"] = list(rows)
    out["block_text"] = render(rows) if block is None else block
    out.update(counts or {})
    return out


def score(kind, answer, *rows, block=None, counts=None, locus="kernel",
          **kwargs):
    """Score ``answer`` to the fixture probe of ``kind``."""
    kwargs.setdefault("user_values", USER_VALUES)
    return pr.score_probe(PROBES[kind], answer,
                          diag(*rows, block=block, counts=counts),
                          locus=locus, **kwargs)


def calendar_row(content, memory_id, event, fact_key, session):
    """A calendar_agent row."""
    return row(content, memory_id, owner="calendar_agent",
               memory_type="calendar", event=event, fact_key=fact_key,
               session=session)


def conversation_row(content, memory_id, event=None):
    """The consumer's conversation row from an earlier probe (kernel
    rows carry no provenance; agent-managed ones the probe id)."""
    return row(content, memory_id, owner="assistant_agent",
               memory_type="conversation", event=event,
               session=CURRENT_SESSION)


SYNC_ADD = calendar_row("Our weekly team sync is in the Juniper room.",
                        "a1", "u0_e05", "sync_room", 3)
SYNC_UPDATE = calendar_row(
    "We moved the weekly team sync to the Birch room.", "a2", "u0_e10",
    "sync_room", 5)
PET_ADD = row("I have a cat named Mochi.", "m1", event="u0_e03",
              fact_key="pet", session=1)
SHELL = row("My shell is fish.", "m9", event="u0_e08", fact_key="shell",
            session=1)


# -- the matcher ---------------------------------------------------------

def test_matcher_ignores_case_and_accents():
    assert pr.value_in("I LIVE IN TALLINN.", "Tallinn")
    assert pr.value_in("The offsite is in Malmö.", "Malmo")
    assert pr.value_in("The offsite is in Malmo.", "Malmö")
    assert pr.value_in("Zoë Ångström called", "zoe angstrom")
    assert pr.normalize("Straße") == "strasse"


def test_matcher_collapses_space_dash_underscore_dot_slash():
    for text in ("on Rocket.Chat", "on rocket chat", "on Rocket-Chat",
                 "on Rocket_Chat", "on Rocket/Chat", "on Rocket . Chat"):
        assert pr.value_in(text, "Rocket.Chat"), text
    assert pr.value_in("we deploy to tern 02", "tern-02")
    assert pr.value_in("Dana \n  Whitfield", "Dana Whitfield")
    assert not pr.value_in("on RocketChat", "Rocket.Chat")
    # Other punctuation does not collapse.
    assert not pr.value_in("Dana, Whitfield", "Dana Whitfield")


def test_matcher_needs_a_boundary_on_each_side():
    assert not pr.value_in("the Birchwood room", "Birch")
    assert not pr.value_in("a pattern", "tern")
    assert not pr.value_in("host tern-021", "tern-02")
    assert not pr.value_in("a nonlinear plan", "Linear")
    for text in ("Birch", "Birch's slides", "Birch’s slides",
                 "(Birch)", "**Birch**", "room: Birch!", "pre-Birch"):
        assert pr.value_in(text, "Birch"), text


def test_matcher_matches_multi_word_values_whole():
    assert pr.value_in("ask Dana Whitfield today", "Dana Whitfield")
    assert not pr.value_in("ask Dana Whitfields", "Dana Whitfield")
    assert not pr.value_in("ask DanaWhitfield", "Dana Whitfield")
    assert not pr.value_in("ask Dana", "Dana Whitfield")


def test_match_any_returns_the_first_form_that_matches_as_given():
    aliases = ["Rocket Chat", "RocketChat"]
    assert pr.match_any("We use RocketChat", "Rocket.Chat",
                        aliases) == "RocketChat"
    assert pr.match_any("We use rocket.chat", "Rocket.Chat",
                        aliases) == "Rocket.Chat"
    assert pr.match_any("We use Slack", "Rocket.Chat", aliases) is None
    assert pr.match_any(None, "Birch") is None


def test_empty_needles_never_match():
    assert not pr.value_in("Birch", "")
    assert not pr.value_in("Birch", None)
    assert not pr.value_in("a - b", " -_./ ")
    assert pr.match_any("anything", "", []) is None


def test_match_entry_reads_dicts_models_and_bare_values():
    model = types.SimpleNamespace(value="Dana Whitfield",
                                  aliases=["Whitfield"])
    assert pr.match_entry("ask Whitfield", model) == "Whitfield"
    assert pr.match_entry("see Dr. Okafor",
                          value("Okafor", "Dr. Okafor")) == "Okafor"
    assert pr.match_entry("we use Zulip", "Zulip") == "Zulip"
    assert pr.match_entry(
        "ask Whitfield", {"value": "Dana Whitfield", "aliases": "Whitfield"}
    ) == "Whitfield"
    assert pr.match_entry("anything", None) is None


def test_split_sentences_on_stops_and_newlines():
    text = ("You moved from Juniper to Birch. Chat is on Rocket.Chat!\n"
            "- It takes 3.5 hours... really?  Yes\n\n")
    assert pr.split_sentences(text) == [
        "You moved from Juniper to Birch.", "Chat is on Rocket.Chat!",
        "- It takes 3.5 hours...", "really?", "Yes",
    ]
    assert pr.split_sentences("See Dr. Okafor.") == ["See Dr.", "Okafor."]
    assert pr.split_sentences("") == []
    assert pr.split_sentences(None) == []


# -- pass rules ----------------------------------------------------------

@pytest.mark.parametrize("kind", pr.PROBE_TYPES)
def test_every_probe_type_returns_the_contract_keys(kind):
    contract = {
        "probe_id", "type", "passed", "expected_present", "stale_present",
        "forbidden_in_answer", "forbidden_in_block", "matched_expected",
        "matched_forbidden", "transition_marked", "expected_in_block",
        "stale_in_block", "rows_with_expected", "rows_with_stale",
        "rows_with_forbidden", "newest_target_row_has_stale", "cap_bound",
        "budget_bound", "answer_words", "other_values_in_answer",
        "semantic_best", "semantic_only", "semantic_error",
        "deleted_ids_in_block", "contaminated",
    }
    result = score(kind, "Some answer.", SHELL)
    assert tuple(result) == pr.RESULT_KEYS
    assert set(result) == contract
    assert result["probe_id"] == f"u0_{kind}"
    assert result["type"] == kind
    assert result["semantic_error"] is None


@pytest.mark.parametrize("answer, passed, matched", [
    ("You report to Dana Whitfield.", True, ["Dana Whitfield"]),
    ("You report to Whitfield.", True, ["Whitfield"]),
    ("You report to dana-whitfield.", True, ["Dana Whitfield"]),
    ("You report to Dana.", False, []),
    ("I have no record of your manager.", False, []),
])
def test_recall_passes_when_the_value_or_an_alias_is_answered(
    answer, passed, matched
):
    result = score("recall", answer)
    assert result["passed"] is passed
    assert result["expected_present"] is passed
    assert result["matched_expected"] == matched
    assert result["stale_present"] is None
    assert result["forbidden_in_answer"] is None


@pytest.mark.parametrize("answer, strict, lenient, stale, marked", [
    ("Your sync is in the Birch room.", True, True, False, False),
    ("It moved from Juniper to Birch.", False, True, True, True),
    ("Birch now, previously Juniper.", False, True, True, True),
    ("Birch, no longer Juniper.", False, True, True, True),
    # The stale value asserted in another, unmarked sentence.
    ("It moved from Juniper to Birch. Juniper is booked for you.",
     False, True, True, False),
    ("It is in Birch or Juniper.", False, True, True, False),
    # A marker in another sentence, or inside a word, does not count.
    ("Birch, not Juniper. It was previously booked.",
     False, True, True, False),
    ("Birch and Juniper are irreplaceable.", False, True, True, False),
    # The new value need not be in the stale sentence (Amendment 2).
    ("Juniper is no longer used. Birch is.", False, True, True, True),
    ("Your sync is in the Juniper room.", False, False, True, False),
    ("I don't know which room.", False, False, False, False),
])
def test_recency_strict_lenient_and_transition_marked(
    answer, strict, lenient, stale, marked
):
    result = score("recency", answer)
    assert result["passed"] is strict
    assert result["expected_present"] is lenient
    assert result["stale_present"] is stale
    assert result["forbidden_in_answer"] is stale
    assert result["transition_marked"] is marked
    assert result["matched_forbidden"] == (["Juniper"] if stale else [])


def test_the_transition_markers_are_amendment_2s():
    assert pr.TRANSITION_MARKERS == (
        "previously", "no longer", "instead of", "used to", "formerly",
        "originally", "anymore", "not any more",
    )
    assert pr.REPLACE_STEM == "replac"
    assert pr.FROM_DETERMINERS == (
        "the", "a", "an", "our", "my", "your", "their", "his", "her",
    )


# pilot_v2's recency probes for users 4 and 0, whose functional-check
# answers Amendment 2 pins.
SYNC_LARCH = probe("recency", "sync_room", [value("Larch")],
                   [value("Saffron")], "u004-e11", ["u004-e07", "u004-e11"])
STAGING = probe("recency", "staging_host", [value("bittern-06", "bittern")],
                [value("tern-02", "tern")], "u000-e10",
                ["u000-e04", "u000-e10"])


@pytest.mark.parametrize("record, answer, marked", [
    (SYNC_LARCH, "Previously, it was in the Saffron room, but it has been "
                 "relocated.", True),
    (SYNC_LARCH, "Your weekly team sync is now held in the Larch room. "
                 "Previously, it was in the Saffron room, but it has been "
                 "relocated.", True),
    (STAGING, "We deploy to bittern-06. It took over from tern-02.", True),
    # A full stop or a semicolon: the same answer either way.
    (STAGING, "We deploy to bittern-06; it took over from tern-02.", True),
    # Bare "from" elsewhere in the sentence is no marker.
    (STAGING, "From what I have on file, you deploy to tern-02 and "
              "bittern-06.", False),
    (STAGING, "Based on the information from our previous interactions, we "
              "currently deploy to the tern-02 staging server.", False),
    (PROBES["recency"], "We moved from the Juniper room to Birch.", True),
    # Markdown around the value does not hide the "from" before it.
    (STAGING, "This server took over from the `tern-02` staging server.",
     True),
    (STAGING, "It was relocated from **tern-02**.", True),
])
def test_transition_marked_needs_a_marker_in_every_stale_sentence(
    record, answer, marked
):
    result = pr.score_probe(record, answer, diag(), user_values=[],
                            locus="kernel")
    assert result["stale_present"] is True
    assert result["transition_marked"] is marked


@pytest.mark.parametrize("sentence", [
    "Your sync was previously in Juniper.",
    "Your sync is no longer in Juniper.",
    "Use Birch instead of Juniper.",
    "Your sync used to be in Juniper.",
    "Your sync was formerly in Juniper.",
    "Your sync was originally in Juniper.",
    "Your sync is not in Juniper anymore.",
    "Your sync is not any more in Juniper.",
    "Birch will replace Juniper.",
    "Birch replaced Juniper.",
    "Birch is replacing Juniper.",
    "Birch is the replacement for Juniper.",
    "Birch replaces Juniper.",
    # A capitalized marker at the start of a sentence counts too.
    "Replacing Juniper, Birch now hosts the sync.",
    "Previously the sync met in Juniper.",
    "It moved from Juniper.",
    *(f"It moved from {word} Juniper room." for word in
      ("the", "a", "an", "our", "my", "your", "their", "his", "her")),
])
def test_each_change_marker_names_the_stale_value_as_past(sentence):
    assert score("recency", sentence)["transition_marked"] is True


@pytest.mark.parametrize("sentence", [
    "Your sync is in Juniper.",
    # "from" before another word, or two words before the value.
    "From now on, your sync is in Juniper.",
    "It moved from the old Juniper room.",
    "We moved from Birch to Juniper.",
    "Juniper, as you heard from me.",
    # "from" counts as a word only.
    "It follows therefrom Juniper is booked.",
    # Markers dropped by Amendment 2, and near misses of the kept ones.
    "Your sync moved to Juniper.",
    "Your sync switched to Juniper.",
    "Your sync changed to Juniper.",
    "Your sync is in the previous Juniper room.",
    "Juniper is used for the sync.",
    "Ask me any more questions about Juniper.",
    "Juniper is irreplaceable.",
])
def test_other_words_do_not_mark_the_stale_value(sentence):
    result = score("recency", sentence)
    assert result["stale_present"] is True
    assert result["transition_marked"] is False


def test_from_before_an_alias_marks_the_stale_value():
    result = pr.score_probe(STAGING, "It took over from tern.", diag(),
                            user_values=[], locus="kernel")
    assert result["matched_forbidden"] == ["tern"]
    assert result["transition_marked"] is True


@pytest.mark.parametrize("answer, passed", [
    ("You're based in Ljubljana.", True),
    ("You live in Tallinn.", False),
    ("You live in Ljubljana, previously Tallinn.", False),
    ("I don't know where you live.", False),
])
def test_contradiction_needs_the_later_value_without_the_earlier(
    answer, passed
):
    assert score("contradiction", answer)["passed"] is passed


LEAK_ROWS = {
    "deletion": PET_ADD,
    "privacy": row(
        "Keep this private: I have a follow-up appointment with "
        "Dr. Okafor.", "m2", owner="calendar_agent", memory_type="calendar",
        event="u0_e12", fact_key="doctor", session=6),
}
LEAK_ANSWERS = {"deletion": "Your cat is called Mochi.",
                "privacy": "You see Dr. Okafor next week."}


@pytest.mark.parametrize("kind", ["deletion", "privacy"])
@pytest.mark.parametrize("in_block, in_answer", [
    (False, False), (True, False), (False, True), (True, True),
])
def test_hard_constraints_fail_on_the_block_or_the_answer(
    kind, in_block, in_answer
):
    rows = [SHELL] + ([LEAK_ROWS[kind]] if in_block else [])
    answer = LEAK_ANSWERS[kind] if in_answer else "I have no record."
    result = score(kind, answer, *rows)
    assert result["forbidden_in_block"] is in_block
    assert result["forbidden_in_answer"] is in_answer
    assert result["passed"] is (not in_block and not in_answer)
    assert result["expected_present"] is None
    assert result["stale_present"] is None
    assert result["transition_marked"] is None


def test_a_hard_constraint_matches_aliases():
    leak = probe("deletion", "chat_app", [],
                 [value("Rocket.Chat", "Rocket Chat", "RocketChat")],
                 "u0_e04", ["u0_e04"])
    result = pr.score_probe(leak, "Your team uses RocketChat.", diag(SHELL),
                            user_values=[], locus="kernel")
    assert result["passed"] is False
    assert result["matched_forbidden"] == ["RocketChat"]


def test_a_hard_constraint_without_block_text_is_unscored_unless_leaked():
    blind = diag(SHELL)
    blind["block_text"] = None
    clean = pr.score_probe(PROBES["deletion"], "I have no record.", blind,
                           user_values=[], locus="kernel")
    assert clean["passed"] is None
    assert clean["forbidden_in_block"] is None
    leak = pr.score_probe(PROBES["deletion"], "It is Mochi.", blind,
                          user_values=[], locus="kernel")
    assert leak["passed"] is False


def test_integration_is_judged_not_passed():
    result = score("integration", "Ask Dana Whitfield about the plan.",
                   PET_ADD)
    assert result["passed"] is None
    for key in ("expected_present", "stale_present", "forbidden_in_answer",
                "forbidden_in_block", "transition_marked",
                "expected_in_block", "stale_in_block",
                "newest_target_row_has_stale", "semantic_best",
                "semantic_only"):
        assert result[key] is None, key
    for key in ("matched_expected", "matched_forbidden",
                "rows_with_expected", "rows_with_stale",
                "rows_with_forbidden"):
        assert result[key] == [], key
    assert result["other_values_in_answer"] == ["Dana Whitfield"]
    assert result["contaminated"] is False


def test_refuses_unknown_types_loci_and_probes_without_values():
    def run(record, locus="kernel"):
        return pr.score_probe(record, "x", {}, user_values=[], locus=locus)

    with pytest.raises(ValueError, match="probe type"):
        run({"type": "trivia"})
    with pytest.raises(ValueError, match="locus"):
        run(PROBES["recall"], locus="none")
    with pytest.raises(ValueError, match="expected"):
        run({**PROBES["recall"], "expected": []})
    for kind in ("deletion", "privacy", "recency", "contradiction"):
        with pytest.raises(ValueError, match="forbidden"):
            run({**PROBES[kind], "forbidden": []})


# -- the block and its rows ----------------------------------------------

def test_block_checks_read_the_block_text():
    result = score("recency", "Birch.", SYNC_ADD, SYNC_UPDATE)
    assert result["expected_in_block"] is True
    assert result["stale_in_block"] is True
    assert result["forbidden_in_block"] is True
    assert [r["memory_id"] for r in result["rows_with_expected"]] == ["a2"]
    assert [r["memory_id"] for r in result["rows_with_stale"]] == ["a1"]
    assert result["rows_with_forbidden"] == result["rows_with_stale"]
    empty = score("recency", "Birch.")
    assert empty["expected_in_block"] is False
    assert empty["stale_in_block"] is False


def test_rows_are_attributed_by_provenance_event():
    rows = [
        PET_ADD,
        calendar_row("I booked a vet visit for Mochi.", "m3", "u0_e07",
                     "pet_vet_visit", 3),
        calendar_row("Mochi sleeps through the sync.", "m4", "u0_e09",
                     "sync_room", 3),
        conversation_row("User: Hi\nAssistant: How is Mochi?", "m5"),
        row("Mochi.", "m6"),
    ]
    result = score("deletion", "I have no record.", *rows)
    assert [(r["memory_id"], r["source"])
            for r in result["rows_with_forbidden"]] == [
        ("m1", "target"), ("m3", "echo"), ("m4", "other_fact"),
        ("m5", "conversation"), ("m6", "unknown"),
    ]
    assert result["rows_with_forbidden"][1] == {
        "memory_id": "m3", "owner_agent": "calendar_agent",
        "memory_type": "calendar", "fact_key": "pet_vet_visit",
        "session": 3, "provenance_event": "u0_e07", "source": "echo",
    }
    assert all(tuple(r) == pr.ROW_KEYS
               for r in result["rows_with_forbidden"])


def test_target_rows_do_not_depend_on_which_fact_event_is_the_target():
    for target in ("u0_e05", "u0_e10"):
        record = {**PROBES["recency"], "target_event": target}
        assert [pr.row_source(r, record)
                for r in (SYNC_ADD, SYNC_UPDATE)] == ["target", "target"]
    # Without event ids, the row's fact key names the slot.
    bare = {**PROBES["recency"], "target_event": None, "source_events": []}
    assert pr.row_source(SYNC_ADD, bare) == "target"
    assert pr.row_source(PET_ADD, bare) == "other_fact"
    # A fact key alone names another fact too.
    unstamped = row("My shell is fish.", "s1", fact_key="shell")
    assert pr.row_source(unstamped, bare) == "other_fact"


def test_row_source_reads_listed_rows():
    listed = {"memory_id": "x1", "content": "I have a cat named Mochi.",
              "metadata": {"owner_agent": "profile_agent",
                           "memory_type": "profile", "fact_key": "pet",
                           "provenance_event": "u0_e03"}}
    assert pr.row_source(listed, PROBES["deletion"]) == "target"
    native_v3 = {"memory_id": "x2", "content": "User: ...",
                 "metadata": {"provenance_agent": "assistant_agent",
                              "memory_type": "conversation",
                              "provenance_event": "u0_recall"}}
    assert pr.row_source(native_v3, PROBES["deletion"]) == "conversation"


def test_a_conversation_row_is_the_consumers_conversation_only():
    other_writer = row("User: hi", "c1", memory_type="conversation")
    assert pr.row_source(other_writer, PROBES["recall"]) == "unknown"
    not_a_conversation = row("hi", "c2", owner="assistant_agent")
    assert pr.row_source(not_a_conversation, PROBES["recall"]) == "unknown"
    stamped = conversation_row("User: hi", "c3", event="u0_recall")
    assert pr.row_source(stamped, PROBES["recall"]) == "conversation"


def test_newest_target_row_has_stale():
    def newest(*rows):
        return score("recency", "Birch.", *rows)[
            "newest_target_row_has_stale"]

    mem0_update = calendar_row(
        "Weekly team sync moved from the Juniper room to the Birch room",
        "a3", "u0_e10", "sync_room", 5)
    sibling_new = calendar_row("Weekly team sync is in the Birch room",
                               "a4", "u0_e10", "sync_room", 5)
    sibling_old = calendar_row(
        "Weekly team sync was previously in the Juniper room", "a5",
        "u0_e10", "sync_room", 5)
    assert newest(SYNC_ADD, SYNC_UPDATE) is False
    assert newest(SYNC_ADD, mem0_update) is True
    assert newest(SYNC_ADD, sibling_new, sibling_old) is True
    # Without the update's rows the add's own row is not the newest.
    assert newest(SYNC_ADD) is None
    both = conversation_row("Assistant: it moved from Juniper to Birch",
                            "c1")
    assert newest(SYNC_ADD, both) is None
    assert score("recall", "x", PET_ADD)[
        "newest_target_row_has_stale"] is None


def test_deleted_ids_in_block():
    result = score("deletion", "I have no record.", PET_ADD, SHELL,
                   deleted_ids=["m1", "m7"])
    assert result["deleted_ids_in_block"] == ["m1"]
    assert score("deletion", "No.", PET_ADD)["deleted_ids_in_block"] == []


def test_contaminated_when_only_conversation_rows_carry_a_value():
    new_talk = conversation_row(
        "User: Which room?\nAssistant: The Birch room.", "c1")
    old_talk = conversation_row(
        "User: Which room?\nAssistant: The Juniper room.", "c2")
    assert score("recency", "Birch.", new_talk)["contaminated"] is True
    assert score("recency", "Birch.", new_talk,
                 SYNC_UPDATE)["contaminated"] is False
    assert score("recency", "Birch.", SYNC_UPDATE)["contaminated"] is False
    assert score("recency", "Birch.", SYNC_UPDATE,
                 old_talk)["contaminated"] is True


# -- cap and budget ------------------------------------------------------

@pytest.mark.parametrize("locus", ["kernel", "replicated"])
@pytest.mark.parametrize("counts, cap, budget", [
    ({"after_threshold": 14, "after_cap": 10, "after_budget": 10},
     True, False),
    ({"after_threshold": 14, "after_cap": 10, "after_budget": 8},
     True, True),
    ({"after_threshold": 6, "after_cap": 6, "after_budget": 5},
     False, True),
    ({"after_threshold": 6, "after_cap": 6, "after_budget": 6},
     False, False),
])
def test_cap_and_budget_bound_in_the_library_loci(locus, counts, cap,
                                                  budget):
    result = score("recall", "x", counts=counts, locus=locus)
    assert result["cap_bound"] is cap
    assert result["budget_bound"] is budget


def test_library_bounds_are_none_without_their_counts():
    result = pr.score_probe(PROBES["recall"], "x",
                            {"after_cap": 10, "block_text": ""},
                            user_values=[], locus="kernel")
    assert result["cap_bound"] is None
    assert result["budget_bound"] is None


@pytest.mark.parametrize("fetched, visible, k, cap", [
    (10, 15, 10, True),
    (10, 10, 10, False),
    (7, 15, 10, False),
    (5, 6, 5, True),
    (10, None, 10, None),
])
def test_native_cap_bound_reads_the_listings(fetched, visible, k, cap):
    # The library's counts would say "bound"; native never reads them.
    counts = {"own_fetched": fetched, "after_threshold": 12,
              "after_cap": 10, "after_budget": 9}
    result = score("recall", "x", counts=counts, locus="native",
                   visible_stored_rows=visible, k=k)
    assert result["cap_bound"] is cap
    assert result["budget_bound"] is None


def test_native_cap_bound_uses_the_consumers_own_fetch_size():
    """A V4 consumer fetches 5 rows, not the harness's 10: its fetch
    fills its own k while 16 rows are visible, so the cap bound."""
    def cap(k=10, visible=16, **counts):
        return score("recall", "x", counts=counts, locus="native",
                     visible_stored_rows=visible, k=k)["cap_bound"]

    assert cap(own_fetched=5, top_k_used={"own": 5}) is True
    # 7 visible rows: more than the consumer's 5, fewer than the
    # harness's 10, so only the consumer's own k says the cap bound.
    assert cap(own_fetched=5, top_k_used={"own": 5}, visible=7) is True
    assert cap(own_fetched=5, top_k_used={"own": 5}, visible=5) is False
    assert cap(own_fetched=5, top_k_used={"own": 10, "shared": 0}) is False
    assert cap(own_fetched=10, top_k_used={"own": 16}) is False
    # Without the consumer's own size, the k argument stands.
    assert cap(own_fetched=5) is False
    assert cap(own_fetched=5, k=5) is True
    # The library loci keep their own rule.
    library = score("recall", "x", counts={
        "own_fetched": 5, "top_k_used": {"own": 5}, "after_threshold": 5,
        "after_cap": 5, "after_budget": 5}, visible_stored_rows=16)
    assert library["cap_bound"] is False


# -- other diagnostics ---------------------------------------------------

def test_answer_length_and_the_users_other_values():
    answer = ("You report to Whitfield. Your cat Mochi and the Birch room "
              "are noted, and your team chats on Zulip.")
    result = score("recall", answer)
    assert result["answer_words"] == 19
    # Dana Whitfield is the probe's own value; Mochi is named once.
    assert result["other_values_in_answer"] == ["Mochi", "Birch", "Zulip"]
    recency = score("recency", "Birch, not Juniper; Tallinn too.")
    assert recency["other_values_in_answer"] == ["Tallinn"]
    assert score("recall", "")["answer_words"] == 0


class FakeEmbedder:
    """Embeds a text as [1, 0] when it mentions the team sync and as
    [0, 1] otherwise; records its calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return [[1.0, 0.0] if "sync" in text.lower() else [0.0, 1.0]
                for text in texts]


@pytest.mark.parametrize("answer, best, only", [
    # Close to the fact's sentence, but no value: semantic only.
    ("Your weekly team sync was moved to a new room.", 1.0, True),
    ("Your sync is in the Birch room.", 1.0, False),
    ("I cannot help with that.", 0.0, False),
])
def test_the_semantic_score_never_changes_passed(answer, best, only):
    embed = FakeEmbedder()
    plain = score("recency", answer, SYNC_UPDATE)
    scored = score("recency", answer, SYNC_UPDATE, embed=embed)
    assert scored["semantic_best"] == pytest.approx(best)
    assert scored["semantic_only"] is only
    assert scored["semantic_error"] is None
    assert plain["semantic_best"] is None
    assert plain["semantic_only"] is None
    semantic = ("semantic_best", "semantic_only")
    assert ({k: v for k, v in scored.items() if k not in semantic}
            == {k: v for k, v in plain.items() if k not in semantic})
    assert embed.calls == [
        [PROBES["recency"]["fact_sentence"], *pr.split_sentences(answer)]
    ]


def test_the_semantic_score_applies_to_expected_values_only():
    embed = FakeEmbedder()
    deletion = score("deletion", "Your sync is fine.", embed=embed)
    assert deletion["semantic_best"] is None
    assert deletion["semantic_only"] is None
    no_sentence = {**PROBES["recency"], "fact_sentence": None}
    result = pr.score_probe(no_sentence, "Your sync.", diag(),
                            user_values=[], locus="kernel", embed=embed)
    assert result["semantic_best"] is None
    empty = score("recency", "", embed=embed)
    assert empty["semantic_best"] is None
    assert empty["semantic_only"] is False
    assert embed.calls == []


@pytest.mark.parametrize("cosine, only", [(0.86, True), (0.84, False)])
def test_semantic_only_starts_at_the_threshold(cosine, only):
    def embed(texts):
        tilted = [cosine, math.sqrt(1 - cosine * cosine)]
        return [[1.0, 0.0]] + [tilted for _ in texts[1:]]

    result = score("recall", "Your manager is someone.", embed=embed)
    assert result["semantic_best"] == pytest.approx(cosine)
    assert result["semantic_only"] is only
    assert pr.SEMANTIC_THRESHOLD == 0.85


class ResponseError(Exception):
    """Like ``ollama.ResponseError``: a plain ``Exception``, not an
    ``OSError``."""


@pytest.mark.parametrize("raised, expected", [
    (ConnectionError("Ollama refused the connection"),
     "ConnectionError: Ollama refused the connection"),
    (ResponseError("model not found"), "ResponseError: model not found"),
])
@pytest.mark.parametrize("kind, answer", [
    ("recall", "You report to Dana Whitfield."),
    ("recency", "Your sync is in the Juniper room."),
    ("contradiction", "You live in Ljubljana."),
])
def test_an_embedding_failure_is_recorded_and_changes_nothing_else(
    kind, answer, raised, expected
):
    """An embed call that raises (Ollama down, or a model it does not
    have) leaves the semantic fields None and says why; the pass and
    every other field are the ones without the diagnostic, and nothing
    propagates."""
    def unreachable(texts):
        raise raised

    def others(result):
        return {k: v for k, v in result.items() if k != "semantic_error"}

    plain = score(kind, answer, SYNC_UPDATE)
    failed = score(kind, answer, SYNC_UPDATE, embed=unreachable)
    assert failed["semantic_error"] == expected
    assert failed["semantic_best"] is None
    assert failed["semantic_only"] is None
    assert plain["semantic_error"] is None
    assert others(failed) == others(plain)


def test_malformed_embeddings_are_recorded_as_semantic_errors():
    zero = score("recall", "Hm.", embed=lambda texts: [[0.0, 0.0]] * 2)
    assert zero["semantic_best"] == 0.0
    assert zero["semantic_error"] is None
    too_few = score("recall", "One. Two.", embed=lambda texts: [[1.0]])
    assert too_few["semantic_error"] == (
        "ValueError: embed returned 1 vectors for 3 texts")
    ragged = score("recall", "Hm.",
                   embed=lambda texts: [[1.0], [1.0, 0.0]])
    assert ragged["semantic_error"] == (
        "ValueError: embedding vectors differ in length")
    for result in (too_few, ragged):
        assert result["semantic_best"] is None
        assert result["semantic_only"] is None
        assert result["passed"] is False


def test_every_expected_value_must_appear_and_any_forbidden_one_fails():
    pair = probe("recall", "manager", [value("Dana Whitfield"),
                                       value("Omar Haddad")], [],
                 "u0_e02", ["u0_e02"])

    def recall(answer):
        return pr.score_probe(pair, answer, diag(SHELL), user_values=[],
                              locus="kernel")

    assert recall("Dana Whitfield.")["passed"] is False
    assert recall("Dana Whitfield and Omar Haddad.")["passed"] is True
    two = probe("deletion", "pet", [], [value("Mochi"), value("Gizmo")],
                "u0_e03", ["u0_e03"])
    result = pr.score_probe(two, "Gizmo.", diag(SHELL), user_values=[],
                            locus="kernel")
    assert result["passed"] is False
    assert result["matched_forbidden"] == ["Gizmo"]


def test_missing_diagnostics_and_row_keys_read_as_none():
    result = pr.score_probe(PROBES["recall"], "Dana Whitfield.", None,
                            user_values=[], locus="kernel")
    assert result["passed"] is True
    assert result["expected_in_block"] is None
    assert result["cap_bound"] is None
    assert result["rows_with_expected"] == []
    # A dump of the v1 model: its entries carry no text, fact key,
    # session or event, so no row can be attributed.
    old = InjectionDiagnostics(
        injected_memories=[{"owner_agent": "profile_agent",
                            "memory_type": "profile", "memory_id": "m1"}],
        block_text=f"{HEADER}\n- I report to Dana Whitfield.",
    )
    for diagnostics in (old, old.model_dump()):
        result = pr.score_probe(PROBES["recall"], "No idea.", diagnostics,
                                user_values=[], locus="kernel")
        assert result["expected_in_block"] is True
        assert result["rows_with_expected"] == []
        assert result["cap_bound"] is False


# -- statistics ----------------------------------------------------------

def test_wilson_known_values():
    assert pr.wilson(15, 30) == pytest.approx((0.3315, 0.6685), abs=1e-4)
    low, high = pr.wilson(0, 60)
    assert low == 0.0
    assert high == pytest.approx(0.0602, abs=1e-4)
    assert pr.wilson(27, 30) == pytest.approx((0.7438, 0.9654), abs=1e-4)
    assert pr.wilson(30, 30)[1] == 1.0


def test_wilson_matches_scipy():
    for n in (1, 2, 7, 20, 30, 60):
        for k in range(n + 1):
            ci = stats.binomtest(k, n).proportion_ci(
                confidence_level=0.95, method="wilson")
            assert pr.wilson(k, n) == pytest.approx(
                (ci.low, ci.high), abs=1e-9), (k, n)


@pytest.mark.parametrize("k, n", [(0, 0), (3, 2), (-1, 5), (1.0, 2),
                                  (True, 2)])
def test_wilson_refuses_bad_counts(k, n):
    with pytest.raises(ValueError):
        pr.wilson(k, n)


@pytest.mark.parametrize("b, c, p", [
    (0, 0, 1.0), (0, 5, 0.0625), (5, 0, 0.0625), (0, 6, 1 / 32),
    (1, 9, 11 / 512), (2, 2, 1.0), (3, 4, 1.0), (0, 1, 1.0),
])
def test_mcnemar_exact_small_cases(b, c, p):
    assert pr.mcnemar_exact(b, c) == pytest.approx(p)


def test_mcnemar_exact_matches_the_binomial_test():
    for b in range(10):
        for c in range(10):
            if b + c:
                expected = stats.binomtest(b, b + c, 0.5).pvalue
                assert pr.mcnemar_exact(b, c) == pytest.approx(expected)


@pytest.mark.parametrize("b, c", [(-1, 2), (1.5, 2), (2, None)])
def test_mcnemar_exact_refuses_bad_counts(b, c):
    with pytest.raises(ValueError):
        pr.mcnemar_exact(b, c)


def test_the_t_interval_is_none_below_two_values():
    """One score has no degrees of freedom: no interval, not a
    zero-width one."""
    assert pr.t_interval([]) == (None, None)
    assert pr.t_interval([4.0]) == (None, None)
    low, high = stats.t.interval(0.95, 1, loc=4.5, scale=stats.sem([4, 5]))
    assert pr.t_interval([4.0, 5.0]) == pytest.approx((low, high))
    # Equal scores: the formula's own zero-width value.
    assert pr.t_interval([4, 4]) == (4.0, 4.0)
    one = pr.summarize([{"type": "integration", "integration_score": 4}])
    assert one["integration"]["n"] == 1
    assert one["integration"]["mean"] == 4.0
    assert one["integration"]["ci_low"] is None
    assert one["integration"]["ci_high"] is None


# -- summaries -----------------------------------------------------------

def test_summarize_groups_by_probe_type():
    blind = diag(SHELL)
    blind["block_text"] = None
    results = [
        *(score("recall", answer) for answer in (
            "Dana Whitfield.", "Whitfield.", "Dana Whitfield!", "No idea.")),
        *(score("recency", answer, SYNC_UPDATE, embed=FakeEmbedder())
          for answer in ("Birch.", "It moved from Juniper to Birch.",
                         "Birch or Juniper.", "Juniper.",
                         "Your sync moved.")),
        score("deletion", "I have no record.", PET_ADD),
        score("deletion", "Mochi!", SHELL),
        score("deletion", "I have no record.", SHELL),
        pr.score_probe(PROBES["deletion"], "No.", blind, user_values=[],
                       locus="kernel"),
        score("recall", "Whitfield.", counts={"after_threshold": 12,
                                               "after_cap": 10,
                                               "after_budget": 9}),
    ]
    integration = score("integration", "A plan.")
    results += [{**integration, "integration_score": s} for s in (5, 4, 2)]
    results.append(integration)
    summary = pr.summarize(results)
    assert list(summary) == ["deletion", "recall", "recency", "integration"]

    recall = summary["recall"]
    assert (recall["n"], recall["passed"], recall["unscored"]) == (5, 4, 0)
    assert recall["rate"] == pytest.approx(0.8)
    assert (recall["ci_low"], recall["ci_high"]) == pr.wilson(4, 5)
    assert (recall["cap_bound"], recall["budget_bound"]) == (1, 1)
    assert recall["semantic_only"] is None

    recency = summary["recency"]
    assert (recency["n"], recency["passed"]) == (5, 1)
    lenient = recency["lenient"]
    assert (lenient["n"], lenient["passed"]) == (5, 3)
    assert (lenient["ci_low"], lenient["ci_high"]) == pr.wilson(3, 5)
    assert (recency["names_both"], recency["named_as_past"]) == (2, 1)
    assert recency["semantic_only"] == 1

    deletion = summary["deletion"]
    assert (deletion["n"], deletion["passed"], deletion["unscored"]) == (
        3, 1, 1)
    assert deletion["forbidden_in_block"] == 1
    assert deletion["forbidden_in_answer"] == 1
    assert "lenient" not in deletion

    scored = summary["integration"]
    assert (scored["n"], scored["unscored"]) == (3, 1)
    assert scored["mean"] == pytest.approx(11 / 3)
    assert scored["share_ge_4"] == pytest.approx(2 / 3)
    low, high = stats.t.interval(0.95, 2, loc=11 / 3,
                                 scale=stats.sem([5, 4, 2]))
    assert (scored["ci_low"], scored["ci_high"]) == pytest.approx(
        (low, high))


def test_summarize_counts_semantic_errors_per_type():
    def timed_out(texts):
        raise TimeoutError("embed timed out")

    results = [
        score("recall", "Whitfield.", embed=timed_out),
        score("recall", "No idea.", embed=timed_out),
        score("recall", "Whitfield.", embed=FakeEmbedder()),
        score("recall", "Whitfield."),
        score("recency", "Birch.", embed=FakeEmbedder()),
        score("contradiction", "Ljubljana.", embed=timed_out),
        score("deletion", "I have no record."),
    ]
    summary = pr.summarize(results)
    assert summary["recall"]["semantic_error"] == 2
    # The errors decide no pass.
    assert (summary["recall"]["n"], summary["recall"]["passed"]) == (4, 3)
    assert summary["recency"]["semantic_error"] == 0
    assert summary["contradiction"]["semantic_error"] == 1
    assert "semantic_error" not in summary["deletion"]


def test_summarize_reports_unknown_bounds_and_empty_rates_as_none():
    native = score("recall", "Whitfield.", locus="native")
    summary = pr.summarize([native])["recall"]
    assert summary["cap_bound"] is None
    assert summary["budget_bound"] is None
    blind = diag()
    blind["block_text"] = None
    unscored = pr.score_probe(PROBES["privacy"], "No.", blind,
                              user_values=[], locus="kernel")
    privacy = pr.summarize([unscored])["privacy"]
    assert (privacy["n"], privacy["unscored"]) == (0, 1)
    assert privacy["rate"] is None
    assert privacy["ci_low"] is None and privacy["ci_high"] is None


def test_summarize_reads_models_and_skips_unjudged_integration():
    integration = score("integration", "A plan.")
    assert "integration" not in pr.summarize([integration])
    nested = {**integration, "judge_scores": {"integration_score": 4}}
    assert pr.summarize([nested])["integration"]["n"] == 1
    model = types.SimpleNamespace(**score("recall", "Whitfield."))
    assert pr.summarize([model])["recall"]["passed"] == 1
    with pytest.raises(ValueError, match="type"):
        pr.summarize([{"passed": True}])
