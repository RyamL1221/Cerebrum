"""The pilot report's regression fixture (NeurIPS Subtask 20): Subtask
11's pilot read on each score, the stored hybrid, the keyword score and
the second judge's LLM score, from the second judge's re-judge of it
(``s20_rejudge/claude-sonnet-5.5/pilot_v1_hetero``: the stored records
with the judge's record added, which give the hybrid and keyword
renderings of ``pilot_v1_hetero`` itself byte for byte), trimmed to the
fields ``pilot_analysis`` reads.

    PYTHONPATH=. python tests/agents/fixtures/pilot_runs/make_fixtures.py

(from the Cerebrum checkout, with the runs under ``results/``). As
``fixtures/ablation_runs/make_fixtures.py`` (whose recording dict and
trim it uses): it runs the report on the full records with every key it
reads recorded, keeps only those keys, writes one ``.tar.xz``
beside this file, and checks the report on the trimmed records
reproduces each committed rendering (``results/s20_rejudge/
pilot_report/``) byte for byte.
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

from benchmarks.shared_memory import pilot_analysis as report

HERE = Path(__file__).resolve().parent
RESULTS = Path("results")
EXPECTED = RESULTS / "s20_rejudge" / "pilot_report"
# fixture name: (root under results/, [(rendering, report arguments)])
ROOTS = {
    "pilot_v1_hetero": ("s20_rejudge/claude-sonnet-5.5/pilot_v1_hetero", [
        ("hybrid", ["--score", "hybrid"]),
        ("keyword", ["--score", "keyword"]),
        ("llm_claude-sonnet-5.5",
         ["--score", "llm", "--judge", "claude-sonnet-5.5"])]),
}

_spec = importlib.util.spec_from_file_location(
    "ablation_fixtures", HERE.parent / "ablation_runs" / "make_fixtures.py")
recording = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recording)


def files(root):
    return sorted((RESULTS / root).glob("*/*/*/results_*.json"))


def render(root, out, name, args):
    report.main([str(root), *args, "--markdown", str(out / f"{name}.md"),
                 "--json", str(out / f"{name}.json")])


def recorded_load(root):
    """``report.load`` with every trial and metadata dict recording what
    is read (paths rooted at ``trials`` and ``metadata``)."""
    cells, metadata = {}, {}
    for key, path in _cell_paths(root):
        data = json.loads(path.read_text())
        trials = recording.wrap(data["conditions"][0]["trials"],
                                ("trials",))
        cells[key] = {t["trial_index"]: t for t in trials}
        metadata[key] = recording.wrap(data["experiment_metadata"],
                                       ("metadata",))
    return cells, metadata


def _cell_paths(root):
    for model in report.MODELS:
        for (locus, backend) in report.CELLS:
            for level in report.LEVELS:
                path = report.cell_file(root, model, locus, backend, level)
                if path.exists():
                    yield (model, locus, backend, level), path


def rescore_in_place(cells, source, judge=None):
    """``report.rescore`` writing the scores into the recorded trials
    (its ``{**trial}`` copy would read every key)."""
    if source == "hybrid":
        return cells
    for trials in cells.values():
        for trial in trials.values():
            if trial.get("failed"):
                continue
            if source == "keyword":
                values = report.trial_keyword_scores(trial)
            else:
                values = (((trial.get("judges") or {}).get(judge) or {})
                          .get("llm") or {})
            for d, field in report.DIMENSIONS.items():
                dict.__setitem__(trial, field, values.get(d))
    return cells


def record(root, renders):
    with tempfile.TemporaryDirectory() as tmp:
        for name, args in renders:
            loaded = recorded_load(RESULTS / root)
            with patch.object(report, "load", return_value=loaded), \
                    patch.object(report, "rescore", rescore_in_place):
                render(RESULTS / root, Path(tmp), name, args)


def write(fixture, root):
    target = HERE / f"{fixture}.tar.xz"
    with tarfile.open(target, "w:xz",
                      preset=9 | lzma.PRESET_EXTREME) as archive:
        for path in files(root):
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
                str(Path(fixture) / path.relative_to(RESULTS / root)))
            info.size, info.mtime, info.mode = len(raw), 0, 0o644
            archive.addfile(info, io.BytesIO(raw))
    return target


def reproduces(fixture, renders, archive_path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archive_path) as archive:
            archive.extractall(tmp)
        out = Path(tmp) / "out"
        out.mkdir()
        ok = True
        for name, args in renders:
            render(Path(tmp) / fixture, out, name, args)
            for suffix in (".md", ".json"):
                same = ((out / f"{name}{suffix}").read_bytes()
                        == (EXPECTED / f"{name}{suffix}").read_bytes())
                print(fixture, name + suffix,
                      "identical" if same else "DIFFERS")
                ok &= same
        return ok


def main() -> int:
    for fixture, (root, renders) in ROOTS.items():
        recording.READ.clear()
        record(root, renders)
        archive = write(fixture, root)
        ok = reproduces(fixture, renders, archive)
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
