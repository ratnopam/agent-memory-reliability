"""Two systems over one long-term store: the store alone, and the store with the layer.

Both are **extras**, measured only when named or when ``AMR_EXTRAS=1`` asks for them, and
both need the ``langgraph`` extra::

    pip install -e ".[langgraph]"
    SYSTEMS=langgraph-store,langgraph-layered python -m amr reproduce --out .amr-runs/pair

The pair is the measurement. ``langgraph-store`` is the store's own five operations with
nothing computed over them, and its FAILs say which questions a document store does not
answer. ``langgraph-layered`` is the same store underneath
``systems/persistent/writethrough.py``, which answers them with the reference's semantics
and the store's storage. Neither imports a model client, and no semantic index is
configured: every ``put`` passes ``index=False``.
"""

from __future__ import annotations

from amr.registry import register
from systems.langgraph_store.layered import StoreBackend, layered_factory
from systems.langgraph_store.naming import VERSION
from systems.langgraph_store.store_alone import NotProvided, StoreAlone

STORE_NAME = "langgraph-store"
LAYERED_NAME = "langgraph-layered"

#: What the registry imports to decide whether these can run at all, and what the error
#: names when they cannot. The module rather than the distribution: an extra is installed
#: or it is not, and ``find_spec`` is the only honest way to ask.
REQUIRES = ("langgraph.store.base",)


def store_factory(default_forget_mode=None, store: object | None = None) -> StoreAlone:
    """The store alone. ``default_forget_mode`` is accepted and has nothing to act on."""
    return StoreAlone(store, name=STORE_NAME)


register(
    STORE_NAME, store_factory, default=False, extra="langgraph", requires=REQUIRES
)
register(
    LAYERED_NAME, layered_factory, default=False, extra="langgraph", requires=REQUIRES
)

__all__ = [
    "LAYERED_NAME",
    "REQUIRES",
    "STORE_NAME",
    "VERSION",
    "NotProvided",
    "StoreAlone",
    "StoreBackend",
    "layered_factory",
    "store_factory",
]
