"""Kernel ablation switches in the harness (NeurIPS Subtask 19, AIOS
docs/ABLATION.md): one definition, read from the AIOS library; the run's
ablation from ``--ablate`` and the old controls' aliases; the loci that
can run each switch; what every trial records; the fixed variants of an
ablation's condition; and a V4 consumer's own config on its chat
request."""
import importlib.util
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import ablation, history, run_evaluation
from benchmarks.shared_memory.ablation import (
    ALIASES,
    ABLATION_PATH,
    kernel_problems,
    locus_problems,
    run_ablation,
    trial_ablation,
)
from cerebrum.example.agents import variants as variant_catalog
from cerebrum.example.agents.variants import apply_variant
from tests.agents.test_history_v2 import USER_ID, managed

V4 = {"k": 5, "relevance_threshold": 0.5, "max_memory_tokens": 1500}


def test_the_switches_are_the_libraries_own():
    """Loaded from the AIOS checkout by path, as the matcher is: one
    definition for the kernel and the harness."""
    spec = importlib.util.spec_from_file_location("_check", ABLATION_PATH)
    library = importlib.util.module_from_spec(spec)
    import sys

    sys.modules["_check"] = library
    try:
        spec.loader.exec_module(library)
    finally:
        sys.modules.pop("_check", None)
    assert ablation.SWITCHES == library.SWITCHES
    assert ablation.ALIASES == library.ALIASES


def test_a_run_ablation_from_the_flag_and_an_aliased_control():
    assert run_ablation() == {}
    assert run_ablation(["barrier"]) == {"barrier": "off"}
    assert run_ablation(["forget_scope=none", "threshold=0.3"]) == {
        "forget_scope": "none", "threshold": 0.3}
    assert run_ablation(["barrier=on"]) == {}  # the full kernel's value
    for control, switches in ALIASES.items():
        assert run_ablation((), control) == switches
    assert run_ablation((), "no_memory") == {}  # a control, not a switch
    assert run_ablation(["quota"], "no_delete") == {
        "quota": "off", "forget_scope": "none"}


@pytest.mark.parametrize("ablate, control, message", [
    (["barrier", "barrier=off"], None, "names barrier twice"),
    (["forget_scope"], "no_delete", "already sets forget_scope"),
    (["cache"], None, "unknown ablation switch"),
    (["identity=maybe"], None, "must be one of"),
])
def test_a_bad_run_ablation_is_refused(ablate, control, message):
    with pytest.raises(ValueError, match=message):
        run_ablation(ablate, control)


@pytest.mark.parametrize("locus, switches, refused", [
    ("kernel", {"identity": "claim", "consumer_config": "honor"}, []),
    ("replicated", {"barrier": "off", "visibility": "off",
                    "forget_scope": "writer", "quota": "off"}, []),
    ("replicated", {"identity": "claim"}, ["identity"]),
    ("replicated", {"consumer_config": "honor"}, ["consumer_config"]),
    ("native", {"visibility": "off", "forget_scope": "none"}, []),
    ("native", {"forget_scope": "writer"}, ["forget_scope"]),
    ("native", {"supersession": "off"}, ["supersession"]),
    ("native", {"barrier": "off"}, ["barrier"]),
])
def test_each_locus_runs_the_switches_it_has(locus, switches, refused):
    problems = locus_problems(switches, locus)
    assert [p.split(":")[0] for p in problems] == refused


def test_the_orchestrator_refuses_a_switch_its_locus_lacks(tmp_path):
    with pytest.raises(ValueError, match="identity: a replicated agent"):
        orchestrator(tmp_path, method="replicated_inhouse",
                     ablate=["identity"])
    with pytest.raises(ValueError, match="barrier: off has no native"):
        orchestrator(tmp_path, method="native_inhouse", ablate=["barrier"])


def test_the_kernel_must_report_the_runs_switches():
    full = {name: value for name, (value, _, _)
            in ablation.SWITCHES.items()}
    assert kernel_problems(full, {}) == []
    assert kernel_problems({}, {}) == []
    assert kernel_problems(dict(full, quota="off"), {"quota": "off"}) == []
    assert kernel_problems(full, {"quota": "off"}) == [
        "ablate.quota is 'on', not 'off'"]
    assert kernel_problems({"quota": False}, {}) == [
        "ablate.quota is 'off', not 'on'"]
    assert "predates" in kernel_problems(None, {})[0]
    assert "invalid" in kernel_problems({"cache": "off"}, {})[0]


def test_a_trial_from_before_the_switches_reads_as_its_controls_alias():
    assert trial_ablation({"control": "writer_scoped"}) == {
        "forget_scope": "writer"}
    assert trial_ablation({"control": "no_memory"}) == {}
    assert trial_ablation({}) == {}
    assert trial_ablation({"control": "no_delete",
                           "ablation": {"forget_scope": "none"}}) == {
        "forget_scope": "none"}
    assert trial_ablation({"ablation": {}}) == {}


# -- the orchestrator ---------------------------------------------------------

def orchestrator(tmp_path, **kwargs):
    from benchmarks.shared_memory import synth_v2

    path = tmp_path / "v2.jsonl"
    if not path.exists():
        synth_v2.generate(path, n=2)
    with patch.object(run_evaluation, "SyntheticDataGenerator"), \
            patch.object(run_evaluation, "HybridJudge"):
        return run_evaluation.EvaluationOrchestrator(
            trials=1, output_dir=str(tmp_path / "out"), write_csv=False,
            condition=None, method=kwargs.pop("method", "kernel_shared"),
            dataset=kwargs.pop("dataset", str(path)),
            judge=kwargs.pop("judge", False), **kwargs)


def test_every_trial_and_the_results_record_the_ablation(tmp_path):
    """``ablation`` on the trial (``{}`` for the full kernel) and in the
    run settings; an aliased control records its switches."""
    full = orchestrator(tmp_path)
    assert full.ablation == {} and full._run_settings()["ablation"] == {}
    ablated = orchestrator(tmp_path, ablate=["barrier"])
    assert ablated._run_settings()["ablation"] == {"barrier": "off"}
    alias = orchestrator(tmp_path, control="writer_scoped")
    assert alias.ablation == {"forget_scope": "writer"}
    seen = {}

    def run_history_trial(user, variants=None, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop after the call")

    pipeline = SimpleNamespace(run_history_trial=run_history_trial)
    trial = ablated.run_single_trial_v2(0, "kernel_shared", pipeline,
                                        "kernel_shared")
    assert trial.ablation == {"barrier": "off"}
    assert seen["ablation"] == {"barrier": "off"}
    trial = full.run_single_trial_v2(0, "kernel_shared", pipeline,
                                     "kernel_shared")
    assert trial.ablation == {}


def test_the_full_kernel_passes_no_ablation_to_the_history(tmp_path):
    seen = {}

    def run_history_trial(user, variants=None, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop")

    orchestrator(tmp_path).run_single_trial_v2(
        0, "kernel_shared", SimpleNamespace(
            run_history_trial=run_history_trial), "kernel_shared")
    assert "ablation" not in seen


def test_the_cli_takes_ablate_and_variants():
    args = run_evaluation.build_arg_parser().parse_args([
        "--ablate", "barrier", "--ablate", "threshold=0.3",
        "--variants", "assistant_agent=V4",
    ])
    assert args.ablate == ["barrier", "threshold=0.3"]
    assert args.variants == ["assistant_agent=V4"]
    assert run_evaluation.build_arg_parser().parse_args([]).ablate is None


# -- fixed variants -----------------------------------------------------------

def test_fixed_variants_give_every_user_the_same_condition(tmp_path):
    o = orchestrator(tmp_path, variants=["assistant_agent=V4"])
    assert o.heterogeneity == 1
    assert [o.trial_variants(i) for i in range(5)] == [
        {"assistant_agent": "V4"}] * 5
    assert o._heterogeneity_metadata()["variants"] == {
        "assistant_agent": "V4"}
    two = orchestrator(tmp_path, variants=["profile_agent=V2",
                                           "assistant_agent=V3"])
    assert two.heterogeneity == 2


@pytest.mark.parametrize("variants, kwargs, message", [
    (["assistant_agent=V9"], {}, "V9"),
    (["janitor_agent=V4"], {}, "janitor_agent"),
    (["assistant_agent=V4", "assistant_agent=V3"], {}, "twice"),
    (["assistant_agent"], {}, "AGENT=CODE"),
    (["assistant_agent=V4"], {"heterogeneity": 1}, "fixes the variants"),
    (["assistant_agent=V4"], {"judge": True}, "--no-judge"),
])
def test_bad_fixed_variants_are_refused(tmp_path, variants, kwargs,
                                        message):
    with pytest.raises((ValueError, KeyError), match=message):
        orchestrator(tmp_path, variants=variants, **kwargs)


# -- the loci -----------------------------------------------------------------

def test_the_kernel_runs_no_visibility_and_native_its_consumer_check():
    """Before Subtask 19 the kernel refused no_visibility; it is now the
    kernel's ablation. A native consumer's own check is switched off,
    and a replicated agent's library copies the kernel's switch."""
    from tests.agents.test_history_v2 import NativeRulesConsumer

    kernel = history.KernelLocus()
    kernel.start_user(USER_ID, "no_visibility")
    native = managed("native", consumer=NativeRulesConsumer)
    native.start_user(USER_ID, "no_visibility")
    assert native.agents[history.CONSUMER].check_visibility is False
    replicated = managed("replicated", consumer=NativeRulesConsumer)
    replicated.start_user(USER_ID, "no_visibility")
    assert replicated.agents[history.CONSUMER].check_visibility is True


def test_an_ablation_reaches_the_locus_only_when_there_is_one():
    seen = []

    class Locus(history.KernelLocus):
        def start_user(self, user_id, control, writers=history.WRITERS,
                       **kwargs):
            seen.append(kwargs)
            raise RuntimeError("stop")

    from benchmarks.shared_memory.pipeline import VariantRunner
    from tests.agents.test_history_v2 import v2_user

    for switches in ({}, {"barrier": "off"}):
        with pytest.raises(RuntimeError):
            history.run_history(v2_user(), Locus(),
                                VariantRunner(None, "kernel"),
                                ablation=switches)
    assert seen == [{}, {"ablation": {"barrier": "off"}}]


# -- a V4 consumer's own config ----------------------------------------------

def consumer():
    return SimpleNamespace(user_id=USER_ID, llms=None)


@pytest.mark.parametrize("switches, applied", [
    ({}, False), ({"consumer_config": "honor"}, True),
])
def test_a_v4_kernel_consumer_sends_its_config(switches, applied):
    """The config rides on the chat request whatever the kernel runs;
    it is recorded as applied only under ``consumer_config: honor``."""
    agent = consumer()
    v4 = variant_catalog.variant("V4")
    with apply_variant(v4, agent, history.CONSUMER, "kernel",
                       ablation=switches) as skipped:
        assert agent.retrieval == V4
        assert (skipped is None) is applied
        if not applied:
            assert "consumer_config: honor" in skipped
    assert not hasattr(agent, "retrieval")


def test_a_v4_writer_gets_no_retrieval_channel():
    agent = consumer()
    with apply_variant(variant_catalog.variant("V4"), agent,
                       "profile_agent", "kernel",
                       ablation={"consumer_config": "honor"}) as skipped:
        assert not hasattr(agent, "retrieval")
        assert "the kernel applies its own threshold" in skipped


def test_the_assistant_sends_its_config_only_when_it_has_one():
    from cerebrum.example.agents.assistant_agent import agent as module

    sent = []

    def llm_chat(**kwargs):
        sent.append(kwargs)
        return {"response": {"response_message": "ok"}}

    with patch.object(module, "llm_chat", side_effect=llm_chat):
        plain = module.AssistantAgent("assistant_agent")
        plain.run("hi")
        tuned = module.AssistantAgent("assistant_agent")
        tuned.retrieval = dict(V4)
        tuned.run("hi")
    assert "retrieval" not in sent[0]
    assert sent[1]["retrieval"] == V4


def test_the_sdk_chat_request_carries_the_config():
    from cerebrum.llm import apis

    with patch.object(apis, "send_request", side_effect=lambda a, q, u: q):
        query = apis.llm_chat("assistant_agent", [{"role": "user",
                                                   "content": "hi"}],
                              retrieval=V4)
        plain = apis.llm_chat("assistant_agent", [{"role": "user",
                                                   "content": "hi"}])
    assert query.retrieval == V4 and plain.retrieval is None
