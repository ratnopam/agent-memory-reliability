"""An MCP server over a single ``ReferenceSystem``.

The server translates, and the translation is ``amr.toolcalls`` — this file is the MCP
half and nothing else. It does not decide anything: no default confidence, no retry on a
rejected write, no collapsing FORGOTTEN into NOT_FOUND, no reordering of sources so a
write will succeed. Every tool is a JSON shape in, a call into the system, a JSON shape
out, and a raised protocol error turned into a tool error with a stable code prefix. If a
behaviour is arguable, it belongs in ``systems/reference/`` where the conformance suite
can see it, not here where nothing checks it.

The tool signatures stay written out, rather than becoming one dispatcher taking
``**arguments``, because the SDK generates each tool's schema from its type hints and a
dispatcher publishes no schema at all. Each body is one call into ``amr.toolcalls``.

State is one in-process ``ReferenceSystem`` for the lifetime of the process, so a client
sees its own writes and nothing survives a restart. ``AMR_FORGET_MODE`` sets the default
forget mode (``tombstone``, ``cascade``, or ``erase``); ``memory_forget`` can override it
per call. ``memory_capabilities`` reports what is in force.

**Who the caller is.** By default, nobody: ``scope`` is an ordinary tool argument and the
server believes it. One process, one store, and a client that may name any scope it likes,
which means scope here is a *namespace* and not a boundary — SPEC.md 7's isolation is a
property of the system under test, and this server does not add an identity to it. Start
it with ``--scope NAME`` (or ``AMR_MCP_SCOPE``) to bind the connection to one scope: the
argument then defaults to that scope and a call naming a different one is refused with
``scope:``. That is the whole of the trust model; mcp/README.md says it in prose.

**Tracing.** ``--trace FILE`` (or ``AMR_MCP_TRACE``) appends one JSON line per tool call:
sequence number, tool, arguments, and the result or the error code. ``amr replay FILE``
re-executes those calls against a fresh system through this same translation and reports
any value that came back different. A trace contains whatever was written through it, so
it is a transcript of your memories and not a log of their shapes.

Run it:

    python mcp/server.py                      # stdio, scope is the caller's to choose
    python mcp/server.py --scope team-sre     # stdio, bound to one scope
    python mcp/server.py --trace run.jsonl    # stdio, recording every call
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
for _path in (_ROOT, _ROOT / "src"):
    # Works from a checkout with nothing installed but the mcp package; an editable
    # install of this project makes both entries redundant rather than wrong.
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import (  # noqa: E402
    ToolError as AnticipatedToolError,
)

from amr import toolcalls  # noqa: E402
from amr.protocol import ForgetMode  # noqa: E402
from amr.toolcalls import ToolCallError, Tracer  # noqa: E402
from systems.reference import ReferenceSystem  # noqa: E402

INSTRUCTIONS = """\
Declared provenance for agent memory. Every write may cite the memories it was derived
from; effective confidence is the weakest link along that chain. Cite what you actually
used: an uncited derivation is indistinguishable from an original observation, and the
number will be too high.

A write whose sources do not all resolve is rejected outright, so write ancestors first.
Forgetting has a declared consequence for descendants -- see memory_capabilities.

scope names a namespace, not an identity: this server does not authenticate you. If it was
started bound to one scope, omit the argument -- naming another scope is refused.
"""

#: The codes a tool error is prefixed with. Defined once, in ``amr.toolcalls``, so the
#: replay that compares against a recorded code reads the same table the server wrote it
#: from. Re-exported because ``mcp/README.md`` documents it as part of this interface.
ERROR_CODES = toolcalls.ERROR_CODES


class ToolError(AnticipatedToolError):
    """A protocol error, in a shape a client can branch on.

    Subclassing the SDK's anticipated-failure type is what puts the message in front of
    the caller. Anything else escaping a tool is a crash, and the SDK withholds its text
    from the client — correct for a bug, wrong for "your write cited an id that does not
    exist", which is information the caller needs in order to fix the call.
    """


def _default_mode() -> ForgetMode:
    return toolcalls.forget_mode(os.environ.get("AMR_FORGET_MODE")) or ForgetMode.TOMBSTONE


def _option(name: str, variable: str, argv: list[str] | None = None) -> str | None:
    """``--name VALUE``, else ``--name=VALUE``, else the environment, else None."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    flag = f"--{name}"
    if flag in arguments:
        index = arguments.index(flag)
        if index + 1 >= len(arguments):
            raise SystemExit(f"{flag} takes a value")
        return arguments[index + 1]
    for argument in arguments:
        if argument.startswith(f"{flag}="):
            return argument.partition("=")[2]
    value = os.environ.get(variable, "").strip()
    return value or None


def _bound_scope(argv: list[str] | None = None) -> str | None:
    """``--scope NAME``, else ``AMR_MCP_SCOPE``, else unbound. See the module docstring."""
    return _option("scope", "AMR_MCP_SCOPE", argv)


def _trace_path(argv: list[str] | None = None) -> Path | None:
    """``--trace FILE``, else ``AMR_MCP_TRACE``, else no trace."""
    value = _option("trace", "AMR_MCP_TRACE", argv)
    return None if value is None else Path(value)


# ----------------------------------------------------------------------- server


def build_server(
    system: ReferenceSystem | None = None,
    bound_scope: str | None = None,
    trace: Path | None = None,
) -> MCPServer:
    """The nine record operations of SPEC.md 3 as tools, plus ``memory_capabilities``.

    Not the other three. ``grant``, ``revoke``, and ``grants`` administer who may read
    across a scope boundary, and a client that can widen its own visibility is not
    isolated by anything (SPEC.md 7). Grants are configuration, set by whoever runs the
    server; there is no tool for them on purpose.

    ``bound_scope`` fixes the caller's scope for the connection. Unbound — the default —
    ``scope`` is an argument like any other and the server believes whatever it is told.
    ``trace`` appends every call to a file that ``amr replay`` can re-execute.
    """
    memory = system or ReferenceSystem(default_forget_mode=_default_mode())
    scoped = toolcalls.scope_binder(bound_scope)
    tracer = (
        None
        if trace is None
        else Tracer(
            trace,
            default_forget_mode=memory.capabilities().default_forget_mode,
            bound_scope=bound_scope,
        )
    )

    def call(tool: str, **arguments: Any) -> dict[str, Any]:
        """One tool call, translated, recorded, and refused with a code if it must be.

        The arguments recorded are the ones the client sent — including the ``scope`` it
        omitted, as an absent key — because that is what a replay has to re-send. What the
        binding resolved them to is reconstructed from the trace's header, not stored per
        call, so a trace cannot disagree with itself about which scope a session was in.
        """
        given = {name: value for name, value in arguments.items() if value is not None}
        try:
            result = toolcalls.dispatch(memory, tool, given, scoped)
        except ToolCallError as error:
            if tracer is not None:
                tracer.record(tool, given, error=error)
            raise ToolError(str(error)) from error
        if tracer is not None:
            tracer.record(tool, given, result=result)
        return result

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
        scope: str | None = None,
        origin_kind: str | None = None,
        origin_ref: str | None = None,
    ) -> dict[str, Any]:
        return call(
            "memory_write",
            content=content,
            declared_confidence=declared_confidence,
            sources=sources,
            scope=scope,
            origin_kind=origin_kind,
            origin_ref=origin_ref,
        )

    @server.tool(
        description=(
            "Read a memory. outcome is ok, forgotten, or not_found; forgotten and "
            "not_found are different answers and are never collapsed."
        )
    )
    def memory_get(memory_id: str, scope: str | None = None) -> dict[str, Any]:
        return call("memory_get", memory_id=memory_id, scope=scope)

    @server.tool(
        description=(
            "Walk the full provenance of a memory. Every transitive ancestor appears "
            "exactly once. An ancestor in another scope appears with opaque=true: its "
            "id and declared confidence are visible, its content is not."
        )
    )
    def memory_provenance(memory_id: str, scope: str | None = None) -> dict[str, Any]:
        return call("memory_provenance", memory_id=memory_id, scope=scope)

    @server.tool(
        description=(
            "Effective confidence: the minimum of this memory's declared confidence "
            "and every ancestor's. A memory is no more trustworthy than its weakest "
            "evidence."
        )
    )
    def memory_effective_confidence(
        memory_id: str, scope: str | None = None
    ) -> dict[str, Any]:
        return call("memory_effective_confidence", memory_id=memory_id, scope=scope)

    @server.tool(description="Every memory derived from this one, transitively.")
    def memory_descendants(memory_id: str, scope: str | None = None) -> dict[str, Any]:
        return call("memory_descendants", memory_id=memory_id, scope=scope)

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
        scope: str | None = None,
    ) -> dict[str, Any]:
        return call(
            "memory_revise",
            memory_id=memory_id,
            declared_confidence=declared_confidence,
            reason=reason,
            scope=scope,
        )

    @server.tool(description="The revision history of a memory, oldest first.")
    def memory_revisions(memory_id: str, scope: str | None = None) -> dict[str, Any]:
        return call("memory_revisions", memory_id=memory_id, scope=scope)

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
        memory_id: str, scope: str | None = None, mode: str | None = None
    ) -> dict[str, Any]:
        return call("memory_forget", memory_id=memory_id, scope=scope, mode=mode)

    @server.tool(
        description=(
            "Every memory native to a scope. A memory shared from another scope is "
            "readable but is not listed here."
        )
    )
    def memory_list_scope(scope: str | None = None) -> dict[str, Any]:
        return call("memory_list_scope", scope=scope)

    @server.tool(
        description=(
            "What this server guarantees: supported forget modes, the default, the "
            "empty-chain convention, revision and scope semantics, durability."
        )
    )
    def memory_capabilities() -> dict[str, Any]:
        return call("memory_capabilities")

    return server


def main() -> None:
    build_server(bound_scope=_bound_scope(), trace=_trace_path()).run(transport="stdio")


if __name__ == "__main__":
    main()
