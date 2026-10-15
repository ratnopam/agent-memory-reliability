# Conformance results

Generated 2026-10-15T23:20:47+00:00 · schema 0.1 · commit `2ee30b349d2551a94eac8fbabe76abb3eb6378f8` · Python 3.14.6 on darwin · pytest 9.1.1.

387 tests: 349 PASS, 35 FAIL, 3 DIVERGENCE.

## langgraph-layered 0.1.0

Declared: forget modes cascade, erase, tombstone; default `tombstone`; empty chain 1.0; revision `logged`; scopes `native`; cross-scope `opaque-ancestor`; durability `round-trip`.

| Check | Scenario | tombstone | cascade | erase |
|---|---|---|---|---|
| P1.1 | Write citing an id that has not been assigned | PASS | PASS | PASS |
| P1.2 | Three-hop chain, walk from leaf | PASS | PASS | PASS |
| P1.3 | Diamond graph, walk from sink | PASS | PASS | PASS |
| P1.4 | Walk after an ancestor is forgotten | PASS | PASS | PASS |
| P1.5 | Walk after store reopen | PASS | PASS | PASS |
| P1.6 | Write citing an unresolvable source id | PASS | PASS | PASS |
| P1.7 | Deserialise a store containing a cycle | PASS | PASS | PASS |
| P2.1 | Chain 0.4 → 0.9, read leaf | PASS | PASS | PASS |
| P2.2 | Revise root 0.9 → 0.2, read leaf | PASS | PASS | PASS |
| P2.3 | Diamond with one weak ancestor | PASS | PASS | PASS |
| P2.4 | Root with no sources, declared 0.7 | PASS | PASS | PASS |
| P2.5 | Forget weakest ancestor, re-read leaf | PASS | PASS | DIVERGENCE |
| P2.6 | Read revision history after a revise | PASS | PASS | PASS |
| P2.7 | Raise an ancestor above a descendant's declared value | PASS | PASS | PASS |
| P2.8 | Read `effective_confidence` of a record from its owner scope and from a granted reader scope | PASS | PASS | PASS |
| P3.1 | Read a forgotten record | PASS | PASS | PASS |
| P3.2 | Forget twice | PASS | PASS | PASS |
| P3.3 | Forget a mid-chain record | PASS | PASS | PASS |
| P3.4 | Re-write identical content | PASS | PASS | PASS |
| P3.5 | Inspect receipt | PASS | PASS | PASS |
| P4.1 | Write in A, list in B | PASS | PASS | PASS |
| P4.2 | Grant, read, revoke, read | PASS | PASS | PASS |
| P4.3 | Cross-scope derivation, walk from B | PASS | PASS | PASS |
| P4.4 | Forget in A with descendants in B | PASS | PASS | PASS |
| P4.5 | Replay a fixed set of interleaved write schedules, each a valid topological order of one plan | PASS | PASS | PASS |
| P4.6 | Reader with a grant attempts `revise` and `forget` on the owner's record | PASS | PASS | PASS |

## langgraph-store 0.1.0

Declared: forget modes tombstone; default `tombstone`; empty chain 1.0; revision `none`; scopes `native`; cross-scope `rejected`; durability `in-memory`.

| Check | Scenario | tombstone |
|---|---|---|
| P1.1 | Write citing an id that has not been assigned | FAIL |
| P1.2 | Three-hop chain, walk from leaf | FAIL |
| P1.3 | Diamond graph, walk from sink | FAIL |
| P1.4 | Walk after an ancestor is forgotten | FAIL |
| P1.5 | Walk after store reopen | FAIL |
| P1.6 | Write citing an unresolvable source id | FAIL |
| P1.7 | Deserialise a store containing a cycle | FAIL |
| P2.1 | Chain 0.4 → 0.9, read leaf | FAIL |
| P2.2 | Revise root 0.9 → 0.2, read leaf | FAIL |
| P2.3 | Diamond with one weak ancestor | FAIL |
| P2.4 | Root with no sources, declared 0.7 | FAIL |
| P2.5 | Forget weakest ancestor, re-read leaf | FAIL |
| P2.6 | Read revision history after a revise | FAIL |
| P2.7 | Raise an ancestor above a descendant's declared value | FAIL |
| P2.8 | Read `effective_confidence` of a record from its owner scope and from a granted reader scope | FAIL |
| P3.1 | Read a forgotten record | FAIL |
| P3.2 | Forget twice | FAIL |
| P3.3 | Forget a mid-chain record | FAIL |
| P3.4 | Re-write identical content | FAIL |
| P3.5 | Inspect receipt | FAIL |
| P4.1 | Write in A, list in B | PASS |
| P4.2 | Grant, read, revoke, read | FAIL |
| P4.3 | Cross-scope derivation, walk from B | FAIL |
| P4.4 | Forget in A with descendants in B | FAIL |
| P4.5 | Replay a fixed set of interleaved write schedules, each a valid topological order of one plan | FAIL |
| P4.6 | Reader with a grant attempts `revise` and `forget` on the owner's record | FAIL |

## reference 0.1.0

Declared: forget modes cascade, erase, tombstone; default `tombstone`; empty chain 1.0; revision `logged`; scopes `native`; cross-scope `opaque-ancestor`; durability `round-trip`.

| Check | Scenario | tombstone | cascade | erase |
|---|---|---|---|---|
| P1.1 | Write citing an id that has not been assigned | PASS | PASS | PASS |
| P1.2 | Three-hop chain, walk from leaf | PASS | PASS | PASS |
| P1.3 | Diamond graph, walk from sink | PASS | PASS | PASS |
| P1.4 | Walk after an ancestor is forgotten | PASS | PASS | PASS |
| P1.5 | Walk after store reopen | PASS | PASS | PASS |
| P1.6 | Write citing an unresolvable source id | PASS | PASS | PASS |
| P1.7 | Deserialise a store containing a cycle | PASS | PASS | PASS |
| P2.1 | Chain 0.4 → 0.9, read leaf | PASS | PASS | PASS |
| P2.2 | Revise root 0.9 → 0.2, read leaf | PASS | PASS | PASS |
| P2.3 | Diamond with one weak ancestor | PASS | PASS | PASS |
| P2.4 | Root with no sources, declared 0.7 | PASS | PASS | PASS |
| P2.5 | Forget weakest ancestor, re-read leaf | PASS | PASS | DIVERGENCE |
| P2.6 | Read revision history after a revise | PASS | PASS | PASS |
| P2.7 | Raise an ancestor above a descendant's declared value | PASS | PASS | PASS |
| P2.8 | Read `effective_confidence` of a record from its owner scope and from a granted reader scope | PASS | PASS | PASS |
| P3.1 | Read a forgotten record | PASS | PASS | PASS |
| P3.2 | Forget twice | PASS | PASS | PASS |
| P3.3 | Forget a mid-chain record | PASS | PASS | PASS |
| P3.4 | Re-write identical content | PASS | PASS | PASS |
| P3.5 | Inspect receipt | PASS | PASS | PASS |
| P4.1 | Write in A, list in B | PASS | PASS | PASS |
| P4.2 | Grant, read, revoke, read | PASS | PASS | PASS |
| P4.3 | Cross-scope derivation, walk from B | PASS | PASS | PASS |
| P4.4 | Forget in A with descendants in B | PASS | PASS | PASS |
| P4.5 | Replay a fixed set of interleaved write schedules, each a valid topological order of one plan | PASS | PASS | PASS |
| P4.6 | Reader with a grant attempts `revise` and `forget` on the owner's record | PASS | PASS | PASS |

## sqlite 0.1.0

Declared: forget modes cascade, erase, tombstone; default `tombstone`; empty chain 1.0; revision `logged`; scopes `native`; cross-scope `opaque-ancestor`; durability `durable`.

| Check | Scenario | tombstone | cascade | erase |
|---|---|---|---|---|
| P1.1 | Write citing an id that has not been assigned | PASS | PASS | PASS |
| P1.2 | Three-hop chain, walk from leaf | PASS | PASS | PASS |
| P1.3 | Diamond graph, walk from sink | PASS | PASS | PASS |
| P1.4 | Walk after an ancestor is forgotten | PASS | PASS | PASS |
| P1.5 | Walk after store reopen | PASS | PASS | PASS |
| P1.6 | Write citing an unresolvable source id | PASS | PASS | PASS |
| P1.7 | Deserialise a store containing a cycle | PASS | PASS | PASS |
| P2.1 | Chain 0.4 → 0.9, read leaf | PASS | PASS | PASS |
| P2.2 | Revise root 0.9 → 0.2, read leaf | PASS | PASS | PASS |
| P2.3 | Diamond with one weak ancestor | PASS | PASS | PASS |
| P2.4 | Root with no sources, declared 0.7 | PASS | PASS | PASS |
| P2.5 | Forget weakest ancestor, re-read leaf | PASS | PASS | DIVERGENCE |
| P2.6 | Read revision history after a revise | PASS | PASS | PASS |
| P2.7 | Raise an ancestor above a descendant's declared value | PASS | PASS | PASS |
| P2.8 | Read `effective_confidence` of a record from its owner scope and from a granted reader scope | PASS | PASS | PASS |
| P3.1 | Read a forgotten record | PASS | PASS | PASS |
| P3.2 | Forget twice | PASS | PASS | PASS |
| P3.3 | Forget a mid-chain record | PASS | PASS | PASS |
| P3.4 | Re-write identical content | PASS | PASS | PASS |
| P3.5 | Inspect receipt | PASS | PASS | PASS |
| P4.1 | Write in A, list in B | PASS | PASS | PASS |
| P4.2 | Grant, read, revoke, read | PASS | PASS | PASS |
| P4.3 | Cross-scope derivation, walk from B | PASS | PASS | PASS |
| P4.4 | Forget in A with descendants in B | PASS | PASS | PASS |
| P4.5 | Replay a fixed set of interleaved write schedules, each a valid topological order of one plan | PASS | PASS | PASS |
| P4.6 | Reader with a grant attempts `revise` and `forget` on the owner's record | PASS | PASS | PASS |

Beyond the numbered checks: 62 supplementary checks (mode-independent properties, random-DAG agreement with the reference arithmetic, taxonomy reproductions) and 65 meta checks (one test per specification check id, taxonomy entries matching the code they embed). Both are counted in the totals above.

## Failures

- `P1.1` under `tombstone` — Failed: DID NOT RAISE any of (CycleError, UnresolvedSourceError)
- `P1.2` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: provenance is not provided by this store: it stores documents under a namespace and a key and computes nothing…
- `P1.3` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: provenance is not provided by this store: it stores documents under a namespace and a key and computes nothing…
- `P1.4` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `P1.5` under `tombstone` — + where False = isinstance(<systems.langgraph_store.store_alone.StoreAlone object at 0x10bc7df20>, Reopenable)
- `P1.6` under `tombstone` — Failed: DID NOT RAISE UnresolvedSourceError
- `P1.7` under `tombstone` — + where False = isinstance(<systems.langgraph_store.store_alone.StoreAlone object at 0x10bcd9850>, Reopenable)
- `P2.1` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `P2.2` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `P2.3` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `P2.4` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `P2.5` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `P2.6` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: revise is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `P2.7` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `P2.8` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: grant is not provided by this store: it stores documents under a namespace and a key and computes nothing over…
- `P3.1` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `P3.2` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `P3.3` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `P3.4` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `P3.5` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `P4.2` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: grant is not provided by this store: it stores documents under a namespace and a key and computes nothing over…
- `P4.3` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: grant is not provided by this store: it stores documents under a namespace and a key and computes nothing over…
- `P4.4` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: grant is not provided by this store: it stores documents under a namespace and a key and computes nothing over…
- `P4.5` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: grant is not provided by this store: it stores documents under a namespace and a key and computes nothing over…
- `P4.6` under `tombstone` — systems.langgraph_store.store_alone.NotProvided: grant is not provided by this store: it stores documents under a namespace and a key and computes nothing over…
- `test_effective_confidence_is_insertion_order_independent[langgraph-store]` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `test_effective_confidence_is_topological_order_independent[langgraph-store]` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…
- `test_erasure_inflation_reproduces[langgraph-store]` — skipped: an unrun check is not a satisfied check
- `test_forget_removes_the_record_from_its_own_scope_under_every_mode[langgraph-store]` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `test_forget_without_descendants_is_mode_independent[langgraph-store]` — systems.langgraph_store.store_alone.NotProvided: forget is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `test_matches_reference_arithmetic_on_random_dags[langgraph-store]` — systems.langgraph_store.store_alone.NotProvided: provenance is not provided by this store: it stores documents under a namespace and a key and computes nothing…
- `test_not_found_is_raised_as_a_named_type[langgraph-store]` — systems.langgraph_store.store_alone.NotProvided: revise is not provided by this store: it stores documents under a namespace and a key and computes nothing ove…
- `test_orphaned_derivative_is_handled[langgraph-store]` — skipped: an unrun check is not a satisfied check
- `test_silent_chain_truncation_is_handled[langgraph-store]` — assert False is True
- `test_undeclared_derivation_is_out_of_scope[langgraph-store]` — systems.langgraph_store.store_alone.NotProvided: effective_confidence is not provided by this store: it stores documents under a namespace and a key and comput…

## Divergences

A divergence is behaviour the specification leaves open, in a system whose capability declaration says it behaves that way. It is reported, not scored.

- `P2.5` under `erase` (SPEC.md 6.4) — erase: m003 rose 0.4 -> 0.9 when its weakest ancestor was forgotten; min over the empty chain returns 1.0
- `P2.5` under `erase` (SPEC.md 6.4) — erase: m003 rose 0.4 -> 0.9 when its weakest ancestor was forgotten; min over the empty chain returns 1.0
- `P2.5` under `erase` (SPEC.md 6.4) — erase: m003 rose 0.4 -> 0.9 when its weakest ancestor was forgotten; min over the empty chain returns 1.0

## Poster matrix

**langgraph-layered**

| Property | tombstone | cascade | erase |
|---|---|---|---|
| P1 — Provenance walk across writes | PASS | PASS | PASS |
| P2 — Confidence cascading along the chain | PASS | PASS | DIVERGENCE |
| P3 — Forget operations | PASS | PASS | PASS |
| P4 — Isolation when agents share state | PASS | PASS | PASS |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **PASS** | **PASS** | **DIVERGENCE** |

**langgraph-store**

| Property | tombstone |
|---|---|
| P1 — Provenance walk across writes | FAIL |
| P2 — Confidence cascading along the chain | FAIL |
| P3 — Forget operations | FAIL |
| P4 — Isolation when agents share state | FAIL |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **FAIL** |

**reference**

| Property | tombstone | cascade | erase |
|---|---|---|---|
| P1 — Provenance walk across writes | PASS | PASS | PASS |
| P2 — Confidence cascading along the chain | PASS | PASS | DIVERGENCE |
| P3 — Forget operations | PASS | PASS | PASS |
| P4 — Isolation when agents share state | PASS | PASS | PASS |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **PASS** | **PASS** | **DIVERGENCE** |

**sqlite**

| Property | tombstone | cascade | erase |
|---|---|---|---|
| P1 — Provenance walk across writes | PASS | PASS | PASS |
| P2 — Confidence cascading along the chain | PASS | PASS | DIVERGENCE |
| P3 — Forget operations | PASS | PASS | PASS |
| P4 — Isolation when agents share state | PASS | PASS | PASS |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **PASS** | **PASS** | **DIVERGENCE** |
