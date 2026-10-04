"""Re-execute a recorded tool-call trace and compare every value that comes back.

A trace is what a session did; a replay is the claim that the session was deterministic
and that the code still does it. The two are not the same assertion as ``make determinism``
makes: that one runs the suite twice in the same tree, where this one runs a session
recorded by an *older* tree against the current one. A value that moved is either a fix or
a regression, and either way the replay names it.

The calls go through ``amr.toolcalls`` — the same translation the server used to produce
the trace, not a second implementation of it. That is the whole reason the translation is
not inside ``mcp/server.py``: a replay that needed the MCP SDK installed in order to
compare two numbers is a replay nobody runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amr import registry, toolcalls
from amr.protocol import ForgetMode


@dataclass(frozen=True)
class Difference:
    """One recorded call whose replay did not agree with the record."""

    seq: int
    tool: str
    expected: Any
    actual: Any

    def report(self) -> str:
        return (
            f"  {self.seq:>3}  {self.tool}\n"
            f"       recorded: {_short(self.expected)}\n"
            f"       replayed: {_short(self.actual)}"
        )


@dataclass(frozen=True)
class Replay:
    path: Path
    system: str
    calls: int
    differences: tuple[Difference, ...]

    @property
    def identical(self) -> bool:
        return not self.differences

    def report(self) -> str:
        if self.identical:
            return (
                f"{self.path.name}: {self.calls} calls replayed against {self.system}, "
                f"every result identical"
            )
        lines = [
            (
                f"{self.path.name}: {len(self.differences)} of {self.calls} calls differ "
                f"when replayed against {self.system}"
            )
        ]
        lines.extend(difference.report() for difference in self.differences)
        return "\n".join(lines)


def _short(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def read_trace(path: Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """The header and the calls. A trace without a header cannot be replayed."""
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not lines:
        raise ValueError(f"{path} is empty")
    header = json.loads(lines[0])
    if "amr_trace" not in header:
        raise ValueError(
            f"{path} has no trace header; its first line must carry amr_trace, "
            "the bound scope and the default forget mode"
        )
    if header["amr_trace"] != toolcalls.TRACE_VERSION:
        raise ValueError(
            f"{path} is trace version {header['amr_trace']}; this build reads "
            f"version {toolcalls.TRACE_VERSION}"
        )
    return header, tuple(json.loads(line) for line in lines[1:])


def replay(path: Path, system_name: str = "reference") -> Replay:
    """Run every call in ``path`` against a fresh system and collect the differences."""
    header, calls = read_trace(path)
    mode = ForgetMode(header["default_forget_mode"])
    system = registry.registration(system_name).build(mode)
    scoped = toolcalls.scope_binder(header.get("bound_scope"))

    differences: list[Difference] = []
    for entry in calls:
        seq, tool = entry["seq"], entry["tool"]
        arguments = entry.get("arguments", {})
        try:
            actual: Any = {"result": toolcalls.dispatch(system, tool, arguments, scoped)}
        except toolcalls.ToolCallError as error:
            actual = {"error": {"code": error.code, "message": error.message}}
        expected = (
            {"error": entry["error"]} if "error" in entry else {"result": entry["result"]}
        )
        if actual != expected:
            differences.append(
                Difference(seq=seq, tool=tool, expected=expected, actual=actual)
            )
    return Replay(
        path=path,
        system=system_name,
        calls=len(calls),
        differences=tuple(differences),
    )


def replay_all(paths: list[Path], system_name: str = "reference") -> list[Replay]:
    """Each trace against its own fresh system: one trace must not seed the next."""
    return [replay(path, system_name) for path in paths]
