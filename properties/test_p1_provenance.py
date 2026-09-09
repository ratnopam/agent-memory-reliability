"""P1 -- provenance walk across writes. SPEC.md 4.

Every write records what it was derived from, and that derivation is walkable from any
descendant back to its roots.
"""

from __future__ import annotations

import pytest

from harness.extensions import Reopenable
from harness.protocol import (
    CycleError,
    ForgetMode,
    ForgottenRecordError,
    MemorySystem,
    Origin,
    ReadOutcome,
    UnresolvedSourceError,
)
from properties.support import (
    assert_acyclic,
    assert_referentially_complete,
    canonical_chain,
)

UNKNOWN_ID = "no-such-id"


@pytest.mark.check("P1.1")
def test_p1_1_cycle_rejected(system: MemorySystem) -> None:
    """P1.1 | Write a cycle-forming record | Rejected"""
    root = system.write("root", 0.9)
    leaf = system.write("leaf", 0.9, sources=[root])

    # A record can only close a cycle by citing an identifier that does not exist yet:
    # its own, or one of its descendants'. Both are unresolvable at write time, so the
    # rejection arrives as a rejection whichever way the implementation classifies it.
    with pytest.raises((CycleError, UnresolvedSourceError)):
        system.write("cycle", 0.9, sources=[root, UNKNOWN_ID])

    # No operation adds an edge to an existing record, so a cycle cannot appear later
    # either: sources are immutable after a write (SPEC.md 3).
    system.revise(root, 0.5, "unrelated revision")
    read = system.get(root)
    assert read.outcome is ReadOutcome.OK
    assert read.record is not None
    assert read.record.sources == frozenset()

    chain = system.provenance(leaf)
    assert_acyclic(chain)
    assert_referentially_complete(chain)


@pytest.mark.check("P1.2")
def test_p1_2_three_hop_chain(system: MemorySystem) -> None:
    """P1.2 | Three-hop chain, walk from leaf | All three ancestors returned"""
    first = system.write("first", 0.9, origin=Origin(kind="document", ref="doc://1"))
    second = system.write("second", 0.9, sources=[first])
    third = system.write("third", 0.9, sources=[second])
    leaf = system.write("leaf", 0.9, sources=[third])

    chain = system.provenance(leaf)
    assert chain.ancestor_ids() == frozenset({first, second, third})
    assert_referentially_complete(chain)
    assert_acyclic(chain)


@pytest.mark.check("P1.3")
def test_p1_3_diamond_shared_ancestor_once(system: MemorySystem) -> None:
    """P1.3 | Diamond graph, walk from sink | Shared ancestor returned exactly once"""
    shared = system.write("shared", 0.6)
    left = system.write("left", 0.9, sources=[shared])
    right = system.write("right", 0.9, sources=[shared])
    sink = system.write("sink", 0.9, sources=[left, right])

    chain = system.provenance(sink)
    assert chain.ancestor_ids() == frozenset({shared, left, right})
    assert len(chain.nodes) == 4, "one entry per ancestor, not one per path"
    assert list(chain.nodes).count(shared) == 1
    assert_referentially_complete(chain)


@pytest.mark.check("P1.4")
def test_p1_4_walk_after_ancestor_forgotten(
    system: MemorySystem, mode: ForgetMode
) -> None:
    """P1.4 | Walk after an ancestor is forgotten | No dangling ids, per declared mode"""
    root = system.write("root", 0.4)
    middle = system.write("middle", 0.8, sources=[root])
    leaf = system.write("leaf", 0.9, sources=[middle])

    system.forget(middle)

    # Mode-independent: whatever remains walkable must resolve every id it names.
    for memory_id in (root, middle, leaf):
        try:
            chain = system.provenance(memory_id)
        except (ForgottenRecordError, LookupError):
            continue
        assert_referentially_complete(chain)
        assert_acyclic(chain)

    if mode is ForgetMode.TOMBSTONE:
        chain = system.provenance(leaf)
        assert chain.ancestor_ids() == frozenset({root, middle})
        assert chain.nodes[middle].tombstoned is True
        assert chain.nodes[middle].declared_confidence == 0.8
    elif mode is ForgetMode.CASCADE:
        with pytest.raises(ForgottenRecordError):
            system.provenance(leaf)
        assert system.provenance(root).ancestor_ids() == frozenset()
    else:
        chain = system.provenance(leaf)
        assert middle not in chain.nodes, "an erased ancestor is gone, not dangling"
        assert chain.ancestor_ids() == frozenset()


@pytest.mark.check("P1.5")
def test_p1_5_walk_after_store_reopen(system: MemorySystem) -> None:
    """P1.5 | Walk after store reopen | Byte-identical chain"""
    assert isinstance(system, Reopenable), (
        "I1.5 requires provenance to survive a restart; a system that cannot be "
        "reopened cannot demonstrate it"
    )
    shared = system.write("shared", 0.3)
    left = system.write("left", 0.7, sources=[shared])
    right = system.write("right", 0.8, sources=[shared])
    sink = system.write("sink", 0.9, sources=[left, right])
    system.revise(left, 0.6, "sharpened after review")

    before = canonical_chain(system.provenance(sink))
    reopened = system.reopen()
    after = canonical_chain(reopened.provenance(sink))

    assert after == before
    assert reopened.effective_confidence(sink) == system.effective_confidence(sink)
    assert reopened.revisions(left) == system.revisions(left)


@pytest.mark.check("P1.6")
def test_p1_6_unresolvable_source_rejected(system: MemorySystem) -> None:
    """P1.6 | Write citing an unresolvable source id | Rejected, nothing persisted"""
    root = system.write("root", 0.9)
    before = system.list_scope()

    with pytest.raises(UnresolvedSourceError):
        system.write("derived", 0.9, sources=[root, UNKNOWN_ID])

    assert system.list_scope() == before, "a rejected write persists nothing"
    assert system.get(UNKNOWN_ID).outcome is ReadOutcome.NOT_FOUND
    assert system.descendants(root) == frozenset()
