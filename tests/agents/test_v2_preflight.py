"""Benchmark v2's pre-flight (AIOS docs/BENCHMARK_V2.md, "Harness",
"Pre-flight", Amendment 3 and Amendment 4): the kernel's memory
settings a v2 run needs, read from ``/memory/config``."""
import os
from unittest.mock import patch

import pytest

from benchmarks.shared_memory import run_evaluation

TOMBSTONES = "/srv/aios/.aios_state/tombstones.sqlite"
HISTORY_DB = "/srv/aios/.mem0/chroma_store/history.db"
SHARED_HISTORY = os.path.join(os.path.expanduser("~"), ".mem0",
                              "history.db")
KERNEL_METHODS = ("kernel_shared",)
REPLICATED_METHODS = ("replicated_mem0", "replicated_inhouse")
NATIVE_METHODS = ("native_mem0", "native_inhouse")
CONTROLS = (None, "no_memory", "no_delete", "writer_scoped",
            "no_supersession")


def kernel_config(auto_inject=True, auto_extract=False, provider="in-house",
                  tombstones_path=TOMBSTONES, history_db_path=None,
                  **pipeline):
    """A ``/memory/config`` body that passes the v2 pre-flight for a
    kernel method (supersession on, a tombstone file), with
    ``pipeline`` changes."""
    settings = {"max_injected_memories": 30, "max_memory_tokens": 300,
                "relevance_threshold": 0.0, "block_format": "compact",
                "block_recency": True, "block_recency_unit": "session",
                "write_barrier": {"enabled": True, "timeout_ms": 60000},
                "supersession": "exclude"}
    settings.update(pipeline)
    return {"pipeline": settings, "auto_inject": auto_inject,
            "auto_extract": auto_extract, "pipeline_version": "v",
            "provider": provider, "tombstones_path": tombstones_path,
            "history_db_path": history_db_path}


def agent_config(**changes):
    """The body for an agent-managed method: the kernel's memory off."""
    return kernel_config(auto_inject=False, **changes)


def preflight(body, method="kernel_shared", control=None, ablation=None):
    """The pre-flight against ``body``. Since Subtask 19 the kernel must
    run the run's ablation (an aliased control's included): a body that
    sets no ``ablate`` reports the one the run needs."""
    from benchmarks.shared_memory.ablation import run_ablation

    if "ablate" not in body["pipeline"]:
        body["pipeline"]["ablate"] = (
            dict(ablation) if ablation is not None
            else run_ablation((), control))
    with patch.object(run_evaluation.requests, "get") as get:
        get.return_value.json.return_value = body
        return run_evaluation.check_v2_settings("http://kernel", method,
                                                control=control,
                                                ablation=ablation)


def test_a_kernel_v2_run_needs_injection_on_and_extraction_off():
    checked = preflight(kernel_config())
    assert (checked["auto_inject"], checked["auto_extract"]) == (True, False)
    with pytest.raises(SystemExit, match="auto_extract off"):
        preflight(kernel_config(auto_extract=True))
    with pytest.raises(SystemExit, match="auto_inject on"):
        preflight(kernel_config(auto_inject=False))


def test_the_v2_budget_is_300_tokens():
    assert run_evaluation.V2_SETTINGS["max_memory_tokens"] == 300
    with pytest.raises(SystemExit,
                       match="max_memory_tokens is 500, not 300"):
        preflight(kernel_config(max_memory_tokens=500))
    # An agent-managed method reads the same settings; the kernel's own
    # memory is off for it (check_kernel_mode checks that).
    native = kernel_config(auto_inject=False)
    assert preflight(native, "native_mem0")["pipeline"][
        "max_memory_tokens"] == 300


def test_the_v2_k_is_30_so_the_budget_limits_a_block():
    """Amendment 6: k 30 in every v2 cell's kernel, so the 300-token
    budget, not the cap, limits a kernel or replicated block; the
    earlier k 10 is refused."""
    assert run_evaluation.V2_SETTINGS["max_injected_memories"] == 30
    with pytest.raises(SystemExit,
                       match="max_injected_memories is 10, not 30"):
        preflight(kernel_config(max_injected_memories=10))
    assert preflight(kernel_config(auto_inject=False), "native_mem0")[
        "pipeline"]["max_injected_memories"] == 30


def test_v2_native_consumers_keep_k_10_and_replicated_the_kernels():
    """Amendment 6: a v2 native consumer, with no budget, keeps k 10
    (``V2_NATIVE_K``); a replicated agent's pipeline takes the kernel's
    settings, k 30 included."""
    from types import SimpleNamespace

    from benchmarks.shared_memory import pipeline as pl
    from cerebrum.example.agents.replicated import agents as replicated

    config = {"embedding": {"provider": "ollama",
                            "model": "nomic-embed-text"},
              "max_injected_memories": 30,
              "pipeline": {"max_injected_memories": 30,
                           "max_memory_tokens": 300}}
    built = []
    with patch.object(pl.AgentPipeline, "_kernel_memory_config",
                      return_value=config), \
            patch.object(pl, "NativeMemory", side_effect=lambda b, s:
                         built.append(("native", s.k)) or
                         SimpleNamespace(settings=s)), \
            patch.object(replicated, "ReplicatedMemory",
                         side_effect=lambda b, c: built.append(
                             ("replicated", c["max_injected_memories"]))
                         or SimpleNamespace()):
        pl.MethodPipeline("native_inhouse")._v2_agents("native", "inhouse")
        pl.MethodPipeline("replicated_inhouse")._v2_agents(
            "replicated", "inhouse")
    assert built == [("native", 10)] * 4 + [("replicated", 30)] * 4


# -- Amendment 4 -------------------------------------------------------------

@pytest.mark.parametrize("control", CONTROLS)
def test_supersession_is_exclude_under_every_control(control):
    """A v2 cell of the kernel or replicated locus runs with
    ``memory.supersession`` ``exclude``; since Subtask 19 no_supersession
    is the ablation ``supersession: off``, checked apart (before, it
    needed ``memory.supersession: off``)."""
    assert run_evaluation.expected_supersession(control) == "exclude"


@pytest.mark.parametrize("control", CONTROLS)
@pytest.mark.parametrize("method", KERNEL_METHODS + REPLICATED_METHODS)
def test_kernel_and_replicated_cells_need_the_controls_supersession(
        method, control):
    """The pre-flight of a kernel or replicated cell refuses a kernel
    whose ``supersession`` is not ``exclude`` (the replicated agents
    copy it from ``/memory/config``), a missing one included, and
    records the one it checked."""
    want, other = "exclude", "off"
    body = (kernel_config if method in KERNEL_METHODS else agent_config)
    checked = preflight(body(supersession=want), method, control)
    assert checked["pipeline"]["supersession"] == want
    with pytest.raises(SystemExit, match=f"supersession is '{other}', "
                                         f"not '{want}'"):
        preflight(body(supersession=other), method, control)
    without = body()
    del without["pipeline"]["supersession"]
    with pytest.raises(SystemExit, match=f"supersession is None, "
                                         f"not '{want}'"):
        preflight(without, method, control)


@pytest.mark.parametrize("control", CONTROLS)
@pytest.mark.parametrize("method", NATIVE_METHODS)
@pytest.mark.parametrize("supersession", ["off", "exclude", None])
def test_native_cells_do_not_check_supersession(method, control,
                                                supersession):
    """Native runs no library supersession, so its pre-flight takes the
    kernel's setting, whatever it is, and needs no tombstone file."""
    body = agent_config(supersession=supersession, tombstones_path=None)
    if supersession is None:
        del body["pipeline"]["supersession"]
    assert preflight(body, method, control)["pipeline"] == body["pipeline"]


def test_a_kernel_method_needs_a_tombstone_file():
    """Tombstones in memory would not survive a kernel restart, so a
    kernel cell needs ``memory.tombstones_path``; the path is recorded.
    A replicated cell keeps its tombstones in its own store, so the
    kernel's path is not checked for it."""
    assert preflight(kernel_config())["tombstones_path"] == TOMBSTONES
    for missing in (None, ""):
        with pytest.raises(SystemExit, match="memory.tombstones_path"):
            preflight(kernel_config(tombstones_path=missing))
    for method in REPLICATED_METHODS:
        preflight(agent_config(tombstones_path=None), method)


@pytest.mark.parametrize("path,passes", [
    (HISTORY_DB, True),
    (None, False),
    ("", False),
    (SHARED_HISTORY, False),
    (os.path.join(os.path.expanduser("~"), ".mem0", "store", "h.db"),
     False),
    # A sibling directory is a store's own, not the shared one.
    (os.path.join(os.path.expanduser("~"), ".mem0_x", "history.db"),
     True),
])
def test_a_kernel_mem0_store_needs_its_own_history_file(path, passes):
    """On Mem0 a kernel cell needs a history file of the store's own,
    not the ``~/.mem0`` one every run shared (known issue 46); the path
    is recorded. An in-house kernel needs none."""
    body = kernel_config(provider="mem0", history_db_path=path)
    if passes:
        assert preflight(body)["history_db_path"] == path
    else:
        with pytest.raises(SystemExit, match="Mem0's history file is"):
            preflight(body)
    assert preflight(kernel_config(provider="in-house",
                                   history_db_path=path))[
        "history_db_path"] == path


def test_a_v2_run_refuses_a_kernel_url_its_agents_do_not_use(monkeypatch):
    """``--kernel-url`` naming another kernel than the configured one
    stops a v2 run before any pre-flight call: the pre-flight would
    check that kernel while the agents, the audit and the judge use the
    configured one."""
    monkeypatch.setattr(run_evaluation.config, "get_kernel_url",
                        lambda: "http://localhost:8000")
    monkeypatch.setattr("sys.argv", [
        "run_evaluation", "--dataset", "pilot_v2", "--trials", "1",
        "--method", "kernel_shared", "--provider", "in-house",
        "--no-judge", "--kernel-url", "http://localhost:8001",
    ])
    with patch.object(run_evaluation.requests, "get",
                      side_effect=AssertionError("no kernel call")):
        with pytest.raises(SystemExit, match="configured kernel"):
            run_evaluation.main()


# -- Subtask 19: the kernel's ablation switches ----------------------------

@pytest.mark.parametrize("method", KERNEL_METHODS + REPLICATED_METHODS
                         + NATIVE_METHODS)
def test_the_kernel_must_run_the_runs_ablation(method):
    """AIOS docs/ABLATION.md: the kernel's ``pipeline.ablate`` must equal
    the run's ablation in every switch, whatever the locus. A full-kernel
    cell refuses an ablated kernel, an ablated cell a full kernel or
    another ablation, and a kernel from before the switches."""
    body = (kernel_config if method in KERNEL_METHODS else agent_config)
    checked = preflight(body(ablate={"barrier": "off"}), method,
                        ablation={"barrier": "off"})
    assert checked["pipeline"]["ablate"] == {"barrier": "off"}
    with pytest.raises(SystemExit, match="ablate.barrier is 'off', not "
                                         "'on'"):
        preflight(body(ablate={"barrier": "off"}), method, ablation={})
    with pytest.raises(SystemExit, match="ablate.quota is 'on', not 'off'"):
        preflight(body(ablate={"barrier": "off"}), method,
                  ablation={"quota": "off"})
    with pytest.raises(SystemExit, match="predates the ablation"):
        preflight(body(ablate=None), method, ablation={})


@pytest.mark.parametrize("control, switches", [
    ("no_visibility", {"visibility": "off"}),
    ("no_delete", {"forget_scope": "none"}),
    ("writer_scoped", {"forget_scope": "writer"}),
    ("no_supersession", {"supersession": "off"}),
])
def test_an_old_control_needs_its_ablation_on_the_kernel(control,
                                                         switches):
    full = kernel_config(ablate={})
    with pytest.raises(SystemExit, match="ablate\\."):
        preflight(full, control=control)
    preflight(kernel_config(ablate=dict(switches)), control=control)
