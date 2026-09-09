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

from amr.protocol import (
    Capabilities,
    ForgetMode,
    MemorySystem,
    ReadOutcome,
    ScopeError,
    effective_confidence_reference,
)
from properties.interleavings import ALPHA, BETA, BY_KEY, PLAN, SCHEDULES, is_topological
from properties.support import (
    assert_acyclic,
    assert_referentially_complete,
    readable_graph,
    sharing_system,
    survives,
)


def _operations_on(system: MemorySystem, memory_id: str, scope: str) -> dict[str, object]:
    """Every id-taking operation, invoked; the raised type or the returned value.

    I4.1 makes an invisible record indistinguishable from a nonexistent one for *every*
    operation, so the check has to call every operation. A rejection that names the scope
    on any one of them is an existence oracle, and it does not matter which one.
    """
    calls = {
        "get": lambda: system.get(memory_id, scope).outcome,
        "provenance": lambda: system.provenance(memory_id, scope),
        "effective_confidence": lambda: system.effective_confidence(memory_id, scope),
        "descendants": lambda: system.descendants(memory_id, scope),
        "revisions": lambda: system.revisions(memory_id, scope),
        "revise": lambda: system.revise(memory_id, 0.1, "probe", scope),
        "forget": lambda: system.forget(memory_id, scope),
    }
    observed: dict[str, object] = {}
    for name, call in calls.items():
        try:
            observed[name] = call()
        except Exception as error:
            observed[name] = type(error)
    return observed


@pytest.mark.check("P4.1")
def test_p4_1_write_in_a_absent_in_b(system: MemorySystem) -> None:
    """P4.1 | Write in A, list in B | Absent"""
    private = system.write("alpha's business", 0.9, scope=ALPHA)

    assert private in system.list_scope(ALPHA)
    assert private not in system.list_scope(BETA)

    invisible = _operations_on(system, private, BETA)
    unassigned = _operations_on(system, "no-such-id", BETA)

    assert invisible["get"] is ReadOutcome.NOT_FOUND
    assert invisible == unassigned, (
        "a record this scope cannot see must behave exactly as an id that was never "
        f"assigned; it does not: {invisible} vs {unassigned}"
    )


@pytest.mark.check("P4.2")
def test_p4_2_grant_then_revoke(
    system: MemorySystem, capabilities: Capabilities
) -> None:
    """P4.2 | Grant, read, revoke, read | Visible then absent"""
    sharing = sharing_system(system, capabilities)
    shared = system.write("shared with beta", 0.9, scope=ALPHA)
    assert system.get(shared, BETA).outcome is ReadOutcome.NOT_FOUND

    sharing.grant(ALPHA, BETA)
    granted = system.get(shared, BETA)

    assert BETA in sharing.grants(ALPHA)
    assert granted.outcome is ReadOutcome.OK
    assert granted.record is not None
    assert granted.record.content == "shared with beta"
    assert shared not in system.list_scope(BETA), (
        "a grant makes a record readable, not resident: list_scope is not a directory "
        "of another scope's contents"
    )

    sharing.revoke(ALPHA, BETA)

    assert BETA not in sharing.grants(ALPHA)
    assert system.get(shared, BETA).outcome is ReadOutcome.NOT_FOUND


@pytest.mark.check("P4.3")
def test_p4_3_opaque_ancestor(system: MemorySystem, capabilities: Capabilities) -> None:
    """P4.3 | Cross-scope derivation, walk from B | Ancestor id present, content withheld"""
    sharing = sharing_system(system, capabilities)
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
    sharing = sharing_system(system, capabilities)
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
        sharing = sharing_system(system, capabilities)
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


@pytest.mark.check("P4.6")
def test_p4_6_grant_conveys_reading_only(
    system: MemorySystem, capabilities: Capabilities
) -> None:
    """P4.6 | Reader with a grant attempts revise and forget | ScopeError, nothing applied

    The one place SPEC.md 3.1 still allows a scope error, and the reason it has to: with
    no signal here, I4.2 would make ``grant`` a transfer of control rather than of read
    access. It leaks nothing, because the caller can already read the record.

    The negative half matters as much as the exception: a store that raised ``ScopeError``
    after applying the change would satisfy a check that only looked for the raise.
    """
    sharing = sharing_system(system, capabilities)
    shared = system.write("alpha's evidence", 0.9, scope=ALPHA)
    sharing.grant(ALPHA, BETA)
    assert system.get(shared, BETA).outcome is ReadOutcome.OK

    with pytest.raises(ScopeError):
        system.revise(shared, 0.1, "not beta's to revise", scope=BETA)
    with pytest.raises(ScopeError):
        system.forget(shared, scope=BETA)

    owner_view = system.get(shared, ALPHA)
    assert owner_view.outcome is ReadOutcome.OK, "nothing was applied"
    assert owner_view.record is not None
    assert owner_view.record.declared_confidence == 0.9, "the revise did not land"
    assert system.revisions(shared, ALPHA) == ()
