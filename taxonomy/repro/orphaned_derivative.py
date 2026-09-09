"""Orphaned derivative: a forget that leaves a derivative pointing at nothing."""

from __future__ import annotations

from harness.protocol import ForgetMode, MemorySystem, ReadOutcome


def _observe(system: MemorySystem, derived: str) -> dict[str, object]:
    read = system.get(derived)
    if read.outcome is not ReadOutcome.OK:
        return {"survives": False, "dangling": [], "ancestors": []}
    chain = system.provenance(derived)
    dangling = sorted(
        source_id
        for node in chain.nodes.values()
        for source_id in node.sources
        if source_id not in chain.nodes
    )
    return {
        "survives": True,
        "dangling": dangling,
        "ancestors": sorted(chain.ancestor_ids()),
    }


def reproduce(system: MemorySystem) -> dict[str, object]:
    outcomes: dict[str, object] = {}
    for mode in (ForgetMode.TOMBSTONE, ForgetMode.CASCADE, ForgetMode.ERASE):
        source = system.write(f"evidence for {mode.value}", 0.4)
        derived = system.write(f"conclusion for {mode.value}", 0.9, sources=[source])
        receipt = system.forget(source, mode=mode)
        observation = _observe(system, derived)
        observation["receipt_names_derivative"] = derived in receipt.forgotten or any(
            delta.id == derived for delta in receipt.deltas
        )
        outcomes[mode.value] = observation
    return outcomes
