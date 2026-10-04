"""Fails unless the example adapter, really installed, fails exactly what it declares.

``docs/adding-a-system.md`` promises a stranger that four commands get their store measured:
install the suite, install their adapter, run ``amr reproduce``, read the matrix. The suite
already checks the *shape* of that promise — ``properties/test_external_adapter_example.py``
hand-writes the ``dist-info`` an install leaves behind, because a test is not allowed to
reach an index. So the one thing no test can cover is the step the stranger actually takes:
``pip install -e examples/external-adapter``, with pip's build backend fetched from PyPI
and the entry point written by setuptools rather than by us.

This script is the other half. It assumes the install already happened — the CI job does
it, and that is the part that needs the network — and then asserts three things about a run
against the example alone:

* the example is discovered through the ``amr.systems`` entry-point group and nothing else,
* ``amr reproduce`` exits non-zero, because an adapter declaring less than a conforming one
  has failures and a suite that passed it would be measuring nothing,
* the red cells are exactly the five the declaration predicts: P1.5, P1.7 and P2.6 from
  ``durability: "in-memory"`` and ``revision: "none"``, plus the two taxonomy
  reproductions that need ``cascade`` and ``erase`` and are therefore skipped — and a skip
  is counted as a FAIL, because there is no *not applicable* state (SPEC.md §9).

A fourth, red cell appearing is a regression in the adapter or the suite. A fourth cell
going *green* is the more interesting failure: it means a declaration stopped costing
something, and the example stopped teaching what it exists to teach.

Expects to be run from the repository root, with the suite and the example both installed:

    python -m pip install -e ".[test]"
    python -m pip install -e examples/external-adapter
    python .github/check_example_adapter.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from amr import registry  # noqa: E402

SYSTEM = "amr-adapter-example"

#: What the declaration costs, check by check. Kept in step with
#: ``properties/test_external_adapter_example.py``, which asserts the same set over the
#: hand-written install; if these two ever disagree, the example changed and one of them
#: was not updated.
EXPECTED_FAILURES = frozenset({"P1.5", "P1.7", "P2.6"})

#: Two taxonomy reproductions need a mode the example does not declare. They skip, and a
#: skip is a FAIL (the project's feedback log, entry 16). Unnumbered, so they land in
#: ``suite_checks`` rather than in a matrix cell.
EXPECTED_SUITE_FAILURES = frozenset(
    {
        f"test_erasure_inflation_reproduces[{SYSTEM}]",
        f"test_orphaned_derivative_is_handled[{SYSTEM}]",
    }
)


def discovery_problems() -> list[str]:
    """Is the example registered, and by the route an outside package has to use?"""
    os.environ["SYSTEMS"] = SYSTEM
    try:
        found = registry.systems()
    except ValueError as error:
        return [
            f"{error}. Install it: python -m pip install -e examples/external-adapter"
        ]
    sources = {registration.name: registration.source for registration in found}
    if SYSTEM not in sources:
        return [f"{SYSTEM} is not registered; SYSTEMS selected {sorted(sources)}"]
    if sources[SYSTEM] != "entry-point":
        return [
            f"{SYSTEM} was discovered {sources[SYSTEM]}, not through the "
            f"{registry.ENTRY_POINT_GROUP} entry-point group an installed package uses"
        ]
    return []


def reproduce(out: Path) -> tuple[int, dict | None]:
    """``SYSTEMS=amr-adapter-example amr reproduce``, out of process, as a reader runs it."""
    completed = subprocess.run(
        [sys.executable, "-m", "amr", "reproduce", "--out", str(out), "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
        env={
            **os.environ,
            "SYSTEMS": SYSTEM,
            # The outer run would otherwise collect the in-tree test that starts a run of
            # its own, forever. See conftest.py.
            "AMR_NESTED_RUN": "1",
        },
    )
    raw = out / "raw.json"
    if not raw.is_file():
        print(completed.stdout + completed.stderr, file=sys.stderr)
        return completed.returncode, None
    return completed.returncode, json.loads(raw.read_text(encoding="utf-8"))


def matrix_problems(document: dict) -> list[str]:
    """Every numbered check reported, and the red ones exactly the declared ones."""
    problems: list[str] = []
    runs = document["runs"]
    if [run["system"] for run in runs] != [SYSTEM]:
        return [f"the run measured {[run['system'] for run in runs]}, not just {SYSTEM}"]
    outcomes = {check["check"]: check["outcome"] for check in runs[0]["checks"]}
    declared = document["spec"]["checks"]
    if len(outcomes) != len(declared):
        problems.append(
            f"{len(outcomes)} checks reported, {len(declared)} in the specification: "
            f"{sorted(set(declared) - set(outcomes))} did not run"
        )
    failed = {check for check, outcome in outcomes.items() if outcome == "FAIL"}
    for unexpected in sorted(failed - EXPECTED_FAILURES):
        problems.append(f"{unexpected} FAILed, which the declaration does not predict")
    for recovered in sorted(EXPECTED_FAILURES - failed):
        problems.append(
            f"{recovered} is {outcomes.get(recovered, 'absent')}; the declaration says "
            "it cannot pass, so either the adapter or this gate is out of date"
        )
    other = {
        check
        for check, outcome in outcomes.items()
        if outcome not in ("PASS", "FAIL")
    }
    if other:
        problems.append(f"a third result state in the column: {sorted(other)}")

    suite = {check["name"]: check["outcome"] for check in document.get("suite_checks", ())}
    red = {name for name, outcome in suite.items() if outcome == "FAIL"}
    for unexpected in sorted(red - EXPECTED_SUITE_FAILURES):
        problems.append(f"unnumbered check {unexpected} FAILed unexpectedly")
    for recovered in sorted(EXPECTED_SUITE_FAILURES - red):
        problems.append(
            f"unnumbered check {recovered} is {suite.get(recovered, 'absent')}; it needs "
            "a forget mode the example does not declare, and a skip is a FAIL"
        )
    if document.get("missing_checks"):
        problems.append(f"missing checks: {document['missing_checks']}")
    return problems


def main() -> int:
    problems = discovery_problems()
    document = None
    returncode = 0
    if not problems:
        with tempfile.TemporaryDirectory(prefix="amr-example-") as temporary:
            returncode, document = reproduce(Path(temporary) / "out")
        if document is None:
            problems.append("the run produced no raw.json; its output is above")
        else:
            if returncode == 0:
                problems.append(
                    "amr reproduce exited 0; an adapter that declares less than it "
                    "implements has failures, so a green run means nothing was measured"
                )
            problems.extend(matrix_problems(document))

    for problem in problems:
        print(f"{SYSTEM}: {problem}", file=sys.stderr)
    if problems:
        return 1
    checks = len(document["runs"][0]["checks"]) if document else 0
    print(
        f"{SYSTEM}: installed, discovered by entry point, exited {returncode} with "
        f"{len(EXPECTED_FAILURES)} of {checks} checks red "
        f"({', '.join(sorted(EXPECTED_FAILURES))}) and "
        f"{len(EXPECTED_SUITE_FAILURES)} skipped reproductions counted as failures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
