"""Offline static-threshold search — config→restart→verify primitives.

This module implements the reusable "apply one candidate config and get to a
verified-ready AIOS kernel" building block that every candidate iteration of the
threshold search calls. It deliberately contains ONLY the
config-edit → full-restart → gating-verify cycle. Trial-running and the search
loop itself are out of scope here (later subtasks).

Source of truth for the mechanics encapsulated here — three investigation
reports produced in Subtasks 1–3 (all under ``docs/`` in this repo):

* ``docs/threshold-search-config-reload-mechanics.md`` (Subtask 1)
  Empirically confirmed that ``POST /core/refresh`` does NOT apply
  ``memory.static_thresholds`` changes (a missing ``global`` in the kernel's
  ``restart_kernel`` discards the rebuilt MemoryManager), so a **full AIOS
  server process restart is required** between candidate configs. Hence
  :func:`restart_kernel_and_wait` stops and re-spawns the process rather than
  hitting a reload endpoint.

* ``docs/threshold-search-trial-pool-structure.md`` (Subtask 2)
  Established that ``kernel_shared_tuned`` requires BOTH
  ``static_thresholds.enabled = true`` AND ``adaptive_policy.enabled = false``
  — two independent kernel toggles — and that the harness verifies (raises on
  mismatch) but does not set them. Hence :func:`write_candidate_config` sets
  both toggles every time, and :func:`verify_gating_status` is the safety net.

* ``docs/threshold-search-harness-invocation.md`` (Subtask 3)
  Confirmed the live ``GET /memory/gating_status`` payload shape and that the
  gating state must be correct *before* trials run. This module gets the kernel
  into that verified-ready state.

The three thresholds (``novelty_threshold`` / ``similarity_threshold`` /
``redundancy_threshold``) each use the loader's default+overrides table form
(see ``aios/memory/static_thresholds.py``). A per-model candidate is written as
a **wildcard-on-llm_core override** — an ``overrides`` entry of
``{llm_core: <model>, value: <v>}`` with no ``task_type`` — while the other two
thresholds are held at their currently-fixed ``default`` values (baseline or the
coordinate-search's best-so-far). The wildcard form is what
``resolve_threshold`` matches for that model regardless of task type.

Config edits are **surgical/targeted** (regex line replacement inside the
already-present threshold sub-blocks) rather than a full ``yaml.safe_dump``
re-serialize, so comments, ordering, and unrelated formatting in the kernel's
``config.yaml`` are preserved.

No AIOS code is imported or modified by this module; it only reads/writes the
kernel's ``config.yaml`` on disk and talks to the running kernel over HTTP.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# The three static-threshold gates, as they appear under
# ``memory.static_thresholds`` in the kernel's config.yaml.
THRESHOLD_NAMES = (
    "novelty_threshold",
    "similarity_threshold",
    "redundancy_threshold",
)

# Default poll cadence when waiting for the kernel to come up.
_STATUS_POLL_INTERVAL_S = 2.0

# How close two floats must be to count as "equal" when comparing the written
# config against the kernel's reported gating_status (guards against YAML/JSON
# float round-tripping, e.g. 0.6 vs 0.6000000000000001).
_FLOAT_TOL = 1e-9


class GatingVerificationError(RuntimeError):
    """Raised when the live kernel's gating state does not match what was
    written. Carries the full expected-vs-actual detail in its message so a
    failed candidate application aborts loudly (never a silent warning)."""


class KernelStartupError(RuntimeError):
    """Raised when the freshly-started kernel does not report ``/status`` ok
    within the allotted timeout."""


class ConfigEditError(RuntimeError):
    """Raised when the surgical config edit cannot locate a block/line it
    expects, rather than writing a malformed or half-edited file."""


@dataclass
class CandidateConfig:
    """A single search candidate: one threshold varied for one model.

    Attributes:
        model_name: The ``llm_core`` the candidate value is scoped to via a
            wildcard override (e.g. ``"qwen2.5:7b"``).
        threshold_name: Which gate is being varied — one of
            :data:`THRESHOLD_NAMES`.
        value: The candidate threshold value for ``(model_name, *)``.
        other_thresholds_at: Fixed ``default`` values for the two thresholds
            NOT being varied (and the default for the varied one too). Maps a
            threshold name to the float held in its ``default`` slot. Any
            threshold absent from this map keeps whatever ``default`` is
            already on disk.
    """

    model_name: str
    threshold_name: str
    value: float
    other_thresholds_at: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.threshold_name not in THRESHOLD_NAMES:
            raise ValueError(
                f"threshold_name must be one of {THRESHOLD_NAMES}; "
                f"got {self.threshold_name!r}"
            )
        if not self.model_name:
            raise ValueError("model_name must be a non-empty string")


# ---------------------------------------------------------------------------
# 1. Surgical config editing
# ---------------------------------------------------------------------------

def _replace_block_toggle(text: str, block: str, key: str, value_literal: str) -> str:
    """Replace ``    <key>: <old>  # comment`` inside a top-level-ish ``block``.

    Targets the first ``key:`` line that appears AFTER the ``block:`` header
    line, preserving any trailing inline comment. Used for the two boolean
    toggles (``static_thresholds.enabled`` and ``adaptive_policy.enabled``).

    Args:
        text: Full config file text.
        block: The parent block key (e.g. ``"static_thresholds"`` or
            ``"adaptive_policy"``) whose child ``key`` is edited.
        key: The child key to set (e.g. ``"enabled"``).
        value_literal: The literal YAML value to write (e.g. ``"true"``).

    Returns:
        The edited text.

    Raises:
        ConfigEditError: If the block header or the child key line is not found.
    """
    block_match = re.search(rf"(?m)^(\s*){re.escape(block)}:\s*$", text)
    if not block_match:
        raise ConfigEditError(f"Could not find block '{block}:' in config.")
    start = block_match.end()

    # Match the child key line after the block header, keeping its comment.
    child_re = re.compile(
        rf"(?m)^(?P<indent>\s+){re.escape(key)}:[ \t]*"
        rf"(?P<val>\S+)(?P<comment>[ \t]*(?:#.*)?)$"
    )
    m = child_re.search(text, start)
    if not m:
        raise ConfigEditError(
            f"Could not find '{key}:' under block '{block}:' in config."
        )
    replacement = f"{m.group('indent')}{key}: {value_literal}{m.group('comment')}"
    return text[: m.start()] + replacement + text[m.end():]


def _set_threshold(
    text: str,
    threshold_name: str,
    default_value: Optional[float],
    overrides_literal: Optional[str],
) -> str:
    """Set the ``default:`` and/or ``overrides:`` lines of one threshold block.

    Operates within the specific ``<threshold_name>:`` sub-block under
    ``static_thresholds`` so the identical-looking ``default:``/``overrides:``
    lines of the OTHER two thresholds are never touched. The sub-block is
    bounded by its header line and the next same-or-lesser-indented key.

    Args:
        text: Full config file text.
        threshold_name: The threshold sub-block to edit.
        default_value: New ``default`` float, or None to leave it unchanged.
        overrides_literal: New literal for the ``overrides`` value (e.g. a
            flow-style list ``[{llm_core: "m", value: 0.6}]`` or ``[]``), or
            None to leave it unchanged.

    Returns:
        The edited text.

    Raises:
        ConfigEditError: If the sub-block or a requested line is not found.
    """
    header_re = re.compile(rf"(?m)^(?P<indent>\s+){re.escape(threshold_name)}:\s*$")
    hm = header_re.search(text)
    if not hm:
        raise ConfigEditError(
            f"Could not find threshold block '{threshold_name}:' in config."
        )
    header_indent = len(hm.group("indent"))
    block_start = hm.end()

    # The sub-block ends at the next line indented <= the header's indent
    # (i.e. a sibling threshold or the end of static_thresholds).
    end_re = re.compile(r"(?m)^(?P<indent>\s*)\S")
    block_end = len(text)
    for em in end_re.finditer(text, block_start):
        if len(em.group("indent")) <= header_indent:
            block_end = em.start()
            break

    block = text[block_start:block_end]

    if default_value is not None:
        default_re = re.compile(
            r"(?m)^(?P<indent>\s+)default:[ \t]*(?P<val>\S+)(?P<comment>[ \t]*(?:#.*)?)$"
        )
        dm = default_re.search(block)
        if not dm:
            raise ConfigEditError(
                f"Could not find 'default:' inside '{threshold_name}:' block."
            )
        new_default = (
            f"{dm.group('indent')}default: {_fmt_float(default_value)}"
            f"{dm.group('comment')}"
        )
        block = block[: dm.start()] + new_default + block[dm.end():]

    if overrides_literal is not None:
        overrides_re = re.compile(
            r"(?m)^(?P<indent>\s+)overrides:[ \t]*(?P<val>.*?)(?P<comment>[ \t]*(?:#.*)?)$"
        )
        om = overrides_re.search(block)
        if not om:
            raise ConfigEditError(
                f"Could not find 'overrides:' inside '{threshold_name}:' block."
            )
        new_overrides = (
            f"{om.group('indent')}overrides: {overrides_literal}"
            f"{om.group('comment')}"
        )
        block = block[: om.start()] + new_overrides + block[om.end():]

    return text[:block_start] + block + text[block_end:]


def _fmt_float(v: float) -> str:
    """Format a float for YAML without trailing-zero noise (0.6 not 0.60)."""
    # ``repr`` keeps 0.6 as "0.6" and 0.75 as "0.75" without float artifacts
    # for the short decimals used as thresholds.
    return repr(float(v))


def _overrides_literal(model_name: str, value: float) -> str:
    """Build a flow-style single wildcard override list literal.

    Produces ``[{llm_core: "<model>", value: <v>}]`` — a wildcard-on-llm_core
    entry (no ``task_type``) that ``resolve_threshold`` matches for that model
    regardless of task type. Flow style keeps the edit to a single line.
    """
    return f'[{{llm_core: "{model_name}", value: {_fmt_float(value)}}}]'


def write_candidate_config(
    config_path: str | Path,
    model_name: str,
    threshold_name: str,
    value: float,
    other_thresholds_at: Dict[str, float],
) -> None:
    """Surgically edit the AIOS ``config.yaml`` for one search candidate.

    Sets, in a single write:

    * ``static_thresholds.enabled: true`` and ``adaptive_policy.enabled: false``
      — every time, because Subtask 3 confirmed both must be correct together
      for the ``kernel_shared_tuned`` pre-flight to pass.
    * The varied ``threshold_name``'s ``overrides`` to a wildcard entry
      ``{llm_core: model_name, value: value}`` so ``value`` applies to
      ``model_name`` for any task type.
    * Each threshold's ``default`` to the value in ``other_thresholds_at`` when
      provided (holding the non-varied gates at their fixed baseline/best).

    The edit is targeted line-replacement inside the existing blocks; comments
    and unrelated formatting are preserved (no full re-serialization).

    Args:
        config_path: Path to the kernel's ``config.yaml``.
        model_name: ``llm_core`` the candidate value is scoped to.
        threshold_name: Gate being varied (one of :data:`THRESHOLD_NAMES`).
        value: Candidate threshold value.
        other_thresholds_at: Fixed ``default`` values keyed by threshold name.
            Thresholds omitted here keep their on-disk ``default``.

    Raises:
        ValueError: If ``threshold_name`` is not a known gate.
        ConfigEditError: If any expected block/line cannot be located.
    """
    if threshold_name not in THRESHOLD_NAMES:
        raise ValueError(
            f"threshold_name must be one of {THRESHOLD_NAMES}; got {threshold_name!r}"
        )
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")

    # 1. Force the two gating toggles.
    text = _replace_block_toggle(text, "static_thresholds", "enabled", "true")
    text = _replace_block_toggle(text, "adaptive_policy", "enabled", "false")

    # 2. Each threshold's default (when specified) + the varied override.
    for tname in THRESHOLD_NAMES:
        default_value = other_thresholds_at.get(tname)
        if tname == threshold_name:
            text = _set_threshold(
                text,
                tname,
                default_value=default_value,
                overrides_literal=_overrides_literal(model_name, value),
            )
        else:
            # Non-varied gate: hold default (if given), clear overrides so a
            # stale wildcard from a prior candidate can't leak in.
            text = _set_threshold(
                text,
                tname,
                default_value=default_value,
                overrides_literal="[]",
            )

    path.write_text(text, encoding="utf-8")
    logger.info(
        "Wrote candidate config: %s=%s for model=%s (static=on, adaptive=off); "
        "other defaults=%s",
        threshold_name, value, model_name, other_thresholds_at,
    )


# ---------------------------------------------------------------------------
# 2. Full process restart + readiness wait
# ---------------------------------------------------------------------------

def _kernel_status_ok(kernel_url: str, timeout_s: float = 2.0) -> bool:
    """Return True iff ``GET /status`` responds with status == 'ok'."""
    try:
        resp = requests.get(f"{kernel_url.rstrip('/')}/status", timeout=timeout_s)
    except requests.RequestException:
        return False
    if resp.status_code != 200:
        return False
    try:
        return resp.json().get("status") == "ok"
    except ValueError:
        return False


def restart_kernel_and_wait(
    aios_repo_dir: str | Path,
    kernel_url: str = "http://localhost:8000",
    timeout_s: float = 180.0,
    python_executable: str | None = None,
    stop_existing: bool = True,
) -> subprocess.Popen:
    """Stop any running kernel, start a fresh one, and wait until ready.

    Implements the confirmed requirement (Subtask 1) that a **full process
    restart** — not ``/core/refresh`` — is needed to pick up
    ``static_thresholds`` changes. Mirrors the manual polling pattern used in
    Subtasks 1 and 3: poll ``GET /status`` until it reports ``ok`` or the
    timeout elapses.

    Args:
        aios_repo_dir: AIOS repo root; the new process runs
            ``python -m runtime.launch`` with this as its cwd.
        kernel_url: Base URL to poll for readiness.
        timeout_s: Max seconds to wait for readiness.
        python_executable: Python to launch with. Defaults to the AIOS repo's
            ``.venv/bin/python`` when present, else ``"python"``.
        stop_existing: When True, terminate any process already bound to the
            kernel port before starting the new one.

    Returns:
        The started ``subprocess.Popen`` handle (caller owns its lifetime).

    Raises:
        KernelStartupError: If the kernel is not ready within ``timeout_s``.
    """
    aios_repo_dir = Path(aios_repo_dir)

    if stop_existing:
        _stop_existing_kernel(kernel_url)

    if python_executable is None:
        venv_py = aios_repo_dir / ".venv" / "bin" / "python"
        python_executable = str(venv_py) if venv_py.exists() else "python"

    logger.info(
        "Starting fresh kernel: %s -m runtime.launch (cwd=%s)",
        python_executable, aios_repo_dir,
    )
    proc = subprocess.Popen(
        [python_executable, "-m", "runtime.launch"],
        cwd=str(aios_repo_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise KernelStartupError(
                f"Kernel process exited early with code {proc.returncode} "
                f"before reporting ready."
            )
        if _kernel_status_ok(kernel_url):
            logger.info("Kernel ready at %s", kernel_url)
            return proc
        time.sleep(_STATUS_POLL_INTERVAL_S)

    # Timed out — clean up the process we spawned before raising.
    proc.terminate()
    raise KernelStartupError(
        f"Kernel did not report /status ok within {timeout_s:.0f}s at {kernel_url}."
    )


def _stop_existing_kernel(kernel_url: str) -> None:
    """Best-effort terminate a kernel already serving on the kernel port.

    Uses ``lsof`` to find the PID bound to the port and sends SIGTERM. Silent
    no-op when nothing is listening (fresh machine) or ``lsof`` is unavailable.
    """
    port = _port_from_url(kernel_url)
    if port is None:
        return
    try:
        out = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return
    pids = [p for p in out.stdout.split() if p.strip()]
    for pid in pids:
        try:
            subprocess.run(["kill", pid], timeout=10)
            logger.info("Sent SIGTERM to existing kernel pid=%s on port %s", pid, port)
        except subprocess.SubprocessError:
            pass
    if pids:
        # Give the port a moment to free before the caller starts a new proc.
        for _ in range(20):
            if not _kernel_status_ok(kernel_url, timeout_s=1.0):
                break
            time.sleep(0.5)


def _port_from_url(url: str) -> Optional[int]:
    m = re.search(r":(\d+)", url)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 3. Gating verification (the loud safety net)
# ---------------------------------------------------------------------------

def _fetch_gating_status(kernel_url: str, timeout_s: float = 10.0) -> dict:
    """GET /memory/gating_status and return the parsed dict.

    Raises:
        GatingVerificationError: On transport failure, non-200, or non-JSON.
    """
    url = f"{kernel_url.rstrip('/')}/memory/gating_status"
    try:
        resp = requests.get(url, timeout=timeout_s)
    except requests.RequestException as e:
        raise GatingVerificationError(
            f"Could not reach gating_status at {url}: {type(e).__name__}: {e}"
        ) from e
    if resp.status_code != 200:
        raise GatingVerificationError(
            f"gating_status at {url} returned HTTP {resp.status_code}; "
            f"body={resp.text[:300]!r}"
        )
    try:
        return resp.json()
    except ValueError as e:
        raise GatingVerificationError(
            f"gating_status at {url} returned non-JSON body: {resp.text[:300]!r}"
        ) from e


def verify_gating_status(
    expected_static_enabled: bool,
    expected_adaptive_enabled: bool,
    expected_thresholds: Dict[str, float],
    kernel_url: str = "http://localhost:8000",
    status: Optional[dict] = None,
    expected_override: Optional[tuple] = None,
) -> dict:
    """Assert the live kernel gating state matches what was written; else raise.

    Compares ``GET /memory/gating_status`` against the expected toggles, the
    expected per-threshold ``default`` values, and (optionally) the varied
    candidate's wildcard override. Any mismatch raises
    :class:`GatingVerificationError` with the full expected-vs-actual detail —
    it never silently continues (the safety net from the master prompt's
    non-goals).

    Args:
        expected_static_enabled: Required ``static_thresholds_enabled``.
        expected_adaptive_enabled: Required ``adaptive_policy_enabled``.
        expected_thresholds: Expected ``default`` per threshold name. Only the
            thresholds listed here are checked (against
            ``static_thresholds_config[<name>]["default"]``).
        kernel_url: Kernel base URL (ignored if ``status`` is supplied).
        status: Optional pre-fetched gating_status dict (used by tests to avoid
            a live call). When None, the status is fetched from ``kernel_url``.
        expected_override: Optional ``(threshold_name, model_name, value)`` —
            when given, the varied threshold's ``overrides`` must contain a
            wildcard entry for ``model_name`` with that ``value``. This
            confirms the actual candidate value (which lives in the override,
            not the ``default``) landed on the live kernel.

    Returns:
        The gating_status dict on success.

    Raises:
        GatingVerificationError: On any mismatch or fetch failure.
    """
    if status is None:
        status = _fetch_gating_status(kernel_url)

    mismatches: list[str] = []

    actual_static = status.get("static_thresholds_enabled")
    if actual_static != expected_static_enabled:
        mismatches.append(
            f"static_thresholds_enabled: expected {expected_static_enabled!r}, "
            f"got {actual_static!r}"
        )

    actual_adaptive = status.get("adaptive_policy_enabled")
    if actual_adaptive != expected_adaptive_enabled:
        mismatches.append(
            f"adaptive_policy_enabled: expected {expected_adaptive_enabled!r}, "
            f"got {actual_adaptive!r}"
        )

    cfg = status.get("static_thresholds_config") or {}
    for tname, expected_default in expected_thresholds.items():
        block = cfg.get(tname)
        if not isinstance(block, dict) or "default" not in block:
            mismatches.append(
                f"{tname}.default: expected {expected_default!r}, but no "
                f"default present in gating_status (block={block!r})"
            )
            continue
        actual_default = block["default"]
        try:
            close = abs(float(actual_default) - float(expected_default)) <= _FLOAT_TOL
        except (TypeError, ValueError):
            close = False
        if not close:
            mismatches.append(
                f"{tname}.default: expected {expected_default!r}, "
                f"got {actual_default!r}"
            )

    if expected_override is not None:
        ov_threshold, ov_model, ov_value = expected_override
        block = cfg.get(ov_threshold)
        overrides = block.get("overrides") if isinstance(block, dict) else None
        found = False
        if isinstance(overrides, list):
            for entry in overrides:
                if not isinstance(entry, dict):
                    continue
                if entry.get("llm_core") != ov_model:
                    continue
                # A wildcard override has no task_type (or an explicit null).
                if entry.get("task_type") not in (None, ""):
                    continue
                try:
                    if abs(float(entry.get("value")) - float(ov_value)) <= _FLOAT_TOL:
                        found = True
                        break
                except (TypeError, ValueError):
                    continue
        if not found:
            mismatches.append(
                f"{ov_threshold}.overrides: expected a wildcard entry "
                f"{{llm_core: {ov_model!r}, value: {ov_value!r}}}, "
                f"got overrides={overrides!r}"
            )

    if mismatches:
        raise GatingVerificationError(
            "Kernel gating state does not match the written candidate config:\n  - "
            + "\n  - ".join(mismatches)
            + f"\nFull gating_status: {status!r}"
        )

    logger.info(
        "Gating verified: static=%s adaptive=%s thresholds=%s",
        expected_static_enabled, expected_adaptive_enabled, expected_thresholds,
    )
    return status


# ---------------------------------------------------------------------------
# 4. Orchestrator: config → restart → verify
# ---------------------------------------------------------------------------

def apply_candidate_and_verify(
    candidate: CandidateConfig,
    config_path: str | Path,
    aios_repo_dir: str | Path,
    kernel_url: str = "http://localhost:8000",
    timeout_s: float = 180.0,
    python_executable: str | None = None,
) -> subprocess.Popen:
    """Apply one candidate config and return a verified-ready kernel process.

    The single building block a candidate-runner (later subtask) calls once per
    candidate BEFORE running trials:

    1. :func:`write_candidate_config` — surgical edit of the kernel config
       (static on, adaptive off, the varied wildcard override, held defaults).
    2. :func:`restart_kernel_and_wait` — full process restart + ``/status`` poll
       (required; ``/core/refresh`` does not apply threshold changes).
    3. :func:`verify_gating_status` — assert the live gating state matches what
       was written, raising loudly on any mismatch.

    Args:
        candidate: The candidate to apply.
        config_path: Path to the kernel's ``config.yaml``.
        aios_repo_dir: AIOS repo root (cwd for the launched kernel).
        kernel_url: Kernel base URL.
        timeout_s: Kernel readiness timeout.
        python_executable: Optional explicit Python for the kernel process.

    Returns:
        The started, verified-ready kernel ``subprocess.Popen`` handle.

    Raises:
        ConfigEditError, KernelStartupError, GatingVerificationError: as raised
            by the respective steps. On a verification mismatch the started
            kernel process is terminated before re-raising, so a bad candidate
            never leaves a stray kernel running.
    """
    # The default that all three thresholds' `default` slots should show is the
    # varied threshold's own value folded into other_thresholds_at plus the
    # held values. For verification we expect each threshold's `default` to be
    # whatever other_thresholds_at specified (defaults are the "held" values;
    # the varied model gets its value via the override, not the default).
    write_candidate_config(
        config_path=config_path,
        model_name=candidate.model_name,
        threshold_name=candidate.threshold_name,
        value=candidate.value,
        other_thresholds_at=candidate.other_thresholds_at,
    )

    proc = restart_kernel_and_wait(
        aios_repo_dir=aios_repo_dir,
        kernel_url=kernel_url,
        timeout_s=timeout_s,
        python_executable=python_executable,
    )

    try:
        verify_gating_status(
            expected_static_enabled=True,
            expected_adaptive_enabled=False,
            expected_thresholds=dict(candidate.other_thresholds_at),
            kernel_url=kernel_url,
            expected_override=(
                candidate.threshold_name,
                candidate.model_name,
                candidate.value,
            ),
        )
    except GatingVerificationError:
        # Don't leave a stray kernel running behind a failed candidate.
        proc.terminate()
        raise

    return proc


# ---------------------------------------------------------------------------
# 5. Candidate trial runner (run N trials, collect + average judge scores)
# ---------------------------------------------------------------------------

# Judge model for the threshold search. GPT-5.4 (azure) is used — the same
# high-quality judge the rest of the benchmark reporting uses — NOT the local
# qwen2.5:7b model used for the Subtask 3/4 smoke tests. Rationale: the search
# optimizes thresholds against a judge signal, so the signal must be as reliable
# as the one the final reporting run uses; a weak local judge would bias the
# search toward whatever the weak judge happens to reward. The smoke test below
# may override this with a local model purely to exercise wiring cheaply.
DEFAULT_SEARCH_JUDGE_MODEL = "gpt-5.4:azure"

# Per-trial judge score dimensions, in the order the harness averages them.
_JUDGE_SCORE_FIELDS = (
    "profile_usage_score",
    "task_usage_score",
    "integration_score",
)


class TrialRunError(RuntimeError):
    """Raised when the harness subprocess fails or its output can't be found
    or parsed. Distinct from gating/config errors so a runner failure is
    attributable to the trial batch, not the config/verify cycle."""


@dataclass
class CandidateTrialResult:
    """Structured outcome of scoring one candidate over a batch of trials.

    Carries enough detail to both drive the search (``batch_mean_score``) and
    debug any suspicious candidate later (raw file paths, per-trial rewards,
    counts). A bare float would lose the provenance needed to inspect a
    transcript when a score looks off.

    Attributes:
        model_name: The ``llm_core`` (assistant model) this batch scored.
        threshold_name: Gate being varied for this candidate.
        value: Candidate threshold value.
        num_trials_requested: ``--trials`` passed to the harness.
        num_trials_completed: Trials that were NOT ``failed`` and had at least
            one non-null judge score (i.e. contributed to the mean).
        num_trials_failed: Trials excluded from the mean (``failed: true`` or
            all-null scores). ``requested`` may exceed ``completed + failed``
            only if the harness wrote fewer trial records than requested.
        batch_mean_score: Mean over completed trials of each trial's own
            reward (mean of that trial's non-null scores). ``None`` when no
            trial completed (all failed) — the search must treat ``None`` as
            "no usable signal", never as 0.0.
        per_trial_rewards: The completed trials' per-trial reward values, in
            file order, for inspection.
        results_json_path: Absolute path to ``results_kernel_shared_tuned.json``.
        results_csv_path: Absolute path to ``results.csv`` (None if not written).
        output_dir: The batch's output directory.
    """

    model_name: str
    threshold_name: str
    value: float
    num_trials_requested: int
    num_trials_completed: int
    num_trials_failed: int
    batch_mean_score: Optional[float]
    per_trial_rewards: List[float]
    results_json_path: str
    results_csv_path: Optional[str]
    output_dir: str


def _trial_reward(trial: Dict[str, Any]) -> Optional[float]:
    """Compute one trial's reward: mean of its non-null judge scores.

    Mirrors the harness's own per-trial reward formula
    (``run_evaluation.py:462-469``): collect the non-null values among
    ``profile_usage_score`` / ``task_usage_score`` / ``integration_score`` and
    average them. Returns ``None`` when the trial has NO non-null score, so the
    caller can exclude it rather than fold a null-derived 0.0 into the mean.
    (Note: the harness records 0.0 for its own reward-report side-channel in the
    all-null case; for search aggregation we deliberately treat all-null as
    "no signal" = excluded, matching the failed-trial policy below.)
    """
    vals = [
        trial.get(f)
        for f in _JUDGE_SCORE_FIELDS
        if trial.get(f) is not None
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


def aggregate_judge_scores(
    results_json: Dict[str, Any],
) -> tuple[Optional[float], List[float], int, int]:
    """Aggregate per-trial judge scores from a parsed results JSON.

    Failed-trial policy (documented): a trial is EXCLUDED from the batch mean
    when it is marked ``failed: true`` OR has no non-null judge score. Excluded
    trials are counted in ``num_failed`` but never folded into the mean as 0.
    The batch mean is the mean of the surviving trials' per-trial rewards
    (each reward itself the mean of that trial's non-null scores). When no
    trial survives, the batch mean is ``None`` (no usable signal), never 0.0.

    Args:
        results_json: The parsed ``results_<method>.json`` structure, i.e. a
            dict with ``conditions: [{trials: [...]}, ...]``.

    Returns:
        ``(batch_mean, per_trial_rewards, num_completed, num_failed)``.
    """
    trials: List[Dict[str, Any]] = []
    for cond in results_json.get("conditions", []) or []:
        trials.extend(cond.get("trials", []) or [])

    # Rubric-version guard: the per-trial reward is a mean of raw judge scores,
    # and v1 (holistic [1,5]) and v2 (decomposed [0,5]) scores are on different
    # scales/instruments. Averaging a batch that mixes them — or comparing one
    # candidate's v1-scaled reward against another's v2-scaled reward during the
    # search — is meaningless. A normal search run is single-rubric (the harness
    # is invoked with a fixed --method and no rubric switching mid-run), so this
    # should always be a single version; refuse loudly if a results file ever
    # mixes them rather than silently misweighting. Trials without the field
    # (older results predating rubric_version) default to "v1".
    versions = {
        (t.get("rubric_version") or "v1")
        for t in trials
        if t.get("failed") is not True
    }
    if len(versions) > 1:
        raise TrialRunError(
            "results file mixes rubric versions "
            f"{sorted(versions)}; refusing to aggregate rewards across "
            "different judge scales. Aggregate each rubric_version separately."
        )

    per_trial_rewards: List[float] = []
    num_failed = 0
    for trial in trials:
        if trial.get("failed") is True:
            num_failed += 1
            continue
        reward = _trial_reward(trial)
        if reward is None:
            # Not flagged failed, but no usable score — exclude and count.
            num_failed += 1
            continue
        per_trial_rewards.append(reward)

    num_completed = len(per_trial_rewards)
    batch_mean = (
        sum(per_trial_rewards) / num_completed if num_completed else None
    )
    return batch_mean, per_trial_rewards, num_completed, num_failed


def parse_candidate_results(
    results_json_path: str | Path,
    model_name: str,
    threshold_name: str,
    value: float,
    num_trials_requested: int,
    results_csv_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> CandidateTrialResult:
    """Load a results JSON file and build a :class:`CandidateTrialResult`.

    Pure of subprocess/kernel concerns so it can be unit-tested against a
    fabricated fixture.

    Raises:
        TrialRunError: If the file is missing or not valid JSON.
    """
    path = Path(results_json_path)
    if not path.exists():
        raise TrialRunError(
            f"Harness did not produce expected results file: {path}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise TrialRunError(f"Could not read/parse results file {path}: {e}") from e

    batch_mean, rewards, completed, failed = aggregate_judge_scores(data)
    return CandidateTrialResult(
        model_name=model_name,
        threshold_name=threshold_name,
        value=value,
        num_trials_requested=num_trials_requested,
        num_trials_completed=completed,
        num_trials_failed=failed,
        batch_mean_score=batch_mean,
        per_trial_rewards=rewards,
        results_json_path=str(path.resolve()),
        results_csv_path=str(Path(results_csv_path).resolve()) if results_csv_path else None,
        output_dir=str(Path(output_dir).resolve()) if output_dir else str(path.parent.resolve()),
    )


def run_candidate_trials(
    model_name: str,
    model_backend: str,
    threshold_name: str,
    value: float,
    num_trials: int,
    output_dir: str | Path,
    run_id: str,
    kernel_url: str = "http://localhost:8000",
    judge_model: str = DEFAULT_SEARCH_JUDGE_MODEL,
    cerebrum_repo_dir: str | Path | None = None,
    python_executable: str | None = None,
    timeout_s: float = 3600.0,
) -> CandidateTrialResult:
    """Run N trials for one candidate against an already-verified live kernel.

    Invokes ``run_evaluation.py`` via subprocess with the exact flags confirmed
    in Subtask 3 (``docs/threshold-search-harness-invocation.md``):
    ``--trials N --method kernel_shared_tuned --assistant-model "<name>:<backend>"
    --judge-model <judge_model> --kernel-url <url> --output <dir> --run-id <id>
    --csv``. It does NOT configure or verify gating — the caller
    (:func:`apply_candidate_and_verify`, Subtask 4) must have already put the
    kernel into a verified-ready state.

    Args:
        model_name: Assistant ``llm_core`` name (e.g. ``"qwen2.5:7b"``). Must
            match the candidate whose override is live on the kernel.
        model_backend: Assistant backend (e.g. ``"ollama"``, ``"azure"``).
        threshold_name: Gate this candidate varies (recorded on the result).
        value: Candidate threshold value (recorded on the result).
        num_trials: Number of trials to run (``--trials``).
        output_dir: Directory for this batch's result files (should be unique
            per candidate so batches don't overwrite each other).
        run_id: ``--run-id`` for memory-namespace isolation (should be unique
            per candidate).
        kernel_url: Kernel base URL.
        judge_model: Judge model string; defaults to
            :data:`DEFAULT_SEARCH_JUDGE_MODEL` (GPT-5.4). Overridable for cheap
            local smoke tests.
        cerebrum_repo_dir: Repo root to run the subprocess from. Defaults to the
            repo containing this file.
        python_executable: Python to run the harness with. Defaults to
            ``sys.executable``.
        timeout_s: Max seconds for the whole trial batch.

    Returns:
        A :class:`CandidateTrialResult` with the batch mean and provenance.

    Raises:
        TrialRunError: If the subprocess fails (non-zero exit / timeout) or its
            output is missing/unparseable.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if cerebrum_repo_dir is None:
        # threshold_search.py lives at <repo>/benchmarks/shared_memory/, so the
        # repo root is three parents up.
        cerebrum_repo_dir = Path(__file__).resolve().parents[2]
    if python_executable is None:
        python_executable = sys.executable

    assistant_arg = f"{model_name}:{model_backend}"
    cmd = [
        python_executable,
        "benchmarks/shared_memory/run_evaluation.py",
        "--trials", str(num_trials),
        "--method", "kernel_shared_tuned",
        "--assistant-model", assistant_arg,
        "--judge-model", judge_model,
        "--kernel-url", kernel_url,
        "--output", str(output_dir),
        "--run-id", run_id,
        "--csv",
    ]
    logger.info("Running candidate trials: %s", " ".join(cmd))

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cerebrum_repo_dir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        raise TrialRunError(
            f"Trial batch timed out after {timeout_s:.0f}s "
            f"(model={model_name}, {threshold_name}={value})."
        ) from e

    if completed.returncode != 0:
        raise TrialRunError(
            f"Harness exited {completed.returncode} for candidate "
            f"model={model_name} {threshold_name}={value}.\n"
            f"stderr tail:\n{completed.stderr[-2000:]}"
        )

    results_json_path = output_dir / "results_kernel_shared_tuned.json"
    results_csv_path = output_dir / "results.csv"
    result = parse_candidate_results(
        results_json_path=results_json_path,
        model_name=model_name,
        threshold_name=threshold_name,
        value=value,
        num_trials_requested=num_trials,
        results_csv_path=results_csv_path if results_csv_path.exists() else None,
        output_dir=output_dir,
    )
    logger.info(
        "Candidate scored: model=%s %s=%s → batch_mean=%s "
        "(completed=%d, failed=%d, requested=%d) | results=%s",
        model_name, threshold_name, value, result.batch_mean_score,
        result.num_trials_completed, result.num_trials_failed,
        num_trials, result.results_json_path,
    )
    return result


# ---------------------------------------------------------------------------
# 6. Coordinate search loop
# ---------------------------------------------------------------------------
#
# Algorithm (per the master prompt), run INDEPENDENTLY for each model:
#
#   1. Search novelty_threshold over the candidate grid, holding
#      similarity+redundancy at BASELINE. Fix novelty at its winner.
#   2. Search similarity_threshold, holding novelty at its winner and
#      redundancy at BASELINE. Fix similarity at its winner.
#   3. Search redundancy_threshold, holding novelty+similarity at their winners.
#      Fix redundancy at its winner.
#
# The three winners for a model are its result. Models never share state. The
# "real" config.yaml is NOT written with any intermediate/candidate value —
# only after ALL models finish are the 9 winners written in one final step.
#
# Fixed search order (novelty → similarity → redundancy).
_SEARCH_ORDER = (
    "novelty_threshold",
    "similarity_threshold",
    "redundancy_threshold",
)

# Default candidate grid and per-candidate trial count (master-prompt spec).
DEFAULT_CANDIDATE_GRID = (0.5, 0.6, 0.7, 0.8, 0.9)
DEFAULT_TRIALS_PER_CANDIDATE = 8
# Baseline value each not-yet-searched threshold's `default` is held at.
DEFAULT_BASELINE_THRESHOLD = 0.7

# Target models for the full search (master-prompt spec).
DEFAULT_SEARCH_MODELS = ("gpt-4o", "llama3.1:8b", "qwen2.5:7b")

# Model → backend map for constructing the ``--assistant-model`` arg. Mirrors
# the active entries in the AIOS config.yaml (see
# docs/threshold-search-harness-invocation.md §3).
DEFAULT_MODEL_BACKENDS = {
    "gpt-4o": "azure",
    "llama3.1:8b": "ollama",
    "qwen2.5:7b": "ollama",
}


@dataclass
class CandidateAttempt:
    """One candidate value tried during a threshold search, with its score.

    History record (persisted by Subtask 7). ``batch_mean_score`` is ``None``
    for an all-failed batch — recorded, not dropped, so the full search is
    auditable.
    """

    threshold_name: str
    value: float
    batch_mean_score: Optional[float]
    num_trials_completed: int
    num_trials_failed: int
    results_json_path: Optional[str] = None


@dataclass
class CoordinateSearchState:
    """Mutable per-model search state — the unit Subtask 7 will persist.

    Attributes:
        model_name: The model this search is for.
        model_backend: Its assistant backend.
        winners: Threshold name → winning value, filled in as each step
            completes. A threshold not yet searched is absent.
        current_threshold: The threshold currently being searched, or None when
            not mid-step (before start / after all three done).
        history: Every candidate tried across all three steps, in order.
        completed: True once all three thresholds have a winner.
    """

    model_name: str
    model_backend: str
    winners: Dict[str, float] = field(default_factory=dict)
    current_threshold: Optional[str] = None
    history: List[CandidateAttempt] = field(default_factory=list)
    completed: bool = False

    def held_defaults(self, searching: str) -> Dict[str, float]:
        """Return the ``default`` values to hold while searching ``searching``.

        A gate already searched (in ``winners``) is held at its winner; every
        other gate (including the one being searched) is held at baseline. The
        varied gate's candidate value is applied via its override, not its
        default, so its held default is irrelevant to the candidate but is
        still written (baseline) for a clean, deterministic config.
        """
        held: Dict[str, float] = {}
        for tname in THRESHOLD_NAMES:
            if tname in self.winners:
                held[tname] = self.winners[tname]
            else:
                held[tname] = DEFAULT_BASELINE_THRESHOLD
        return held


def select_winner(
    attempts: List[CandidateAttempt],
) -> tuple[float, Optional[float]]:
    """Pick the winning candidate value from a step's attempts.

    Selection rule (explicit, not accidental):

    * **Highest ``batch_mean_score`` wins.**
    * **Tie-break:** the FIRST candidate (earliest in grid order) with the top
      score wins. We iterate in the order attempts were made and only replace
      the incumbent on a *strictly greater* score, so ties resolve to the
      lower grid index (typically the lower threshold value).
    * **None / all-failed candidates are treated as worst** (score ``-inf``),
      so they can never win when any scored candidate exists, but they are NOT
      dropped from ``attempts`` — they remain in history for audit.
    * **Degenerate case — every candidate is None:** no candidate produced a
      usable signal. Rather than crash, the FIRST attempted candidate is
      returned as the winner and the returned best-score is ``None`` so the
      caller can flag it. (This keeps the search progressing; the persisted
      history makes the degeneracy visible for later inspection.)

    Args:
        attempts: The step's candidate attempts, in the order tried
            (must be non-empty).

    Returns:
        ``(winning_value, winning_score)`` where ``winning_score`` is ``None``
        only in the all-None degenerate case.

    Raises:
        ValueError: If ``attempts`` is empty.
    """
    if not attempts:
        raise ValueError("select_winner requires at least one attempt")

    best_value: Optional[float] = None
    best_score = float("-inf")
    for a in attempts:
        score = a.batch_mean_score
        if score is None:
            continue
        if score > best_score:
            best_score = score
            best_value = a.value

    if best_value is None:
        # Every candidate was None — degenerate. Fall back to the first tried.
        return attempts[0].value, None
    return best_value, best_score


# A callable matching run_candidate_trials' signature, injectable for testing.
# (model_name, model_backend, threshold_name, value, num_trials, output_dir,
#  run_id, kernel_url) -> CandidateTrialResult
# and apply_candidate_and_verify-like: (CandidateConfig) -> proc (context).


def search_one_threshold(
    model_name: str,
    model_backend: str,
    threshold_name: str,
    other_thresholds_at: Dict[str, float],
    config_path: str | Path,
    aios_repo_dir: str | Path,
    output_root: str | Path,
    candidates=DEFAULT_CANDIDATE_GRID,
    trials_per_candidate: int = DEFAULT_TRIALS_PER_CANDIDATE,
    kernel_url: str = "http://localhost:8000",
    judge_model: str = DEFAULT_SEARCH_JUDGE_MODEL,
    run_id_prefix: str = "search",
    apply_fn=None,
    run_fn=None,
    state: Optional[CoordinateSearchState] = None,
    progress_log: Optional["ProgressLog"] = None,
    prior_attempts: Optional[Dict[float, CandidateAttempt]] = None,
) -> tuple[float, List[CandidateAttempt]]:
    """Search one threshold's candidate grid; return the winning value.

    For each candidate value: apply it (config edit → restart → verify) via
    ``apply_fn`` (default :func:`apply_candidate_and_verify`), then score it
    over ``trials_per_candidate`` trials via ``run_fn`` (default
    :func:`run_candidate_trials`). The kernel process started for a candidate
    is terminated before the next candidate, so at most one kernel runs at a
    time. The winner is chosen by :func:`select_winner` (highest batch mean;
    ties → first/lowest; None treated as worst).

    ``apply_fn``/``run_fn`` are injectable so the control flow can be
    unit-tested without any real kernel restart or trial (mocked in tests).

    Args:
        model_name / model_backend: The model under search.
        threshold_name: The gate to vary.
        other_thresholds_at: ``default`` values to hold for all gates (the
            varied gate's default is included but its candidate is applied via
            the override).
        config_path / aios_repo_dir: Passed to ``apply_fn``.
        output_root: Parent dir; each candidate gets a unique subdir.
        candidates: The candidate grid (default :data:`DEFAULT_CANDIDATE_GRID`).
        trials_per_candidate: Trials per candidate (default 8).
        kernel_url / judge_model: Passed through.
        run_id_prefix: Prefix for per-candidate run-ids/output dirs.
        apply_fn / run_fn: Injected for testing; default to the real primitives.
        state: Optional :class:`CoordinateSearchState` to record history onto.
        progress_log: Optional :class:`ProgressLog`; each newly-run candidate
            is appended to it immediately (incremental, crash-safe).
        prior_attempts: Optional map of ``value → CandidateAttempt`` recovered
            from a previous run. A candidate whose value is present here is
            SKIPPED (its persisted score is reused) — never re-run, so resume
            wastes no real trial time. Skipped attempts are NOT re-appended to
            the log (they are already on disk).

    Returns:
        ``(winning_value, attempts)``.
    """
    if apply_fn is None:
        apply_fn = apply_candidate_and_verify
    if run_fn is None:
        run_fn = run_candidate_trials

    output_root = Path(output_root)
    prior_attempts = prior_attempts or {}
    attempts: List[CandidateAttempt] = []

    if state is not None:
        state.current_threshold = threshold_name

    for value in candidates:
        # Resume: reuse a persisted attempt for this value; do not re-run.
        if value in prior_attempts:
            attempt = prior_attempts[value]
            logger.info(
                "Resume: reusing persisted candidate model=%s %s=%s "
                "(score=%s) — not re-running.",
                model_name, threshold_name, value, attempt.batch_mean_score,
            )
            attempts.append(attempt)
            if state is not None:
                state.history.append(attempt)
            continue

        candidate = CandidateConfig(
            model_name=model_name,
            threshold_name=threshold_name,
            value=value,
            other_thresholds_at=dict(other_thresholds_at),
        )
        # Unique per (model, threshold, value) so batches never collide.
        tag = f"{run_id_prefix}_{_sanitize(model_name)}_{threshold_name}_{_fmt_float(value)}"
        out_dir = output_root / tag

        logger.info(
            "Search step: model=%s %s=%s (holding %s)",
            model_name, threshold_name, value, other_thresholds_at,
        )
        proc = apply_fn(
            candidate=candidate,
            config_path=config_path,
            aios_repo_dir=aios_repo_dir,
            kernel_url=kernel_url,
        )
        try:
            result = run_fn(
                model_name=model_name,
                model_backend=model_backend,
                threshold_name=threshold_name,
                value=value,
                num_trials=trials_per_candidate,
                output_dir=out_dir,
                run_id=tag,
                kernel_url=kernel_url,
                judge_model=judge_model,
            )
        finally:
            # Always stop the candidate's kernel before the next candidate.
            _terminate_proc(proc)

        attempt = CandidateAttempt(
            threshold_name=threshold_name,
            value=value,
            batch_mean_score=result.batch_mean_score,
            num_trials_completed=result.num_trials_completed,
            num_trials_failed=result.num_trials_failed,
            results_json_path=result.results_json_path,
        )
        attempts.append(attempt)
        if state is not None:
            state.history.append(attempt)
        # Persist THIS candidate immediately (before moving on), so a crash
        # loses at most this candidate's successor, never this one.
        if progress_log is not None:
            progress_log.append_attempt(model_name, model_backend, attempt)

    winning_value, winning_score = select_winner(attempts)
    logger.info(
        "Winner for model=%s %s: value=%s score=%s",
        model_name, threshold_name, winning_value, winning_score,
    )
    return winning_value, attempts


def search_one_model(
    model_name: str,
    config_path: str | Path,
    aios_repo_dir: str | Path,
    output_root: str | Path,
    model_backend: Optional[str] = None,
    candidates=DEFAULT_CANDIDATE_GRID,
    trials_per_candidate: int = DEFAULT_TRIALS_PER_CANDIDATE,
    kernel_url: str = "http://localhost:8000",
    judge_model: str = DEFAULT_SEARCH_JUDGE_MODEL,
    apply_fn=None,
    run_fn=None,
    progress_log: Optional["ProgressLog"] = None,
    resume_state: Optional[CoordinateSearchState] = None,
    all_states: Optional[Dict[str, "CoordinateSearchState"]] = None,
) -> CoordinateSearchState:
    """Run the full three-step coordinate search for one model.

    Order is fixed: novelty → similarity → redundancy. Each step holds
    already-won gates at their winners and not-yet-searched gates at baseline,
    threading winners forward. Returns the completed
    :class:`CoordinateSearchState` (winners + full history). Does NOT write the
    real config — persistence of the winners is the caller's final step.

    Resume: when ``resume_state`` is supplied (from :func:`load_progress`), any
    threshold it already has a winner for is SKIPPED entirely, and the
    in-progress threshold reuses its already-attempted candidates (only the
    remaining grid values are actually run).

    Args:
        model_name: The model to search.
        model_backend: Its backend; defaults from
            :data:`DEFAULT_MODEL_BACKENDS` (falls back to ``"ollama"``).
        progress_log: Optional log; passed to each threshold step so candidates
            persist incrementally, and rewritten as a summary after each step.
        resume_state: Optional recovered state for this model to resume from.
        all_states: Optional dict of all models' states (for the summary
            checkpoint spanning every model); defaults to just this model.
        (others as in :func:`search_one_threshold`.)

    Returns:
        The completed :class:`CoordinateSearchState` for this model.
    """
    if model_backend is None:
        model_backend = DEFAULT_MODEL_BACKENDS.get(model_name, "ollama")

    # Seed from recovered state (winners already fixed carry over verbatim).
    if resume_state is not None:
        state = resume_state
        state.model_backend = state.model_backend or model_backend
    else:
        state = CoordinateSearchState(model_name=model_name, model_backend=model_backend)

    # Prior attempts recovered per threshold, for resuming the in-progress one.
    prior_by_threshold: Dict[str, Dict[float, CandidateAttempt]] = {}
    for a in state.history:
        prior_by_threshold.setdefault(a.threshold_name, {})[a.value] = a

    for threshold_name in _SEARCH_ORDER:
        # Already-won threshold (from a prior run): skip entirely.
        if threshold_name in state.winners:
            logger.info(
                "Resume: model=%s %s already won at %s — skipping step.",
                model_name, threshold_name, state.winners[threshold_name],
            )
            continue

        held = state.held_defaults(searching=threshold_name)
        winning_value, _attempts = search_one_threshold(
            model_name=model_name,
            model_backend=model_backend,
            threshold_name=threshold_name,
            other_thresholds_at=held,
            config_path=config_path,
            aios_repo_dir=aios_repo_dir,
            output_root=output_root,
            candidates=candidates,
            trials_per_candidate=trials_per_candidate,
            kernel_url=kernel_url,
            judge_model=judge_model,
            apply_fn=apply_fn,
            run_fn=run_fn,
            state=state,
            progress_log=progress_log,
            prior_attempts=prior_by_threshold.get(threshold_name),
        )
        # Thread this step's winner forward into subsequent steps.
        state.winners[threshold_name] = winning_value
        # Checkpoint the summary after each threshold milestone (atomic write).
        if progress_log is not None:
            snapshot = dict(all_states) if all_states is not None else {}
            snapshot[model_name] = state
            progress_log.write_summary(snapshot)

    state.current_threshold = None
    state.completed = True
    logger.info("Model %s search complete. Winners: %s", model_name, state.winners)
    return state


def run_full_search(
    config_path: str | Path,
    aios_repo_dir: str | Path,
    output_root: str | Path,
    search_run_id: str,
    models=DEFAULT_SEARCH_MODELS,
    model_backends: Optional[Dict[str, str]] = None,
    candidates=DEFAULT_CANDIDATE_GRID,
    trials_per_candidate: int = DEFAULT_TRIALS_PER_CANDIDATE,
    kernel_url: str = "http://localhost:8000",
    judge_model: str = DEFAULT_SEARCH_JUDGE_MODEL,
    apply_fn=None,
    run_fn=None,
    write_final: bool = True,
    resume: bool = True,
    progress_root: str | Path | None = None,
) -> Dict[str, CoordinateSearchState]:
    """Search all models independently, then write the 9 winners ONCE.

    Each model is searched with its own :class:`CoordinateSearchState`
    (no cross-model state). Only AFTER every model completes are the collected
    winners written to the real ``config.yaml`` — in a single
    :func:`write_final_overrides` call — so no intermediate/candidate value is
    ever persisted mid-search.

    Resume (default): when ``resume=True`` the run first calls
    :func:`load_progress` for ``search_run_id``. A fully-completed model is
    skipped entirely (its recovered winners are kept); a partially-completed
    model resumes — already-won thresholds skipped, the in-progress threshold's
    already-attempted candidates reused (only remaining grid values run). A
    candidate whose result is already on disk is NEVER re-run.

    Args:
        config_path / aios_repo_dir / output_root: search plumbing.
        search_run_id: Identifier for the progress log dir (enables resume).
        models: Models to search (default :data:`DEFAULT_SEARCH_MODELS`).
        model_backends: Optional overrides for model→backend.
        candidates / trials_per_candidate / kernel_url / judge_model: passthrough.
        apply_fn / run_fn: injected for testing.
        write_final: When True (default), write the winners to the real config
            after all models finish. Tests pass False to assert timing without
            touching a real file.
        resume: When True (default), load and resume from prior progress.
        progress_root: Override the progress-log root (tests).

    Returns:
        Model name → its completed :class:`CoordinateSearchState`.
    """
    model_backends = model_backends or DEFAULT_MODEL_BACKENDS
    progress_log = ProgressLog(search_run_id, progress_root=progress_root)

    recovered: Dict[str, CoordinateSearchState] = {}
    if resume:
        recovered = load_progress(
            search_run_id, progress_root=progress_root, candidates=candidates,
        )
        if recovered:
            logger.info(
                "Resuming search %s: recovered state for models %s",
                search_run_id, list(recovered.keys()),
            )

    states: Dict[str, CoordinateSearchState] = {}

    for model_name in models:
        backend = model_backends.get(model_name, "ollama")
        recovered_state = recovered.get(model_name)

        # Fully-completed model: skip entirely, keep recovered winners.
        if recovered_state is not None and recovered_state.completed:
            logger.info(
                "Resume: model=%s already fully complete (winners=%s) — skipping.",
                model_name, recovered_state.winners,
            )
            states[model_name] = recovered_state
            continue

        states[model_name] = search_one_model(
            model_name=model_name,
            model_backend=backend,
            config_path=config_path,
            aios_repo_dir=aios_repo_dir,
            output_root=output_root,
            candidates=candidates,
            trials_per_candidate=trials_per_candidate,
            kernel_url=kernel_url,
            judge_model=judge_model,
            apply_fn=apply_fn,
            run_fn=run_fn,
            progress_log=progress_log,
            resume_state=recovered_state,
            all_states=states,
        )

    # Exactly-once final persistence, only after ALL models are done.
    if write_final:
        winners_by_model = {m: s.winners for m, s in states.items()}
        write_final_overrides(config_path, winners_by_model)
        logger.info("Final config written with winners: %s", winners_by_model)

    return states


def write_final_overrides(
    config_path: str | Path,
    winners_by_model: Dict[str, Dict[str, float]],
) -> None:
    """Persist the multi-model search winners into the real ``config.yaml``.

    For each threshold, writes one wildcard override per model that has a
    winner for it: ``[{llm_core: <model>, value: <v>}, ...]``. Sets
    ``static_thresholds.enabled: true`` / ``adaptive_policy.enabled: false``
    (the tuned regime) and leaves each threshold's ``default`` untouched.
    Surgical, format-preserving editing (same approach as
    :func:`write_candidate_config`) — this is the ONE persisted write at the
    end of :func:`run_full_search`, never called per-candidate.

    Args:
        config_path: Path to the kernel's ``config.yaml``.
        winners_by_model: model → {threshold_name → winning value}.

    Raises:
        ConfigEditError: If an expected block/line cannot be located.
    """
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")

    text = _replace_block_toggle(text, "static_thresholds", "enabled", "true")
    text = _replace_block_toggle(text, "adaptive_policy", "enabled", "false")

    # Build, per threshold, the list of wildcard overrides across all models.
    for tname in THRESHOLD_NAMES:
        entries = []
        for model_name, winners in winners_by_model.items():
            if tname in winners:
                entries.append(
                    f'{{llm_core: "{model_name}", value: {_fmt_float(winners[tname])}}}'
                )
        overrides_literal = "[" + ", ".join(entries) + "]"
        text = _set_threshold(
            text, tname, default_value=None, overrides_literal=overrides_literal
        )

    path.write_text(text, encoding="utf-8")


def _sanitize(name: str) -> str:
    """Filesystem-safe token from a model name (e.g. 'qwen2.5:7b' → 'qwen2.5_7b')."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _terminate_proc(proc) -> None:
    """Best-effort stop of a kernel process handle returned by apply_fn.

    Tolerates a None / mock handle (tests inject fakes) — only calls
    ``terminate``/``wait`` when present.
    """
    if proc is None:
        return
    terminate = getattr(proc, "terminate", None)
    if callable(terminate):
        try:
            terminate()
            wait = getattr(proc, "wait", None)
            if callable(wait):
                wait(timeout=15)
        except Exception:  # noqa: BLE001 - cleanup must not mask search errors
            kill = getattr(proc, "kill", None)
            if callable(kill):
                try:
                    kill()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# 7. Crash-safe incremental progress logging + resume
# ---------------------------------------------------------------------------
#
# On-disk layout, under ``benchmarks/shared_memory/threshold_search_progress/
# <search_run_id>/``:
#
#   attempts.jsonl   Append-only. One JSON object per COMPLETED candidate
#                    attempt (model, threshold, value, batch_mean_score, trial
#                    counts, results path, timestamp). Written + flushed +
#                    fsync'd immediately after each candidate's trials finish,
#                    so a crash loses at most the single in-flight candidate,
#                    never earlier candidates in the same threshold. Append-only
#                    JSONL is inherently crash-safe: a hard kill mid-write can
#                    only corrupt the final partial line, which the reader
#                    tolerates (see _read_jsonl_tolerant) — every prior line is
#                    intact.
#
#   summary.json     A convenience checkpoint rewritten ATOMICALLY (write temp
#                    then os.replace) after each threshold winner is fixed:
#                    per-model winners + which thresholds are "done". Atomic
#                    replace means a crash mid-write leaves either the old or
#                    the new complete file, never a corrupt one. summary.json is
#                    NOT the source of truth for resume — attempts.jsonl is
#                    (it is finer-grained and updated first). The summary just
#                    speeds inspection and records the completed/winner view.
#
# Resume is driven from attempts.jsonl: winners are recomputed deterministically
# from the recorded attempts via select_winner, so resume never depends on the
# summary having been written before a crash.

_PROGRESS_ROOT_NAME = "threshold_search_progress"


def default_progress_root() -> Path:
    """Return ``<repo>/benchmarks/shared_memory/threshold_search_progress``."""
    return Path(__file__).resolve().parent / _PROGRESS_ROOT_NAME


class ProgressLog:
    """Crash-safe, append-only progress log for one search run.

    One instance per ``search_run_id``. Call :meth:`append_attempt` after every
    candidate completes (incrementally) and :meth:`write_summary` after each
    threshold/model milestone. The attempts file is the resume source of truth.
    """

    def __init__(self, search_run_id: str, progress_root: str | Path | None = None):
        root = Path(progress_root) if progress_root else default_progress_root()
        self.dir = root / search_run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.attempts_path = self.dir / "attempts.jsonl"
        self.summary_path = self.dir / "summary.json"
        self.search_run_id = search_run_id

    def append_attempt(
        self, model_name: str, model_backend: str, attempt: CandidateAttempt
    ) -> None:
        """Append one completed candidate attempt, flushed + fsync'd to disk.

        Append-only + fsync means this candidate's record survives an immediate
        hard kill, and a kill *during* this write can only truncate this one
        line (tolerated on read) — earlier candidates are already durable.
        """
        record = {
            "model_name": model_name,
            "model_backend": model_backend,
            "threshold_name": attempt.threshold_name,
            "value": attempt.value,
            "batch_mean_score": attempt.batch_mean_score,
            "num_trials_completed": attempt.num_trials_completed,
            "num_trials_failed": attempt.num_trials_failed,
            "results_json_path": attempt.results_json_path,
            "ts": time.time(),
        }
        line = json.dumps(record) + "\n"
        # Open in append mode, write, flush, fsync — durable before returning.
        with open(self.attempts_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def write_summary(self, states: Dict[str, "CoordinateSearchState"]) -> None:
        """Atomically (temp + os.replace) rewrite the summary checkpoint.

        Records per-model winners, completed thresholds, and completion flag.
        A crash mid-write leaves either the previous or the new complete file.
        """
        summary = {
            "search_run_id": self.search_run_id,
            "updated_ts": time.time(),
            "models": {
                m: {
                    "model_backend": s.model_backend,
                    "winners": dict(s.winners),
                    "completed_thresholds": [
                        t for t in _SEARCH_ORDER if t in s.winners
                    ],
                    "completed": s.completed,
                }
                for m, s in states.items()
            },
        }
        tmp_path = self.summary_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.summary_path)


def _read_jsonl_tolerant(path: Path) -> List[dict]:
    """Read a JSONL file, skipping a trailing partial/corrupt final line.

    Every fully-written line parses; a hard kill mid-append can only leave the
    LAST line partial, which is silently dropped (with a warning) so the rest
    of the recovered history is usable.
    """
    if not path.exists():
        return []
    records: List[dict] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            # Only the final line may legitimately be a torn write.
            if i == len(lines) - 1:
                logger.warning(
                    "Dropping torn final line in %s (crash mid-write); "
                    "%d prior records recovered.", path, len(records),
                )
            else:
                logger.warning(
                    "Skipping unparseable line %d in %s.", i, path,
                )
    return records


def load_progress(
    search_run_id: str,
    progress_root: str | Path | None = None,
    candidates=DEFAULT_CANDIDATE_GRID,
) -> Dict[str, CoordinateSearchState]:
    """Reconstruct per-model :class:`CoordinateSearchState` from disk.

    Rebuilds state purely from ``attempts.jsonl`` (the finer-grained,
    crash-safe source of truth): groups attempts by model, replays them in the
    fixed threshold order, and — for any threshold whose full candidate grid
    has been attempted — fixes its winner via :func:`select_winner` and threads
    it forward. A model is ``completed`` when all three thresholds have a
    winner. The in-progress threshold and its already-attempted candidate values
    are recoverable from each state's ``history``.

    Returns an empty dict when there is no log for ``search_run_id`` (fresh run).

    Args:
        search_run_id: The run whose progress to load.
        progress_root: Override the progress root (tests). Defaults to
            :func:`default_progress_root`.
        candidates: The candidate grid a threshold must have fully attempted to
            count as "done" (must match the search's grid).

    Returns:
        model name → reconstructed :class:`CoordinateSearchState`.
    """
    full_grid = set(candidates)
    root = Path(progress_root) if progress_root else default_progress_root()
    attempts_path = root / search_run_id / "attempts.jsonl"
    records = _read_jsonl_tolerant(attempts_path)

    # Group attempts by model, preserving append order.
    by_model: Dict[str, List[dict]] = {}
    backends: Dict[str, str] = {}
    for r in records:
        m = r.get("model_name")
        if m is None:
            continue
        by_model.setdefault(m, []).append(r)
        if r.get("model_backend"):
            backends[m] = r["model_backend"]

    states: Dict[str, CoordinateSearchState] = {}
    for model_name, recs in by_model.items():
        state = CoordinateSearchState(
            model_name=model_name,
            model_backend=backends.get(model_name, "ollama"),
        )
        # Rebuild history and, per threshold, the attempts made for it.
        per_threshold: Dict[str, List[CandidateAttempt]] = {}
        for r in recs:
            attempt = CandidateAttempt(
                threshold_name=r["threshold_name"],
                value=r["value"],
                batch_mean_score=r.get("batch_mean_score"),
                num_trials_completed=r.get("num_trials_completed", 0),
                num_trials_failed=r.get("num_trials_failed", 0),
                results_json_path=r.get("results_json_path"),
            )
            state.history.append(attempt)
            per_threshold.setdefault(r["threshold_name"], []).append(attempt)

        # Replay in fixed order: a threshold with a FULL grid of attempts has a
        # fixed winner; the first threshold lacking a full grid is in-progress.
        for tname in _SEARCH_ORDER:
            attempts_for_t = per_threshold.get(tname, [])
            # Dedupe by value keeping the LAST recorded (a resumed re-run of the
            # same candidate would append again; last wins).
            latest_by_value: Dict[float, CandidateAttempt] = {}
            for a in attempts_for_t:
                latest_by_value[a.value] = a
            attempted_values = set(latest_by_value.keys())
            if attempted_values >= full_grid:
                winning_value, _ = select_winner(list(latest_by_value.values()))
                state.winners[tname] = winning_value
            else:
                # First incomplete threshold: this is where resume continues.
                state.current_threshold = tname if attempts_for_t else None
                break

        state.completed = all(t in state.winners for t in _SEARCH_ORDER)
        if state.completed:
            state.current_threshold = None
        states[model_name] = state

    return states
