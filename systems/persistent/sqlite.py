"""A ``Backend`` over one SQLite table. Standard library only.

Two columns, because the wrapper asked for a key-value store and anything more would be
a schema this file would then have to migrate. The values are canonical JSON — sorted
keys, fixed separators — so two stores holding the same state hold the same bytes, which
is what lets a test diff a database file instead of trusting a reopen.

``items`` pages. Not because a conformance run is large, but because a store whose listing
is paged is the normal case and a loader that works only against an unpaged one is a
loader that silently truncates against a real store. The paging is keyset, not ``OFFSET``:
a cursor over a moving table skips rows, and a loader that skips rows shortens chains.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator

from systems.persistent.backend import Item

#: Rows per page. Small on purpose: a conformance run holds tens of records, and a page
#: size nothing ever exceeds leaves the paging untested.
PAGE = 8

SCHEMA = "CREATE TABLE IF NOT EXISTS items (key TEXT PRIMARY KEY, value TEXT NOT NULL)"

UPSERT = (
    "INSERT INTO items (key, value) VALUES (?, ?) "
    "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
)

PAGE_QUERY = "SELECT key, value FROM items WHERE key > ? ORDER BY key LIMIT ?"


class SQLiteBackend:
    """State in a file, which is what ``durable`` in SPEC.md 8 means."""

    durability = "durable"

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute(SCHEMA)
        self._connection.commit()

    def put(self, key: str, value: Item) -> None:
        self._connection.execute(UPSERT, (key, _dumps(value)))
        self._connection.commit()

    def get(self, key: str) -> Item | None:
        row = self._connection.execute(
            "SELECT value FROM items WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def delete(self, key: str) -> None:
        self._connection.execute("DELETE FROM items WHERE key = ?", (key,))
        self._connection.commit()

    def items(self) -> Iterator[tuple[str, Item]]:
        """Every item, a page at a time, in key order. See the module docstring."""
        after = ""
        while True:
            rows = self._connection.execute(PAGE_QUERY, (after, PAGE)).fetchall()
            if not rows:
                return
            for key, value in rows:
                yield key, json.loads(value)
            after = rows[-1][0]

    def close(self) -> None:
        self._connection.close()


def _dumps(value: Item) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
