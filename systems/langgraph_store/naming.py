"""Where things live in the store, and the one loop that must not be written twice.

A long-term store lists with ``search(namespace_prefix, limit=..., offset=...)``, and
**the default limit is ten.** A reload that calls it once gets ten items and no indication
that there were more. Nothing downstream looks broken: the records that came back are
self-consistent, every chain among them is intact, and every effective confidence along a
chain whose weak root did not come back is *higher* than it should be. That is erasure
inflation arriving through the loader instead of through a forget — the same failure
``systems/persistent/backend.py`` describes, reached by a different route.

So the paging lives here, once, and both adapters call it. It reads pages until one comes
back short, which is the only termination condition that does not assume a count.
"""

from __future__ import annotations

from typing import Iterator

VERSION = "0.1.0"

#: The root of everything these adapters write, so a store they share with an application
#: has one prefix to look under and one to ignore.
ROOT = ("amr",)

#: One namespace per scope under here: ``("amr", "records", "<scope>")``, with the record
#: id as the key. Visibility is then the store's own boundary rather than a field.
RECORDS = (*ROOT, "records")

#: The wrapper's bookkeeping — counter, scopes, grants, forgotten ids — in its own
#: namespace, so a reader looking at a scope sees records and nothing else.
META = (*ROOT, "meta")

#: Items per page. Smaller than any conformance run, because a page size nothing exceeds
#: leaves the paging untested, and the store's own default is smaller still.
PAGE = 5


def every_item(
    store: object, namespace: tuple[str, ...], page: int = PAGE
) -> Iterator[tuple[str, dict]]:
    """Every key and value under ``namespace``, a page at a time, or nothing.

    Offset paging is what the store offers. It is sound here because a reload reads a
    store nothing else is writing to; against a moving store an offset cursor skips rows,
    and a loader that skips rows shortens chains. A backend over a store that can move
    under a reader owes its loader a snapshot or a keyset cursor.
    """
    offset = 0
    while True:
        found = store.search(namespace, limit=page, offset=offset)
        for item in found:
            yield item.key, dict(item.value)
        if len(found) < page:
            return
        offset += page


def every_namespace(store: object, prefix: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every namespace under ``prefix``, paged the same way for the same reason."""
    found: list[tuple[str, ...]] = []
    while True:
        page = store.list_namespaces(prefix=prefix, limit=PAGE, offset=len(found))
        found.extend(page)
        if len(page) < PAGE:
            return found
