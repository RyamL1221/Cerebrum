"""LLM-as-judge evaluation for the shared memory evaluation harness.

Uses ``llm_chat_with_json_output`` to score assistant responses on
profile usage, task-context usage, and integration using a structured
3-score rubric.
"""

import hashlib
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from string import Template
from typing import Any, Callable, Dict, List, Optional

from cerebrum.llm.apis import llm_chat_with_json_output
from cerebrum.config.config_manager import config

from benchmarks.shared_memory.metrics import (  # noqa: F401 (re-exported)
    DIMENSIONS,
    SCORE_FIELD,
    _extract_keywords,
    hybrid_scores,
    keyword_score,
    keyword_scores,
    median_score,
)
from benchmarks.shared_memory.models import (
    JudgeScores,
    SyntheticProfile,
    SyntheticTaskContext,
)
from benchmarks.shared_memory.synth import _unwrap_nested

logger = logging.getLogger(__name__)

# Version 2 names no memory mechanism, so the prompt is the same for every
# condition, and drops the plausible-actions section, which results files
# do not store and so a re-judge could not reproduce. The rubric is
# unchanged from version 1.
JUDGE_PROMPT_VERSION = 2
# The judge's decoding (Subtask 9d follow-up): greedy with a fixed seed,
# on the judge's llms entry (the kernel applies it to the call). The
# prompt is unchanged, so this is still judge v2, with decoding recorded.
JUDGE_TEMPERATURE = 0.0
JUDGE_SEED = 20261105

SYSTEM_PROMPT = (
    "You are an expert evaluator. You MUST respond with ONLY a valid JSON "
    "object. No markdown code fences. No explanation text. No preamble. "
    "Just the raw JSON object. You are evaluating whether an assistant's "
    "response reflects the user profile and task context given below. A "
    "concise response that correctly references these attributes is "
    "well-personalized; a long response that does not is generic."
)

USER_PROMPT_TEMPLATE = Template(
    "Evaluate the following AI assistant response.\n\n"
    "--- USER PROFILE ---\n"
    "Name: $user_name\n"
    "Preferred Tools: $preferred_tools\n"
    "Preferred Language: $preferred_language\n"
    "Response Style: $response_style\n\n"
    "--- TASK CONTEXT ---\n"
    "Current Project: $current_project\n"
    "Active Experiment: $active_experiment\n"
    "Goals: $goals\n"
    "Blockers: $blockers\n"
    "Next Steps: $next_steps\n\n"
    "--- FOLLOW-UP QUERY ---\n"
    "$query\n\n"
    "--- ASSISTANT RESPONSE ---\n"
    "$response\n\n"
    "--- SCORING RUBRIC ---\n"
    "Score based on whether the response content references "
    "profile and task attributes, regardless of response length. "
    "A short response that correctly references the user's "
    "preferred tools and current project is well-personalized.\n\n"
    "Profile Usage (1-5):\n"
    "  5 = Correctly and specifically references multiple profile "
    "attributes (tools, language, style) in the recommendation, "
    "regardless of response length\n"
    "  4 = Correctly references most profile attributes\n"
    "  3 = References some profile attributes but misses key ones\n"
    "  2 = Vague or incorrect references to profile attributes\n"
    "  1 = No evidence of profile knowledge; response could apply "
    "to any developer\n\n"
    "Task Usage (1-5):\n"
    "  5 = Correctly and specifically references project goals, "
    "blockers, and next steps in the recommendation, "
    "regardless of response length\n"
    "  4 = Correctly references most task context details\n"
    "  3 = References some task context details but misses key ones\n"
    "  2 = Vague or incorrect references to task context\n"
    "  1 = No evidence of task context knowledge; response is "
    "generic advice\n\n"
    "Integration (1-5):\n"
    "  5 = Seamlessly combines profile preferences and task context "
    "into a single grounded recommendation\n"
    "  4 = Combines both sources with minor gaps in integration\n"
    "  3 = Addresses profile and task context separately without "
    "integrating them\n"
    "  2 = Mentions both sources but the recommendation does not "
    "logically follow from them\n"
    "  1 = No integration; response addresses at most one source "
    "or is entirely generic\n\n"
    "Respond with ONLY a JSON object (no markdown fences, no explanation, "
    "no text before or after). Use exactly these keys:\n"
    '{"profile_usage_score": <int 1-5>, "task_usage_score": <int 1-5>, '
    '"integration_score": <int 1-5>, "profile_usage_reasoning": '
    '"<string>", "task_usage_reasoning": "<string>", '
    '"integration_reasoning": "<string>"}'
)


def judge_prompt_sha256() -> str:
    """Return the SHA-256 of the judge's system prompt and user template."""
    text = SYSTEM_PROMPT + "\n" + USER_PROMPT_TEMPLATE.template
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Canonical field names for the 3-score rubric
_SCORE_FIELDS = [
    "profile_usage_score",
    "task_usage_score",
    "integration_score",
]


def _canonicalize_key(raw: str) -> str:
    """Convert an arbitrary key string to snake_case without trailing _score."""
    import re
    # Strip whitespace
    key = raw.strip()
    # Insert underscore before capitals (CamelCase -> Camel_Case)
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    # Lowercase everything
    key = key.lower()
    # Replace spaces and hyphens with underscores
    key = re.sub(r"[\s\-]+", "_", key)
    # Collapse multiple underscores
    key = re.sub(r"_+", "_", key)
    # Strip trailing _score suffix for matching
    key = re.sub(r"_score$", "", key)
    return key


# Map canonicalized base names to their canonical output keys
_CANONICAL_MAP: Dict[str, str] = {
    "profile_usage": "profile_usage_score",
    "task_usage": "task_usage_score",
    "integration": "integration_score",
    "profile_usage_reasoning": "profile_usage_reasoning",
    "task_usage_reasoning": "task_usage_reasoning",
    "integration_reasoning": "integration_reasoning",
}


def _normalize_judge_keys(data: dict) -> dict:
    """Normalize LLM judge response keys to the expected 3-score format.

    Handles variant key formats: snake_case, CamelCase, Title Case,
    hyphenated, UPPER_SNAKE, with or without ``_score`` suffix.
    """
    normalized: Dict[str, Any] = {}
    for k, v in data.items():
        canon = _canonicalize_key(k)
        target = _CANONICAL_MAP.get(canon)
        if target and not isinstance(v, (dict, list)):
            normalized[target] = v
        elif target is None and isinstance(v, dict):
            # Nested reasoning dict — extract by keyword
            for rk, rv in v.items():
                rk_lower = rk.lower().strip()
                if "profile" in rk_lower and "profile_usage_reasoning" not in normalized:
                    normalized["profile_usage_reasoning"] = str(rv)
                elif "task" in rk_lower and "task_usage_reasoning" not in normalized:
                    normalized["task_usage_reasoning"] = str(rv)
                elif "integrat" in rk_lower and "integration_reasoning" not in normalized:
                    normalized["integration_reasoning"] = str(rv)
    return normalized


def _clamp_score(value: Any, name: str) -> int:
    """Clamp a score to [1, 5], logging a warning if out of range."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        logger.warning("%s is not an integer (%s), defaulting to 1", name, value)
        return 1
    if v < 1 or v > 5:
        logger.warning("%s %d out of range, clamping to [1, 5]", name, v)
    return max(1, min(5, v))


def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract a JSON object from free-form text.

    Looks for the first ``{`` and last ``}`` in the text and attempts
    to parse the substring as JSON. Returns None if no valid JSON found.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _now() -> str:
    """The current UTC time, ISO 8601."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def build_messages(
    query: str,
    response: str,
    profile: SyntheticProfile,
    task_context: SyntheticTaskContext,
) -> List[Dict[str, str]]:
    """The judge's system and user messages for one answer (prompt v2),
    the same for every judge."""
    user_content = USER_PROMPT_TEMPLATE.substitute(
        user_name=profile.user_name,
        preferred_tools=", ".join(profile.preferred_tools),
        preferred_language=profile.preferred_language,
        response_style=profile.response_style,
        current_project=task_context.current_project,
        active_experiment=task_context.active_experiment,
        goals=", ".join(task_context.goals),
        blockers=", ".join(task_context.blockers),
        next_steps=", ".join(task_context.next_steps),
        query=query,
        response=response,
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def parse_judge_reply(raw: Any) -> JudgeScores:
    """A judge reply's scores: JSON (or the first ``{`` to the last
    ``}``), keys normalized, each score clamped to 1-5. Empty scores for
    a reply without all three."""
    if raw is None:
        return JudgeScores()
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = _extract_json_from_text(raw)
            if data is None:
                logger.warning("Judge LLM returned non-JSON text: %s",
                               raw[:200])
                return JudgeScores()
    else:
        data = raw
    if not isinstance(data, dict):
        logger.warning("Judge LLM returned non-dict data: %r", data)
        return JudgeScores()
    logger.debug("Judge parsed data before normalization: %s", data)
    if not all(k in data for k in _SCORE_FIELDS):
        data = _normalize_judge_keys(data)
    pu = data.get("profile_usage_score")
    tu = data.get("task_usage_score")
    ig = data.get("integration_score")
    if pu is None or tu is None or ig is None:
        logger.warning("Judge returned incomplete scores: %s", data)
        return JudgeScores()
    return JudgeScores(
        profile_usage_score=_clamp_score(pu, "profile_usage_score"),
        task_usage_score=_clamp_score(tu, "task_usage_score"),
        integration_score=_clamp_score(ig, "integration_score"),
        profile_usage_reasoning=data.get("profile_usage_reasoning"),
        task_usage_reasoning=data.get("task_usage_reasoning"),
        integration_reasoning=data.get("integration_reasoning"),
    )


def _usage_of(usage: Any) -> Optional[Dict[str, int]]:
    """``{prompt_tokens, completion_tokens}`` of a reply's usage."""
    if not isinstance(usage, dict):
        return None
    kept = {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens")}
    return kept if any(v is not None for v in kept.values()) else None


class LLMJudge:
    """The primary judge: a model behind the kernel's ``/query``
    (``gpt-5.4`` on Azure), greedy with a fixed seed."""

    def __init__(
        self, agent_name: str = "eval_judge", llms: list | None = None,
        temperature: float | None = JUDGE_TEMPERATURE,
        seed: int | None = JUDGE_SEED,
    ):
        self.agent_name = agent_name
        self.kernel_url = config.get_kernel_url()
        # The decoding rides on the llms entries; without llms (the
        # kernel's default model) none applies and none is recorded.
        if llms:
            self.temperature, self.seed = temperature, seed
            extra = {k: v for k, v in (("temperature", temperature),
                                       ("seed", seed)) if v is not None}
            llms = [dict(entry, **extra) for entry in llms]
        else:
            self.temperature = self.seed = None
        self.llms = llms

    @property
    def model(self) -> Optional[str]:
        """``backend/name`` of the judge model, as the kernel calls it."""
        if not self.llms:
            return None
        entry = self.llms[0]
        backend = entry.get("backend")
        return f"{backend}/{entry['name']}" if backend else entry["name"]

    def decoding(self) -> Dict[str, Any]:
        return {"temperature": self.temperature, "seed": self.seed}

    def _build_judge_prompt(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> List[Dict[str, str]]:
        """Build the messages list for the LLM judge call."""
        return build_messages(query, response, profile, task_context)

    def evaluate(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> JudgeScores:
        """One judge call: the answer's scores, with the call's model,
        time and tokens. Empty scores when the reply has none."""
        messages = self._build_judge_prompt(
            query, response, profile, task_context
        )

        response_format: Dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": "judge_scores",
                "schema": {
                    "type": "object",
                    "properties": {
                        "profile_usage_score": {"type": "integer"},
                        "task_usage_score": {"type": "integer"},
                        "integration_score": {"type": "integer"},
                        "profile_usage_reasoning": {"type": "string"},
                        "task_usage_reasoning": {"type": "string"},
                        "integration_reasoning": {"type": "string"},
                    },
                    "required": [
                        "profile_usage_score",
                        "task_usage_score",
                        "integration_score",
                        "profile_usage_reasoning",
                        "task_usage_reasoning",
                        "integration_reasoning",
                    ],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

        call = {"model": self.model, "judged_at": _now()}
        try:
            llm_response = llm_chat_with_json_output(
                agent_name=self.agent_name,
                messages=messages,
                base_url=self.kernel_url,
                response_format=response_format,
                llms=self.llms,
            )

            raw = llm_response["response"]["response_message"]
            call["token_usage"] = _usage_of(llm_response.get("token_usage"))
            logger.debug("Judge raw response_message: %r", raw)
            if raw is None:
                # Fallback: retry with plain llm_chat (kernel may not support
                # response_format passthrough for chat_with_json_output)
                logger.debug(
                    "Falling back to llm_chat for judge scoring."
                )
                from cerebrum.llm.apis import llm_chat
                llm_response = llm_chat(
                    agent_name=self.agent_name,
                    messages=messages,
                    base_url=self.kernel_url,
                    llms=self.llms,
                )
                raw = llm_response["response"]["response_message"]
                call["token_usage"] = _usage_of(
                    llm_response.get("token_usage"))
                if raw is None:
                    logger.warning(
                        "Judge LLM returned None response_message on fallback — "
                        "model may be unavailable. "
                        "llms=%s kernel=%s",
                        self.llms,
                        self.kernel_url,
                    )
                    return JudgeScores(**call)
            return parse_judge_reply(raw).model_copy(update=call)

        except Exception as e:
            logger.warning("Judge evaluation failed: %s", e)
            return JudgeScores(**call)


# The second judge (Subtask 20, METRICS.md "The judges"): Claude Sonnet
# 5.5 on the Anthropic API. It accepts no sampling parameter, so it
# samples at the API's default; thinking is off as far as the model
# allows (``between_tools``, and the judge passes no tools).
CLAUDE_MODEL = "claude-sonnet-5-5"
CLAUDE_MAX_TOKENS = 1024
CLAUDE_THINKING = {"type": "between_tools"}
# An OAuth token from ``ant auth login`` needs this beta on /v1/messages.
OAUTH_BETA = "oauth-2025-04-20"


def anthropic_client():
    """An Anthropic client on the ``ant`` profile's OAuth token, fetched
    now (``ant auth print-credentials --access-token``) and never stored
    or logged; it bills the profile's workspace. Refuses to run with an
    ``ANTHROPIC_API_KEY`` set, which would outrank the token and bill
    another workspace."""
    import anthropic

    if os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is set: the second judge uses the `ant` "
            "profile's OAuth token; unset the key")
    token = subprocess.run(
        ["ant", "auth", "print-credentials", "--access-token"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return anthropic.Anthropic(
        auth_token=token, default_headers={"anthropic-beta": OAUTH_BETA})


class ClaudeJudge:
    """The second judge: the same prompt v2 on Claude Sonnet 5.5, called
    directly through the Anthropic SDK (one call per ``evaluate``; many
    in one batch through ``claude_batch_scores``)."""

    temperature = None
    seed = None

    def __init__(self, model: str = CLAUDE_MODEL,
                 max_tokens: int = CLAUDE_MAX_TOKENS,
                 client_factory: Callable[[], Any] = anthropic_client):
        self.model_id = model
        self.max_tokens = max_tokens
        self.client_factory = client_factory

    @property
    def model(self) -> str:
        return f"anthropic/{self.model_id}"

    def decoding(self) -> Dict[str, Any]:
        return {"sampling": "api default", "thinking": CLAUDE_THINKING,
                "max_tokens": self.max_tokens}

    def params(self, query: str, response: str, profile: SyntheticProfile,
               task_context: SyntheticTaskContext) -> Dict[str, Any]:
        """The Messages request for one answer."""
        system, user = build_messages(query, response, profile,
                                      task_context)
        return {"model": self.model_id, "max_tokens": self.max_tokens,
                "thinking": CLAUDE_THINKING, "system": system["content"],
                "messages": [user]}

    def scores_of(self, message: Any, **call: Any) -> JudgeScores:
        """A Messages reply's scores, model and tokens."""
        text = "".join(block.text for block in message.content
                       if getattr(block, "type", None) == "text")
        if message.stop_reason != "end_turn":
            logger.warning("second judge stopped on %s",
                           message.stop_reason)
        usage = getattr(message, "usage", None)
        return parse_judge_reply(text or None).model_copy(update={
            "model": f"anthropic/{message.model}",
            "token_usage": {
                "prompt_tokens": getattr(usage, "input_tokens", None),
                "completion_tokens": getattr(usage, "output_tokens", None),
            } if usage else None,
            **call,
        })

    def evaluate(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> JudgeScores:
        """One judge call through the Messages API."""
        judged_at = _now()
        try:
            message = self.client_factory().messages.create(
                **self.params(query, response, profile, task_context))
        except Exception as e:
            logger.warning("Second judge call failed: %s", e)
            return JudgeScores(model=self.model, judged_at=judged_at)
        return self.scores_of(message, judged_at=judged_at)


# A batch's results download is retried this many times (a transient
# connection error must not lose a finished batch's results).
BATCH_DOWNLOADS = 3


def claude_batch_scores(
    judge: ClaudeJudge,
    items: Dict[str, Dict[str, Any]],
    poll_seconds: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
    batch_id: Optional[str] = None,
    on_submit: Optional[Callable[[str], None]] = None,
) -> Dict[str, JudgeScores]:
    """Judge ``items`` (custom id -> ``{query, response, profile,
    task_context}``) in one Message Batch, and return each item's scores
    (empty for an errored or unparsable result), with the batch's id,
    its submission time and its end time (``judged_at``). Each status
    poll and each results download take a new token; the download is
    retried ``BATCH_DOWNLOADS`` times. ``batch_id``: collect that batch,
    already submitted for these items, instead of submitting one;
    ``on_submit`` gets a new batch's id as soon as it exists."""
    from anthropic.types.message_create_params import (
        MessageCreateParamsNonStreaming,
    )
    from anthropic.types.messages.batch_create_params import Request

    if batch_id is None:
        requests = [
            Request(custom_id=custom_id,
                    params=MessageCreateParamsNonStreaming(
                        **judge.params(**item)))
            for custom_id, item in items.items()
        ]
        batch = judge.client_factory().messages.batches.create(
            requests=requests)
        submitted_at = _now()
        if on_submit is not None:
            on_submit(batch.id)
        logger.info("second judge: batch %s, %d requests", batch.id,
                    len(requests))
    else:
        batch = judge.client_factory().messages.batches.retrieve(batch_id)
        created = getattr(batch, "created_at", None)
        submitted_at = created.isoformat() if created else None
        logger.info("second judge: collecting batch %s", batch_id)
    while batch.processing_status != "ended":
        sleep(poll_seconds)
        batch = judge.client_factory().messages.batches.retrieve(batch.id)
        logger.info("second judge: batch %s %s %s", batch.id,
                    batch.processing_status, batch.request_counts)
    ended_at = (batch.ended_at.isoformat() if getattr(batch, "ended_at",
                                                      None) else _now())
    call = {"batch_id": batch.id, "submitted_at": submitted_at,
            "judged_at": ended_at}
    for attempt in range(1, BATCH_DOWNLOADS + 1):
        scores = {custom_id: JudgeScores(model=judge.model, **call)
                  for custom_id in items}
        # The client is held while its results stream: collected
        # mid-download, it closes the stream's connection.
        client = judge.client_factory()
        try:
            for result in client.messages.batches.results(batch.id):
                if result.custom_id not in scores:
                    continue
                if result.result.type == "succeeded":
                    scores[result.custom_id] = judge.scores_of(
                        result.result.message, **call)
                else:
                    logger.warning("second judge: %s %s", result.custom_id,
                                   result.result.type)
            return scores
        except Exception as error:
            if attempt == BATCH_DOWNLOADS:
                raise
            logger.warning("second judge: downloading batch %s failed "
                           "(%s); again", batch.id, error)
            sleep(poll_seconds)
    return scores


# The keyword score (``_extract_keywords``, ``keyword_score``) is a
# judge-free measure: it lives in ``metrics.py`` (imported above).


# How a trial's scores are produced: the keyword score averaged with the
# LLM judge's, rounded, per dimension. Recorded on every scored trial.
SCORER = "hybrid_keyword_llm"
# LLM judge calls per trial before the trial is marked failed.
JUDGE_RETRIES = 3


class JudgeFailed(RuntimeError):
    """The LLM judge gave no complete scores after ``attempts`` calls."""

    def __init__(self, attempts: int):
        super().__init__(f"no LLM judge scores after {attempts} attempts")
        self.attempts = attempts


def _complete(scores: JudgeScores) -> bool:
    return all(getattr(scores, f) is not None for f in _SCORE_FIELDS)


class HybridJudge:
    """Judges an answer ``repeats`` times with one LLM judge and keeps
    every repeat (METRICS.md, "The three scores of a judgment").

    ``evaluate`` returns the hybrid scores (the keyword score averaged
    with the median LLM score, halves to even) in the three score
    fields, as every run before Subtask 20 stored them, and the full
    record in ``record``: each repeat's LLM scores, reasoning, time and
    tokens, their median (``llm``, the judged metric), the keyword
    scores (``keyword``, judge-free) and the hybrid (``hybrid``). The
    LLM half is required: a repeat without complete scores after
    ``JUDGE_RETRIES`` calls raises ``JudgeFailed``; it never scores on
    keywords alone.
    """

    def __init__(
        self, agent_name: str = "eval_judge", llms: list | None = None,
        temperature: float | None = JUDGE_TEMPERATURE,
        seed: int | None = JUDGE_SEED,
        repeats: int = 1,
        judge: Any = None,
        name: Optional[str] = None,
    ):
        if repeats < 1 or repeats % 2 == 0:
            raise ValueError(
                f"judge repeats must be odd and positive, got {repeats}")
        self.llm_judge = judge if judge is not None else LLMJudge(
            agent_name=agent_name, llms=llms,
            temperature=temperature, seed=seed,
        )
        self.repeats = repeats
        # A judge on the kernel's default model has no model to name.
        self.name = name or judge_name_of(self.llm_judge) or "kernel-default"

    @property
    def temperature(self) -> float | None:
        return self.llm_judge.temperature

    @property
    def seed(self) -> int | None:
        return self.llm_judge.seed

    def describe(self) -> Dict[str, Any]:
        """The judge as a run's metadata records it."""
        decoding = getattr(self.llm_judge, "decoding", None)
        return {
            "name": self.name,
            "model": getattr(self.llm_judge, "model", None),
            "repeats": self.repeats,
            "prompt_version": JUDGE_PROMPT_VERSION,
            "prompt_sha256": judge_prompt_sha256(),
            "decoding": decoding() if callable(decoding) else None,
        }

    def llm_scores(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> tuple:
        """One repeat: the LLM judge's scores, the calls they took, and
        every call's scores (each call's tokens are spent). Raises
        ``JudgeFailed`` after ``JUDGE_RETRIES`` incomplete ones."""
        calls = []
        for attempt in range(1, JUDGE_RETRIES + 1):
            scores = self.llm_judge.evaluate(
                query, response, profile, task_context
            )
            calls.append(scores)
            if _complete(scores):
                return scores, attempt, calls
            logger.warning(
                "LLM judge attempt %d/%d gave no complete scores",
                attempt, JUDGE_RETRIES,
            )
        raise JudgeFailed(JUDGE_RETRIES)

    def evaluate(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> JudgeScores:
        """Judge the answer ``repeats`` times. Raises ``JudgeFailed``."""
        judgments = []
        for repeat in range(1, self.repeats + 1):
            scores, attempts, calls = self.llm_scores(
                query, response, profile, task_context
            )
            judgments.append(judgment(repeat, scores, attempts, calls))
        return self.from_judgments(response, profile, task_context,
                                   judgments)

    def from_judgments(
        self,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
        judgments: List[Dict[str, Any]],
    ) -> JudgeScores:
        """The hybrid scores and the record, from complete judgments."""
        llm = {d: median_score(j["scores"][d] for j in judgments)
               for d in DIMENSIONS}
        first = judgments[0]
        median = JudgeScores(**{
            SCORE_FIELD[d]: llm[d] for d in DIMENSIONS
        }, **{
            f"{SCORE_FIELD[d][:-len('_score')]}_reasoning":
                first["reasoning"][d] for d in DIMENSIONS
        })
        combined = self.combine(response, profile, task_context, median)
        keyword = keyword_scores(response, profile, task_context)
        spent = [j["token_usage"] for j in judgments if j["token_usage"]]
        prompt = sum(u.get("prompt_tokens") or 0 for u in spent)
        completion = sum(u.get("completion_tokens") or 0 for u in spent)
        times = [j["judged_at"] for j in judgments if j["judged_at"]]
        record = {
            **self.describe(),
            "judge": self.name,
            "judgments": judgments,
            "llm": llm,
            "keyword": keyword,
            "hybrid": hybrid_scores(keyword, llm),
            "judged_at": {"first": min(times) if times else None,
                          "last": max(times) if times else None},
            "token_usage": {
                "calls": sum(j["attempts"] for j in judgments),
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
                "models": sorted({j["model"] for j in judgments
                                  if j["model"]}),
            },
        }
        record.pop("name")
        return combined.model_copy(update={
            "judge_attempts": record["token_usage"]["calls"],
            "model": first["model"],
            "judged_at": first["judged_at"],
            "record": record,
        })

    @staticmethod
    def combine(
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
        llm_scores: JudgeScores,
    ) -> JudgeScores:
        """Average the keyword scores with the LLM's. Every LLM score
        must be present (``ValueError`` otherwise)."""
        if not _complete(llm_scores):
            raise ValueError("combine needs all three LLM judge scores")
        keywords = _extract_keywords(profile, task_context)
        kw_profile = keyword_score(response, keywords["profile"])
        kw_task = keyword_score(response, keywords["task"])
        kw_integration = min(kw_profile, kw_task)  # both must be present

        def _avg(kw: int, llm_val: int) -> int:
            return max(1, min(5, round((kw + llm_val) / 2)))

        return JudgeScores(
            profile_usage_score=_avg(kw_profile, llm_scores.profile_usage_score),
            task_usage_score=_avg(kw_task, llm_scores.task_usage_score),
            integration_score=_avg(kw_integration, llm_scores.integration_score),
            profile_usage_reasoning=(
                f"keyword_hits={kw_profile}/5; "
                + (llm_scores.profile_usage_reasoning or "")
            ),
            task_usage_reasoning=(
                f"keyword_hits={kw_task}/5; "
                + (llm_scores.task_usage_reasoning or "")
            ),
            integration_reasoning=(
                f"keyword_integration={kw_integration}/5; "
                + (llm_scores.integration_reasoning or "")
            ),
        )


def judgment(repeat: int, scores: JudgeScores, attempts: int,
             calls: List[JudgeScores]) -> Dict[str, Any]:
    """One repeat's record: its complete scores and reasoning, the calls
    it took, and the tokens of every one of them."""
    spent = [c.token_usage for c in calls if c.token_usage]
    usage = None
    if spent:
        usage = {k: sum(u.get(k) or 0 for u in spent)
                 for k in ("prompt_tokens", "completion_tokens")}
    return {
        "repeat": repeat,
        "scores": {d: getattr(scores, SCORE_FIELD[d]) for d in DIMENSIONS},
        "reasoning": {
            d: getattr(scores, f"{SCORE_FIELD[d][:-len('_score')]}_reasoning")
            for d in DIMENSIONS},
        "attempts": attempts,
        "model": scores.model,
        "judged_at": scores.judged_at,
        "submitted_at": scores.submitted_at,
        "batch_id": scores.batch_id,
        "token_usage": usage,
    }


def batch_judgments(
    llm_judge: Any,
    items: Dict[str, Dict[str, Any]],
    repeats: int,
    batch_scores: Callable[..., Dict[str, JudgeScores]] = None,
    **first_round: Any,
) -> Dict[str, Dict[int, Any]]:
    """Judge many answers ``repeats`` times each through the second
    judge's Message Batches: every judgment in one batch, the incomplete
    ones resubmitted, up to ``JUDGE_RETRIES`` attempts. ``items``: id ->
    ``{query, response, profile, task_context}``. Returns id -> repeat
    -> its ``judgment`` record, or a ``JudgeFailed`` for a repeat that
    never completed. ``first_round`` goes to the first batch call
    (``batch_id`` to collect a batch already submitted for every
    judgment; ``on_submit``, to every round)."""
    batch_scores = batch_scores or claude_batch_scores
    # The API's custom id: [a-zA-Z0-9_-]{1,64}.
    keys = {f"{item_id}-{r}": (item_id, r) for item_id in items
            for r in range(1, repeats + 1)}
    calls: Dict[str, List[JudgeScores]] = {key: [] for key in keys}
    done: Dict[str, JudgeScores] = {}
    pending = list(keys)
    for round_ in range(JUDGE_RETRIES):
        if not pending:
            break
        extra = first_round if round_ == 0 else {
            k: v for k, v in first_round.items() if k == "on_submit"}
        got = batch_scores(llm_judge, {
            key: items[keys[key][0]] for key in pending}, **extra)
        for key in pending:
            calls[key].append(got[key])
            if _complete(got[key]):
                done[key] = got[key]
        pending = [key for key in pending if key not in done]
    out: Dict[str, Dict[int, Any]] = {item_id: {} for item_id in items}
    for key, (item_id, r) in keys.items():
        out[item_id][r] = (
            judgment(r, done[key], len(calls[key]), calls[key])
            if key in done else JudgeFailed(len(calls[key])))
    return out


def batch_evaluate(
    judge: HybridJudge,
    items: Dict[str, Dict[str, Any]],
    batch_scores: Callable[..., Dict[str, JudgeScores]] = None,
) -> Dict[str, Any]:
    """``HybridJudge.evaluate`` for many answers through the second
    judge's batches (``batch_judgments``). Returns id -> the hybrid
    ``JudgeScores`` with its record, or a ``JudgeFailed`` for an answer
    a repeat of which never completed."""
    got = batch_judgments(judge.llm_judge, items, judge.repeats,
                          batch_scores)
    out: Dict[str, Any] = {}
    for item_id, item in items.items():
        repeats = [got[item_id][r] for r in range(1, judge.repeats + 1)]
        failed = [j for j in repeats if isinstance(j, JudgeFailed)]
        out[item_id] = failed[0] if failed else judge.from_judgments(
            item["response"], item["profile"], item["task_context"],
            repeats)
    return out


# The judges by name (``--judge``; METRICS.md, "The judges").
PRIMARY_JUDGE = "gpt-5.4"
SECOND_JUDGE = "claude-sonnet-5.5"
JUDGES: Dict[str, Callable[[], Any]] = {
    PRIMARY_JUDGE: lambda: LLMJudge(
        llms=[{"name": "gpt-5.4", "backend": "azure"}]),
    SECOND_JUDGE: lambda: ClaudeJudge(),
}


def judge_name_of(judge: Any) -> Optional[str]:
    """A judge's name: the registry's for the second judge, else the
    kernel model's name (``gpt-5.4``)."""
    if isinstance(judge, ClaudeJudge):
        return SECOND_JUDGE if judge.model_id == CLAUDE_MODEL \
            else judge.model_id
    llms = getattr(judge, "llms", None)
    return llms[0]["name"] if llms else None


def make_judge(name: Optional[str] = None, llms: list | None = None,
               repeats: int = 1) -> HybridJudge:
    """The named judge (``JUDGES``), or the kernel judge on ``llms``."""
    if name is not None:
        if name not in JUDGES:
            raise ValueError(
                f"unknown judge {name!r}; one of {sorted(JUDGES)}")
        return HybridJudge(judge=JUDGES[name](), repeats=repeats, name=name)
    return HybridJudge(llms=llms, repeats=repeats)


# The second judge's subset in the full grid (AIOS docs/FULL_GRID.md,
# "The two judges"), fixed before the grid runs: 30% of each cell's
# users, by user index alone, stratified by echo users.
SECOND_JUDGE_SHARE = 0.3
SECOND_JUDGE_SEED = 20261121
SECOND_JUDGE_USERS = 150   # users_v2's users


def second_judge_order(seed: int = SECOND_JUDGE_SEED
                       ) -> Dict[str, List[int]]:
    """Each stratum's user indices (of users_v2's 150) in the order one
    ``random.Random(seed)`` shuffles them: the echo users first, then
    the others."""
    import random

    from benchmarks.shared_memory.synth_v2 import is_echo_user

    rng = random.Random(seed)
    order = {}
    for stratum, echo in (("echo", True), ("other", False)):
        users = [i for i in range(SECOND_JUDGE_USERS)
                 if is_echo_user(i) == echo]
        rng.shuffle(users)
        order[stratum] = users
    return order


def second_judge_users(users) -> List[int]:
    """The users of a cell whose answers the second judge scores: from
    each stratum, the first round(0.3 x the cell's users in it) of the
    cell's users in ``second_judge_order`` (at least one when the cell
    has a user of the stratum). Sorted."""
    cell = set(users)
    outside = cell - set(range(SECOND_JUDGE_USERS))
    if outside:
        raise ValueError(f"users outside users_v2: {sorted(outside)}")
    chosen: List[int] = []
    for ranked in second_judge_order().values():
        mine = [i for i in ranked if i in cell]
        if mine:
            chosen += mine[:max(1, round(SECOND_JUDGE_SHARE * len(mine)))]
    return sorted(chosen)
