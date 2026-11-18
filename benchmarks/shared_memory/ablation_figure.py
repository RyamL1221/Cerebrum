"""The kernel ablations' contribution figure (NeurIPS Subtask 19, AIOS
docs/ABLATION.md, "Analysis"): one horizontal bar per component, the
paired difference (ablated minus full kernel) of its primary measure,
with its 95% interval as a whisker.

The measures have different units (late writes, rows, probes failed,
tokens), so each row is a small multiple on its own axis, symmetric
about 0, and is labelled with its measure; no two rows share a scale.
One series, one hue (the reference palette's first slot, validated
light and dark); text in ink, never the series colour. Each bar carries
a ``<title>`` (the hover tooltip) with the full and ablated means. A
draft for the paper: the values are the report's rows, unchanged.
"""
from html import escape
from typing import List

WIDTH = 900
LABEL_W = 330      # the component and measure
PLOT_W = 300       # each row's own axis
VALUE_W = WIDTH - LABEL_W - PLOT_W
ROW_H = 46
TOP = 56
BAR_H = 12

STYLE = """
.viz-root { --surface-1: #fcfcfb; --text-primary: #0b0b0b;
  --text-secondary: #52514e; --grid: #e4e3df; --series-1: #2a78d6; }
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .viz-root {
    --surface-1: #1a1a19; --text-primary: #f0efec;
    --text-secondary: #c3c2b7; --grid: #3a3a37; --series-1: #3987e5; }
}
:root[data-theme="dark"] .viz-root { --surface-1: #1a1a19;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --grid: #3a3a37;
  --series-1: #3987e5; }
.viz-root text { font-family: -apple-system, "Helvetica Neue", Arial,
  sans-serif; }
.label { font-size: 13px; fill: var(--text-primary); }
.sub { font-size: 11px; fill: var(--text-secondary); }
.value { font-size: 12px; fill: var(--text-primary);
  font-variant-numeric: tabular-nums; }
.title { font-size: 15px; font-weight: 600; fill: var(--text-primary); }
.zero { stroke: var(--text-secondary); stroke-width: 1; }
.track { stroke: var(--grid); stroke-width: 1; }
.bar { fill: var(--series-1); }
.whisker { stroke: var(--text-primary); stroke-width: 2;
  stroke-linecap: round; }
"""


def _bar_path(x0: float, x1: float, y: float) -> str:
    """A bar from the zero line ``x0`` to ``x1``, its data end rounded
    (4 px), its baseline end square."""
    r = min(4.0, abs(x1 - x0) / 2, BAR_H / 2)
    top, bottom = y - BAR_H / 2, y + BAR_H / 2
    if x1 >= x0:
        return (f"M{x0:.1f},{top:.1f} H{x1 - r:.1f} "
                f"Q{x1:.1f},{top:.1f} {x1:.1f},{top + r:.1f} "
                f"V{bottom - r:.1f} Q{x1:.1f},{bottom:.1f} "
                f"{x1 - r:.1f},{bottom:.1f} H{x0:.1f} Z")
    return (f"M{x0:.1f},{top:.1f} H{x1 + r:.1f} "
            f"Q{x1:.1f},{top:.1f} {x1:.1f},{top + r:.1f} "
            f"V{bottom - r:.1f} Q{x1:.1f},{bottom:.1f} "
            f"{x1 + r:.1f},{bottom:.1f} H{x0:.1f} Z")


def _fmt(value) -> str:
    return "-" if value is None else f"{value:+.2f}"


def contribution_svg(table: List[dict]) -> str:
    """The figure for the report's rows: the primary measure of each
    switch and condition (a row with no pairs is drawn as "no data")."""
    rows = [r for r in table if r.get("primary")]
    height = TOP + ROW_H * max(len(rows), 1) + 24
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="viz-root" '
        f'width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'role="img" aria-label="What each kernel component is worth">',
        f"<style>{STYLE}</style>",
        f'<rect width="{WIDTH}" height="{height}" '
        f'fill="var(--surface-1)"/>',
        '<text class="title" x="16" y="24">What each kernel component is '
        "worth</text>",
        '<text class="sub" x="16" y="42">Paired difference, component '
        "removed minus full kernel (95% interval); each row on its own "
        "axis</text>",
    ]
    if not rows:
        parts.append(f'<text class="sub" x="16" y="{TOP + 20}">no paired '
                     "cells</text>")
    for i, row in enumerate(rows):
        y = TOP + ROW_H * i + ROW_H / 2
        zero = LABEL_W + PLOT_W / 2
        name = f"{row['switch']}: {row['value']}"
        parts.append(f'<text class="label" x="16" y="{y - 4:.1f}">'
                     f"{escape(name)}</text>")
        parts.append(f'<text class="sub" x="16" y="{y + 12:.1f}">'
                     f"{escape(row['measure'])} ({escape(row['condition'])}"
                     f", n {row.get('n', 0)})</text>")
        parts.append(f'<line class="track" x1="{LABEL_W}" '
                     f'x2="{LABEL_W + PLOT_W}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<line class="zero" x1="{zero:.1f}" x2="{zero:.1f}" '
                     f'y1="{y - BAR_H:.1f}" y2="{y + BAR_H:.1f}"/>')
        diff, ci = row.get("diff"), row.get("ci")
        if diff is None:
            parts.append(f'<text class="sub" x="{zero + 8:.1f}" '
                         f'y="{y + 4:.1f}">no data</text>')
            continue
        ends = [abs(diff)] + ([abs(c) for c in ci] if ci else [])
        span = max(max(ends) * 1.1, 1e-9)
        scale = (PLOT_W / 2 - 6) / span

        def x(value: float) -> float:
            return zero + value * scale

        tip = (f"{name}, {row['measure']} ({row['condition']}): full "
               f"{row.get('full'):.2f}, ablated {row.get('ablated'):.2f}, "
               f"difference {_fmt(diff)}"
               + (f" [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else ""))
        parts.append(f'<g><title>{escape(tip)}</title>'
                     f'<rect x="{LABEL_W}" y="{y - ROW_H / 2 + 2:.1f}" '
                     f'width="{PLOT_W}" height="{ROW_H - 4}" '
                     f'fill="transparent"/>')
        if abs(x(diff) - zero) >= 0.5:
            parts.append(f'<path class="bar" '
                         f'd="{_bar_path(zero, x(diff), y)}"/>')
        if ci:
            lo, hi = x(ci[0]), x(ci[1])
            parts.append(
                f'<line class="whisker" x1="{lo:.1f}" x2="{hi:.1f}" '
                f'y1="{y:.1f}" y2="{y:.1f}"/>'
                f'<line class="whisker" x1="{lo:.1f}" x2="{lo:.1f}" '
                f'y1="{y - 5:.1f}" y2="{y + 5:.1f}"/>'
                f'<line class="whisker" x1="{hi:.1f}" x2="{hi:.1f}" '
                f'y1="{y - 5:.1f}" y2="{y + 5:.1f}"/>')
        parts.append("</g>")
        interval = f" [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else ""
        parts.append(f'<text class="value" x="{LABEL_W + PLOT_W + 12}" '
                     f'y="{y + 4:.1f}">{_fmt(diff)}{interval}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
