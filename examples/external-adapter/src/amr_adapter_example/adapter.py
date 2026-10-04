"""The twelve operations of SPEC.md 3, over one dict. Nothing else.

Specification types are spelled ``protocol.X`` so that the import list is visibly the whole
of the coupling. README.md, next to this file, says which methods are worth copying and why.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from amr import protocol
from amr.protocol import ForgetMode, MemoryId, Scope
from amr_adapter_example.capabilities import DECLARATION, EMPTY_CHAIN, MODES


@dataclass
class Row:
    """One record. ``tombstoned`` keeps its confidence and its edges (SPEC.md 6.1)."""

    id: MemoryId
    content: object
    declared: float
    sources: frozenset[MemoryId]
    scope: Scope
    origin: protocol.Origin | None = None
    tombstoned: bool = False


class ExampleAdapter:
    """A conformance adapter for a store that happens to be a dict."""

    def __init__(self, default_forget_mode: ForgetMode = ForgetMode.TOMBSTONE) -> None:
        mode = ForgetMode(default_forget_mode)
        if mode not in MODES:
            raise ValueError(f"this adapter does not implement {mode.value!r}")
        self._default_mode = mode
        self._rows: dict[MemoryId, Row] = {}
        self._grants: dict[Scope, set[Scope]] = {}
        self._issued = 0

    def capabilities(self) -> protocol.Capabilities:
        return replace(DECLARATION, default_forget_mode=self._default_mode)

    def write(
        self, content: object, declared_confidence: float,
        sources: Iterable[MemoryId] = (), scope: Scope = "default",
        origin: protocol.Origin | None = None,
    ) -> MemoryId:
        cited = frozenset(sources)
        declared = _confidence(declared_confidence)
        # Strict: nothing is stored unless every cited id resolves for this scope (I1.6).
        for source in sorted(cited):
            if not self._visible(source, scope):
                raise protocol.UnresolvedSourceError(f"{source!r} does not resolve")
            if self._rows[source].tombstoned:
                raise protocol.ForgottenRecordError(f"{source!r} has been forgotten")
        self._issued += 1
        memory_id = f"e{self._issued}"
        self._rows[memory_id] = Row(memory_id, content, declared, cited, scope, origin)
        return memory_id

    def revise(
        self, memory_id: MemoryId, new_declared: float,
        reason: str, scope: Scope = "default",
    ) -> protocol.RevisionReceipt:
        row = self._resolve(memory_id, scope, owner_only=True)
        if row.tombstoned:
            raise protocol.ForgottenRecordError(f"{memory_id!r} has been forgotten")
        before, after = row.declared, _confidence(new_declared)
        was = {child: self._weakest(child) for child in self._offspring(memory_id)}
        row.declared = after
        # Nothing is appended: revision="none" means no history, so P2.6 fails.
        return protocol.RevisionReceipt(memory_id, before, after, reason, self._deltas(was))

    def forget(
        self, memory_id: MemoryId, scope: Scope = "default",
        mode: ForgetMode | None = None,
    ) -> protocol.ForgetReceipt:
        chosen = self._default_mode if mode is None else ForgetMode(mode)
        if chosen not in MODES:
            raise ValueError(f"this adapter does not implement {chosen.value!r}")
        row = self._resolve(memory_id, scope, owner_only=True)
        if row.tombstoned:
            return protocol.ForgetReceipt(chosen, frozenset())  # idempotent (I3.3)
        was = {child: self._weakest(child) for child in self._offspring(memory_id)}
        row.tombstoned = True
        forgotten = frozenset({memory_id})
        affected = sorted(forgotten | set(was))
        return protocol.ForgetReceipt(
            chosen, forgotten, tombstoned=forgotten, deltas=self._deltas(was),
            affected_scopes=tuple((each, self._rows[each].scope) for each in affected),
        )

    def get(self, memory_id: MemoryId, scope: Scope = "default") -> protocol.ReadResult:
        if not self._visible(memory_id, scope):
            return protocol.ReadResult(protocol.ReadOutcome.NOT_FOUND)
        row = self._rows[memory_id]
        if row.tombstoned:
            return protocol.ReadResult(protocol.ReadOutcome.FORGOTTEN)
        record = protocol.Record(
            row.id, row.content, row.declared, row.sources, row.scope, row.origin
        )
        return protocol.ReadResult(protocol.ReadOutcome.OK, record)

    def provenance(self, memory_id: MemoryId, scope: Scope = "default") -> protocol.Chain:
        self._resolve(memory_id, scope)
        nodes: dict[MemoryId, protocol.ChainNode] = {}
        for each in sorted(self._closure([memory_id])):
            row = self._rows[each]
            # A foreign ancestor keeps its confidence and loses its content (I4.3).
            nodes[each] = protocol.ChainNode(
                each, row.declared, row.sources, row.tombstoned, row.scope != scope
            )
        return protocol.Chain(root_id=memory_id, nodes=nodes)

    def effective_confidence(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> float:
        # The scope decides whether this answers, never what it answers (I2.8, P2.8).
        self._resolve(memory_id, scope)
        return self._weakest(memory_id)

    def descendants(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> frozenset[MemoryId]:
        self._resolve(memory_id, scope)
        return frozenset(c for c in self._offspring(memory_id) if self._visible(c, scope))

    def revisions(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> tuple[protocol.RevisionReceipt, ...]:
        self._resolve(memory_id, scope)
        return ()  # revision="none". P2.6 fails here, and the declaration says it will.

    def list_scope(self, scope: Scope = "default") -> frozenset[MemoryId]:
        rows = self._rows.values()
        return frozenset(r.id for r in rows if r.scope == scope and not r.tombstoned)

    def grant(self, owner: Scope, reader: Scope) -> protocol.GrantReceipt:
        if owner == reader:
            raise ValueError("a scope does not need a grant to read itself")
        self._grants.setdefault(owner, set()).add(reader)
        return protocol.GrantReceipt(owner, reader, granted=True)

    def revoke(self, owner: Scope, reader: Scope) -> protocol.GrantReceipt:
        self._grants.get(owner, set()).discard(reader)
        return protocol.GrantReceipt(owner, reader, granted=False)

    def grants(self, owner: Scope) -> frozenset[Scope]:
        return frozenset(self._grants.get(owner, ()))

    def _visible(self, memory_id: MemoryId, scope: Scope) -> bool:
        """Native, or granted. A tombstone stays visible: forgotten is not absent (I3.1)."""
        row = self._rows.get(memory_id)
        return row is not None and scope in {row.scope, *self._grants.get(row.scope, ())}

    def _resolve(self, memory_id: MemoryId, scope: Scope, owner_only: bool = False) -> Row:
        """SPEC.md 3.1, in order: absent first, and only then not-yours (see README.md)."""
        if not self._visible(memory_id, scope):
            raise protocol.NotFoundError(f"{memory_id!r} does not resolve")
        row = self._rows[memory_id]
        if owner_only and row.scope != scope:
            raise protocol.ScopeError(f"{memory_id!r} is native to another scope")
        return row

    def _closure(self, ids: Iterable[MemoryId]) -> set[MemoryId]:
        """``ids`` and every ancestor of them, each one once (I1.2, I1.3)."""
        found: set[MemoryId] = set()
        pending = [each for each in ids if each in self._rows]
        while pending:
            current = pending.pop()
            if current not in found:
                found.add(current)
                pending.extend(self._rows[current].sources & self._rows.keys())
        return found

    def _weakest(self, memory_id: MemoryId) -> float:
        """SPEC.md 5, read literally: the smallest declared value in the whole closure."""
        declared = (self._rows[each].declared for each in self._closure([memory_id]))
        return min(declared, default=EMPTY_CHAIN)

    def _offspring(self, memory_id: MemoryId) -> frozenset[MemoryId]:
        """Everything derived from ``memory_id``, transitively, ignoring visibility."""
        others = (row.id for row in self._rows.values() if row.id != memory_id)
        return frozenset(each for each in others if memory_id in self._closure([each]))

    def _deltas(self, was: dict[MemoryId, float]) -> tuple[protocol.ConfidenceDelta, ...]:
        """One delta per affected record, whether or not its number moved (I3.5)."""
        return tuple(
            protocol.ConfidenceDelta(each, before, self._weakest(each))
            for each, before in sorted(was.items())
        )


def _confidence(value: float) -> float:
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"declared_confidence must be in [0.0, 1.0], got {value}")
    return float(value)
