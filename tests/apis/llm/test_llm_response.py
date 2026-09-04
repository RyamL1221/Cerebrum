"""Unit tests for the LLMResponse Pydantic model.

Covers the token_usage field added to LLMResponse in cerebrum/llm/apis.py.
These tests are pure model/serialization tests — they do NOT require a
running AIOS kernel — and lock in the three payload shapes the kernel can
produce:

  1. token_usage absent entirely (today's live kernel output) -> None.
  2. token_usage present as a fully-populated dict -> round-trips exactly.
  3. token_usage present with partial None values (kernel-side
     getattr(..., None) behavior) -> validates cleanly and preserves None.

Run directly:
    python tests/apis/llm/test_llm_response.py
"""

import sys
import unittest

sys.path.insert(0, ".")

from cerebrum.llm.apis import LLMResponse


class TestLLMResponseTokenUsage(unittest.TestCase):
    """Validation and round-trip coverage for LLMResponse.token_usage."""

    def _base_payload(self):
        """A minimal LLM response payload mirroring the kernel body shape."""
        return {
            "response_class": "llm",
            "response_message": "Python is a high-level programming language.",
            "finished": True,
            "status_code": 200,
        }

    def test_token_usage_absent_defaults_to_none(self):
        """A payload with no token_usage key validates with token_usage=None."""
        response = LLMResponse.model_validate(self._base_payload())
        self.assertIsNone(response.token_usage)

    def test_token_usage_populated_round_trips(self):
        """A well-formed token_usage dict validates and round-trips exactly."""
        usage = {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}
        payload = dict(self._base_payload(), token_usage=usage)

        response = LLMResponse.model_validate(payload)
        self.assertEqual(response.token_usage, usage)
        self.assertTrue(all(isinstance(v, int) for v in response.token_usage.values()))

        # Round-trip: model_dump -> re-validate yields the same field value.
        redumped = LLMResponse.model_validate(response.model_dump())
        self.assertEqual(redumped.token_usage, usage)

    def test_token_usage_partial_none_validates(self):
        """A partial-None token_usage dict validates and preserves the Nones."""
        usage = {"prompt_tokens": 120, "completion_tokens": None, "total_tokens": None}
        payload = dict(self._base_payload(), token_usage=usage)

        response = LLMResponse.model_validate(payload)
        self.assertEqual(response.token_usage, usage)

        # Round-trip preserves the partial-None shape.
        redumped = LLMResponse.model_validate(response.model_dump())
        self.assertEqual(redumped.token_usage, usage)


if __name__ == "__main__":
    unittest.main()
