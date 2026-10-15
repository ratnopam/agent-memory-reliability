# Conformance results

Generated 2026-10-15T23:19:45+00:00 · schema 0.1 · commit `c5551f69e93ab6b01ef1026b47dc73291a4221c9` · Python 3.14.6 on darwin · pytest 9.1.1.

172 tests: 171 PASS, 0 FAIL, 1 DIVERGENCE.

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

Beyond the numbered checks: 32 supplementary checks (mode-independent properties, random-DAG agreement with the reference arithmetic, taxonomy reproductions) and 62 meta checks (one test per specification check id, taxonomy entries matching the code they embed). Both are counted in the totals above.

## Failures

None.

## Divergences

A divergence is behaviour the specification leaves open, in a system whose capability declaration says it behaves that way. It is reported, not scored.

- `P2.5` under `erase` (SPEC.md 6.4) — erase: m003 rose 0.4 -> 0.9 when its weakest ancestor was forgotten; min over the empty chain returns 1.0

## Poster matrix

| Property | tombstone | cascade | erase |
|---|---|---|---|
| P1 — Provenance walk across writes | PASS | PASS | PASS |
| P2 — Confidence cascading along the chain | PASS | PASS | DIVERGENCE |
| P3 — Forget operations | PASS | PASS | PASS |
| P4 — Isolation when agents share state | PASS | PASS | PASS |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **PASS** | **PASS** | **DIVERGENCE** |

## Contamination

Seed 7, 60 rounds, three roles, tau 0.5. One belief declared 0.4 was injected in round 1.

| arm | writes | inherited | inflated (declared ≥ 0.9, effective ≤ tau) | depth |
| --- | --- | --- | --- | --- |
| ungated | 180 | 87 (48%) | 44 (24%) | 9 |
| surfaced | 180 | 9 (5%) | 8 (4%) | 3 |
| gated | 180 | 0 (0%) | 0 (0%) | 0 |

gated is zero by construction at tau=0.5: the injected belief and every descendant are bounded at 0.40 and cannot be cited. The gated bar demonstrates the boundary; the surfaced bar measures what visibility alone achieves.
