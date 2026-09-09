"""Optional operations the suite feature-detects.

SPEC.md 3 defines eight operations. Two invariants cannot be checked through them:

* **I4.2** requires that cross-scope visibility is granted and revoked, and nothing in
  the operation set grants anything.
* **I1.5** requires that provenance survives a process restart, and nothing in the
  operation set closes and reopens a store.

Rather than widen the specified operation set, both live here as optional protocols.
A system that declares ``scopes: "native"`` and does not implement ``ScopeSharing``
fails P4.2; a system that declares a durability other than ``"none"`` and does not
implement ``Reopenable`` fails P1.5. Proposed specification text for both is in
design-notes/spec-feedback.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from harness.protocol import MemorySystem, Scope


@dataclass(frozen=True)
class GrantReceipt:
    """The record of a grant or a revocation. See SPEC.md I4.2."""

    owner: Scope
    reader: Scope
    granted: bool


@runtime_checkable
class ScopeSharing(Protocol):
    """Explicit, revocable cross-scope read grants. See SPEC.md I4.2."""

    def grant(self, owner: Scope, reader: Scope) -> GrantReceipt:
        """Let ``reader`` read records native to ``owner``."""

    def revoke(self, owner: Scope, reader: Scope) -> GrantReceipt:
        """Withdraw the grant. Revocation is immediate."""

    def grants(self) -> frozenset[tuple[Scope, Scope]]:
        """Every live ``(owner, reader)`` pair."""


@runtime_checkable
class Reopenable(Protocol):
    """Round-trip durability. See SPEC.md I1.5."""

    def to_dict(self) -> dict[str, object]:
        """A JSON-serialisable snapshot of the whole store."""

    def reopen(self) -> MemorySystem:
        """Serialise, discard this instance, deserialise, return the new one.

        The returned system must answer every read identically. This stands in for a
        process restart without requiring the suite to spawn one.
        """
