"""The three forget modes and their receipts. See SPEC.md 6.

The universal post-conditions (SPEC.md 6.2) are what the modes have in common. What they
disagree about is the fate of the descendants, and that disagreement is the whole point of
the suite:

* ``tombstone`` keeps the chain position, so the arithmetic is unchanged and I2.5 holds.
* ``cascade`` removes the descendants too, so there is nothing left to inflate and I2.5
  holds vacuously.
* ``erase`` detaches the edges and lets the descendants survive with shorter chains, so
  ``min`` runs over a smaller set and I2.5 is violated by construction. The deltas in the
  receipt are where the inflation becomes visible; see SPEC.md 6.4 and
  taxonomy/erasure-inflation.md.

Authorisation happens before either function here is called; see ``ReferenceSystem._resolve``.
"""

from __future__ import annotations

from amr.protocol import ForgetMode, ForgetReceipt, MemoryId, NotFoundError, Scope
from systems.reference.confidence import ConfidenceIndex
from systems.reference.store import Store, StoredRecord


def apply_forget(
    store: Store,
    confidence: ConfidenceIndex,
    record: StoredRecord,
    mode: ForgetMode,
) -> ForgetReceipt:
    memory_id = record.id
    descendants = store.descendants(memory_id)
    was = confidence.snapshot(descendants)
    scope_of: dict[MemoryId, Scope] = {memory_id: record.scope}
    scope_of.update({d: store.require(d).scope for d in descendants})

    if mode is ForgetMode.TOMBSTONE:
        store.tombstone(memory_id)
        forgotten = tombstoned = frozenset({memory_id})
        survivors = descendants
    elif mode is ForgetMode.CASCADE:
        store.remove(memory_id, mode)
        for descendant in sorted(descendants):
            store.remove(descendant, mode)
        forgotten = frozenset({memory_id}) | descendants
        tombstoned = survivors = frozenset()
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
    named = sorted(forgotten | survivors)
    return ForgetReceipt(
        mode=mode,
        forgotten=forgotten,
        tombstoned=tombstoned,
        deltas=confidence.deltas(was, survivors),
        affected_scopes=tuple((name, scope_of[name]) for name in named),
    )


def already_forgotten(state: tuple[ForgetMode, Scope] | None) -> ForgetReceipt:
    """A second forget succeeds and changes nothing (I3.3).

    The receipt reports the mode originally applied and names nothing, because this call
    affected nothing. Reporting the original mode is the load-bearing half: were a repeat
    call to adopt the mode it was handed, ``forget(x, tombstone)`` then
    ``forget(x, cascade)`` would destroy descendants the first call spared.
    """
    if state is None:  # pragma: no cover - the caller resolves the id first
        raise NotFoundError("record does not resolve")
    return ForgetReceipt(mode=state[0], forgotten=frozenset())
