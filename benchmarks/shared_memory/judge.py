"""LLM-as-judge evaluation for the shared memory evaluation harness.

Uses ``llm_chat_with_json_output`` to score assistant responses on
profile usage, task-context usage, and integration using a structured
3-score rubric.
"""

import json
import logging
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
        self,
        agent_name: str = "eval_judge",
        llms: list | None = None,
        rubric_version: str = "v1",
    ):
        self.agent_name = agent_name
        self.kernel_url = config.get_kernel_url()
        self.llms = llms  # Optional model override, e.g. [{"name": "gpt-4.5", "backend": "openai"}]
        # Selects the prompt/parsing path. Inert in this subtask (only "v1"
        # exists); subtask 3 branches on it and flips the stamped rubric_version.
        self.rubric_version = rubric_version

    def _build_judge_prompt(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
        plausible_actions: list[str] | None = None,
    ) -> List[Dict[str, str]]:
        """Dispatch to the v1 or v2 prompt builder based on ``rubric_version``.

        Thin dispatcher only — the v1 branch returns byte-for-byte the same
        messages this method produced before the v2 path was added, so existing
        v1 runs are unaffected.
        """
        if self.rubric_version == "v2":
            return self._build_judge_prompt_v2(
                query, response, profile, task_context, plausible_actions
            )
        return self._build_judge_prompt_v1(
            query, response, profile, task_context, plausible_actions
        )

    def _build_judge_prompt_v1(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
        plausible_actions: list[str] | None = None,
    ) -> List[Dict[str, str]]:
        """Build the messages list for the LLM judge call (v1 holistic rubric)."""
        # Build plausible actions section (only when provided and non-empty)
        plausible_actions_section = ""
        if plausible_actions:
            actions_list = "\n".join(
                f"  {i}. {action}" for i, action in enumerate(plausible_actions, 1)
            )
            plausible_actions_section = (
                "--- PLAUSIBLE ACTIONS ---\n"
                "The developer had these pending options to choose from:\n"
                f"{actions_list}\n\n"
            )

        user_content = (
            "Evaluate the following AI assistant response.\n\n"
            "--- USER PROFILE ---\n"
            f"Name: {profile.user_name}\n"
            f"Preferred Tools: {', '.join(profile.preferred_tools)}\n"
            f"Preferred Language: {profile.preferred_language}\n"
            f"Response Style: {profile.response_style}\n\n"
            "--- TASK CONTEXT ---\n"
            f"Current Project: {task_context.current_project}\n"
            f"Active Experiment: {task_context.active_experiment}\n"
            f"Goals: {', '.join(task_context.goals)}\n"
            f"Blockers: {', '.join(task_context.blockers)}\n"
            f"Next Steps: {', '.join(task_context.next_steps)}\n\n"
            f"{plausible_actions_section}"
            "--- FOLLOW-UP QUERY ---\n"
            f"{query}\n\n"
            "--- ASSISTANT RESPONSE ---\n"
            f"{response}\n\n"
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
            "Respond with ONLY a JSON object (no markdown fences, no explanation, no text before or after). "
            "Use exactly these keys:\n"
            '{"profile_usage_score": <int 1-5>, "task_usage_score": <int 1-5>, "integration_score": <int 1-5>, '
            '"profile_usage_reasoning": "<string>", "task_usage_reasoning": "<string>", "integration_reasoning": "<string>"}'
        )
        return [
            {
                "role": "system",
                "content": (
                    "You are an expert evaluator. You MUST respond with ONLY a valid JSON object. "
                    "No markdown code fences. No explanation text. No preamble. Just the raw JSON object. "
                    "The assistant had access to shared memories injected "
                    "by the kernel containing the user's profile and task "
                    "context. A concise response that demonstrates awareness "
                    "of these attributes is well-personalized, not generic."
                ),
            },
            {"role": "user", "content": user_content},
        ]

    def _build_judge_prompt_v2(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
        plausible_actions: list[str] | None = None,
    ) -> List[Dict[str, str]]:
        """Build the messages for the v2 DECOMPOSED rubric.

        Instead of asking for a single holistic 1-5 per dimension (v1), the v2
        rubric decomposes each dimension into five binary sub-criteria. The
        model marks each 1 (clearly & fully satisfied) or 0, and the dimension
        score is the SUM of its five criteria (0-5). This forces the model to
        justify a high score rather than defaulting to a 5.

        The five criteria per dimension are derived from the established v1
        rubric wording (see ``benchmarks/human_rating/rubric.py``, which treats
        the v1 judge prompt as canonical): each v1 "5" descriptor enumerates the
        specific attributes a top score requires, which decompose cleanly into
        binary checks. Still a SINGLE LLM call covering all three dimensions —
        matching v1's architecture and the documented token-cost tradeoff — not
        three separate calls.
        """
        # Build plausible actions section (only when provided and non-empty).
        # Mirrors v1 so the two prompts differ only in the rubric/contract.
        plausible_actions_section = ""
        if plausible_actions:
            actions_list = "\n".join(
                f"  {i}. {action}" for i, action in enumerate(plausible_actions, 1)
            )
            plausible_actions_section = (
                "--- PLAUSIBLE ACTIONS ---\n"
                "The developer had these pending options to choose from:\n"
                f"{actions_list}\n\n"
            )

        user_content = (
            "Evaluate the following AI assistant response.\n\n"
            "--- USER PROFILE ---\n"
            f"Name: {profile.user_name}\n"
            f"Preferred Tools: {', '.join(profile.preferred_tools)}\n"
            f"Preferred Language: {profile.preferred_language}\n"
            f"Response Style: {profile.response_style}\n\n"
            "--- TASK CONTEXT ---\n"
            f"Current Project: {task_context.current_project}\n"
            f"Active Experiment: {task_context.active_experiment}\n"
            f"Goals: {', '.join(task_context.goals)}\n"
            f"Blockers: {', '.join(task_context.blockers)}\n"
            f"Next Steps: {', '.join(task_context.next_steps)}\n\n"
            f"{plausible_actions_section}"
            "--- FOLLOW-UP QUERY ---\n"
            f"{query}\n\n"
            "--- ASSISTANT RESPONSE ---\n"
            f"{response}\n\n"
            "--- SCORING RUBRIC (DECOMPOSED) ---\n"
            "Each of the three dimensions below has FIVE binary criteria. "
            "Award 1 point per criterion only if it is clearly and fully "
            "satisfied by the response content, regardless of response length; "
            "otherwise award 0. Do not award a 5 by default; a 5 requires all "
            "five criteria to hold. The dimension score is the SUM of its five "
            "criteria (an integer 0-5).\n\n"
            "Profile Usage — criteria:\n"
            "  1. References the user's preferred tools by name.\n"
            "  2. References the user's preferred language.\n"
            "  3. Reflects the user's stated response style.\n"
            "  4. Uses these profile attributes correctly (no incorrect or "
            "invented attributes).\n"
            "  5. Ties at least one profile attribute directly into the "
            "recommendation (not merely restated).\n\n"
            "Task Usage — criteria:\n"
            "  1. References the current project.\n"
            "  2. References at least one stated goal.\n"
            "  3. References at least one stated blocker.\n"
            "  4. References at least one stated next step or the active "
            "experiment.\n"
            "  5. Uses this task context correctly and specifically (not vague "
            "or generic advice).\n\n"
            "Integration — criteria:\n"
            "  1. Draws on BOTH the profile and the task context (not just "
            "one).\n"
            "  2. Combines them within a single recommendation rather than "
            "addressing them separately.\n"
            "  3. The recommendation logically follows from the combined "
            "profile and task context.\n"
            "  4. The integration is seamless (the two sources reinforce one "
            "coherent recommendation).\n"
            "  5. The result is grounded and specific to THIS user and THIS "
            "task (not generic).\n\n"
            "For each dimension, mark every criterion 1 or 0, set score = the "
            "sum, and provide a one-sentence justification for EACH criterion "
            "you scored 0 (justification is required only for 0-scored "
            "criteria; you may omit it for criteria scored 1).\n\n"
            "Respond with ONLY a JSON object (no markdown fences, no "
            "explanation, no text before or after). Use exactly these three "
            "top-level keys — profile_usage, task_usage, integration — each an "
            "object of this shape:\n"
            '{"profile_usage": {"criteria": {"1": <0|1>, "2": <0|1>, '
            '"3": <0|1>, "4": <0|1>, "5": <0|1>}, "score": <int 0-5>, '
            '"justification": {"<criterion index>": "<one sentence>"}}, '
            '"task_usage": {"criteria": {"1": <0|1>, "2": <0|1>, "3": <0|1>, '
            '"4": <0|1>, "5": <0|1>}, "score": <int 0-5>, "justification": '
            '{"<criterion index>": "<one sentence>"}}, '
            '"integration": {"criteria": {"1": <0|1>, "2": <0|1>, "3": <0|1>, '
            '"4": <0|1>, "5": <0|1>}, "score": <int 0-5>, "justification": '
            '{"<criterion index>": "<one sentence>"}}}'
        )
        return [
            {
                "role": "system",
                "content": (
                    "You are an expert evaluator using a DECOMPOSED rubric. You "
                    "MUST respond with ONLY a valid JSON object. No markdown "
                    "code fences. No explanation text. No preamble. Just the "
                    "raw JSON object. The object has exactly three top-level "
                    "keys — profile_usage, task_usage, integration — each an "
                    'object with "criteria" (five keys "1".."5", each 0 or 1), '
                    '"score" (the integer sum of those five criteria, 0-5), and '
                    '"justification" (a one-sentence reason for each criterion '
                    "you scored 0). Award 1 per criterion only when it is "
                    "clearly and fully satisfied; never award a 5 by default. "
                    "The assistant had access to shared memories injected by "
                    "the kernel containing the user's profile and task context; "
                    "a concise response that demonstrates awareness of these "
                    "attributes is well-personalized, not generic."
                ),
            },
            {"role": "user", "content": user_content},
        ]

    def _build_response_format(self) -> Dict[str, Any]:
        """Build the ``response_format`` json_schema for the active rubric.

        v1 keeps the flat 6-key schema (three ``*_score`` integers + three
        ``*_reasoning`` strings). v2 uses a nested schema: three dimension keys,
        each an object with a ``criteria`` map ("1".."5" → 0|1), an integer
        ``score`` (0-5), and a ``justification`` map. ``justification`` is not in
        ``required`` because the rubric only asks for justifications on
        0-scored criteria, so a perfect dimension may legitimately omit it.
        """
        if self.rubric_version == "v2":
            dimension_schema = {
                "type": "object",
                "properties": {
                    "criteria": {
                        "type": "object",
                        "properties": {
                            "1": {"type": "integer"},
                            "2": {"type": "integer"},
                            "3": {"type": "integer"},
                            "4": {"type": "integer"},
                            "5": {"type": "integer"},
                        },
                        "required": ["1", "2", "3", "4", "5"],
                        "additionalProperties": False,
                    },
                    "score": {"type": "integer"},
                    "justification": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["criteria", "score"],
                "additionalProperties": False,
            }
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "judge_scores_v2",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "profile_usage": dimension_schema,
                            "task_usage": dimension_schema,
                            "integration": dimension_schema,
                        },
                        "required": [
                            "profile_usage",
                            "task_usage",
                            "integration",
                        ],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            }

        return {
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

    def evaluate(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
        plausible_actions: list[str] | None = None,
    ) -> JudgeScores:
        """Score an assistant response on profile usage, task usage, and integration."""
        messages = self._build_judge_prompt(
            query, response, profile, task_context, plausible_actions
        )

        response_format: Dict[str, Any] = self._build_response_format()

        # Per-call judge token usage: the kernel emits it as a top-level
        # sibling of "response" in the /query body (NOT nested under
        # "response"), exactly like the assistant path. Capture it here from
        # whichever call actually produced the scored response (primary or
        # fallback) so it can be threaded onto the returned JudgeScores.
        judge_token_usage: Any = None
        try:
            llm_response = llm_chat_with_json_output(
                agent_name=self.agent_name,
                messages=messages,
                base_url=self.kernel_url,
                response_format=response_format,
                llms=self.llms,
            )
            judge_token_usage = llm_response.get("token_usage")

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
                # Prefer the fallback call's usage since it produced the
                # response we actually parse. Fall back to the primary call's
                # usage only if the fallback omitted it.
                judge_token_usage = llm_response.get("token_usage") or judge_token_usage
                raw = llm_response["response"]["response_message"]
                if raw is None:
                    logger.warning(
                        "Judge LLM returned None response_message on fallback — "
                        "model may be unavailable. "
                        "llms=%s kernel=%s",
                        self.llms,
                        self.kernel_url,
                    )
                    return JudgeScores(token_usage=judge_token_usage)
            # Try to parse as JSON; if it fails, try to extract JSON from text
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    # Try to extract JSON object from free-form text
                    data = _extract_json_from_text(raw)
                    if data is None:
                        logger.warning("Judge LLM returned non-JSON text: %s", raw[:200])
                        return JudgeScores(token_usage=judge_token_usage)
            else:
                data = raw
            if not isinstance(data, dict):
                logger.warning("Judge LLM returned non-dict data: %r", data)
                return JudgeScores(token_usage=judge_token_usage)
            logger.debug("Judge parsed data before normalization: %s", data)

            # TODO(subtask 4): This parse path only understands the v1 FLAT
            # shape ({profile_usage_score, task_usage_score, integration_score,
            # *_reasoning}). When self.rubric_version == "v2", `data` is the
            # NESTED shape ({profile_usage: {criteria, score, justification},
            # ...}) produced by _build_judge_prompt_v2 / _build_response_format,
            # and the flat-key extraction below will find no *_score keys and
            # return an empty JudgeScores. Parsing/summing the v2 criteria into
            # scores (and flipping rubric_version to "v2") is subtask 4. Until
            # then, evaluate() under rubric_version="v2" is expected to
            # mis-parse — this is intentional and not silently left implicit.

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
                return JudgeScores(token_usage=judge_token_usage)

            scores = JudgeScores(
                profile_usage_score=_clamp_score(pu, "profile_usage_score"),
                task_usage_score=_clamp_score(tu, "task_usage_score"),
                integration_score=_clamp_score(ig, "integration_score"),
                # Wired through as the constant "v1" for now. Subtask 3
                # introduces the v2 prompt/parsing path and flips this.
                rubric_version="v1",
                profile_usage_reasoning=data.get("profile_usage_reasoning"),
                task_usage_reasoning=data.get("task_usage_reasoning"),
                integration_reasoning=data.get("integration_reasoning"),
                token_usage=judge_token_usage,
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


class HybridJudge:
    """Combines deterministic keyword matching with LLM-based scoring.

    The keyword scores provide a reliable signal for whether the response
    references profile/task attributes. The LLM scores assess quality and
    integration. The final score is the average of both, rounded.
    """

    def __init__(
        self,
        agent_name: str = "eval_judge",
        llms: list | None = None,
        rubric_version: str = "v1",
    ):
        self.llm_judge = LLMJudge(
            agent_name=agent_name, llms=llms, rubric_version=rubric_version
        )

    def evaluate(
        self,
        query: str,
        response: str,
        profile: SyntheticProfile,
        task_context: SyntheticTaskContext,
        plausible_actions: list[str] | None = None,
    ) -> JudgeScores:
        """Score using both keyword matching and LLM judge."""
        # Keyword-based scores
        keywords = _extract_keywords(profile, task_context)
        kw_profile = keyword_score(response, keywords["profile"])
        kw_task = keyword_score(response, keywords["task"])
        kw_integration = min(kw_profile, kw_task)  # both must be present

        # LLM-based scores
        llm_scores = self.llm_judge.evaluate(
            query, response, profile, task_context, plausible_actions
        )

        # Combine: average keyword and LLM scores
        def _avg(kw: int, llm_val: int | None) -> int:
            if llm_val is None:
                return kw
            return max(1, min(5, round((kw + llm_val) / 2)))

        return JudgeScores(
            profile_usage_score=_avg(kw_profile, llm_scores.profile_usage_score),
            task_usage_score=_avg(kw_task, llm_scores.task_usage_score),
            integration_score=_avg(kw_integration, llm_scores.integration_score),
            # Carry the rubric version from the LLM judge's result rather than
            # hardcoding it a second time — single source of truth.
            rubric_version=llm_scores.rubric_version,
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
            # Pass through the LLM judge's per-call token usage unchanged; the
            # keyword component makes no LLM call and adds no tokens.
            token_usage=llm_scores.token_usage,
        )
