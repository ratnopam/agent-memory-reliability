"""The examples run, and print what they are quoted as printing.

An example whose output has drifted is worse than no example: it is a claim about the
system that nobody checked. So the transcript is asserted here line for line, and the
script runs in a subprocess the way a reader would run it rather than being imported.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from amr.paths import repo_root

ERASURE_INFLATION = """\
effective(plan), ticket present    0.40
effective(plan), ticket tombstoned 0.40
effective(plan), ticket erased     0.90

The plan was never revised. Erasing its weakest ancestor left min() with an
empty chain, which is 1.0, so the plan rose from 0.40 to 0.90.
"""

#: An example is a thing you read in one screen. Past this it is a program.
MAX_LINES = 32


def _run(name: str) -> str:
    root = repo_root()
    script = root / "examples" / name
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        # As a reader would, from a checkout: no install, no conftest on the path.
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(root / "src"), str(root)]),
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert len(script.read_text(encoding="utf-8").splitlines()) <= MAX_LINES, (
        f"{name} has outgrown one screen"
    )
    return completed.stdout


@pytest.mark.extra("example-erasure-inflation")
def test_erasure_inflation_prints_three_comparable_numbers() -> None:
    """Erasing the weakest ancestor raises the descendant. SPEC.md 6.4."""
    assert _run("erasure_inflation.py") == ERASURE_INFLATION
