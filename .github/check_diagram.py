"""Fails if the architecture diagram states a fact about this tree that is false.

``docs/architecture.svg`` is the first thing most readers look at, and it is the only
document in the repository that no test reads. It names source files, it counts the
numbered checks, and it says the operation set has twelve operations in it — three claims
that were true when it was drawn and that nothing notices going stale. One of them already
had: the diagram named a ``scope.py`` that this repository has never contained.

Three facts, each checked against the thing that defines it rather than against a copy:

* every ``*.py`` the diagram names exists in the tree, matched by basename, because the
  diagram writes ``amr/protocol.py`` where ``git ls-files`` writes ``src/amr/protocol.py``
  and a diagram is not the place to track a directory layout;
* the "N numbered checks" it prints equals the number of rows
  ``properties/test_spec_coverage.py`` parses out of the specification — the same parse the
  suite's own coverage check uses, so there is one definition of "how many checks there
  are" and the diagram is held to it;
* the spelled count in "N operations" equals the number of operations ``MemorySystem``
  declares, which catches both the diagram going stale and the diagram being reworded to a
  number the protocol does not support.

A missing phrase is a problem rather than a pass. A gate whose subject can be deleted is a
gate that can be switched off by deleting its subject.

The C2PA manifest is stripped before anything is read. It is a base64 blob inside
``<metadata>`` and matching ``.py`` inside it would be matching noise.

What this does not check: layout, colour, whether the arrows point at the right boxes, or
whether ``docs/architecture.png`` was re-exported from the SVG. A gate over an image's
*meaning* is not available from text; these are its load-bearing strings.

Run: python .github/check_diagram.py
"""

from __future__ import annotations

import ast
import html
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIAGRAM = ROOT / "docs" / "architecture.svg"
COVERAGE_TEST = ROOT / "properties" / "test_spec_coverage.py"
PROTOCOL = ROOT / "src" / "amr" / "protocol.py"

#: The signed manifest, which is bytes that happen to be text.
METADATA = re.compile(r"<metadata>.*?</metadata>", re.DOTALL)
TAG = re.compile(r"<[^>]+>")

#: A path-ish token ending in .py. Deliberately greedy about directories so that a
#: diagram naming ``src/amr/protocol.py`` and one naming ``protocol.py`` are both read.
PY_FILE = re.compile(r"[\w./-]+\.py\b")
NUMBERED_CHECKS = re.compile(r"(\d+)\s+numbered checks")

#: ``capabilities`` is the declaration, not an operation: SPEC.md 3 lists twelve and it is
#: not among them. The MCP server draws the same line, exposing nine record operations and
#: withholding the three grant ones.
NOT_AN_OPERATION = frozenset({"capabilities"})

#: The count is spelled, so the gate has to read spelling. Both directions matter: a
#: diagram saying "twelve" when there are thirteen is wrong, and so is one quietly
#: reworded to "thirteen" while the protocol still declares twelve.
OPERATION_COUNT = re.compile(r"([A-Za-z]+|\d+)\s+operations")
NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        (
            "zero one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
        ).split()
    )
}


def diagram_text(path: Path) -> str:
    """The SVG's words, with the signed manifest and the markup removed."""
    raw = METADATA.sub(" ", path.read_text(encoding="utf-8"))
    return html.unescape(TAG.sub(" ", raw))


def tracked_basenames() -> set[str]:
    """Every tracked file's name without its directory. ``git ls-files`` is the index."""
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {Path(line).name for line in completed.stdout.splitlines() if line}


def spec_check_count() -> int:
    """How many numbered checks the specification has, as the suite counts them.

    Imported from ``test_spec_coverage.py`` rather than reimplemented here. A gate with its
    own copy of the parse can agree with the diagram and disagree with the suite, which is
    two sources of truth wearing one hat. The module imports ``re`` and ``pathlib`` and
    nothing else, so this does not drag pytest into a gate.
    """
    spec = importlib.util.spec_from_file_location("_amr_spec_coverage", COVERAGE_TEST)
    if spec is None or spec.loader is None:  # pragma: no cover - import machinery
        raise ImportError(f"cannot load {COVERAGE_TEST}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return len(module.spec_check_ids())


def declared_operations() -> list[str]:
    """The operations ``MemorySystem`` declares, read out of the source, not imported."""
    tree = ast.parse(PROTOCOL.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "MemorySystem":
            return [
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name not in NOT_AN_OPERATION
            ]
    raise ValueError(f"no MemorySystem class in {PROTOCOL}")


def main() -> int:
    if not DIAGRAM.exists():
        print(f"{DIAGRAM.relative_to(ROOT)} does not exist", file=sys.stderr)
        return 1
    text = diagram_text(DIAGRAM)
    problems: list[str] = []

    named = sorted(set(PY_FILE.findall(text)))
    tracked = tracked_basenames()
    absent = [name for name in named if Path(name).name not in tracked]
    for name in absent:
        problems.append(f"names {name}, which is not a file in this tree")

    expected_checks = spec_check_count()
    counted = [int(found) for found in NUMBERED_CHECKS.findall(text)]
    if not counted:
        problems.append(
            "no 'N numbered checks' phrase: the diagram used to state the check count, "
            "and a gate that checks nothing passes for the wrong reason"
        )
    for found in sorted(set(counted)):
        if found != expected_checks:
            problems.append(
                f"says {found} numbered checks; the specification has {expected_checks}"
            )

    operations = declared_operations()
    stated = OPERATION_COUNT.findall(text.lower())
    if not stated:
        problems.append(
            "no 'N operations' phrase: the diagram used to state the size of the "
            "operation set, and a gate that checks nothing passes for the wrong reason"
        )
    for word in sorted(set(stated)):
        counted_operations = (
            int(word) if word.isdigit() else NUMBER_WORDS.get(word)
        )
        if counted_operations is None:
            problems.append(
                f"says {word!r} operations, which is not a number this gate can read; "
                "write a digit or a word from zero to twenty"
            )
        elif counted_operations != len(operations):
            problems.append(
                f"says {word} operations; MemorySystem declares "
                f"{len(operations)}: {', '.join(operations)}"
            )

    relative = DIAGRAM.relative_to(ROOT)
    for problem in problems:
        print(f"{relative}: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(
        f"{relative}: {len(named)} source files exist, {expected_checks} numbered "
        f"checks, {len(operations)} operations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
