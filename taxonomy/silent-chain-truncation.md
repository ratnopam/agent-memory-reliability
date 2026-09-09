# Silent chain truncation

**Status:** `handled` by strict writes
**Caught by:** P1.6

Erasure inflation needs a deletion. This one does not. Any mechanism that shortens a chain
produces the identical inflated number: a write that cites an identifier which no longer
resolves, a summarising step that drops the sources of the records it summarises, a store
that was reset while identifiers from the old one were still in flight. If the
implementation accepts such a write and quietly skips the ancestor it cannot resolve, the
resulting record has a chain that *looks* complete — it has a `sources` list, it walks
cleanly, it returns a number — and is not. `min` was taken over a smaller set, so the
number is too high, and nothing anywhere records that an ancestor went missing.

A typo is enough to trigger it. That is why SPEC.md I1.6 takes the strictest available
position: a write whose `sources` contain an unresolvable identifier is rejected, and
nothing is persisted. Failing at write time puts the error where a caller can still be
blamed for it and fixed; failing silently at read time produces a confident number with a
truncated chain behind it, which is the worst outcome available. The cost is ordering:
parents must be written before children, and callers that batch writes have to sort them.
That cost is real and it is worth paying.

## Reproduction

Embedded verbatim from `taxonomy/repro/silent_chain_truncation.py`:

```python
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
```

The reproduction shows both halves: what a lenient implementation would have returned
(0.9, computed by `effective_confidence_reference` over the truncated graph) against what
the intact chain returns (0.4), and then that the write is rejected and nothing is
persisted.

## Notes

`min(∅) = 1.0` is what turns a missing ancestor into a *higher* number rather than a
missing value. Alternatives are SPEC.md open question 1.
