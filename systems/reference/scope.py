"""Isolation, grants, and opaque ancestors.

Three rules, in the order they are applied:

1. **Reads are scope-bound.** A record is visible to a viewer if the viewer owns it or
   the owning scope granted the viewer read access (I4.1, I4.2).
2. **An invisible record is indistinguishable from a record that never existed.**
   ``get`` answers ``NOT_FOUND``, not ``FORGOTTEN`` and not an error. Anything else
   turns the boundary into an existence oracle.
3. **A foreign ancestor is always opaque, grant or no grant.** A provenance walk carries
   ids, confidences, and edges; it never carries content across a boundary (I4.3). The
   grant is what makes ``get`` work; it is not a licence for the walk to leak payload.

Mutation (``revise``, ``forget``) requires ownership, not a grant. A grant is a read
grant; nothing in SPEC.md 7 says otherwise.
"""

from __future__ import annotations

from harness.protocol import ChainNode, Scope
from systems.reference.store import StoredRecord, Store


def visible(store: Store, record: StoredRecord, viewer: Scope) -> bool:
    return record.scope == viewer or (record.scope, viewer) in store.grants()


def readable(store: Store, memory_id: str, viewer: Scope) -> StoredRecord | None:
    """The record if the viewer may see it at all, else ``None``.

    "See it at all" includes tombstones: a tombstone is not readable content, but its
    existence is not hidden from the scope that owns it.
    """
    record = store.record(memory_id)
    if record is None or not visible(store, record, viewer):
        return None
    return record


def owned(store: Store, memory_id: str, viewer: Scope) -> StoredRecord | None:
    record = store.record(memory_id)
    if record is None or record.scope != viewer:
        return None
    return record


def native_live_ids(store: Store, scope: Scope) -> frozenset[str]:
    """What ``list_scope`` returns.

    Records native to the scope and still readable. Tombstones are excluded (I3.2), and
    so are granted records: a grant makes a record readable, not resident. Listing
    granted records would make ``list_scope`` a directory of another scope's contents.
    """
    return frozenset(
        record.id
        for record in store.records()
        if record.scope == scope and not record.tombstoned
    )


def chain_node(record: StoredRecord, viewer: Scope) -> ChainNode:
    """Project a record into a provenance node from the viewer's side of the boundary."""
    return ChainNode(
        id=record.id,
        declared_confidence=record.declared_confidence,
        sources=record.sources,
        tombstoned=record.tombstoned,
        opaque=record.scope != viewer,
    )
