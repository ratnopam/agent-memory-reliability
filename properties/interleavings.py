"""Fixed interleaving schedules for P4.5.

"Concurrent interleaved writes" is checked without threads. The suite replays a
checked-in set of schedules -- the interleavings are data, not scheduling -- so the whole
run stays byte-reproducible while still exercising every order in which two agents'
writes can reach the store.

Every schedule below is a valid topological order of ``PLAN``: a record is always written
after the records it cites, which strict writes (I1.6) require. ``b2`` cites a record
owned by the other agent, so the schedules also cover a cross-scope edge.
"""

from __future__ import annotations

from dataclasses import dataclass

ALPHA = "alpha"
BETA = "beta"


@dataclass(frozen=True)
class Step:
    key: str
    scope: str
    declared: float
    sources: tuple[str, ...] = ()


PLAN: tuple[Step, ...] = (
    Step(key="a1", scope=ALPHA, declared=0.4),
    Step(key="a2", scope=ALPHA, declared=0.9, sources=("a1",)),
    Step(key="a3", scope=ALPHA, declared=0.6, sources=("a1", "a2")),
    Step(key="b1", scope=BETA, declared=0.8),
    Step(key="b2", scope=BETA, declared=0.95, sources=("b1", "a1")),
    Step(key="b3", scope=BETA, declared=0.7, sources=("b2",)),
)

BY_KEY: dict[str, Step] = {step.key: step for step in PLAN}

SCHEDULES: tuple[tuple[str, ...], ...] = (
    ("a1", "a2", "a3", "b1", "b2", "b3"),
    ("a1", "b1", "a2", "b2", "a3", "b3"),
    ("a1", "b1", "b2", "b3", "a2", "a3"),
    ("b1", "a1", "b2", "a2", "a3", "b3"),
    ("a1", "a2", "b1", "b2", "b3", "a3"),
    ("b1", "a1", "a2", "b2", "a3", "b3"),
)


def is_topological(schedule: tuple[str, ...]) -> bool:
    written: set[str] = set()
    for key in schedule:
        step = BY_KEY[key]
        if not set(step.sources) <= written:
            return False
        written.add(key)
    return written == set(BY_KEY)
