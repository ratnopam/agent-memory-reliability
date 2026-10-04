"""The whole layer in one screen: write a chain, read the bound, forget the middle.

Run it with ``python examples/use_it.py``. Nothing is configured and no model is called.
"""

from amr.registry import named

memory = named("reference")  # default forget mode: tombstone

incident = memory.write("checkout p99 regressed after the deploy", 0.90)
hearsay = memory.write("someone in chat says it is the memory leak again", 0.40,
                       sources=[incident])
summary = memory.write("root cause: the memory leak", 0.95, sources=[hearsay])

print(f"declared  {memory.get(summary).record.declared_confidence:.2f}")
print(f"effective {memory.effective_confidence(summary):.2f}  <- bounded by the hearsay")

receipt = memory.forget(hearsay)
print(f"\nforget({hearsay}) mode={receipt.mode.value} forgotten={sorted(receipt.forgotten)}")
for delta in receipt.deltas:
    print(f"  {delta.id}: {delta.before:.2f} -> {delta.after:.2f}")
print(f"get({hearsay}) -> {memory.get(hearsay).outcome.value}")
print(f"effective {memory.effective_confidence(summary):.2f}  <- the bound survived the forget")
