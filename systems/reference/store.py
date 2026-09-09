"""Records, edges, scopes, grants, visibility, and the serialisation round-trip.

Standard library only, dict-backed, deliberately slow. The store is the only place that
mutates state; confidence, forget, and the façade all read through it.

Identifiers are allocated in order (``m001``, ``m002``, ...). The counter only ever
increases and survives serialisation, which is what makes "never reused after a forget"
(SPEC.md 2) true rather than merely likely.

Visibility lives here because it is a question about stored state and there is no second
answer to it. The rules are SPEC.md I4.1–I4.3 and 3.1, and the short version is: a viewer
sees what it owns plus what a grant covers; anything else is reported exactly as an id
that never existed; a foreign ancestor is opaque in a walk whether or not a grant exists;
and mutation needs ownership, because a read grant grants reading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from amr.protocol import (
    ChainNode,
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

    Unreachable through the operation set: strict writes reject unresolvable sources
    (I1.6) and ``erase`` detaches edges rather than orphaning them. Raised rather than
    skipped, because skipping is taxonomy/silent-chain-truncation.md.
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

    def chain_node(self, viewer: Scope) -> ChainNode:
        """This record as a provenance node, from the viewer's side of the boundary."""
        return ChainNode(
            id=self.id,
            declared_confidence=self.declared_confidence,
            sources=self.sources,
            tombstoned=self.tombstoned,
            opaque=self.scope != viewer,
        )


def _as_dict(record: StoredRecord) -> dict[str, object]:
    """One record, canonically: sorted sources, no set iteration order anywhere."""
    origin = record.origin
    return {
        "id": record.id,
        "content": record.content,
        "declared_confidence": record.declared_confidence,
        "sources": sorted(record.sources),
        "scope": record.scope,
        "origin": None if origin is None else {"kind": origin.kind, "ref": origin.ref},
        "tombstoned": record.tombstoned,
        "revisions": [dict(vars(r)) for r in record.revisions],
    }


def _from_dict(entry: dict) -> StoredRecord:
    origin = entry["origin"]
    return StoredRecord(
        id=entry["id"],
        content=entry["content"],
        declared_confidence=float(entry["declared_confidence"]),
        sources=frozenset(entry["sources"]),
        scope=entry["scope"],
        origin=None if origin is None else Origin(**origin),
        tombstoned=bool(entry["tombstoned"]),
        revisions=[Revision(**r) for r in entry["revisions"]],
    )


class Store:
    """The whole state of a reference memory system."""

    def __init__(self) -> None:
        self._records: dict[MemoryId, StoredRecord] = {}
        self._children: dict[MemoryId, set[MemoryId]] = {}
        self._forgotten: dict[MemoryId, tuple[ForgetMode, Scope]] = {}
        self._grants: set[tuple[Scope, Scope]] = set()
        self._scopes: set[Scope] = set()
        self._counter = 0

    # ------------------------------------------------------------------ writes

    def add(
        self,
        content: object,
        declared_confidence: float,
        sources: Iterable[MemoryId],
        scope: Scope,
        origin: Origin | None = None,
    ) -> StoredRecord:
        """Create a record. Rejects rather than repairs. See I1.1, I1.6, SPEC.md 6.2."""
        if not 0.0 <= float(declared_confidence) <= 1.0:
            raise ValueError(
                f"declared_confidence must be in [0.0, 1.0], got {declared_confidence}"
            )
        source_ids = frozenset(sources)
        for source_id in sorted(source_ids):
            record = self.readable(source_id, scope)
            if record is not None and not record.tombstoned:
                continue
            if record is not None or self.visible_forgotten(source_id, scope):
                # A tombstone keeps its chain position for records that already cited
                # it; it does not accept new ones (SPEC.md 6.2).
                raise ForgottenRecordError(
                    f"cannot derive from forgotten record {source_id!r}"
                )
            # Covers "no such id" and "someone else's id" with one answer: a
            # distinguishable rejection would make a write an existence oracle across the
            # scope boundary, and would let a writer pin a record it cannot read (I1.6).
            raise UnresolvedSourceError(
                f"source {source_id!r} does not resolve in scope {scope!r}"
            )

        self._counter += 1
        record_id = f"m{self._counter:03d}"
        if record_id in self.ancestors(source_ids):
            # Unreachable while ids are freshly allocated and never reused. Kept because
            # I1.1 is an invariant of the store, not of the allocator.
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

    def forget_state(self, memory_id: MemoryId) -> tuple[ForgetMode, Scope] | None:
        return self._forgotten.get(memory_id)

    def records(self) -> tuple[StoredRecord, ...]:
        """Every live or tombstoned record, ordered by id."""
        return tuple(sorted(self._records.values(), key=lambda r: r.id))

    def children(self, memory_id: MemoryId) -> frozenset[MemoryId]:
        return frozenset(self._children.get(memory_id, ()))

    def ancestors(self, seeds: Iterable[MemoryId]) -> frozenset[MemoryId]:
        """Closure over ``sources``, seeds included, each id once (I1.2, I1.3)."""
        return self._closure(seeds, self._parents)

    def descendants(self, memory_id: MemoryId) -> frozenset[MemoryId]:
        """Closure over the reverse edge, across every scope. Excludes the seed."""
        return self._closure(self.children(memory_id), self.children)

    def _parents(self, memory_id: MemoryId) -> frozenset[MemoryId]:
        record = self._records.get(memory_id)
        return record.sources if record is not None else frozenset()

    @staticmethod
    def _closure(seeds, step) -> frozenset[MemoryId]:
        seen: set[MemoryId] = set()
        pending = list(seeds)
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(step(current))
        return frozenset(seen)

    # -------------------------------------------------------------- visibility

    def readable(self, memory_id: MemoryId, viewer: Scope) -> StoredRecord | None:
        """The record if the viewer may see it at all, else ``None``.

        "See it at all" includes tombstones: a tombstone is not readable content, but its
        existence is not hidden from a scope that could see the record.
        """
        record = self._records.get(memory_id)
        if record is None:
            return None
        if record.scope == viewer or (record.scope, viewer) in self._grants:
            return record
        return None

    def visible_forgotten(self, memory_id: MemoryId, viewer: Scope) -> bool:
        """Whether this viewer may be told the id was forgotten rather than absent."""
        state = self._forgotten.get(memory_id)
        if state is None:
            return False
        owner = state[1]
        return owner == viewer or (owner, viewer) in self._grants

    def native_live_ids(self, scope: Scope) -> frozenset[MemoryId]:
        """What ``list_scope`` returns: native and not tombstoned (I3.2, SPEC.md 7).

        Granted records are excluded. A grant makes a record readable, not resident, and
        listing them would make ``list_scope`` a directory of another scope's contents.
        """
        return frozenset(
            record.id
            for record in self._records.values()
            if record.scope == scope and not record.tombstoned
        )

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

    def readers_of(self, owner: Scope) -> frozenset[Scope]:
        return frozenset(reader for granted, reader in self._grants if granted == owner)

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
            "records": [_as_dict(record) for record in self.records()],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> Store:
        store = cls()
        if payload.get("format") != STORE_FORMAT:
            raise ValueError(f"unsupported store format {payload.get('format')!r}")
        store._counter = int(payload["counter"])
        store._scopes = set(payload.get("scopes", []))
        store._grants = {(owner, reader) for owner, reader in payload.get("grants", [])}
        for entry in payload.get("forgotten", []):
            store._forgotten[entry["id"]] = (ForgetMode(entry["mode"]), entry["scope"])
        for entry in payload.get("records", []):
            store._install(_from_dict(entry))
        store._validate()
        return store

    def _validate(self) -> None:
        """Reject a deserialised graph that dangles or is cyclic (I1.1, I1.4, P1.7).

        This is where I1.1 stays falsifiable. A write allocates its own id, so no write can
        close a cycle; a snapshot's edges are caller-supplied and can. Dangling first, so
        that a snapshot with both faults names the one a reader can act on.
        """
        for record in self._records.values():
            missing = record.sources - self._records.keys()
            if missing:
                raise StoreIntegrityError(
                    f"{record.id!r} cites unresolvable source {min(missing)!r}"
                )
        for record in self._records.values():
            if record.id in self.ancestors(record.sources):
                raise CycleError(f"{record.id!r} is its own ancestor")
