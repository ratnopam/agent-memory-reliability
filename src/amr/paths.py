"""Where the repository is, from wherever ``amr`` was installed.

The console script can be launched from anywhere, and an editable install puts the
package under ``src/`` rather than beside ``properties/``. Every command needs the
repository itself — the specification, the property tests, the results directory — so the
root is located rather than assumed: the working directory and its parents first, then the
directory the package was installed from.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Present in a checkout and in nothing else.
MARKERS = ("properties", "version2", "systems")

SPEC_RELATIVE = Path("version2") / "SPEC.md"


class RootNotFound(RuntimeError):
    """The command needs the repository and could not find it."""


def _is_root(candidate: Path) -> bool:
    return all((candidate / marker).is_dir() for marker in MARKERS)


def _search(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if _is_root(candidate):
            return candidate
    return None


def repo_root() -> Path:
    """The checkout this command is operating on."""
    override = os.environ.get("AMR_ROOT")
    if override:
        candidate = Path(override).resolve()
        if not _is_root(candidate):
            raise RootNotFound(f"AMR_ROOT={override} is not an amr checkout")
        return candidate
    for start in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        found = _search(start)
        if found is not None:
            return found
    raise RootNotFound(
        "no amr checkout found from the working directory or the installed package; "
        f"expected a directory containing {', '.join(MARKERS)}, or set AMR_ROOT"
    )


def spec_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / SPEC_RELATIVE
