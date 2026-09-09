"""P4 -- isolation when agents share state. SPEC.md 7.

Agents in separate scopes cannot read each other's memories by default, cannot corrupt
each other's chains, and cannot use provenance as a side channel around the boundary.

Two conventions this suite adopts, both logged in design-notes/spec-feedback.md: a record
that is invisible is indistinguishable from a record that never existed, and a foreign
ancestor stays opaque in a walk whether or not a grant exists.
"""

from __future__ import annotations

import json
from typing import Callable

import pytest

from harness.extensions import ScopeSharing
from harness.protocol import (
    Capabilities,
    ForgetMode,
    MemorySystem,
    ReadOutcome,
    effective_confidence_reference,
)
from properties.interleavings import ALPHA, BETA, BY_KEY, PLAN, SCHEDULES, is_topological
from properties.support import (
    assert_acyclic,
    assert_referentially_complete,
    readable_graph,
    survives,
)


def _sharing(system: MemorySystem, capabilities: Capabilities) -> ScopeSharing:
    assert isinstance(system, ScopeSharing), (
        f"the system declares scopes={capabilities.scopes!r}, so I4.2 requires a "
        "recorded, revocable grant; no grant operation is exposed"
    )
    return system


@pytest.mark.check("P4.1")
def test_p4_1_write_in_a_absent_in_b(system: MemorySystem) -> None:
    """P4.1 | Write in A, list in B | Absent"""
    private = system.write("alpha's business", 0.9, scope=ALPHA)

    assert private in system.list_scope(ALPHA)
    assert private not in system.list_scope(BETA)
    assert system.get(private, BETA).outcome is ReadOutcome.NOT_FOUND
    with pytest.raises(LookupError):
        system.provenance(private, BETA)


@pytest.mark.check("P4.2")
def test_p4_2_grant_then_revoke(
    system: MemorySystem, capabilities: Capabilities
) -> None:
    """P4.2 | Grant, read, revoke, read | Visible then absent"""
    sharing = _sharing(system, capabilities)
    shared = system.write("shared with beta", 0.9, scope=ALPHA)
    assert system.get(shared, BETA).outcome is ReadOutcome.NOT_FOUND

    sharing.grant(ALPHA, BETA)
    granted = system.get(shared, BETA)

    assert (ALPHA, BETA) in sharing.grants()
    assert granted.outcome is ReadOutcome.OK
    assert granted.record is not None
    assert granted.record.content == "shared with beta"
    assert shared not in system.list_scope(BETA), (
        "a grant makes a record readable, not resident: list_scope is not a directory "
        "of another scope's contents"
    )

    sharing.revoke(ALPHA, BETA)

    assert (ALPHA, BETA) not in sharing.grants()
    assert system.get(shared, BETA).outcome is ReadOutcome.NOT_FOUND


@pytest.mark.check("P4.3")
def test_p4_3_opaque_ancestor(system: MemorySystem, capabilities: Capabilities) -> None:
    """P4.3 | Cross-scope derivation, walk from B | Ancestor id present, content withheld"""
    sharing = _sharing(system, capabilities)
    upstream = system.write("alpha's weak evidence", 0.3, scope=ALPHA)
    sharing.grant(ALPHA, BETA)
    derived = system.write(
        "beta's conclusion", 0.9, sources=[upstream], scope=BETA
    )
    sharing.revoke(ALPHA, BETA)

    chain = system.provenance(derived, BETA)
    node = chain.nodes[upstream]

    assert node.opaque is True, "a foreign ancestor is marked, not silently inlined"
    assert node.declared_confidence == 0.3, "the confidence contribution is present"
    assert_referentially_complete(chain)
    assert_acyclic(chain)
    assert system.effective_confidence(derived, BETA) == 0.3, (
        "the walk still bounds the derivative"
    )
    assert system.get(upstream, BETA).outcome is ReadOutcome.NOT_FOUND, (
        "provenance is not a side channel around the boundary"
    )


@pytest.mark.check("P4.4")
def test_p4_4_cross_scope_forget(
    system: MemorySystem, capabilities: Capabilities, mode: ForgetMode
) -> None:
    """P4.4 | Forget in A with descendants in B | Declared mode applied across the boundary"""
    sharing = _sharing(system, capabilities)
    upstream = system.write("alpha's evidence", 0.3, scope=ALPHA)
    sharing.grant(ALPHA, BETA)
    derived = system.write("beta's conclusion", 0.9, sources=[upstream], scope=BETA)

    receipt = system.forget(upstream, scope=ALPHA)

    assert receipt.mode is mode
    scopes = dict(receipt.affected_scopes)
    assert scopes[upstream] == ALPHA
    assert derived in scopes and scopes[derived] == BETA, (
        "one receipt, all affected ids, scope noted per id"
    )
    assert system.get(upstream, ALPHA).outcome is ReadOutcome.FORGOTTEN

    if mode is ForgetMode.TOMBSTONE:
        assert survives(system, derived, BETA)
        assert system.effective_confidence(derived, BETA) == 0.3
    elif mode is ForgetMode.CASCADE:
        assert system.get(derived, BETA).outcome is ReadOutcome.FORGOTTEN, (
            "isolation is not an excuse to leave a derivative untouched"
        )
        assert derived in receipt.forgotten
    else:
        assert survives(system, derived, BETA)
        assert system.provenance(derived, BETA).ancestor_ids() == frozenset()


@pytest.mark.check("P4.5")
def test_p4_5_interleaved_writes(
    make_system: Callable[[], MemorySystem], capabilities: Capabilities
) -> None:
    """P4.5 | Concurrent interleaved writes | DAG intact, no lost edges"""
    canonical: dict[str, str] = {}
    for schedule in SCHEDULES:
        assert is_topological(schedule), f"{schedule} is not a valid write order"
        system = make_system()
        sharing = _sharing(system, capabilities)
        sharing.grant(ALPHA, BETA)

        ids: dict[str, str] = {}
        for key in schedule:
            step = BY_KEY[key]
            ids[key] = system.write(
                content=f"content-{key}",
                declared_confidence=step.declared,
                sources=[ids[source] for source in step.sources],
                scope=step.scope,
            )

        by_id = {memory_id: key for key, memory_id in ids.items()}
        shape: dict[str, object] = {}
        for step in PLAN:
            memory_id = ids[step.key]
            chain = system.provenance(memory_id, step.scope)
            assert_referentially_complete(chain)
            assert_acyclic(chain)
            declared, sources = readable_graph(system, [memory_id], step.scope)
            effective = system.effective_confidence(memory_id, step.scope)
            assert effective == effective_confidence_reference(
                declared, sources, memory_id, capabilities.empty_chain_convention
            )
            shape[step.key] = {
                "declared": step.declared,
                "sources": sorted(
                    by_id[source] for source in chain.nodes[memory_id].sources
                ),
                "effective": effective,
                "ancestors": sorted(by_id[a] for a in chain.ancestor_ids()),
            }
        canonical[",".join(schedule)] = json.dumps(shape, sort_keys=True)

    distinct = set(canonical.values())
    assert len(distinct) == 1, (
        "interleaving changed the graph: "
        + json.dumps(canonical, sort_keys=True, indent=2)
    )
    resolved = json.loads(distinct.pop())
    for step in PLAN:
        assert resolved[step.key]["sources"] == sorted(step.sources), "lost edge"
