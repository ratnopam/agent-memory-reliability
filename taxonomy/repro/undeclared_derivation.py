"""Undeclared derivation: a conclusion that never cites what it was based on."""

from __future__ import annotations

from amr.protocol import MemorySystem


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
