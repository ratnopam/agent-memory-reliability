"""Every committed trace still replays, and a trace that has moved is still caught.

A trace is a recorded session: the tool calls someone made and the values that came back.
Replaying it asserts something the rest of the suite cannot, because the suite only ever
runs the code against itself. A trace was recorded by an *older* tree, so a value that
moved is either a fix or a regression, and the replay names it either way.

The second test is the one that keeps the first honest. A comparison that always agrees
is indistinguishable from a comparison that never runs, so one recorded value is altered
in a copy and the replay has to notice. Without it, ``every result identical`` would be a
sentence this file prints rather than a thing it checked.
"""

from __future__ import annotations

import json

import pytest

from amr import replay as replay_module
from amr.paths import repo_root


def _traces() -> list:
    return sorted((repo_root() / "examples" / "traces").glob("*.jsonl"))


@pytest.mark.extra("traces-replay")
def test_every_committed_trace_replays_identically() -> None:
    traces = _traces()
    assert traces, "examples/traces/ holds no trace; amr replay has nothing to prove on"
    for run in replay_module.replay_all(traces):
        assert run.identical, run.report()


@pytest.mark.extra("traces-detect-a-moved-value")
def test_an_altered_recording_is_reported(tmp_path) -> None:
    trace = _traces()[0]
    lines = trace.read_text(encoding="utf-8").splitlines()
    index, entry = next(
        (position, json.loads(line))
        for position, line in enumerate(lines)
        if position and "result" in json.loads(line)
    )
    entry["result"] = {"a value no tool returns": True}
    lines[index] = json.dumps(entry, sort_keys=True, separators=(",", ":"))

    altered = tmp_path / trace.name
    altered.write_text("\n".join(lines) + "\n", encoding="utf-8")

    run = replay_module.replay(altered)
    assert not run.identical, "an altered recording replayed as if nothing had changed"
    assert [difference.seq for difference in run.differences] == [entry["seq"]]


@pytest.mark.extra("traces-require-a-header")
def test_a_trace_without_a_header_is_refused(tmp_path) -> None:
    """The header carries the forget mode the session ran under.

    Replaying without it would mean guessing, and a guess that happened to be right
    would make every ``memory_forget`` call that omitted an explicit mode pass for the
    wrong reason.
    """
    headless = tmp_path / "headless.jsonl"
    headless.write_text(
        '{"seq":1,"tool":"memory_list_scope","arguments":{},"result":{}}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no trace header"):
        replay_module.replay(headless)
