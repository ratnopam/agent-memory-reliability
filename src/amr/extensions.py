"""The one operation the suite feature-detects.

SPEC.md 3 defines twelve operations. Grants used to live here; entry 2 moved them into
the specified set, because P4.2 checks a required invariant and a check for a required
invariant cannot depend on a mechanism the specification declines to name.

Durability stays optional, and stays here, because it is not an operation on a record:
I1.5 requires that provenance survives a restart, and a store's lifecycle is outside the
operation boundary. A system declaring `durability` other than ``in-memory`` and not
implementing ``Reopenable`` fails P1.5 and P1.7 — the declaration is the promise, this
protocol is how the suite collects on it. A system declaring ``in-memory`` fails P1.5
outright (SPEC.md 8); there is no exemption.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from amr.protocol import MemorySystem


@runtime_checkable
class Reopenable(Protocol):
    """Round-trip durability. See SPEC.md I1.5, P1.5, P1.7."""

    def to_dict(self) -> dict[str, object]:
        """A JSON-serialisable snapshot of the whole store.

        I1.5 makes part of the shape normative: somewhere in the returned structure is a
        list of record objects, each with a string ``id`` and a list of string
        ``sources``. That is the minimum an external validator needs to check
        acyclicity and referential integrity without knowing the storage format, and it
        is what P1.7 reads. Everything else in the snapshot is the implementation's.
        """

    def reopen(self) -> MemorySystem:
        """Serialise, discard this instance, deserialise, return the new one.

        The returned system must answer every read identically. This stands in for a
        process restart without requiring the suite to spawn one.
        """

    def load(self, snapshot: Mapping[str, object]) -> MemorySystem:
        """Build a system from a snapshot in ``to_dict`` form.

        Raises ``CycleError`` if the snapshot's edges contain a cycle (P1.7) and
        ``UnresolvedSourceError`` if any ``sources`` entry dangles (I1.4). Separate from
        ``reopen`` because P1.7 has to load a snapshot this instance did not produce.
        """
