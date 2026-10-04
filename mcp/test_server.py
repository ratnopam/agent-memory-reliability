"""Integration test: a real client, a real subprocess, a real stdio transport.

The point of going over the wire rather than calling the tool functions directly is that
everything between the client and ``ReferenceSystem`` is what could be wrong — the schema
generated from the type hints, the JSON round trip, the error translation. Calling the
functions in-process would test none of it.

This test is not part of the conformance suite. ``make test``, ``make reproduce``, and
``make determinism`` do not need the ``mcp`` package; ``make mcp-test`` runs this.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest

mcp = pytest.importorskip("mcp", reason="the mcp package is only needed for mcp/")

SERVER = Path(__file__).resolve().parent / "server.py"
ROOT = SERVER.parent.parent

Call = Callable[..., Awaitable[Any]]


def _attribute(result: Any, *names: str, default: Any = None) -> Any:
    """The first attribute present. The SDK spells these both ways across versions."""
    for name in names:
        value = getattr(result, name, None)
        if value is not None:
            return value
    return default


def payload(result: Any) -> Any:
    """The tool's return value, whichever way this client surfaced it."""
    structured = _attribute(result, "structured_content", "structuredContent")
    if structured is not None:
        return structured.get("result", structured)
    return json.loads(text_of(result))


def text_of(result: Any) -> str:
    blocks = _attribute(result, "content", default=())
    return "".join(getattr(block, "text", "") for block in blocks)


def errored(result: Any) -> bool:
    return bool(_attribute(result, "is_error", "isError", default=False))


def run_session(
    script: Callable[[Call, Call], Awaitable[Any]], *arguments: str
) -> Any:
    """Start the server over stdio, run ``script`` against one session, shut it down.

    ``script`` is given two helpers: ``call`` returns the decoded payload and fails on a
    tool error, ``raw`` returns the result untouched so a test can assert on an error.
    Extra ``arguments`` go to the server process, which is how a bound scope is set.
    """

    async def run() -> Any:
        parameters = mcp.StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER), *arguments],
            cwd=str(ROOT),
        )
        async with mcp.Client(parameters) as client:

            async def raw(name: str, **arguments: Any) -> Any:
                return await client.call_tool(name, arguments)

            async def call(name: str, **arguments: Any) -> Any:
                result = await raw(name, **arguments)
                assert not errored(result), f"{name} failed: {text_of(result)}"
                return payload(result)

            return await script(call, raw)

    return asyncio.run(run())


def test_derivation_over_stdio_bounds_confidence() -> None:
    """Two writes with a derivation, then the arithmetic, over the real transport."""

    async def script(call: Call, _raw: Call) -> None:
        weak = (await call("memory_write", content="a weak observation", declared_confidence=0.4))["id"]
        derived = (
            await call(
                "memory_write",
                content="a confident conclusion",
                declared_confidence=0.9,
                sources=[weak],
            )
        )["id"]

        value = await call("memory_effective_confidence", memory_id=derived)
        assert value["effective_confidence"] == 0.4, "weakest link, not the declared 0.9"

        chain = await call("memory_provenance", memory_id=derived)
        assert chain["root_id"] == derived
        assert chain["ancestor_ids"] == [weak]
        assert chain["nodes"][weak]["declared_confidence"] == 0.4

        read = await call("memory_get", memory_id=derived)
        assert read["outcome"] == "ok"
        assert read["record"]["sources"] == [weak]
        assert read["record"]["declared_confidence"] == 0.9

        assert (await call("memory_descendants", memory_id=weak))["descendants"] == [derived]
        assert sorted((await call("memory_list_scope"))["ids"]) == sorted([weak, derived])

    run_session(script)


def test_unresolvable_source_is_rejected_with_a_coded_error() -> None:
    """The strict write of I1.6 survives translation, with a code a client can branch on."""

    async def script(call: Call, raw: Call) -> None:
        result = await raw(
            "memory_write",
            content="a conclusion citing nothing that exists",
            declared_confidence=0.9,
            sources=["no-such-id"],
        )
        assert errored(result), "an unresolvable source must be rejected"
        assert "unresolved_source" in text_of(result)
        assert (await call("memory_list_scope"))["ids"] == [], "nothing was persisted"

    run_session(script)


def test_revise_lowers_a_descendant_and_is_logged() -> None:
    async def script(call: Call, _raw: Call) -> None:
        root = (await call("memory_write", content="an observation", declared_confidence=0.9))["id"]
        leaf = (
            await call(
                "memory_write",
                content="a conclusion",
                declared_confidence=0.8,
                sources=[root],
            )
        )["id"]
        receipt = await call(
            "memory_revise",
            memory_id=root,
            declared_confidence=0.2,
            reason="the source retracted it",
        )
        assert (receipt["before"], receipt["after"]) == (0.9, 0.2)
        assert (await call("memory_effective_confidence", memory_id=leaf))[
            "effective_confidence"
        ] == 0.2
        history = (await call("memory_revisions", memory_id=root))["revisions"]
        assert [(entry["before"], entry["after"], entry["reason"]) for entry in history] == [
            (0.9, 0.2, "the source retracted it")
        ]

    run_session(script)


def test_forget_receipt_reports_what_it_affected() -> None:
    """Erase shortens the chain, so the receipt has to admit the survivor rose."""

    async def script(call: Call, _raw: Call) -> None:
        weak = (await call("memory_write", content="a weak observation", declared_confidence=0.4))["id"]
        derived = (
            await call(
                "memory_write",
                content="a confident conclusion",
                declared_confidence=0.9,
                sources=[weak],
            )
        )["id"]

        receipt = await call("memory_forget", memory_id=weak, mode="erase")
        assert receipt["mode"] == "erase"
        assert receipt["forgotten"] == [weak]
        assert [delta for delta in receipt["deltas"] if delta["inflated"]] == [
            {"id": derived, "before": 0.4, "after": 0.9, "inflated": True}
        ]
        assert (await call("memory_effective_confidence", memory_id=derived))[
            "effective_confidence"
        ] == 0.9
        assert (await call("memory_get", memory_id=weak))["outcome"] == "forgotten"
        assert (await call("memory_get", memory_id="never-existed"))["outcome"] == "not_found"

    run_session(script)


def test_a_bound_server_refuses_another_scope() -> None:
    """``--scope`` fixes the caller's scope for the connection. See mcp/README.md.

    Unbound, ``scope`` is an argument the server believes, which is the default and is
    stated as the trust model rather than defended. Bound, two things have to hold: a call
    that omits the argument acts in the bound scope, and a call that names a different one
    is refused with the ``scope:`` code instead of being redirected. The refusal is the
    half worth testing — silently writing to ``team-sre`` a record the client asked to put
    in ``other-team`` would be the server deciding something, which is what it does not do.
    """

    async def script(call: Call, raw: Call) -> None:
        written = (
            await call(
                "memory_write", content="a bound write", declared_confidence=0.9
            )
        )["id"]
        listed = await call("memory_list_scope")
        assert listed["scope"] == "team-sre", "omitting scope means the bound scope"
        assert listed["ids"] == [written]

        result = await raw("memory_list_scope", scope="other-team")
        assert errored(result), "a bound server must refuse another scope"
        assert "scope:" in text_of(result), text_of(result)
        assert "team-sre" in text_of(result), "the refusal names the bound scope"

        result = await raw(
            "memory_write",
            content="a write aimed elsewhere",
            declared_confidence=0.9,
            scope="other-team",
        )
        assert errored(result), "the refusal is not read-only"
        assert (await call("memory_list_scope"))["ids"] == [written], "nothing was written"

        # Naming the bound scope explicitly is the same call as omitting it.
        assert (await call("memory_get", memory_id=written, scope="team-sre"))[
            "outcome"
        ] == "ok"

    run_session(script, "--scope", "team-sre")


def test_capabilities_are_reported() -> None:
    async def script(call: Call, _raw: Call) -> None:
        declaration = await call("memory_capabilities")
        assert declaration["system"] == "reference"
        assert declaration["empty_chain_convention"] == 1.0
        assert declaration["default_forget_mode"] == "tombstone"
        assert sorted(declaration["supported_forget_modes"]) == [
            "cascade",
            "erase",
            "tombstone",
        ]

    run_session(script)
