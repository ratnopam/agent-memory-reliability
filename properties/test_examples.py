"""The examples run, and print what they are quoted as printing.

An example whose output has drifted is worse than no example: it is a claim about the
system that nobody checked. So the transcript is asserted here line for line, and the
script runs in a subprocess the way a reader would run it rather than being imported.
"""

from __future__ import annotations

import os
import re
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

USE_IT = """\
declared  0.95
effective 0.40  <- bounded by the hearsay

forget(m002) mode=tombstone forgotten=['m002']
  m003: 0.40 -> 0.40
get(m002) -> forgotten
effective 0.40  <- the bound survived the forget
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
        # SYSTEMS is cleared because the example names the reference and asserts its
        # numbers; a caller measuring their own system must not change what it prints.
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(root / "src"), str(root)]),
            "SYSTEMS": "",
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


@pytest.mark.extra("example-use-it")
def test_use_it_prints_the_bound_and_the_receipt() -> None:
    """A declared 0.95 reads 0.40, and the forget comes back as a receipt."""
    assert _run("use_it.py") == USE_IT


#: Fenced blocks, as ``(info string, body)``. The fences are anchored to the start of a
#: line and paired in one pass, because a pattern that is not will read the *closing*
#: fence of one block and the opening fence of the next as a pair and silently find
#: nothing where the body it was asked for is.
_FENCE = re.compile(r"^```([^\n]*)\n(.*?)^```$", re.DOTALL | re.MULTILINE)


def _fenced(text: str, language: str = "") -> list[str]:
    return [body for info, body in _FENCE.findall(text) if info.strip() == language]


def test_the_readme_embeds_use_it_and_its_output() -> None:
    """The README's Python example is the file, and its transcript is the run.

    The README is the one document a reader trusts before running anything, so the
    snippet in it is not a paraphrase of ``examples/use_it.py`` — it is that file, and
    the block under it is that file's stdout. Both are compared here rather than
    maintained by hand, the same way ``properties/test_taxonomy.py`` holds the taxonomy
    entries to the modules they document.
    """
    root = repo_root()
    readme = (root / "README.md").read_text(encoding="utf-8")
    source = (root / "examples" / "use_it.py").read_text(encoding="utf-8")
    assert source in _fenced(readme, "python"), (
        "README.md does not embed the current source of examples/use_it.py"
    )
    assert USE_IT in _fenced(readme), (
        "README.md does not quote the current output of examples/use_it.py"
    )
