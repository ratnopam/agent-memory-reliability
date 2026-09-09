"""Weakest-link effective confidence, memoised. SPEC.md 5.

    effective(m) = min( declared(m), min{ effective(a) : a in sources(m) } )
    min over the empty set = the declared empty-chain convention (1.0 here)

Iterative rather than recursive so a deep chain cannot exhaust the interpreter stack, and
each ancestor is visited once, so a diamond constrains a sink exactly once (I2.3) and the
answer does not depend on traversal order (I2.4).

Memoised values are invalidated over ``{id} ∪ descendants(id)`` on every ``revise`` and
every ``forget``: those are the only two operations that can change an answer.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from amr.protocol import ConfidenceDelta, MemoryId
from systems.reference.store import Store


class ConfidenceIndex:
    def __init__(self, store: Store, empty_chain: float = 1.0) -> None:
        self._store = store
        self._empty_chain = empty_chain
        self._memo: dict[MemoryId, float] = {}

    def effective(self, memory_id: MemoryId) -> float:
        memo = self._memo
        if memory_id in memo:
            return memo[memory_id]
        stack: list[tuple[MemoryId, bool]] = [(memory_id, False)]
        while stack:
            node, expanded = stack.pop()
            if node in memo:
                continue
            record = self._store.require(node)
            if not expanded:
                stack.append((node, True))
                stack.extend(
                    (source_id, False)
                    for source_id in sorted(record.sources)
                    if source_id not in memo
                )
                continue
            chain_min = min(
                (memo[source_id] for source_id in record.sources),
                default=self._empty_chain,
            )
            memo[node] = min(record.declared_confidence, chain_min)
        return memo[memory_id]

    def snapshot(self, memory_ids: Iterable[MemoryId]) -> dict[MemoryId, float]:
        """Effective confidence for each id, read before a mutation changes it."""
        return {memory_id: self.effective(memory_id) for memory_id in memory_ids}

    def deltas(
        self, before: Mapping[MemoryId, float], survivors: Iterable[MemoryId]
    ) -> tuple[ConfidenceDelta, ...]:
        """One delta per survivor, sorted, including the ones that did not move.

        A delta for every survivor is what makes a receipt self-checking (I3.5): a
        descendant the implementation failed to recompute shows up as a missing row rather
        than as a silent zero.
        """
        return tuple(
            ConfidenceDelta(survivor, before[survivor], self.effective(survivor))
            for survivor in sorted(survivors)
        )

    def invalidate(self, memory_ids: Iterable[MemoryId]) -> None:
        for memory_id in memory_ids:
            self._memo.pop(memory_id, None)
            for descendant in self._store.descendants(memory_id):
                self._memo.pop(descendant, None)
