"""Runs the conformance suite and returns one outcome per cell of the matrix.

pytest does the running. The alternative — a hand-rolled loop that imports the test
modules and calls them — would need its own fixture mechanism, its own assertion
reporting, and its own parameterisation, and would then disagree with ``make test``
about what passed. One runner, two front ends.

The suite is executed in a single pytest session rather than once per
``(system, forget_mode)``. The fixtures already parameterise every check over every
cell, so a session covers the whole matrix, and the runner groups the reports it gets
back by the ``(system, mode)`` stamped on them by ``properties/conftest.py``. Grouping
after the fact reads the same stamps the terminal does, so the two cannot drift.

Outcome mapping:

- passed, no divergence stamp -> PASS
- passed, divergence stamp    -> DIVERGENCE
- failed, errored, or skipped -> FAIL

A skip is a FAIL on purpose. An unrun check is not a satisfied check, and a suite that
reports "not applicable" for a property is exactly the failure mode this repository
exists to avoid.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from amr import registry
from amr.outcomes import DIVERGENCE_PROPERTY, CheckOutcome, DivergenceRecord
from amr.protocol import Capabilities, ForgetMode

CHECK_PROPERTY = "amr-check"
EXTRA_PROPERTY = "amr-extra"
SYSTEM_PROPERTY = "amr-system"
MODE_PROPERTY = "amr-mode"
DOC_PROPERTY = "amr-doc"

PROPERTIES_DIR = "properties"


@dataclass(frozen=True)
class CheckResult:
    """One executed test, resolved to a matrix cell."""

    nodeid: str
    name: str
    outcome: CheckOutcome
    detail: str
    check: str | None = None
    extra: str | None = None
    system: str | None = None
    mode: str | None = None
    divergences: tuple[DivergenceRecord, ...] = ()

    @property
    def numbered(self) -> bool:
        return self.check is not None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "nodeid": self.nodeid,
            "outcome": self.outcome.value,
            "detail": self.detail,
        }
        if self.check is not None:
            payload["check"] = self.check
        if self.extra is not None:
            payload["extra"] = self.extra
        if self.divergences:
            payload["divergences"] = [record.as_dict() for record in self.divergences]
        return payload


@dataclass(frozen=True)
class Run:
    """One ``(system, forget_mode)`` pair: a column of the results matrix."""

    system: str
    version: str
    mode: ForgetMode
    capabilities: Capabilities
    checks: tuple[CheckResult, ...] = ()
    extras: tuple[CheckResult, ...] = ()

    def outcome_for(self, check: str) -> CheckOutcome | None:
        for result in self.checks:
            if result.check == check:
                return result.outcome
        return None


@dataclass
class SuiteResult:
    """Everything one execution of the suite observed."""

    runs: tuple[Run, ...]
    suite_checks: tuple[CheckResult, ...]
    exit_code: int
    check_ids: tuple[str, ...]

    @property
    def all_results(self) -> tuple[CheckResult, ...]:
        collected: list[CheckResult] = list(self.suite_checks)
        for run in self.runs:
            collected.extend(run.checks)
            collected.extend(run.extras)
        return tuple(collected)

    def counts(self) -> dict[str, int]:
        counts = {outcome.value: 0 for outcome in CheckOutcome}
        for result in self.all_results:
            counts[result.outcome.value] += 1
        counts["tests"] = len(self.all_results)
        return counts

    @property
    def failed(self) -> bool:
        return any(
            result.outcome is CheckOutcome.FAIL for result in self.all_results
        )


class _Collector:
    """A pytest plugin that keeps the call-phase report for every test."""

    def __init__(self) -> None:
        self.results: list[CheckResult] = []
        self._setup_failures: dict[str, CheckResult] = {}

    def pytest_runtest_logreport(self, report: object) -> None:
        when = getattr(report, "when", None)
        if when not in {"setup", "call"}:
            return
        outcome = getattr(report, "outcome", "")
        if when == "setup" and outcome == "passed":
            return
        properties = dict(_pairs(getattr(report, "user_properties", ())))
        divergences = tuple(
            DivergenceRecord(**json.loads(raw))
            for key, raw in _pairs(getattr(report, "user_properties", ()))
            if key == DIVERGENCE_PROPERTY
        )
        if outcome == "passed":
            resolved = (
                CheckOutcome.DIVERGENCE if divergences else CheckOutcome.PASS
            )
        else:
            resolved = CheckOutcome.FAIL
        nodeid = str(getattr(report, "nodeid", ""))
        self.results.append(
            CheckResult(
                nodeid=nodeid,
                name=nodeid.rpartition("::")[2],
                outcome=resolved,
                detail=_detail(report, properties, divergences),
                check=properties.get(CHECK_PROPERTY),
                extra=properties.get(EXTRA_PROPERTY),
                system=properties.get(SYSTEM_PROPERTY),
                mode=properties.get(MODE_PROPERTY),
                divergences=divergences,
            )
        )


def _pairs(properties: object) -> list[tuple[str, str]]:
    return [(str(key), str(value)) for key, value in properties or ()]


def _detail(
    report: object,
    properties: dict[str, str],
    divergences: tuple[DivergenceRecord, ...],
) -> str:
    """One line. What diverged, or what failed, or what the check asserts."""
    if divergences:
        return divergences[0].detail
    if getattr(report, "outcome", "") == "skipped":
        return "skipped: an unrun check is not a satisfied check"
    if getattr(report, "outcome", "") == "failed":
        text = str(getattr(report, "longrepr", "") or "assertion failed")
        for line in reversed(text.splitlines()):
            stripped = line.strip()
            if stripped.startswith("E "):
                return _one_line(stripped[2:].strip())
        return _one_line(text.strip().splitlines()[-1] if text.strip() else "failed")
    return _one_line(properties.get(DOC_PROPERTY, ""))


def _one_line(text: str, limit: int = 160) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def spec_check_ids(spec_path: Path) -> tuple[str, ...]:
    """The numbered checks, read from the specification's conformance table."""
    pattern = re.compile(r"^\|\s*(P\d+\.\d+)\s*\|")
    found: list[str] = []
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return tuple(found)


def run_suite(
    root: Path,
    spec_path: Path | None = None,
    extra_args: tuple[str, ...] = (),
) -> SuiteResult:
    """Execute the suite in-process and resolve every report to a matrix cell."""
    import pytest

    collector = _Collector()
    args = [
        str(root / PROPERTIES_DIR),
        "-q",
        "-p",
        "no:cacheprovider",
        "--rootdir",
        str(root),
        *extra_args,
    ]
    exit_code = int(pytest.main(args, plugins=[collector]))

    grouped: dict[tuple[str, str], list[CheckResult]] = {}
    suite_checks: list[CheckResult] = []
    for result in collector.results:
        if result.system is None or result.mode is None:
            suite_checks.append(result)
        else:
            grouped.setdefault((result.system, result.mode), []).append(result)

    runs: list[Run] = []
    for registration in registry.systems():
        for mode in registry.modes_for(registration):
            capabilities = registration.build(mode).capabilities()
            cell = grouped.get((registration.name, mode.value), [])
            runs.append(
                Run(
                    system=registration.name,
                    version=capabilities.version,
                    mode=mode,
                    capabilities=capabilities,
                    checks=tuple(
                        sorted(
                            (r for r in cell if r.numbered),
                            key=lambda r: _check_key(r.check or ""),
                        )
                    ),
                    extras=tuple(
                        sorted((r for r in cell if not r.numbered), key=_name_key)
                    ),
                )
            )

    return SuiteResult(
        runs=tuple(runs),
        suite_checks=tuple(sorted(suite_checks, key=_name_key)),
        exit_code=exit_code,
        check_ids=spec_check_ids(spec_path) if spec_path else (),
    )


def _check_key(check: str) -> tuple[int, ...]:
    digits = check.lstrip("Pp").split(".")
    try:
        return tuple(int(part) for part in digits)
    except ValueError:  # pragma: no cover - a check id that is not numbered
        return (0,)


def _name_key(result: CheckResult) -> tuple[str, str]:
    return (result.name, result.nodeid)


@dataclass(frozen=True)
class MissingCheck:
    """A numbered check the specification lists and a run did not report."""

    system: str
    mode: str
    check: str
    reason: str = "no test reported this check"


def missing_checks(result: SuiteResult) -> tuple[MissingCheck, ...]:
    gaps: list[MissingCheck] = []
    for run in result.runs:
        for check in result.check_ids:
            if run.outcome_for(check) is None:
                gaps.append(
                    MissingCheck(system=run.system, mode=run.mode.value, check=check)
                )
    return tuple(gaps)
