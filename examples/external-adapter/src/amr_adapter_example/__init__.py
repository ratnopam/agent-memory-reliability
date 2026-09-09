"""An external adapter, entire. Copy the directory, rename three things, run the suite.

``factory`` is what the ``amr.systems`` entry point in pyproject.toml points at. That is
the whole of the integration: nothing here imports the suite's registry and nothing in the
suite imports this, so a conforming system never needs a patch to
``agent-memory-reliability`` to be measured by it.

The in-tree ``systems/reference`` also calls ``amr.registry.register`` at import time,
because it lives inside the repository and has to be discoverable without being installed.
An external package does not: the entry point is the supported path.
"""

from __future__ import annotations

from amr_adapter_example.adapter import ExampleAdapter
from amr_adapter_example.capabilities import DECLARATION, SYSTEM_NAME, SYSTEM_VERSION

#: The entry-point target. A callable taking ``default_forget_mode`` or nothing.
factory = ExampleAdapter

__all__ = [
    "DECLARATION",
    "SYSTEM_NAME",
    "SYSTEM_VERSION",
    "ExampleAdapter",
    "factory",
]
