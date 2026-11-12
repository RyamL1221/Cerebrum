"""Per-trial cost (NeurIPS Subtask 7): the price table, the summary
columns, and the token and latency fields every condition records."""

import json
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.shared_memory import cost, run_evaluation
from benchmarks.shared_memory.models import TokenUsage, TrialResult
from benchmarks.shared_memory.pipeline import MethodPipeline, cost_fields
from cerebrum.utils import usage

from tests.agents import test_native_conditions as native

KERNEL_USAGE = {"prompt_tokens": 1000, "completion_tokens": 200,
                "total_tokens": 1200}
GPT4O = [{"name": "gpt-4o", "backend": "azure"}]


def test_price_table_loads_and_prices_a_known_usage():
    prices = cost.load_prices()
    assert prices["as_of"]
    known = {"calls": 1, "prompt_tokens": 1_000_000,
             "completion_tokens": 100_000, "models": ["azure/gpt-4o"]}
    # 1M input at 2.50 + 0.1M output at 10.00 per 1M.
    assert cost.price_usage(known, prices) == pytest.approx(3.50)
    local = {**known, "models": ["ollama/qwen2.5:7b"]}
    assert cost.price_usage(local, prices) == 0.0
    assert cost.price_usage({"calls": 0}, prices) == 0.0
    assert cost.price_usage({**known, "models": ["unknown/m"]}, prices) is None


def test_price_table_rejects_a_missing_price(tmp_path):
    path = tmp_path / "prices.yaml"
    path.write_text('as_of: "x"\nsource: s\nmodels:\n  m: {input: 1}\n')
    with pytest.raises(ValueError, match="m.output"):
        cost.load_prices(path)


def trial(scores, assistant=1200, backend=0, failed=False):
    def tokens(total, model="azure/gpt-4o"):
        return TokenUsage(calls=1 if total else 0, prompt_tokens=total,
                          total_tokens=total,
                          models=[model] if total else []).model_dump()
    return {
        "failed": failed,
        "profile_usage_score": scores[0], "task_usage_score": scores[1],
        "integration_score": scores[2], "latency_seconds": 2.0,
        "token_usage": tokens(assistant), "writer_tokens": tokens(400),
        "backend_llm_tokens": tokens(backend),
        "embedding_tokens": tokens(30, "ollama/nomic-embed-text"),
        "latency_breakdown": {"kernel_overhead_ms": 40.0, "llm_ms": 1900.0},
    }


def test_cell_summary_has_the_cost_split_and_tokens_per_quality():
    prices = cost.load_prices()
    row = cost.cell_summary(
        [trial((5, 5, 5), backend=3000), trial((3, 3, 3), backend=1000),
         trial((1, 1, 1), failed=True)],
        prices,
    )
    assert row["n"] == 2
    assert row["backend_total_tokens"] == 2000
    assert row["total_tokens"] == 1200 + 400 + 2000 + 30
    # Mean total tokens over the mean of the three score means (4.0).
    assert row["tokens_per_quality"] == pytest.approx(3630 / 4.0)
    assert row["backend_usd"] == pytest.approx(2000 * 2.50 / 1e6)
    assert row["embedding_usd"] == 0.0
    assert row["total_usd"] == pytest.approx(
        row["assistant_usd"] + row["writers_usd"] + row["backend_usd"]
    )
    assert row["kernel_overhead_ms"] == 40.0
    assert row["latency_ms"] == 2000.0


def test_cost_fields_sum_writers_and_read_the_latency_breakdown():
    assistant = {
        "token_usage": KERNEL_USAGE,
        "injection_diagnostics": {
            "barrier_wait_ms": 1.0, "search_ms": 30.0, "select_ms": 1.0,
            "format_ms": 2.0, "kernel_overhead_ms": 34.0,
            "llm_ms": 1500.0, "schedule_wait_ms": 300.0,
        },
    }
    writers = [{"token_usage": KERNEL_USAGE}, {"token_usage": None},
               {"result": "no reply"}]
    fields = cost_fields(assistant, writers, GPT4O)
    assert fields["token_usage"].total_tokens == 1200
    assert fields["token_usage"].models == ["azure/gpt-4o"]
    # Two calls replied (one reported no usage); one never reached the
    # kernel.
    assert fields["writer_tokens"].calls == 2
    assert fields["writer_tokens"].total_tokens == 1200
    latency = fields["latency_breakdown"]
    assert latency.kernel_overhead_ms == 34.0 and latency.llm_ms == 1500.0


def test_cost_fields_without_diagnostics_use_the_llm_timing():
    fields = cost_fields(
        {"token_usage": KERNEL_USAGE,
         "llm_timing": {"llm_ms": 900.0, "schedule_wait_ms": 50.0}},
        [], GPT4O,
    )
    assert fields["latency_breakdown"].llm_ms == 900.0
    assert fields["latency_breakdown"].kernel_overhead_ms is None
    assert fields["writer_tokens"].calls == 0


@pytest.fixture
def native_harness(harness):
    """The native harness, with a Mem0 whose add makes one counted LLM
    call (as the LiteLLM callback records it) and an llm_chat that
    reports the kernel's usage and timing."""
    memory_calls, chat = harness
    chat.return_value = {
        "response": {"response_message": "ok"},
        "token_usage": KERNEL_USAGE,
        "llm_timing": {"llm_ms": 700.0, "schedule_wait_ms": 90.0},
    }
    real_add = native.FakeMem0.add

    def counted_add(self, messages, user_id, agent_id, metadata, infer):
        usage.ACCUMULATOR.record(
            usage.current_tag(), usage.BACKEND_EXTRACTION,
            "azure/gpt-4o", 3000, 100,
        )
        return real_add(self, messages, user_id, agent_id, metadata, infer)

    with patch.object(native.FakeMem0, "add", counted_add):
        yield chat


harness = native.harness


@pytest.mark.parametrize("method", ["native_mem0", "native_inhouse"])
def test_native_trial_records_every_cost_field(native_harness, method):
    result = MethodPipeline(method=method, assistant_llms=GPT4O).run_trial(
        native.TRIAL
    )
    assert result.token_usage.total_tokens == 1200
    assert result.writer_tokens.calls == 2
    latency = result.latency_breakdown
    assert latency.llm_ms == 700.0 and latency.barrier_wait_ms == 0.0
    assert latency.kernel_overhead_ms == pytest.approx(
        latency.search_ms + latency.select_ms + latency.format_ms
        + latency.schedule_wait_ms
    )
    if method == "native_mem0":
        # Profile, task and the assistant's conversation write.
        assert result.backend_llm_tokens.calls == 3
        assert result.backend_llm_tokens.total_tokens == 3 * 3100
    else:
        assert result.backend_llm_tokens.calls == 0
    # The in-house store's embeddings are counted by its embedder (faked
    # here); the trial took everything recorded for its user.
    assert usage.ACCUMULATOR.take(native.TRIAL.user_id + "__" + method,
                                  wait=0) == []


@pytest.mark.parametrize("variants", [
    None, {"profile_agent": "V2"}, {"assistant_agent": "V2"}])
def test_agent_managed_v1_trial_counts_every_user_id(native_harness,
                                                     variants):
    """A V2 agent tags its backend calls with a rewritten id. The
    assistant's run took only its own id's calls, so a V2 writer's calls
    or, under a V2 assistant, every writer's were never counted
    (Subtask 16's pilot_v1 smoke)."""
    method = "native_mem0"
    result = MethodPipeline(method=method, assistant_llms=GPT4O).run_trial(
        native.TRIAL, variants=variants
    )
    # Profile, task and the assistant's conversation write.
    assert result.backend_llm_tokens.calls == 3
    assert result.backend_llm_tokens.total_tokens == 3 * 3100
    base = native.TRIAL.user_id + "__" + method
    for uid in (base, f"{base}@users.example"):
        assert usage.ACCUMULATOR.take(uid, wait=0) == []


def test_kernel_backend_usage_is_read_from_memory_cost():
    body = {
        "backend_llm_tokens": {"calls": 0, "prompt_tokens": 0,
                               "completion_tokens": 0, "total_tokens": 0,
                               "models": []},
        "embedding_tokens": {"calls": 4, "prompt_tokens": 120,
                             "completion_tokens": 0, "total_tokens": 120,
                             "models": ["ollama/nomic-embed-text"]},
    }
    with patch.object(run_evaluation.requests, "get") as get:
        get.return_value.json.return_value = body
        fields = run_evaluation.read_backend_usage("http://k", "ana__ks")
    assert get.call_args.kwargs["params"] == {"user_id": "ana__ks"}
    assert fields["embedding_tokens"].calls == 4
    assert fields["backend_llm_tokens"].calls == 0
    # The kernel waits on the user's writes before it reads (Subtask
    # 16), up to the barrier's timeout: the read must outlast that wait,
    # or a timed-out read would leave the trial with no backend calls.
    assert get.call_args.kwargs["timeout"] > (
        run_evaluation.V2_BARRIER_TIMEOUT_MS / 1000)


def test_trial_result_has_the_cost_fields():
    fields = TrialResult(trial_index=0, condition="c").model_dump()
    for key in ("token_usage", "writer_tokens", "backend_llm_tokens",
                "embedding_tokens", "latency_breakdown"):
        assert key in fields
