"""Conformance harness: protocol, registry, runner, results, report.

Nothing in this package imports a memory system except ``registry.discover``, which
imports adapter packages so that they can register themselves.
"""
