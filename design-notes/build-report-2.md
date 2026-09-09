# Phase 1 build report

Built against `version2/SPEC.md`, draft v0.4 — 24 numbered checks. `version1/SPEC.md` is
untouched and frozen. No model is called anywhere, in the suite or in the simulation; the
package has no runtime dependencies.

## Built

- **`version2/SPEC.md`** — 632 lines, draft v0.4. Copied from v0.3 and rewritten so that all
  nineteen spec-feedback entries are normative text rather than a list of complaints about
  it: §3 grows to **twelve** operations (`revisions`, `grant`, `revoke`, `grants`) and gains
  an error-vocabulary table (§3.1); §8 defines the `durability` vocabulary with `in-memory`
  **failing** P1.5; I1.1 gains the construction corollary and P1.1 splits, so the count is
  **24**; §6.1 gains a fourth declarable mode, `residue`, with composing floors and its cost
  priced in §6.4. The changelog names every entry it folded in and every change that came
  from somewhere else. Five further entries (20–24) were raised against the draft itself and
  applied to it, including a new **I2.8**.
- **Packaging** — `pyproject.toml` (61 lines): distribution `agent-memory-reliability`,
  import name `amr`, version 0.1.0, `requires-python >= 3.11`, `dependencies = []`, `pytest`
  under `[test]` and `mcp` under `[mcp]`, console script `amr`, and
  `[project.entry-points."amr.systems"] reference = "systems.reference:factory"`. `harness/`
  became `src/amr/`; `requirements-dev.txt` and `requirements-mcp.txt` are gone.
- **`src/amr/`** — 13 files, 2,065 lines. New since Phase 0: `paths.py` (repo root and spec
  path, one place), `svg.py` (100 lines of hand-written SVG primitives, hardcoded hex,
  no CSS variables), `demo.py` (the fifteen-line transcript, the aligned text matrix, and the
  standalone SVG matrix). `registry.py` discovers the `amr.systems` entry-point group *and*
  the in-tree `systems/*` packages, deduplicated by name; `report.py` grew `matrix_rows`, one
  aggregation feeding three renderers so the screen and the file cannot disagree;
  `determinism.py` now runs `reproduce` and `contamination` in each of its two subprocesses
  and compares four files; `__main__.py` is the six-subcommand CLI.
- **`scenarios/`** — 4 files, 441 lines. `contamination/run.py` (337) is the simulation:
  three role-scoped agents, twelve rounds, one seed, two arms; `contamination/chart.py` (98)
  renders the two-bar chart. No model, no network, standard library plus `amr`.
- **`examples/erasure_inflation.py`** — 32 lines. Ticket 0.40 → analysis 0.90 → plan 0.95,
  then the same forget under `tombstone` and under `erase`. Three comparable numbers.
- **`properties/`** — two new files. `test_registry.py` (106 lines) installs a throwaway
  distribution into a temp directory and asserts the suite finds it, and that an entry point
  wins over an in-tree package of the same name. `test_examples.py` (56) runs the example in
  a subprocess and asserts its output verbatim. `test_p1_provenance.py` gained P1.7 (a
  snapshot containing a cycle is rejected on deserialise) and `test_p4_isolation.py` gained
  a probe that calls all seven id-taking operations across a scope boundary and asserts that
  what an invisible record returns is indistinguishable, operation by operation, from what an
  id that was never assigned returns.
- **`systems/reference/`** — 5 files, **798** lines, down from 891. `scope.py` folded into
  `store.py`; one serialisation path instead of two; one `_resolve`; shared delta and closure
  helpers. Every test outcome unchanged (see Verification). Standard library only, still
  enforced by `.github/check_stdlib_only.py`.
- **`docs/demo.tape`** — 44 lines of `vhs` script for `docs/demo.gif`: 24pt type, dark
  background, no window chrome, about forty seconds. **The GIF is not committed** — a
  recording nobody generated from the tape is a claim nobody checked. `vhs docs/demo.tape`
  makes it.
- **`Makefile`** — `demo`, `contamination`, and `matrix` added; every target is now a wrapper
  over `amr`, and `deps` installs `-e ".[test]"` into a `.venv` when the ambient interpreter
  lacks pytest.
- **`.github/workflows/ci.yml`** — the conformance job runs on **3.11, 3.12, 3.13, and
  3.14**, installs with `pip install -e ".[test]"` (which is also what exercises the
  entry-point path), runs test / reproduce / contamination / determinism / demo / lint, the
  LLM-import grep and the stdlib gate, and uploads `raw.json`, `summary.md`,
  `contamination.json`, and `contamination.svg` as `results-py<version>` with
  `if-no-files-found: error`.
- **Docs** — `README.md` gained the "How far one bad memory travels" section with the
  contamination table, and its "Add a system" section is now the entry-point TOML.
  `DECISIONS.md` gained a section on the contamination scenario, the narrowed `ScopeError`
  justification, and a rewritten Layout section. `results/README.md` documents
  `contamination.json` field by field.

## Test results

**91 tests: 90 PASS, 0 FAIL, 1 DIVERGENCE.** `make reproduce` exits 0, `missing_checks` is
empty, `test_spec_coverage.py` reports 24 checks mapped one-to-one onto marked tests.

Declared by the reference: forget modes cascade, erase, tombstone; default `tombstone`;
empty chain 1.0; revision `logged`, raising supported; scopes `native`; cross-scope
`opaque-ancestor`; durability `round-trip`.

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
| P3.1 | Read a forgotten record | PASS | PASS | PASS |
| P3.2 | Forget twice | PASS | PASS | PASS |
| P3.3 | Forget a mid-chain record | PASS | PASS | PASS |
| P3.4 | Re-write identical content | PASS | PASS | PASS |
| P3.5 | Inspect receipt | PASS | PASS | PASS |
| P4.1 | Write in A, list in B | PASS | PASS | PASS |
| P4.2 | Grant, read, revoke, read | PASS | PASS | PASS |
| P4.3 | Cross-scope derivation, walk from B | PASS | PASS | PASS |
| P4.4 | Forget in A with descendants in B | PASS | PASS | PASS |
| P4.5 | Replay a fixed set of interleaved write schedules | PASS | PASS | PASS |

Two changes from the Phase 0 matrix, both mandated: P1.1's scenario is now the write-side
half of the split, and **P1.7** is new. Nothing else moved — same outcomes, same one
divergence, in the same cell.

That is 72 cells. Beyond them: 13 supplementary checks — `grant-conveys-reading-only` once
per mode, plus ten whose answer cannot depend on a forget mode (mode-independent properties,
random-DAG agreement with the reference arithmetic, the four taxonomy reproductions, the two
entry-point checks, and the example's transcript) — and 6 meta checks over the specification
and the taxonomy. 72 + 13 + 6 = 91.

`amr demo`, verbatim — **15 lines**, 1.4 seconds wall clock:

```
reference 0.1.0 — 24 checks × 3 forget modes
  forget modes    cascade, erase, tombstone
  empty chain     1.0   durability round-trip
  scopes          native   cross-scope opaque-ancestor

                                              tombstone   cascade     erase
P1 — Provenance walk across writes            PASS        PASS        PASS
P2 — Confidence cascading along the chain     PASS        PASS        DIVERGENCE
P3 — Forget operations                        PASS        PASS        PASS
P4 — Isolation when agents share state        PASS        PASS        PASS
P2.5 — Forget weakest ancestor, re-read leaf  PASS        PASS        DIVERGENCE

- P2.5 under erase (SPEC.md 6.4) — erase: m003 rose 0.4 -> 0.9 when its weakest ancestor was forgotten; min over the empty chain returns 1.0

91 tests: 90 PASS, 0 FAIL, 1 DIVERGENCE
```

`python examples/erasure_inflation.py`, verbatim — asserted byte for byte by
`properties/test_examples.py`:

```
effective(plan), ticket present    0.40
effective(plan), ticket tombstoned 0.40
effective(plan), ticket erased     0.90

The plan was never revised. Erasing its weakest ancestor left min() with an
empty chain, which is 1.0, so the plan rose from 0.40 to 0.90.
```

`make determinism`:

```
determinism: two runs produced byte-identical results
  compared raw.json (ignoring generated_at), summary.md (ignoring the generated-at line),
  and contamination.json and contamination.svg verbatim
  schema 0.1
```

`make lint` → `All checks passed!` (ruff 0.16.6, rules pinned in `ruff.toml`).
`make mcp-test` → 5 passed. `.github/check_stdlib_only.py` →
`systems/reference: standard library only`.

## Contamination results

`amr contamination --seed 7`. Three agents — `support-triage`, `sre`, `platform` — each
owning a scope, with mutual read grants, sharing one reference store for twelve rounds. In
round 1 `support-triage` writes two conflicting beliefs about the same fact, both roots:
`p99 SLO is 250ms` declared 0.95 with origin `runbook`, and `p99 SLO is 400ms` declared 0.40
with origin `chat`. Nothing after that is special-cased. The agents are deterministic
policies over `random.Random(7)`.

```json
"ungated": {
  "denominator": 36,
  "inherited_count": 17, "inherited_fraction": 0.4722,
  "inflated_count": 8,   "inflated_fraction": 0.2222,
  "max_chain_depth": 6,
  "totals": {"rounds": 12, "writes": 36, "reads": 144,
             "strict_write_rejections": 3, "abstentions": 0}
},
"gated": {
  "denominator": 36,
  "inherited_count": 0, "inherited_fraction": 0.0,
  "inflated_count": 0,  "inflated_fraction": 0.0,
  "max_chain_depth": 0,
  "totals": {"rounds": 12, "writes": 36, "reads": 144,
             "strict_write_rejections": 4, "abstentions": 0}
}
```

The number is sensible: with three agents each citing one or two of four sampled memories
per round, a belief injected in round 1 has eleven rounds to spread, so 47% of 36 derived
writes descending from it — down a chain up to six deep — is what compounding at that fan-out
looks like, and the gate reaching zero rather than roughly a third is the point, because it
filters on *effective* confidence and therefore catches the second generation as well as the
first. Two supporting facts: `reads` is 144 in both arms, so the gate is measured against an
identical reading schedule and only citation differs; and 8 of the 36 ungated writes were
declared at 0.9 or above while their effective confidence sat at or below 0.5, which is the
declared-versus-effective gap this repository exists to make visible. The two arms reject a
different number of hallucinated citations (3 versus 4) because `random.sample` consumes a
different amount of randomness from a smaller population, so once the gate narrows what an
agent may cite the two arms stop drawing in lockstep. The seed is shared; the draw sequence is
not. That is expected, and it is why the arms are compared on their measured fractions rather
than write for write.

Reproducibility, checked: `amr contamination --seed 7` twice in separate subprocesses
produces byte-identical `contamination.json` and `contamination.svg`, and `make determinism`
now enforces it. Neither file carries a timestamp, so they are compared verbatim with nothing
stripped.

## Spec feedback

Five new entries, 20–24, in [spec-feedback.md](spec-feedback.md). **Blocking: zero.** All
five are applied to `version2/SPEC.md`; entries 1–19 are the Phase 0 set and are unchanged.

20. **§7 / §3.1 — with invisibility total, is a scope error reachable at all?** Entry 6 as
    accepted removes every observable scope error; I4.2 needs revocation to be able to undo
    something. `ScopeError` survives with exactly one condition — the caller *can* read the
    record through a grant and does not own it — and `revise`/`forget` are the only two
    operations that can raise it. Order is `NotFound`, then forgotten, then scope.
21. **§4 — entry 5 splits P1.1 and does not name the second half.** The new row is **P1.7**,
    appended; P1.2–P1.6 keep their v0.3 ids, because a check id is a citation and results
    already exist that name them.
22. **§5 / §7 — is effective confidence relative to the scope that asks?** Silent, and
    load-bearing for the simulation. It is scope-invariant: the walk crosses boundaries in
    full, so an ancestor a caller cannot read still bounds the answer. The alternative would
    make a number rise when a grant was revoked — §6.4's inflation through the grant table.
    Applied as **I2.8**.
23. **§6.1 / §9 — `residue` is declarable and no numbered check can tell it from `erase`.**
    No new check, and the mode is not implemented (out of scope). What was verified is that
    P2.5 already measures such a system rather than excusing it: a correct `residue`
    implementation passes it, and `residue` declared over `erase` behaviour FAILs rather
    than diverging. The residual gap — no operation reads a record's floor, so composition
    and reopen survival can only be inferred — is the same shape as entries 1 and 2, and a
    `floors` reader plus two checks are proposed for a later revision.
24. **§8 — the declaration is normative and its serialised shape is not specified.** Sets
    sorted, canonical JSON, every field explicit, absence is not a default. Without it,
    `make determinism` would fail intermittently under an unpinned `PYTHONHASHSEED` — which
    is exactly the bug that target exists to catch.

One defect found in the draft while checking the above and fixed in place: §3.1 said "Four
failure signals" over a table of five.

## Decisions

Full text in [DECISIONS.md](../DECISIONS.md); the new ones, briefly.

- The `amr` console script is the interface and the Makefile is a convenience over it, so
  nothing in the repository can only be done by GNU make. Its `--help` is hand-written for a
  terminal rather than reflowed from a module docstring.
- Two discovery sources rather than one: an adapter under development should not have to be
  installed to be run, and a released one should not have to be vendored here. An entry point
  wins over an in-tree package of the same name.
- `properties/test_registry.py` hand-writes a `.dist-info` instead of calling `pip install`,
  because pip's default build isolation fetches setuptools from the network and no test here
  may touch the network.
- `systems/` and `scenarios/` stay at the repository root rather than under `src/amr/`: an
  adapter is a peer of the suite, not a module of it.
- The simulation's agents are policies over a seeded PRNG. Reproducibility is the whole value
  of the number.
- Each role gets its own scope with mutual read grants, so the role labels are not decorative
  and the grant machinery is exercised.
- The gate filters *citation*, not reading — so `reads` is identical across arms and usable as
  a control.
- The inflation metric reads the gate's own `tau` rather than a second hardcoded 0.5, so the
  two numbers cannot drift when `tau` changes.
- Twelve rounds, chosen from a monotone sensitivity series (5/18 at six rounds, 17/36 at
  twelve, 28/60 at twenty, gated flat at zero throughout) recorded in `DECISIONS.md` so the
  choice is auditable rather than flattering.
- `amr demo` renders the matrix as aligned text, not Markdown: the `|---|` rule is noise on a
  filmed terminal and cost the sixteenth line.
- Grants are deliberately not exposed as MCP tools. A client that can widen its own
  visibility is not isolated by anything.
- The committed results are generated in a fresh clone with `--out` outside the tree, so both
  records carry the same clean commit instead of the second command seeing the first one's
  output.

## Not done

- **`systems/reference/` is 798 lines, not ≤600.** This is the one item in §1 that is not
  met. The trim was real — 891 → 798, with `scope.py` folded into `store.py`, one
  serialisation path where there were two, one `_resolve`, and shared delta and closure
  helpers — but the floor is code, not formatting: of the 798 lines, **513 are code**, 135
  are docstrings, 22 are comments, and 128 are blank. Hitting 600 would leave 87 lines for
  every docstring, comment, and blank line across five files that implement twelve
  operations, four forget modes' worth of post-conditions, grants, canonical serialisation,
  and memoised confidence with invalidation. The remaining cuts I could find were all of the
  kind §5 forbids — "if a cut makes a file harder to follow, don't make it" — so I stopped at
  798 and am reporting the number rather than deleting the explanations. The two things §5
  names as untouchable are untouched: the defensive cycle check on the write path and the
  acyclicity validation on deserialise (which is now P1.7's subject).
- **`scenarios/contamination/run.py` is 337 lines against a 200–300 target**, plus 98 in
  `chart.py`. Code-only it is 220, inside the range; the excess is the module docstring
  explaining the three agents and the two arms, and the constant table that is the whole
  input to the simulation. I would rather a reader could see every parameter in one screen
  than hit the line count.
- **`docs/demo.gif` is not committed**, as instructed. `docs/demo.tape` is, and the README
  says who renders it.
- `residue` is not implemented, no adapter for any external system was written, and
  `version1/SPEC.md` and `SPEC-old.md` are untouched — all four as instructed.

## Verification

Fresh clone into `/tmp` from the committed tree at `a47ac75`, ambient Python **3.14.6** with
no pytest, so `make deps` built a `.venv` from the `[test]` extra and nothing else:

```
make test          90 passed, 1 divergence
make reproduce     exit 0 — 91 tests, 90 PASS, 0 FAIL, 1 DIVERGENCE
make contamination ungated 17 (47%) / gated 0 (0%)
make determinism   exit 0 — byte-identical across four files
make demo          15 lines
```

In that clone, `contamination.svg` came out byte-identical to the committed file and
`contamination.json` identical apart from `git_sha` — so the simulation reproduces across
clones, not only across two subprocesses in one tree.

A second clean venv containing only pip: `pip install -e .` installs
`agent-memory-reliability 0.1.0` with no dependencies, `python -c "from amr.protocol import
MemorySystem"` succeeds, the `amr` console script is on the path, and
`amr.registry.systems()` reports `reference` with source `entry-point` — the group, not the
in-tree fallback.

Entry-point discovery from an external package: `properties/test_registry.py` writes a
throwaway distribution with an `entry_points.txt` under `[amr.systems]` into a temp directory,
puts it on `sys.path`, and asserts the suite finds it alongside `reference`, and that when the
two collide on a name the entry point's factory is the one that wins. Both tests pass, and no
edit to this repository was involved in registering it.

**The claim that every test outcome survived the trim**, checked per cell rather than by
diffing two `raw.json` files: the Phase 0 record and the current one share 82 (check, mode)
cells, and **zero outcomes changed** — 81 PASS and the one DIVERGENCE at P2.5/erase, in the
same cell, with the same detail string. The only cells that are new are the ones §2 mandated:
`P1.7` and the supplementary `grant-conveys-reading-only`, one of each per forget mode. A
literal before-and-after diff of the same file is not reconstructible, because the trim was
interleaved with the API changes v0.4's new checks require — the per-cell comparison is the
substantive form of the same claim, and it is the stronger one, since it compares outcomes
rather than bytes that were always going to move.

Greps: the former-name grep (the pre-rename project name, spelled out in neither this report nor
the gate that runs it — see the `Makefile`) returns nothing in tracked files. `git grep -w harness`
returns three files, all prose — `design-notes/build-plan.md` and
`design-notes/build-report.md`, each carrying a "Historical" note at the top saying `harness/`
became `src/amr/`, and the frozen `version1/poster/poster.svg`.

## Suggested next steps

1. **Register a second system.** Everything that was in the way is gone: the entry-point
   group works from an external distribution, the suite is parameterised over every
   registered system, and no test names one. The matrix is still one column wide, and the
   argument is much sharper with a real product's capability declaration beside the
   reference's.
2. **Decide open question 1 for v0.4 final**, now that `residue` is written down and priced.
   The draft leaves the tension open in §6.4 and the poster is stronger if the specification
   takes a side; entry 23 says what a `residue` implementation would additionally have to
   expose to be checkable — a `floors` reader and two checks.
3. **Render `docs/demo.gif`** from the tape and check the fifteen lines fit at 24pt on the
   tablet you intend to use. The tape is untested against a real `vhs`; the sleeps are
   guesses.
4. **Sweep the contamination scenario for a second measurement.** Inheritance and inflation
   are two numbers over the same run; the store can also answer "how many writes cited a
   memory whose effective confidence had moved since it was read", which is the staleness
   question and needs no new machinery.
5. **Take the gate's threshold out of the scenario and into a small policy module** if a
   second scenario is coming. `tau` is currently a constant of `contamination/run.py`; a
   second simulation that wants the same gate would copy it, and the copy would drift.
