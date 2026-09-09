"""An MCP server over a single ``ReferenceSystem``.

The server translates. It does not decide anything: no default confidence, no retry on a
rejected write, no collapsing FORGOTTEN into NOT_FOUND, no reordering of sources so a
write will succeed. Every tool is a JSON shape in, a call into the system, a JSON shape
out, and a raised protocol error turned into a tool error with a stable code prefix. If a
behaviour is arguable, it belongs in ``systems/reference/`` where the conformance suite
can see it, not here where nothing checks it.

State is one in-process ``ReferenceSystem`` for the lifetime of the process, so a client
sees its own writes and nothing survives a restart. ``AMR_FORGET_MODE`` sets the default
forget mode (``tombstone``, ``cascade``, or ``erase``); ``memory_forget`` can override it
per call. ``memory_capabilities`` reports what is in force.

Run it:

    python mcp/server.py                      # stdio
    AMR_FORGET_MODE=erase python mcp/server.py

This directory has no ``__init__.py`` on purpose: a package here named ``mcp`` would
shadow the installed one.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError as AnticipatedToolError  # noqa: E402

from harness.protocol import (  # noqa: E402
    Chain,
    ConfidenceDelta,
    CycleError,
    ForgetMode,
    ForgetReceipt,
    ForgottenRecordError,
    Origin,
    ReadResult,
    Record,
    RevisionReceipt,
    ScopeError,
    UnresolvedSourceError,
)
from systems.reference import ReferenceSystem  # noqa: E402

DEFAULT_SCOPE = "default"

INSTRUCTIONS = """\
Declared provenance for agent memory. Every write may cite the memories it was derived
from; effective confidence is the weakest link along that chain. Cite what you actually
used: an uncited derivation is indistinguishable from an original observation, and the
number will be too high.

A write whose sources do not all resolve is rejected outright, so write ancestors first.
Forgetting has a declared consequence for descendants -- see memory_capabilities.
"""

#: Protocol errors, mapped to the code a tool error is prefixed with. The prefix is part
#: of the interface: a client can branch on it without parsing English.
ERROR_CODES: tuple[tuple[type[Exception], str], ...] = (
    (CycleError, "cycle"),
    (UnresolvedSourceError, "unresolved_source"),
    (ForgottenRecordError, "forgotten"),
    (ScopeError, "scope"),
    (LookupError, "not_found"),
    (ValueError, "invalid_argument"),
)


class ToolError(AnticipatedToolError):
    """A protocol error, in a shape a client can branch on.

    Subclassing the SDK's anticipated-failure type is what puts the message in front of
    the caller. Anything else escaping a tool is a crash, and the SDK withholds its text
    from the client — correct for a bug, wrong for "your write cited an id that does not
    exist", which is information the caller needs in order to fix the call.
    """


def _forget_mode(name: str | None) -> ForgetMode | None:
    if name is None:
        return None
    try:
        return ForgetMode(name)
    except ValueError:
        supported = ", ".join(mode.value for mode in ForgetMode)
        raise ToolError(f"invalid_argument: unknown forget mode {name!r}; one of {supported}")


def _default_mode() -> ForgetMode:
    return _forget_mode(os.environ.get("AMR_FORGET_MODE")) or ForgetMode.TOMBSTONE


# ------------------------------------------------------------------ translation


def _record(record: Record) -> dict[str, Any]:
    return {
        "id": record.id,
        "content": record.content,
        "declared_confidence": record.declared_confidence,
        "sources": sorted(record.sources),
        "scope": record.scope,
        "origin": (
            None
            if record.origin is None
            else {"kind": record.origin.kind, "ref": record.origin.ref}
        ),
    }


def _read_result(result: ReadResult) -> dict[str, Any]:
    return {
        "outcome": result.outcome.value,
        "record": None if result.record is None else _record(result.record),
    }


def _chain(chain: Chain) -> dict[str, Any]:
    return {
        "root_id": chain.root_id,
        "ancestor_ids": sorted(chain.ancestor_ids()),
        "nodes": {
            node.id: {
                "id": node.id,
                "declared_confidence": node.declared_confidence,
                "sources": sorted(node.sources),
                "tombstoned": node.tombstoned,
                "opaque": node.opaque,
            }
            for node in sorted(chain.nodes.values(), key=lambda node: node.id)
        },
    }


def _delta(delta: ConfidenceDelta) -> dict[str, Any]:
    return {
        "id": delta.id,
        "before": delta.before,
        "after": delta.after,
        "inflated": delta.inflated,
    }


def _revision_receipt(receipt: RevisionReceipt) -> dict[str, Any]:
    return {
        "id": receipt.id,
        "before": receipt.before,
        "after": receipt.after,
        "reason": receipt.reason,
        "deltas": [_delta(delta) for delta in receipt.deltas],
    }


def _forget_receipt(receipt: ForgetReceipt) -> dict[str, Any]:
    return {
        "mode": receipt.mode.value,
        "forgotten": sorted(receipt.forgotten),
        "tombstoned": sorted(receipt.tombstoned),
        "deltas": [_delta(delta) for delta in receipt.deltas],
        "affected_scopes": [
            {"id": memory_id, "scope": scope}
            for memory_id, scope in receipt.affected_scopes
        ],
    }


def _capabilities(system: ReferenceSystem) -> dict[str, Any]:
    declaration = system.capabilities()
    return {
        "system": declaration.system,
        "version": declaration.version,
        "supported_forget_modes": sorted(
            mode.value for mode in declaration.supported_forget_modes
        ),
        "default_forget_mode": declaration.default_forget_mode.value,
        "empty_chain_convention": declaration.empty_chain_convention,
        "revision": declaration.revision,
        "revision_raise_supported": declaration.revision_raise_supported,
        "scopes": declaration.scopes,
        "cross_scope_derivation": declaration.cross_scope_derivation,
        "durability": declaration.durability,
        "notes": list(declaration.notes),
    }


def _translated(call):
    """Run ``call``, re-raising a protocol error as a coded ToolError."""
    try:
        return call()
    except ToolError:
        raise
    except Exception as error:
        for exception_type, code in ERROR_CODES:
            if isinstance(error, exception_type):
                raise ToolError(f"{code}: {error}") from error
        raise


# ----------------------------------------------------------------------- server


def build_server(system: ReferenceSystem | None = None) -> MCPServer:
    """The nine operations of SPEC.md 3 as tools, plus the revision reader."""
    memory = system or ReferenceSystem(default_forget_mode=_default_mode())
    server = MCPServer(
        name="agent-memory-reliability",
        version=memory.capabilities().version,
        instructions=INSTRUCTIONS,
    )

    @server.tool(
        description=(
            "Write a memory. Cite every memory this was derived from in sources; a "
            "source id that does not resolve rejects the write and persists nothing."
        )
    )
    def memory_write(
        content: str,
        declared_confidence: float,
        sources: list[str] | None = None,
        scope: str = DEFAULT_SCOPE,
        origin_kind: str | None = None,
        origin_ref: str | None = None,
    ) -> dict[str, Any]:
        if (origin_kind is None) != (origin_ref is None):
            raise ToolError(
                "invalid_argument: origin_kind and origin_ref are given together or "
                "not at all"
            )
        origin = None if origin_kind is None else Origin(kind=origin_kind, ref=origin_ref or "")
        memory_id = _translated(
            lambda: memory.write(
                content,
                declared_confidence,
                sources=tuple(sources or ()),
                scope=scope,
                origin=origin,
            )
        )
        return {"id": memory_id}

    @server.tool(
        description=(
            "Read a memory. outcome is ok, forgotten, or not_found; forgotten and "
            "not_found are different answers and are never collapsed."
        )
    )
    def memory_get(memory_id: str, scope: str = DEFAULT_SCOPE) -> dict[str, Any]:
        return _read_result(_translated(lambda: memory.get(memory_id, scope=scope)))

    @server.tool(
        description=(
            "Walk the full provenance of a memory. Every transitive ancestor appears "
            "exactly once. An ancestor in another scope appears with opaque=true: its "
            "id and declared confidence are visible, its content is not."
        )
    )
    def memory_provenance(memory_id: str, scope: str = DEFAULT_SCOPE) -> dict[str, Any]:
        return _chain(_translated(lambda: memory.provenance(memory_id, scope=scope)))

    @server.tool(
        description=(
            "Effective confidence: the minimum of this memory's declared confidence "
            "and every ancestor's. A memory is no more trustworthy than its weakest "
            "evidence."
        )
    )
    def memory_effective_confidence(
        memory_id: str, scope: str = DEFAULT_SCOPE
    ) -> dict[str, Any]:
        value = _translated(
            lambda: memory.effective_confidence(memory_id, scope=scope)
        )
        return {"id": memory_id, "effective_confidence": value}

    @server.tool(description="Every memory derived from this one, transitively.")
    def memory_descendants(memory_id: str, scope: str = DEFAULT_SCOPE) -> dict[str, Any]:
        found = _translated(lambda: memory.descendants(memory_id, scope=scope))
        return {"id": memory_id, "descendants": sorted(found)}

    @server.tool(
        description=(
            "Change a memory's declared confidence, with a reason. Nothing else about "
            "a memory can change. Lowering propagates to everything derived from it; "
            "raising does not lift a descendant past its own declared value."
        )
    )
    def memory_revise(
        memory_id: str,
        declared_confidence: float,
        reason: str,
        scope: str = DEFAULT_SCOPE,
    ) -> dict[str, Any]:
        return _revision_receipt(
            _translated(
                lambda: memory.revise(memory_id, declared_confidence, reason, scope=scope)
            )
        )

    @server.tool(description="The revision history of a memory, oldest first.")
    def memory_revisions(memory_id: str, scope: str = DEFAULT_SCOPE) -> dict[str, Any]:
        history = _translated(lambda: memory.revisions(memory_id, scope=scope))
        return {
            "id": memory_id,
            "revisions": [_revision_receipt(receipt) for receipt in history],
        }

    @server.tool(
        description=(
            "Forget a memory. mode defaults to the server's declared default: "
            "tombstone erases content and keeps the chain position, cascade removes "
            "descendants too, erase removes the memory and leaves descendants with a "
            "shorter chain. The receipt names every affected memory and every "
            "confidence that moved -- under erase a descendant's confidence can rise."
        )
    )
    def memory_forget(
        memory_id: str, scope: str = DEFAULT_SCOPE, mode: str | None = None
    ) -> dict[str, Any]:
        chosen = _forget_mode(mode)
        return _forget_receipt(
            _translated(lambda: memory.forget(memory_id, scope=scope, mode=chosen))
        )

    @server.tool(
        description=(
            "Every memory native to a scope. A memory shared from another scope is "
            "readable but is not listed here."
        )
    )
    def memory_list_scope(scope: str = DEFAULT_SCOPE) -> dict[str, Any]:
        return {
            "scope": scope,
            "ids": sorted(_translated(lambda: memory.list_scope(scope))),
        }

    @server.tool(
        description=(
            "What this server guarantees: supported forget modes, the default, the "
            "empty-chain convention, revision and scope semantics, durability."
        )
    )
    def memory_capabilities() -> dict[str, Any]:
        return _capabilities(memory)

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
