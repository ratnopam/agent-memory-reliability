# agent-memory-reliability

An agent writes a conclusion it derived from something it read last week. Nothing records
that derivation, so nothing can tell you the conclusion rests on a note someone has since
retracted. Retrieval benchmarks measure whether the right memory comes back. They do not
measure whether a memory that comes back can be trusted given where it came from — whether
its provenance is walkable, whether its confidence is bounded by its weakest evidence,
whether deleting that evidence has a defined consequence, and whether another agent's scope
can reach it. This repository specifies those four properties as falsifiable checks, ships a
reference implementation, and runs a conformance suite against it with no model anywhere in
the measurement path.

## The four properties

**P1 — Provenance walk across writes.** Every write records what it was derived from, and
the walk from any descendant to its roots is complete, terminating, acyclic, free of
dangling identifiers, and unchanged across a reopen. A write citing a source that does not
resolve is rejected outright.

**P2 — Confidence cascading along the chain.** `effective(m) = min(declared(m), min over
effective(sources))`, with `min` over the empty set defined as 1.0. Lowering trust in
evidence lowers everything derived from it; a shared ancestor in a diamond constrains the
sink once; raising an ancestor does not lift a descendant past its own claim.

**P3 — Forget operations.** Forgetting makes a memory unreadable and has a declared,
observable effect on its descendants — `tombstone`, `cascade`, or `erase`. It is idempotent,
it cannot be undone by rewriting the same content, and it returns a receipt naming the mode,
every affected identifier, and every confidence that moved.

**P4 — Isolation when agents share state.** Scopes cannot read each other's memories without
a recorded, revocable grant, a cross-scope ancestor contributes confidence without leaking
content, a forget crosses the boundary, and interleaved writes produce one well-formed DAG.

The normative text is [version1/SPEC.md](version1/SPEC.md): 23 numbered checks, one test
each.

## The finding: erasure inflation

`min` over an empty chain is 1.0, because a record with no ancestors is bounded only by its
own claim. Correct for roots. It also means that a forget which genuinely removes an
ancestor shortens its descendant's chain, so `min` runs over a smaller set:

```
source(0.4) <- derived(declared 0.9)      effective(derived) = min(0.9, 0.4) = 0.4
forget(source, mode=erase)
derived(declared 0.9), chain empty        effective(derived) = min(0.9, 1.0) = 0.9
```

Forgetting the evidence strengthened the conclusion. Nothing is corrupted, no invariant
breaks, no error is raised, and the number a downstream reader trusts went up. Under
`tombstone` the chain position survives and the value does not move; under `cascade` the
derivative does not survive to be inflated; under `erase` the inflation is guaranteed by
construction. The suite reports it as a DIVERGENCE rather than scoring it, because
[SPEC.md §6.4](version1/SPEC.md) leaves the tension open and each of the three obvious
fixes costs something real. The same number is reachable with no deletion at all — see
[taxonomy/](taxonomy/).

## Results

| Property | tombstone | cascade | erase |
|---|---|---|---|
| P1 — Provenance walk across writes | PASS | PASS | PASS |
| P2 — Confidence cascading along the chain | PASS | PASS | DIVERGENCE |
| P3 — Forget operations | PASS | PASS | PASS |
| P4 — Isolation when agents share state | PASS | PASS | PASS |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **PASS** | **PASS** | **DIVERGENCE** |

Reference implementation, one column per forget mode. The per-check table, the capability
declaration, and the machine-readable record are in [results/](results/). A property row is
PASS only if every check in it passed. P2.5 is a single signed comparison,
`effective_after <= effective_before`, with no branch on the mode: the divergence comes from
the system's declared capabilities, not from the check expecting it.

## Reproduce

```
git clone https://github.com/ratnopam/agent-memory-reliability && cd agent-memory-reliability
make reproduce
make determinism
```

Python 3.11+ and pip. `pytest` is the only dependency; nothing is vendored, and no model is
called anywhere. `make determinism` runs the whole thing twice in fresh subprocesses and
fails if a single byte of the results differs apart from the timestamp.

## Add a system

Write `systems/<name>/__init__.py` with an adapter implementing
`harness.protocol.MemorySystem`, publish a `Capabilities` declaration, and call
`harness.registry.register("<name>", Factory)`. The factory takes `default_forget_mode`. The
suite is parameterised over every registered system and every mode it declares, so a new
adapter adds columns without any test being edited. `SYSTEMS=<name> make test` runs one.
Nothing in `harness/` or `properties/` names a system.

## Add a failure mode

Write `taxonomy/repro/<slug>.py` with a `reproduce(system) -> dict` that uses
`harness.protocol` only, write `taxonomy/<slug>.md` embedding that module's source in a
`python` block, and register it in `properties/test_taxonomy.py`. The suite runs the
reproduction against every registered system and asserts the embedded snippet is
byte-identical to the code that ran, so an entry cannot drift from the behaviour it
describes.

## Against retrieval benchmarks

Orthogonal, not competing. LoCoMo, LongMemEval, and BEAM ask whether the right memory comes
back for a query; every check here assumes the memory came back and asks what can be
trusted about it. A system can score perfectly here and retrieve badly, or retrieve well and
fail every property. Nothing in this repository measures ranking, recall, embeddings, or
latency.

## Prior art

The provenance model is a deliberately small subset of W3C PROV and of data-lineage systems
in the warehouse tradition: one node type, one edge type (*derived from*), no typed
relations, no agent or activity distinction. What is added is the confidence arithmetic over
that graph, the requirement that deletion have a declared and observable effect on
descendants, and the treatment of a shortened chain as a first-class failure mode rather
than an integrity error. Judgments — contradiction, corroboration, supersession — are
records derived from what they judge, not edge types, which is what keeps the arithmetic
terminating and any model that produced a judgment upstream of the layer rather than inside
it.

## Limitations

- It cannot make an agent act on the number. A bounded confidence is available; whether a
  policy reads it is above this layer.
- It cannot detect an undeclared source. An agent that reads a memory and writes a
  conclusion without citing it produces a record indistinguishable from an original
  observation. Detecting that needs a model in the measurement path, which would cost
  determinism. See `taxonomy/undeclared-derivation.md`.
- It does not judge conflicts. Deciding that two memories contradict each other requires
  semantics. Representing the judgment is in scope; making it is not.
- It does not measure retrieval quality. See above.

## License

Apache 2.0.
