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

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

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
