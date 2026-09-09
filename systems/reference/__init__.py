"""The reference memory system: standard library only, dict-backed, readable.

It exists to be read and to give the conformance suite something to run against. It is
not a memory product and imports nothing from one.
"""

from __future__ import annotations

from harness.registry import register
from systems.reference.system import (
    SYSTEM_NAME,
    SYSTEM_VERSION,
    ReferenceSystem,
)

register(SYSTEM_NAME, ReferenceSystem)

__all__ = ["SYSTEM_NAME", "SYSTEM_VERSION", "ReferenceSystem"]
