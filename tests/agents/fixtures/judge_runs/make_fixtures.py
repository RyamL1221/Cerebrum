"""The reliability report's regression fixture (NeurIPS Subtask 20): the
second judge's 2,002 judgments of ``calibration_v1``
(``results/judge_reliability_s20/claude-sonnet-5.5.jsonl``) without the
judge's reasoning text, which the report does not read.

    PYTHONPATH=. python tests/agents/fixtures/judge_runs/make_fixtures.py

(from the Cerebrum checkout). Writes ``claude-sonnet-5.5.jsonl.xz``
beside this file and checks ``judge_reliability report`` on it
reproduces the committed ``report_claude_only.md`` and ``.json`` byte
for byte.
"""
import json
import lzma
import sys
import tempfile
from pathlib import Path

from benchmarks.shared_memory import judge_reliability

HERE = Path(__file__).resolve().parent
RUN = Path("results") / "judge_reliability_s20"
SET = Path("benchmarks/shared_memory/data/calibration_v1.jsonl")
NAME = "claude-sonnet-5.5.jsonl"


def write() -> Path:
    rows = [json.loads(line) for line in (RUN / NAME).read_text()
            .splitlines() if line.strip()]
    text = "".join(json.dumps({k: v for k, v in row.items()
                               if k != "reasoning"}, sort_keys=True) + "\n"
                   for row in rows)
    target = HERE / f"{NAME}.xz"
    target.write_bytes(lzma.compress(text.encode(),
                                     preset=9 | lzma.PRESET_EXTREME))
    return target


def reproduces(archive: Path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        judgments = Path(tmp) / NAME
        judgments.write_bytes(lzma.decompress(archive.read_bytes()))
        md, js = Path(tmp) / "report.md", Path(tmp) / "report.json"
        judge_reliability.main(["report", "--set", str(SET), "--judgments",
                                str(judgments), "--md", str(md),
                                "--json", str(js)])
        ok = True
        for out, name in ((md, "report_claude_only.md"),
                          (js, "report_claude_only.json")):
            same = out.read_bytes() == (RUN / name).read_bytes()
            print(name, "identical" if same else "DIFFERS")
            ok &= same
        return ok


if __name__ == "__main__":
    sys.exit(0 if reproduces(write()) else 1)
