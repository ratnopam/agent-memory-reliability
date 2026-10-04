"""The store on its own: field mapping and nothing else.

A long-term store holds JSON documents under a namespace and a key. It can put, get,
search, delete and list namespaces. Everything in this module is one of those five calls
plus a dictionary, which is the point: this is what a store answers before anybody writes
a layer over it.

Every operation the specification defines as *computed* — the provenance walk, the
weakest-link bound, the descendant set, a revision with its history, a forget with a
receipt, a grant — raises ``NotProvided``, naming itself. The checks that call them FAIL,
and **a FAIL here means "this store does not provide this", not "this store is
defective"**. A document store was not built to answer these questions. The failing column
is the measurement of the gap a layer has to fill, which is what
``systems/langgraph_store/layered.py`` then fills with the reference's semantics.

Ids are allocated here, not by the store: a store assigns no identifiers, and a conformance
check cannot run without stable ones (SPEC.md 2). That is the one thing this module
computes, and it is the smallest thing it could have been.
"""

from __future__ import annotations

from typing import Iterable

from amr.protocol import (
    Capabilities,
    ForgetMode,
    MemoryId,
    Origin,
    ReadOutcome,
    ReadResult,
    Record,
    Scope,
)
from systems.langgraph_store.naming import PAGE, RECORDS, VERSION, every_item

NOTES = (
    (
        "The store alone: put, get, search, delete, list_namespaces, and no computed "
        "operation. A FAIL below means the store does not provide the operation, not "
        "that it answered wrongly."
    ),
    (
        "One namespace per scope and the record id as the key, so visibility is the "
        "store's own boundary. Values are plain JSON a reader can inspect in the store."
    ),
    (
        "Forget modes name tombstone because a column cannot be measured without a "
        "declared mode; forget itself is not provided, so every P3 check fails."
    ),
)


class NotProvided(NotImplementedError):
    """Raised by every operation this store does not have.

    A distinct exception rather than a wrong answer. A store that returned an empty walk
    or a default confidence would pass checks by inventing values, which is the failure
    this whole repository exists to catch.
    """

    def __init__(self, operation: str) -> None:
        super().__init__(
            f"{operation} is not provided by this store: it stores documents under a "
            "namespace and a key and computes nothing over them. See "
            "systems/langgraph_store/layered.py for the same store with the "
            "specification's semantics on top."
        )


class StoreAlone:
    """A ``MemorySystem`` that is the store's five operations and no more."""

    def __init__(self, store: object | None = None, name: str = "langgraph-store") -> None:
        from langgraph.store.memory import InMemoryStore

        self._store = InMemoryStore() if store is None else store
        self._name = name
        self._counter = 0

    def capabilities(self) -> Capabilities:
        """Every field of SPEC.md 8, stated for a store that computes nothing."""
        return Capabilities(
            system=self._name,
            version=VERSION,
            supported_forget_modes=frozenset({ForgetMode.TOMBSTONE}),
            default_forget_mode=ForgetMode.TOMBSTONE,
            empty_chain_convention=1.0,
            revision="none",
            revision_raise_supported=False,
            # The same word the reference uses, because it is the same claim: a scope is
            # the store's own addressing and not a field a reader has to remember to
            # filter on. The pair is meant to be read as two columns, and a second word
            # for one mechanism would make the rows look different where they agree.
            scopes="native",
            cross_scope_derivation="rejected",
            durability="in-memory",
            notes=NOTES,
        )

    # ------------------------------------------------------- what a store can answer

    def write(
        self,
        content: object,
        declared_confidence: float,
        sources: Iterable[MemoryId] = (),
        scope: Scope = "default",
        origin: Origin | None = None,
    ) -> MemoryId:
        self._counter += 1
        memory_id = f"m{self._counter:03d}"
        self._store.put(
            (*RECORDS, scope),
            memory_id,
            {
                "id": memory_id,
                "content": content,
                "declared_confidence": declared_confidence,
                "sources": sorted(sources),
                "scope": scope,
                "origin": None if origin is None else {"kind": origin.kind, "ref": origin.ref},
            },
            index=False,  # no embedding index: a semantic index is not configured here
        )
        return memory_id

    def get(self, memory_id: MemoryId, scope: Scope = "default") -> ReadResult:
        item = self._store.get((*RECORDS, scope), memory_id)
        if item is None:
            return ReadResult(ReadOutcome.NOT_FOUND)
        value = item.value
        origin = value.get("origin")
        return ReadResult(
            ReadOutcome.OK,
            Record(
                id=value["id"],
                content=value["content"],
                declared_confidence=value["declared_confidence"],
                sources=frozenset(value["sources"]),
                scope=value["scope"],
                origin=None if origin is None else Origin(origin["kind"], origin["ref"]),
            ),
        )

    def list_scope(self, scope: Scope = "default") -> frozenset[MemoryId]:
        """Paged, because ``search`` answers ten items unless asked for more."""
        return frozenset(
            key for key, _ in every_item(self._store, (*RECORDS, scope), page=PAGE)
        )

    # ------------------------------------------------------ what a store cannot answer

    def provenance(self, memory_id: MemoryId, scope: Scope = "default") -> None:
        raise NotProvided("provenance")

    def effective_confidence(self, memory_id: MemoryId, scope: Scope = "default") -> None:
        raise NotProvided("effective_confidence")

    def descendants(self, memory_id: MemoryId, scope: Scope = "default") -> None:
        raise NotProvided("descendants")

    def revise(
        self,
        memory_id: MemoryId,
        new_declared: float,
        reason: str,
        scope: Scope = "default",
    ) -> None:
        raise NotProvided("revise")

    def revisions(self, memory_id: MemoryId, scope: Scope = "default") -> None:
        raise NotProvided("revisions")

    def forget(
        self,
        memory_id: MemoryId,
        scope: Scope = "default",
        mode: ForgetMode | None = None,
    ) -> None:
        raise NotProvided("forget")

    def grant(self, owner: Scope, reader: Scope) -> None:
        raise NotProvided("grant")

    def revoke(self, owner: Scope, reader: Scope) -> None:
        raise NotProvided("revoke")

    def grants(self, owner: Scope) -> None:
        raise NotProvided("grants")
