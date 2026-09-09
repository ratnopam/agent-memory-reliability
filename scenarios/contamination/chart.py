"""The one figure the simulation produces: two panels, three bars each.

Left panel is ``inherited_fraction`` — writes descended from the 0.40 belief. Right panel
is ``inflated_fraction`` — writes declared at or above 0.9 whose effective confidence sat
at or below ``tau``. Three bars per panel, one per arm, values printed on the bars.

Hand-written SVG through ``amr.svg``, so the file has no dependency, no timestamp, and no
generated identifier, and two runs of the same seed produce the same bytes.
"""

from __future__ import annotations

from amr import svg

WIDTH = 880
HEIGHT = 412
TOP = 130
BOTTOM = 360
BAR_WIDTH = 74
GAP = 96
#: Left edge of each panel's axis. The second panel starts far enough right that the
#: longest tick label cannot collide with the first panel's last bar.
PANEL_LEFT = (96, 528)
PANEL_WIDTH = 320

TICKS = (0.0, 0.25, 0.5, 0.75, 1.0)
#: Ungated red, gated green, and surfaced amber between them — the same three-way reading
#: as the matrix, where the middle colour is "measured, not clean".
FILL = {
    "ungated": svg.UNGATED_FILL,
    "surfaced": svg.SURFACED_FILL,
    "gated": svg.GATED_FILL,
}
ARMS = ("ungated", "surfaced", "gated")

PANELS = (
    ("inherited", "Inherited the 0.40 belief", "inherited_fraction", "inherited_count"),
    ("inflated", "Declared ≥ 0.9, effective ≤ tau", "inflated_fraction", "inflated_count"),
)

#: The honest caption. Hand-wrapped, because the SVG has no text-layout engine and the
#: break has to be chosen by someone; joined with spaces for the summary table and
#: results/README.md, so all three say it the same way. The gated bar is a boundary, not a
#: result, and a reader should not have to work that out for themselves.
CAPTION_LINES = (
    (
        "gated is zero by construction at tau={tau}: the injected belief and every "
        "descendant are bounded at 0.40 and"
    ),
    (
        "cannot be cited. The gated bar demonstrates the boundary; the surfaced bar "
        "measures what visibility alone achieves."
    ),
)


def caption_lines(tau: float) -> tuple[str, ...]:
    return tuple(line.format(tau=tau) for line in CAPTION_LINES)


def caption(tau: float) -> str:
    """One line, for the Markdown table and the results README."""
    return " ".join(caption_lines(tau))


def inherited_chart(document: dict) -> str:
    """Both metrics, all three arms. Named for the metric the poster leads with."""
    tau = document["parameters"]["tau"]
    body = [
        svg.text(
            PANEL_LEFT[0] - 48,
            36,
            "How far one low-confidence belief travels",
            size=19,
            weight="bold",
        ),
        svg.text(
            PANEL_LEFT[0] - 48,
            58,
            f"reference · seed {document['seed']} · "
            f"{document['parameters']['rounds']} rounds · three roles · tau {tau}",
            size=12,
            fill=svg.MUTED,
            family=svg.MONO,
        ),
    ]
    body.extend(_subtitle(tau))

    for index, (_, heading, fraction_key, count_key) in enumerate(PANELS):
        body.extend(
            _panel(document, PANEL_LEFT[index], heading, fraction_key, count_key)
        )
    return svg.document(WIDTH, HEIGHT, body, "contamination: two metrics, three arms")


def _subtitle(tau: float) -> list[str]:
    return [
        svg.text(PANEL_LEFT[0] - 48, 84 + 16 * offset, line, size=11, fill=svg.MUTED)
        for offset, line in enumerate(caption_lines(tau))
    ]


def _panel(
    document: dict, left: int, heading: str, fraction_key: str, count_key: str
) -> list[str]:
    body = [svg.text(left, TOP - 14, heading, size=13, weight="bold")]
    right = left + PANEL_WIDTH
    height = BOTTOM - TOP

    for tick in TICKS:
        y = BOTTOM - height * tick
        body.append(svg.line(left, y, right, y))
        body.append(
            svg.text(left - 10, y + 4, f"{tick:.0%}", size=11, fill=svg.MUTED, anchor="end")
        )

    for index, name in enumerate(ARMS):
        arm = document["arms"][name]
        fraction = arm[fraction_key]
        x = left + 16 + GAP * index
        bar = height * fraction
        if bar > 0:
            body.append(svg.rect(x, BOTTOM - bar, BAR_WIDTH, bar, FILL[name]))
        centre = x + BAR_WIDTH / 2
        # Zero, or a bar too short to hold a label, prints the value above the axis
        # instead of inside the bar. Every bar is labelled either way.
        inside = bar > 30
        body.append(
            svg.text(
                centre,
                BOTTOM - bar + (22 if inside else -8),
                f"{fraction:.0%}",
                size=15,
                fill=svg.PAPER if inside else svg.INK,
                anchor="middle",
                weight="bold",
            )
        )
        body.append(
            svg.text(centre, BOTTOM + 22, name, size=13, anchor="middle", weight="bold")
        )
        body.append(
            svg.text(
                centre,
                BOTTOM + 38,
                f"{arm[count_key]} of {arm['denominator']}",
                size=10,
                fill=svg.MUTED,
                anchor="middle",
            )
        )

    body.append(svg.line(left, BOTTOM, right, BOTTOM, stroke=svg.INK))
    return body
