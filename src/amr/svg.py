"""Hand-written SVG. No plotting library, no CSS variables, no runtime dependency.

Two figures: the compact conformance matrix (``amr matrix --svg``) and the contamination
bar chart (``amr contamination``). Both are meant to be dropped into a poster or a README
and to survive being opened by something that is not a browser, so every colour is a
literal hex value and every glyph position is computed here.

Colours are fixed, in one place, because the matrix is the argument: PASS and DIVERGENCE
must not be confusable at two metres, and DIVERGENCE must not read as failure.
"""

from __future__ import annotations

INK = "#12181f"
MUTED = "#5c6773"
PAPER = "#ffffff"
GRID = "#d7dde4"

PASS_FILL = "#1f7a4d"
DIVERGENCE_FILL = "#b3541e"
FAIL_FILL = "#a11d2b"
MISSING_FILL = "#5c6773"

OUTCOME_FILL = {
    "PASS": PASS_FILL,
    "DIVERGENCE": DIVERGENCE_FILL,
    "FAIL": FAIL_FILL,
}

UNGATED_FILL = "#a11d2b"
GATED_FILL = "#1f7a4d"

FONT = "'DejaVu Sans','Helvetica Neue',Helvetica,Arial,sans-serif"
MONO = "'DejaVu Sans Mono',Menlo,Consolas,monospace"


def escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text(
    x: float,
    y: float,
    body: str,
    size: int = 14,
    fill: str = INK,
    anchor: str = "start",
    weight: str = "normal",
    family: str = FONT,
) -> str:
    return (
        f'<text x="{_n(x)}" y="{_n(y)}" font-family="{family}" font-size="{size}" '
        f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">'
        f"{escape(body)}</text>"
    )


def rect(x: float, y: float, width: float, height: float, fill: str, rx: int = 3) -> str:
    return (
        f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(width)}" height="{_n(height)}" '
        f'rx="{rx}" fill="{fill}"/>'
    )


def line(x1: float, y1: float, x2: float, y2: float, stroke: str = GRID) -> str:
    return (
        f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
        f'stroke="{stroke}" stroke-width="1"/>'
    )


def document(width: float, height: float, body: list[str], title: str) -> str:
    """One SVG file. Deterministic: no timestamps, no ids, no generated names."""
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(width)}" '
        f'height="{_n(height)}" viewBox="0 0 {_n(width)} {_n(height)}" '
        f'role="img" aria-label="{escape(title)}">'
    )
    return "\n".join(
        [
            head,
            f"<title>{escape(title)}</title>",
            rect(0, 0, width, height, PAPER, rx=0),
            *body,
            "</svg>",
            "",
        ]
    )


def _n(value: float) -> str:
    """Numbers with no trailing ``.0``, so two runs cannot differ in formatting."""
    rounded = round(float(value), 2)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)
