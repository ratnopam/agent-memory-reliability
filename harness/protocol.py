"""Abstract operation set for agent memory reliability conformance.

This module is the boundary the specification constrains. It has no dependencies
beyond the standard library, and it never imports any memory system. Adapters in
``systems/`` implement ``MemorySystem``; property tests in ``properties/`` are
written against this protocol and nothing else.

See SPEC.md for the normative statement of each property.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Protocol, runtime_checkable

MemoryId = str
Scope = str


class ForgetMode(str, Enum):
    """See SPEC.md 6.1."""

    TOMBSTONE = "tombstone"
    CASCADE = "cascade"
    ERASE = "erase"


class ReadOutcome(str, Enum):
    """``get`` distinguishes three outcomes. See SPEC.md 3.

    FORGOTTEN and NOT_FOUND are deliberately distinct: conformance check P3.1
    depends on an implementation not collapsing them.
    """

    OK = "ok"
    NOT_FOUND = "not_found"
    FORGOTTEN = "forgotten"


class CycleError(Exception):
    """Raised when a write would introduce a cycle. See SPEC.md I1.1."""


class ScopeError(Exception):
    """Raised on an unauthorised cross-scope access. See SPEC.md I4.1."""


class UnresolvedSourceError(Exception):
    """Raised when a write cites a source that does not resolve. See SPEC.md I1.6.

    Distinct from ``CycleError`` because the two rejections are different checks
    (P1.1 and P1.6) and a caller repairs them differently.
    """


class ForgottenRecordError(Exception):
    """Raised when an operation targets a record that has been forgotten.

    ``get`` reports this state as ``ReadOutcome.FORGOTTEN`` rather than raising
    (SPEC.md I3.1). Operations that would change or walk a record that no longer
    exists -- ``revise``, ``provenance`` on a cascaded record -- raise instead, so
    that a caller cannot mistake a forgotten record for a fresh one.
    """


@dataclass(frozen=True)
class Origin:
    """What an external root refers to. See SPEC.md 2.1.

    Descriptive only: ``kind`` and ``ref`` never affect the arithmetic in SPEC.md 5.
    """

    kind: str
    ref: str


@dataclass(frozen=True)
class Record:
    id: MemoryId
    content: object
    declared_confidence: float
    sources: frozenset[MemoryId] = frozenset()
    scope: Scope = "default"
    origin: Origin | None = None


@dataclass(frozen=True)
class ReadResult:
    outcome: ReadOutcome
    record: Record | None = None


@dataclass(frozen=True)
class ChainNode:
    """One entry in a provenance walk.

    ``opaque`` marks an ancestor that exists and contributes confidence but whose
    content is withheld across a scope boundary (SPEC.md I4.3). ``tombstoned``
    marks an ancestor whose content was erased but whose chain position survives.
    Both keep the walk referentially complete (SPEC.md I1.4).
    """

    id: MemoryId
    declared_confidence: float
    sources: frozenset[MemoryId] = frozenset()
    tombstoned: bool = False
    opaque: bool = False


@dataclass(frozen=True)
class Chain:
    root_id: MemoryId
    nodes: Mapping[MemoryId, ChainNode]

    def ancestor_ids(self) -> frozenset[MemoryId]:
        return frozenset(self.nodes) - {self.root_id}


@dataclass(frozen=True)
class ConfidenceDelta:
    id: MemoryId
    before: float
    after: float

    @property
    def inflated(self) -> bool:
        """True when a removal raised a survivor's confidence. SPEC.md 6.4."""
        return self.after > self.before


@dataclass(frozen=True)
class RevisionReceipt:
    """Returned by ``revise``. See SPEC.md I2.6.

    Retaining ``before`` is what lets an audit answer "what did this say last
    quarter". An implementation that overwrites without recording fails P2.6.
    """

    id: MemoryId
    before: float
    after: float
    reason: str
    deltas: tuple[ConfidenceDelta, ...] = ()


@dataclass(frozen=True)
class ForgetReceipt:
    """Returned by ``forget``. See SPEC.md I3.5."""

    mode: ForgetMode
    forgotten: frozenset[MemoryId]
    tombstoned: frozenset[MemoryId] = frozenset()
    deltas: tuple[ConfidenceDelta, ...] = ()
    affected_scopes: tuple[tuple[MemoryId, Scope], ...] = ()
    """Scope of every id named by this receipt, sorted by id.

    A cascade crossing a scope boundary is one receipt, not two (SPEC.md I4.4), so
    the receipt has to say which side of the boundary each affected id was on.
    """


@dataclass(frozen=True)
class Capabilities:
    """Published by every adapter. See SPEC.md 8.

    The declaration is what lets the suite report DIVERGENCE rather than FAIL for
    behavior the specification deliberately leaves open.
    """

    system: str
    version: str
    supported_forget_modes: frozenset[ForgetMode]
    default_forget_mode: ForgetMode
    empty_chain_convention: float = 1.0
    revision: str = "logged"
    revision_raise_supported: bool = True
    scopes: str = "native"
    cross_scope_derivation: str = "opaque-ancestor"
    durability: str = "in-memory"
    notes: tuple[str, ...] = field(default_factory=tuple)


@runtime_checkable
class MemorySystem(Protocol):
    """The operations conformance is defined against. SPEC.md 3.

    The eight operations of SPEC.md 3, plus ``capabilities`` and ``revisions``.
    ``revisions`` is the reader for the history I2.6 requires to be retrievable
    after the fact; SPEC.md 3 lists the writer (``revise``) but no reader, so P2.6
    cannot be checked without it. See design-notes/spec-feedback.md.
    """

    def capabilities(self) -> Capabilities:
        ...

    def write(
        self,
        content: object,
        declared_confidence: float,
        sources: Iterable[MemoryId] = (),
        scope: Scope = "default",
        origin: Origin | None = None,
    ) -> MemoryId:
        """Raises CycleError if ``sources`` would close a cycle (I1.1).

        Raises UnresolvedSourceError if any id in ``sources`` does not resolve, and
        persists nothing in that case (I1.6). ``origin`` is descriptive metadata for
        a root that stands in for something outside the store (SPEC.md 2.1).
        """

    def get(self, memory_id: MemoryId, scope: Scope = "default") -> ReadResult:
        ...

    def provenance(self, memory_id: MemoryId, scope: Scope = "default") -> Chain:
        """Transitive ancestor closure, each ancestor once (I1.2, I1.3)."""

    def effective_confidence(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> float:
        """min(declared, min over ancestors), empty set per capabilities (P2)."""

    def descendants(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> frozenset[MemoryId]:
        ...

    def revise(
        self,
        memory_id: MemoryId,
        new_declared: float,
        reason: str,
        scope: Scope = "default",
    ) -> RevisionReceipt:
        """Change declared confidence only. Everything else is immutable (§3).

        Lowering propagates to descendants; raising does not lift them past their
        own declared values (I2.7). Raising is optional and declared in
        ``Capabilities.revision_raise_supported``.

        Raises ForgottenRecordError if ``memory_id`` has been forgotten.
        """

    def revisions(
        self, memory_id: MemoryId, scope: Scope = "default"
    ) -> tuple[RevisionReceipt, ...]:
        """Every revision of ``memory_id``, oldest first. See SPEC.md I2.6."""

    def forget(
        self,
        memory_id: MemoryId,
        scope: Scope = "default",
        mode: ForgetMode | None = None,
    ) -> ForgetReceipt:
        """``mode=None`` means the adapter's declared default."""

    def list_scope(self, scope: Scope = "default") -> frozenset[MemoryId]:
        ...


def effective_confidence_reference(
    declared: Mapping[MemoryId, float],
    sources: Mapping[MemoryId, Iterable[MemoryId]],
    memory_id: MemoryId,
    empty_chain: float = 1.0,
) -> float:
    """Normative arithmetic for P2, independent of any storage.

    Present here so the rule can be read in one place and so property tests can
    compare an implementation against it without importing an implementation.
    """
    seen: set[MemoryId] = set()

    def walk(node: MemoryId) -> float:
        if node in seen:
            return 1.0
        seen.add(node)
        parents = [p for p in sources.get(node, ()) if p in declared]
        chain_min = min((walk(p) for p in parents), default=empty_chain)
        return min(declared[node], chain_min)

    return walk(memory_id)
