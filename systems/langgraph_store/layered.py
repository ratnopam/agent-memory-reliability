"""The same store, with the reference's semantics on top.

``systems/persistent/writethrough.py`` is the layer: the unchanged reference system,
persisting every mutation through four methods. This file is those four methods over a
long-term store, and that is the whole of the difference between the failing column in
``store_alone.py`` and a column that passes everything.

The mapping is the one a reader of the store would want to find:

* a record goes to ``("amr", "records", "<scope>")`` under its own id, so a scope is a
  namespace and visibility is the store's boundary rather than a field to filter on;
* the wrapper's bookkeeping goes to ``("amr", "meta")``, so a scope's namespace holds
  records and nothing else;
* values are the plain JSON the reference already produces for its snapshot — readable in
  the store with no decoding step, which is the difference between a store somebody can
  audit and a store holding one opaque blob.

Nothing is indexed. ``put`` passes ``index=False``, so no semantic index is configured and
no embedding is ever computed over a memory's content: this measures storage, and an
embedding model in the measured path would be a model in the measured path.
"""

from __future__ import annotations

from typing import Iterator

from systems.langgraph_store.naming import (
    META,
    RECORDS,
    VERSION,
    every_item,
    every_namespace,
)
from systems.persistent.backend import Item
from systems.persistent.writethrough import RECORD_PREFIX, WriteThrough

#: The reference's snapshot keys are flat — ``record/<id>`` and ``meta/<name>`` — and the
#: store's are a namespace and a key. This is the translation, in both directions.
META_PREFIX = "meta/"


class StoreBackend:
    """A ``systems.persistent`` backend over a long-term store.

    ``round-trip`` rather than ``durable``: an in-memory store survives a reopen in this
    process and nothing survives the process, which is exactly what the reference
    declares. Point this at a store that writes to a database and the honest declaration
    changes with it — which is why ``durability`` is a constructor argument and not a
    constant.
    """

    def __init__(self, store: object | None = None, durability: str = "round-trip") -> None:
        if store is None:
            from langgraph.store.memory import InMemoryStore

            store = InMemoryStore()
        self._store = store
        self.durability = durability

    # ------------------------------------------------------------------ the mapping

    def _address(self, key: str, value: Item | None = None) -> tuple[tuple[str, ...], str]:
        """A flat snapshot key as a namespace and a store key.

        A record's namespace is its scope, which is in the record. On the way back in
        (``put``) the value says which scope that is; on a ``get`` or a ``delete`` there
        is no value to ask, so the namespaces are searched. Keeping an index of
        id-to-scope here instead would be a second copy of something the store already
        holds, and a copy that can go stale is how a delete misses.
        """
        if key.startswith(META_PREFIX):
            return META, key[len(META_PREFIX) :]
        record_id = key[len(RECORD_PREFIX) :]
        if value is not None:
            return (*RECORDS, str(value["scope"])), record_id
        for namespace in every_namespace(self._store, RECORDS):
            if self._store.get(namespace, record_id) is not None:
                return namespace, record_id
        return (*RECORDS, "default"), record_id

    @staticmethod
    def _flat(namespace: tuple[str, ...], key: str) -> str:
        return (
            f"{META_PREFIX}{key}"
            if namespace == META
            else f"{RECORD_PREFIX}{key}"
        )

    # ----------------------------------------------------------------- the four calls

    def put(self, key: str, value: Item) -> None:
        namespace, store_key = self._address(key, value)
        self._store.put(namespace, store_key, value, index=False)

    def get(self, key: str) -> Item | None:
        namespace, store_key = self._address(key)
        item = self._store.get(namespace, store_key)
        return None if item is None else dict(item.value)

    def delete(self, key: str) -> None:
        namespace, store_key = self._address(key)
        self._store.delete(namespace, store_key)

    def items(self) -> Iterator[tuple[str, Item]]:
        """Every item under every namespace, paged. See ``naming.every_item``."""
        for namespace in [META, *every_namespace(self._store, RECORDS)]:
            for key, value in every_item(self._store, namespace):
                yield self._flat(namespace, key), value


def layered_factory(default_forget_mode=None, store: object | None = None) -> WriteThrough:
    """The store with the layer over it, registered as ``langgraph-layered``."""
    return WriteThrough(
        StoreBackend(store), default_forget_mode, name="langgraph-layered"
    )


__all__ = ["VERSION", "StoreBackend", "layered_factory"]
