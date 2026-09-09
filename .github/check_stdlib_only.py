"""Fails if systems/reference/ imports anything outside the standard library.

The neutrality claim rests on this: the reference implementation must not import a memory
product, a vector store, a database driver, or a model client, and the way to keep that
true is to allow nothing but the standard library and the protocol definitions the suite
itself owns. Checked in CI so the claim cannot rot.

Run: python .github/check_stdlib_only.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "systems" / "reference"

#: The suite's own modules. Not third-party, and not the standard library either.
OWN = {"amr", "systems"}

#: Names that must not appear even if some environment happens to provide them.
FORBIDDEN = {"sqlite3", "pgvector", "opensearch", "opensearchpy", "psycopg", "psycopg2"}


def top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # a relative import stays inside the package
                continue
            if node.module:
                found.add(node.module.split(".")[0])
    return found


def main() -> int:
    allowed = set(sys.stdlib_module_names) | OWN
    problems: list[str] = []
    for path in sorted(TARGET.rglob("*.py")):
        for name in sorted(top_level_imports(path)):
            relative = path.relative_to(ROOT)
            if name in FORBIDDEN:
                problems.append(f"{relative}: imports {name}, which is forbidden here")
            elif name not in allowed:
                problems.append(f"{relative}: imports {name}, which is not stdlib")
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(f"{TARGET.relative_to(ROOT)}: standard library only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
