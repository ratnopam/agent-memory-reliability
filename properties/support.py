"""Helpers shared by the property modules.

Everything here is written against ``harness.protocol`` only. Nothing imports an
implementation, so a helper cannot accidentally encode the reference system's habits.
"""

from __future__ import annotations

import json
import random
from typing import Iterable, Sequence

from harness.protocol import (
    Chain,
    ForgottenRecordError,
    MemoryId,
    MemorySystem,
    ReadOutcome,
    Scope,
)


def canonical_chain(chain: Chain) -> str:
    """A byte-comparable rendering of a provenance walk.

    Used by P1.5: "byte-identical chain" needs a byte string, and a ``Chain`` holds
    sets whose iteration order is not part of its meaning.
    """
    return json.dumps(
        {
            "root": chain.root_id,
            "nodes": [
                {
                    "id": node.id,
                    "declared_confidence": node.declared_confidence,
                    "sources": sorted(node.sources),
                    "tombstoned": node.tombstoned,
                    "opaque": node.opaque,
                }
                for node in sorted(chain.nodes.values(), key=lambda n: n.id)
            ],
        },
        sort_keys=True,
        indent=None,
    )


def assert_referentially_complete(chain: Chain) -> None:
    """I1.4: every id named inside a returned chain resolves inside that chain."""
    for node in chain.nodes.values():
        for source_id in node.sources:
            assert source_id in chain.nodes, (
                f"dangling id {source_id!r} in the chain of {chain.root_id!r}: "
                "a walk that names an id it cannot resolve is a conformance failure"
            )


def assert_acyclic(chain: Chain) -> None:
    """I1.1, verified on what the walk actually returned (Kahn's algorithm)."""
    pending = {node.id: set(node.sources) for node in chain.nodes.values()}
    ordered: list[MemoryId] = []
    while True:
        ready = sorted(
            node_id for node_id, sources in pending.items() if not sources
        )
        if not ready:
            break
        for node_id in ready:
            del pending[node_id]
            ordered.append(node_id)
        for sources in pending.values():
            sources.difference_update(ready)
    assert not pending, f"cycle among {sorted(pending)}"


def readable_graph(
    system: MemorySystem, memory_ids: Iterable[MemoryId], scope: Scope = "default"
) -> tuple[dict[MemoryId, float], dict[MemoryId, set[MemoryId]]]:
    """Declared confidences and edges as the system reports them.

    The pair is what ``effective_confidence_reference`` consumes, which is how a test
    compares a system against the normative arithmetic without knowing anything about
    how the system stores it.
    """
    declared: dict[MemoryId, float] = {}
    sources: dict[MemoryId, set[MemoryId]] = {}
    for memory_id in memory_ids:
        for node in system.provenance(memory_id, scope).nodes.values():
            declared[node.id] = node.declared_confidence
            sources[node.id] = set(node.sources)
    return declared, sources


def survives(system: MemorySystem, memory_id: MemoryId, scope: Scope = "default") -> bool:
    """True when the record is still readable.

    A survival test, not a mode test: the caller must not have to know which forget
    mode ran to ask whether something is still there.
    """
    return system.get(memory_id, scope).outcome is ReadOutcome.OK


def effective_or_none(
    system: MemorySystem, memory_id: MemoryId, scope: Scope = "default"
) -> float | None:
    try:
        return system.effective_confidence(memory_id, scope)
    except (ForgottenRecordError, LookupError):
        return None


def observable_state(
    system: MemorySystem, memory_ids: Sequence[MemoryId], scopes: Sequence[Scope]
) -> str:
    """Everything a caller can observe, as a comparable string.

    Used where a check has to assert that an operation "changes nothing" (I3.3).
    """
    return json.dumps(
        {
            "scopes": {
                scope: sorted(system.list_scope(scope)) for scope in sorted(scopes)
            },
            "reads": {
                memory_id: [
                    system.get(memory_id, scope).outcome.value for scope in sorted(scopes)
                ]
                for memory_id in sorted(memory_ids)
            },
            "effective": {
                memory_id: effective_or_none(system, memory_id)
                for memory_id in sorted(memory_ids)
            },
        },
        sort_keys=True,
    )


#: Fixed seed. The random DAGs are data, not chance: two runs of the suite build the
#: same ten graphs, which is what makes ``make determinism`` meaningful.
DAG_SEED = 20261022


def random_dags(
    count: int = 10, seed: int = DAG_SEED
) -> tuple[tuple[tuple[float, tuple[int, ...]], ...], ...]:
    """``count`` randomly shaped DAGs as ``(declared, parent indices)`` per node.

    Parents are always earlier nodes, so the shape is a DAG by construction and can be
    written parents-first, which strict writes (I1.6) require.
    """
    rng = random.Random(seed)
    dags: list[tuple[tuple[float, tuple[int, ...]], ...]] = []
    for _ in range(count):
        size = rng.randint(3, 12)
        nodes: list[tuple[float, tuple[int, ...]]] = []
        for index in range(size):
            fan_in = 0 if index == 0 else rng.randint(0, min(3, index))
            parents = tuple(sorted(rng.sample(range(index), fan_in)))
            declared = rng.choice([0.05, 0.2, 0.4, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0])
            nodes.append((declared, parents))
        dags.append(tuple(nodes))
    return tuple(dags)


def write_dag(
    system: MemorySystem,
    dag: Sequence[tuple[float, Sequence[int]]],
    scope: Scope = "default",
) -> list[MemoryId]:
    ids: list[MemoryId] = []
    for index, (declared, parents) in enumerate(dag):
        ids.append(
            system.write(
                content=f"node-{index}",
                declared_confidence=declared,
                sources=[ids[parent] for parent in parents],
                scope=scope,
            )
        )
    return ids
