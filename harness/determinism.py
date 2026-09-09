"""Proves the suite is deterministic by running it twice and comparing bytes.

The two runs are separate subprocesses, not two calls in one process. A same-process
repeat shares imported modules, memoised registries, and one hash seed, which is exactly
the state a nondeterminism bug would hide in. Subprocesses get a fresh interpreter each,
and ``PYTHONHASHSEED`` is deliberately *not* pinned, so a result that depends on set
iteration order fails here rather than in six months on someone else's machine.

Compared: ``raw.json`` with the volatile fields removed, and ``summary.md`` with its
generated-at line removed. The timestamp is the only thing allowed to differ.
"""

from __future__ import annotations

import difflib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness.results import SCHEMA_VERSION, VOLATILE_FIELDS, serialise, strip_volatile

GENERATED_PREFIX = "Generated "


@dataclass(frozen=True)
class Comparison:
    """The result of one determinism run."""

    identical: bool
    diffs: dict[str, str]
    runs: tuple[Path, Path]

    def report(self) -> str:
        if self.identical:
            return (
                "determinism: two runs produced byte-identical results\n"
                f"  compared raw.json (ignoring {', '.join(VOLATILE_FIELDS)}) "
                "and summary.md (ignoring the generated-at line)\n"
                f"  schema {SCHEMA_VERSION}"
            )
        lines = ["determinism: FAILED — two runs of the same tree disagree"]
        for name, diff in self.diffs.items():
            lines.append(f"--- {name}")
            lines.append(diff)
        return "\n".join(lines)


def _reproduce_into(root: Path, directory: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "harness", "reproduce", "--out", str(directory), "--quiet"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "a determinism run did not finish cleanly "
            f"(exit {completed.returncode})\n{completed.stdout}\n{completed.stderr}"
        )


def _canonical_json(path: Path) -> str:
    return serialise(strip_volatile(json.loads(path.read_text(encoding="utf-8"))))


def _canonical_summary(path: Path) -> str:
    kept = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.startswith(GENERATED_PREFIX)
    ]
    return "\n".join(kept) + "\n"


def _diff(name: str, left: str, right: str) -> str:
    return "".join(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=f"run-1/{name}",
            tofile=f"run-2/{name}",
        )
    )


def compare_two_runs(root: Path) -> Comparison:
    with tempfile.TemporaryDirectory(prefix="amr-determinism-") as workspace:
        first = Path(workspace) / "run-1"
        second = Path(workspace) / "run-2"
        _reproduce_into(root, first)
        _reproduce_into(root, second)
        diffs: dict[str, str] = {}
        for name, canonicalise in (
            ("raw.json", _canonical_json),
            ("summary.md", _canonical_summary),
        ):
            left = canonicalise(first / name)
            right = canonicalise(second / name)
            if left != right:
                diffs[name] = _diff(name, left, right)
        return Comparison(
            identical=not diffs, diffs=diffs, runs=(first, second)
        )
