"""Judge repeats, the second judge, and their records (NeurIPS Subtask
20, AIOS docs/METRICS.md "The judges", "Recording")."""
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import judge, models, rejudge
from benchmarks.shared_memory.judge import (
    CLAUDE_THINKING,
    OAUTH_BETA,
    SECOND_JUDGE,
    SYSTEM_PROMPT,
    ClaudeJudge,
    HybridJudge,
    JudgeFailed,
    JudgeScores,
    batch_evaluate,
    build_messages,
    claude_batch_scores,
)
from benchmarks.shared_memory.metrics import hybrid_scores, keyword_scores
from benchmarks.shared_memory.models import ProbeResult
from tests.agents.test_judge_prompt_v2 import (
    PROFILE,
    TASK,
    experiment,
    trial,
)

ANSWER = "Use vim and Go for the web server."


def scores(p, t, i, usage=(100, 20), at="2026-11-19T00:00:00.000+00:00"):
    return JudgeScores(
        profile_usage_score=p, task_usage_score=t, integration_score=i,
        profile_usage_reasoning=f"p{p}", task_usage_reasoning=f"t{t}",
        integration_reasoning=f"i{i}", model="azure/gpt-5.4",
        judged_at=at,
        token_usage={"prompt_tokens": usage[0],
                     "completion_tokens": usage[1]})


def test_repeats_must_be_odd():
    with pytest.raises(ValueError, match="odd"):
        HybridJudge(repeats=2)
    from benchmarks.shared_memory.run_evaluation import _odd_repeats
    assert _odd_repeats("3") == 3
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        _odd_repeats("4")


def test_repeats_record_every_judgment_and_score_the_median():
    hybrid = HybridJudge(llms=[{"name": "gpt-5.4", "backend": "azure"}],
                         repeats=3)
    calls = [scores(2, 5, 2), JudgeScores(token_usage={
        "prompt_tokens": 100, "completion_tokens": 5}),
        scores(4, 5, 3), scores(3, 4, 5)]
    with patch.object(hybrid.llm_judge, "evaluate", side_effect=calls):
        out = hybrid.evaluate("q", ANSWER, PROFILE, TASK)
    record = out.record
    assert [j["scores"] for j in record["judgments"]] == [
        {"profile": 2, "task": 5, "integration": 2},
        {"profile": 4, "task": 5, "integration": 3},
        {"profile": 3, "task": 4, "integration": 5}]
    assert [j["attempts"] for j in record["judgments"]] == [1, 2, 1]
    # The failed attempt's tokens were spent too.
    assert record["judgments"][1]["token_usage"] == {
        "prompt_tokens": 200, "completion_tokens": 25}
    assert record["llm"] == {"profile": 3, "task": 5, "integration": 3}
    keyword = keyword_scores(ANSWER, PROFILE, TASK)
    assert record["keyword"] == keyword
    assert record["hybrid"] == hybrid_scores(keyword, record["llm"])
    assert (out.profile_usage_score, out.task_usage_score,
            out.integration_score) == tuple(record["hybrid"].values())
    assert out.judge_attempts == record["token_usage"]["calls"] == 4
    assert record["token_usage"]["prompt_tokens"] == 400
    assert record["judge"] == "gpt-5.4" and record["repeats"] == 3
    assert record["decoding"] == {"temperature": 0.0, "seed": 20261105}


def test_the_primary_judge_records_its_call():
    reply = {"response": {"response_message": json.dumps({
        "profile_usage_score": 4, "task_usage_score": 5,
        "integration_score": 3, "profile_usage_reasoning": "a",
        "task_usage_reasoning": "b", "integration_reasoning": "c"})},
        "token_usage": {"prompt_tokens": 900, "completion_tokens": 120,
                        "total_tokens": 1020}}
    llm = judge.LLMJudge(llms=[{"name": "gpt-5.4", "backend": "azure"}])
    with patch.object(judge, "llm_chat_with_json_output",
                      return_value=reply):
        out = llm.evaluate("q", ANSWER, PROFILE, TASK)
    assert out.integration_score == 3
    assert out.model == "azure/gpt-5.4"
    assert out.token_usage == {"prompt_tokens": 900,
                               "completion_tokens": 120}
    assert out.judged_at


class FakeMessage:
    def __init__(self, text, stop="end_turn", model="claude-sonnet-5-5"):
        self.content = [SimpleNamespace(type="text", text=text)]
        self.stop_reason = stop
        self.model = model
        self.usage = SimpleNamespace(input_tokens=1100, output_tokens=150)


REPLY = json.dumps({"profile_usage_score": 5, "task_usage_score": 4,
                    "integration_score": 4, "profile_usage_reasoning": "x",
                    "task_usage_reasoning": "y",
                    "integration_reasoning": "z"})


def test_the_second_judge_sends_the_same_prompt_without_sampling():
    sent = []
    client = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: sent.append(kw) or FakeMessage(REPLY)))
    second = ClaudeJudge(client_factory=lambda: client)
    out = second.evaluate("q", ANSWER, PROFILE, TASK)
    system, user = build_messages("q", ANSWER, PROFILE, TASK)
    (params,) = sent
    assert params["system"] == system["content"] == SYSTEM_PROMPT
    assert params["messages"] == [user]
    assert params["thinking"] == CLAUDE_THINKING == {"type": "between_tools"}
    assert params["max_tokens"] == 1024
    assert params["model"] == "claude-sonnet-5-5"
    assert not {"temperature", "top_p", "top_k"} & set(params)
    assert (out.profile_usage_score, out.integration_score) == (5, 4)
    assert out.model == "anthropic/claude-sonnet-5-5"
    assert out.token_usage == {"prompt_tokens": 1100,
                               "completion_tokens": 150}


def test_the_client_takes_a_fresh_token_and_refuses_an_api_key(monkeypatch):
    import anthropic
    made = []
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(judge.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(stdout="tok-123\n"))
    monkeypatch.setattr(anthropic, "Anthropic",
                        lambda **kw: made.append(kw) or "client")
    assert judge.anthropic_client() == "client"
    assert made == [{"auth_token": "tok-123",
                     "default_headers": {"anthropic-beta": OAUTH_BETA}}]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "set")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        judge.anthropic_client()


class FakeBatches:
    """A Message Batches endpoint: ends after one poll, returns its
    results in reverse order, the last one errored."""

    def __init__(self):
        self.created = None
        self.polls = 0

    def create(self, requests):
        self.created = requests
        return SimpleNamespace(id="b1", processing_status="in_progress")

    def retrieve(self, batch_id):
        self.polls += 1
        return SimpleNamespace(
            id=batch_id, processing_status="ended", request_counts=None,
            ended_at=SimpleNamespace(isoformat=lambda: "ended"))

    def results(self, batch_id):
        ids = [r["custom_id"] for r in self.created]
        out = [SimpleNamespace(custom_id=cid, result=SimpleNamespace(
            type="succeeded", message=FakeMessage(REPLY)))
            for cid in ids[:-1]]
        out.append(SimpleNamespace(custom_id=ids[-1], result=SimpleNamespace(
            type="errored")))
        return list(reversed(out))


def test_a_batch_is_keyed_by_custom_id_with_a_fresh_client_per_call():
    batches = FakeBatches()
    made = []

    def factory():
        made.append(1)
        return SimpleNamespace(messages=SimpleNamespace(batches=batches))

    second = ClaudeJudge(client_factory=factory)
    item = {"query": "q", "response": ANSWER, "profile": PROFILE,
            "task_context": TASK}
    out = claude_batch_scores(second, {"a": item, "b": item, "c": item},
                              sleep=lambda s: None)
    assert [r["custom_id"] for r in batches.created] == ["a", "b", "c"]
    assert out["a"].integration_score == out["b"].integration_score == 4
    assert out["c"].integration_score is None          # errored
    assert {s.batch_id for s in out.values()} == {"b1"}
    assert out["a"].judged_at == "ended" and out["a"].submitted_at
    assert len(made) == 3        # create, one poll, the results


def test_batch_evaluate_retries_incomplete_judgments_and_fails_the_rest():
    second = HybridJudge(judge=ClaudeJudge(client_factory=lambda: None),
                         name=SECOND_JUDGE, repeats=3)
    rounds = []

    def batch_scores(llm_judge, items):
        rounds.append(sorted(items))
        out = {}
        for key in items:
            ok = key.startswith("a") or (key == "b-2" and len(rounds) == 2) \
                or (key.startswith("b") and key != "b-2")
            out[key] = scores(4, 4, 4) if ok else JudgeScores()
        return out

    item = {"query": "q", "response": ANSWER, "profile": PROFILE,
            "task_context": TASK}
    out = batch_evaluate(second, {"a": item, "b": item, "c": item},
                         batch_scores)
    assert rounds[0] == sorted(f"{i}-{r}" for i in "abc" for r in (1, 2, 3))
    assert rounds[1] == ["b-2", "c-1", "c-2", "c-3"]
    # Every custom id is one the Batches API accepts.
    assert all(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", key)
               for key in rounds[0])
    assert len(rounds) == 3
    assert out["a"].record["llm"] == {"profile": 4, "task": 4,
                                      "integration": 4}
    assert [j["attempts"] for j in out["b"].record["judgments"]] == [1, 2, 1]
    assert isinstance(out["c"], JudgeFailed)


def v2_trial():
    t = trial(1)
    probe = ProbeResult(probe_id="p", type="integration", question="q",
                        observed=ANSWER,
                        judge_scores={"profile_usage_score": 1,
                                      "task_usage_score": 1,
                                      "integration_score": 1},
                        integration_score=1)
    return t.model_copy(update={"probe_results": [probe],
                                "assistant_response": ANSWER})


def judged_by(name, value):
    hybrid = HybridJudge(llms=[{"name": "gpt-5.4", "backend": "azure"}],
                         name=name)
    with patch.object(hybrid.llm_judge, "evaluate",
                      return_value=scores(value, value, value)):
        return hybrid, hybrid.evaluate("q", ANSWER, PROFILE, TASK)


def test_the_second_judge_adds_its_record_and_keeps_the_scores():
    second, out = judged_by(SECOND_JUDGE, 5)
    t = rejudge.apply_judgment(second, v2_trial(), out)
    assert (t.profile_usage_score, t.integration_score) == (1, 1)
    assert t.probe_results[0].integration_score == 1
    assert t.judges[SECOND_JUDGE] == out.record
    assert t.probe_results[0].judges[SECOND_JUDGE] == out.record
    # another judge's record is kept
    earlier = {"gpt-5.4": {"llm": {"profile": 3}}}
    both = rejudge.apply_judgment(
        second, v2_trial().model_copy(update={"judges": earlier}), out)
    assert both.judges == {**earlier, SECOND_JUDGE: out.record}
    failed = rejudge.apply_judgment(second, v2_trial(), JudgeFailed(3))
    assert not failed.failed
    assert failed.judges[SECOND_JUDGE] == {
        "judge": SECOND_JUDGE, "failed": True, "attempts": 3}


def test_the_primary_judge_rewrites_the_v2_probe_score_too():
    primary, out = judged_by("gpt-5.4", 5)
    t = rejudge.apply_judgment(primary, v2_trial(), out)
    assert t.integration_score == out.integration_score
    assert t.probe_results[0].integration_score == out.integration_score
    assert t.probe_results[0].judge_scores["integration_score"] == \
        out.integration_score
    assert t.judges["gpt-5.4"] == out.record


def test_rejudge_root_keeps_the_inputs_layout(tmp_path):
    source = tmp_path / "in" / "qwen" / "kinh" / "h0_kernel_shared" / \
        "results_kernel_shared.json"
    assert rejudge.output_path(source, tmp_path / "out", "kernel_shared",
                               tmp_path / "in") == \
        tmp_path / "out" / "qwen" / "kinh" / "h0_kernel_shared" / \
        "results_kernel_shared.json"


def test_rejudge_in_batch_judges_every_file_at_once():
    second, out = judged_by(SECOND_JUDGE, 4)
    seen = []

    def evaluate(judge_, items):
        seen.append(len(items))
        return {item_id: out for item_id in items}

    files = {"x": experiment([trial(1), trial(2, failed=True)]),
             "y": experiment([trial(3)])}
    done = rejudge.rejudge_in_batch(files, second, SECOND_JUDGE, evaluate)
    assert seen == [2]                       # one batch, failed skipped
    assert done["x"].conditions[0].trials[0].judges[SECOND_JUDGE] == \
        out.record
    assert done["x"].conditions[0].trials[1].judges is None
    assert done["y"].experiment_metadata.rejudge["judge"]["name"] == \
        SECOND_JUDGE


def test_the_harness_records_the_judge_and_its_record(tmp_path):
    from benchmarks.shared_memory.pipeline import PipelineResult
    from benchmarks.shared_memory.run_evaluation import (
        EvaluationOrchestrator,
    )

    trial_data = models.SyntheticTrialData(
        profile=PROFILE, task_context=TASK, follow_up_query="q",
        plausible_actions=["a"], user_id="u",
    )
    with patch(
        "benchmarks.shared_memory.run_evaluation.SyntheticDataGenerator"
    ) as generator, patch(
        "benchmarks.shared_memory.run_evaluation.MethodPipeline"
    ) as pipeline, patch.object(models.requests, "get") as get:
        get.return_value.json.return_value = {}
        generator.return_value.generate_trial_data.return_value = trial_data
        pipeline.return_value.run_trial.return_value = PipelineResult(
            profile_result={}, task_result={}, assistant_result={},
            assistant_response=ANSWER, latency_seconds=1.0,
        )
        orchestrator = EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path), write_csv=False,
            condition=None, method="kernel_private",
            judge_name="gpt-5.4", judge_repeats=3,
        )
        with patch.object(orchestrator.judge.llm_judge, "evaluate",
                          side_effect=[scores(3, 4, 3)] * 3):
            orchestrator.run()
    data = json.loads((tmp_path / "results_kernel_private.json").read_text())
    meta = data["experiment_metadata"]["judge"]
    assert (meta["name"], meta["repeats"]) == ("gpt-5.4", 3)
    assert meta["model"] == "azure/gpt-5.4"
    record = data["conditions"][0]["trials"][0]["judges"]["gpt-5.4"]
    assert len(record["judgments"]) == 3
    assert all(j["judged_at"] for j in record["judgments"])


def test_a_failed_download_is_retried_and_a_batch_can_be_collected():
    """A finished batch's results are downloaded again after a
    transient error; ``batch_id`` collects a batch without creating
    one."""
    batches = FakeBatches()
    downloads = []
    real = batches.results

    def flaky(batch_id):
        downloads.append(batch_id)
        if len(downloads) == 1:
            raise OSError("Bad file descriptor")
        return real(batch_id)

    batches.results = flaky
    client = SimpleNamespace(messages=SimpleNamespace(batches=batches))
    second = ClaudeJudge(client_factory=lambda: client)
    item = {"query": "q", "response": ANSWER, "profile": PROFILE,
            "task_context": TASK}
    submitted = []
    out = claude_batch_scores(second, {"a": item, "b": item},
                              sleep=lambda s: None,
                              on_submit=submitted.append)
    assert submitted == ["b1"] and len(downloads) == 2
    assert out["a"].integration_score == 4
    created = batches.created
    batches.created = None
    batches.create = lambda requests: pytest.fail("submitted again")
    batches.created = created
    again = claude_batch_scores(second, {"a": item, "b": item},
                                sleep=lambda s: None, batch_id="b1")
    assert again["a"].integration_score == 4


def test_the_client_lives_while_its_results_stream():
    """The SDK's client and its resources form a cycle; collected while
    a batch's results stream, the client closes the stream's connection
    ("Bad file descriptor"). The download holds the client."""
    import gc

    class Client:
        def __init__(self, batches):
            self.closed = {"value": False}
            closed = self.closed
            # A cycle, as client -> resources -> client in the SDK.
            self.messages = SimpleNamespace(batches=batches, owner=self)

            def results(batch_id):
                for result in batches.results(batch_id):
                    gc.collect()
                    if closed["value"]:
                        raise OSError("Bad file descriptor")
                    yield result
            self.messages.batches = SimpleNamespace(
                create=batches.create, retrieve=batches.retrieve,
                results=results)
            import weakref
            weakref.finalize(self, closed.__setitem__, "value", True)

    batches = FakeBatches()
    second = ClaudeJudge(client_factory=lambda: Client(batches))
    item = {"query": "q", "response": ANSWER, "profile": PROFILE,
            "task_context": TASK}
    with patch.object(judge, "BATCH_DOWNLOADS", 1):
        out = claude_batch_scores(second, {"a": item, "b": item, "c": item},
                                  sleep=lambda s: None)
    assert out["a"].integration_score == 4


def test_the_second_judge_subset_is_30_percent_by_user_and_echo():
    from benchmarks.shared_memory.synth_v2 import is_echo_user

    users = judge.second_judge_users(range(150))
    assert len(users) == 45
    # FULL_GRID.md's list, fixed before the grid runs
    assert users == [
        4, 5, 7, 11, 15, 16, 20, 25, 26, 27, 28, 32, 36, 38, 41, 43, 44,
        49, 54, 56, 57, 60, 61, 62, 66, 72, 74, 78, 79, 80, 89, 90, 93, 94,
        96, 97, 105, 106, 115, 120, 130, 134, 138, 140, 147]
    assert sum(1 for i in users if is_echo_user(i)) == 15
    assert users == judge.second_judge_users(reversed(range(150)))
    order = judge.second_judge_order()
    assert set(users) == set(order["echo"][:15]) | set(order["other"][:30])
    # A 30-user cell: 10 echo users (3 taken) and 20 others (6 taken).
    small = judge.second_judge_users(range(30))
    assert len(small) == 9 and set(small) <= set(range(30))
    assert sum(1 for i in small if is_echo_user(i)) == 3
    # One user of a stratum is still judged.
    assert judge.second_judge_users([0, 1]) == [0, 1]
    with pytest.raises(ValueError, match="outside"):
        judge.second_judge_users([150])


def test_a_collected_batch_id_goes_to_the_first_round_only():
    """``batch_id`` collects the batch already submitted for every
    judgment; a judgment it left incomplete goes in a new batch."""
    seen = []

    def scores(llm_judge, items, **extra):
        seen.append((sorted(items), extra.get("batch_id")))
        first = len(seen) == 1
        return {key: JudgeScores(
            profile_usage_score=4, task_usage_score=4,
            integration_score=None if first and key == "a-1" else 4)
            for key in items}

    item = {"query": "q", "response": ANSWER, "profile": PROFILE,
            "task_context": TASK}
    out = judge.batch_judgments(None, {"a": item, "b": item}, 1, scores,
                                batch_id="b1")
    assert seen == [(["a-1", "b-1"], "b1"), (["a-1"], None)]
    assert not isinstance(out["a"][1], JudgeFailed)


def test_rejudge_main_sends_the_second_judge_through_one_batch(tmp_path):
    source = tmp_path / "in" / "qwen_kernel_shared" / \
        "results_kernel_shared.json"
    source.parent.mkdir(parents=True)
    source.write_text(experiment([trial(0)]).model_dump_json())
    batched = []

    def in_batch(todo, judge_, label):
        batched.append((sorted(todo), judge_.name, label))
        return dict(todo)

    with patch.object(rejudge, "rejudge_in_batch", in_batch), \
            patch.object(rejudge, "rejudge_experiment",
                         side_effect=AssertionError("per answer")):
        rejudge.main([str(source), "--output", str(tmp_path / "out"),
                      "--judge", SECOND_JUDGE])
    assert batched == [([str(source)], SECOND_JUDGE, SECOND_JUDGE)]


def test_a_rejudged_file_with_a_failed_trial_is_not_complete(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(experiment([trial(0), trial(1, failed=True)])
                    .model_dump_json())
    assert not rejudge.complete(path, 2)
    path.write_text(experiment([trial(0), trial(1)]).model_dump_json())
    assert rejudge.complete(path, 2)
