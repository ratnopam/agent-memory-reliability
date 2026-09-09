"""Erasure inflation, end to end: deleting the weak evidence raises the number.

Run it with ``python examples/erasure_inflation.py``. Three numbers come out. The first
two agree. The third does not, and nothing about the plan was revised to make it move.
"""

from amr.protocol import ForgetMode
from amr.registry import named


def read_the_plan(mode: ForgetMode) -> tuple[float, float]:
    """A ticket, an analysis of the ticket, a plan from the analysis. Forget the ticket."""
    memory = named("reference", mode)
    ticket = memory.write("customer says checkout is broken", 0.40)
    analysis = memory.write("checkout p99 regressed after the gateway change", 0.90,
                            sources=[ticket])
    plan = memory.write("roll back the gateway change", 0.95, sources=[analysis])

    before = memory.effective_confidence(plan)
    memory.forget(ticket, mode=mode)
    return before, memory.effective_confidence(plan)


present, after_tombstone = read_the_plan(ForgetMode.TOMBSTONE)
_, after_erase = read_the_plan(ForgetMode.ERASE)

print(f"effective(plan), ticket present    {present:.2f}")
print(f"effective(plan), ticket tombstoned {after_tombstone:.2f}")
print(f"effective(plan), ticket erased     {after_erase:.2f}")
print()
print("The plan was never revised. Erasing its weakest ancestor left min() with an")
print(f"empty chain, which is 1.0, so the plan rose from {present:.2f} to {after_erase:.2f}.")
