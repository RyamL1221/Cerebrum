"""LLM-as-judge evaluation for the shared memory evaluation harness.

Uses ``llm_chat_with_json_output`` to score assistant responses on
profile usage, task-context usage, and integration using a structured
3-score rubric.
"""

import hashlib
import json
import logging
from string import Template
from typing import Any, Dict, List

from cerebrum.llm.apis import llm_chat_with_json_output
from cerebrum.config.config_manager import config

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


class LLMJudge:
    """Evaluates assistant responses using a 3-score rubric."""

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

    def _build_judge_prompt(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> List[Dict[str, str]]:
        """Build the messages list for the LLM judge call."""
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

    def evaluate(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> JudgeScores:
        """Score an assistant response on profile usage, task usage, and integration."""
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

        try:
            llm_response = llm_chat_with_json_output(
                agent_name=self.agent_name,
                messages=messages,
                base_url=self.kernel_url,
                response_format=response_format,
                llms=self.llms,
            )

            raw = llm_response["response"]["response_message"]
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
                if raw is None:
                    logger.warning(
                        "Judge LLM returned None response_message on fallback — "
                        "model may be unavailable. "
                        "llms=%s kernel=%s",
                        self.llms,
                        self.kernel_url,
                    )
                    return JudgeScores()
            # Try to parse as JSON; if it fails, try to extract JSON from text
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    # Try to extract JSON object from free-form text
                    data = _extract_json_from_text(raw)
                    if data is None:
                        logger.warning("Judge LLM returned non-JSON text: %s", raw[:200])
                        return JudgeScores()
            else:
                data = raw
            if not isinstance(data, dict):
                logger.warning("Judge LLM returned non-dict data: %r", data)
                return JudgeScores()
            logger.debug("Judge parsed data before normalization: %s", data)

            # If the dict already has the exact keys we need, use them directly
            if all(k in data for k in ("profile_usage_score", "task_usage_score", "integration_score")):
                pass  # data already has correct keys
            else:
                data = _normalize_judge_keys(data)

            pu = data.get("profile_usage_score")
            tu = data.get("task_usage_score")
            ig = data.get("integration_score")

            if pu is None or tu is None or ig is None:
                logger.warning("Judge returned incomplete scores: %s", data)
                return JudgeScores()

            scores = JudgeScores(
                profile_usage_score=_clamp_score(pu, "profile_usage_score"),
                task_usage_score=_clamp_score(tu, "task_usage_score"),
                integration_score=_clamp_score(ig, "integration_score"),
                profile_usage_reasoning=data.get("profile_usage_reasoning"),
                task_usage_reasoning=data.get("task_usage_reasoning"),
                integration_reasoning=data.get("integration_reasoning"),
            )

            return scores

        except Exception as e:
            logger.warning("Judge evaluation failed: %s", e)
            return JudgeScores()


def _extract_keywords(profile: SyntheticProfile, task_context: SyntheticTaskContext) -> Dict[str, list]:
    """Extract searchable keywords from synthetic profile and task context.

    Returns a dict with 'profile' and 'task' keyword lists.
    """
    profile_keywords = []
    # User name (first and last separately)
    for part in profile.user_name.split():
        if len(part) > 2:
            profile_keywords.append(part.lower())
    # Tools
    for tool in profile.preferred_tools:
        profile_keywords.append(tool.lower())
    # Language
    if profile.preferred_language:
        profile_keywords.append(profile.preferred_language.lower())

    task_keywords = []
    # Project name words (skip short words)
    for word in task_context.current_project.split():
        if len(word) > 2:
            task_keywords.append(word.lower())
    # Experiment name words
    for word in task_context.active_experiment.split():
        if len(word) > 3:
            task_keywords.append(word.lower())
    # Goal keywords (first 3 significant words per goal)
    for goal in task_context.goals:
        for word in goal.split():
            if len(word) > 3:
                task_keywords.append(word.lower())
    # Blocker keywords
    for blocker in task_context.blockers:
        for word in blocker.split():
            if len(word) > 3:
                task_keywords.append(word.lower())

    return {"profile": list(set(profile_keywords)), "task": list(set(task_keywords))}


def keyword_score(response: str, keywords: list) -> int:
    """Score 1-5 based on fraction of keywords found in the response.

    Args:
        response: The assistant's response text.
        keywords: List of lowercase keywords to search for.

    Returns:
        Integer score 1-5.
    """
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
    """Combines deterministic keyword matching with LLM-based scoring.

    The keyword scores provide a reliable signal for whether the response
    references profile/task attributes. The LLM scores assess quality and
    integration. The final score is the average of both, rounded. The LLM
    half is required: without it after ``JUDGE_RETRIES`` calls the
    judge raises ``JudgeFailed``; it never scores on keywords alone.
    """

    def __init__(
        self, agent_name: str = "eval_judge", llms: list | None = None,
        temperature: float | None = JUDGE_TEMPERATURE,
        seed: int | None = JUDGE_SEED,
    ):
        self.llm_judge = LLMJudge(
            agent_name=agent_name, llms=llms,
            temperature=temperature, seed=seed,
        )

    @property
    def temperature(self) -> float | None:
        return self.llm_judge.temperature

    @property
    def seed(self) -> int | None:
        return self.llm_judge.seed

    def llm_scores(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
    ) -> tuple:
        """The LLM judge's scores and the number of calls they took.
        Raises ``JudgeFailed`` after ``JUDGE_RETRIES`` incomplete ones."""
        for attempt in range(1, JUDGE_RETRIES + 1):
            scores = self.llm_judge.evaluate(
                query, response, profile, task_context
            )
            if _complete(scores):
                return scores, attempt
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
        """Score using both keyword matching and LLM judge; the result
        carries ``judge_attempts``. Raises ``JudgeFailed``."""
        llm_scores, attempts = self.llm_scores(
            query, response, profile, task_context
        )
        scores = self.combine(response, profile, task_context, llm_scores)
        return scores.model_copy(update={"judge_attempts": attempts})

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
