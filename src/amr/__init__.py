"""``amr`` — the conformance machinery: protocol, registry, runner, results, report.

Nothing in this package imports a memory system except ``registry.discover``, which
loads the ``amr.systems`` entry points and the in-tree adapter packages so that they can
register themselves.
"""

__version__ = "0.1.0"
