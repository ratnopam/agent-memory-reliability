"""The example adapter is discovered from outside the tree, and fails exactly what it says.

``examples/external-adapter/`` is the answer to "how do I get my store measured", so the
claim has to be executable: this puts the example on the path the way an install would,
runs ``amr reproduce`` against it and nothing else, and asserts the whole column -- three
FAILs that follow from the declaration, twenty-three PASSes, and no third state.

The install is hand-written rather than done with ``pip``, for the reason
``test_registry.py`` gives at length: pip's build isolation fetches setuptools from an
index, and the suite is not allowed to reach the network. A ``*.dist-info`` directory
holding ``METADATA`` and ``entry_points.txt`` on ``sys.path`` is exactly what an install
leaves behind, and ``importlib.metadata`` reads it by the same code path either way. The
example's README documents both routes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from amr import registry
from amr.paths import repo_root

SYSTEM = "amr-adapter-example"
VERSION = "0.1.0"
PACKAGE = "amr_adapter_example"

#: What the declaration in ``capabilities.py`` costs, check by check. This is the whole of
#: the difference between this adapter and a conforming one, and it is not a bug list:
#: ``durability: "in-memory"`` with no ``Reopenable`` cannot survive P1.5 or P1.7, and
#: ``revision: "none"`` cannot survive P2.6. Nothing else is allowed to be red.
EXPECTED_FAILURES = frozenset({"P1.5", "P1.7", "P2.6"})

#: Declaring one forget mode does not make the two multi-mode taxonomy reproductions
#: inapplicable -- there is no such state (design-notes/spec-feedback.md, entry 16). They
#: are skipped, a skip is a FAIL, and it lands here rather than in a numbered cell.
EXPECTED_SUITE_FAILURES = frozenset(
    {
        f"test_erasure_inflation_reproduces[{SYSTEM}]",
        f"test_orphaned_derivative_is_handled[{SYSTEM}]",
    }
)

METADATA = f"""\
Metadata-Version: 2.1
Name: {SYSTEM}
Version: {VERSION}
"""


def _install(directory: Path) -> Path:
    """Write the ``dist-info`` an install of ``examples/external-adapter`` would produce."""
    dist_info = directory / f"{PACKAGE}-{VERSION}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(METADATA, encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(
        f"[{registry.ENTRY_POINT_GROUP}]\n{SYSTEM} = {PACKAGE}:factory\n", encoding="utf-8"
    )
    return dist_info


def _reproduce(tmp_path: Path) -> dict:
    """Run the suite against the example alone, out of process, and return ``raw.json``."""
    root = repo_root()
    _install(tmp_path)
    out = tmp_path / "out"
    completed = subprocess.run(
        [sys.executable, "-m", "amr", "reproduce", "--out", str(out), "--quiet"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                [
                    str(root / "src"),
                    str(root),
                    str(root / "examples" / "external-adapter" / "src"),
                    str(tmp_path),
                ]
            ),
            "SYSTEMS": SYSTEM,
            # Keeps the inner run from collecting this file and starting a third. The
            # conftest at the root says what it does with this.
            "AMR_NESTED_RUN": "1",
        },
    )
    # A red exit is the point: reproduce fails while anything is FAIL, and this adapter is
    # built to have failures. The evidence is the matrix, so it is parsed either way.
    raw = out / "raw.json"
    assert raw.is_file(), completed.stdout + completed.stderr
    assert completed.returncode != 0, "an adapter declaring less than it implements passed"
    return json.loads(raw.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def document(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return _reproduce(tmp_path_factory.mktemp("external-adapter"))


@pytest.mark.extra("external-adapter-discovered")
def test_the_example_is_discovered_by_its_entry_point_alone(document: dict) -> None:
    """No edit to this repository names the example: the entry point is the whole link."""
    runs = document["runs"]
    assert [run["system"] for run in runs] == [SYSTEM], "SYSTEMS selected something else"
    capabilities = runs[0]["capabilities"]
    assert capabilities["supported_forget_modes"] == ["tombstone"], capabilities
    assert runs[0]["forget_mode"] == "tombstone"
    assert capabilities["version"] == VERSION


@pytest.mark.extra("external-adapter-matrix")
def test_the_example_fails_exactly_what_its_declaration_predicts(document: dict) -> None:
    """Every numbered check is reported, and the red ones are the declared three."""
    checks = document["runs"][0]["checks"]
    outcomes = {check["check"]: check["outcome"] for check in checks}
    assert len(outcomes) == len(checks), "a check id was reported twice"
    assert len(outcomes) == len(document["spec"]["checks"]), "not every check ran"

    failed = {check for check, outcome in outcomes.items() if outcome == "FAIL"}
    assert failed == set(EXPECTED_FAILURES), sorted(failed)
    passed = {check for check, outcome in outcomes.items() if outcome == "PASS"}
    assert passed == set(outcomes) - failed, "a third state appeared in the column"
    assert not document["missing_checks"], document["missing_checks"]


@pytest.mark.extra("external-adapter-skips-are-failures")
def test_the_examples_skipped_reproductions_are_counted_as_failures(document: dict) -> None:
    """A mode it did not declare does not become a check it is excused from."""
    suite = {check["name"]: check["outcome"] for check in document["suite_checks"]}
    red = {name for name, outcome in suite.items() if outcome == "FAIL"}
    assert red & EXPECTED_SUITE_FAILURES == EXPECTED_SUITE_FAILURES, sorted(red)
    assert red - EXPECTED_SUITE_FAILURES == set(), sorted(red - EXPECTED_SUITE_FAILURES)
