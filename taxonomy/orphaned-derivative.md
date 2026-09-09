# Orphaned derivative

**Status:** `handled` by defined forget modes
**Caught by:** P3.3, with the receipt checked by P3.5

The naive implementation of "forget this memory" deletes the row and stops. Everything
derived from it survives, still holding the deleted identifier in its `sources`. The
derivative is now an orphan: it claims a provenance that cannot be walked. A reader who
asks for its chain gets a dangling identifier, and an implementation that resolves such
identifiers leniently gets [silent chain truncation](silent-chain-truncation.md) on top —
the same inflated number, arrived at by a different route. Worse, the failure is invisible
until someone walks that particular chain, which may be long after the deletion, in a
different session, run by a different agent.

The specification rules this out by requiring that a forget operation have a *declared*
consequence for descendants (SPEC.md 6.1) and that it hand back a receipt naming every
affected identifier (I3.5). All three modes leave the derivative in a defined state:
`tombstone` keeps the ancestor's identifier, declared confidence, and edges, so the walk
still resolves and the arithmetic does not move; `cascade` removes the derivative too, so
there is no orphan left to read; `erase` detaches the edge, so the derivative survives with
a genuinely shorter chain rather than a broken one. What is not permitted is the fourth
option: leaving the edge pointing at a record that is gone. I1.4 makes a dangling
identifier a conformance failure outright.

## Reproduction

Embedded verbatim from `taxonomy/repro/orphaned_derivative.py`:

```python
"""Orphaned derivative: a forget that leaves a derivative pointing at nothing."""

from __future__ import annotations

from amr.protocol import ForgetMode, MemorySystem, ReadOutcome


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
```

The reproduction forgets one source per mode in a single store and reports, for each, whether
the derivative survived, whether any identifier in its chain fails to resolve, and whether
the receipt named the derivative. No mode produces a dangling identifier.

## Notes

`erase` leaves a *defined* derivative, not a correct one: its number is now inflated. The
two failure modes are independent, and a system can handle this one while diverging on the
other.
