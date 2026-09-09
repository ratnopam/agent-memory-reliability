"""Records, edges, scopes, grants, and the serialisation round-trip.

Standard library only, dict-backed, and deliberately slow. The store is the only place
that mutates state; confidence, forget, and scope logic all read through it.

Identifiers are opaque strings allocated in order (``m001``, ``m002``, ...). The counter
only ever increases and survives serialisation, which is what makes "never reused after
a forget" (SPEC.md 2) true rather than merely likely.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from harness.protocol import (
    CycleError,
    ForgetMode,
    ForgottenRecordError,
    MemoryId,
    Origin,
    Scope,
    UnresolvedSourceError,
)

STORE_FORMAT = "1"


class StoreIntegrityError(Exception):
    """A source id held by a live record does not resolve.

    This should be unreachable: strict writes (I1.6) reject unresolvable sources at
    write time, and ``erase`` detaches edges rather than leaving them dangling. It is
    raised rather than skipped because silently skipping an unresolvable ancestor is
    exactly the failure mode in taxonomy/silent-chain-truncation.md.
    """


@dataclass
class Revision:
    """One entry in a record's revision history. See SPEC.md I2.6."""

    before: float
    after: float
    reason: str


@dataclass
class StoredRecord:
    id: MemoryId
    content: object | None
    declared_confidence: float
    sources: frozenset[MemoryId]
    scope: Scope
    origin: Origin | None = None
    tombstoned: bool = False
    revisions: list[Revision] = field(default_factory=list)


class Store:
    """The whole state of a reference memory system."""

    def __init__(self) -> None:
        self._records: dict[MemoryId, StoredRecord] = {}
        self._children: dict[MemoryId, set[MemoryId]] = {}
        self._forgotten: dict[MemoryId, tuple[ForgetMode, Scope]] = {}
        self._grants: set[tuple[Scope, Scope]] = set()
        self._scopes: set[Scope] = set()
        self._counter = 0

    # ---------------------------------------------------------------- identity

    def allocate_id(self) -> MemoryId:
        self._counter += 1
        return f"m{self._counter:03d}"

    # ------------------------------------------------------------------ writes

    def add(
        self,
        content: object,
        declared_confidence: float,
        sources: Iterable[MemoryId],
        scope: Scope,
        origin: Origin | None = None,
    ) -> StoredRecord:
        """Create a record. Rejects rather than repairs. See I1.1, I1.6."""
        if not 0.0 <= float(declared_confidence) <= 1.0:
            raise ValueError(
                f"declared_confidence must be in [0.0, 1.0], got {declared_confidence}"
            )
        source_ids = frozenset(sources)
        for source_id in sorted(source_ids):
            if source_id in self._records:
                if self._records[source_id].tombstoned:
                    raise ForgottenRecordError(
                        f"cannot derive from forgotten record {source_id!r}"
                    )
                continue
            if source_id in self._forgotten:
                raise ForgottenRecordError(
                    f"cannot derive from forgotten record {source_id!r}"
                )
            raise UnresolvedSourceError(f"source {source_id!r} does not resolve")

        record_id = self.allocate_id()
        if record_id in source_ids or record_id in self.ancestors(source_ids):
            # Unreachable while ids are freshly allocated and never reused. Kept as a
            # guard because I1.1 is an invariant of the store, not of the allocator.
            raise CycleError(f"{record_id!r} would be its own ancestor")

        record = StoredRecord(
            id=record_id,
            content=content,
            declared_confidence=float(declared_confidence),
            sources=source_ids,
            scope=scope,
            origin=origin,
        )
        self._install(record)
        return record

    def _install(self, record: StoredRecord) -> None:
        self._records[record.id] = record
        self._children.setdefault(record.id, set())
        self._scopes.add(record.scope)
        for source_id in record.sources:
            self._children.setdefault(source_id, set()).add(record.id)

    # ------------------------------------------------------------------- reads

    def record(self, memory_id: MemoryId) -> StoredRecord | None:
        return self._records.get(memory_id)

    def require(self, memory_id: MemoryId) -> StoredRecord:
        record = self._records.get(memory_id)
        if record is None:
            raise StoreIntegrityError(f"{memory_id!r} does not resolve")
        return record

    def is_forgotten(self, memory_id: MemoryId) -> bool:
        return memory_id in self._forgotten

    def forget_state(self, memory_id: MemoryId) -> tuple[ForgetMode, Scope] | None:
        return self._forgotten.get(memory_id)

    def known(self, memory_id: MemoryId) -> bool:
        return memory_id in self._records or memory_id in self._forgotten

    def ids(self) -> frozenset[MemoryId]:
        return frozenset(self._records)

    def records(self) -> tuple[StoredRecord, ...]:
        """Every live or tombstoned record, ordered by id."""
        return tuple(sorted(self._records.values(), key=lambda r: r.id))

    def scopes(self) -> frozenset[Scope]:
        return frozenset(self._scopes)

    def children(self, memory_id: MemoryId) -> frozenset[MemoryId]:
        return frozenset(self._children.get(memory_id, ()))

    def ancestors(self, seeds: Iterable[MemoryId]) -> frozenset[MemoryId]:
        """Transitive closure over ``sources``. Each ancestor once (I1.3)."""
        seen: set[MemoryId] = set()
        pending = [s for s in seeds]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            record = self._records.get(current)
            if record is not None:
                pending.extend(record.sources)
        return frozenset(seen)

    def descendants(self, memory_id: MemoryId) -> frozenset[MemoryId]:
        """Transitive closure over the reverse edge, across every scope."""
        seen: set[MemoryId] = set()
        pending = list(self.children(memory_id))
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(self.children(current))
        return frozenset(seen)

    # ---------------------------------------------------------------- mutation

    def set_declared(self, memory_id: MemoryId, value: float) -> None:
        self.require(memory_id).declared_confidence = float(value)

    def append_revision(self, memory_id: MemoryId, revision: Revision) -> None:
        self.require(memory_id).revisions.append(revision)

    def tombstone(self, memory_id: MemoryId) -> None:
        """Erase content; keep id, declared confidence, and sources (SPEC.md 6.1)."""
        record = self.require(memory_id)
        record.content = None
        record.tombstoned = True
        self._forgotten[memory_id] = (ForgetMode.TOMBSTONE, record.scope)

    def remove(self, memory_id: MemoryId, mode: ForgetMode) -> None:
        """Drop the record itself, keeping only the fact that it was forgotten."""
        record = self.require(memory_id)
        for source_id in record.sources:
            self._children.get(source_id, set()).discard(memory_id)
        self._children.pop(memory_id, None)
        del self._records[memory_id]
        self._forgotten[memory_id] = (mode, record.scope)

    def detach_source(self, child_id: MemoryId, source_id: MemoryId) -> None:
        """Remove one edge. Used by ``erase``, which shortens surviving chains."""
        child = self.require(child_id)
        child.sources = child.sources - {source_id}
        self._children.get(source_id, set()).discard(child_id)

    # ------------------------------------------------------------------ grants

    def grants(self) -> frozenset[tuple[Scope, Scope]]:
        return frozenset(self._grants)

    def add_grant(self, owner: Scope, reader: Scope) -> None:
        self._scopes.update({owner, reader})
        self._grants.add((owner, reader))

    def drop_grant(self, owner: Scope, reader: Scope) -> None:
        self._grants.discard((owner, reader))

    # --------------------------------------------------------------- durability

    def to_dict(self) -> dict[str, object]:
        """A canonical, sorted, JSON-serialisable snapshot. See I1.5."""
        return {
            "format": STORE_FORMAT,
            "counter": self._counter,
            "scopes": sorted(self._scopes),
            "grants": [[owner, reader] for owner, reader in sorted(self._grants)],
            "forgotten": [
                {"id": memory_id, "mode": mode.value, "scope": scope}
                for memory_id, (mode, scope) in sorted(self._forgotten.items())
            ],
            "records": [
                {
                    "id": record.id,
                    "content": record.content,
                    "declared_confidence": record.declared_confidence,
                    "sources": sorted(record.sources),
                    "scope": record.scope,
                    "origin": (
                        None
                        if record.origin is None
                        else {"kind": record.origin.kind, "ref": record.origin.ref}
                    ),
                    "tombstoned": record.tombstoned,
                    "revisions": [
                        {
                            "before": revision.before,
                            "after": revision.after,
                            "reason": revision.reason,
                        }
                        for revision in record.revisions
                    ],
                }
                for record in sorted(self._records.values(), key=lambda r: r.id)
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> Store:
        store = cls()
        if payload.get("format") != STORE_FORMAT:
            raise ValueError(f"unsupported store format {payload.get('format')!r}")
        store._counter = int(payload["counter"])  # type: ignore[arg-type]
        store._scopes = set(payload.get("scopes", []))  # type: ignore[arg-type]
        for owner, reader in payload.get("grants", []):  # type: ignore[union-attr]
            store._grants.add((owner, reader))
        for entry in payload.get("forgotten", []):  # type: ignore[union-attr]
            store._forgotten[entry["id"]] = (
                ForgetMode(entry["mode"]),
                entry["scope"],
            )
        for entry in payload.get("records", []):  # type: ignore[union-attr]
            origin = entry["origin"]
            store._install(
                StoredRecord(
                    id=entry["id"],
                    content=entry["content"],
                    declared_confidence=float(entry["declared_confidence"]),
                    sources=frozenset(entry["sources"]),
                    scope=entry["scope"],
                    origin=None if origin is None else Origin(**origin),
                    tombstoned=bool(entry["tombstoned"]),
                    revisions=[Revision(**r) for r in entry["revisions"]],
                )
            )
        store._validate()
        return store

    def _validate(self) -> None:
        """Reject a deserialised graph that is dangling or cyclic (I1.1, I1.4)."""
        for record in self._records.values():
            for source_id in record.sources:
                if source_id not in self._records:
                    raise StoreIntegrityError(
                        f"{record.id!r} cites unresolvable source {source_id!r}"
                    )
        for record in self._records.values():
            if record.id in self.ancestors(record.sources):
                raise CycleError(f"{record.id!r} is its own ancestor")
