"""Erasure inflation: forgetting the evidence strengthens the conclusion."""

from __future__ import annotations

from amr.protocol import ForgetMode, MemorySystem


def reproduce(system: MemorySystem) -> dict[str, object]:
    source = system.write("a weak observation", 0.4)
    derived = system.write("a confident conclusion", 0.9, sources=[source])

    before = system.effective_confidence(derived)
    receipt = system.forget(source, mode=ForgetMode.ERASE)
    after = system.effective_confidence(derived)

    return {
        "before": before,
        "after": after,
        "inflated": after > before,
        "chain_after": sorted(system.provenance(derived).ancestor_ids()),
        "receipt_reports_inflation": [
            (delta.id, delta.before, delta.after)
            for delta in receipt.deltas
            if delta.inflated
        ],
    }
