"""Persistence as a wrapper: the reference system with a store behind it.

``WriteThrough`` composes the unchanged ``ReferenceSystem`` and writes every mutation
through a four-method backend, so a store gets measured without anybody reimplementing
confidence arithmetic or scope visibility. ``systems/reference/`` is not touched by any of
it; see ``writethrough.py`` for why that is the point rather than a nicety.

One system is registered here, ``sqlite``, and it is registered as an **extra**: the
published matrix is the default run, and adding an adapter to this repository must not be
able to move it. Ask for it by name, or with ``AMR_EXTRAS=1``::

    SYSTEMS=sqlite amr reproduce --out /tmp/sqlite-run
    make extras

With no ``path``, the database is a file in a directory this process made and removes when
it exits — disposable because a conformance run is disposable, and a file rather than
memory because ``durable`` is a claim about a restart and a claim is checked in
``properties/test_persistent_system.py``.
"""

from __future__ import annotations

import atexit
import shutil
import tempfile
from itertools import count
from pathlib import Path

from amr.protocol import ForgetMode
from amr.registry import register
from systems.persistent.backend import Backend, MemoryBackend
from systems.persistent.sqlite import SQLiteBackend
from systems.persistent.writethrough import VERSION, WriteThrough

SQLITE_NAME = "sqlite"

_scratch: Path | None = None
_sequence = count(1)


def _scratch_path() -> Path:
    """A fresh database path in one per-process directory, removed at exit.

    One directory rather than one per instance so that the cleanup is a single hook, and
    a counter rather than a random name so that a failed run leaves files whose order a
    reader can follow.
    """
    global _scratch
    if _scratch is None:
        _scratch = Path(tempfile.mkdtemp(prefix="amr-sqlite-"))
        atexit.register(shutil.rmtree, _scratch, True)
    return _scratch / f"store-{next(_sequence):04d}.sqlite3"


def sqlite_factory(
    default_forget_mode: ForgetMode | None = None, path: Path | str | None = None
) -> WriteThrough:
    """The write-through system over SQLite. ``path`` opens or creates that database."""
    backend = SQLiteBackend(_scratch_path() if path is None else path)
    return WriteThrough(backend, default_forget_mode, name=SQLITE_NAME)


register(SQLITE_NAME, sqlite_factory, default=False)

__all__ = [
    "SQLITE_NAME",
    "VERSION",
    "Backend",
    "MemoryBackend",
    "SQLiteBackend",
    "WriteThrough",
    "sqlite_factory",
]
