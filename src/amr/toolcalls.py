"""The tool-call layer: one JSON shape in, one call into a system, one JSON shape out.

This is everything ``mcp/server.py`` does apart from speaking MCP. It lives here, and not
there, for one reason: ``amr replay`` has to re-execute a recorded session *through the
same translation the server used*, and a replay that needed the MCP SDK installed in order
to compare two numbers would be a replay nobody runs. Nothing in this module imports
``mcp``, and nothing in it decides anything — no default confidence, no retry on a rejected
write, no collapsing FORGOTTEN into NOT_FOUND. A raised protocol error becomes a
``ToolCallError`` carrying a stable code, and that is the whole of the behaviour.

``mcp/server.py`` keeps the tool signatures, because the SDK generates each tool's schema
from its type hints and a dispatcher with ``**arguments`` would publish no schema at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from amr.protocol import (
    Chain,
    ConfidenceDelta,
    CycleError,
    ForgetMode,
    ForgetReceipt,
    ForgottenRecordError,
    MemorySystem,
    NotFoundError,
    Origin,
    ReadResult,
    Record,
    RevisionReceipt,
    Scope,
    ScopeError,
    UnresolvedSourceError,
)

DEFAULT_SCOPE = "default"

#: The trace format's version. A trace is a file on disk that a later checkout replays, so
#: the shape it was written in is recorded in it rather than assumed.
TRACE_VERSION = 1

#: Protocol errors, mapped to the code a tool error is prefixed with. The prefix is part
#: of the interface: a client can branch on it without parsing English.
ERROR_CODES: tuple[tuple[type[Exception], str], ...] = (
    (CycleError, "cycle"),
    (UnresolvedSourceError, "unresolved_source"),
    (ForgottenRecordError, "forgotten"),
    (ScopeError, "scope"),
    # ``NotFoundError`` is a ``LookupError``; both entries map to one code, because an
    # adapter that raises the bare built-in still conforms (SPEC.md 3.1).
    (NotFoundError, "not_found"),
    (LookupError, "not_found"),
    (ValueError, "invalid_argument"),
)


class ToolCallError(Exception):
    """A refused call, with a code a caller can branch on and a message it can read."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def coded(error: Exception) -> ToolCallError | None:
    """``error`` as a ``ToolCallError``, or None if it is not one of ours — a crash."""
    if isinstance(error, ToolCallError):
        return error
    for exception_type, code in ERROR_CODES:
        if isinstance(error, exception_type):
            return ToolCallError(code, str(error))
    return None


def forget_mode(name: str | None) -> ForgetMode | None:
    if name is None:
        return None
    try:
        return ForgetMode(name)
    except ValueError as error:
        supported = ", ".join(mode.value for mode in ForgetMode)
        raise ToolCallError(
            "invalid_argument", f"unknown forget mode {name!r}; one of {supported}"
        ) from error


def scope_binder(bound_scope: str | None) -> Callable[[str | None], Scope]:
    """Which scope a call acts in, given what the caller asked for.

    Unbound, the caller decides and omitting the argument means ``default``. Bound,
    omitting it means the bound scope and naming a different one is refused rather than
    silently redirected: a client that believes it wrote to ``alpha`` and was quietly given
    ``beta`` has been lied to about where its memory is. The refusal carries the bound
    name, because this is a configuration mismatch — the scope of a connection is not a
    secret from the client connected to it.
    """

    def scoped(requested: str | None) -> Scope:
        if bound_scope is None:
            return requested if requested is not None else DEFAULT_SCOPE
        if requested is not None and requested != bound_scope:
            raise ToolCallError(
                "scope",
                f"this server is bound to scope {bound_scope!r} and cannot act in "
                f"{requested!r}; omit the argument or pass {bound_scope!r}",
            )
        return bound_scope

    return scoped


# ------------------------------------------------------------------ translation


def as_record(record: Record) -> dict[str, Any]:
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


def as_read_result(result: ReadResult) -> dict[str, Any]:
    return {
        "outcome": result.outcome.value,
        "record": None if result.record is None else as_record(result.record),
    }


def as_chain(chain: Chain) -> dict[str, Any]:
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


def as_delta(delta: ConfidenceDelta) -> dict[str, Any]:
    return {
        "id": delta.id,
        "before": delta.before,
        "after": delta.after,
        "inflated": delta.inflated,
    }


def as_revision(receipt: RevisionReceipt) -> dict[str, Any]:
    return {
        "id": receipt.id,
        "before": receipt.before,
        "after": receipt.after,
        "reason": receipt.reason,
        "deltas": [as_delta(delta) for delta in receipt.deltas],
    }


def as_forget_receipt(receipt: ForgetReceipt) -> dict[str, Any]:
    return {
        "mode": receipt.mode.value,
        "forgotten": sorted(receipt.forgotten),
        "tombstoned": sorted(receipt.tombstoned),
        "deltas": [as_delta(delta) for delta in receipt.deltas],
        "affected_scopes": [
            {"id": memory_id, "scope": scope}
            for memory_id, scope in receipt.affected_scopes
        ],
    }


def as_capabilities(system: MemorySystem) -> dict[str, Any]:
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


# --------------------------------------------------------------------- the tools


def _write(
    system: MemorySystem,
    scoped: Callable[[str | None], Scope],
    content: str,
    declared_confidence: float,
    sources: list[str] | None = None,
    scope: str | None = None,
    origin_kind: str | None = None,
    origin_ref: str | None = None,
) -> dict[str, Any]:
    acting = scoped(scope)
    if (origin_kind is None) != (origin_ref is None):
        raise ToolCallError(
            "invalid_argument",
            "origin_kind and origin_ref are given together or not at all",
        )
    origin = None if origin_kind is None else Origin(kind=origin_kind, ref=origin_ref or "")
    return {
        "id": system.write(
            content,
            declared_confidence,
            sources=tuple(sources or ()),
            scope=acting,
            origin=origin,
        )
    }


def _get(system, scoped, memory_id: str, scope: str | None = None) -> dict[str, Any]:
    return as_read_result(system.get(memory_id, scope=scoped(scope)))


def _provenance(system, scoped, memory_id: str, scope: str | None = None) -> dict[str, Any]:
    return as_chain(system.provenance(memory_id, scope=scoped(scope)))


def _effective_confidence(
    system, scoped, memory_id: str, scope: str | None = None
) -> dict[str, Any]:
    value = system.effective_confidence(memory_id, scope=scoped(scope))
    return {"id": memory_id, "effective_confidence": value}


def _descendants(system, scoped, memory_id: str, scope: str | None = None) -> dict[str, Any]:
    found = system.descendants(memory_id, scope=scoped(scope))
    return {"id": memory_id, "descendants": sorted(found)}


def _revise(
    system,
    scoped,
    memory_id: str,
    declared_confidence: float,
    reason: str,
    scope: str | None = None,
) -> dict[str, Any]:
    return as_revision(
        system.revise(memory_id, declared_confidence, reason, scope=scoped(scope))
    )


def _revisions(system, scoped, memory_id: str, scope: str | None = None) -> dict[str, Any]:
    history = system.revisions(memory_id, scope=scoped(scope))
    return {"id": memory_id, "revisions": [as_revision(entry) for entry in history]}


def _forget(
    system, scoped, memory_id: str, scope: str | None = None, mode: str | None = None
) -> dict[str, Any]:
    acting = scoped(scope)
    chosen = forget_mode(mode)
    return as_forget_receipt(system.forget(memory_id, scope=acting, mode=chosen))


def _list_scope(system, scoped, scope: str | None = None) -> dict[str, Any]:
    acting = scoped(scope)
    return {"scope": acting, "ids": sorted(system.list_scope(acting))}


def _capabilities(system, _scoped) -> dict[str, Any]:
    return as_capabilities(system)


#: Tool name to handler. The names are the server's published tool names, because a trace
#: records what a client called and a replay has to find the same handler by that name.
TOOLS: Mapping[str, Callable[..., dict[str, Any]]] = {
    "memory_write": _write,
    "memory_get": _get,
    "memory_provenance": _provenance,
    "memory_effective_confidence": _effective_confidence,
    "memory_descendants": _descendants,
    "memory_revise": _revise,
    "memory_revisions": _revisions,
    "memory_forget": _forget,
    "memory_list_scope": _list_scope,
    "memory_capabilities": _capabilities,
}


def dispatch(
    system: MemorySystem,
    tool: str,
    arguments: Mapping[str, Any],
    scoped: Callable[[str | None], Scope],
) -> dict[str, Any]:
    """Run one tool call. Raises ``ToolCallError`` for anything a caller can fix."""
    handler = TOOLS.get(tool)
    if handler is None:
        known = ", ".join(sorted(TOOLS))
        raise ToolCallError("invalid_argument", f"unknown tool {tool!r}; one of {known}")
    try:
        return handler(system, scoped, **arguments)
    except Exception as error:  # re-raised unless it is one of ours
        translated = coded(error)
        if translated is None:
            raise
        raise translated from error


# ---------------------------------------------------------------------- tracing


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Tracer:
    """One JSON line per tool call, appended to a file.

    No timestamps and no durations. A trace exists to be replayed and compared, and a
    field that cannot be reproduced is a field every replay reports as a difference — the
    same reason ``generated_at`` is the only volatile key in ``results/<date>/raw.json``.

    The first line is a header: the configuration a replay needs in order to build the
    same system the call was made against. Without it a replay would have to guess the
    server's default forget mode, and a guess that happened to be right would make
    ``memory_forget`` with no explicit mode pass for the wrong reason.
    """

    def __init__(
        self, path: Path, *, default_forget_mode: ForgetMode, bound_scope: str | None
    ) -> None:
        self.path = Path(path)
        self._sequence = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            _canonical(
                {
                    "amr_trace": TRACE_VERSION,
                    "bound_scope": bound_scope,
                    "default_forget_mode": default_forget_mode.value,
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def record(
        self,
        tool: str,
        arguments: Mapping[str, Any],
        *,
        result: dict[str, Any] | None = None,
        error: ToolCallError | None = None,
    ) -> None:
        self._sequence += 1
        entry: dict[str, Any] = {
            "seq": self._sequence,
            "tool": tool,
            "arguments": dict(arguments),
        }
        if error is not None:
            entry["error"] = {"code": error.code, "message": error.message}
        else:
            entry["result"] = result
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(entry) + "\n")
