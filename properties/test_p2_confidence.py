"""P2 -- confidence cascading along the chain. SPEC.md 5.

A memory cannot be more trustworthy than the weakest evidence it rests on.

P2.5 is the check the poster is about. It is a signed comparison with no mode in it:
``effective_after <= effective_before``. Under ``tombstone`` and ``cascade`` it holds.
Under ``erase`` it does not, because the chain is shorter and ``min`` runs over a smaller
set -- and because the system declared ``erase`` and SPEC.md 6.4 leaves the tension open,
the suite reports DIVERGENCE rather than FAIL. One configuration flag, two outcomes.
"""

from __future__ import annotations

import random
from typing import Sequence

import pytest

from amr.outcomes import erasure_inflation_is_declared
from amr.protocol import (
    Capabilities,
    ForgetMode,
    MemorySystem,
    ReadOutcome,
    effective_confidence_reference,
)
from properties.conftest import DivergenceRecorder
from properties.interleavings import ALPHA, BETA
from properties.support import (
    random_dags,
    readable_graph,
    sharing_system,
    survives,
    write_dag,
)

#: A third scope, so that P2.8's bounding ancestor is one the reader cannot reach: a
#: grant of alpha's scope conveys alpha's records, not the records alpha itself derived
#: from. Open question 9 is about this granularity; the check holds either way.
GAMMA = "gamma"


@pytest.mark.check("P2.1")
def test_p2_1_chain_bounded_by_weakest(system: MemorySystem) -> None:
    """P2.1 | Chain 0.4 -> 0.9, read leaf | 0.4"""
    root = system.write("weak evidence", 0.4)
    leaf = system.write("confident conclusion", 0.9, sources=[root])

    assert system.effective_confidence(leaf) == 0.4
    assert system.effective_confidence(root) == 0.4


@pytest.mark.check("P2.2")
def test_p2_2_downgrade_propagates(system: MemorySystem) -> None:
    """P2.2 | Revise root 0.9 -> 0.2, read leaf | Leaf <= 0.2"""
    root = system.write("root", 0.9)
    middle = system.write("middle", 0.8, sources=[root])
    leaf = system.write("leaf", 0.85, sources=[middle])
    assert system.effective_confidence(leaf) == 0.8

    receipt = system.revise(root, 0.2, "contradicted by a postmortem")

    assert system.effective_confidence(leaf) <= 0.2
    assert system.effective_confidence(middle) <= 0.2
    assert {delta.id for delta in receipt.deltas} == {middle, leaf}
    assert all(delta.after <= delta.before for delta in receipt.deltas)


@pytest.mark.check("P2.3")
def test_p2_3_diamond_bounded_once(system: MemorySystem) -> None:
    """P2.3 | Diamond with one weak ancestor | Sink bounded once, not squared"""
    shared = system.write("weak shared root", 0.5)
    left = system.write("left", 0.9, sources=[shared])
    right = system.write("right", 0.9, sources=[shared])
    sink = system.write("sink", 1.0, sources=[left, right])

    assert system.effective_confidence(sink) == 0.5, "0.5, not 0.5 * 0.5"


@pytest.mark.check("P2.4")
def test_p2_4_root_is_its_own_bound(system: MemorySystem) -> None:
    """P2.4 | Root with no sources, declared 0.7 | 0.7"""
    root = system.write("root", 0.7)

    assert system.effective_confidence(root) == 0.7
    assert system.provenance(root).ancestor_ids() == frozenset()


@pytest.mark.check("P2.5")
def test_p2_5_no_inflation_on_removal(
    system: MemorySystem,
    mode: ForgetMode,
    capabilities: Capabilities,
    divergence: DivergenceRecorder,
) -> None:
    """P2.5 | Forget weakest ancestor, re-read leaf | effective_after <= effective_before"""
    weak = system.write("weak evidence", 0.4)
    strong = system.write("strong evidence", 0.95)
    leaf = system.write("conclusion", 0.9, sources=[weak, strong])
    downstream = system.write("acted on the conclusion", 1.0, sources=[leaf])
    watched = (leaf, downstream)

    before = {memory_id: system.effective_confidence(memory_id) for memory_id in watched}
    assert before[leaf] == 0.4

    receipt = system.forget(weak)

    # Survival, not mode: a record that did not survive cannot be inflated, so the
    # comparison is simply vacuous for it. Nothing here branches on the forget mode.
    after = {
        memory_id: system.effective_confidence(memory_id)
        for memory_id in watched
        if survives(system, memory_id)
    }

    try:
        for memory_id, value in after.items():
            assert value <= before[memory_id], (
                f"{memory_id} rose from {before[memory_id]} to {value} when its "
                "weakest ancestor was forgotten"
            )
    except AssertionError:
        if not erasure_inflation_is_declared(capabilities, mode):
            raise
        # The failure is only a divergence if the system also behaved consistently with
        # its own declaration: it named the mode, it reported the inflation it caused,
        # and the inflated value is exactly the declared arithmetic over the shortened
        # chain rather than an arbitrary number.
        assert receipt.mode is mode
        inflated = [delta for delta in receipt.deltas if delta.inflated]
        assert inflated, "a receipt must report the inflation the removal caused"
        declared, sources = readable_graph(system, after)
        for memory_id, value in after.items():
            assert value == effective_confidence_reference(
                declared,
                sources,
                memory_id,
                capabilities.empty_chain_convention,
            )
        divergence.record(
            check="P2.5",
            spec_ref="SPEC.md 6.4",
            detail=(
                f"{mode.value}: {inflated[0].id} rose "
                f"{inflated[0].before} -> {inflated[0].after} when its weakest "
                f"ancestor was forgotten; min over the empty chain returns "
                f"{capabilities.empty_chain_convention}"
            ),
        )


@pytest.mark.check("P2.6")
def test_p2_6_revisions_are_recorded(system: MemorySystem) -> None:
    """P2.6 | Read revision history after a revise | Prior value, new value, and reason present"""
    root = system.write("root", 0.9)
    system.revise(root, 0.2, "contradicted by a postmortem")
    system.revise(root, 0.3, "partially rehabilitated")

    history = system.revisions(root)
    assert [(entry.before, entry.after) for entry in history] == [(0.9, 0.2), (0.2, 0.3)]
    assert history[0].reason == "contradicted by a postmortem"
    assert history[1].reason == "partially rehabilitated"


@pytest.mark.check("P2.7")
def test_p2_7_raise_does_not_lift_descendant(
    system: MemorySystem, capabilities: Capabilities
) -> None:
    """P2.7 | Raise an ancestor above a descendant's declared value | Descendant unchanged"""
    root = system.write("root", 0.5)
    leaf = system.write("leaf", 0.4, sources=[root])
    assert system.effective_confidence(leaf) == 0.4

    if not capabilities.revision_raise_supported:
        # A system that declares it cannot raise has to refuse, not silently accept.
        # The specification does not name the exception, so the check accepts either
        # "you asked for something invalid" or "I do not implement that".
        with pytest.raises((ValueError, NotImplementedError)):
            system.revise(root, 0.9, "raise attempt on a system that declares no raise")
        assert system.effective_confidence(leaf) == 0.4
        return

    system.revise(root, 0.9, "corroborated")

    assert system.effective_confidence(leaf) == 0.4, "a record is capped by its own claim"
    assert system.effective_confidence(root) == 0.9


@pytest.mark.check("P2.8")
def test_p2_8_effective_confidence_is_scope_invariant(
    system: MemorySystem, capabilities: Capabilities
) -> None:
    """P2.8 | Read effective_confidence from the owner and from a granted reader | Identical

    I2.8. The scope argument decides *whether* the operation answers, never what it
    answers. The chain is built so the two readings could differ if it did: the leaf's
    bound comes from an ancestor the reader never gains sight of, so a scope-relative
    implementation would hand the reader the higher, inflated number.
    """
    sharing = sharing_system(system, capabilities)
    weak = system.write("weak evidence", 0.3, scope=GAMMA)
    sharing.grant(GAMMA, ALPHA)
    leaf = system.write("conclusion", 0.9, sources=[weak], scope=ALPHA)
    sharing.grant(ALPHA, BETA)

    owner_value = system.effective_confidence(leaf, ALPHA)
    assert owner_value == 0.3

    assert system.get(leaf, BETA).outcome is ReadOutcome.OK, "the grant landed"
    assert system.get(weak, BETA).outcome is ReadOutcome.NOT_FOUND, (
        "a grant of alpha's scope does not reach gamma's records"
    )

    assert system.effective_confidence(leaf, BETA) == owner_value, (
        "effective confidence is a property of the graph, not of who is asking"
    )


@pytest.mark.extra("reference-arithmetic-agreement")
def test_matches_reference_arithmetic_on_random_dags(any_system: MemorySystem) -> None:
    """Ten fixed-seed random DAGs agree with effective_confidence_reference."""
    capabilities = any_system.capabilities()
    dags = random_dags(count=10)
    assert len(dags) == 10
    for dag in dags:
        # Each DAG is written as a fresh disconnected component of the same store, so
        # the check also exercises a graph with several roots.
        ids = write_dag(any_system, dag)
        declared, sources = readable_graph(any_system, ids)
        for memory_id in ids:
            assert any_system.effective_confidence(
                memory_id
            ) == effective_confidence_reference(
                declared, sources, memory_id, capabilities.empty_chain_convention
            )


@pytest.mark.extra("insertion-order-independence")
def test_effective_confidence_is_insertion_order_independent(
    make_any_system,
) -> None:
    """I2.4: the same diamond built in two orders yields the same numbers."""
    forward = make_any_system()
    shared_a = forward.write("shared", 0.35)
    left_a = forward.write("left", 0.9, sources=[shared_a])
    right_a = forward.write("right", 0.8, sources=[shared_a])
    sink_a = forward.write("sink", 1.0, sources=[left_a, right_a])

    reversed_ = make_any_system()
    shared_b = reversed_.write("shared", 0.35)
    right_b = reversed_.write("right", 0.8, sources=[shared_b])
    left_b = reversed_.write("left", 0.9, sources=[shared_b])
    sink_b = reversed_.write("sink", 1.0, sources=[right_b, left_b])

    assert forward.effective_confidence(sink_a) == reversed_.effective_confidence(sink_b)
    assert forward.effective_confidence(left_a) == reversed_.effective_confidence(left_b)


@pytest.mark.extra("topological-order-independence")
def test_effective_confidence_is_topological_order_independent(make_any_system) -> None:
    """I2.4: ten random DAGs, each written in two valid topological orders, agree.

    I2.4 says "same graph, same values, independent of insertion or traversal order",
    and the check above it tests one diamond in two orders. That shape has exactly two
    valid orders and three edges; a store whose arithmetic depended on insertion order
    in a way a diamond cannot show would pass it.

    Store-assigned ids differ between the two runs, so the comparison is keyed by
    content label, which is the only thing the two graphs share. Both orders are
    asserted to be topological before anything is compared: an order that was not would
    be rejected by strict writes (I1.6) rather than measuring anything.
    """
    dags = random_dags(count=10)
    assert len(dags) == 10
    rng = random.Random(ORDER_SEED)
    reordered_at_least_once = False

    for dag in dags:
        natural = tuple(range(len(dag)))
        shuffled = _topological_order(dag, rng)
        for order in (natural, shuffled):
            assert _is_topological(dag, order), f"{order} is not a write order for {dag}"
        reordered_at_least_once |= shuffled != natural

        first = _effective_by_label(make_any_system(), dag, natural)
        second = _effective_by_label(make_any_system(), dag, shuffled)
        assert first == second, (
            "effective confidence depends on the order the graph was written in: "
            f"{first} vs {second}"
        )

    assert reordered_at_least_once, (
        "every generated order matched the natural one; the check compared a graph "
        "with itself ten times"
    )


#: Fixed, like DAG_SEED: the second write order is data, not chance, so a failure is
#: reproducible from this file alone and ``make determinism`` stays meaningful.
ORDER_SEED = 20261104


def _topological_order(
    dag: Sequence[tuple[float, Sequence[int]]], rng: random.Random
) -> tuple[int, ...]:
    """A valid write order, chosen with random tie-breaking among the ready nodes."""
    pending = {index: set(parents) for index, (_, parents) in enumerate(dag)}
    order: list[int] = []
    while pending:
        ready = sorted(index for index, parents in pending.items() if not parents)
        chosen = rng.choice(ready)
        del pending[chosen]
        order.append(chosen)
        for parents in pending.values():
            parents.discard(chosen)
    return tuple(order)


def _is_topological(
    dag: Sequence[tuple[float, Sequence[int]]], order: Sequence[int]
) -> bool:
    position = {index: place for place, index in enumerate(order)}
    return sorted(position) == list(range(len(dag))) and all(
        position[parent] < position[index]
        for index, (_, parents) in enumerate(dag)
        for parent in parents
    )


def _effective_by_label(
    system: MemorySystem,
    dag: Sequence[tuple[float, Sequence[int]]],
    order: Sequence[int],
) -> dict[str, float]:
    """Write ``dag`` in ``order``, and report the numbers keyed by content label."""
    ids: dict[int, str] = {}
    for index in order:
        declared, parents = dag[index]
        ids[index] = system.write(
            content=f"node-{index}",
            declared_confidence=declared,
            sources=[ids[parent] for parent in parents],
        )
    return {
        f"node-{index}": system.effective_confidence(memory_id)
        for index, memory_id in sorted(ids.items())
    }
