"""The Graphiti tests' ``load_env`` copies ``NEO4J_*`` from AIOS/.env and
nothing else (AIOS known issue 51): the file also holds the Azure key,
which no test process needs. No value is printed."""
import os

from tests.agents import _graphiti_script as script


def test_load_env_copies_the_neo4j_names_only(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "NEO4J_URI=bolt://127.0.0.1:1\n"
        "NEO4J_USER=from-file\n"
        "AZURE_API_KEY=not-a-real-key-0123456789\n"
        "# NEO4J_PASSWORD=commented-out\n")
    monkeypatch.setattr(script, "AIOS_ROOT", tmp_path)
    for name in ("NEO4J_URI", "NEO4J_PASSWORD", "AZURE_API_KEY"):
        monkeypatch.setenv(name, "x")  # restored after the test
        monkeypatch.delenv(name)
    monkeypatch.setenv("NEO4J_USER", "from-caller")
    script.load_env()
    assert os.environ["NEO4J_URI"] == "bolt://127.0.0.1:1"
    assert os.environ["NEO4J_USER"] == "from-caller"
    assert "AZURE_API_KEY" not in os.environ
    assert "NEO4J_PASSWORD" not in os.environ
