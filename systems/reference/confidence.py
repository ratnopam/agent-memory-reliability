"""Weakest-link effective confidence, memoised.

    effective(m) = min( declared(m), min{ effective(a) : a in sources(m) } )
    min over the empty set = the declared empty-chain convention (1.0 here)

The walk is iterative rather than recursive so that a deep chain cannot exhaust the
interpreter stack, and it visits each ancestor once, so a diamond constrains a sink
exactly once (I2.3) and the answer does not depend on traversal order (I2.4).

Memoised values are invalidated over ``{id} ∪ descendants(id)`` on every ``revise`` and
every ``forget``: those are the only two operations that can change an answer.
"""

from __future__ import annotations

from typing import Iterable

from harness.protocol import MemoryId
from systems.reference.store import Store


class ConfidenceIndex:
    def __init__(self, store: Store, empty_chain: float = 1.0) -> None:
        self._store = store
        self._empty_chain = empty_chain
        self._memo: dict[MemoryId, float] = {}

    @property
    def empty_chain(self) -> float:
        return self._empty_chain

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
                for source_id in sorted(record.sources):
                    if source_id not in memo:
                        stack.append((source_id, False))
                continue
            chain_min = min(
                (memo[source_id] for source_id in record.sources),
                default=self._empty_chain,
            )
            memo[node] = min(record.declared_confidence, chain_min)
        return memo[memory_id]

    def invalidate(self, memory_ids: Iterable[MemoryId]) -> None:
        for memory_id in memory_ids:
            self._memo.pop(memory_id, None)
            for descendant in self._store.descendants(memory_id):
                self._memo.pop(descendant, None)

    def clear(self) -> None:
        self._memo.clear()
