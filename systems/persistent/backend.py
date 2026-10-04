"""The storage interface the write-through wrapper persists through.

Four operations and one declaration. Deliberately smaller than any real store's API,
because the wrapper is the thing being reused and a backend that had to be clever would
have to be reimplemented for every store it was pointed at.

``items`` returns an iterator and is the only method with a hazard in it: a store whose
listing is paged will answer the first page and stop, and a wrapper that believed it
would rebuild a *shorter* graph than it stored. Nothing above would notice — the records
that came back are self-consistent, every chain is intact, and every effective confidence
along a truncated chain is higher than it should be. That is erasure inflation arriving
through the loader instead of through a forget. So paging is the backend's business: an
implementation of ``items`` yields every item or raises, and never returns a prefix.

``durability`` is the value the wrapper declares in SPEC.md 8's ``durability`` field, so a
backend states its own promise rather than having one assumed for it.
"""

from __future__ import annotations

import json
from typing import Iterator, Protocol

#: One stored item: a JSON object, which is all the wrapper ever puts.
Item = dict[str, object]


class Backend(Protocol):
    """What the wrapper needs from a store. See the module docstring."""

    #: ``in-memory``, ``round-trip`` or ``durable`` (SPEC.md 8).
    durability: str

    def put(self, key: str, value: Item) -> None:
        """Store ``value`` under ``key``, replacing whatever was there."""

    def get(self, key: str) -> Item | None:
        """The item, or ``None`` if the key holds nothing."""

    def delete(self, key: str) -> None:
        """Remove ``key``. Removing a key that holds nothing is not an error."""

    def items(self) -> Iterator[tuple[str, Item]]:
        """Every item. Paging happens inside; a prefix is not an acceptable answer."""


def copied(value: Item) -> Item:
    """``value`` through JSON and back.

    Every backend owes the wrapper this much: an item handed out cannot be reached back
    into the store by mutating it, and an item put in cannot be changed afterwards by its
    caller. A real store gets the property for free by serialising. A dict does not, and a
    dict that skipped it would make the wrapper's tests pass for the wrong reason.
    """
    return json.loads(json.dumps(value))


class MemoryBackend:
    """A dict, with the serialisation a real backend would do anyway.

    Not registered as a system. It exists so the wrapper can be tested without a file,
    and so loading a foreign snapshot has somewhere to go that is not the live store.
    ``round-trip`` rather than ``durable``: the snapshot survives a reopen and nothing
    survives the process, which is exactly what the reference declares.
    """

    durability = "round-trip"

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}

    def put(self, key: str, value: Item) -> None:
        self._items[key] = copied(value)

    def get(self, key: str) -> Item | None:
        found = self._items.get(key)
        return None if found is None else copied(found)

    def delete(self, key: str) -> None:
        self._items.pop(key, None)

    def items(self) -> Iterator[tuple[str, Item]]:
        # One page, because a dict has no reason to have two.
        for key in sorted(self._items):
            yield key, copied(self._items[key])
