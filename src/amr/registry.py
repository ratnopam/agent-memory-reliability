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

Three ways to choose what runs, and the default is the narrow one:

* nothing set — every *default* system. This is what ``make test`` and ``make reproduce``
  measure, and it is why adding an adapter to this repository cannot move the published
  matrix: a system registered with ``default=False`` is invisible until asked for.
* ``SYSTEMS=a,b`` — exactly those, default or not. Naming one that is not registered, or
  one whose optional dependency is not installed, is an error rather than an empty run.
* ``AMR_EXTRAS=1`` — the default systems and every extra whose dependencies are present.
  Absent ones are skipped silently here, because nobody named them.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import pkgutil
from dataclasses import dataclass, replace
from typing import Callable

from amr.protocol import ForgetMode, MemorySystem

#: The entry-point group an external package declares to be discovered.
ENTRY_POINT_GROUP = "amr.systems"

SystemFactory = Callable[..., MemorySystem]

_REGISTRY: dict[str, "Registration"] = {}
_DISCOVERED = False


@dataclass(frozen=True)
class Registration:
    """One registered system, and what it takes to run it.

    ``requires`` is import names, not distribution names, because that is what can be
    checked without a metadata lookup and without importing the adapter. ``extra`` is the
    name to put in ``pip install -e ".[...]"`` — carried so that the failure for a missing
    dependency can say what to do about it instead of only what went wrong.
    """

    name: str
    factory: SystemFactory
    source: str = "in-tree"
    default: bool = True
    extra: str | None = None
    requires: tuple[str, ...] = ()

    @property
    def missing(self) -> tuple[str, ...]:
        """The modules ``requires`` names that this interpreter cannot import."""
        return tuple(module for module in self.requires if not _importable(module))

    @property
    def available(self) -> bool:
        return not self.missing

    @property
    def kind(self) -> str:
        """``default`` or ``extra``: whether a run with nothing set includes it."""
        return "default" if self.default else "extra"

    def build(self, mode: ForgetMode | None = None) -> MemorySystem:
        """Instantiate. A factory accepts ``default_forget_mode`` or takes nothing."""
        if mode is None:
            return self.factory()
        return self.factory(default_forget_mode=mode)


def _importable(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        # A parent package that is itself absent, or a name that is not a module path.
        return False


def register(
    name: str,
    factory: SystemFactory,
    source: str = "in-tree",
    *,
    default: bool = True,
    extra: str | None = None,
    requires: tuple[str, ...] = (),
) -> None:
    """Record ``factory`` under ``name``. The first registration of a name wins.

    Re-registering the same object is a no-op, so an adapter may both call this at
    import time and be named by an entry point without either path having to know
    about the other.

    ``default=False`` keeps a system out of every run that did not ask for it by name.
    An adapter that is slower, that needs a package the core does not depend on, or that
    exists to be compared against the reference rather than to be the reference, says so
    here rather than in a conditional somewhere in the runner.
    """
    existing = _REGISTRY.get(name)
    if existing is not None:
        if existing.factory is not factory:
            raise ValueError(
                f"system {name!r} is already registered from {existing.source}"
            )
        # Loading an entry point imports the module, and an in-tree adapter registers
        # itself at import time — so the same factory arrives twice, in-tree first.
        # Record the more deliberate source, or the label would say "in-tree" for a
        # system the suite found by the entry point that imported it.
        if source == "entry-point":
            _REGISTRY[name] = replace(existing, source=source)
        return
    _REGISTRY[name] = Registration(
        name=name,
        factory=factory,
        source=source,
        default=default,
        extra=extra,
        requires=tuple(requires),
    )


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


def extras_requested() -> bool:
    """``AMR_EXTRAS=1``. Anything else, including ``0``, is not a request."""
    return os.environ.get("AMR_EXTRAS", "").strip() == "1"


def registered() -> tuple[Registration, ...]:
    """Every registered system, ordered by name, whatever is selected.

    What ``amr systems`` prints. ``systems()`` is the filtered view; a reader asking
    what exists wants the inventory, including the rows a run would leave out.
    """
    discover()
    return tuple(_REGISTRY[name] for name in sorted(_REGISTRY))


def systems() -> tuple[Registration, ...]:
    """The systems this run measures, ordered by name. See the module docstring."""
    discover()
    wanted = selected_names()
    if wanted is not None:
        return tuple(require(name) for name in sorted(set(wanted)))
    extras = extras_requested()
    return tuple(
        registration
        for registration in registered()
        if registration.default or (extras and registration.available)
    )


def _inventory() -> str:
    rows = []
    for registration in registered():
        note = "" if registration.available else ", not installed"
        rows.append(f"{registration.name} ({registration.kind}{note})")
    return "registered: " + (", ".join(rows) or "none")


def require(name: str) -> Registration:
    """One registered system by name, refusing rather than returning an empty run.

    Two failures, both of which a caller who typed a name wants spelled out: the name is
    not registered at all, or it is registered and its optional dependency is not here.
    The second one used to look like the first — an adapter silently absent from the
    matrix — which reads as "the suite does not support it" rather than "install it".
    """
    discover()
    registration = _REGISTRY.get(name)
    if registration is None:
        raise LookupError(f"no registered system named {name!r}; {_inventory()}")
    missing = registration.missing
    if missing:
        remedy = (
            f'install it with: pip install -e ".[{registration.extra}]"'
            if registration.extra
            else f"install {' and '.join(missing)} to use it"
        )
        raise ModuleNotFoundError(
            f"system {name!r} needs {', '.join(missing)}, which this interpreter "
            f"cannot import; {remedy}. {_inventory()}"
        )
    return registration


def registration(name: str) -> Registration:
    """One registered system by name, whatever ``SYSTEMS`` says.

    ``SYSTEMS`` narrows *a run* — which systems the matrix has columns for. A caller that
    has already named the one system it wants is not running a matrix, and filtering it
    out would mean ``SYSTEMS=mine amr replay`` failed to find the system the trace was
    recorded against. ``systems()`` is the filtered view; this is the lookup.
    """
    return require(name)


def named(name: str, mode: ForgetMode | None = None) -> MemorySystem:
    """One registered system, built. For a script that wants a store and not a matrix."""
    return require(name).build(mode)


def modes_for(registration: Registration) -> tuple[ForgetMode, ...]:
    """The declared forget modes, in specification order (SPEC.md 6.1)."""
    declared = registration.build().capabilities().supported_forget_modes
    return tuple(mode for mode in ForgetMode if mode in declared)
