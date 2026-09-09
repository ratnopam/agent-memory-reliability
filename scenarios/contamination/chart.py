"""The one figure the simulation produces: two bars, ungated against gated.

Hand-written SVG through ``amr.svg``, so the file has no dependency, no timestamp, and no
generated identifier, and two runs of the same seed produce the same bytes.
"""

from __future__ import annotations

from amr import svg

WIDTH = 560
HEIGHT = 380
LEFT = 90
BOTTOM = 300
TOP = 70
BAR_WIDTH = 110
GAP = 150

TICKS = (0.0, 0.25, 0.5, 0.75, 1.0)
FILL = {"ungated": svg.UNGATED_FILL, "gated": svg.GATED_FILL}


def inherited_chart(document: dict) -> str:
    """``inherited_fraction`` per arm: writes descended from the 0.40 belief."""
    tau = document["parameters"]["tau"]
    body = [
        svg.text(
            LEFT - 42,
            34,
            "Writes inheriting the low-confidence belief",
            size=18,
            weight="bold",
        ),
        svg.text(
            LEFT - 42,
            54,
            f"reference · seed {document['seed']} · "
            f"{document['parameters']['rounds']} rounds · three roles · tau {tau}",
            size=12,
            fill=svg.MUTED,
            family=svg.MONO,
        ),
    ]

    height = BOTTOM - TOP
    for tick in TICKS:
        y = BOTTOM - height * tick
        body.append(svg.line(LEFT, y, WIDTH - 40, y))
        body.append(
            svg.text(LEFT - 10, y + 4, f"{tick:.0%}", size=11, fill=svg.MUTED, anchor="end")
        )

    for index, name in enumerate(("ungated", "gated")):
        arm = document["arms"][name]
        fraction = arm["inherited_fraction"]
        x = LEFT + 40 + GAP * index
        bar = height * fraction
        if bar > 0:
            body.append(svg.rect(x, BOTTOM - bar, BAR_WIDTH, bar, FILL[name]))
        centre = x + BAR_WIDTH / 2
        # Zero has no bar to print a label inside, so the value sits above the axis.
        body.append(
            svg.text(
                centre,
                BOTTOM - bar + (24 if bar > 30 else -8),
                f"{fraction:.0%}",
                size=16,
                fill=svg.PAPER if bar > 30 else svg.INK,
                anchor="middle",
                weight="bold",
            )
        )
        body.append(
            svg.text(centre, BOTTOM + 22, name, size=14, anchor="middle", weight="bold")
        )
        body.append(
            svg.text(
                centre,
                BOTTOM + 40,
                f"{arm['inherited_count']} of {arm['denominator']} writes",
                size=11,
                fill=svg.MUTED,
                anchor="middle",
            )
        )

    body.append(svg.line(LEFT, BOTTOM, WIDTH - 40, BOTTOM, stroke=svg.INK))
    body.append(
        svg.text(
            LEFT - 42,
            HEIGHT - 16,
            f"gated: a source whose effective confidence is below {tau} may be read, "
            "not cited.",
            size=11,
            fill=svg.MUTED,
        )
    )
    return svg.document(WIDTH, HEIGHT, body, "contamination: inherited fraction by arm")
