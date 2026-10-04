"""``WriteThrough`` — the reference system, unchanged, with a store behind it.

The reference is a dict in a process. This makes it survive a process, and it does so
without touching ``systems/reference/``: it composes a ``ReferenceSystem``, lets it decide
everything it already decides, and after every call that changes state writes the result
out through a four-method backend. Nothing here computes a confidence, resolves a scope,
or chooses what a forget removes. If it did, there would be two implementations of the
specification in this repository and the second one would be the one with the bugs.

**What is persisted.** The reference already produces a canonical snapshot for I1.5, so
that is what is stored — split up, not as one blob. One item per record under
``record/<id>``, and four metadata items for the counter, the scopes, the grants and the
forgotten ids. A single blob would mean rewriting every record on every write, and would
make "the store holds records" a sentence about a string. Revision logs travel inside
their record because that is where the canonical snapshot puts them; see the build report.

**Write-through, not transactional.** The in-memory system is changed first and the
backend second, so a backend that fails mid-persist leaves this object ahead of its store.
That is the honest shape for a wrapper that does not own the storage and cannot roll it
back. A store that needs atomicity should implement ``put`` against a transaction.

**Reopening** rebuilds from the items through ``ReferenceSystem.load`` — the snapshot
reader that already exists and already rejects a cyclic or dangling graph (P1.7, I1.4).
A reopen is therefore the same code path as a cold open from a file, which is the only
way the two can be guaranteed to agree.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from amr.protocol import (
    Capabilities,
    Chain,
    ForgetMode,
    ForgetReceipt,
    GrantReceipt,
    MemoryId,
    MemorySystem,
    Origin,
    ReadResult,
    RevisionReceipt,
    Scope,
)
from systems.persistent.backend import Backend, Item, MemoryBackend
from systems.reference import ReferenceSystem

VERSION = "0.1.0"
RECORD_PREFIX = "record/"
ENVELOPE = "meta/envelope"
COUNTER = "meta/counter"
SCOPES = "meta/scopes"
GRANTS = "meta/grants"
FORGOTTEN = "meta/forgotten"

NOTES = (
    (
        "The reference system unchanged, with every mutating call written through to a "
        "store. Confidence, visibility and forget semantics are the reference's."
    ),
    (
        "One stored item per record, plus four metadata items. A reopen rebuilds through "
        "the snapshot reader, so a reopen and a cold open from the store are one path."
    ),
    (
        "Write-through rather than transactional: the in-memory system is updated first, "
        "so a backend that fails mid-persist leaves this object ahead of its store."
    ),
)


def as_items(snapshot: Mapping[str, object]) -> dict[str, Item]:
    """A canonical snapshot as the items that hold it."""
    store = dict(snapshot["store"])  # type: ignore[arg-type]
    items: dict[str, Item] = {
        ENVELOPE: {
            "format": snapshot["format"],
            "default_forget_mode": snapshot["default_forget_mode"],
            "store_format": store["format"],
        },
        COUNTER: {"counter": store["counter"]},
        SCOPES: {"scopes": store["scopes"]},
        GRANTS: {"grants": store["grants"]},
        FORGOTTEN: {"forgotten": store["forgotten"]},
    }
    for record in store["records"]:  # type: ignore[union-attr]
        items[f"{RECORD_PREFIX}{record['id']}"] = dict(record)
    return items


def as_snapshot(items: Mapping[str, Item], system: str) -> dict[str, object]:
    """The items back as a snapshot ``ReferenceSystem.load`` accepts."""
    envelope = items[ENVELOPE]
    return {
        "format": envelope["format"],
        "system": system,
        "version": VERSION,
        "default_forget_mode": envelope["default_forget_mode"],
        "store": {
            "format": envelope["store_format"],
            "counter": items[COUNTER]["counter"],
            "scopes": items[SCOPES]["scopes"],
            "grants": items[GRANTS]["grants"],
            "forgotten": items[FORGOTTEN]["forgotten"],
            # Order is immaterial to the reader, which installs each record and then
            # validates the whole graph. Sorted anyway, so two opens of one store cannot
            # produce two snapshots.
            "records": [
                value
                for key, value in sorted(items.items())
                if key.startswith(RECORD_PREFIX)
            ],
        },
    }


class WriteThrough:
    """A ``MemorySystem`` that is a ``ReferenceSystem`` plus a backend."""

    def __init__(
        self,
        backend: Backend | None = None,
        default_forget_mode: ForgetMode | None = None,
        name: str = "write-through",
    ) -> None:
        self._backend = backend if backend is not None else MemoryBackend()
        self._name = name
        self._items = dict(self._backend.items())
        if self._items:
            snapshot = as_snapshot(self._items, name)
            if default_forget_mode is not None:
                # A caller that named a mode gets it; the stored one was the last
                # caller's. Set in the snapshot rather than after the fact, so the
                # reference's own constructor is still the only thing that reads it.
                snapshot["default_forget_mode"] = ForgetMode(default_forget_mode).value
            self._inner: ReferenceSystem = ReferenceSystem().load(snapshot)
        else:
            self._inner = ReferenceSystem(
                default_forget_mode=(
                    ForgetMode.TOMBSTONE
                    if default_forget_mode is None
                    else ForgetMode(default_forget_mode)
                )
            )
        self._persist()

    # ----------------------------------------------------------------- the store

    def _persist(self) -> None:
        """Write what changed, delete what is gone, and remember what is stored.

        Diffed against the last known state rather than rewritten wholesale, because
        "one item per record" is only worth anything if a write touches one record.
        """
        items = as_items(self._inner.to_dict())
        for key, value in items.items():
            if self._items.get(key) != value:
                self._backend.put(key, value)
        for key in self._items.keys() - items.keys():
            self._backend.delete(key)
        self._items = items

    # ---------------------------------------------------------------- capabilities

    def capabilities(self) -> Capabilities:
        """Every field of SPEC.md 8, named here rather than inherited.

        The values that describe the engine come from the engine, because repeating them
        would let the two drift apart silently. ``durability`` is the backend's, because
        that is the one promise this class changes.
        """
        inner = self._inner.capabilities()
        return Capabilities(
            system=self._name,
            version=VERSION,
            supported_forget_modes=inner.supported_forget_modes,
            default_forget_mode=inner.default_forget_mode,
            empty_chain_convention=inner.empty_chain_convention,
            revision=inner.revision,
            revision_raise_supported=inner.revision_raise_supported,
            scopes=inner.scopes,
            cross_scope_derivation=inner.cross_scope_derivation,
            durability=self._backend.durability,
            notes=NOTES + inner.notes,
        )

    # --------------------------------------------------------------- what mutates

    def write(
        self,
        content: object,
        declared_confidence: float,
        sources: Iterable[MemoryId] = (),
        scope: Scope = "default",
        origin: Origin | None = None,
    ) -> MemoryId:
        written = self._inner.write(content, declared_confidence, sources, scope, origin)
        self._persist()
        return written

    def revise(
        self,
        memory_id: MemoryId,
        new_declared: float,
        reason: str,
        scope: Scope = "default",
    ) -> RevisionReceipt:
        receipt = self._inner.revise(memory_id, new_declared, reason, scope)
        self._persist()
        return receipt

    def forget(
        self,
        memory_id: MemoryId,
        scope: Scope = "default",
        mode: ForgetMode | None = None,
    ) -> ForgetReceipt:
        receipt = self._inner.forget(memory_id, scope, mode)
        self._persist()
        return receipt

    def grant(self, owner: Scope, reader: Scope) -> GrantReceipt:
        receipt = self._inner.grant(owner, reader)
        self._persist()
        return receipt

    def revoke(self, owner: Scope, reader: Scope) -> GrantReceipt:
        receipt = self._inner.revoke(owner, reader)
        self._persist()
        return receipt

    # ------------------------------------------------------------------ what reads

    def get(self, memory_id: MemoryId, scope: Scope = "default") -> ReadResult:
        return self._inner.get(memory_id, scope)

    def provenance(self, memory_id: MemoryId, scope: Scope = "default") -> Chain:
        return self._inner.provenance(memory_id, scope)

    def effective_confidence(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> float:
        return self._inner.effective_confidence(memory_id, scope)

    def descendants(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> frozenset[MemoryId]:
        return self._inner.descendants(memory_id, scope)

    def revisions(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> tuple[RevisionReceipt, ...]:
        return self._inner.revisions(memory_id, scope)

    def list_scope(self, scope: Scope = "default") -> frozenset[MemoryId]:
        return self._inner.list_scope(scope)

    def grants(self, owner: Scope) -> frozenset[Scope]:
        return self._inner.grants(owner)

    # ------------------------------------------------------------------ Reopenable

    def to_dict(self) -> dict[str, object]:
        """The reference's snapshot, saying which system produced it."""
        return {**self._inner.to_dict(), "system": self._name, "version": VERSION}

    def load(self, snapshot: Mapping[str, object]) -> MemorySystem:
        """Validate a snapshot and return a system holding it — not this store.

        A foreign snapshot is something to check, not something to adopt: writing it
        through would overwrite live records with a graph that arrived from outside. So
        the copy is detached, over a backend that holds it in memory, and it declares the
        ``round-trip`` durability that is true of where it actually lives.
        """
        backend = MemoryBackend()
        for key, value in as_items(snapshot).items():
            backend.put(key, value)
        return WriteThrough(backend, name=self._name)

    def reopen(self) -> MemorySystem:
        """Rebuild from the backend, as a new process opening the same store would.

        Not a serialise-and-parse of this object's state: that would test the snapshot
        and leave the store untested. This reads the items back and runs them through
        ``ReferenceSystem.load``, which is the same path a cold open takes.
        """
        return WriteThrough(self._backend, name=self._name)
