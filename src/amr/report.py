"""Turns ``raw.json`` into ``summary.md``.

Two tables. The per-system table is the record: every numbered check as a row, every
declared forget mode as a column, one of the three result states in each cell. The poster
matrix is the argument: four rows, one per property, aggregated so a reader standing two
metres away can see which column is not clean, plus the P2.5 row on its own because that
is the finding.

Aggregation is pessimistic. A property row is FAIL if any of its checks failed,
DIVERGENCE if any diverged and none failed, PASS only if every check passed. A property
that is 4/5 PASS is not a PASS.

Check descriptions and property titles are read out of the specification rather than
restated here, so a renamed property cannot be described two ways in one repository.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from amr.outcomes import CheckOutcome

MODE_ORDER = ("tombstone", "cascade", "erase")
HEADLINE_CHECK = "P2.5"
MISSING_CELL = "—"

_CHECK_ROW = re.compile(r"^\|\s*(P\d+\.\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")
_PROPERTY_HEADING = re.compile(r"^##\s*\d+\.\s*(P\d+)\s*[—–-]\s*(.+?)\s*$")


@dataclass(frozen=True)
class SpecCheck:
    id: str
    scenario: str
    required: str

    @property
    def property_id(self) -> str:
        return self.id.split(".")[0]


@dataclass(frozen=True)
class SpecText:
    """The parts of the specification the report quotes."""

    checks: dict[str, SpecCheck]
    properties: dict[str, str]

    def scenario(self, check: str) -> str:
        entry = self.checks.get(check)
        return entry.scenario if entry else ""

    def required(self, check: str) -> str:
        entry = self.checks.get(check)
        return entry.required if entry else ""

    def title(self, property_id: str) -> str:
        return self.properties.get(property_id, property_id)


def read_spec(path: Path) -> SpecText:
    checks: dict[str, SpecCheck] = {}
    properties: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = _CHECK_ROW.match(line)
        if row:
            checks.setdefault(
                row.group(1),
                SpecCheck(id=row.group(1), scenario=row.group(2), required=row.group(3)),
            )
            continue
        heading = _PROPERTY_HEADING.match(line)
        if heading:
            properties.setdefault(heading.group(1), heading.group(2))
    return SpecText(checks=checks, properties=properties)


# ------------------------------------------------------------------ aggregation


def modes_in(runs: list[dict]) -> list[str]:
    """Declared modes, in specification order, with anything unrecognised appended."""
    present = {run["forget_mode"] for run in runs}
    ordered = [mode for mode in MODE_ORDER if mode in present]
    ordered.extend(sorted(present - set(MODE_ORDER)))
    return ordered


def outcomes_by_check(run: dict) -> dict[str, str]:
    return {
        check["check"]: check["outcome"]
        for check in run["checks"]
        if "check" in check
    }


def worst(outcomes: list[str]) -> str:
    """Pessimistic aggregation. An absent outcome is worse than a failure."""
    if not outcomes or MISSING_CELL in outcomes:
        return MISSING_CELL
    if CheckOutcome.FAIL.value in outcomes:
        return CheckOutcome.FAIL.value
    if CheckOutcome.DIVERGENCE.value in outcomes:
        return CheckOutcome.DIVERGENCE.value
    return CheckOutcome.PASS.value


def check_ids_in(document: dict, runs: list[dict]) -> list[str]:
    declared = list(document.get("spec", {}).get("checks", ()))
    seen = [check for run in runs for check in outcomes_by_check(run)]
    for check in seen:
        if check not in declared:
            declared.append(check)
    return declared


# ---------------------------------------------------------------------- rendering


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _rule(count: int) -> str:
    return "|" + "|".join(["---"] * count) + "|"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [_row(header), _rule(len(header)), *[_row(row) for row in rows]]


def system_table(document: dict, spec: SpecText, system: str) -> list[str]:
    runs = [run for run in document["runs"] if run["system"] == system]
    modes = modes_in(runs)
    by_mode = {run["forget_mode"]: outcomes_by_check(run) for run in runs}
    rows: list[list[str]] = []
    for check in check_ids_in(document, runs):
        cells = [check, spec.scenario(check)]
        cells.extend(by_mode[mode].get(check, MISSING_CELL) for mode in modes)
        rows.append(cells)
    return _table(["Check", "Scenario", *modes], rows)


@dataclass(frozen=True)
class MatrixRow:
    """One line of the poster matrix, before anyone decides what it looks like."""

    label: str
    cells: tuple[str, ...]
    headline: bool = False


def matrix_rows(
    document: dict, spec: SpecText, system: str
) -> tuple[list[str], list[MatrixRow]]:
    """The compact matrix as data: mode columns, then one row per property plus P2.5.

    One aggregation, three renderers — Markdown for summary.md, SVG for the poster,
    aligned text for ``amr demo`` — so the screen and the file cannot disagree.
    """
    runs = [run for run in document["runs"] if run["system"] == system]
    if not runs:
        raise ValueError(f"{system!r} has no runs in this results document")
    modes = modes_in(runs)
    by_mode = {run["forget_mode"]: outcomes_by_check(run) for run in runs}
    property_ids = sorted(
        {check.split(".")[0] for outcomes in by_mode.values() for check in outcomes}
    )
    rows = [
        MatrixRow(
            label=f"{property_id} — {spec.title(property_id)}",
            cells=tuple(
                worst(
                    [
                        outcome
                        for check, outcome in by_mode[mode].items()
                        if check.startswith(f"{property_id}.")
                    ]
                )
                for mode in modes
            ),
        )
        for property_id in property_ids
    ]
    rows.append(
        MatrixRow(
            label=f"{HEADLINE_CHECK} — {spec.scenario(HEADLINE_CHECK)}",
            cells=tuple(
                by_mode[mode].get(HEADLINE_CHECK, MISSING_CELL) for mode in modes
            ),
            headline=True,
        )
    )
    return modes, rows


def poster_matrix(document: dict, spec: SpecText, system: str) -> list[str]:
    modes, rows = matrix_rows(document, spec, system)
    return _table(
        ["Property", *modes],
        [
            [_bold(row.label, row.headline), *[_bold(c, row.headline) for c in row.cells]]
            for row in rows
        ],
    )


def _bold(cell: str, when: bool) -> str:
    return f"**{cell}**" if when else cell


def divergence_lines(document: dict) -> list[str]:
    lines: list[str] = []
    for run in document["runs"]:
        for check in run["checks"] + run.get("supplementary", []):
            for record in check.get("divergences", ()):
                lines.append(
                    f"- `{record['check']}` under `{run['forget_mode']}` "
                    f"({record['spec_ref']}) — {record['detail']}"
                )
    return lines


def failure_lines(document: dict) -> list[str]:
    lines: list[str] = []
    for run in document["runs"]:
        for check in run["checks"] + run.get("supplementary", []):
            if check["outcome"] == CheckOutcome.FAIL.value:
                label = check.get("check") or check["name"]
                lines.append(
                    f"- `{label}` under `{run['forget_mode']}` — {check['detail']}"
                )
    for check in document.get("suite_checks", ()):
        if check["outcome"] == CheckOutcome.FAIL.value:
            lines.append(f"- `{check['name']}` — {check['detail']}")
    for gap in document.get("missing_checks", ()):
        lines.append(
            f"- `{gap['check']}` under `{gap['forget_mode']}` — {gap['reason']}"
        )
    return lines


def capability_lines(run: dict) -> list[str]:
    capabilities = run["capabilities"]
    declared = (
        f"Declared: forget modes {', '.join(capabilities['supported_forget_modes'])}; "
        f"default `{capabilities['default_forget_mode']}`; "
        f"empty chain {capabilities['empty_chain_convention']}; "
        f"revision `{capabilities['revision']}`; scopes `{capabilities['scopes']}`; "
        f"cross-scope `{capabilities['cross_scope_derivation']}`; "
        f"durability `{capabilities['durability']}`."
    )
    return [declared]


def _unnumbered_counts(document: dict) -> tuple[int, int]:
    """(supplementary, meta). A supplementary check names itself; a meta check does not."""
    unnumbered = list(document.get("suite_checks", ()))
    for run in document["runs"]:
        unnumbered.extend(run.get("supplementary", []))
    supplementary = sum(1 for check in unnumbered if check.get("extra"))
    return supplementary, len(unnumbered) - supplementary


def render(document: dict, spec: SpecText) -> str:
    environment = document["environment"]
    totals = document["totals"]
    systems: list[str] = []
    for run in document["runs"]:
        if run["system"] not in systems:
            systems.append(run["system"])

    provenance = (
        f"Generated {document['generated_at']} · schema {document['schema']} · "
        f"commit `{environment['git_sha']}` · "
        f"Python {environment['python_version']} on {environment['platform']} · "
        f"pytest {environment['pytest_version']}."
    )
    tally = (
        f"{totals['tests']} tests: {totals[CheckOutcome.PASS.value]} PASS, "
        f"{totals[CheckOutcome.FAIL.value]} FAIL, "
        f"{totals[CheckOutcome.DIVERGENCE.value]} DIVERGENCE."
    )
    lines: list[str] = ["# Conformance results", "", provenance, "", tally, ""]

    for system in systems:
        runs = [run for run in document["runs"] if run["system"] == system]
        lines.append(f"## {system} {runs[0]['system_version']}")
        lines.append("")
        lines.extend(capability_lines(runs[0]))
        lines.append("")
        lines.extend(system_table(document, spec, system))
        lines.append("")

    supplementary, meta = _unnumbered_counts(document)
    lines.append(
        f"Beyond the numbered checks: {supplementary} supplementary checks "
        "(mode-independent properties, random-DAG agreement with the reference "
        f"arithmetic, taxonomy reproductions) and {meta} meta checks (one test per "
        "specification check id, taxonomy entries matching the code they embed). Both "
        "are counted in the totals above."
    )
    lines.append("")

    failures = failure_lines(document)
    lines.append("## Failures")
    lines.append("")
    lines.extend(failures or ["None."])
    lines.append("")

    divergences = divergence_lines(document)
    lines.append("## Divergences")
    lines.append("")
    if divergences:
        lines.append(
            "A divergence is behaviour the specification leaves open, in a system whose "
            "capability declaration says it behaves that way. It is reported, not scored."
        )
        lines.append("")
    lines.extend(divergences or ["None."])
    lines.append("")

    lines.append("## Poster matrix")
    lines.append("")
    for system in systems:
        if len(systems) > 1:
            lines.append(f"**{system}**")
            lines.append("")
        lines.extend(poster_matrix(document, spec, system))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def readme_matrix_drift(document: dict, spec: SpecText, readme_path: Path) -> str | None:
    """The README's matrix against the one just generated. None means they agree.

    The README is where the claim is read, so a stale table there is the most expensive
    kind of drift in the repository. ``make reproduce`` fails on it.
    """
    if not readme_path.exists():
        return f"{readme_path.name} does not exist"
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("| Property |")]
    if not starts:
        return f"{readme_path.name} contains no results matrix (no '| Property |' table)"
    start = starts[0]
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    found = [line.rstrip() for line in lines[start:end]]
    system = document["runs"][0]["system"]
    expected = poster_matrix(document, spec, system)
    if found != expected:
        diff = "\n".join(
            difflib.unified_diff(
                found, expected, fromfile="README.md", tofile="generated", lineterm=""
            )
        )
        return f"{readme_path.name} does not render the generated matrix\n{diff}"
    return None


#: The undated path the README embeds. Written by a deliberate contamination run; see
#: ``scenarios/contamination/run.py``, which owns the constant this mirrors.
STABLE_CHART = Path("docs") / "contamination.svg"

#: The header row of the README's contamination table, and of nothing else in the file.
CONTAMINATION_HEADER = "| arm |"


def embedded_chart_drift(root: Path, dated_chart: Path) -> str | None:
    """``docs/contamination.svg`` against the newest dated one. None means identical.

    The README embeds the undated copy, so the undated copy is what a reader sees. Nothing
    reads an image: if it were left behind by a regenerated run, the page would show last
    month's bars beside this month's numbers and no test would notice. Bytes, not a
    re-render, because the writer is deterministic and a diff of the two is not useful.
    """
    stable = root / STABLE_CHART
    if not stable.exists():
        return (
            f"{STABLE_CHART.as_posix()} does not exist; the README embeds it. "
            "Run `make results`."
        )
    if stable.read_bytes() != dated_chart.read_bytes():
        return (
            f"{STABLE_CHART.as_posix()} is not the chart in {dated_chart.parent.name}. "
            "The README embeds the stale one; run `make results`."
        )
    return None


def readme_contamination_drift(contamination: dict, readme_path: Path) -> str | None:
    """The README's contamination figures against the simulation record.

    Five numbers per arm, typed out by hand in prose-shaped Markdown: writes, inherited
    with its percentage, inflated with its percentage, and depth. They are the headline
    claim of the repository and the one table no generator writes, so this is where a
    number goes stale. Percentages are formatted exactly as the scenario formats them,
    so the README is held to the rounding the record itself prints.
    """
    if not readme_path.exists():
        return f"{readme_path.name} does not exist"
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    starts = [
        index for index, line in enumerate(lines) if line.startswith(CONTAMINATION_HEADER)
    ]
    if not starts:
        return (
            f"{readme_path.name} contains no contamination table "
            f"(no {CONTAMINATION_HEADER!r} row)"
        )
    end = starts[0] + 1
    while end < len(lines) and lines[end].startswith("|"):
        end += 1

    arms = contamination["arms"]
    problems: list[str] = []
    named: list[str] = []
    for line in lines[starts[0] + 1 : end]:
        cells = _cells(line)
        if _is_rule(cells):
            continue
        if len(cells) != 5:
            problems.append(f"a row of {len(cells)} columns, not 5: {line.strip()}")
            continue
        label, found = cells[0], cells[1:]
        # The README labels an arm and then qualifies it — "gated (τ = 0.5)". A prefix
        # match reads that; it does not confuse "ungated" for "gated", which a substring
        # match would.
        matched = [name for name in arms if label.startswith(name)]
        if len(matched) != 1:
            problems.append(f"{label!r} names {len(matched)} simulated arms, not 1")
            continue
        named.append(matched[0])
        expected = _contamination_cells(arms[matched[0]])
        if found != expected:
            problems.append(
                f"{matched[0]}: README says {' | '.join(found)}; the simulation "
                f"measured {' | '.join(expected)}"
            )
    absent = sorted(set(arms) - set(named))
    if absent:
        problems.append(f"no row for {', '.join(absent)}")
    if problems:
        return f"{readme_path.name} does not state the measured contamination:\n" + "\n".join(
            f"- {problem}" for problem in problems
        )
    return None


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_rule(cells: list[str]) -> bool:
    return all(set(cell) <= {"-", ":"} and cell for cell in cells)


def _contamination_cells(arm: dict) -> list[str]:
    """One arm's four figures, formatted as ``scenarios/contamination/run.py`` prints them."""
    return [
        str(arm["denominator"]),
        f"{arm['inherited_count']} ({arm['inherited_fraction']:.0%})",
        f"{arm['inflated_count']} ({arm['inflated_fraction']:.0%})",
        str(arm["max_chain_depth"]),
    ]


def write(document: dict, spec_path: Path, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "summary.md"
    path.write_text(render(document, read_spec(spec_path)), encoding="utf-8")
    return path
