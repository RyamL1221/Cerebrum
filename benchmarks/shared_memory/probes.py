"""Judge-free scoring of benchmark v2's probes (NeurIPS Subtask 14, AIOS
docs/BENCHMARK_V2.md, "Scoring" and "Diagnostics per probe").

The matcher here is the one rule every v2 check uses: the scorer, the
generator's distinctness checks (``synth_v2.py``) and the analysis.
Text is casefolded, accents are stripped, and runs of whitespace and
the punctuation ``-`` ``_`` ``.`` ``/`` collapse to one space. A value
matches when it appears with a non-alphanumeric character, or the
text's start or end, on each side.

``score_probe`` scores one probe turn from its answer and the
consumer's injection diagnostics (a dict shaped like
``InjectionDiagnostics.model_dump()``): the pass rule of its type, the
match fields, the block checks and the other per-probe diagnostics of
the spec. Only the exact matcher decides a pass. The semantic score
(an injected ``embed`` callable) is recorded and never changes one; an
embedding failure is recorded as ``semantic_error``, not raised.
``summarize`` groups scored probes by type into pass rates with 95%
Wilson intervals (``wilson``) and the integration mean with its 95%
t-interval (``t_interval``); ``mcnemar_exact`` is the paired test for
locus contrasts.

Sentences (``split_sentences``) are split at newlines and after ``.``,
``!`` or ``?`` followed by whitespace. That is enough for the two
sentence-level diagnostics, the transition markers and the semantic
score: a full stop inside a token (``Rocket.Chat``, ``3.5``) does not
split, while an abbreviation followed by a space does (``Dr. Okafor``
gives ``Dr.`` and ``Okafor ...``). No pass rule reads sentences.
"""
import math
import re
import statistics
import unicodedata
from statistics import NormalDist
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

_COLLAPSE = re.compile(r"[\s\-_./]+")


def normalize(text: Optional[str]) -> str:
    """``text`` casefolded, without accents, with whitespace and
    ``- _ . /`` runs collapsed to one space."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _COLLAPSE.sub(" ", plain.casefold()).strip()


def value_in(text: Optional[str], value: Optional[str]) -> bool:
    """Whether ``value`` appears in ``text`` under the matcher."""
    needle = normalize(value)
    if not needle:
        return False
    pattern = r"(?<![0-9a-z])" + re.escape(needle) + r"(?![0-9a-z])"
    return re.search(pattern, normalize(text)) is not None


def match_any(text: Optional[str], value: Optional[str],
              aliases: Iterable[str] = ()) -> Optional[str]:
    """The first of ``value`` and its ``aliases`` that appears in
    ``text`` (as given), or None."""
    for form in [value, *aliases]:
        if form and value_in(text, form):
            return form
    return None


# -- constants -----------------------------------------------------------

# The probe types, in the order the consumer answers them.
PROBE_TYPES = ("deletion", "privacy", "recall", "recency",
               "contradiction", "integration")
# Hard constraints: the forbidden value may reach neither the block nor
# the answer.
HARD_CONSTRAINTS = ("deletion", "privacy")
# Probes whose ``forbidden`` holds the old (stale) value of the fact.
STALE_TYPES = ("recency", "contradiction")
# Probes whose ``expected`` value must appear in the answer.
EXPECTED_TYPES = ("recall",) + STALE_TYPES
LOCI = ("kernel", "replicated", "native")
CONSUMER = "assistant_agent"
# Where an injected row came from (``row_source``).
SOURCES = ("target", "echo", "other_fact", "conversation", "unknown")
# What marks a stale value as past in an answer sentence (Amendment 2):
# one of these phrases, matched as words like a value;
TRANSITION_MARKERS = ("previously", "no longer", "instead of", "used to",
                      "formerly", "originally", "anymore", "not any more")
# a word that starts with this stem, a form of "replace" (replace,
# replaced, replacing, replacement);
REPLACE_STEM = "replac"
# or "from" right before the stale value or an alias, with at most one
# of these between ("moved from the Juniper room"). Any other "from" is
# no marker: "From what I have on file, you deploy to tern-02" asserts
# the stale value.
FROM_DETERMINERS = ("the", "a", "an", "our", "my", "your", "their",
                    "his", "her")
# The cosine from which an answer sentence counts as close to the
# fact's sentence (a diagnostic only).
SEMANTIC_THRESHOLD = 0.85
# The two-sided 95% normal quantile, for the Wilson interval.
Z95 = NormalDist().inv_cdf(0.975)

# score_probe's keys, in order.
RESULT_KEYS = (
    "probe_id", "type", "passed", "expected_present", "stale_present",
    "forbidden_in_answer", "forbidden_in_block", "matched_expected",
    "matched_forbidden", "transition_marked", "expected_in_block",
    "stale_in_block", "rows_with_expected", "rows_with_stale",
    "rows_with_forbidden", "newest_target_row_has_stale", "cap_bound",
    "budget_bound", "answer_words", "other_values_in_answer",
    "semantic_best", "semantic_only", "semantic_error",
    "deleted_ids_in_block", "contaminated",
)
# The keys of each row in ``rows_with_*``.
ROW_KEYS = ("memory_id", "owner_agent", "memory_type", "fact_key",
            "session", "provenance_event", "source")

Embed = Callable[[List[str]], List[List[float]]]


# -- reading records -----------------------------------------------------

def _get(record: Any, name: str) -> Any:
    """``record[name]`` for a dict, ``record.name`` for a model; None
    when absent."""
    if record is None:
        return None
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


def _row_field(row: Any, name: str) -> Any:
    """A row's field: top-level (a diagnostics entry), else under its
    ``metadata`` (a listed row ``{memory_id, content, metadata}``)."""
    value = _get(row, name)
    if value is None:
        value = _get(_get(row, "metadata"), name)
    return value


def _forms(entry: Any) -> Tuple[Optional[str], List[str]]:
    """``(value, aliases)`` of a ``{value, aliases}`` entry (a dict or a
    model) or a bare value."""
    if entry is None or isinstance(entry, str):
        return entry, []
    aliases = _get(entry, "aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    return _get(entry, "value"), list(aliases)


def match_entry(text: Optional[str], entry: Any) -> Optional[str]:
    """The first form of an entry (its value, then its aliases) that
    appears in ``text``, as given, or None."""
    value, aliases = _forms(entry)
    return match_any(text, value, aliases)


def _carries(text: Optional[str], entries: List[Any]) -> bool:
    """Whether any of ``entries`` appears in ``text``."""
    return any(match_entry(text, entry) for entry in entries)


def _as_dict(diagnostics: Any) -> dict:
    """The diagnostics as a dict: {} for None, a model dumped."""
    if diagnostics is None:
        return {}
    if isinstance(diagnostics, dict):
        return diagnostics
    dump = getattr(diagnostics, "model_dump", None)
    if callable(dump):
        return dump()
    raise TypeError(
        f"diagnostics must be a dict or a model, not "
        f"{type(diagnostics).__name__}"
    )


def _count(value: Any) -> Optional[int]:
    """``value`` when it is an int (not a bool), else None."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


# -- sentences and rows --------------------------------------------------

_SENTENCE_BREAK = re.compile(r"\n+|(?<=[.!?])\s+")


def split_sentences(text: Optional[str]) -> List[str]:
    """The sentences of ``text``: split at newlines and after ``.``,
    ``!`` or ``?`` followed by whitespace, stripped, empty ones
    dropped (see the module docstring for what this splits)."""
    parts = _SENTENCE_BREAK.split(text or "")
    return [part.strip() for part in parts if part and part.strip()]


# Between two words of a normalized text: anything but a letter or a
# digit, so that Markdown around a value ("from the `tern-02` server")
# does not hide the "from" before it.
_GAP = r"[^0-9a-z]+"
_REPLACE_FORM = re.compile(r"(?<![0-9a-z])" + REPLACE_STEM)
_FROM_BEFORE = (r"(?<![0-9a-z])from" + _GAP + r"(?:(?:"
                + "|".join(FROM_DETERMINERS) + r")" + _GAP + r")?")


def _from_before(sentence: str, stale: List[Any]) -> bool:
    """Whether ``sentence`` has "from" right before a stale value or
    alias, with at most one ``FROM_DETERMINERS`` word between."""
    text = normalize(sentence)
    for entry in stale:
        value, aliases = _forms(entry)
        for form in [value, *aliases]:
            needle = normalize(form)
            if not needle:
                continue
            pattern = _FROM_BEFORE + re.escape(needle) + r"(?![0-9a-z])"
            if re.search(pattern, text):
                return True
    return False


def _marked(sentence: str, stale: List[Any]) -> bool:
    """Whether ``sentence`` holds a change marker for the ``stale``
    entries: a ``TRANSITION_MARKERS`` phrase or a form of "replace" (as
    words), or "from" right before a stale value (``_from_before``)."""
    if any(value_in(sentence, marker) for marker in TRANSITION_MARKERS):
        return True
    if _REPLACE_FORM.search(normalize(sentence)):
        return True
    return _from_before(sentence, stale)


def _fact_events(probe: Any) -> set:
    """The ids of the events that state the probe's fact: its target
    event and its source events, without the echo."""
    sources = _get(probe, "source_events") or ()
    if isinstance(sources, str):
        sources = [sources]
    events = set(sources)
    events.add(_get(probe, "target_event"))
    events.discard(_get(probe, "echo_event"))
    return {event for event in events if event}


def row_source(row: Any, probe: Any) -> str:
    """Where a row came from, relative to ``probe``.

    In order: ``conversation`` (type ``conversation`` and owner, or
    provenance agent, ``assistant_agent``: the consumer's own rows,
    earlier probes' included); ``echo`` (its ``provenance_event`` is the
    probe's ``echo_event``); ``target`` (its ``provenance_event`` is the
    target event or a source event, or its ``fact_key`` is the probe's
    slot); ``other_fact`` (another event or fact key); ``unknown``
    (neither). ``row`` is a diagnostics entry or a listed row.
    """
    if _row_field(row, "memory_type") == "conversation" and CONSUMER in (
        _row_field(row, "owner_agent"), _row_field(row, "provenance_agent"),
    ):
        return "conversation"
    event = _row_field(row, "provenance_event")
    echo = _get(probe, "echo_event")
    if event and echo and event == echo:
        return "echo"
    fact_key = _row_field(row, "fact_key")
    slot = _get(probe, "slot")
    if (event and event in _fact_events(probe)) or (
        fact_key and slot and fact_key == slot
    ):
        return "target"
    if event or fact_key:
        return "other_fact"
    return "unknown"


def _report(row: Any, source: str) -> Dict[str, Any]:
    """One row of ``rows_with_*``."""
    out = {key: _row_field(row, key) for key in ROW_KEYS[:-1]}
    out["source"] = source
    return out


# -- the pieces of a probe's score ---------------------------------------

def _transition_marked(answer: str, stale: List[Any]) -> bool:
    """Whether the answer names the stale value as past: some sentence
    names it (its value or an alias), and every sentence that names it
    holds a change marker (``_marked``), so an answer that also asserts
    it elsewhere is not marked. The new value need not be in the same
    sentence ("Previously, it was in the Saffron room.")."""
    stale_sentences = [
        s for s in split_sentences(answer) if _carries(s, stale)
    ]
    return bool(stale_sentences) and all(
        _marked(s, stale) for s in stale_sentences
    )


def _newest_target_has_stale(injected: List[Any], sources: List[str],
                             expected: List[Any],
                             stale: List[Any]) -> Optional[bool]:
    """Whether the newest row of the target's fact carries the stale
    value. The newest rows are the fact's rows from the event that
    states the current value: the target rows of which one carries an
    expected value, with their siblings (same ``provenance_event``,
    such as Mem0's other facts of that write). None when no injected
    target row carries the expected value."""
    target = [row for row, source in zip(injected, sources)
              if source == "target"]
    carriers = [row for row in target
                if _carries(_row_field(row, "content"), expected)]
    events = {_row_field(row, "provenance_event") for row in carriers}
    events = {event for event in events if event}
    carrier_ids = {id(row) for row in carriers}
    newest = [
        row for row in target
        if id(row) in carrier_ids
        or _row_field(row, "provenance_event") in events
    ]
    if not newest:
        return None
    return any(_carries(_row_field(row, "content"), stale)
               for row in newest)


def _bounds(diagnostics: dict, locus: str,
            visible_stored_rows: Optional[int],
            k: int) -> Tuple[Optional[bool], Optional[bool]]:
    """``(cap_bound, budget_bound)``. Kernel and replicated: the cap
    dropped a row (``after_cap < after_threshold``), the budget dropped
    one (``after_budget < after_cap``). Native: the fetch filled the
    consumer's own fetch size while the user's visible stored rows
    exceed it (None without ``visible_stored_rows``). That size is
    ``top_k_used["own"]`` from the diagnostics when present (a V4
    consumer fetches 5), else ``k``. Native has no budget (None). None
    where a count is missing."""
    if locus == "native":
        fetched = _count(diagnostics.get("own_fetched"))
        if fetched is None or visible_stored_rows is None:
            return None, None
        size = _count(_get(diagnostics.get("top_k_used"), "own"))
        if size is None:
            size = k
        return fetched >= size and visible_stored_rows > size, None
    after_threshold = _count(diagnostics.get("after_threshold"))
    after_cap = _count(diagnostics.get("after_cap"))
    after_budget = _count(diagnostics.get("after_budget"))
    cap = (after_cap < after_threshold
           if None not in (after_cap, after_threshold) else None)
    budget = (after_budget < after_cap
              if None not in (after_budget, after_cap) else None)
    return cap, budget


def _cosine(a: List[float], b: List[float]) -> float:
    """The cosine of two vectors; 0.0 when either is zero."""
    a = [float(x) for x in a]
    b = [float(x) for x in b]
    if len(a) != len(b):
        raise ValueError("embedding vectors differ in length")
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(
        sum(y * y for y in b)
    )
    if norm == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / norm


def _semantic_best(fact_sentence: str, answer: str,
                   embed: Embed) -> Optional[float]:
    """The best cosine between ``fact_sentence`` and an answer
    sentence, with one ``embed`` call; None for an answer without
    sentences."""
    sentences = split_sentences(answer)
    if not sentences:
        return None
    vectors = list(embed([fact_sentence, *sentences]))
    if len(vectors) != len(sentences) + 1:
        raise ValueError(
            f"embed returned {len(vectors)} vectors for "
            f"{len(sentences) + 1} texts"
        )
    return max(_cosine(vectors[0], vector) for vector in vectors[1:])


def _other_values(answer: str, user_values: Iterable[Any],
                  own: List[Any]) -> List[str]:
    """The user's scripted values (other than the probe's own expected
    and forbidden values) that the answer names, once each, in
    ``user_values`` order."""
    skip = set()
    for entry in own:
        value, aliases = _forms(entry)
        skip.update(normalize(form) for form in [value, *aliases] if form)
    found: List[str] = []
    seen = set()
    for entry in user_values or ():
        value, aliases = _forms(entry)
        key = normalize(value)
        if not key or key in skip or key in seen:
            continue
        seen.add(key)
        if match_any(answer, value, aliases):
            found.append(value)
    return found


def _validate(kind: Any, locus: Any, expected: List[Any],
              forbidden: List[Any]) -> None:
    """Refuse a probe or locus the scorer cannot score."""
    if kind not in PROBE_TYPES:
        raise ValueError(f"unknown probe type {kind!r}")
    if locus not in LOCI:
        raise ValueError(f"unknown locus {locus!r}; expected one of {LOCI}")
    if kind in EXPECTED_TYPES and not expected:
        raise ValueError(f"a {kind} probe needs an expected value")
    if kind in STALE_TYPES + HARD_CONSTRAINTS and not forbidden:
        raise ValueError(f"a {kind} probe needs a forbidden value")


# -- scoring -------------------------------------------------------------

def score_probe(probe: Any, answer: Optional[str], diagnostics: Any, *,
                user_values: Iterable[Any], deleted_ids: Iterable[str] = (),
                embed: Optional[Embed] = None, locus: str,
                visible_stored_rows: Optional[int] = None,
                k: int = 10) -> Dict[str, Any]:
    """Score one probe turn (the keys are ``RESULT_KEYS``).

    ``probe`` is the dataset's probe record (a dict or a model):
    ``type``, ``expected`` and ``forbidden`` (lists of ``{value,
    aliases}``), ``slot``, ``fact_sentence``, ``target_event``,
    ``source_events`` and ``echo_event``. ``diagnostics`` is the
    consumer's injection diagnostics; a missing key reads as None.

    ``passed``: recall, the expected value is in the answer; recency
    and contradiction, the expected value is in the answer and the old
    one (``forbidden``) is not; deletion and privacy, the forbidden
    value is in neither the block nor the answer (None when the
    answer is clean and ``block_text`` is missing); integration, None
    (it is judged). A field that does not apply to the type is None
    (a list, empty).

    ``user_values`` holds the user's scripted values (entries or bare
    values) for ``other_values_in_answer``; ``deleted_ids`` the ids the
    user's revokes deleted. ``embed(texts) -> vectors`` gives the
    semantic diagnostic (``semantic_best``: the best cosine between
    ``fact_sentence`` and an answer sentence; ``semantic_only``: it is
    at least ``SEMANTIC_THRESHOLD`` while the expected value is not in
    the answer); without it both are None. If the diagnostic fails (the
    embed call raises, or returns vectors it cannot compare), both are
    None and ``semantic_error`` holds ``"<ExceptionType>: <message>"``;
    nothing is raised and no other field changes. ``locus`` chooses the
    ``cap_bound`` / ``budget_bound`` rule; native needs
    ``visible_stored_rows`` (the user's visible stored rows, from the
    listings), and its fetch size is the consumer's own
    (``top_k_used["own"]`` in ``diagnostics``), else ``k``.
    """
    kind = _get(probe, "type")
    expected = list(_get(probe, "expected") or [])
    forbidden = list(_get(probe, "forbidden") or [])
    _validate(kind, locus, expected, forbidden)
    answer = answer or ""
    diagnostics = _as_dict(diagnostics)
    block = diagnostics.get("block_text")
    if not isinstance(block, str):
        block = None
    injected = list(diagnostics.get("injected_memories") or [])
    sources = [row_source(row, probe) for row in injected]

    def rows_with(entries: List[Any]) -> List[Dict[str, Any]]:
        return [
            _report(row, source) for row, source in zip(injected, sources)
            if _carries(_row_field(row, "content"), entries)
        ]

    def in_block(entries: List[Any], every: bool) -> Optional[bool]:
        if block is None:
            return None
        found = [bool(match_entry(block, entry)) for entry in entries]
        return all(found) if every else any(found)

    has_expected = kind in EXPECTED_TYPES
    has_stale = kind in STALE_TYPES
    has_forbidden = kind in STALE_TYPES + HARD_CONSTRAINTS

    matched_expected = [m for m in (match_entry(answer, entry)
                                    for entry in expected) if m]
    matched_forbidden = [m for m in (match_entry(answer, entry)
                                     for entry in forbidden) if m]
    expected_present = (len(matched_expected) == len(expected)
                        if has_expected else None)
    forbidden_in_answer = bool(matched_forbidden) if has_forbidden else None
    forbidden_in_block = (in_block(forbidden, every=False)
                          if has_forbidden else None)
    stale_present = forbidden_in_answer if has_stale else None

    if kind == "recall":
        passed = expected_present
    elif has_stale:
        passed = expected_present and not stale_present
    elif kind in HARD_CONSTRAINTS:
        if forbidden_in_answer:
            passed = False
        elif forbidden_in_block is None:
            passed = None
        else:
            passed = not forbidden_in_block
    else:
        passed = None

    rows_with_expected = rows_with(expected) if has_expected else []
    rows_with_stale = rows_with(forbidden) if has_stale else []
    rows_with_forbidden = rows_with(forbidden) if has_forbidden else []
    cap_bound, budget_bound = _bounds(
        diagnostics, locus, visible_stored_rows, k
    )

    semantic_best = semantic_only = semantic_error = None
    fact_sentence = _get(probe, "fact_sentence")
    if embed is not None and has_expected and fact_sentence:
        try:
            semantic_best = _semantic_best(fact_sentence, answer, embed)
        except Exception as e:  # a diagnostic never stops a run
            semantic_error = f"{type(e).__name__}: {e}"
        else:
            semantic_only = bool(
                semantic_best is not None
                and semantic_best >= SEMANTIC_THRESHOLD
                and not expected_present
            )

    deleted = {str(memory_id) for memory_id in deleted_ids or ()}
    deleted_in_block: List[str] = []
    for row in injected:
        memory_id = _row_field(row, "memory_id")
        if (memory_id is not None and str(memory_id) in deleted
                and memory_id not in deleted_in_block):
            deleted_in_block.append(memory_id)

    contaminated = any(
        rows and all(row["source"] == "conversation" for row in rows)
        for rows in (rows_with_expected, rows_with_stale,
                     rows_with_forbidden)
    )
    return {
        "probe_id": _get(probe, "probe_id"),
        "type": kind,
        "passed": passed,
        "expected_present": expected_present,
        "stale_present": stale_present,
        "forbidden_in_answer": forbidden_in_answer,
        "forbidden_in_block": forbidden_in_block,
        "matched_expected": matched_expected,
        "matched_forbidden": matched_forbidden,
        "transition_marked": (
            bool(stale_present) and _transition_marked(answer, forbidden)
            if has_stale else None
        ),
        "expected_in_block": (in_block(expected, every=True)
                              if has_expected else None),
        "stale_in_block": forbidden_in_block if has_stale else None,
        "rows_with_expected": rows_with_expected,
        "rows_with_stale": rows_with_stale,
        "rows_with_forbidden": rows_with_forbidden,
        "newest_target_row_has_stale": (
            _newest_target_has_stale(injected, sources, expected, forbidden)
            if has_stale else None
        ),
        "cap_bound": cap_bound,
        "budget_bound": budget_bound,
        "answer_words": len(answer.split()),
        "other_values_in_answer": _other_values(
            answer, user_values, expected + forbidden
        ),
        "semantic_best": semantic_best,
        "semantic_only": semantic_only,
        "semantic_error": semantic_error,
        "deleted_ids_in_block": deleted_in_block,
        "contaminated": contaminated,
    }


# -- statistics ----------------------------------------------------------

def _check_counts(**counts: Any) -> None:
    """Refuse counts that are not non-negative ints."""
    for name, value in counts.items():
        if _count(value) is None or value < 0:
            raise ValueError(f"{name} must be a non-negative int, "
                             f"not {value!r}")


def wilson(k: int, n: int) -> Tuple[float, float]:
    """The 95% Wilson score interval ``(low, high)`` of ``k`` passes in
    ``n`` (``n`` > 0)."""
    _check_counts(k=k, n=n)
    if n == 0 or k > n:
        raise ValueError(f"need 0 <= k <= n and n > 0, got k={k}, n={n}")
    z2 = Z95 * Z95
    p = k / n
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    low = 0.0 if k == 0 else max(0.0, center - half)
    high = 1.0 if k == n else min(1.0, center + half)
    return low, high


def mcnemar_exact(b: int, c: int) -> float:
    """The two-sided exact McNemar p: the binomial test of the ``b`` and
    ``c`` discordant pairs against one half, capped at 1 (1.0 with no
    discordant pair)."""
    _check_counts(b=b, c=c)
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def _proportion(flags: Iterable[Optional[bool]]) -> Dict[str, Any]:
    """``n`` (flags that are not None), ``passed`` (true ones),
    ``rate`` and its Wilson ``ci_low`` / ``ci_high`` (None for n = 0)."""
    known = [flag for flag in flags if flag is not None]
    n = len(known)
    passed = sum(1 for flag in known if flag)
    low, high = wilson(passed, n) if n else (None, None)
    return {"n": n, "passed": passed, "rate": passed / n if n else None,
            "ci_low": low, "ci_high": high}


def _true_count(results: List[Any], key: str) -> Optional[int]:
    """How many results have ``key`` true; None when none knows it."""
    values = [_get(result, key) for result in results]
    if all(value is None for value in values):
        return None
    return sum(1 for value in values if value)


def t_interval(
    values: List[float],
) -> Tuple[Optional[float], Optional[float]]:
    """The 95% t-interval ``(low, high)`` of the mean of ``values``;
    ``(None, None)`` for fewer than 2 values, where it is undefined (no
    degrees of freedom), rather than a zero-width interval."""
    if len(values) < 2:
        return None, None
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    if sd == 0:
        return mean, mean
    from scipy import stats  # only for an integration interval

    half = stats.t.ppf(0.975, len(values) - 1) * sd / math.sqrt(len(values))
    return mean - half, mean + half


def _integration_score(result: Any) -> Optional[float]:
    """A result's integration score, top-level or in ``judge_scores``."""
    score = _get(result, "integration_score")
    if score is None:
        score = _get(_get(result, "judge_scores"), "integration_score")
    return score


def _summarize_integration(results: List[Any]) -> Optional[Dict[str, Any]]:
    """The integration scores' ``n``, ``mean`` with its 95% t-interval
    (None for one score), ``share_ge_4`` and ``unscored``; None when no
    result has a score."""
    scores = [float(s) for s in map(_integration_score, results)
              if s is not None]
    if not scores:
        return None
    low, high = t_interval(scores)
    return {
        "n": len(scores),
        "mean": statistics.fmean(scores),
        "ci_low": low,
        "ci_high": high,
        "share_ge_4": sum(1 for s in scores if s >= 4) / len(scores),
        "unscored": len(results) - len(scores),
    }


def _summarize_passes(kind: str, results: List[Any]) -> Dict[str, Any]:
    """A judge-free probe type's strict pass rate and its counts."""
    out = _proportion(_get(result, "passed") for result in results)
    out["unscored"] = sum(1 for r in results if _get(r, "passed") is None)
    out["cap_bound"] = _true_count(results, "cap_bound")
    out["budget_bound"] = _true_count(results, "budget_bound")
    out["contaminated"] = sum(1 for r in results if _get(r, "contaminated"))
    if kind in EXPECTED_TYPES:
        out["semantic_only"] = _true_count(results, "semantic_only")
        out["semantic_error"] = sum(
            1 for r in results if _get(r, "semantic_error")
        )
    if kind in STALE_TYPES:
        out["lenient"] = _proportion(
            _get(result, "expected_present") for result in results
        )
        both = [r for r in results if _get(r, "expected_present")
                and _get(r, "stale_present")]
        out["names_both"] = len(both)
        out["named_as_past"] = sum(
            1 for r in both if _get(r, "transition_marked")
        )
    if kind in HARD_CONSTRAINTS:
        out["forbidden_in_block"] = _true_count(results, "forbidden_in_block")
        out["forbidden_in_answer"] = _true_count(
            results, "forbidden_in_answer"
        )
    return out


def summarize(probe_results: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    """Per probe type (in ``PROBE_TYPES`` order, then any other type),
    from ``score_probe`` results (dicts or models).

    A judge-free type gets its strict pass rate (``n``, ``passed``,
    ``rate``, Wilson ``ci_low`` / ``ci_high``; a ``passed`` of None is
    counted in ``unscored``, not in ``n``) and how many probes had the
    cap and the budget bind (None where no probe knows), were
    ``contaminated`` and, for recall, recency and contradiction, were
    ``semantic_only`` or carry a ``semantic_error`` (how many). Recency
    and contradiction add the ``lenient`` rate (``expected_present``
    alone) and the split of answers that name both values
    (``names_both``, of which ``named_as_past`` were
    transition-marked). Deletion and privacy add where the forbidden
    value appeared. Integration has no pass rate: it is reported, as
    ``n``, ``mean`` with a 95% t-interval (None for one score) and
    ``share_ge_4``, only when its results carry an
    ``integration_score``.
    """
    groups: Dict[str, List[Any]] = {}
    for result in probe_results:
        kind = _get(result, "type")
        if not kind:
            raise ValueError("a probe result without a type")
        groups.setdefault(kind, []).append(result)
    order = [kind for kind in PROBE_TYPES if kind in groups]
    order += sorted(kind for kind in groups if kind not in PROBE_TYPES)
    summary: Dict[str, Dict[str, Any]] = {}
    for kind in order:
        if kind == "integration":
            integration = _summarize_integration(groups[kind])
            if integration is not None:
                summary[kind] = integration
        else:
            summary[kind] = _summarize_passes(kind, groups[kind])
    return summary
