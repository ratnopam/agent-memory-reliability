"""The reference memory system: standard library only, dict-backed, readable.

It exists to be read and to give the conformance suite something to run against. It is not
a memory product and imports nothing from one.

``factory`` is the ``amr.systems`` entry-point target (see pyproject.toml); the ``register``
call covers an in-tree checkout that has not been installed. Both resolve to the same
object, so the registry deduplicates rather than conflicts.
"""

from __future__ import annotations

from amr.registry import register
from systems.reference.system import SYSTEM_NAME, SYSTEM_VERSION, ReferenceSystem

factory = ReferenceSystem
register(SYSTEM_NAME, factory)

__all__ = ["SYSTEM_NAME", "SYSTEM_VERSION", "ReferenceSystem", "factory"]
