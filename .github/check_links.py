"""Fails if a relative link in the documents a reader arrives at points at nothing.

The README is where every claim in this repository is read, and a link from it to a file
that was renamed is the cheapest possible way to look careless. So the links are checked
rather than trusted, in the places a first-time reader lands: the README, the contributing
guide, the changelog, and everything under ``docs/``.

Only relative targets are checked. An external URL is somebody else's uptime and this
script will not reach the network to find out; ``http``, ``https`` and ``mailto`` are
skipped deliberately. A bare ``#fragment`` is skipped too: this checks that files exist,
not that headings do.

Run: python .github/check_links.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

#: Markdown inline links and images, which are the same syntax with one character between
#: them. Reference-style links are not used anywhere here; if that changes, so does this.
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

#: Targets nothing local is expected to answer for.
EXTERNAL = ("http://", "https://", "mailto:", "//")


def documents() -> list[Path]:
    """The pages a reader arrives at. One line to add another."""
    found = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "CHANGELOG.md"]
    found.extend(sorted((ROOT / "docs").rglob("*.md")))
    return [path for path in found if path.is_file()]


def targets(text: str) -> list[str]:
    """Every relative link target in one document, in the order they are written."""
    found = []
    for raw in LINK.findall(text):
        # `](path "title")` is legal Markdown, and the title is not part of the path.
        target = raw.split()[0].strip("<>")
        if target.startswith(EXTERNAL) or target.startswith("#"):
            continue
        found.append(target)
    return found


def resolve(document: Path, target: str) -> Path:
    """A link is relative to the file it is written in, and a fragment is not a path."""
    path, _, _ = unquote(target).partition("#")
    return (document.parent / path).resolve() if path else document


def main() -> int:
    problems: list[str] = []
    for document in documents():
        links = targets(document.read_text(encoding="utf-8"))
        broken = [link for link in links if not resolve(document, link).exists()]
        relative = document.relative_to(ROOT)
        for link in broken:
            problems.append(f"{relative}: {link} does not exist")
        if not broken:
            print(f"{relative}: {len(links)} relative links resolve")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
