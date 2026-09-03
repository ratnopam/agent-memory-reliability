# Agent Memory Reliability Specification

**License:** Apache 2.0

---

## 1. Scope

This document specifies four reliability properties for systems that store memories on
behalf of long-running agents. It is implementation-neutral: it constrains observable
behavior at an operation boundary, not storage format, indexing strategy, or agent
framework.

It does **not** specify retrieval quality. Whether the right memory comes back for a
given query is measured by existing benchmarks (LoCoMo, LongMemEval, BEAM). This
specification is orthogonal to those. A system can score perfectly here and retrieve
badly, or retrieve well and fail every property below.

A **conforming implementation** is one that (a) exposes the operation set in §3,
(b) publishes a capability declaration per §7, and (c) produces the required outcome
for every conformance check in §4–§6 given its declared capabilities.

---

## 2. Model

A **memory store** holds **records**. Each record has:

| Field | Type | Meaning |
|---|---|---|
| `id` | opaque identifier | Stable for the lifetime of the record. Not reused after deletion. |
| `content` | opaque payload | Not interpreted by this specification. |
| `declared_confidence` | float in [0.0, 1.0] | Asserted by the writer at write time. |
| `sources` | set of `id` | The records this one was derived from. May be empty. |
| `scope` | opaque identifier | The isolation boundary the record belongs to (§7). |
| `origin` | typed reference, or none | Descriptive only. What an external root refers to: a document, URL, tool call, or conversation turn. Never affects arithmetic. |

The `sources` relation over all records forms the **provenance graph**. A record with
empty `sources` is a **root**. A record reachable from `m` by following `sources`
transitively is an **ancestor** of `m`; the reverse relation is **descendant**.

A **tombstone** is a record whose content has been erased but whose `id`,
`declared_confidence`, and `sources` are retained. Tombstones participate in chain
arithmetic. They are never readable.

### 2.1 External origins

Roots frequently refer to things outside the store: a document, a URL, a tool result, a
conversation turn. Such a thing is written into the store first, as a root record whose
content is the reference and whose `origin` names its kind. It then carries a declared
confidence, participates in the weakest-link walk, and can be reached by a cascade like
any other record.

The graph therefore stays closed. No edge ever points out of it.

Fields that record where something came from informally — free-text source annotations,
the query that triggered a write, workflow identifiers, turn context — are annotations.
They MUST NOT be read as provenance, and nothing in §5 may depend on them.

What this costs: someone has to declare a confidence for the external thing, and there
is no principled way to choose one. See open question 6.

### 2.2 Judgments are records, not edges

There is exactly one edge type: *derived from*. Contradiction, agreement, correction,
and supersession are expressed as **records derived from the memories they judge**, not
as additional edge types.

A judge — a model, a person, or a rule — reads two conflicting memories and writes a
third record derived from both, whose content states the judgment and whose
`declared_confidence` states how sure the judge is. Independent corroboration works the
same way: a record derived from two agreeing sources, declared higher than either.

This keeps the arithmetic in §5 well-defined, keeps the graph acyclic, and keeps any
model that produced a judgment upstream of this layer rather than inside it. Judgment is
captured as content, which is auditable and replayable. It is never captured as
arithmetic, which would make conformance unfalsifiable.

---

## 3. Operation set

Conformance is defined against these operations. Names are indicative; adapters map
them onto whatever the underlying system calls them.

```
write(content, declared_confidence, sources, scope) -> id
get(id, scope)                                      -> record | NotFound | Forgotten
provenance(id, scope)                               -> ancestor subgraph
effective_confidence(id, scope)                     -> float
descendants(id, scope)                              -> set of id
revise(id, scope, new_declared, reason)             -> revision receipt
forget(id, scope, mode)                             -> forget receipt
list_scope(scope)                                   -> set of id
```

`get` distinguishes three outcomes: the record exists and is readable, the record never
existed, or the record existed and has been forgotten. The third is a distinct signal
and MUST NOT be collapsed into the second — §6.2 depends on it.

`revise` and `forget` are the only operations that change existing state. `revise`
changes a record's `declared_confidence` and nothing else: content, `sources`, `scope`,
and `id` are immutable after a write. What triggers a revision — a recency policy, a
postmortem finding, a human correction — is a caller's concern. This specification takes
no position on it, in the same way it takes no position on how a declared confidence is
chosen in the first place.

---

## 4. P1 — Provenance walk across writes

**Statement.** Every write records what it was derived from, and that derivation is
walkable from any descendant back to its roots, across sessions and across agents.

**Invariants.**

- **I1.1 Acyclicity.** The provenance graph is a DAG. A write whose `sources` would
  introduce a cycle MUST be rejected.
- **I1.2 Closure.** `provenance(m)` returns every ancestor of `m`, not only its
  immediate sources.
- **I1.3 Termination.** `provenance(m)` terminates on diamonds, deep chains, and
  wide fan-in. Each ancestor appears once regardless of how many paths reach it.
- **I1.4 Referential integrity.** Every `id` appearing in a returned chain resolves to
  a live record, a tombstone, or an explicitly-marked opaque ancestor (§7). Dangling
  identifiers are a conformance failure.
- **I1.5 Durability.** Provenance survives process restart and is identical when read
  by a different agent in a scope with access.
- **I1.6 Strict writes.** A write whose `sources` contain an identifier that does not
  resolve MUST be rejected. An implementation MUST NOT accept the write and silently
  drop the unresolvable ancestor.

  This is the strictest available choice and it is deliberate. An ancestor that is
  skipped during a walk shortens the chain, which raises effective confidence by the
  mechanism in §6.4 — without anyone having deleted anything. A typo, a stale
  identifier, or a reset store is enough to trigger it. Failing at write time puts the
  error where a caller can still be blamed for it; failing silently at read time
  produces a chain that looks complete and is not. The cost is ordering: parents MUST be
  written before children.

**Conformance checks.**

| ID | Check | Required outcome |
|---|---|---|
| P1.1 | Write a cycle-forming record | Rejected |
| P1.2 | Three-hop chain, walk from leaf | All three ancestors returned |
| P1.3 | Diamond graph, walk from sink | Shared ancestor returned exactly once |
| P1.4 | Walk after an ancestor is forgotten | No dangling ids, per declared mode |
| P1.5 | Walk after store reopen | Byte-identical chain |
| P1.6 | Write citing an unresolvable source id | Rejected, nothing persisted |

---

## 5. P2 — Confidence cascading along the chain

**Statement.** A memory cannot be more trustworthy than the weakest evidence it rests
on, and lowering trust in evidence lowers trust in everything derived from it.

**Rule.**

```
effective(m) = min( declared(m), min{ effective(a) : a in sources(m) } )
min over the empty set = 1.0
```

The empty-set convention is stated explicitly because it is load-bearing. `min(∅) = 1.0`
is the vacuous upper bound: a record with no ancestors is bounded only by its own
declared confidence. This is the correct reading for roots. It is also the mechanism
behind the failure mode in §6.4, and alternatives (`0.0`, undefined, refuse-to-answer)
are an open question, not a settled one.

**Invariants.**

- **I2.1 Weakest-link bound.** For every ancestor `a` of `m`, `effective(m) ≤ effective(a)`.
- **I2.2 Downgrade propagation.** Lowering `declared(a)` lowers `effective(m)` for every
  descendant `m`, observable on the next read.
- **I2.3 Diamond consistency.** A shared ancestor constrains the sink once. Effective
  confidence is a function of the ancestor set, not of path count.
- **I2.4 Determinism.** Same graph, same values, independent of insertion or traversal
  order.
- **I2.5 No inflation on removal.** Removing a record MUST NOT raise the effective
  confidence of any surviving record.
- **I2.6 Revisions are recorded.** A revision MUST be retrievable after the fact: the
  previous declared value, the new one, and the stated reason. An audit layer that
  silently overwrites its own numbers cannot answer "what did this say last quarter",
  which is the question audits exist to answer.
- **I2.7 Revision is directionally asymmetric.** Lowering a record's declared confidence
  lowers every descendant's effective confidence that was bounded by it. Raising it does
  not raise descendants beyond their own declared values, because each descendant is
  still capped by its own assertion and by every other ancestor. Implementations MUST
  support lowering. Support for raising is optional and MUST be declared.

I2.5 is the property that separates forget modes. Under `tombstone` it holds. Under
`erase` it cannot hold, because the chain shortens and `min` is taken over a smaller
set. See §6.4.

**Conformance checks.**

| ID | Check | Required outcome |
|---|---|---|
| P2.1 | Chain 0.4 → 0.9, read leaf | 0.4 |
| P2.2 | Revise root 0.9 → 0.2, read leaf | Leaf ≤ 0.2 |
| P2.3 | Diamond with one weak ancestor | Sink bounded once, not squared |
| P2.4 | Root with no sources, declared 0.7 | 0.7 |
| P2.5 | Forget weakest ancestor, re-read leaf | `effective_after ≤ effective_before` |
| P2.6 | Read revision history after a revise | Prior value, new value, and reason present |
| P2.7 | Raise an ancestor above a descendant's declared value | Descendant unchanged |

P2.5 is written as a signed comparison, not as a mode-specific assertion. The same
assertion passes under `tombstone` and fails under `erase`. That difference is the
result, and it is reproducible with a one-line configuration change.

---

## 6. P3 — Forget operations

**Statement.** A request to forget makes a memory unreadable and has a declared,
observable effect on everything derived from it.

### 6.1 Modes

An implementation MUST support at least one and MUST declare which:

- **`tombstone`** — content erased; `id`, `declared_confidence`, and `sources` retained.
  Descendants survive. Chain arithmetic unchanged. I2.5 holds.
- **`cascade`** — the record and every descendant are removed. Nothing survives to
  inflate. I2.5 holds vacuously.
- **`erase`** — the record and its edges are removed. Descendants survive with shortened
  chains. I2.5 is violated by construction.

### 6.2 Universal post-conditions

Independent of mode, after `forget(x)`:

- **I3.1** `get(x)` returns `Forgotten`, never content.
- **I3.2** `x` does not appear in `list_scope`.
- **I3.3** `forget(x)` is idempotent. A second call succeeds and changes nothing.
- **I3.4** No resurrection. Writing a new record with identical content does not restore
  `x`'s identifier, chain position, or descendants.
- **I3.5** The operation returns a receipt naming the mode, the affected ids, and the
  effective-confidence delta for each surviving descendant.

### 6.3 Conformance checks

| ID | Check | Required outcome |
|---|---|---|
| P3.1 | Read a forgotten record | `Forgotten`, distinct from `NotFound` |
| P3.2 | Forget twice | Second call succeeds, no change |
| P3.3 | Forget a mid-chain record | Descendants handled per declared mode |
| P3.4 | Re-write identical content | New id, no inherited descendants |
| P3.5 | Inspect receipt | Mode, affected ids, and deltas present |

### 6.4 Erasure inflation — an unresolved tension

Under `erase`, a derived record whose weakest ancestor is forgotten becomes **more**
confident, because `min` is now taken over a smaller ancestor set — and if it was the
only ancestor, over the empty set, which returns 1.0.

```
before:  source(0.4) -> derived(declared 0.9)   effective = min(0.9, 0.4) = 0.4
forget(source, mode=erase)
after:   derived(declared 0.9), chain empty     effective = min(0.9, 1.0) = 0.9
```

Forgetting the evidence strengthens the conclusion.

The same arithmetic is reachable without any deletion at all. Anything that shortens a
chain silently produces an identical inflation: an unresolvable ancestor skipped during
a walk, a summarised record that drops its sources, a store reset that orphans
identifiers. Erasure is the most visible way to shorten a chain, not the only one. That
is why I1.6 rejects writes citing unresolvable sources.

This specification does not resolve the tension. It is recorded here because the three
obvious resolutions each cost something real:

- **Tombstone everything.** Chain arithmetic stays correct, but a tombstone is a
  retained record about a subject who asked to be forgotten. Whether that satisfies a
  deletion obligation is a legal question, not an engineering one.
- **Cascade always.** Deleting one source destroys unrelated downstream work.
- **Recompute derivatives to zero.** Defensible, but it means an unrelated forget
  request can silently zero out conclusions no one asked about.

Implementations MUST declare which they chose. The conformance suite records the
divergence rather than scoring it.

---

## 7. P4 — Isolation when agents share state

**Statement.** Agents operating in separate scopes cannot read each other's memories by
default, cannot corrupt each other's chains, and cannot use provenance as a side channel
around the boundary.

**Invariants.**

- **I4.1 Read isolation.** A record written in scope A is not returned by any read in
  scope B absent an explicit grant.
- **I4.2 Explicit sharing.** Cross-scope visibility requires a recorded grant. Grants
  are revocable and revocation is immediate.
- **I4.3 Opaque ancestors.** A record in B derived from a record in A retains the
  ancestor's `id` and its confidence contribution, but not its content. Provenance
  remains complete (I1.4) without leaking payload.
- **I4.4 Cross-scope forget.** Forgetting in A applies the declared mode to descendants
  in B. Isolation is not an excuse to leave derivatives untouched.
- **I4.5 Concurrent consistency.** Interleaved writes from N agents produce one
  well-formed DAG, with no lost edges and no cycles.

**Conformance checks.**

| ID | Check | Required outcome |
|---|---|---|
| P4.1 | Write in A, list in B | Absent |
| P4.2 | Grant, read, revoke, read | Visible then absent |
| P4.3 | Cross-scope derivation, walk from B | Ancestor id present, content withheld |
| P4.4 | Forget in A with descendants in B | Declared mode applied across the boundary |
| P4.5 | Concurrent interleaved writes | DAG intact, no lost edges |

---

## 8. Capability declaration

Every adapter publishes a declaration. It is what makes divergence principled rather
than a euphemism for failure.

```json
{
  "system": "reference",
  "version": "0.1.0",
  "supported_forget_modes": ["tombstone", "cascade", "erase"],
  "default_forget_mode": "tombstone",
  "empty_chain_convention": 1.0,
  "revision": "logged",
  "revision_raise_supported": true,
  "scopes": "native",
  "cross_scope_derivation": "opaque-ancestor",
  "durability": "in-memory"
}
```

---

## 9. Result states

The suite reports three states, not two.

- **PASS** — the required outcome was produced.
- **FAIL** — the required outcome was not produced and the implementation did not
  declare an exemption.
- **DIVERGENCE** — the implementation declared behavior that this specification
  deliberately leaves open, and behaved consistently with its declaration. P2.5 under
  `erase` is a divergence, not a failure.

A run is identified by `(system, forget_mode)`. Both dimensions appear in the results
matrix.

---

## 10. Non-goals

- Retrieval quality, ranking, and recall.
- Embedding models, similarity metrics, and index structures.
- Any confidence-elicitation mechanism. `declared_confidence` is an input.
- Conflict *detection*. Deciding that two memories contradict each other requires
  semantics and belongs to an agent above this layer. Conflict *representation* is in
  scope, and is handled by §2.2.
- Cryptographic audit guarantees. Receipts are structural, not signed.
- Performance. Nothing here is a latency or throughput claim.

---

## 11. Open questions

1. Should `min(∅)` be 1.0, 0.0, or undefined? Each breaks something different.
2. Is a tombstone compatible with a deletion obligation?
3. Should `erase` be permitted at all, or is it a mode that only exists to be measured?
4. Does weakest-link min discard too much? A record derived from ten independent weak
   sources is arguably stronger than one derived from a single weak source, and min
   cannot express that.
5. Should confidence recomputation be eager or lazy, and is the difference observable in
   a way that matters?
6. What confidence should an external origin declare? A runbook, a Slack message, and a
   tool result are not equally trustworthy, and nothing here says how to pick a number.
7. Is one edge type the right call? Typed edges (supports, contradicts, supersedes) are
   more expressive, but no one has yet offered a confidence rule for them that stays
   both defensible and terminating. §2.2 is the current answer. A better one would
   change the specification.

---

## Changelog

- **0.3** — `revise` added as an eighth operation, closing the hole that made I2.2
  untestable. Revisions must be recorded (I2.6) and are directionally asymmetric (I2.7).
  Checks P2.6 and P2.7 added.
- **0.2** — strict writes (I1.6, P1.6). External origins as root records (§2.1).
  Judgments expressed as derived records rather than typed edges (§2.2). Conflict
  detection reframed in §10. Two open questions added.
- **0.1** — initial draft. Four properties, three forget modes, three result states.
