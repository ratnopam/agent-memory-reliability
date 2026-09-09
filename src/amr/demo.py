"""``amr demo`` and ``amr matrix --svg``: the two surfaces meant to be looked at.

``demo`` runs the reference through the same runner ``reproduce`` uses — there is no second
code path, so what the screen shows and what ``raw.json`` records cannot drift apart — and
prints four blocks and nothing else: the declaration, the compact matrix, the divergence,
the totals. It is screen-recorded on a loop, so every line has to earn its place.

``matrix`` renders the same compact matrix as a standalone SVG table from an existing
``raw.json``, for a poster or a README.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

from amr import report, results, svg
from amr.outcomes import CheckOutcome
from amr.paths import spec_path
from amr.runner import run_suite

SYSTEM = "reference"

CELL_WIDTH = 132
ROW_HEIGHT = 40
LABEL_WIDTH = 300
PADDING = 24


def transcript(root: Path) -> str:
    """Everything ``amr demo`` prints, as one string. Deterministic given the tree."""
    spec_file = spec_path(root)
    # pytest writes to stdout even under -q; the demo is a fixed number of lines, so the
    # suite's own output is captured and dropped rather than filtered.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        suite = run_suite(root, spec_path=spec_file)
        document = results.build_document(suite, root)
    spec = report.read_spec(spec_file)
    runs = [run for run in document["runs"] if run["system"] == SYSTEM]
    if not runs:  # pragma: no cover - the reference is always registered
        raise RuntimeError(f"no runs for {SYSTEM!r}")

    capabilities = runs[0]["capabilities"]
    totals = document["totals"]
    lines = [
        (
            f"{SYSTEM} {runs[0]['system_version']} — "
            f"{len(document['spec']['checks'])} checks × {len(runs)} forget modes"
        ),
        f"  forget modes    {', '.join(capabilities['supported_forget_modes'])}",
        (
            f"  empty chain     {capabilities['empty_chain_convention']}   "
            f"durability {capabilities['durability']}"
        ),
        (
            f"  scopes          {capabilities['scopes']}   "
            f"cross-scope {capabilities['cross_scope_derivation']}"
        ),
        "",
        *text_matrix(document, spec, SYSTEM),
        "",
        # The divergence text is the same string summary.md carries; the Markdown
        # backticks around the ids are noise on a screen and nothing else differs.
        *[line.replace("`", "") for line in report.divergence_lines(document)],
        "",
        (
            f"{totals['tests']} tests: {totals[CheckOutcome.PASS.value]} PASS, "
            f"{totals[CheckOutcome.FAIL.value]} FAIL, "
            f"{totals[CheckOutcome.DIVERGENCE.value]} DIVERGENCE"
        ),
    ]
    return "\n".join(lines) + "\n"


def text_matrix(document: dict, spec: report.SpecText, system: str) -> list[str]:
    """The compact matrix as aligned columns, for a terminal that is being filmed.

    Markdown pipes and a ``|---|`` rule are noise on a screen and cost a line the demo
    does not have. Same rows as ``summary.md``; different glyphs.
    """
    modes, rows = report.matrix_rows(document, spec, system)
    label_width = max(len(row.label) for row in rows)
    widths = [max(len(mode), 10) for mode in modes]
    header = "  ".join(
        [" " * label_width, *[mode.ljust(width) for mode, width in zip(modes, widths, strict=True)]]
    )
    body = [
        "  ".join(
            [
                row.label.ljust(label_width),
                *[cell.ljust(width) for cell, width in zip(row.cells, widths, strict=True)],
            ]
        ).rstrip()
        for row in rows
    ]
    return [header.rstrip(), *body]


def matrix_svg(document: dict, spec: report.SpecText, system: str) -> str:
    """The compact matrix as a standalone SVG table."""
    runs = [run for run in document["runs"] if run["system"] == system]
    modes, rows = report.matrix_rows(document, spec, system)

    width = PADDING * 2 + LABEL_WIDTH + CELL_WIDTH * len(modes)
    height = PADDING * 2 + ROW_HEIGHT * (len(rows) + 1) + 52
    body: list[str] = [
        svg.text(
            PADDING,
            PADDING + 20,
            f"{system} {runs[0]['system_version']} — conformance by forget mode",
            size=19,
            weight="bold",
        ),
        svg.text(
            PADDING,
            PADDING + 42,
            f"{document['spec']['path']} · commit {document['environment']['git_sha']}",
            size=12,
            fill=svg.MUTED,
            family=svg.MONO,
        ),
    ]

    top = PADDING + 62
    for index, mode in enumerate(modes):
        centre = PADDING + LABEL_WIDTH + CELL_WIDTH * index + CELL_WIDTH / 2
        body.append(
            svg.text(centre, top + 20, mode, size=14, anchor="middle", weight="bold")
        )
    body.append(svg.line(PADDING, top + 30, width - PADDING, top + 30))

    for row_index, row in enumerate(rows):
        y = top + 30 + ROW_HEIGHT * row_index
        if row.headline:
            body.append(svg.line(PADDING, y, width - PADDING, y, stroke=svg.INK))
        body.append(
            svg.text(
                PADDING,
                y + 26,
                row.label,
                size=14,
                weight="bold" if row.headline else "normal",
            )
        )
        for index, outcome in enumerate(row.cells):
            x = PADDING + LABEL_WIDTH + CELL_WIDTH * index
            fill = svg.OUTCOME_FILL.get(outcome, svg.MISSING_FILL)
            body.append(svg.rect(x + 8, y + 8, CELL_WIDTH - 16, ROW_HEIGHT - 16, fill))
            body.append(
                svg.text(
                    x + CELL_WIDTH / 2,
                    y + 26,
                    outcome,
                    size=12,
                    fill=svg.PAPER,
                    anchor="middle",
                    weight="bold",
                )
            )
        body.append(svg.line(PADDING, y + ROW_HEIGHT, width - PADDING, y + ROW_HEIGHT))

    body.append(
        svg.text(
            PADDING,
            height - PADDING + 4,
            "DIVERGENCE is declared behaviour where the specification is open; "
            "it is reported, not scored.",
            size=12,
            fill=svg.MUTED,
        )
    )
    return svg.document(width, height, body, f"{system} conformance matrix")


def write_matrix_svg(raw_path: Path, out: Path | None = None) -> Path:
    document = results.load(raw_path)
    spec = report.read_spec(spec_path())
    system = document["runs"][0]["system"]
    target = out or raw_path.with_name("matrix.svg")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(matrix_svg(document, spec, system), encoding="utf-8")
    return target
