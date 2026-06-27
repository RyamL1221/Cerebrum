"""Regression tests: mem0_default uses kernel memory APIs.

Verifies that _run_mem0_default:
1. Calls create_memory twice (profile + task context) with correct metadata
2. Calls search_memories with user_id=method_user_id
3. Manually prepends retrieved memories into the assistant prompt
4. Handles write/search failures gracefully without crashing

No running kernel, Ollama, ChromaDB, or real LLM required.
"""

import sys
sys.path.insert(0, ".")

from unittest.mock import patch, MagicMock, call

from benchmarks.shared_memory.pipeline import MethodPipeline
from benchmarks.shared_memory.models import SyntheticTrialData, SyntheticProfile, SyntheticTaskContext


def _make_trial_data(user_id="test_user_abc__mem0_default"):
    """Build minimal SyntheticTrialData for testing."""
    return SyntheticTrialData(
        profile=SyntheticProfile(
            user_name="Test User",
            preferred_tools=["VS Code", "Git"],
            preferred_language="Python",
            response_style="concise",
        ),
        task_context=SyntheticTaskContext(
            current_project="Test Project",
            active_experiment="Testing memory retrieval",
            goals=["Ship feature", "Write tests"],
            blockers=["Flaky CI"],
            next_steps=["Fix CI", "Deploy"],
        ),
        follow_up_query="What should I focus on next?",
        user_id="test_user_abc",
    )


def test_mem0_default_calls_create_memory_twice_with_correct_metadata():
    """mem0_default writes profile and task memories via kernel create_memory."""
    trial_data = _make_trial_data()
    method_user_id = f"{trial_data.user_id}__mem0_default"

    create_calls = []
    
    def mock_create_memory(agent_name, content, metadata=None, base_url=None):
        create_calls.append({"agent_name": agent_name, "content": content, "metadata": metadata})
        return {"response": {"memory_id": f"mem_{len(create_calls)}", "success": True}}

    def mock_search_memories(agent_name, query, k=5, base_url=None, *, user_id=None, sharing_policy=None):
        return {"response": {"search_results": []}}

    def mock_assistant_run(self, task_input):
        return {"agent_name": "assistant_agent", "result": "mocked", "rounds": 1}

    with patch("benchmarks.shared_memory.pipeline.create_memory", side_effect=mock_create_memory):
        with patch("benchmarks.shared_memory.pipeline.search_memories", side_effect=mock_search_memories):
            with patch("cerebrum.example.agents.assistant_agent.agent.llm_chat", return_value={"response": {"response_message": "mocked"}}):
                pipeline = MethodPipeline(method="mem0_default", assistant_llms=[{"name": "gpt-4o", "backend": "azure"}])
                result = pipeline.run_trial(trial_data)

    # ASSERT: create_memory called twice
    assert len(create_calls) == 2, f"Expected 2 create_memory calls, got {len(create_calls)}"

    # ASSERT: First call is profile
    profile_call = create_calls[0]
    assert profile_call["agent_name"] == "mem0_default_agent"
    assert profile_call["metadata"]["user_id"] == method_user_id
    assert profile_call["metadata"]["owner_agent"] == "mem0_default_agent"
    assert profile_call["metadata"]["memory_type"] == "profile"
    assert profile_call["metadata"]["sharing_policy"] == "shared"
    assert "Test User" in profile_call["content"]

    # ASSERT: Second call is task_context
    task_call = create_calls[1]
    assert task_call["agent_name"] == "mem0_default_agent"
    assert task_call["metadata"]["user_id"] == method_user_id
    assert task_call["metadata"]["owner_agent"] == "mem0_default_agent"
    assert task_call["metadata"]["memory_type"] == "task_context"
    assert task_call["metadata"]["sharing_policy"] == "shared"
    assert "Test Project" in task_call["content"]


def test_mem0_default_calls_search_memories_with_user_id():
    """mem0_default retrieves memories using search_memories with explicit user_id."""
    trial_data = _make_trial_data()
    method_user_id = f"{trial_data.user_id}__mem0_default"

    search_calls = []

    def mock_create_memory(agent_name, content, metadata=None, base_url=None):
        return {"response": {"memory_id": "mem_1", "success": True}}

    def mock_search_memories(agent_name, query, k=5, base_url=None, *, user_id=None, sharing_policy=None):
        search_calls.append({
            "agent_name": agent_name,
            "query": query,
            "k": k,
            "user_id": user_id,
        })
        return {
            "response": {
                "search_results": [
                    {"memory": "User prefers concise technical answers."},
                    {"content": "User is working on Test Project."},
                ]
            }
        }

    with patch("benchmarks.shared_memory.pipeline.create_memory", side_effect=mock_create_memory):
        with patch("benchmarks.shared_memory.pipeline.search_memories", side_effect=mock_search_memories):
            with patch("cerebrum.example.agents.assistant_agent.agent.llm_chat", return_value={"response": {"response_message": "mocked"}}):
                pipeline = MethodPipeline(method="mem0_default", assistant_llms=[{"name": "gpt-4o", "backend": "azure"}])
                result = pipeline.run_trial(trial_data)

    # ASSERT: search_memories called once
    assert len(search_calls) == 1, f"Expected 1 search call, got {len(search_calls)}"

    sc = search_calls[0]
    assert sc["agent_name"] == "mem0_default_agent"
    assert sc["query"] == trial_data.follow_up_query
    assert sc["k"] == 5
    assert sc["user_id"] == method_user_id

    # ASSERT: retrieved_context_count reflects search results
    assert result.retrieved_context_count == 2


def test_mem0_default_prepends_memories_to_prompt():
    """mem0_default manually prepends retrieved memories into the assistant prompt."""
    trial_data = _make_trial_data()

    captured_prompts = []

    def mock_create_memory(agent_name, content, metadata=None, base_url=None):
        return {"response": {"memory_id": "mem_1", "success": True}}

    def mock_search_memories(agent_name, query, k=5, base_url=None, *, user_id=None, sharing_policy=None):
        return {
            "response": {
                "search_results": [
                    {"memory": "User prefers Python and VS Code."},
                    {"content": "Current project is Test Project with flaky CI."},
                ]
            }
        }

    def mock_llm_chat(agent_name, messages, base_url=None, llms=None, user_id=None):
        # Capture what the assistant receives
        for msg in messages:
            if msg.get("role") == "user":
                captured_prompts.append(msg["content"])
        return {"response": {"response_message": "personalized answer"}}

    with patch("benchmarks.shared_memory.pipeline.create_memory", side_effect=mock_create_memory):
        with patch("benchmarks.shared_memory.pipeline.search_memories", side_effect=mock_search_memories):
            with patch("cerebrum.example.agents.assistant_agent.agent.llm_chat", side_effect=mock_llm_chat):
                pipeline = MethodPipeline(method="mem0_default", assistant_llms=[{"name": "gpt-4o", "backend": "azure"}])
                result = pipeline.run_trial(trial_data)

    # ASSERT: The prompt includes the retrieved memories section
    assert len(captured_prompts) >= 1
    prompt = captured_prompts[-1]
    assert "--- RETRIEVED MEMORIES ---" in prompt
    assert "User prefers Python and VS Code." in prompt
    assert "Current project is Test Project with flaky CI." in prompt
    assert "--- QUERY ---" in prompt
    assert trial_data.follow_up_query in prompt


def test_mem0_default_handles_write_failure_gracefully():
    """mem0_default does not crash if create_memory raises an exception."""
    trial_data = _make_trial_data()

    def mock_create_memory(agent_name, content, metadata=None, base_url=None):
        raise ConnectionError("Kernel unavailable")

    def mock_search_memories(agent_name, query, k=5, base_url=None, *, user_id=None, sharing_policy=None):
        return {"response": {"search_results": []}}

    with patch("benchmarks.shared_memory.pipeline.create_memory", side_effect=mock_create_memory):
        with patch("benchmarks.shared_memory.pipeline.search_memories", side_effect=mock_search_memories):
            with patch("cerebrum.example.agents.assistant_agent.agent.llm_chat", return_value={"response": {"response_message": "mocked"}}):
                pipeline = MethodPipeline(method="mem0_default", assistant_llms=[{"name": "gpt-4o", "backend": "azure"}])
                result = pipeline.run_trial(trial_data)

    # ASSERT: Trial did not crash
    assert result.method == "mem0_default"
    assert result.assistant_response is not None
    assert result.retrieved_context_count == 0


def test_mem0_default_handles_search_failure_gracefully():
    """mem0_default does not crash if search_memories raises an exception."""
    trial_data = _make_trial_data()

    def mock_create_memory(agent_name, content, metadata=None, base_url=None):
        return {"response": {"memory_id": "mem_1", "success": True}}

    def mock_search_memories(agent_name, query, k=5, base_url=None, *, user_id=None, sharing_policy=None):
        raise ConnectionError("Kernel search unavailable")

    with patch("benchmarks.shared_memory.pipeline.create_memory", side_effect=mock_create_memory):
        with patch("benchmarks.shared_memory.pipeline.search_memories", side_effect=mock_search_memories):
            with patch("cerebrum.example.agents.assistant_agent.agent.llm_chat", return_value={"response": {"response_message": "mocked"}}):
                pipeline = MethodPipeline(method="mem0_default", assistant_llms=[{"name": "gpt-4o", "backend": "azure"}])
                result = pipeline.run_trial(trial_data)

    # ASSERT: Trial did not crash
    assert result.method == "mem0_default"
    assert result.assistant_response is not None
    assert result.retrieved_context_count == 0


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

results_log = []


def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results_log.append((name, status, detail))
    print(f"  [{status}] {name}")
    if detail:
        print(f"    Detail: {detail}")


def run_all():
    print("=" * 70)
    print("mem0_default Kernel Memory — Regression Tests")
    print("Confirms mem0_default uses kernel APIs, not local Mem0 client.")
    print("=" * 70)

    print("\n--- create_memory called twice with correct metadata ---")
    try:
        test_mem0_default_calls_create_memory_twice_with_correct_metadata()
        record("create_memory_calls", True)
    except Exception as e:
        record("create_memory_calls", False, str(e)[:200])

    print("\n--- search_memories called with user_id ---")
    try:
        test_mem0_default_calls_search_memories_with_user_id()
        record("search_memories_user_id", True)
    except Exception as e:
        record("search_memories_user_id", False, str(e)[:200])

    print("\n--- Retrieved memories prepended to prompt ---")
    try:
        test_mem0_default_prepends_memories_to_prompt()
        record("memories_prepended_to_prompt", True)
    except Exception as e:
        record("memories_prepended_to_prompt", False, str(e)[:200])

    print("\n--- Write failure handled gracefully ---")
    try:
        test_mem0_default_handles_write_failure_gracefully()
        record("write_failure_graceful", True)
    except Exception as e:
        record("write_failure_graceful", False, str(e)[:200])

    print("\n--- Search failure handled gracefully ---")
    try:
        test_mem0_default_handles_search_failure_gracefully()
        record("search_failure_graceful", True)
    except Exception as e:
        record("search_failure_graceful", False, str(e)[:200])

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, s, _ in results_log if s == "PASS")
    failed = sum(1 for _, s, _ in results_log if s == "FAIL")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {len(results_log)}")

    if failed > 0:
        print(f"\n{failed} test(s) FAILED.")
    else:
        print("\nAll tests PASSED.")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
