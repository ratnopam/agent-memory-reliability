"""Executable reproductions for the failure modes in ``taxonomy/``.

Every entry in the taxonomy embeds the source of its module here, and
``properties/test_taxonomy.py`` both runs the reproduction and asserts that the embedded
code is byte-identical to the module. A taxonomy entry therefore cannot drift from the
behaviour it describes.

Each module exposes ``reproduce(system) -> dict``, takes a ``MemorySystem``, and names
any forget mode explicitly rather than relying on the system's configured default.
"""
