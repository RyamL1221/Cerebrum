"""A-MEM is pinned to one commit in this venv too (NeurIPS Subtask 17,
AIOS docs/AMEM_BACKEND.md, "Versions and setup"): the native and
replicated agents run in this venv, and the A-MEM they run must be the
commit requirements-amem.txt names, the kernel's (AIOS
tests/environment/test_amem_pin.py checks the AIOS venv)."""
import json
import re
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/WujiangXu/A-mem-sys"


def test_this_venv_has_the_pinned_commit():
    from cerebrum.utils import amem

    text = (ROOT / "requirements-amem.txt").read_text()
    match = re.search(
        r"^agentic-memory\s*@\s*git\+(\S+)@([0-9a-f]{40})", text, re.M)
    assert match and match.group(1) == REPO
    commit = match.group(2)
    assert commit == amem.PINNED_COMMIT
    installed = json.loads(metadata.distribution(
        "agentic-memory").read_text("direct_url.json") or "{}")
    assert installed.get("url") in (REPO, REPO + ".git")
    assert (installed.get("vcs_info") or {}).get("commit_id") == commit
    assert amem.versions()["agentic_memory"] == commit
