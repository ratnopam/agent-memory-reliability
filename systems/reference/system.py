"""``ReferenceSystem`` -- the façade that implements ``MemorySystem``.

It decides nothing on its own. Visibility questions go to ``scope``, arithmetic to
``confidence``, deletion to ``forget``, and state to ``store``. What lives here is the
translation between the specified operation set and those four modules, plus the
capability declaration that makes divergence reportable.

The configured forget mode is a constructor argument, so a run of the suite is
``(system, forget_mode)`` and the divergence in P2.5 is produced by one flag.
"""

from __future__ import annotations

import json
from typing import Iterable

from harness.extensions import GrantReceipt
from harness.protocol import (
    Capabilities,
    Chain,
    ChainNode,
    ConfidenceDelta,
    ForgetMode,
    ForgetReceipt,
    ForgottenRecordError,
    MemoryId,
    Origin,
    ReadOutcome,
    ReadResult,
    Record,
    RevisionReceipt,
    Scope,
    ScopeError,
    UnresolvedSourceError,
)
from systems.reference.confidence import ConfidenceIndex
from systems.reference.forget import apply_forget
from systems.reference.scope import chain_node, native_live_ids, owned, readable
from systems.reference.store import Revision, Store

EMPTY_CHAIN = 1.0
SYSTEM_NAME = "reference"
SYSTEM_VERSION = "0.1.0"
SNAPSHOT_FORMAT = "1"


class ReferenceSystem:
    def __init__(
        self,
        default_forget_mode: ForgetMode = ForgetMode.TOMBSTONE,
        store: Store | None = None,
    ) -> None:
        self._store = store if store is not None else Store()
        self._confidence = ConfidenceIndex(self._store, EMPTY_CHAIN)
        self._default_mode = ForgetMode(default_forget_mode)

    # ------------------------------------------------------------ declaration

    def capabilities(self) -> Capabilities:
        return Capabilities(
            system=SYSTEM_NAME,
            version=SYSTEM_VERSION,
            supported_forget_modes=frozenset(
                {ForgetMode.TOMBSTONE, ForgetMode.CASCADE, ForgetMode.ERASE}
            ),
            default_forget_mode=self._default_mode,
            empty_chain_convention=EMPTY_CHAIN,
            revision="logged",
            revision_raise_supported=True,
            scopes="native",
            cross_scope_derivation="opaque-ancestor",
            durability="round-trip",
            notes=(
                "A foreign ancestor is opaque in a provenance walk whether or not a "
                "grant exists; the grant governs get, not the walk.",
                "A write may only cite sources the writing scope can read.",
                "revise and forget require ownership of the record, not a read grant.",
            ),
        )

    # ---------------------------------------------------------------- writes

    def write(
        self,
        content: object,
        declared_confidence: float,
        sources: Iterable[MemoryId] = (),
        scope: Scope = "default",
        origin: Origin | None = None,
    ) -> MemoryId:
        source_ids = frozenset(sources)
        for source_id in sorted(source_ids):
            if (
                self._store.record(source_id) is not None
                and readable(self._store, source_id, scope) is None
            ):
                # A scope may only cite sources it can read; otherwise provenance
                # becomes a side channel and one scope can pin another scope's record
                # in place. An unreadable source is reported as unresolvable, not as a
                # permission error, so that a write cannot be used as an existence
                # oracle across the boundary either.
                raise UnresolvedSourceError(
                    f"source {source_id!r} does not resolve in scope {scope!r}"
                )
        record = self._store.add(
            content=content,
            declared_confidence=declared_confidence,
            sources=source_ids,
            scope=scope,
            origin=origin,
        )
        return record.id

    def revise(
        self,
        memory_id: MemoryId,
        new_declared: float,
        reason: str,
        scope: Scope = "default",
    ) -> RevisionReceipt:
        record = owned(self._store, memory_id, scope)
        if record is None:
            if self._store.known(memory_id):
                raise ScopeError(f"{memory_id!r} is not native to scope {scope!r}")
            raise LookupError(f"{memory_id!r} does not resolve")
        if record.tombstoned or self._store.is_forgotten(memory_id):
            raise ForgottenRecordError(f"{memory_id!r} has been forgotten")
        if not 0.0 <= float(new_declared) <= 1.0:
            raise ValueError(
                f"declared_confidence must be in [0.0, 1.0], got {new_declared}"
            )

        descendants = self._store.descendants(memory_id)
        before_values = {d: self._confidence.effective(d) for d in descendants}
        before = record.declared_confidence
        self._store.set_declared(memory_id, float(new_declared))
        self._confidence.invalidate([memory_id, *descendants])

        deltas = tuple(
            ConfidenceDelta(
                id=descendant,
                before=before_values[descendant],
                after=self._confidence.effective(descendant),
            )
            for descendant in sorted(descendants)
        )
        revision = Revision(before=before, after=float(new_declared), reason=reason)
        self._store.append_revision(memory_id, revision)
        return RevisionReceipt(
            id=memory_id,
            before=before,
            after=float(new_declared),
            reason=reason,
            deltas=deltas,
        )

    def forget(
        self,
        memory_id: MemoryId,
        scope: Scope = "default",
        mode: ForgetMode | None = None,
    ) -> ForgetReceipt:
        chosen = self._default_mode if mode is None else ForgetMode(mode)
        if chosen not in self.capabilities().supported_forget_modes:
            raise ValueError(f"unsupported forget mode {chosen!r}")
        return apply_forget(self._store, self._confidence, memory_id, scope, chosen)

    # ----------------------------------------------------------------- reads

    def get(self, memory_id: MemoryId, scope: Scope = "default") -> ReadResult:
        record = readable(self._store, memory_id, scope)
        if record is not None:
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
        if self._forgotten_visible(memory_id, scope):
            return ReadResult(outcome=ReadOutcome.FORGOTTEN)
        return ReadResult(outcome=ReadOutcome.NOT_FOUND)

    def provenance(self, memory_id: MemoryId, scope: Scope = "default") -> Chain:
        self._require_walkable(memory_id, scope)
        nodes: dict[MemoryId, ChainNode] = {}
        for ancestor_id in sorted(self._store.ancestors([memory_id])):
            nodes[ancestor_id] = chain_node(self._store.require(ancestor_id), scope)
        return Chain(root_id=memory_id, nodes=nodes)

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
            if readable(self._store, descendant, scope) is not None
        )

    def revisions(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> tuple[RevisionReceipt, ...]:
        record = readable(self._store, memory_id, scope)
        if record is None:
            if self._forgotten_visible(memory_id, scope):
                raise ForgottenRecordError(f"{memory_id!r} has been forgotten")
            raise LookupError(f"{memory_id!r} does not resolve")
        return tuple(
            RevisionReceipt(
                id=memory_id,
                before=revision.before,
                after=revision.after,
                reason=revision.reason,
            )
            for revision in record.revisions
        )

    def list_scope(self, scope: Scope = "default") -> frozenset[MemoryId]:
        return native_live_ids(self._store, scope)

    # ------------------------------------------------------------ ScopeSharing

    def grant(self, owner: Scope, reader: Scope) -> GrantReceipt:
        if owner == reader:
            raise ValueError("a scope does not need a grant to read itself")
        self._store.add_grant(owner, reader)
        return GrantReceipt(owner=owner, reader=reader, granted=True)

    def revoke(self, owner: Scope, reader: Scope) -> GrantReceipt:
        self._store.drop_grant(owner, reader)
        return GrantReceipt(owner=owner, reader=reader, granted=False)

    def grants(self) -> frozenset[tuple[Scope, Scope]]:
        return self._store.grants()

    # -------------------------------------------------------------- Reopenable

    def to_dict(self) -> dict[str, object]:
        return {
            "format": SNAPSHOT_FORMAT,
            "system": SYSTEM_NAME,
            "version": SYSTEM_VERSION,
            "default_forget_mode": self._default_mode.value,
            "store": self._store.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ReferenceSystem:
        if payload.get("format") != SNAPSHOT_FORMAT:
            raise ValueError(f"unsupported snapshot format {payload.get('format')!r}")
        return cls(
            default_forget_mode=ForgetMode(payload["default_forget_mode"]),
            store=Store.from_dict(payload["store"]),  # type: ignore[arg-type]
        )

    def reopen(self) -> ReferenceSystem:
        """Serialise through JSON and back. See I1.5.

        JSON rather than a direct ``from_dict(self.to_dict())`` because the round trip
        is supposed to prove the snapshot could have been written to a file.
        """
        return type(self).from_dict(json.loads(json.dumps(self.to_dict())))

    # ------------------------------------------------------------------ helpers

    def _forgotten_visible(self, memory_id: MemoryId, scope: Scope) -> bool:
        state = self._store.forget_state(memory_id)
        if state is None:
            return False
        _, owner = state
        return owner == scope or (owner, scope) in self._store.grants()

    def _require_walkable(self, memory_id: MemoryId, scope: Scope) -> None:
        """A walk needs a chain position, which a tombstone still has.

        A record removed by ``cascade`` or ``erase`` has none, so walking it raises
        rather than returning an empty chain: an empty chain would read as "no
        ancestors", which is a different and more dangerous claim.
        """
        if readable(self._store, memory_id, scope) is not None:
            return
        if self._forgotten_visible(memory_id, scope):
            raise ForgottenRecordError(f"{memory_id!r} has been forgotten")
        raise LookupError(f"{memory_id!r} does not resolve")
