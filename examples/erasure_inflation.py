"""Erasure inflation, end to end: deleting the weak evidence raises the number.

Run it with ``python examples/erasure_inflation.py``. Three numbers come out. The first
two agree. The third does not, and nothing about the summary was revised to make it move.
"""

from amr.protocol import ForgetMode
from amr.registry import named


def read_the_summary(mode: ForgetMode) -> tuple[float, float]:
    """A report, an on-call note citing it, a summary citing the note. Forget the note."""
    memory = named("reference", mode)
    report = memory.write("checkout p99 regressed after the deploy", 0.90)
    note = memory.write("someone in chat says it is the memory leak again", 0.40,
                        sources=[report])
    summary = memory.write("root cause: the memory leak", 0.95, sources=[note])

    before = memory.effective_confidence(summary)
    memory.forget(note, mode=mode)
    return before, memory.effective_confidence(summary)


present, after_tombstone = read_the_summary(ForgetMode.TOMBSTONE)
_, after_erase = read_the_summary(ForgetMode.ERASE)

print(f"effective(summary), note present    {present:.2f}")
print(f"effective(summary), note tombstoned {after_tombstone:.2f}")
print(f"effective(summary), note erased     {after_erase:.2f}")
print()
print("The summary was never revised. Erasing its weakest ancestor left min() with an")
print(f"empty chain, which is 1.0, so the summary rose from {present:.2f} to {after_erase:.2f}.")
