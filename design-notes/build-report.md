# Phase 0 build report

Built against `version1/SPEC.md` (23 numbered checks). No model is called anywhere in the
measurement path; the suite's only dependency is pytest.

## Built

- **`harness/`** — 10 files, 1,483 lines. `protocol.py` (the operation set every system
  implements, plus `Capabilities`), `extensions.py` (optional `ScopeSharing` and
  `Reopenable` protocols), `registry.py`, `outcomes.py` (PASS / FAIL / DIVERGENCE),
  `runner.py` (runs one pytest session and resolves reports into matrix cells),
  `results.py` (schema 0.1 writer), `report.py` (`summary.md`, plus README drift
  detection), `determinism.py` (two subprocesses, byte comparison), `__main__.py`.
- **`systems/reference/`** — 6 files, 891 lines. Standard library only:
  `store.py` (records, ids, revision log, canonical serialisation), `confidence.py`
  (weakest-link arithmetic, memoised), `forget.py` (tombstone / cascade / erase and the
  receipt), `scope.py` (grants and visibility), `system.py` (the protocol adapter).
- **`properties/`** — 9 files, 1,308 lines. One test per numbered check across
  `test_p1_provenance.py`, `test_p2_confidence.py`, `test_p3_forget.py`,
  `test_p4_isolation.py`; `conftest.py` parameterises over every registered system and
  every forget mode it declares and stamps the cell into `user_properties`;
  `support.py` (reference arithmetic, random-DAG generator with a checked-in seed),
  `interleavings.py` (six fixed schedules for P4.5), `test_spec_coverage.py`
  (a check id in the specification with no test is a failure), `test_taxonomy.py`.
- **`taxonomy/`** — 10 files, 485 lines. Four failure modes — `erasure-inflation.md`,
  `orphaned-derivative.md`, `silent-chain-truncation.md`, `undeclared-derivation.md` —
  each embedding the verbatim source of a `taxonomy/repro/*.py` module the suite imports
  and runs, with the embedded text asserted byte-identical to the code that ran.
- **`mcp/`** — 3 files, 653 lines. `server.py` exposes the reference system as 10 stdio
  tools and translates protocol errors into coded tool errors; `test_server.py` drives a
  real subprocess over the wire (5 tests); `README.md`. Not on the path of any other
  target, and the conformance suite never imports `mcp`.
- **`results/`** — `README.md` (65 lines, schema 0.1 documented field by field) and
  `2026-09-09/{raw.json (712 lines), summary.md (58 lines)}`, generated from a clean tree
  at `8cf7735`.
- **`design-notes/spec-feedback.md`** — 415 lines, 19 numbered entries, none blocking.
- **`DECISIONS.md`** — 140 lines: dependency justifications and every choice a reader
  could reasonably have made differently.
- **`Makefile`** — 67 lines. `help`, `deps`, `test`, `reproduce`, `determinism`, `lint`,
  `mcp-test`, `clean`. A `.venv` is created only if the ambient interpreter lacks pytest.
- **`.github/`** — `workflows/ci.yml` (69 lines: conformance on 3.11 and 3.12 running
  test, reproduce, determinism, lint, an LLM-import grep and the stdlib gate; a separate
  MCP job) and `check_stdlib_only.py` (60 lines, AST walk over `systems/reference/`).
- **`README.md`** — 138 lines, 1,102 words, no badges, no emoji. Problem, the four
  properties, the erasure-inflation worked example, the generated matrix, three-line
  reproduce, how to add a system, how to add a failure mode, positioning against
  retrieval benchmarks, prior art, four limitations.
- Supporting: `conftest.py` (13 lines, the only packaging), `ruff.toml` (17),
  `requirements-dev.txt` (pytest only), `requirements-mcp.txt` (mcp only). 59 tracked
  files in total.

## Test results

82 tests: 81 PASS, 0 FAIL, 1 DIVERGENCE. `make reproduce` exits 0.

Declared by the reference system: forget modes cascade, erase, tombstone; default
`tombstone`; empty chain 1.0; revision `logged`; scopes `native`; cross-scope
`opaque-ancestor`; durability `round-trip`.

| Check | Scenario | tombstone | cascade | erase |
|---|---|---|---|---|
| P1.1 | Write a cycle-forming record | PASS | PASS | PASS |
| P1.2 | Three-hop chain, walk from leaf | PASS | PASS | PASS |
| P1.3 | Diamond graph, walk from sink | PASS | PASS | PASS |
| P1.4 | Walk after an ancestor is forgotten | PASS | PASS | PASS |
| P1.5 | Walk after store reopen | PASS | PASS | PASS |
| P1.6 | Write citing an unresolvable source id | PASS | PASS | PASS |
| P2.1 | Chain 0.4 → 0.9, read leaf | PASS | PASS | PASS |
| P2.2 | Revise root 0.9 → 0.2, read leaf | PASS | PASS | PASS |
| P2.3 | Diamond with one weak ancestor | PASS | PASS | PASS |
| P2.4 | Root with no sources, declared 0.7 | PASS | PASS | PASS |
| P2.5 | Forget weakest ancestor, re-read leaf | PASS | PASS | DIVERGENCE |
| P2.6 | Read revision history after a revise | PASS | PASS | PASS |
| P2.7 | Raise an ancestor above a descendant's declared value | PASS | PASS | PASS |
| P3.1 | Read a forgotten record | PASS | PASS | PASS |
| P3.2 | Forget twice | PASS | PASS | PASS |
| P3.3 | Forget a mid-chain record | PASS | PASS | PASS |
| P3.4 | Re-write identical content | PASS | PASS | PASS |
| P3.5 | Inspect receipt | PASS | PASS | PASS |
| P4.1 | Write in A, list in B | PASS | PASS | PASS |
| P4.2 | Grant, read, revoke, read | PASS | PASS | PASS |
| P4.3 | Cross-scope derivation, walk from B | PASS | PASS | PASS |
| P4.4 | Forget in A with descendants in B | PASS | PASS | PASS |
| P4.5 | Concurrent interleaved writes | PASS | PASS | PASS |

Beyond the numbered checks: 7 supplementary checks (mode-independent properties,
random-DAG agreement with the reference arithmetic, taxonomy reproductions) and 6 meta
checks (one test per specification check id, taxonomy entries matching the code they
embed). Both are counted in the 82.

| Property | tombstone | cascade | erase |
|---|---|---|---|
| P1 — Provenance walk across writes | PASS | PASS | PASS |
| P2 — Confidence cascading along the chain | PASS | PASS | DIVERGENCE |
| P3 — Forget operations | PASS | PASS | PASS |
| P4 — Isolation when agents share state | PASS | PASS | PASS |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **PASS** | **PASS** | **DIVERGENCE** |

The one divergence, as reported: `P2.5` under `erase` (SPEC.md 6.4) — erase: m003 rose
0.4 -> 0.9 when its weakest ancestor was forgotten; min over the empty chain returns 1.0.
P2.5 is a single signed comparison, `effective_after <= effective_before`, with no branch
on forget mode; whether the failed comparison is a DIVERGENCE is decided from the
system's capability declaration.

`make determinism`:

```
determinism: two runs produced byte-identical results
  compared raw.json (ignoring generated_at) and summary.md (ignoring the generated-at line)
  schema 0.1
```

`make lint` → `All checks passed!` (ruff, rules pinned in `ruff.toml`).
`make mcp-test` → 5 passed. `.github/check_stdlib_only.py` →
`systems/reference: standard library only`.

## Spec feedback

19 entries in [spec-feedback.md](spec-feedback.md). **Blocking: zero.** Each names the
section, the ambiguity, the conservative reading taken, why, and proposed specification
text.

1. §3 — I2.6 requires a retained revision history and no operation reads it. Added
   `revisions(id, scope)` to the protocol; P2.6 asserts the whole log, not the last entry.
2. §3 — I4.2 requires recorded, revocable grants and no operation records one. Optional
   `ScopeSharing` protocol, feature-detected; a system without it fails P4.2 rather than
   being excused.
3. §4 — P1.5 requires a store reopen and nothing can reopen a store. Optional
   `Reopenable` protocol; the reference serialises to canonical JSON and declares
   `durability: "round-trip"`.
4. §8 — the example declaration says `in-memory`, which contradicts P1.5. The reference
   declares `round-trip`; the check is load-bearing, the example is illustrative.
5. §4 — P1.1 "write a cycle-forming record" is unfalsifiable at the write boundary. The
   check exercises the only cycle-closing construction reachable through the operation set
   (citing an unassigned id) and asserts `revise` cannot change `sources`.
6. §7 — I4.1 does not say whether an invisible record is NotFound or an error. Reads
   cannot distinguish invisible from nonexistent; mutations and walks raise `ScopeError`.
7. §7 — I4.3 does not say whether a grant makes an ancestor transparent. Always opaque:
   the grant governs `get`, the walk withholds content regardless.
8. §4/§7 — may a write cite a source that exists but is unreadable? No: the same
   `UnresolvedSourceError`, with a message that does not distinguish the two cases.
9. §6.2 — I3.5's "delta for each surviving descendant": every surviving descendant
   appears, including unchanged ones, which makes the receipt self-checking.
10. §6.2 — I3.3 does not say what a second forget's receipt contains. It reports the mode
    originally applied, with empty sets and no deltas, and applies nothing.
11. §6 — is `provenance` legal on a forgotten record? A tombstone is walkable; a record
    removed by cascade or erase raises `ForgottenRecordError`.
12. §6.1 — may a new record be derived from a tombstone? No: rejected.
13. §3 — is `revise` legal on a forgotten record? No, tombstone or removed alike, and the
    forgotten error is chosen before the scope error.
14. §3/§7 — `descendants` is scope-filtered, but I4.4 needs a receipt that is not. The
    receipt is complete regardless of scope and carries `affected_scopes`.
15. §7 — does `list_scope` include granted records? No: a granted record is readable by
    id and is not listed.
16. §9 — how is an unrun check reported? A skipped or unrun check is a FAIL, and
    `missing_checks` fails `make reproduce` as a harness defect.
17. §4 — P1.5's "byte-identical chain" does not say bytes of what. Canonical JSON of the
    chain: sorted ids, sorted sources, fixed separators, flags included.
18. §7 — I4.5 requires concurrency with no deterministic way to observe it. Six
    checked-in interleaving schedules replayed against a fresh system. No threads.
19. §5 / open question 1 — `min(∅) = 1.0` is settled in §5 but the check must not assume
    it. The convention is a declared capability, the arithmetic takes it as a parameter,
    and P2.5 branches on nothing.

## Decisions made

Full text in [DECISIONS.md](../DECISIONS.md).

- pytest is the suite's only dependency; `systems/reference/` is standard library only,
  enforced in CI by an AST walk.
- The MCP server's `mcp` dependency lives in a separate requirements file; the suite never
  imports it and `mcp/test_server.py` begins with an `importorskip`.
- ruff is optional and never imported: `make lint` falls back to pyflakes, then
  `compileall`. `ruff.toml` pins the rule set so a contributor's ruff agrees with CI.
- Nothing else: no hypothesis (checked-in seed instead), no pytest-xdist (ordering would
  stop being deterministic), no coverage tooling.
- One pytest session grouped afterwards, not one session per matrix cell, so `make test`
  and `make reproduce` cannot disagree about what ran.
- pytest rather than a hand-rolled loop, which would be a second implementation of the
  thing that decides whether a check passed.
- A skipped test is a FAIL.
- DIVERGENCE is carried in `user_properties` and rendered by a report hook, never
  `xfail`: an xfail is a claim about a test, a divergence is a claim about a
  specification.
- A divergence does not fail `make reproduce`; a failure does. A red build on a
  divergence would pressure whoever ran it to bury the finding.
- `missing_checks` is a first-class field: the harness treats its own silence as a defect.
- Exactly one volatile field, `generated_at`. No durations, no absolute paths, no
  iteration orders.
- Determinism is checked in two subprocesses with `PYTHONHASHSEED` unpinned; pinning it
  would hide set-iteration dependence rather than surface it.
- `summary.md` is compared too, with its generated-at line stripped.
- The results directory is the UTC date; the commit SHA inside says which tree produced
  it, with a `-dirty` suffix when the tree was edited.
- `summary.md` reads scenarios and property titles out of `SPEC.md` rather than restating
  them, and `make reproduce` fails if `README.md` shows a matrix that differs from the
  generated one.
- Property rows aggregate pessimistically (FAIL > DIVERGENCE > PASS); the P2.5 row is
  printed separately because aggregation is exactly what would hide it.
- One poster matrix per system rather than a merged table.
- Grants and store-reopen are optional protocols in `harness/extensions.py`, not
  additions to the §3 operation set.
- Ids are `m001`, `m002`, … — sequential and readable, so a failing assertion names
  something a reader can find.
- Confidence is lazy and memoised, invalidated for a record and its descendants on write,
  revise, and forget, so eagerness is unobservable.
- A forget receipt reports every surviving descendant, including unchanged ones.
- `revise` validates ownership and forgotten-ness before range-checking the value.
- The root `conftest.py` is the only packaging: no `pyproject.toml`, no editable install.
- `mcp/` has no `__init__.py`, so it cannot shadow the installed `mcp` package.
- The MCP server translates and decides nothing; anything worth arguing about lives in
  `systems/reference/` where the suite can see it.
- `make` targets create a `.venv` only when the ambient interpreter lacks pytest, and
  never write outside the clone.
- Each taxonomy entry embeds the verbatim source of a module the suite runs, asserted
  byte-identical, and the reproductions import `harness.protocol` only.

## Not done

Nothing from §4 is outstanding. Two notes, neither a gap in the deliverables:

- The items §8 places out of scope are absent as instructed: no `systems/memledger/`, no
  contamination simulation, `SPEC.md` unedited, `SPEC-old.md` untouched, `LICENSE`
  unmodified.
- The handoff brief itself is still in the working tree at
  `design-notes/HANDOFF-phase0-build.md`. It is untracked and now `.gitignore`d, because
  it names a system the repository must not mention; nothing tracked, and no commit in
  history, contains that string. It is your file, so I did not delete it — deleting it
  makes the constraint hold for the working tree too.

## Verification

Fresh clone into `/tmp`, ambient Python 3.14.6 with no pytest installed, so `make deps`
built a `.venv` from `requirements-dev.txt` and nothing else. `make reproduce` exited 0
and `make determinism` exited 0 in the same clone. Last twenty lines of the reproduce
transcript:

```
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

wrote results/2026-09-09/raw.json and results/2026-09-09/summary.md — 82 tests, 81 PASS, 0 FAIL, 1 DIVERGENCE
```

The results committed in `results/2026-09-09/` are the bytes that run produced.

## Suggested next steps

1. Decide open question 1 for `version2`: keep `min(∅) = 1.0` and require the receipt to
   flag inflation, or make an erased ancestor leave a confidence-bearing stub. Entry 19
   proposes text for both; the poster is stronger if the specification takes a side.
2. Fold the 19 spec-feedback entries into `version1/SPEC.md` — chiefly the revision
   reader, grants, store reopen, and the durability vocabulary — so the two optional
   protocols in `harness/extensions.py` become normative and P1.5/P2.6/P4.2 stop
   depending on feature detection.
3. Register a second system. The matrix is one column wide, and the argument gets much
   sharper when a real product's capability declaration is next to the reference's; no
   test needs editing.
4. Generate the poster's matrix image from `raw.json` in the same command that writes
   `summary.md`. README drift is already gated; the poster is the one artefact that can
   still show numbers nothing produced.
5. Add 3.13 and 3.14 to the CI matrix (3.14.6 is what the fresh-clone verification above
   ran on) and upload `raw.json` as a build artefact so every commit has a citable record.
