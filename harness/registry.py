"""Which systems the suite runs against.

An adapter calls ``register`` at import time. ``discover`` imports every subpackage of
``systems`` so that registration happens without the harness naming any adapter, which
is what keeps the harness neutral.

The ``SYSTEMS`` environment variable filters by name (comma-separated).
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from dataclasses import dataclass
from typing import Callable

from harness.protocol import ForgetMode, MemorySystem

SystemFactory = Callable[..., MemorySystem]

_REGISTRY: dict[str, SystemFactory] = {}
_DISCOVERED = False


@dataclass(frozen=True)
class Registration:
    name: str
    factory: SystemFactory

    def build(self, mode: ForgetMode | None = None) -> MemorySystem:
        """Instantiate. A factory accepts ``default_forget_mode`` or takes nothing."""
        if mode is None:
            return self.factory()
        return self.factory(default_forget_mode=mode)


def register(name: str, factory: SystemFactory) -> None:
    if name in _REGISTRY and _REGISTRY[name] is not factory:
        raise ValueError(f"system {name!r} is already registered")
    _REGISTRY[name] = factory


def discover() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    import systems

    for module in pkgutil.iter_modules(systems.__path__):
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
    return tuple(Registration(name=name, factory=_REGISTRY[name]) for name in names)


def modes_for(registration: Registration) -> tuple[ForgetMode, ...]:
    """The declared forget modes, in specification order (SPEC.md 6.1)."""
    declared = registration.build().capabilities().supported_forget_modes
    return tuple(mode for mode in ForgetMode if mode in declared)
