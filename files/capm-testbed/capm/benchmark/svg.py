"""Tiny dependency-free SVG charting (no matplotlib needed).

Just enough to render the paper's figures from saved results: grouped bar
charts, line charts, and scatter plots. Output is a self-contained SVG string
that renders in any browser or embeds in HTML/Markdown.
"""

from __future__ import annotations

from typing import Sequence

_W, _H = 640, 360
_PADL, _PADR, _PADT, _PADB = 70, 20, 40, 70
_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2"]


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _frame(title: str) -> list:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{_H}" '
        f'font-family="sans-serif" font-size="13">',
        f'<rect width="{_W}" height="{_H}" fill="white"/>',
        f'<text x="{_W/2}" y="22" text-anchor="middle" font-size="15" '
        f'font-weight="bold">{_esc(title)}</text>',
    ]


def _axes(parts, ymax, ylabel):
    x0, y0, x1, y1 = _PADL, _H - _PADB, _W - _PADR, _PADT
    parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="#333"/>')
    parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#333"/>')
    for k in range(6):
        v = ymax * k / 5
        y = y0 - (y0 - y1) * k / 5
        parts.append(f'<line x1="{x0-4}" y1="{y:.1f}" x2="{x0}" y2="{y:.1f}" stroke="#333"/>')
        parts.append(f'<text x="{x0-8}" y="{y+4:.1f}" text-anchor="end" '
                     f'fill="#555">{v:.2g}</text>')
    parts.append(f'<text x="18" y="{(y0+y1)/2:.1f}" text-anchor="middle" fill="#555" '
                 f'transform="rotate(-90 18 {(y0+y1)/2:.1f})">{_esc(ylabel)}</text>')
    return x0, y0, x1, y1


def bar_chart(title: str, labels: Sequence[str], values: Sequence[float],
              ylabel: str = "value", ymax: float | None = None) -> str:
    parts = _frame(title)
    ymax = ymax or (max(values) * 1.15 if values else 1.0) or 1.0
    x0, y0, x1, y1 = _axes(parts, ymax, ylabel)
    n = len(values)
    bw = (x1 - x0) / max(1, n) * 0.6
    for i, (lab, v) in enumerate(zip(labels, values)):
        cx = x0 + (x1 - x0) * (i + 0.5) / n
        h = (y0 - y1) * (v / ymax)
        parts.append(f'<rect x="{cx-bw/2:.1f}" y="{y0-h:.1f}" width="{bw:.1f}" '
                     f'height="{h:.1f}" fill="{_COLORS[i % len(_COLORS)]}"/>')
        parts.append(f'<text x="{cx:.1f}" y="{y0-h-5:.1f}" text-anchor="middle" '
                     f'fill="#222">{v:.2f}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{y0+16:.1f}" text-anchor="middle" '
                     f'fill="#444" font-size="11" '
                     f'transform="rotate(20 {cx:.1f} {y0+16:.1f})">{_esc(lab)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def line_chart(title: str, xs: Sequence[float], ys: Sequence[float],
               xlabel: str = "x", ylabel: str = "y", ymax: float | None = None) -> str:
    parts = _frame(title)
    ymax = ymax or (max(ys) * 1.15 if ys else 1.0) or 1.0
    xmin, xmax = min(xs), max(xs)
    x0, y0, x1, y1 = _axes(parts, ymax, ylabel)

    def px(x):
        return x0 + (x1 - x0) * (x - xmin) / (xmax - xmin or 1)

    def py(y):
        return y0 - (y0 - y1) * (y / ymax)
    pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys))
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{_COLORS[0]}" '
                 f'stroke-width="2.5"/>')
    for x, y in zip(xs, ys):
        parts.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.5" '
                     f'fill="{_COLORS[0]}"/>')
        parts.append(f'<text x="{px(x):.1f}" y="{y0+16:.1f}" text-anchor="middle" '
                     f'fill="#444" font-size="11">{x:g}</text>')
    parts.append(f'<text x="{(x0+x1)/2:.1f}" y="{_H-18}" text-anchor="middle" '
                 f'fill="#555">{_esc(xlabel)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def scatter(title: str, points: Sequence[tuple], xlabel: str, ylabel: str,
            xmax: float | None = None, ymax: float | None = None) -> str:
    parts = _frame(title)
    xs = [p[0] for p in points] or [0]
    ys = [p[1] for p in points] or [0]
    xmax = xmax or max(xs) * 1.1 or 1
    ymax = ymax or max(ys) * 1.1 or 1
    x0, y0, x1, y1 = _axes(parts, ymax, ylabel)
    for x, y in points:
        cx = x0 + (x1 - x0) * (x / xmax)
        cy = y0 - (y0 - y1) * (y / ymax)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" '
                     f'fill="{_COLORS[0]}" fill-opacity="0.7"/>')
    parts.append(f'<text x="{(x0+x1)/2:.1f}" y="{_H-18}" text-anchor="middle" '
                 f'fill="#555">{_esc(xlabel)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)
