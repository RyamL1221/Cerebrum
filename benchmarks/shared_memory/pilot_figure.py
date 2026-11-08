"""Draft headline figure of the pilot (NeurIPS Subtask 11, AIOS
docs/PILOT.md): the kernel - replicated gap vs. heterogeneity level H,
one line per backend (and the pooled gap the rule uses, dashed), per
model and judge dimension, with 95% CIs. Plain SVG, no plotting library.

    python -m benchmarks.shared_memory.pilot_figure results/pilot_v1_hetero \\
        --output results/pilot_v1_hetero/gap_vs_h.svg
"""
import argparse
from pathlib import Path
from typing import List

from benchmarks.shared_memory import pilot_analysis as pa

SERIES = (  # scope, label, color, dashed
    ("mem0", "Mem0", "#2a78d6", False),
    ("inhouse", "In-house", "#eb6834", False),
    ("pooled", "Pooled (rule)", "#52514e", True),
)
MODEL_LABELS = {"qwen": "Qwen-2.5:7B", "gpt4o": "GPT-4o"}
DIM_LABELS = {"profile": "Profile", "integration": "Integration"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
PANEL_W, PANEL_H = 300, 210
LEFT, TOP, GAP_X, GAP_Y = 64, 96, 46, 56
PLOT_L, PLOT_R, PLOT_T, PLOT_B = 44, 92, 26, 34


def series(cells, model, dimension, scope) -> List[dict]:
    backends = pa.BACKENDS if scope == "pooled" else (scope,)
    return [pa.gap(cells, model, "replicated", h, dimension, backends)
            for h in pa.LEVELS]


def _range(values) -> tuple:
    low = min(values + [0.0])
    high = max(values + [0.0])
    pad = max(0.15, (high - low) * 0.1)
    return low - pad, high + pad


def _ticks(low, high) -> List[float]:
    step = 0.25 if high - low <= 2.5 else 0.5
    start = step * int(low / step - (low < 0))
    out, value = [], start
    while value <= high + 1e-9:
        if value >= low - 1e-9:
            out.append(round(value, 2))
        value += step
    return out


def svg(cells) -> str:
    data = {
        (m, d, s): series(cells, m, d, s)
        for m in pa.MODELS for d in pa.PRIMARY for s, *_ in SERIES
    }
    bounds = [v for points in data.values() for p in points
              for v in (p["ci_low"], p["ci_high"]) if v is not None]
    low, high = _range(bounds) if bounds else (-1.0, 1.0)
    width = LEFT + 2 * PANEL_W + GAP_X + 20
    height = TOP + 2 * PANEL_H + GAP_Y + 30
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        'font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        f'<rect width="100%" height="100%" fill="{SURFACE}"/>',
        f'<text x="{LEFT}" y="26" font-size="15" font-weight="600" '
        f'fill="{INK}">Kernel − replicated gap vs. heterogeneity '
        '(draft)</text>',
        f'<text x="{LEFT}" y="44" font-size="11.5" fill="{MUTED}">Paired '
        'difference in judge score (1–5) over pilot_v1’s 30 users; '
        'whiskers are 95% t-intervals.</text>',
        f'<text x="{LEFT}" y="59" font-size="11.5" fill="{MUTED}">Above 0: '
        'the kernel serves the consumer better than the replicated '
        'library.</text>',
    ]
    # Legend, one row above the panels.
    x = LEFT
    for _, label, color, dashed in SERIES:
        dash = ' stroke-dasharray="5 3"' if dashed else ""
        out.append(f'<line x1="{x}" y1="76" x2="{x + 22}" y2="76" '
                   f'stroke="{color}" stroke-width="2"{dash}/>')
        out.append(f'<circle cx="{x + 11}" cy="76" r="4" fill="{color}" '
                   f'stroke="{SURFACE}" stroke-width="2"/>')
        out.append(f'<text x="{x + 28}" y="80" font-size="11.5" '
                   f'fill="{INK}">{label}</text>')
        x += 40 + 7 * len(label)
    for col, model in enumerate(pa.MODELS):
        for row, dimension in enumerate(pa.PRIMARY):
            ox = LEFT + col * (PANEL_W + GAP_X)
            oy = TOP + row * (PANEL_H + GAP_Y)
            pl, pr = ox + PLOT_L, ox + PANEL_W - PLOT_R + 70
            pt, pb = oy + PLOT_T, oy + PANEL_H - PLOT_B

            def y_of(value):
                return pb - (value - low) / (high - low) * (pb - pt)

            def x_of(level, offset=0.0):
                return pl + 18 + level * (pr - pl - 36) / 2 + offset

            out.append(
                f'<text x="{ox}" y="{oy + 12}" font-size="12.5" '
                f'font-weight="600" fill="{INK}">'
                f'{MODEL_LABELS[model]} · {DIM_LABELS[dimension]}</text>')
            for tick in _ticks(low, high):
                ty = y_of(tick)
                color = MUTED if tick == 0 else GRID
                out.append(f'<line x1="{pl}" y1="{ty:.1f}" x2="{pr}" '
                           f'y2="{ty:.1f}" stroke="{color}" '
                           f'stroke-width="1"/>')
                out.append(f'<text x="{pl - 6}" y="{ty + 4:.1f}" '
                           f'font-size="10.5" text-anchor="end" '
                           f'fill="{MUTED}">{tick:+.2f}</text>')
            for level in pa.LEVELS:
                out.append(f'<text x="{x_of(level):.1f}" y="{pb + 18}" '
                           f'font-size="10.5" text-anchor="middle" '
                           f'fill="{MUTED}">H = {level}</text>')
            for k, (scope, label, color, dashed) in enumerate(SERIES):
                points = data[(model, dimension, scope)]
                offset = (k - 1) * 7
                coords = [(x_of(h, offset), y_of(p["mean"]))
                          for h, p in zip(pa.LEVELS, points)
                          if p["mean"] is not None]
                if len(coords) > 1:
                    dash = ' stroke-dasharray="5 3"' if dashed else ""
                    path = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in coords)
                    out.append(f'<polyline points="{path}" fill="none" '
                               f'stroke="{color}" stroke-width="2"{dash}/>')
                for h, p in zip(pa.LEVELS, points):
                    if p["mean"] is None:
                        continue
                    cx = x_of(h, offset)
                    out.append(
                        f'<line x1="{cx:.1f}" y1="{y_of(p["ci_low"]):.1f}" '
                        f'x2="{cx:.1f}" y2="{y_of(p["ci_high"]):.1f}" '
                        f'stroke="{color}" stroke-width="1.5" '
                        'stroke-linecap="round"/>')
                    out.append(
                        f'<circle cx="{cx:.1f}" cy="{y_of(p["mean"]):.1f}" '
                        f'r="4" fill="{color}" stroke="{SURFACE}" '
                        f'stroke-width="2"><title>{label}, H = {h}: '
                        f'{p["mean"]:+.2f} [{p["ci_low"]:+.2f}, '
                        f'{p["ci_high"]:+.2f}], n = {p["n"]}</title>'
                        '</circle>')
    # No end-of-line labels: the three series end within a few hundredths
    # of each other at H = 2, so labels collide; the legend names them.
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    cells, _ = pa.load(Path(args.root))
    Path(args.output).write_text(svg(cells))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
