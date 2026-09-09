"""Silent chain truncation: the same inflated number, with no deletion involved."""

from __future__ import annotations

from amr.protocol import (
    MemorySystem,
    UnresolvedSourceError,
    effective_confidence_reference,
)

STALE_ID = "id-from-a-store-that-was-reset"


def reproduce(system: MemorySystem) -> dict[str, object]:
    weak = system.write("a weak observation", 0.4)

    # What a lenient implementation would have produced: the write is accepted and the
    # unresolvable ancestor is quietly dropped, so ``min`` runs over what is left.
    truncated = effective_confidence_reference(
        declared={"derived": 0.9},
        sources={"derived": [STALE_ID]},
        memory_id="derived",
    )
    intact = effective_confidence_reference(
        declared={"derived": 0.9, weak: 0.4},
        sources={"derived": [weak]},
        memory_id="derived",
    )

    rejected = False
    try:
        system.write("a confident conclusion", 0.9, sources=[weak, STALE_ID])
    except UnresolvedSourceError:
        rejected = True

    return {
        "rejected": rejected,
        "truncated_chain_value": truncated,
        "intact_chain_value": intact,
        "inflation_without_deletion": truncated > intact,
        "persisted": sorted(system.list_scope()) == [weak],
    }
