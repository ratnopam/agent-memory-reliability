"""P3 -- forget operations. SPEC.md 6.

A request to forget makes a memory unreadable and has a declared, observable effect on
everything derived from it. The universal post-conditions (SPEC.md 6.2) are asserted
without reference to the mode; only P3.3 looks at which mode is configured, because that
is the check whose required outcome is "per declared mode".
"""

from __future__ import annotations

import pytest

from amr.protocol import (
    ForgetMode,
    ForgottenRecordError,
    MemorySystem,
    ReadOutcome,
)
from amr.registry import Registration
from properties.support import observable_state, survives


@pytest.mark.check("P3.1")
def test_p3_1_forgotten_is_not_not_found(system: MemorySystem) -> None:
    """P3.1 | Read a forgotten record | `Forgotten`, distinct from `NotFound`"""
    memory_id = system.write("secret", 0.9)
    system.forget(memory_id)

    assert system.get(memory_id).outcome is ReadOutcome.FORGOTTEN
    assert system.get(memory_id).record is None, "a forgotten read carries no content"
    assert system.get("never-written").outcome is ReadOutcome.NOT_FOUND
    assert memory_id not in system.list_scope(), "I3.2"


@pytest.mark.check("P3.2")
def test_p3_2_forget_is_idempotent(system: MemorySystem) -> None:
    """P3.2 | Forget twice | Second call succeeds, no change"""
    root = system.write("root", 0.4)
    leaf = system.write("leaf", 0.9, sources=[root])
    first = system.forget(root)
    watched = (root, leaf)
    state = observable_state(system, watched, ("default",))

    second = system.forget(root)

    assert second.mode is first.mode
    assert second.forgotten == frozenset(), "a second forget does no work"
    assert second.deltas == ()
    assert observable_state(system, watched, ("default",)) == state


@pytest.mark.check("P3.3")
def test_p3_3_mid_chain_forget_handles_descendants(
    system: MemorySystem, mode: ForgetMode
) -> None:
    """P3.3 | Forget a mid-chain record | Descendants handled per declared mode"""
    root = system.write("root", 0.4)
    middle = system.write("middle", 0.8, sources=[root])
    leaf = system.write("leaf", 0.9, sources=[middle])

    receipt = system.forget(middle)

    assert receipt.mode is mode
    assert middle in receipt.forgotten
    assert system.get(middle).outcome is ReadOutcome.FORGOTTEN
    assert survives(system, root), "an ancestor of the target is never touched"

    if mode is ForgetMode.TOMBSTONE:
        assert survives(system, leaf)
        assert receipt.tombstoned == frozenset({middle})
        assert system.effective_confidence(leaf) == 0.4, "arithmetic unchanged"
    elif mode is ForgetMode.CASCADE:
        assert not survives(system, leaf)
        assert system.get(leaf).outcome is ReadOutcome.FORGOTTEN
        assert leaf in receipt.forgotten
    else:
        assert survives(system, leaf)
        assert leaf not in receipt.forgotten
        assert system.provenance(leaf).ancestor_ids() == frozenset()


@pytest.mark.check("P3.4")
def test_p3_4_no_resurrection(system: MemorySystem, mode: ForgetMode) -> None:
    """P3.4 | Re-write identical content | New id, no inherited descendants"""
    root = system.write("identical content", 0.4)
    leaf = system.write("leaf", 0.9, sources=[root])
    system.forget(root)

    rewritten = system.write("identical content", 0.4)

    assert rewritten != root, "an id is never reused"
    assert system.get(root).outcome is ReadOutcome.FORGOTTEN
    assert system.descendants(rewritten) == frozenset(), "no inherited descendants"
    if survives(system, leaf):
        assert rewritten not in system.provenance(leaf).nodes
        assert leaf not in system.descendants(rewritten)


@pytest.mark.check("P3.5")
def test_p3_5_receipt_is_complete(system: MemorySystem, mode: ForgetMode) -> None:
    """P3.5 | Inspect receipt | Mode, affected ids, and deltas present"""
    root = system.write("root", 0.4)
    middle = system.write("middle", 0.8, sources=[root])
    leaf = system.write("leaf", 0.9, sources=[middle])
    expected_descendants = {middle, leaf}

    receipt = system.forget(root)

    assert receipt.mode is mode
    assert root in receipt.forgotten
    survivors = {
        memory_id for memory_id in expected_descendants if survives(system, memory_id)
    }
    assert {delta.id for delta in receipt.deltas} == survivors, (
        "a delta for every surviving descendant, and none for a descendant that did "
        "not survive"
    )
    named = set(receipt.forgotten) | {delta.id for delta in receipt.deltas}
    assert {memory_id for memory_id, _ in receipt.affected_scopes} == named
    assert all(scope == "default" for _, scope in receipt.affected_scopes)
    if mode is ForgetMode.CASCADE:
        assert receipt.forgotten == {root} | expected_descendants


@pytest.mark.extra("forget-control-no-descendants")
def test_forget_without_descendants_is_mode_independent(
    registration: Registration,
) -> None:
    """Control: with no descendants, all declared modes agree.

    Two things are deliberately outside the comparison, because they are where a mode is
    supposed to describe itself: the receipt's ``tombstoned`` field, and the forgotten
    record's own retained arithmetic (a tombstone keeps its chain position by design,
    SPEC.md 6.1). Everything else a caller can observe must match.
    """
    from amr.registry import modes_for

    observations: dict[ForgetMode, tuple[str, ...]] = {}
    for mode in modes_for(registration):
        system = registration.build(mode)
        lonely = system.write("no descendants", 0.4)
        neighbour = system.write("unrelated", 0.9)
        receipt = system.forget(lonely)
        observations[mode] = (
            system.get(lonely).outcome.value,
            system.get(neighbour).outcome.value,
            repr(sorted(system.list_scope())),
            repr(system.effective_confidence(neighbour)),
            repr(sorted(receipt.forgotten)),
            repr(receipt.deltas),
            repr(sorted(receipt.affected_scopes)),
            repr(system.forget(lonely).forgotten),
        )
        with pytest.raises(ForgottenRecordError):
            system.revise(lonely, 0.1, "revise on a forgotten record is rejected")

    distinct = set(observations.values())
    assert len(distinct) == 1, f"modes disagreed with no descendants: {observations}"
