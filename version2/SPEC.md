# Agent Memory Reliability Specification

**Version:** 0.4 (draft)
**License:** Apache 2.0

Draft. `version1/SPEC.md` (0.3) is frozen and is what the Phase 0 results in
`results/2026-09-09/` were produced against. This revision folds in the nineteen entries
in `design-notes/spec-feedback.md`, all of which came from building a conforming
implementation and a suite against 0.3 and finding the text silent, ambiguous, or
self-contradicting. The changelog names each one. Entries from 20 on were raised against
this revision and are applied to it directly.

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
(b) publishes a capability declaration per §8, and (c) produces the required outcome
for every conformance check in §4–§7 given its declared capabilities.

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

Conformance is defined against **twelve** operations: nine that read and write records,
and three that administer cross-scope grants. Names are indicative; adapters map them
onto whatever the underlying system calls them.

```
write(content, declared_confidence, sources, scope) -> id
get(id, scope)                                      -> record | NotFound | Forgotten
provenance(id, scope)                               -> ancestor subgraph
effective_confidence(id, scope)                     -> float
descendants(id, scope)                              -> set of id
revise(id, scope, new_declared, reason)             -> revision receipt
revisions(id, scope)                                -> ordered revision receipts
forget(id, scope, mode)                             -> forget receipt
list_scope(scope)                                   -> set of id

grant(owner_scope, reader_scope)                    -> grant receipt
revoke(owner_scope, reader_scope)                   -> grant receipt
grants(owner_scope)                                 -> set of reader scope
```

`get` distinguishes three outcomes: the record exists and is readable, the record never
existed, or the record existed and has been forgotten. The third is a distinct signal
and MUST NOT be collapsed into the second — §6.2 depends on it.

`revise` and `forget` are the only operations that change existing state. `revise`
changes a record's `declared_confidence` and nothing else: content, `sources`, `scope`,
and `id` are immutable after a write. What triggers a revision — a recency policy, a
postmortem finding, a human correction — is a caller's concern. This specification takes
no position on it, in the same way it takes no position on how a declared confidence is
chosen in the first place. `revise` fails for a forgotten record, including a tombstone:
*forgotten* is terminal for a record's declared state.

`revisions` returns every revision of a record, oldest first. A receipt returned by
`revise` and the corresponding entry from `revisions` carry the same before value, after
value, and reason. Without the reader, I2.6 requires a history that no caller can obtain,
and "recorded" that cannot be read is indistinguishable from "not recorded".

`grant`, `revoke`, and `grants` are the mechanism I4.2 requires. They are part of the
operation set rather than out-of-band administration because P4.2 tests the whole
grant–read–revoke–read sequence, and a check for a required invariant cannot depend on a
mechanism the specification declines to name. `grants(s)` returns the reader scopes that
`s` has granted, which is the observable a revocation has to change.

### 3.1 Error vocabulary

Five failure signals are normative. An adapter author must be able to learn what an
operation raises from this table alone, without reading a reference implementation.

| Signal | Raised by | Condition |
|---|---|---|
| `UnresolvedSourceError` | `write` | Any id in `sources` does not resolve for the writing scope: it never existed, or it exists in another scope with no grant (I1.6, I4.1). The two cases MUST NOT be distinguishable. |
| `CycleError` | `write`, and any operation that opens a stored snapshot | The requested edges would close a cycle, or a snapshot's edges contain one (I1.1, P1.7). |
| `ForgottenRecordError` | `write`, `revise`, `provenance`, `effective_confidence`, `descendants` | The target — or, for `write`, a cited source — has been forgotten and no longer has the state the operation needs. A write MUST NOT cite a forgotten record, tombstone included (§6.2). `provenance`, `effective_confidence`, and `descendants` answer for a tombstone, which retains its chain position, and fail for a record removed by `cascade`, `erase`, or `residue`. |
| `NotFound` | every operation taking an `id` | No record with that id is visible to the calling scope. `get` reports this as an outcome rather than an error; the others fail. |
| `ScopeError` | `revise`, `forget` | The target *is* visible to the calling scope through a grant, and the calling scope does not own it. |

Four consequences worth stating, because each one closes an oracle:

- An operation on a record the calling scope cannot see behaves exactly as it would for
  an id that never existed — `NotFound`, not "forbidden". A permission error on an
  invisible record is an existence oracle: it tells the caller that some id exists
  somewhere, which is the side channel §7 exists to rule out. This holds for *every*
  operation, not only reads, because the oracle does not care which operation leaks it.
- `ScopeError` is therefore reachable only for a record the caller can already read. It
  leaks nothing, and it is required: a read grant conveys reading, and a reader that
  could `revise` or `forget` the owner's record would make I4.2 a grant of everything.
- `NotFound` is checked before `ForgottenRecordError`, and before `ScopeError`. A caller
  learns that a record was forgotten, or that it is someone else's, only if it could have
  seen the record.
- The one deliberate exception to scope-bound reporting is the forget receipt (I4.4),
  which names ids in other scopes — because the call itself affected them.

---

## 4. P1 — Provenance walk across writes

**Statement.** Every write records what it was derived from, and that derivation is
walkable from any descendant back to its roots, across sessions and across agents.

**Invariants.**

- **I1.1 Acyclicity.** The provenance graph is a DAG. A write whose `sources` would
  introduce a cycle MUST be rejected.

  Where identifiers are store-assigned and writes are strict (I1.6), acyclicity follows
  from the construction and is not independently checkable: a source must already exist
  to be cited, so every edge points strictly backwards. Implementations accepting
  caller-supplied identifiers MUST reject a cycle-closing write. Every implementation
  MUST reject a stored snapshot whose edges contain a cycle (I1.5, P1.7); that is where
  the invariant remains falsifiable for all of them.
- **I1.2 Closure.** `provenance(m)` returns every ancestor of `m`, not only its
  immediate sources.
- **I1.3 Termination.** `provenance(m)` terminates on diamonds, deep chains, and
  wide fan-in. Each ancestor appears once regardless of how many paths reach it.
- **I1.4 Referential integrity.** Every `id` appearing in a returned chain resolves to
  a live record, a tombstone, or an explicitly-marked opaque ancestor (§7). Dangling
  identifiers are a conformance failure.
- **I1.5 Durability.** Provenance survives process restart and is identical when read
  by a different agent in a scope with access. The declared `durability` (§8) says how a
  restart is demonstrated; `in-memory` cannot demonstrate it and fails P1.5.

  A stored snapshot MUST expose the provenance graph in a form an external validator can
  check without knowing the storage format: a list of record objects, each carrying a
  string `id` and a list of string `sources`. This is the minimum needed to verify
  acyclicity and referential integrity from outside the implementation, and it is what
  P1.7 reads.
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

  A source id that exists but is not readable by the writing scope is unresolvable for
  the purposes of this invariant, and the rejection MUST NOT be distinguishable from the
  rejection of an id that does not exist. Otherwise a write becomes a probe of another
  scope's id space, and a successful one would let a writer pin a record it cannot read
  into place.

**Conformance checks.**

| ID | Check | Required outcome |
|---|---|---|
| P1.1 | Write citing an id that has not been assigned | Rejected |
| P1.2 | Three-hop chain, walk from leaf | All three ancestors returned |
| P1.3 | Diamond graph, walk from sink | Shared ancestor returned exactly once |
| P1.4 | Walk after an ancestor is forgotten | No dangling ids, per declared mode |
| P1.5 | Walk after store reopen | Byte-identical chain |
| P1.6 | Write citing an unresolvable source id | Rejected, nothing persisted |
| P1.7 | Deserialise a store containing a cycle | Rejected |

P1.1 and P1.7 are the two halves of I1.1: the write boundary and the snapshot boundary.
P1.7 takes a new id at the end of the sequence rather than displacing P1.2–P1.6, because a
check id is a citation and results already exist that name them.

P1.5's "byte-identical" means a canonical serialisation of the chain — ancestors in
sorted id order, `sources` sorted within each node, the tombstoned and opaque flags
included — is unchanged across the reopen. An implementation MAY define its own canonical
form provided it is stable across reopens. A structural comparison would pass while
iteration order changed, and iteration order is exactly what a persistence layer
perturbs.

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

`empty_chain_convention` is therefore declared (§8), and the checks in this
specification MUST be expressed in terms of the declaration rather than assuming a value.
A system that resolves open question 1 differently has to be able to pass P2.5 without
the check being edited. A check that reads `if mode is erase: expect inflation` proves
nothing about this specification.

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
- **I2.6 Revisions are recorded.** A revision MUST be retrievable after the fact through
  `revisions`: the previous declared value, the new one, and the stated reason. An audit
  layer that silently overwrites its own numbers cannot answer "what did this say last
  quarter", which is the question audits exist to answer. Returning the receipt from
  `revise` covers an audit that was watching at the time; the point of I2.6 is an audit
  that was not.
- **I2.7 Revision is directionally asymmetric.** Lowering a record's declared confidence
  lowers every descendant's effective confidence that was bounded by it. Raising it does
  not raise descendants beyond their own declared values, because each descendant is
  still capped by its own assertion and by every other ancestor. Implementations MUST
  support lowering. Support for raising is optional and MUST be declared.
- **I2.8 The number does not depend on who asks.** `effective_confidence(m, s)` returns
  the same value for every scope `s` that may read `m` at all. The walk crosses scope
  boundaries in full (I4.3), so an ancestor a caller cannot read still bounds the answer.
  A scope-relative number would rise as a caller's visibility narrowed, which is §6.4's
  inflation arriving through the grant table.

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
- **`residue`** — *declarable, not a default.* The record is removed completely —
  content, `id`, and edges — and before removal its effective confidence contribution is
  pushed into each surviving descendant as a bare **floor**: a number the descendant now
  carries as a property of itself, with no reference to where it came from. The
  descendant's effective confidence is the minimum of its declared value, its surviving
  chain, and its floor. I2.5 holds, because the floor is exactly the bound the removed
  ancestor was providing.

  Floors MUST compose. When several ancestors of one record are erased under `residue`,
  the record's floor is the minimum of the floors each removal contributed, so the order
  of the removals does not change the result. A record's floor MUST survive a reopen
  (I1.5) and MUST propagate to that record's own descendants through the ordinary
  weakest-link walk, since it participates in `effective` like any other bound.

  `residue` is the mode for a deletion obligation that has to be honoured without
  inflating anything downstream. What it costs is in §6.4.

### 6.2 Universal post-conditions

Independent of mode, after `forget(x)`:

- **I3.1** `get(x)` returns `Forgotten`, never content.
- **I3.2** `x` does not appear in `list_scope`.
- **I3.3** `forget(x)` is idempotent. A second call succeeds and changes nothing. A
  repeat call returns a receipt whose mode is the mode originally applied and whose
  affected-id sets are empty. A repeat call naming a *different* mode does not apply that
  mode. "Changes nothing" has to include not changing the mode: otherwise
  `forget(x, tombstone); forget(x, cascade)` would destroy descendants that survived the
  first call, which is non-idempotent in the only way that matters.
- **I3.4** No resurrection. Writing a new record with identical content does not restore
  `x`'s identifier, chain position, or descendants.
- **I3.5** The operation returns a receipt naming the mode, the affected ids, and the
  effective-confidence delta for **every** surviving descendant, including descendants
  whose effective confidence did not change. This makes the receipt self-checking: the
  delta set is exactly the surviving descendants, so a descendant the implementation
  failed to recompute is visible as a missing row rather than as a silent zero. Under
  `tombstone` the receipt is a list of zero deltas, which is the correct claim —
  nothing moved, and the implementation looked.

Two further post-conditions govern what a forgotten record can still do:

- A tombstoned record remains walkable: `provenance` and `effective_confidence` answer
  for it, since §6.1 retains its `declared_confidence` and `sources`. For a record
  removed by `cascade`, `erase`, or `residue`, those operations fail. `get` returns
  `Forgotten` in every case. Returning an empty chain for a removed record would let a
  caller read a deleted record as a root with no ancestors, which is erasure inflation
  arriving by a different route.
- A write MUST NOT cite a forgotten record, including a tombstone. A tombstone retains
  its chain position for records that already cited it; it does not accept new ones. A
  new derivative of a tombstone claims to be derived from content that has been erased,
  which no one can audit, and it grows the set of records a deletion request failed to
  reach *after* the request was honoured. A writer who genuinely wants the citation can
  cite whatever the tombstone's own sources were.

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

This specification does not resolve the tension. It is recorded here because each
available resolution costs something real:

- **Tombstone everything.** Chain arithmetic stays correct, but a tombstone is a
  retained record about a subject who asked to be forgotten. Whether that satisfies a
  deletion obligation is a legal question, not an engineering one.
- **Cascade always.** Deleting one source destroys unrelated downstream work.
- **Recompute derivatives to zero.** Defensible, but it means an unrelated forget
  request can silently zero out conclusions no one asked about.
- **`residue`.** The floor keeps the number honest and retains nothing about the removed
  record. What it costs is explanation: the descendant is capped and can no longer say
  by what. A reader who asks "why is this 0.4 when everything in its chain is above 0.9"
  has no answer inside the store, which is a worse position than a tombstone leaves them
  in. And a floor is itself a small inference leak — in a graph of two or three records,
  a floor that appears at the moment a deletion request is honoured says something about
  the deleted record's declared confidence. That leak shrinks as the graph grows and does
  not vanish.

Implementations MUST declare which they chose. The conformance suite records the
divergence rather than scoring it.

---

## 7. P4 — Isolation when agents share state

**Statement.** Agents operating in separate scopes cannot read each other's memories by
default, cannot corrupt each other's chains, and cannot use provenance as a side channel
around the boundary.

**Invariants.**

- **I4.1 Read isolation.** A record written in scope A is not returned by any read in
  scope B absent an explicit grant. A record not visible to the calling scope is
  indistinguishable from an id that never existed, for every operation and not only for
  reads: `get` returns `NotFound`, and `provenance`, `effective_confidence`,
  `descendants`, `revise`, `revisions`, and `forget` fail exactly as they would for an
  unassigned id. This includes a record that has been forgotten. §3.1 says why, and gives
  the one remaining scope error: mutating a record made *visible* by a grant, which the
  caller can already read.
- **I4.2 Explicit sharing.** Cross-scope visibility requires a recorded grant, made by
  `grant` and observable through `grants`. Grants are revocable and revocation is
  immediate.
- **I4.3 Opaque ancestors.** A record in B derived from a record in A retains the
  ancestor's `id` and its confidence contribution, but not its content. Provenance
  remains complete (I1.4) without leaking payload. An ancestor in another scope is
  opaque whether or not a grant exists: content is obtained by reading the record, not by
  walking to it. This keeps a walk's shape independent of the grant table, so a
  revocation cannot change the meaning of a chain a caller already holds, and a walk
  cannot be used to enumerate what a grant covers.
- **I4.4 Cross-scope forget.** Forgetting in A applies the declared mode to descendants
  in B. Isolation is not an excuse to leave derivatives untouched. A cross-scope forget
  returns one receipt, not two. The receipt names affected ids in every scope, together
  with the scope each id belongs to. This is the only operation that reports ids outside
  the calling scope, and it does so only for ids the call itself affected.
- **I4.5 Concurrent consistency.** Interleaved writes from N agents produce one
  well-formed DAG, with no lost edges and no cycles. Conformance is demonstrated by
  replaying enumerated interleavings, not by concurrent execution, so that a failure is
  reproducible from the schedule rather than from a scheduler.

`list_scope(s)` returns the records native to `s`. A record made visible by a grant is
readable by id and is not listed: a grant conveys read access to a record, not membership
of a scope. This keeps `list_scope` meaning one thing — what this scope owns — which is
what I3.2 and P3.4 rely on.

**Conformance checks.**

| ID | Check | Required outcome |
|---|---|---|
| P4.1 | Write in A, list in B | Absent |
| P4.2 | Grant, read, revoke, read | Visible then absent |
| P4.3 | Cross-scope derivation, walk from B | Ancestor id present, content withheld |
| P4.4 | Forget in A with descendants in B | Declared mode applied across the boundary |
| P4.5 | Replay a fixed set of interleaved write schedules, each a valid topological order of one plan | Every schedule produces the same DAG: same edges, no cycles, no lost edges |

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
  "durability": "round-trip"
}
```

`durability` is one of:

- **`in-memory`** — state does not survive the process. There is no reopen to perform, so
  the implementation **fails** P1.5. This is a real gap, not an exemption: I1.5 is an
  invariant, and a store that loses provenance on restart does not satisfy it. §9 has no
  not-applicable state.
- **`round-trip`** — state can be serialised to a snapshot and reopened from it. The
  snapshot exposes `id` and `sources` per record (I1.5), and reopening one whose edges
  contain a cycle is rejected (P1.7).
- **`durable`** — state survives a process restart without an explicit serialise. Such an
  implementation still exposes a snapshot for P1.7, because the acyclicity check has to
  remain falsifiable somewhere.

`revision` is `logged` when `revisions` returns a history, and `none` when it does not —
in which case the implementation fails P2.6. `revision_raise_supported` declares whether
`revise` accepts a value above the current one (I2.7).

A declaration MUST be serialisable to canonical JSON — sorted keys, sorted set-valued
fields, fixed separators — and MUST state every field in this section explicitly. An
omitted field is not a default: a checker that cannot read a field MUST report the
declaration as invalid rather than assume a value for it. Two declarations are meant to be
compared, by a reader and by a diff, and an unordered set or an implied default makes both
comparisons unreliable.

---

## 9. Result states

The suite reports three states, not two.

- **PASS** — the required outcome was produced.
- **FAIL** — the required outcome was not produced and the implementation did not
  declare an exemption.
- **DIVERGENCE** — the implementation declared behavior that this specification
  deliberately leaves open, and behaved consistently with its declaration. P2.5 under
  `erase` is a divergence, not a failure.

A check that did not run is reported as FAIL. There is no not-applicable state; a check
that cannot apply to a class of implementation is a defect in this specification, to be
fixed here rather than absorbed by a suite. The failure mode this rule exists to prevent
is a suite reporting a comfortable result for something it did not measure, and
"not applicable" is the politest form of that.

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
8. Does `residue` need to say how a floor is presented to a reader? §6.1 makes the floor
   observable through `effective_confidence` and nothing else, which is what makes it a
   bare floor rather than a tombstone by another name. A reader who cannot ask "why" may
   be worse off than one told "an ancestor was deleted".

---

## Changelog

- **0.4 (draft)** — the nineteen entries in `design-notes/spec-feedback.md`, folded in.
  §3 grows from eight operations to twelve: `revisions` (entry 1) and `grant` / `revoke`
  / `grants` (entry 2), and gains an error-vocabulary table (§3.1). §8 defines the
  `durability` vocabulary, with `in-memory` failing P1.5 rather than being excused
  (entry 3), and the example declaration is corrected to `round-trip` and given the
  revision fields (entry 4). P1.1 is split: the write-side check becomes "citing an id
  that has not been assigned", the snapshot-side check is the new P1.7, and I1.1 gains
  the construction corollary (entry 5). I4.1 makes an invisible record indistinguishable
  from a nonexistent one for every operation, which leaves the scope error reachable only
  for a record a grant has already made readable (entry 6, entry 20). I4.3 fixes an
  ancestor as opaque regardless of grant (entry 7). I1.6 treats
  an unreadable source as unresolvable, indistinguishably (entry 8). I3.5 requires a
  delta for every surviving descendant (entry 9). I3.3 specifies the repeat receipt
  (entry 10). §6.2 says what `provenance` does for a tombstone and for a removed record
  (entry 11), and forbids deriving from a forgotten record (entry 12). §3 says `revise`
  fails on a forgotten record (entry 13). I4.4 makes the forget receipt the one operation
  that names ids outside the calling scope (entry 14). §7 says `list_scope` lists native
  records only (entry 15). §9 states that an unrun check is a FAIL and that there is no
  not-applicable state (entry 16). P1.5 defines "byte-identical" (entry 17). P4.5 is
  restated as replayed interleavings (entry 18). §5 requires checks to be written against
  the declared `empty_chain_convention` (entry 19). New in this revision and not from a
  feedback entry: a fourth declarable forget mode, `residue` (§6.1, §6.4, open question
  8). Twenty-three numbered checks become twenty-four.

  Raised against this revision and applied to it: §3.1 leaves exactly one reachable scope
  error and fixes the order in which failures are reported (entry 20); §4 says why P1.7 took
  a new id rather than displacing P1.2–P1.6 (entry 21); the new **I2.8** makes effective
  confidence scope-invariant (entry 22); §6.1's `residue` is noted as declarable without
  being independently checkable, with a `floors` reader and two checks proposed for a later
  revision (entry 23); §8 gains a serialisation requirement so two declarations can be
  compared byte for byte (entry 24).
- **0.3** — `revise` added as an eighth operation, closing the hole that made I2.2
  untestable. Revisions must be recorded (I2.6) and are directionally asymmetric (I2.7).
  Checks P2.6 and P2.7 added.
- **0.2** — strict writes (I1.6, P1.6). External origins as root records (§2.1).
  Judgments expressed as derived records rather than typed edges (§2.2). Conflict
  detection reframed in §10. Two open questions added.
- **0.1** — initial draft. Four properties, three forget modes, three result states.
