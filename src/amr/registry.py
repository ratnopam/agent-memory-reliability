"""Which systems the suite runs against.

Two sources, deduplicated by name:

1. The ``amr.systems`` entry-point group. Any installed distribution may declare
   ``name = "package.module:factory"`` there and the suite finds it. This is the
   supported way to conform an external system without editing this repository.
2. The in-tree ``systems/*`` subpackages, imported so that an adapter under
   development registers itself before it is packaged.

An entry point wins over an in-tree package of the same name, because an installed
declaration is the more deliberate of the two. Nothing here names an adapter, which is
what keeps ``amr`` neutral.

The ``SYSTEMS`` environment variable filters by name (comma-separated).
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from dataclasses import dataclass
from typing import Callable

from amr.protocol import ForgetMode, MemorySystem

#: The entry-point group an external package declares to be discovered.
ENTRY_POINT_GROUP = "amr.systems"

SystemFactory = Callable[..., MemorySystem]

_REGISTRY: dict[str, SystemFactory] = {}
_SOURCES: dict[str, str] = {}
_DISCOVERED = False


@dataclass(frozen=True)
class Registration:
    name: str
    factory: SystemFactory
    source: str = "in-tree"

    def build(self, mode: ForgetMode | None = None) -> MemorySystem:
        """Instantiate. A factory accepts ``default_forget_mode`` or takes nothing."""
        if mode is None:
            return self.factory()
        return self.factory(default_forget_mode=mode)


def register(name: str, factory: SystemFactory, source: str = "in-tree") -> None:
    """Record ``factory`` under ``name``. The first registration of a name wins.

    Re-registering the same object is a no-op, so an adapter may both call this at
    import time and be named by an entry point without either path having to know
    about the other.
    """
    if name in _REGISTRY:
        if _REGISTRY[name] is not factory:
            raise ValueError(
                f"system {name!r} is already registered from {_SOURCES[name]}"
            )
        return
    _REGISTRY[name] = factory
    _SOURCES[name] = source


def discover() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    _discover_entry_points()
    _discover_in_tree()


def _discover_entry_points() -> None:
    from importlib.metadata import entry_points

    for entry_point in sorted(
        entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name
    ):
        if entry_point.name in _REGISTRY:
            continue
        register(entry_point.name, entry_point.load(), source="entry-point")


def _discover_in_tree() -> None:
    try:
        import systems
    except ImportError:  # pragma: no cover - an install without the in-tree adapters
        return
    for module in sorted(
        pkgutil.iter_modules(systems.__path__), key=lambda m: m.name
    ):
        importlib.import_module(f"systems.{module.name}")


def selected_names() -> tuple[str, ...] | None:
    raw = os.environ.get("SYSTEMS", "").strip()
    if not raw:
        return None
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def systems() -> tuple[Registration, ...]:
    """Every registered system, filtered by ``SYSTEMS``, ordered by name."""
    discover()
    wanted = selected_names()
    names = sorted(_REGISTRY)
    if wanted is not None:
        missing = [name for name in wanted if name not in _REGISTRY]
        if missing:
            raise ValueError(f"unknown system(s) in SYSTEMS: {', '.join(missing)}")
        names = [name for name in names if name in wanted]
    return tuple(
        Registration(name=name, factory=_REGISTRY[name], source=_SOURCES[name])
        for name in names
    )


def named(name: str, mode: ForgetMode | None = None) -> MemorySystem:
    """One registered system, built. For a script that wants a store and not a matrix."""
    for registration in systems():
        if registration.name == name:
            return registration.build(mode)
    raise LookupError(f"no registered system named {name!r}")


def modes_for(registration: Registration) -> tuple[ForgetMode, ...]:
    """The declared forget modes, in specification order (SPEC.md 6.1)."""
    declared = registration.build().capabilities().supported_forget_modes
    return tuple(mode for mode in ForgetMode if mode in declared)
