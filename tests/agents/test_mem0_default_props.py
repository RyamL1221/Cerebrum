"""Property-based tests for the mem0_default pipeline path using Hypothesis.

Feature: personalization-baselines
Property 7: mem0_default retrieved_context_count matches search result count
Property 8: mem0_default error resilience
"""

import sys
sys.path.insert(0, ".")

from unittest.mock import patch, MagicMock

from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import (
    text,
    lists,
    integers,
    composite,
    from_regex,
    sampled_from,
    just,
)

from benchmarks.shared_memory.pipeline import MethodPipeline
from benchmarks.shared_memory.models import (
    SyntheticProfile,
    SyntheticTaskContext,
    SyntheticTrialData,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty printable text (avoid empty strings for names/fields)
_nonempty_text = text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-",
    min_size=1,
    max_size=30,
)

_nonempty_list = lists(_nonempty_text, min_size=1, max_size=5)


@composite
def synthetic_profile_strategy(draw):
    """Generate a random SyntheticProfile."""
    return SyntheticProfile(
        user_name=draw(_nonempty_text),
        preferred_tools=draw(_nonempty_list),
        preferred_language=draw(_nonempty_text),
        response_style=draw(_nonempty_text),
    )


@composite
def synthetic_task_context_strategy(draw):
    """Generate a random SyntheticTaskContext."""
    return SyntheticTaskContext(
        current_project=draw(_nonempty_text),
        active_experiment=draw(_nonempty_text),
        goals=draw(_nonempty_list),
        blockers=draw(_nonempty_list),
        next_steps=draw(_nonempty_list),
    )


@composite
def synthetic_trial_data_strategy(draw):
    """Generate a random SyntheticTrialData."""
    return SyntheticTrialData(
        profile=draw(synthetic_profile_strategy()),
        task_context=draw(synthetic_task_context_strategy()),
        follow_up_query=draw(_nonempty_text),
        plausible_actions=draw(lists(_nonempty_text, min_size=0, max_size=3)),
        user_id=draw(from_regex(r"[a-z][a-z0-9_]{0,19}", fullmatch=True)),
    )


@composite
def mem0_search_results_strategy(draw):
    """Generate a random list of Mem0 search result dicts (each with a 'memory' key)."""
    count = draw(integers(min_value=0, max_value=10))
    results = []
    for _ in range(count):
        results.append({"memory": draw(_nonempty_text)})
    return results


# A selection of exception types to test error resilience
_exception_types = sampled_from([
    RuntimeError,
    ValueError,
    ConnectionError,
    TimeoutError,
    OSError,
    Exception,
])


# ---------------------------------------------------------------------------
# Property 7: mem0_default retrieved_context_count matches search result count
# ---------------------------------------------------------------------------

class TestMem0DefaultCountConsistency:
    """Feature: personalization-baselines, Property 7: mem0_default retrieved_context_count matches search result count

    **Validates: Requirements 5.7**
    """

    @given(
        trial_data=synthetic_trial_data_strategy(),
        search_results=mem0_search_results_strategy(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_retrieved_context_count_matches_search_result_count(
        self, trial_data, search_results
    ):
        """For any Mem0 search result list (including empty), retrieved_context_count
        must equal len(search_results).

        Mocks Memory.add (no-op) and Memory.search (returns the generated list),
        then verifies retrieved_context_count == len(search_results).
        """
        # Feature: personalization-baselines, Property 7: mem0_default retrieved_context_count matches search result count
        pipeline = MethodPipeline(method="mem0_default")

        mock_memory = MagicMock()
        mock_memory.add.return_value = None
        mock_memory.search.return_value = search_results

        mock_assistant_result = {
            "agent_name": "assistant_agent",
            "result": "mocked response",
            "rounds": 1,
        }

        with patch("benchmarks.shared_memory.pipeline.AssistantAgent.run",
                   return_value=mock_assistant_result), \
             patch("mem0.Memory", return_value=mock_memory):
            method_user_id = f"{trial_data.user_id}__mem0_default"
            result = pipeline._run_mem0_default(trial_data, method_user_id)

        assert result.retrieved_context_count == len(search_results), (
            f"Expected retrieved_context_count={len(search_results)}, "
            f"got {result.retrieved_context_count}"
        )

    @given(trial_data=synthetic_trial_data_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_empty_search_results_gives_zero_count(self, trial_data):
        """When Mem0 search returns an empty list, retrieved_context_count must be 0."""
        # Feature: personalization-baselines, Property 7: mem0_default retrieved_context_count matches search result count
        pipeline = MethodPipeline(method="mem0_default")

        mock_memory = MagicMock()
        mock_memory.add.return_value = None
        mock_memory.search.return_value = []

        mock_assistant_result = {
            "agent_name": "assistant_agent",
            "result": "mocked response",
            "rounds": 1,
        }

        with patch("benchmarks.shared_memory.pipeline.AssistantAgent.run",
                   return_value=mock_assistant_result), \
             patch("mem0.Memory", return_value=mock_memory):
            method_user_id = f"{trial_data.user_id}__mem0_default"
            result = pipeline._run_mem0_default(trial_data, method_user_id)

        assert result.retrieved_context_count == 0, (
            f"Expected retrieved_context_count=0 for empty search results, "
            f"got {result.retrieved_context_count}"
        )

    @given(trial_data=synthetic_trial_data_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_method_is_mem0_default(self, trial_data):
        """For any SyntheticTrialData, _run_mem0_default must set method='mem0_default'."""
        # Feature: personalization-baselines, Property 7: mem0_default retrieved_context_count matches search result count
        pipeline = MethodPipeline(method="mem0_default")

        mock_memory = MagicMock()
        mock_memory.add.return_value = None
        mock_memory.search.return_value = []

        mock_assistant_result = {
            "agent_name": "assistant_agent",
            "result": "mocked response",
            "rounds": 1,
        }

        with patch("benchmarks.shared_memory.pipeline.AssistantAgent.run",
                   return_value=mock_assistant_result), \
             patch("mem0.Memory", return_value=mock_memory):
            method_user_id = f"{trial_data.user_id}__mem0_default"
            result = pipeline._run_mem0_default(trial_data, method_user_id)

        assert result.method == "mem0_default", (
            f"Expected method='mem0_default', got {result.method!r}"
        )


# ---------------------------------------------------------------------------
# Property 8: mem0_default error resilience
# ---------------------------------------------------------------------------

class TestMem0DefaultErrorResilience:
    """Feature: personalization-baselines, Property 8: mem0_default error resilience

    **Validates: Requirements 5.8**
    """

    @given(
        trial_data=synthetic_trial_data_strategy(),
        exc_type=_exception_types,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_add_exception_sets_zero_count_and_returns_result(
        self, trial_data, exc_type
    ):
        """When Mem0 add raises any exception, retrieved_context_count must be 0
        and the pipeline must return a PipelineResult (not raise).

        Mocks Memory.add to raise the given exception type, verifies that
        retrieved_context_count == 0 and a PipelineResult is returned.
        """
        # Feature: personalization-baselines, Property 8: mem0_default error resilience
        pipeline = MethodPipeline(method="mem0_default")

        mock_memory = MagicMock()
        mock_memory.add.side_effect = exc_type("simulated add failure")

        mock_assistant_result = {
            "agent_name": "assistant_agent",
            "result": "mocked response",
            "rounds": 1,
        }

        with patch("benchmarks.shared_memory.pipeline.AssistantAgent.run",
                   return_value=mock_assistant_result), \
             patch("mem0.Memory", return_value=mock_memory):
            method_user_id = f"{trial_data.user_id}__mem0_default"
            # Must not raise
            result = pipeline._run_mem0_default(trial_data, method_user_id)

        assert result.retrieved_context_count == 0, (
            f"Expected retrieved_context_count=0 after add exception, "
            f"got {result.retrieved_context_count}"
        )
        assert result.method == "mem0_default", (
            f"Expected method='mem0_default', got {result.method!r}"
        )

    @given(
        trial_data=synthetic_trial_data_strategy(),
        exc_type=_exception_types,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_search_exception_sets_zero_count_and_returns_result(
        self, trial_data, exc_type
    ):
        """When Mem0 search raises any exception, retrieved_context_count must be 0
        and the pipeline must return a PipelineResult (not raise).

        Mocks Memory.add (no-op) and Memory.search to raise the given exception
        type, verifies that retrieved_context_count == 0 and a PipelineResult
        is returned.
        """
        # Feature: personalization-baselines, Property 8: mem0_default error resilience
        pipeline = MethodPipeline(method="mem0_default")

        mock_memory = MagicMock()
        mock_memory.add.return_value = None
        mock_memory.search.side_effect = exc_type("simulated search failure")

        mock_assistant_result = {
            "agent_name": "assistant_agent",
            "result": "mocked response",
            "rounds": 1,
        }

        with patch("benchmarks.shared_memory.pipeline.AssistantAgent.run",
                   return_value=mock_assistant_result), \
             patch("mem0.Memory", return_value=mock_memory):
            method_user_id = f"{trial_data.user_id}__mem0_default"
            # Must not raise
            result = pipeline._run_mem0_default(trial_data, method_user_id)

        assert result.retrieved_context_count == 0, (
            f"Expected retrieved_context_count=0 after search exception, "
            f"got {result.retrieved_context_count}"
        )
        assert result.method == "mem0_default", (
            f"Expected method='mem0_default', got {result.method!r}"
        )

    @given(
        trial_data=synthetic_trial_data_strategy(),
        exc_type=_exception_types,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_exception_does_not_prevent_assistant_run(
        self, trial_data, exc_type
    ):
        """When Mem0 raises any exception, AssistantAgent.run must still be called
        (the trial is not aborted by the Mem0 error alone).
        """
        # Feature: personalization-baselines, Property 8: mem0_default error resilience
        pipeline = MethodPipeline(method="mem0_default")

        mock_memory = MagicMock()
        mock_memory.add.side_effect = exc_type("simulated failure")

        assistant_call_count = []

        def counting_run(self_agent, task_input):
            assistant_call_count.append(task_input)
            return {"agent_name": "assistant_agent", "result": "ok", "rounds": 1}

        with patch("benchmarks.shared_memory.pipeline.AssistantAgent.run",
                   counting_run), \
             patch("mem0.Memory", return_value=mock_memory):
            method_user_id = f"{trial_data.user_id}__mem0_default"
            pipeline._run_mem0_default(trial_data, method_user_id)

        assert len(assistant_call_count) == 1, (
            "AssistantAgent.run must be called exactly once even when Mem0 raises"
        )


if __name__ == "__main__":
    t7 = TestMem0DefaultCountConsistency()
    print("Running Property 7: mem0_default retrieved_context_count matches search result count...")
    t7.test_retrieved_context_count_matches_search_result_count()
    print("PASSED: retrieved_context_count == len(search_results) for all inputs")
    t7.test_empty_search_results_gives_zero_count()
    print("PASSED: retrieved_context_count == 0 for empty search results")
    t7.test_method_is_mem0_default()
    print("PASSED: method == 'mem0_default' for all inputs")

    t8 = TestMem0DefaultErrorResilience()
    print("\nRunning Property 8: mem0_default error resilience...")
    t8.test_add_exception_sets_zero_count_and_returns_result()
    print("PASSED: add exception -> retrieved_context_count == 0, result returned")
    t8.test_search_exception_sets_zero_count_and_returns_result()
    print("PASSED: search exception -> retrieved_context_count == 0, result returned")
    t8.test_exception_does_not_prevent_assistant_run()
    print("PASSED: AssistantAgent.run called even when Mem0 raises")
