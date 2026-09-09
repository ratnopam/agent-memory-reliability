"""The three forget modes and their receipts. See SPEC.md 6.

The universal post-conditions (SPEC.md 6.2) are what the modes have in common: the
target stops being readable, ``get`` says ``FORGOTTEN`` rather than ``NOT_FOUND`` for as
long as the store exists, a second call changes nothing, and the identifier is never
handed to a new record.

What the modes disagree about is the fate of the descendants, and that disagreement is
the whole point of the suite:

* ``tombstone`` keeps the chain position, so the arithmetic is unchanged and I2.5 holds.
* ``cascade`` removes the descendants too, so there is nothing left to inflate and I2.5
  holds vacuously.
* ``erase`` detaches the edges and lets the descendants survive with shorter chains, so
  ``min`` runs over a smaller set and I2.5 is violated by construction. The deltas in
  the receipt are where that inflation becomes visible; see SPEC.md 6.4 and
  taxonomy/erasure-inflation.md.
"""

from __future__ import annotations

from harness.protocol import (
    ConfidenceDelta,
    ForgetMode,
    ForgetReceipt,
    MemoryId,
    Scope,
    ScopeError,
)
from systems.reference.confidence import ConfidenceIndex
from systems.reference.scope import owned
from systems.reference.store import Store


def apply_forget(
    store: Store,
    confidence: ConfidenceIndex,
    memory_id: MemoryId,
    viewer: Scope,
    mode: ForgetMode,
) -> ForgetReceipt:
    state = store.forget_state(memory_id)
    if state is not None and store.record(memory_id) is None:
        return _idempotent(state, memory_id, viewer)

    record = owned(store, memory_id, viewer)
    if record is None:
        if store.known(memory_id):
            raise ScopeError(f"{memory_id!r} is not native to scope {viewer!r}")
        raise LookupError(f"{memory_id!r} does not resolve")
    if record.tombstoned:
        return _idempotent(store.forget_state(memory_id), memory_id, viewer)

    descendants = store.descendants(memory_id)
    before = {
        descendant: confidence.effective(descendant) for descendant in descendants
    }
    scope_of = {memory_id: record.scope}
    scope_of.update({d: store.require(d).scope for d in descendants})

    if mode is ForgetMode.TOMBSTONE:
        store.tombstone(memory_id)
        forgotten = frozenset({memory_id})
        tombstoned = frozenset({memory_id})
        survivors = descendants
    elif mode is ForgetMode.CASCADE:
        store.remove(memory_id, mode)
        for descendant in sorted(descendants):
            store.remove(descendant, mode)
        forgotten = frozenset({memory_id}) | descendants
        tombstoned = frozenset()
        survivors = frozenset()
    elif mode is ForgetMode.ERASE:
        for child in sorted(store.children(memory_id)):
            store.detach_source(child, memory_id)
        store.remove(memory_id, mode)
        forgotten = frozenset({memory_id})
        tombstoned = frozenset()
        survivors = descendants
    else:  # pragma: no cover - ForgetMode is closed
        raise ValueError(f"unsupported forget mode {mode!r}")

    confidence.invalidate([memory_id, *descendants])
    deltas = tuple(
        ConfidenceDelta(
            id=survivor,
            before=before[survivor],
            after=confidence.effective(survivor),
        )
        for survivor in sorted(survivors)
    )
    named = sorted(forgotten | survivors)
    return ForgetReceipt(
        mode=mode,
        forgotten=forgotten,
        tombstoned=tombstoned,
        deltas=deltas,
        affected_scopes=tuple((name, scope_of[name]) for name in named),
    )


def _idempotent(
    state: tuple[ForgetMode, Scope] | None, memory_id: MemoryId, viewer: Scope
) -> ForgetReceipt:
    """A second forget succeeds and changes nothing (I3.3).

    The receipt reports the mode that was originally applied and names nothing, because
    this call affected nothing. An empty ``forgotten`` set is the honest description of
    a call that did no work.
    """
    if state is None:  # pragma: no cover - callers check first
        raise LookupError(f"{memory_id!r} does not resolve")
    mode, owner = state
    if owner != viewer:
        raise ScopeError(f"{memory_id!r} is not native to scope {viewer!r}")
    return ForgetReceipt(mode=mode, forgotten=frozenset())
