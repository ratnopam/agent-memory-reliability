"""Every "Expect" line of ``docs/try-it-with-claude.md``, against a real server.

The document tells an operator what to expect from numbers a language model will read
back to them. Nothing about Claude Desktop can be asserted here. Everything the document
claims about the *server* can be, and that half is the half that rots: a field dropped
from a receipt, a renamed outcome, an id sequence that starts somewhere else — and the
document goes on telling a stranger to expect a value no build produces. A reader who
finds a mismatch is told, in section 6, that it is a finding worth an issue. That promise
is only honest if the expected values are checked by something.

So the acts run here over the real stdio transport, in the real order, with the document's
own contents and confidences. In-process calls would test none of what the document's
reader goes through.

Acts 0-4 and 6 also run against a scope-bound server: every scripted act names one scope,
so a build started with ``--scope demo`` has to produce the same values. Acts 5 and 7 run
unbound only — act 7 writes to a second scope, which a bound server refuses by design, and
the document says so.

The unbound run also writes ``examples/traces/scripted-demo.jsonl`` and compares it with
what is committed, which makes that trace a gate rather than an artifact nobody reads.
``AMR_UPDATE_TRACE=1`` rewrites it, for a change to the script that is meant.

``make mcp-test`` runs this. The conformance suite does not need it or the ``mcp`` package.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp", reason="the mcp package is only needed for mcp/")

from test_server import Call, errored, run_session, text_of

ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "examples" / "traces" / "scripted-demo.jsonl"
DOCUMENT = ROOT / "docs" / "try-it-with-claude.md"

#: The document's section 2 rule: one scope for the whole script.
DEMO = "demo"

Ids = dict[str, str]


async def _write(
    call: Call, content: str, confidence: float, sources: list[str] | None = None
) -> str:
    arguments: dict[str, Any] = {
        "content": content,
        "declared_confidence": confidence,
        "scope": DEMO,
    }
    if sources is not None:
        arguments["sources"] = sources
    return str((await call("memory_write", **arguments))["id"])


async def _effective(call: Call, memory_id: str) -> float:
    result = await call("memory_effective_confidence", memory_id=memory_id, scope=DEMO)
    return float(result["effective_confidence"])


# --------------------------------------------------------------------------- the acts


async def act_0_what_the_system_declares(call: Call) -> None:
    """
    Expect: forget modes `cascade`, `erase`, `tombstone`; default `tombstone`; empty
    chain `1.0`; revision `logged`; durability `round-trip`. The capabilities tool is
    the one tool that takes no scope, so rule 2 does not apply to it.
    """
    declaration = await call("memory_capabilities")
    assert declaration["supported_forget_modes"] == ["cascade", "erase", "tombstone"]
    assert declaration["default_forget_mode"] == "tombstone"
    assert declaration["empty_chain_convention"] == 1.0
    assert declaration["revision"] == "logged"
    assert declaration["durability"] == "round-trip"


async def act_1_confidence_cannot_outscore_its_weakest_source(
    call: Call, ids: Ids
) -> None:
    """
    Expect: ids `m001`, `m002`, `m003`. Effective for `c` is **0.40** (declared 0.95).
    The provenance walk lists `m001` and `m002` as ancestors, and carries each node's
    declared confidence — which is where the declared 0.95 comes from, so step 2 needs
    no third call.
    """
    ids["a"] = await _write(
        call,
        "Incident report: checkout latency degraded after the 14:05 deploy",
        0.90,
    )
    ids["b"] = await _write(
        call, "Oncall note: probably the memory leak again", 0.40, [ids["a"]]
    )
    ids["c"] = await _write(
        call,
        "Agent summary: root cause confirmed as a memory leak",
        0.95,
        [ids["b"]],
    )
    assert [ids["a"], ids["b"], ids["c"]] == ["m001", "m002", "m003"]

    assert await _effective(call, ids["c"]) == 0.40
    chain = await call("memory_provenance", memory_id=ids["c"], scope=DEMO)
    assert chain["root_id"] == ids["c"]
    assert chain["ancestor_ids"] == [ids["a"], ids["b"]]
    # The document asks for "declared vs effective for c" from these two calls alone, so
    # the declared value has to be reachable without a third: the walk carries it.
    assert chain["nodes"][ids["c"]]["declared_confidence"] == 0.95


async def act_2_revise_a_source_and_everything_below_it_moves(
    call: Call, ids: Ids
) -> None:
    """
    Expect: receipt before 0.90, after 0.20, with `m002` and `m003` each moving 0.40 →
    0.20. Effective for `b` and `c` is **0.20**. History shows one entry, with the
    reason and with no deltas of its own: the log records what was revised, and the
    deltas were in the live receipt.
    """
    receipt = await call(
        "memory_revise",
        memory_id=ids["a"],
        declared_confidence=0.20,
        reason="runbook entry retracted",
        scope=DEMO,
    )
    assert (receipt["before"], receipt["after"]) == (0.90, 0.20)
    assert receipt["deltas"] == [
        {"id": ids["b"], "before": 0.40, "after": 0.20, "inflated": False},
        {"id": ids["c"], "before": 0.40, "after": 0.20, "inflated": False},
    ]

    assert await _effective(call, ids["b"]) == 0.20
    assert await _effective(call, ids["c"]) == 0.20

    history = (await call("memory_revisions", memory_id=ids["a"], scope=DEMO))[
        "revisions"
    ]
    assert len(history) == 1
    assert (history[0]["before"], history[0]["after"]) == (0.90, 0.20)
    assert history[0]["reason"] == "runbook entry retracted"
    # The log records what was revised, not what the revision moved: the deltas were in
    # the live receipt and the history entry does not repeat them.
    assert history[0]["deltas"] == []


async def act_3_forget_mode_tombstone(call: Call, ids: Ids) -> None:
    """
    Expect: ids `m004`–`m006`. Step 7: **0.40**. Receipt: mode tombstone, `m005` under
    both `forgotten` and `tombstoned`, `m006` delta 0.40 → 0.40. `get e` reports
    **forgotten** (not "not found") with a null record. Effective for `f` stays
    **0.40**, and the walk still passes through `m005`, now marked `tombstoned`.
    """
    ids["d"] = await _write(call, "Runbook: p99 checkout SLO is 250 ms", 0.90)
    ids["e"] = await _write(
        call, "Customer chat paraphrase: the SLO is about 400 ms", 0.40, [ids["d"]]
    )
    ids["f"] = await _write(
        call, "Agent plan: raise the memory limit to 4Gi", 0.95, [ids["e"]]
    )
    assert [ids["d"], ids["e"], ids["f"]] == ["m004", "m005", "m006"]

    assert await _effective(call, ids["f"]) == 0.40

    receipt = await call(
        "memory_forget", memory_id=ids["e"], mode="tombstone", scope=DEMO
    )
    assert receipt["mode"] == "tombstone"
    assert receipt["forgotten"] == [ids["e"]]
    assert receipt["tombstoned"] == [ids["e"]]
    assert receipt["deltas"] == [
        {"id": ids["f"], "before": 0.40, "after": 0.40, "inflated": False}
    ]
    assert receipt["affected_scopes"] == [
        {"id": ids["e"], "scope": DEMO},
        {"id": ids["f"], "scope": DEMO},
    ]

    read = await call("memory_get", memory_id=ids["e"], scope=DEMO)
    assert read == {"outcome": "forgotten", "record": None}

    assert await _effective(call, ids["f"]) == 0.40
    chain = await call("memory_provenance", memory_id=ids["f"], scope=DEMO)
    assert ids["e"] in chain["ancestor_ids"]
    assert chain["nodes"][ids["e"]]["tombstoned"] is True


async def act_4_forget_mode_erase_the_finding(call: Call, ids: Ids) -> None:
    """
    Expect: ids `m007`–`m009`. Step 11: 0.40. Receipt: mode erase, `tombstoned` empty,
    `m009` delta **0.40 → 0.95** flagged `inflated`. `get h` reports forgotten.
    Effective for `i` is **0.95**, and its provenance chain is empty. The step 14
    table reads: `f` 0.95 / 0.40 / 0.40 / tombstone; `i` 0.95 / 0.40 / **0.95** /
    erase.
    """
    ids["g"] = await _write(call, "Runbook: p99 checkout SLO is 250 ms", 0.90)
    ids["h"] = await _write(
        call, "Customer chat paraphrase: the SLO is about 400 ms", 0.40, [ids["g"]]
    )
    ids["i"] = await _write(
        call, "Agent plan: raise the memory limit to 4Gi", 0.95, [ids["h"]]
    )
    assert [ids["g"], ids["h"], ids["i"]] == ["m007", "m008", "m009"]

    before = await _effective(call, ids["i"])
    assert before == 0.40

    receipt = await call("memory_forget", memory_id=ids["h"], mode="erase", scope=DEMO)
    assert receipt["mode"] == "erase"
    assert receipt["forgotten"] == [ids["h"]]
    assert receipt["tombstoned"] == [], "erase leaves no marker; that is the finding"
    assert receipt["deltas"] == [
        {"id": ids["i"], "before": 0.40, "after": 0.95, "inflated": True}
    ]

    assert (await call("memory_get", memory_id=ids["h"], scope=DEMO))[
        "outcome"
    ] == "forgotten"
    after = await _effective(call, ids["i"])
    assert after == 0.95

    chain = await call("memory_provenance", memory_id=ids["i"], scope=DEMO)
    assert chain["ancestor_ids"] == []
    assert list(chain["nodes"]) == [ids["i"]]

    # Step 14's table, which is the act's whole point: one declared confidence, one
    # effective confidence before, and two different answers after.
    assert (0.95, 0.40, await _effective(call, ids["f"]), "tombstone") == (
        0.95,
        0.40,
        0.40,
        "tombstone",
    )
    assert (0.95, before, after, "erase") == (0.95, 0.40, 0.95, "erase")


async def act_5_forget_mode_cascade(call: Call, ids: Ids) -> None:
    """
    Expect: ids `m010`–`m012`. Both `m011` and `m012` under `forgotten`, and no deltas
    — cascade forgot the descendant rather than re-bounding it. `get l` reports
    forgotten; `j` survives.
    """
    ids["j"] = await _write(call, "Runbook: rollout window is Tuesday", 0.90)
    ids["k"] = await _write(
        call, "Chat paraphrase: maybe Wednesday", 0.40, [ids["j"]]
    )
    ids["l"] = await _write(
        call, "Agent plan: schedule the rollout", 0.95, [ids["k"]]
    )
    assert [ids["j"], ids["k"], ids["l"]] == ["m010", "m011", "m012"]

    receipt = await call(
        "memory_forget", memory_id=ids["k"], mode="cascade", scope=DEMO
    )
    assert receipt["mode"] == "cascade"
    assert receipt["forgotten"] == [ids["k"], ids["l"]]
    # Nothing is left to move: cascade forgot the descendant instead of re-bounding it.
    assert receipt["deltas"] == []

    assert (await call("memory_get", memory_id=ids["l"], scope=DEMO))[
        "outcome"
    ] == "forgotten"
    assert (await call("memory_get", memory_id=ids["j"], scope=DEMO))["outcome"] == "ok"


async def act_6_a_mistyped_source_is_rejected(call: Call, raw: Call) -> None:
    """
    Expect: the error reads `unresolved_source: source 'm999' does not resolve in
    scope 'demo'`; the two lists are identical. The code before the colon is what a
    client branches on.
    """
    before = await call("memory_list_scope", scope=DEMO)
    assert before["ids"], "the act compares two non-empty listings"

    result = await raw(
        "memory_write",
        content="Summary of the incident",
        declared_confidence=0.80,
        sources=["m999"],
        scope=DEMO,
    )
    assert errored(result)
    message = text_of(result)
    assert "unresolved_source" in message
    assert "m999" in message and DEMO in message

    assert await call("memory_list_scope", scope=DEMO) == before


async def act_7_another_scope_cannot_see_it(call: Call, ids: Ids) -> None:
    """
    Expect: id `m013` for the write. Both reads from `ops` return exactly `{"outcome":
    "not_found", "record": null}` — nothing tells apart a record that is there and
    hidden from one that never existed. **This act needs an unbound server.** If yours
    was started with `--scope` or `AMR_MCP_SCOPE`, the write to `hr` is refused with
    the `scope:` code instead, which is the binding working; skip the act.
    """
    ids["hr"] = str(
        (
            await call(
                "memory_write",
                content="Employee on leave through Friday",
                declared_confidence=0.90,
                scope="hr",
            )
        )["id"]
    )
    assert ids["hr"] == "m013"

    hidden = await call("memory_get", memory_id=ids["hr"], scope="ops")
    absent = await call("memory_get", memory_id="m999", scope="ops")
    assert hidden == {"outcome": "not_found", "record": None}
    assert hidden == absent, "a scope boundary is not a different error"

    # It is there for whoever may see it. Otherwise the two results above would agree for
    # the uninteresting reason that the write never landed.
    assert (await call("memory_get", memory_id=ids["hr"], scope="hr"))["outcome"] == "ok"


#: The acts in the document's order. Each one's docstring is its "Expect" paragraph from
#: ``docs/try-it-with-claude.md``, copied rather than paraphrased, so that the test below
#: can hold the two to each other.
ACTS = (
    act_0_what_the_system_declares,
    act_1_confidence_cannot_outscore_its_weakest_source,
    act_2_revise_a_source_and_everything_below_it_moves,
    act_3_forget_mode_tombstone,
    act_4_forget_mode_erase_the_finding,
    act_5_forget_mode_cascade,
    act_6_a_mistyped_source_is_rejected,
    act_7_another_scope_cannot_see_it,
)


def _collapsed(text: str) -> str:
    """Whitespace is where a document and a docstring are allowed to differ."""
    return " ".join(text.split())


# -------------------------------------------------------------------------- the tests


def test_every_expectation_in_the_document_is_the_one_asserted_here() -> None:
    """The acts below assert values; this asserts they are the document's values.

    Without it the two can drift in the direction that matters: the server keeps doing
    what the acts assert while the document goes on promising a stranger something else,
    and every test in this file stays green. So each act's docstring has to appear in
    ``docs/try-it-with-claude.md`` verbatim, up to line wrapping, and the document must
    not have an expectation no act covers.
    """
    document = DOCUMENT.read_text(encoding="utf-8")
    collapsed = _collapsed(document)

    missing = [
        act.__name__ for act in ACTS if _collapsed(act.__doc__ or "") not in collapsed
    ]
    assert missing == [], (
        f"{missing} assert expectations the document does not state in those words. "
        "Correct whichever of the two is wrong — if it is the server that moved, the "
        "document is the thing to fix (section 6)."
    )

    stated = [line for line in document.splitlines() if line.startswith("Expect:")]
    assert len(stated) == len(ACTS), (
        f"the document states {len(stated)} expectations and this file covers {len(ACTS)}"
    )


def test_the_scripted_acts_hold_against_a_real_server(tmp_path: Path) -> None:
    """The document end to end, unbound, with the trace it leaves behind."""
    written = tmp_path / "scripted-demo.jsonl"

    async def script(call: Call, raw: Call) -> None:
        ids: Ids = {}
        await act_0_what_the_system_declares(call)
        await act_1_confidence_cannot_outscore_its_weakest_source(call, ids)
        await act_2_revise_a_source_and_everything_below_it_moves(call, ids)
        await act_3_forget_mode_tombstone(call, ids)
        await act_4_forget_mode_erase_the_finding(call, ids)
        await act_5_forget_mode_cascade(call, ids)
        await act_6_a_mistyped_source_is_rejected(call, raw)
        await act_7_another_scope_cannot_see_it(call, ids)

    run_session(script, "--trace", str(written))

    recorded = written.read_text(encoding="utf-8")
    if os.environ.get("AMR_UPDATE_TRACE") == "1":  # pragma: no cover - a deliberate edit
        TRACE.parent.mkdir(parents=True, exist_ok=True)
        TRACE.write_text(recorded, encoding="utf-8")
    assert recorded == TRACE.read_text(encoding="utf-8"), (
        f"the session no longer records what {TRACE.name} holds. If the change is "
        "intended, rerun with AMR_UPDATE_TRACE=1 and commit the trace."
    )


def test_the_scripted_acts_hold_on_a_scope_bound_server() -> None:
    """Acts 0-4 and 6 again, with the scope fixed by the operator instead of the caller.

    The document's script names one scope throughout, so binding that scope must change
    nothing it claims. Acts 5 and 7 are left out for the reason the document gives: act 7
    writes to a second scope, and a bound server is supposed to refuse.
    """

    async def script(call: Call, raw: Call) -> None:
        ids: Ids = {}
        await act_0_what_the_system_declares(call)
        await act_1_confidence_cannot_outscore_its_weakest_source(call, ids)
        await act_2_revise_a_source_and_everything_below_it_moves(call, ids)
        await act_3_forget_mode_tombstone(call, ids)
        await act_4_forget_mode_erase_the_finding(call, ids)
        await act_6_a_mistyped_source_is_rejected(call, raw)

        result = await raw(
            "memory_write",
            content="Employee on leave through Friday",
            declared_confidence=0.90,
            scope="hr",
        )
        assert errored(result), "act 7 needs an unbound server, as the document says"
        assert "scope:" in text_of(result)

    run_session(script, "--scope", DEMO)
