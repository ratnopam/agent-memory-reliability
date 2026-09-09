# Erasure inflation

**Status:** `open`
**Caught by:** P2.5 under `erase`, reported as DIVERGENCE

Effective confidence is a weakest-link minimum: `effective = min(declared, chain.min)`,
and `min` over an empty chain returns 1.0 because a record with no ancestors is bounded
only by its own claim. That convention is correct for roots and load-bearing for
everything else. It also means that if a forget operation truly removes an ancestor, the
surviving derivative's chain gets shorter, `min` runs over a smaller set, and the
derivative becomes **more** confident than it was while its evidence was still there. A
conclusion resting on a 0.4 observation reads 0.4; erase the observation and the same
conclusion reads 0.9, its own declared value, with nothing left to contradict it.

Forgetting the evidence strengthens the conclusion. Nothing is corrupted, no invariant of
the store is broken, and no error is raised — the arithmetic is simply operating over a
graph that has lost a node. This is why the mode matters more than the number: under
`tombstone` the chain position survives and the value does not move, under `cascade` the
derivative does not survive to be inflated, and under `erase` the inflation is guaranteed
by construction. SPEC.md 6.4 leaves the tension unresolved because each of the three
obvious fixes costs something real, so the suite reports the divergence instead of scoring
it. The receipt makes it visible: every surviving descendant whose effective confidence
moved gets a `ConfidenceDelta`, and `delta.inflated` is true for exactly the records that
gained confidence from a deletion.

## Reproduction

Embedded verbatim from `taxonomy/repro/erasure_inflation.py`:

```python
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
```

Result: `before` is 0.4, `after` is 0.9, `inflated` is true, the chain is empty, and the
receipt reports the inflation it caused.

## Notes

The same number is reachable without deleting anything; see
[silent-chain-truncation](silent-chain-truncation.md). Erasure is the most visible way to
shorten a chain, not the only one.
