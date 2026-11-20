"""The decision probe's regression fixtures (NeurIPS Subtask 20): the
results files of the functional check (``decision_functional_s20``) and
the no-memory check over every user (``decision_nomemory150_s20``),
trimmed to the fields ``bench_v2_analysis`` reads.

    PYTHONPATH=. python tests/agents/fixtures/decision_runs/make_fixtures.py

(from the Cerebrum checkout, with the two runs under ``results/``). As
``fixtures/ablation_runs/make_fixtures.py`` (whose recording dict and
trim it uses): it runs the analysis on the full records with every key
it reads recorded, keeps only those keys, writes one ``.tar.xz`` per run
beside this file, and checks the analysis on the trimmed records
reproduces the run's committed ``analysis.md`` byte for byte and
``analysis.json`` exactly.
"""
import importlib.util
import io
import json
import lzma
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from benchmarks.shared_memory import bench_v2_analysis as analysis

RUNS = ("decision_functional_s20", "decision_nomemory150_s20")
HERE = Path(__file__).resolve().parent
RESULTS = Path("results")
ARGS = ["--no-criteria"]  # as each run's PROVENANCE.md rendered it

_spec = importlib.util.spec_from_file_location(
    "ablation_fixtures", HERE.parent / "ablation_runs" / "make_fixtures.py")
recording = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recording)


def files(run):
    return sorted((RESULTS / run).glob("*/*/*/results_*.json"))


def render(root, out):
    analysis.main([str(root), *ARGS, "--markdown", str(out / "analysis.md"),
                   "--json", str(out / "analysis.json")])


def record(run):
    """Run the analysis on ``run``'s records, recording what it reads
    (paths rooted at a cell: ``trials`` and ``metadata``)."""
    cells = {key: recording.wrap(cell, ())
             for key, cell in analysis.load(RESULTS / run).items()}
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(analysis, "load", return_value=cells):
        render(RESULTS / run, Path(tmp))


def write(run):
    target = HERE / f"{run}.tar.xz"
    with tarfile.open(target, "w:xz",
                      preset=9 | lzma.PRESET_EXTREME) as archive:
        for path in files(run):
            data = json.loads(path.read_text())
            trimmed = {
                "conditions": [{"trials": recording.trim(
                    data["conditions"][0]["trials"], ("trials",))}],
                "experiment_metadata": recording.trim(
                    data["experiment_metadata"], ("metadata",)),
            }
            raw = json.dumps(trimmed, separators=(",", ":"),
                             sort_keys=True).encode()
            info = tarfile.TarInfo(
                str(Path(run) / path.relative_to(RESULTS / run)))
            info.size, info.mtime, info.mode = len(raw), 0, 0o644
            archive.addfile(info, io.BytesIO(raw))
    return target


def reproduces(run, archive_path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archive_path) as archive:
            archive.extractall(tmp)
        out = Path(tmp) / "out"
        out.mkdir()
        render(Path(tmp) / run, out)
        ok = True
        for name in ("analysis.md", "analysis.json"):
            same = ((out / name).read_bytes()
                    == (RESULTS / run / name).read_bytes())
            print(run, name, "identical" if same else "DIFFERS")
            ok &= same
        return ok


def main() -> int:
    for run in RUNS:
        record(run)
    ok = True
    for run in RUNS:
        ok &= reproduces(run, write(run))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
