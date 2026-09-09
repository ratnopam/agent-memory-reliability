"""An external package can conform a system without editing this repository.

That claim is the whole of ``amr``'s extensibility story, so it is tested rather than
asserted in a README. The test builds a throwaway distribution in a temporary directory
-- a module and the ``*.dist-info`` an install produces, including the ``entry_points.txt``
that declares the ``amr.systems`` group -- puts it on ``sys.path``, and asks the registry
what it can see.

Written by hand rather than by ``pip install`` on purpose: pip's default build isolation
reaches the network for setuptools, and the suite is not allowed to. ``entry_points.txt``
inside a ``.dist-info`` directory on ``sys.path`` is exactly the artefact a real install
leaves behind, and ``importlib.metadata`` reads it by the same code path either way.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Iterator

import pytest

from amr import registry

DISTRIBUTION = "throwaway-memory"
MODULE = "throwaway_memory"

MODULE_SOURCE = '''\
"""A stand-in for somebody else's adapter. Never built, only discovered."""


def factory(**kwargs):
    raise NotImplementedError("a placeholder for a real adapter")
'''

METADATA = f"""\
Metadata-Version: 2.1
Name: {DISTRIBUTION}
Version: 0.0.0
"""


def _install(directory: Path, entry_points: str) -> None:
    """Lay out what ``pip install`` would leave on ``sys.path``, and nothing more."""
    (directory / f"{MODULE}.py").write_text(MODULE_SOURCE, encoding="utf-8")
    dist_info = directory / f"{MODULE}-0.0.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(METADATA, encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(
        f"[{registry.ENTRY_POINT_GROUP}]\n{entry_points}\n", encoding="utf-8"
    )


@pytest.fixture
def installed(tmp_path: Path) -> Iterator[callable]:
    """Install a throwaway distribution, then put the process back as it was.

    The registry memoises discovery in module state, which is right for a suite run and
    wrong for a test that changes what is discoverable, so the state is saved and restored
    around the whole thing.
    """
    saved = (dict(registry._REGISTRY), dict(registry._SOURCES), registry._DISCOVERED)
    saved_path = list(sys.path)

    def install(entry_points: str) -> tuple[registry.Registration, ...]:
        _install(tmp_path, entry_points)
        sys.path.insert(0, str(tmp_path))
        importlib.invalidate_caches()
        registry._REGISTRY.clear()
        registry._SOURCES.clear()
        registry._DISCOVERED = False
        return registry.systems()

    yield install

    sys.path[:] = saved_path
    importlib.invalidate_caches()
    registry._REGISTRY.clear()
    registry._REGISTRY.update(saved[0])
    registry._SOURCES.clear()
    registry._SOURCES.update(saved[1])
    registry._DISCOVERED = saved[2]
    if MODULE in sys.modules:
        del sys.modules[MODULE]


@pytest.mark.extra("entry-point-discovery")
def test_an_external_distribution_is_discovered(installed) -> None:
    """A package declaring amr.systems is found with no edit to this repository."""
    found = installed(f"throwaway = {MODULE}:factory")
    by_name = {registration.name: registration for registration in found}
    assert "throwaway" in by_name, f"discovered {sorted(by_name)}"
    assert by_name["throwaway"].source == "entry-point"
    assert "reference" in by_name, "the in-tree adapters are still discovered alongside it"


@pytest.mark.extra("entry-point-deduplication")
def test_an_entry_point_wins_over_an_in_tree_package_of_the_same_name(installed) -> None:
    """One name, one registration: the declared install wins, and nothing is listed twice."""
    found = installed(f"reference = {MODULE}:factory")
    names = [registration.name for registration in found]
    assert names.count("reference") == 1, names
    winner = next(r for r in found if r.name == "reference")
    assert winner.source == "entry-point"
    assert winner.factory.__module__ == MODULE
