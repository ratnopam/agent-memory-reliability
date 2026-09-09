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

import re
from dataclasses import dataclass
from pathlib import Path

from harness.outcomes import CheckOutcome

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


def poster_matrix(document: dict, spec: SpecText, system: str) -> list[str]:
    runs = [run for run in document["runs"] if run["system"] == system]
    modes = modes_in(runs)
    by_mode = {run["forget_mode"]: outcomes_by_check(run) for run in runs}
    property_ids = sorted(
        {check.split(".")[0] for outcomes in by_mode.values() for check in outcomes}
    )
    rows: list[list[str]] = []
    for property_id in property_ids:
        label = f"{property_id} — {spec.title(property_id)}"
        cells = [label]
        for mode in modes:
            outcomes = [
                outcome
                for check, outcome in by_mode[mode].items()
                if check.startswith(f"{property_id}.")
            ]
            cells.append(worst(outcomes))
        rows.append(cells)
    headline = [f"**{HEADLINE_CHECK} — {spec.scenario(HEADLINE_CHECK)}**"]
    for mode in modes:
        outcome = by_mode[mode].get(HEADLINE_CHECK, MISSING_CELL)
        headline.append(f"**{outcome}**")
    rows.append(headline)
    return _table(["Property", *modes], rows)


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


def write(document: dict, spec_path: Path, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "summary.md"
    path.write_text(render(document, read_spec(spec_path)), encoding="utf-8")
    return path
