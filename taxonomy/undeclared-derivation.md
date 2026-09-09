# Undeclared derivation

**Status:** `out-of-scope`
**Caught by:** nothing. No check in this specification can catch it, and none should
claim to.

An agent retrieves a memory, reads it, reasons from it, and writes its conclusion without
citing it. The store receives a root: no sources, declared confidence 0.95, chain empty,
effective confidence 0.95. Every invariant in the specification holds. The provenance walk
is complete, acyclic, and referentially sound. The weakest-link arithmetic is correct over
the graph it was given. The graph is simply not the truth, because the derivation happened
in a model's context window and was never declared at the operation boundary.

This layer makes declared provenance *enforceable*, not *truthful*. It can guarantee that
a citation, once made, is walkable, that it bounds confidence, that it survives restarts,
and that deleting it has a defined consequence. It cannot guarantee that a writer cited
what it actually used, because nothing observable at the write boundary distinguishes a
dishonest root from an honest one — they are the same record. Detecting the omission would
require access to the agent's reasoning, which means a model in the measurement path, which
means the suite stops being deterministic and its results stop being falsifiable. That is a
worse trade than the gap.

Mitigation belongs above this layer: retrieval-time instrumentation that records which
memories were actually returned to an agent, and a writer that cites what it was given.
Such an instrument would produce candidate sources, and those candidates would be written
as ordinary citations, at which point everything in this specification applies to them.
Until then, an uncited conclusion is indistinguishable from an original observation, and the
honest thing to do is say so rather than emit a check that appears to cover it.

## Reproduction

Embedded verbatim from `taxonomy/repro/undeclared_derivation.py`:

```python
"""Undeclared derivation: a conclusion that never cites what it was based on."""

from __future__ import annotations

from harness.protocol import MemorySystem


def reproduce(system: MemorySystem) -> dict[str, object]:
    evidence = system.write("a weak observation the agent read", 0.2)

    # The agent read ``evidence`` and wrote its conclusion without citing it.
    undeclared = system.write("a confident conclusion", 0.95)
    # An honest agent writes the same conclusion with the citation.
    declared = system.write("a confident conclusion", 0.95, sources=[evidence])

    honest_root = system.write("something genuinely unrelated", 0.95)

    return {
        "undeclared_effective": system.effective_confidence(undeclared),
        "declared_effective": system.effective_confidence(declared),
        "undeclared_ancestors": sorted(system.provenance(undeclared).ancestor_ids()),
        # Nothing observable at this boundary separates the dishonest write from an
        # honest root: same empty chain, same number, same everything.
        "indistinguishable_from_honest_root": (
            system.effective_confidence(undeclared)
            == system.effective_confidence(honest_root)
            and system.provenance(undeclared).ancestor_ids()
            == system.provenance(honest_root).ancestor_ids()
        ),
    }
```

The reproduction writes the same conclusion twice — once uncited, once citing the weak
evidence it was actually based on — and shows the uncited version reading 0.95 against the
honest version's 0.2, while being observationally identical to a genuine root.

## Notes

This is the limitation that the README states first, and it is the reason the project is
positioned as a reliability layer rather than a truth layer.
