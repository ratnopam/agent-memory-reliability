"""Every numbered check in the specification has exactly one test.

This is the check on the suite itself. It parses the conformance tables in
``version2/SPEC.md`` and compares them against the ``@pytest.mark.check`` markers in this
directory, so adding a row to the spec without adding a test fails the build.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "version2" / "SPEC.md"
PROPERTIES = ROOT / "properties"

SPEC_ROW = re.compile(r"^\|\s*(P\d+\.\d+)\s*\|")
MARKED_TEST = re.compile(
    r"@pytest\.mark\.check\(\s*\"([^\"]+)\"\s*\)\s*\ndef\s+(test_\w+)\s*\("
)


def spec_check_ids() -> list[str]:
    ids: list[str] = []
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        match = SPEC_ROW.match(line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def marked_tests() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(PROPERTIES.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        for check_id, function in MARKED_TEST.findall(source):
            found.setdefault(check_id, []).append(f"{path.name}::{function}")
    return found


def test_every_spec_check_has_exactly_one_test() -> None:
    """The 24 numbered checks map one-to-one onto marked test functions."""
    spec_ids = spec_check_ids()
    assert len(spec_ids) == len(set(spec_ids)), f"duplicate rows in {SPEC.name}"
    assert len(spec_ids) == 24, (
        f"expected 24 checks in {SPEC.name}, found {len(spec_ids)}"
    )

    found = marked_tests()
    missing = sorted(set(spec_ids) - set(found))
    unknown = sorted(set(found) - set(spec_ids))
    assert not missing, f"no test for {missing}"
    assert not unknown, f"test marked with a check id absent from the spec: {unknown}"
    duplicated = {check: names for check, names in found.items() if len(names) > 1}
    assert not duplicated, f"more than one test per check: {duplicated}"


def test_test_names_follow_their_check_id() -> None:
    """A check id is readable from the test name: P2.5 -> test_p2_5_..."""
    for check_id, names in sorted(marked_tests().items()):
        prefix = "test_" + check_id.lower().replace(".", "_") + "_"
        for name in names:
            function = name.split("::", 1)[1]
            assert function.startswith(prefix), (
                f"{function} implements {check_id} but does not start with {prefix}"
            )
