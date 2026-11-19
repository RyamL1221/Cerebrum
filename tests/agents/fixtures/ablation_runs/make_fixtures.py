"""The ablation report's regression fixtures (NeurIPS Subtask 19): the
results files of the functional check (f19b) and the smoke (s19),
trimmed to the fields ``ablation_report`` reads.

    PYTHONPATH=. python tests/agents/fixtures/ablation_runs/make_fixtures.py

(from the Cerebrum checkout, with the two runs under ``results/``). It
runs the report on the full records with every key it reads recorded,
keeps only those keys (a value the report reaches but never looks
inside, or compares whole, is kept whole), writes one ``.tar.xz`` per
run beside this file, and checks the report on the trimmed records
reproduces the run's committed ``analysis.md``, ``analysis.json`` and
``contribution.svg`` byte for byte.
"""
import io
import json
import lzma
import sys
import tarfile
import tempfile
from pathlib import Path

from benchmarks.shared_memory import ablation_report as report

RUNS = ("ablation_functional_f19b", "ablation_smoke_s19")
HERE = Path(__file__).resolve().parent
RESULTS = Path("results")
READ = set()  # the paths the report read; "[]" stands for a list item


def wrap(value, path):
    if isinstance(value, dict):
        return Recorded(value, path)
    if isinstance(value, list):
        return [wrap(v, path + ("[]",)) for v in value]
    return value


class Recorded(dict):
    """A dict that records every key read from it."""

    def __init__(self, d, path):
        super().__init__()
        self._path = path
        for k, v in d.items():
            dict.__setitem__(self, k, wrap(v, path + (k,)))

    def _read(self, key):
        READ.add(self._path + (key,))

    def __getitem__(self, k):
        self._read(k)
        return dict.__getitem__(self, k)

    def get(self, k, default=None):
        self._read(k)
        return dict.get(self, k, default)

    def __contains__(self, k):
        self._read(k)
        return dict.__contains__(self, k)

    def keys(self):
        self._read("*")
        return dict.keys(self)

    def items(self):
        self._read("*")
        return dict.items(self)

    def values(self):
        self._read("*")
        return dict.values(self)

    def __iter__(self):
        self._read("*")
        return dict.__iter__(self)

    def __eq__(self, other):
        self._read("=")
        return dict.__eq__(self, other)

    __hash__ = None


def trim(value, path):
    """``value`` with only what the report read under ``path``."""
    n = len(path)
    deeper = any(len(p) > n and p[:n] == path for p in READ)
    if not deeper or path + ("=",) in READ:
        return value
    if isinstance(value, dict):
        every = path + ("*",) in READ
        return {k: trim(v, path + (k,)) for k, v in value.items()
                if every or path + (k,) in READ}
    if isinstance(value, list):
        return [trim(v, path + ("[]",)) for v in value]
    return value


def files(run):
    return sorted((RESULTS / run).glob("*/*/*/results_*.json"))


def record(run):
    """Run the report on ``run``'s records, recording what it reads
    (paths rooted at a cell's trials, as ``load`` hands them on)."""
    cells = {key: wrap(trials, ())
             for key, trials in report.load(RESULTS / run).items()}
    table = report.rows(cells)
    report.outcome_rows(cells)
    report.functional_checks(cells)
    report.record_checks(cells)
    report.smoke_checks(table)
    from benchmarks.shared_memory.ablation_figure import contribution_svg
    contribution_svg(table)


def write(run):
    target = HERE / f"{run}.tar.xz"
    with tarfile.open(target, "w:xz",
                      preset=9 | lzma.PRESET_EXTREME) as archive:
        for path in files(run):
            trials = json.loads(path.read_text())["conditions"][0]["trials"]
            data = json.dumps({"conditions": [{"trials": trim(trials, ())}]},
                              separators=(",", ":"), sort_keys=True).encode()
            info = tarfile.TarInfo(
                str(Path(run) / path.relative_to(RESULTS / run)))
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            archive.addfile(info, io.BytesIO(data))
    return target


def reproduces(run, archive_path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archive_path) as archive:
            archive.extractall(tmp)
        out = Path(tmp) / "out"
        out.mkdir()
        report.main([str(Path(tmp) / run), "--md", str(out / "analysis.md"),
                     "--json", str(out / "analysis.json"),
                     "--svg", str(out / "contribution.svg")])
        ok = True
        for name in ("analysis.md", "analysis.json", "contribution.svg"):
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
