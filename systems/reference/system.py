"""``ReferenceSystem`` -- the façade that implements ``MemorySystem``.

It decides nothing on its own. State and visibility go to ``store``, arithmetic to
``confidence``, deletion to ``forget``. What lives here is the translation between the
specified operation set and those three modules, the capability declaration that makes
divergence reportable, and one resolver that fixes the order of the rejections in
SPEC.md 3.1.

The configured forget mode is a constructor argument, so a run of the suite is
``(system, forget_mode)`` and the divergence in P2.5 is produced by one flag.
"""

from __future__ import annotations

import json
from typing import Iterable, Mapping

from amr.protocol import (
    Capabilities,
    Chain,
    ForgetMode,
    ForgetReceipt,
    ForgottenRecordError,
    GrantReceipt,
    MemoryId,
    Origin,
    ReadOutcome,
    ReadResult,
    Record,
    RevisionReceipt,
    Scope,
    ScopeError,
)
from systems.reference.confidence import ConfidenceIndex
from systems.reference.forget import already_forgotten, apply_forget
from systems.reference.store import Revision, Store, StoredRecord

EMPTY_CHAIN = 1.0
SYSTEM_NAME = "reference"
SYSTEM_VERSION = "0.1.0"
SNAPSHOT_FORMAT = "1"

MODES = frozenset({ForgetMode.TOMBSTONE, ForgetMode.CASCADE, ForgetMode.ERASE})

NOTES = (
    (
        "A foreign ancestor is opaque in a provenance walk whether or not a grant "
        "exists; the grant governs get, not the walk."
    ),
    (
        "A write may only cite sources the writing scope can read, and an unreadable "
        "source is rejected as unresolvable rather than as a permission error."
    ),
    (
        "revise and forget require ownership. A record the caller cannot see raises "
        "LookupError, exactly as an unassigned id would."
    ),
)


class ReferenceSystem:
    def __init__(
        self,
        default_forget_mode: ForgetMode = ForgetMode.TOMBSTONE,
        store: Store | None = None,
    ) -> None:
        self._store = store if store is not None else Store()
        self._confidence = ConfidenceIndex(self._store, EMPTY_CHAIN)
        self._default_mode = ForgetMode(default_forget_mode)

    def capabilities(self) -> Capabilities:
        return Capabilities(
            system=SYSTEM_NAME,
            version=SYSTEM_VERSION,
            supported_forget_modes=MODES,
            default_forget_mode=self._default_mode,
            empty_chain_convention=EMPTY_CHAIN,
            revision="logged",
            revision_raise_supported=True,
            scopes="native",
            cross_scope_derivation="opaque-ancestor",
            durability="round-trip",
            notes=NOTES,
        )

    # ------------------------------------------------------------------ writes

    def write(
        self,
        content: object,
        declared_confidence: float,
        sources: Iterable[MemoryId] = (),
        scope: Scope = "default",
        origin: Origin | None = None,
    ) -> MemoryId:
        return self._store.add(
            content, declared_confidence, sources, scope, origin
        ).id

    def revise(
        self,
        memory_id: MemoryId,
        new_declared: float,
        reason: str,
        scope: Scope = "default",
    ) -> RevisionReceipt:
        record = self._resolve(memory_id, scope, owner_only=True)
        if record is None or record.tombstoned:
            raise ForgottenRecordError(f"{memory_id!r} has been forgotten")
        if not 0.0 <= float(new_declared) <= 1.0:
            raise ValueError(
                f"declared_confidence must be in [0.0, 1.0], got {new_declared}"
            )
        after, before = float(new_declared), record.declared_confidence
        descendants = self._store.descendants(memory_id)
        was = self._confidence.snapshot(descendants)

        self._store.set_declared(memory_id, after)
        self._confidence.invalidate([memory_id, *descendants])
        self._store.append_revision(memory_id, Revision(before, after, reason))
        return RevisionReceipt(
            id=memory_id,
            before=before,
            after=after,
            reason=reason,
            deltas=self._confidence.deltas(was, descendants),
        )

    def forget(
        self,
        memory_id: MemoryId,
        scope: Scope = "default",
        mode: ForgetMode | None = None,
    ) -> ForgetReceipt:
        chosen = self._default_mode if mode is None else ForgetMode(mode)
        if chosen not in MODES:
            raise ValueError(f"unsupported forget mode {chosen!r}")
        record = self._resolve(memory_id, scope, owner_only=True)
        if record is None or record.tombstoned:
            return already_forgotten(self._store.forget_state(memory_id))
        return apply_forget(self._store, self._confidence, record, chosen)

    # ------------------------------------------------------------------- reads

    def get(self, memory_id: MemoryId, scope: Scope = "default") -> ReadResult:
        record = self._store.readable(memory_id, scope)
        if record is None:
            forgotten = self._store.visible_forgotten(memory_id, scope)
            return ReadResult(
                outcome=ReadOutcome.FORGOTTEN if forgotten else ReadOutcome.NOT_FOUND
            )
        if record.tombstoned:
            return ReadResult(outcome=ReadOutcome.FORGOTTEN)
        return ReadResult(
            outcome=ReadOutcome.OK,
            record=Record(
                id=record.id,
                content=record.content,
                declared_confidence=record.declared_confidence,
                sources=record.sources,
                scope=record.scope,
                origin=record.origin,
            ),
        )

    def provenance(self, memory_id: MemoryId, scope: Scope = "default") -> Chain:
        self._require_walkable(memory_id, scope)
        return Chain(
            root_id=memory_id,
            nodes={
                ancestor: self._store.require(ancestor).chain_node(scope)
                for ancestor in sorted(self._store.ancestors([memory_id]))
            },
        )

    def effective_confidence(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> float:
        self._require_walkable(memory_id, scope)
        return self._confidence.effective(memory_id)

    def descendants(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> frozenset[MemoryId]:
        self._require_walkable(memory_id, scope)
        return frozenset(
            descendant
            for descendant in self._store.descendants(memory_id)
            if self._store.readable(descendant, scope) is not None
        )

    def revisions(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> tuple[RevisionReceipt, ...]:
        record = self._resolve(memory_id, scope)
        if record is None:
            raise ForgottenRecordError(f"{memory_id!r} has been forgotten")
        return tuple(
            RevisionReceipt(memory_id, r.before, r.after, r.reason)
            for r in record.revisions
        )

    def list_scope(self, scope: Scope = "default") -> frozenset[MemoryId]:
        return self._store.native_live_ids(scope)

    # ------------------------------------------------------------------ grants

    def grant(self, owner: Scope, reader: Scope) -> GrantReceipt:
        if owner == reader:
            raise ValueError("a scope does not need a grant to read itself")
        self._store.add_grant(owner, reader)
        return GrantReceipt(owner=owner, reader=reader, granted=True)

    def revoke(self, owner: Scope, reader: Scope) -> GrantReceipt:
        self._store.drop_grant(owner, reader)
        return GrantReceipt(owner=owner, reader=reader, granted=False)

    def grants(self, owner: Scope) -> frozenset[Scope]:
        return self._store.readers_of(owner)

    # -------------------------------------------------------------- Reopenable

    def to_dict(self) -> dict[str, object]:
        return {
            "format": SNAPSHOT_FORMAT,
            "system": SYSTEM_NAME,
            "version": SYSTEM_VERSION,
            "default_forget_mode": self._default_mode.value,
            "store": self._store.to_dict(),
        }

    def load(self, snapshot: Mapping[str, object]) -> ReferenceSystem:
        """Build a system from any snapshot in ``to_dict`` form. See P1.7."""
        if snapshot.get("format") != SNAPSHOT_FORMAT:
            raise ValueError(f"unsupported snapshot format {snapshot.get('format')!r}")
        return type(self)(
            default_forget_mode=ForgetMode(snapshot["default_forget_mode"]),
            store=Store.from_dict(snapshot["store"]),  # type: ignore[arg-type]
        )

    def reopen(self) -> ReferenceSystem:
        """Serialise through JSON and back (I1.5).

        Through JSON rather than straight from ``to_dict``, because the round trip is
        supposed to prove the snapshot could have been written to a file.
        """
        return self.load(json.loads(json.dumps(self.to_dict())))

    # ----------------------------------------------------------------- helpers

    def _resolve(
        self, memory_id: MemoryId, scope: Scope, owner_only: bool = False
    ) -> StoredRecord | None:
        """The record if this caller may see it; ``None`` if it is gone and they may know.

        Rejections in the order SPEC.md 3.1 fixes. Absent first, as ``LookupError``, and
        that one answer covers both "no such id" and "another scope's id" — distinguishing
        them is an existence oracle. Then not-yours, as ``ScopeError``, reachable only
        once the caller can already read the record.

        "Forgotten" is returned rather than raised, because the callers disagree about
        what it means: ``revise`` fails, a walk answers for a tombstone and fails for a
        removed record, and ``forget`` is idempotent.
        """
        record = self._store.readable(memory_id, scope)
        if record is not None:
            owner = record.scope
        elif self._store.visible_forgotten(memory_id, scope):
            owner = self._store.forget_state(memory_id)[1]  # type: ignore[index]
        else:
            raise LookupError(f"{memory_id!r} does not resolve")
        if owner_only and owner != scope:
            raise ScopeError(f"{memory_id!r} is native to another scope")
        return record

    def _require_walkable(self, memory_id: MemoryId, scope: Scope) -> None:
        """A walk needs a chain position, which a tombstone still has.

        A record removed by ``cascade`` or ``erase`` has none, so walking it raises rather
        than returning an empty chain: an empty chain reads as "no ancestors", which is a
        different and more dangerous claim (SPEC.md 6.2).
        """
        if self._resolve(memory_id, scope) is None:
            raise ForgottenRecordError(f"{memory_id!r} has been forgotten")
