# Spec feedback

Every place the specification was ambiguous, silent, or self-contradicting while this
repository was built. Each entry names the section, what could not be decided from the text,
what was implemented, why, and proposed replacement text.

**Entries 1–19** were raised against `version1/SPEC.md` (v0.3) during Phase 0, and that file
was not edited: it is frozen as the version the first results were produced against. All
nineteen are folded into `version2/SPEC.md` (v0.4 draft), some as modified — see its
changelog. **Entries 20 onwards** were raised against v0.4 itself, and each is applied to
`version2/SPEC.md` directly.

Where a reading was available that rejects more, asserts more, or inflates less, that is
the one implemented. **Nothing here is blocking**: every entry had a conservative reading
that let the build continue, and no check is implemented twice behind a capability flag.

Entries 1–4 are holes in the operation set — a required invariant with no operation that
can observe it. Those are the ones worth fixing before v0.4, because a reader can conclude
from §3 that a conforming implementation is smaller than it has to be.

---

## 1. §3 — I2.6 requires a retained revision history and no operation reads it

**Unclear.** I2.6 requires that a revision be recorded, and P2.6 is "read revision history
after a revise → prior value, new value, and reason present". §3 lists `revise`, which
returns a receipt for the call being made, and no reader. A caller who did not hold the
receipt from the original call has no way to obtain it, so P2.6 is unverifiable against the
operation set as written.

**Choice.** Added `revisions(id, scope) -> tuple[RevisionReceipt, ...]`, oldest first, to
`amr/protocol.py`, and P2.6 checks it. Two revisions are made and the whole log is
asserted, not just the last entry.

**Why.** "Recorded" that cannot be read is indistinguishable from "not recorded". Returning
the receipt from `revise` covers an audit that was watching at the time; the point of I2.6
is an audit that was not.

**Proposed text.** In the §3 operation block:

```
revisions(id, scope)                                -> ordered revision receipts
```

and in §5: "`revisions` returns every revision of a record, oldest first. A receipt
returned by `revise` and the corresponding entry from `revisions` carry the same before
value, after value, and reason."

---

## 2. §3 — I4.2 requires recorded, revocable grants and no operation records one

**Unclear.** I4.2: "Cross-scope visibility requires a recorded grant. Grants are revocable
and revocation is immediate." P4.2 is "grant, read, revoke, read → visible then absent".
There is no `grant`, no `revoke`, and no way to list what has been granted.

**Choice.** Defined them as an optional protocol in `amr/extensions.py`
(`ScopeSharing`: `grant`, `revoke`, `grants`), feature-detected with `isinstance` in the
P4.2 check rather than added to the §3 set. A system that does not implement it fails P4.2
rather than being excused, because I4.2 is not optional.

**Why.** §3 is the specified operation set and this build does not get to expand it. But a
check for a required invariant cannot be omitted either, so the mechanism lives beside the
protocol and the invariant stays enforced.

**Proposed text.** Either add to §3:

```
grant(owner_scope, reader_scope)                     -> grant receipt
revoke(owner_scope, reader_scope)                    -> grant receipt
grants(owner_scope)                                  -> set of reader scope
```

or state in §7 that grant administration is out of band and name the observable that P4.2
tests instead. The current text requires the behaviour and hides the mechanism.

---

## 3. §4 — P1.5 requires a store reopen and nothing in the specification can reopen a store

**Unclear.** P1.5 is "walk after store reopen → byte-identical chain". No operation closes
or reopens a store, and §8's `durability` field is not defined as a set of values.

**Choice.** An optional `Reopenable` protocol (`to_dict`, `reopen`) in
`amr/extensions.py`. `ReferenceSystem` serialises to canonical JSON and reopens from
it, declaring `durability: "round-trip"`. P1.5 compares a canonical serialisation of the
chain before and after the reopen, byte for byte.

**Why.** A round trip through a serialisation is the weakest thing that can honestly be
called a reopen, and it catches what P1.5 is aimed at: ordering that depends on insertion
history, edges reconstructed from a memo instead of the graph, floats that survive to a
different precision. Keeping a database out of the reference implementation keeps the
dependency list at zero.

**Proposed text.** In §8, define the field: "`durability` is one of `in-memory` (state does
not survive the process, and P1.5 is not applicable), `round-trip` (state can be serialised
and reopened), or `durable` (state survives a process restart without an explicit
serialise). An implementation declaring `in-memory` reports P1.5 as not applicable, and the
suite records it as a gap rather than a pass."

---

## 4. §8 — the example declaration says `in-memory`, which contradicts P1.5

**Unclear.** The example declaration in §8 is the reference system, and it declares
`"durability": "in-memory"`. The same specification requires that system to pass "walk
after store reopen". An in-memory store has no reopen.

**Choice.** `ReferenceSystem` declares `round-trip`. Entry 3 defines the vocabulary.

**Why.** Of the two, the check is load-bearing and the example is illustrative. Changing
the check to match the example would delete the only conformance check that catches
persistence bugs.

**Proposed text.** Change the `durability` value in the §8 example to `"round-trip"`.

---

## 5. §4 — P1.1 "write a cycle-forming record" is unfalsifiable at the write boundary

**Unclear.** With ids assigned by the store on write, and I1.6 rejecting any write whose
sources do not all resolve, no sequence of `write` calls can construct a cycle: a source
must already exist to be cited, so every edge points strictly backwards. P1.1 asks for a
rejection of something that cannot be requested.

**Choice.** P1.1 checks the only cycle-closing construction actually reachable through the
operation set — citing an identifier that has not been assigned yet, which is how a caller
would attempt to close a loop — and asserts it is rejected. It also asserts that `revise`
does not change `sources` (the other way a cycle could appear) and that returned chains are
acyclic. The store keeps a defensive cycle check on the write path and validates acyclicity
on deserialisation, so a caller-supplied-id implementation inherits a real check.

**Why.** The invariant is worth stating; the check as written cannot fail for a conforming
implementation of §3. Deleting it would lose the guarantee for implementations where ids are
caller-supplied.

**Proposed text.** Replace the P1.1 row with two: "Write citing an id that has not been
assigned → Rejected" and "Deserialise a store containing a cycle → Rejected", and add to
I1.1: "Where identifiers are assigned by the store and writes are strict (I1.6), acyclicity
is a property of the construction rather than of a check. An implementation accepting
caller-supplied identifiers MUST reject a write that would close a cycle."

---

## 6. §7 — I4.1 does not say whether an invisible record is `NotFound` or an error

**Unclear.** "A record written in scope A is not returned by any read in scope B absent an
explicit grant." Not returned how — `NotFound`, or a permission error? §6.2/I3.1 makes
`Forgotten` and `NotFound` distinct, so the difference between answers is clearly material
here.

**Choice.** For reads, invisible is indistinguishable from nonexistent: `get` returns
`NOT_FOUND`, and a forgotten record in another scope also returns `NOT_FOUND` rather than
`FORGOTTEN`. For operations that mutate or walk (`revise`, `forget`, `provenance`), a
`ScopeError` is raised naming the boundary.

**Why.** The conservative reading. A permission error on a read is an existence oracle: B
learns that some id exists in A, which is exactly the side channel §7's statement rules out.
Mutations are different — the caller holds an id it believes it owns, and a silent
`NotFound` there hides a bug in the caller.

**Proposed text.** Add to I4.1: "A read of a record not visible to the reading scope returns
`NotFound`. It MUST NOT be distinguishable from a read of an id that never existed,
including for a record that has been forgotten."

---

## 7. §7 — I4.3 does not say whether a grant makes an ancestor transparent

**Unclear.** I4.3 requires a cross-scope ancestor to keep its id and confidence
contribution but not its content. If B has been granted read access to A, is that ancestor
still opaque in a walk from B?

**Choice.** Always opaque. The grant governs `get`; the walk withholds content regardless.

**Why.** Conservative: withholds more. It also keeps a provenance walk's shape independent
of the grant table, so a revocation cannot change the meaning of a chain a caller already
holds, and a walk cannot be used to enumerate what a grant covers. B can still call `get`
on the ancestor id and receive the content while the grant lasts, so nothing is lost.

**Proposed text.** Add to I4.3: "An ancestor in another scope is opaque whether or not a
grant exists. Content is obtained by reading the record, not by walking to it."

---

## 8. §4/§7 — may a write cite a source that exists but is not readable by the writer?

**Unclear.** I1.6 rejects a write citing "an unresolvable source id". I4.1 makes another
scope's record unreadable. Is such an id unresolvable, or resolvable-but-forbidden?

**Choice.** Unresolvable: the write raises the same `UnresolvedSourceError` as a
nonexistent id, with a message that does not distinguish the two. Nothing is persisted.

**Why.** Rejecting more, and consistent with entry 6. If the write succeeded, B could pin
A's record in place (a cascade in A would now have to touch B) and could probe A's id space
by watching which writes succeed. If the write failed with a distinguishable error, the
probe still works.

**Proposed text.** Add to I1.6: "A source id that exists but is not readable by the writing
scope is unresolvable for the purposes of this invariant, and the rejection MUST NOT be
distinguishable from the rejection of an id that does not exist."

---

## 9. §6.2 — I3.5 "the delta for each surviving descendant": all, or only those that moved?

**Unclear.** "a receipt naming the mode, the affected ids, and the effective-confidence
delta for each surviving descendant." A descendant whose value did not change has a delta
of zero — is it in the receipt?

**Choice.** Every surviving descendant appears, including those where `before == after`.

**Why.** Asserts more. It also makes the receipt self-checking: P3.5 can assert that the
delta set is exactly the surviving descendants, which catches a descendant the
implementation failed to recompute. Under `tombstone` this means a receipt full of zero
deltas, which is the correct claim: nothing moved, and the implementation looked.

**Proposed text.** Change I3.5 to: "…and the effective-confidence delta for every surviving
descendant, including descendants whose effective confidence did not change."

---

## 10. §6.2 — I3.3 does not say what the second forget's receipt contains

**Unclear.** "`forget(x)` is idempotent. A second call succeeds and changes nothing."
Succeeds returning what? And if the second call names a *different* mode from the first,
which mode does the receipt report?

**Choice.** The second call returns a receipt reporting the mode that was originally
applied, with empty `forgotten` and `tombstoned` sets and no deltas, and applies nothing.
A second call naming a different mode does not re-forget under the new mode.

**Why.** "Changes nothing" has to include not changing the mode. The alternative — the
second call re-applying a stronger mode — makes `forget` non-idempotent in the only way that
matters: `forget(x, tombstone); forget(x, cascade)` would destroy descendants that survived
the first call. Empty sets rather than a repeat of the original sets keeps "what this call
did" honest.

**Proposed text.** Add to I3.3: "A repeat call returns a receipt whose mode is the mode
originally applied and whose affected-id sets are empty. A repeat call naming a different
mode does not apply that mode."

---

## 11. §6 — is `provenance` legal on a forgotten record?

**Unclear.** I3.1 defines `get` on a forgotten record. Nothing says what `provenance`,
`effective_confidence`, or `descendants` do. Under `tombstone` the record still has a chain
position; under `cascade` and `erase` the record is gone.

**Choice.** A tombstone is walkable: `provenance` and `effective_confidence` answer, because
§6.1 says its `declared_confidence` and `sources` are retained and participate in the
arithmetic. A record removed by `cascade` or `erase` raises `ForgottenRecordError`. `get`
still answers `Forgotten` in both cases.

**Why.** Follows from §6.1 rather than being a new decision, and the error is the
conservative choice for the removed case: returning an empty chain would let a caller read a
deleted record as a root with no ancestors, which is entry 4 of the taxonomy arriving by a
different route.

**Proposed text.** Add to §6.2: "A tombstoned record remains walkable: `provenance` and
`effective_confidence` answer for it, since §6.1 retains its `declared_confidence` and
`sources`. For a record removed by `cascade` or `erase`, those operations fail. `get`
returns `Forgotten` in both cases."

---

## 12. §6.1 — may a new record be derived from a tombstone?

**Unclear.** A tombstone resolves, participates in arithmetic, and is never readable. I1.6
requires sources to resolve. So a write citing a tombstone satisfies I1.6 by the letter.

**Choice.** Rejected (`ForgottenRecordError`).

**Why.** Rejects more. A new derivative of a tombstone claims to be derived from content
that has been erased, which no one can audit, and it grows the set of records a deletion
request has failed to reach after the request was honoured. If the citation is genuinely
wanted, the writer can cite whatever the tombstone's own sources were.

**Proposed text.** Add to §6.2: "A write MUST NOT cite a forgotten record, including a
tombstone. A tombstone retains its chain position for records that already cited it; it does
not accept new ones."

---

## 13. §3 — is `revise` legal on a forgotten record?

**Unclear.** `revise` changes declared confidence. A tombstone retains its declared
confidence, so revising one is arithmetically meaningful.

**Choice.** Rejected (`ForgottenRecordError`), for a tombstone and for a removed record
alike. The error is chosen before the ownership check, so a caller revising a forgotten
record it owns is told the record is forgotten rather than pointed at a scope boundary.

**Why.** Rejects more, and "forgotten" should be terminal for a record's declared state.
Revising a tombstone would produce a revision log entry about a record whose content no
longer exists.

**Proposed text.** Extend the §3 note on `revise`: "`revise` fails for a forgotten record,
including a tombstone."

---

## 14. §3/§7 — `descendants` is scope-filtered but I4.4 needs a receipt that is not

**Unclear.** `descendants(id, scope)` is a scoped read, so under I4.1 it cannot name a
descendant in another scope. I4.4 requires a cross-scope forget to apply the declared mode
to descendants in B, and I3.5 requires the receipt to name the affected ids — which are in B.

**Choice.** `descendants` returns only what the viewing scope can see. The forget receipt is
complete regardless of scope, and carries `affected_scopes`: the scope of every id it names,
sorted by id.

**Why.** Both invariants are kept without weakening either. A caller who forgets a record it
owns is entitled to know the full consequence — that is the point of a receipt — while an
ordinary read stays inside the boundary. Naming the scope alongside each id makes the
crossing explicit rather than implied.

**Proposed text.** Add to I4.4: "A cross-scope forget returns one receipt, not two. The
receipt names affected ids in every scope, together with the scope each id belongs to. This
is the only operation that reports ids outside the calling scope, and it does so only for
ids the call itself affected."

---

## 15. §7 — does `list_scope` include records granted from another scope?

**Unclear.** I4.1 says a record in A is "not returned by any read in scope B absent an
explicit grant". `list_scope` is a read. With a grant in place, does B's `list_scope`
include A's record?

**Choice.** No. `list_scope(B)` returns records native to B. A granted record is readable by
id and is not listed.

**Why.** The narrower reading, and it keeps `list_scope` meaning one thing — "what this scope
owns" — which is what I3.2 ("`x` does not appear in `list_scope`") and P3.4 rely on. A grant
conveys read access to a record, not membership of a scope.

**Proposed text.** Add to §7: "`list_scope(s)` returns the records native to `s`. A record
made visible by a grant is readable by id but is not listed by the reading scope."

---

## 16. §9 — how is an unrun check reported?

**Unclear.** Three states are defined, none of which is "did not run". A check that a system
cannot support has no representation.

**Choice.** A skipped or unrun check is a FAIL, and `amr` additionally reports a
`missing_checks` list — a numbered check the specification declares that no test reported —
which fails `make reproduce` as a suite defect rather than a system one.

**Why.** The failure mode this whole repository exists to make visible is a suite that
reports a comfortable result for something it did not measure. "Not applicable" is the
politest form of that.

**Proposed text.** Add to §9: "A check that did not run is reported as FAIL. There is no
not-applicable state; a check that cannot apply to a class of implementation is a defect in
this specification, to be fixed here rather than absorbed by a suite."

---

## 17. §4 — P1.5 "byte-identical chain" does not say bytes of what

**Unclear.** A provenance walk returns a graph. Two graphs can be equal without any
canonical byte representation being defined.

**Choice.** Canonical JSON of the chain: node ids sorted, `sources` sorted within each node,
fixed separators, the tombstoned and opaque flags included. Compared as bytes before and
after the reopen.

**Why.** A structural comparison would pass while iteration order changed, and iteration
order is exactly the thing a persistence layer perturbs.

**Proposed text.** Add to P1.5: "Byte-identical means a canonical serialisation of the chain
— ancestors in sorted id order, `sources` sorted within each node — is unchanged. An
implementation MAY define its own canonical form provided it is stable across reopens."

---

## 18. §7 — I4.5 requires concurrency and specifies no way to observe it deterministically

**Unclear.** "Interleaved writes from N agents produce one well-formed DAG, with no lost
edges and no cycles." Actual threads make the result a function of the scheduler, so a suite
built on them cannot be deterministic, and a determinism requirement is elsewhere
non-negotiable.

**Choice.** Fixed interleaving schedules, checked in: one write plan across two scopes and
six permutations of it that are all valid topological orders. Each schedule is replayed
against a fresh system and every replay must produce the same DAG shape. No threads.

**Why.** The invariant is about the *result* of an interleaving, not about locking. Replaying
enumerated interleavings tests exactly that, and a failure is reproducible from the schedule
in the file. Threads would test the scheduler.

**Proposed text.** Restate P4.5 as: "Replay a fixed set of interleaved write schedules,
each a valid topological order of one plan → every schedule produces the same DAG: same
edges, no cycles, no lost edges." And add to I4.5: "Conformance is demonstrated by replaying
enumerated interleavings, not by concurrent execution, so that a failure is reproducible."

---

## 19. §5 / open question 1 — `min(∅) = 1.0` is settled here but the check must not assume it

**Not a defect; recorded because it shaped the code.** Open question 1 asks whether `min(∅)`
should be 1.0, 0.0, or undefined, and 1.0 is what produces erasure inflation.

**Choice.** The convention is a declared capability (`empty_chain_convention`), the reference
arithmetic takes it as a parameter, and P2.5 is written as one signed comparison —
`effective_after <= effective_before` — with no branch on forget mode anywhere in the check.
Whether the resulting failure is a DIVERGENCE is decided from the capability declaration,
not from the mode.

**Why.** A system that resolves open question 1 differently must pass P2.5 without the check
being edited, and the divergence must be a property of the declaration rather than something
the check special-cases. A check that says `if mode is erase: expect inflation` proves
nothing about the specification.

**Proposed text.** Add to §5: "`empty_chain_convention` is declared (§8). Checks in this
specification MUST be expressed in terms of the declaration rather than assuming a value."

---

Entries 20–24 were raised while building v0.4, the packaging, and the contamination
scenario against the accepted entries above. Each is applied to `version2/SPEC.md`
directly, as the v0.4 changelog records.

---

## 20. §7 / §3.1 — with invisibility total, is a scope error reachable at all?

**Unclear, and self-contradicting as accepted.** Entry 6, as accepted, makes an invisible
record indistinguishable from a nonexistent one for *every* operation, because a permission
error on any operation is an existence oracle. Taken alone that removes the last case in
which a scope error can be raised: every operation on a record the caller cannot see now
answers `NotFound`. But I4.2 requires that a grant be revocable, and a grant that conveyed
`revise` and `forget` along with `get` would leave `revoke` nothing to take back — the reader
could have forgotten the record already.

**Choice.** `ScopeError` survives with exactly one condition: the target *is* visible to the
caller through a grant, and the caller does not own it. `revise` and `forget` are the only
operations that can raise it, because they are the only two that change existing state.
Ordering is `NotFound` first, then `ForgottenRecordError`, then `ScopeError`, so a caller
learns that a record is forgotten or that it belongs to someone else only if it could have
seen the record at all. The reference raises `LookupError` in every other case an earlier
draft raised a scope error in.

**Why.** This is the one place where the two accepted entries pull in opposite directions,
and the narrow reading satisfies both: it leaks nothing, because it is reachable only once
the caller can already read the record, and it keeps a read grant a grant of reading. The
alternative — collapsing it into `NotFound` too — would tell a caller that the record it
just read does not exist, which asserts something false.

**Proposed text.** Applied: §3.1's `ScopeError` row and the second of its four
consequences; I4.1's closing sentence.

---

## 21. §4 — entry 5 splits P1.1 in two and does not say what the second one is called

**Silent.** Entry 5, as accepted, splits P1.1 into a write-side check (citing an id that has
not been assigned) and a snapshot-side check (a stored graph whose edges contain a cycle),
and says the count becomes 24. It does not say which id the new row takes. Renumbering
P1.2–P1.6 upward would make the ids contiguous by property.

**Choice.** The new row is **P1.7**, appended after the existing P1.6. P1.2 through P1.6
keep the ids they had in v0.3.

**Why.** A check id is a citation. The Phase 0 results in `results/2026-09-09/` name P1.5 and
P1.6, and a poster, a build report, and any third-party result already produced against v0.3
name them too; renumbering would silently repoint every one of those. Contiguity buys
nothing that ordering in the table does not already give a reader. The cost is that P1.7
reads out of place next to P1.1 — which is why §4's table keeps them adjacent in document
order and the id is what carries across versions.

**Proposed text.** Applied: §4's check table gains a P1.7 row at the end, in id order, and
the paragraph below it says that P1.1 and P1.7 are the write-boundary and snapshot-boundary
halves of I1.1 and why the new check took a new id rather than displacing P1.2–P1.6.

---

## 22. §5 / §7 — is effective confidence relative to the scope that asks?

**Silent, and load-bearing.** `effective_confidence(id, scope)` takes a scope. §5 defines the
value as a function of the graph, and I4.3 says a cross-scope ancestor contributes its
confidence without its content, but nothing says whether a caller who cannot read an ancestor
gets a number computed over it anyway. Both readings are available from the text.

**Choice.** The value is scope-invariant: every scope that may read `m` at all gets the same
number, computed over `m`'s full ancestor set, including ancestors the caller may not read.
The scope argument decides *whether* the operation answers, never *what* it answers.

**Why.** The reading that inflates less, by a wide margin. Under the alternative, a record's
effective confidence would rise for a caller with narrower visibility — and would rise again
the moment a grant were revoked, without any write, revision, or forget. That is exactly the
§6.4 failure mode arriving through the grant table, and it would make the number unusable as
a shared quantity between two agents, which is the whole premise of §7. It also makes the
number cheap to check: one value per record, not one per (record, scope) pair.

**Proposed text.** Applied as **I2.8**: "`effective_confidence(m, s)` returns the same value
for every scope `s` that may read `m` at all. The walk crosses scope boundaries in full
(I4.3), so an ancestor a caller cannot read still bounds the answer. A scope-relative number
would rise as a caller's visibility narrowed, which is §6.4's inflation arriving through the
grant table."

---

## 23. §6.1 / §9 — `residue` is declarable and no numbered check can tell it from `erase`

**Silent, and the silence is a defect by entry 16.** §6.1 gains a fourth mode whose whole
claim is that I2.5 holds without retaining anything. §6.3 has five checks, none of which
mentions a floor, and §6.4 prices the mode but does not make it observable. A system could
declare `residue`, implement `erase`, and pass every check in the document.

**Choice.** No new numbered check, and the mode is not implemented here (it is out of scope
for this phase by instruction). What was verified instead is that the existing checks are
already written so that a `residue`-declaring system is measured rather than excused: P2.5 is
the signed comparison `effective_after ≤ effective_before` with no branch on mode, so a
correct `residue` implementation **passes** it and a `residue` declaration over `erase`
behaviour **fails** it — not DIVERGENCE, because §6.4's open tension is what licenses a
divergence and a mode that claims I2.5 holds has declared itself out of that tension. P3.3
and P3.5 already require the declared mode's effect and a delta for every surviving
descendant, so the floor shows up in the receipt. `amr.protocol.ForgetMode` has three members
and would need a fourth before any adapter could declare the mode; that member is deliberately
absent, because adding it while nothing implements it would put an unreachable column in the
matrix.

**Why.** The gap that remains is narrower than a missing check: the floor is observable
through `effective_confidence` and through the receipt, but there is no operation that reads
a record's floor directly, so "the floor composed correctly across two removals" and "the
floor survived a reopen" — both required by §6.1 — can only be inferred from arithmetic. That
is the same class of hole as entries 1 and 2, and it should be closed the same way, by adding
a reader, before any system declares the mode.

**Proposed text.** For a later revision, not applied: add `floors(id, scope) -> float | none`
to §3, and two checks to §6.3 — "P3.6 Forget two ancestors under `residue` in either order"
(same floor, order-independent) and "P3.7 Reopen after a `residue` forget" (floor retained).
Until then §6.1 should say that a system declaring `residue` is conformant only to the extent
its floors are visible in `effective_confidence`.

---

## 24. §8 — the declaration is normative and its serialised shape is not specified

**Silent.** §8 requires a published capability declaration and gives an example, so two
systems' declarations are meant to be compared, and a result file is meant to carry one. The
example is illustrative JSON-ish text: nothing says whether a set-valued field such as
`forget_modes` has an order, or whether an absent field and a null field mean the same thing.

**Choice.** Set-valued fields are serialised sorted, every declared field is present with an
explicit value rather than omitted, and the whole declaration is written as canonical JSON —
sorted keys, fixed separators. Absence is not a value: a capability the system does not
declare is a suite defect, not a default.

**Why.** A declaration is the thing every divergence is adjudicated against, so it has to be
byte-comparable between two runs and between two systems. `make determinism` compares
`raw.json` byte for byte with one field stripped; an unordered set in the declaration would
make that comparison fail intermittently under an unpinned `PYTHONHASHSEED`, which is
precisely the bug the target exists to catch. Treating an absent field as a default would let
a system be scored against capabilities it never claimed.

**Proposed text.** Applied to §8: "A declaration MUST be serialisable to canonical JSON —
sorted keys, sorted set-valued fields, fixed separators — and MUST state every field in this
section explicitly. An omitted field is not a default: a checker that cannot read a field MUST
report the declaration as invalid rather than assume a value for it."
