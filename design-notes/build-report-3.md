# Phase 2 build report

Built against `version2/SPEC.md`, draft **v0.5** — 26 numbered checks. `version1/SPEC.md` is
untouched and frozen; `SPEC-old.md` is untouched. No model is called anywhere, in the suite,
in the simulation, or in the example adapter; the package still has no runtime dependencies.
The tree is public-ready in the sense the brief asked for: `make release-check` runs ten gates
in one command and is green, in this working tree and in a fresh clone.

## Built

- **`version2/SPEC.md`** — 689 lines, draft 0.5. All nine fixes applied, each logged first as a
  numbered entry in `design-notes/spec-feedback.md` (25–33) and then written into the normative
  text; the changelog entry for 0.5 names every one of them by F-number and by entry number.
  **F1** the forgotten-id set is now retained in *every* mode, which is what makes I3.1 and
  I3.4 statable under `cascade`, `erase` and `residue`, and §6.1's "removed completely —
  content, `id`, and edges" is corrected accordingly. **F2** "recompute derivatives to zero" is
  gone from §6.4's list of resolutions and is open question 10 instead: it was never a
  declarable mode, and listing it beside three that are implied otherwise. **F3** two checks
  added, taking 24 to **26**. **F4** §3's "the only two operations that change state" is
  reworded — it was written before `grant` existed. **F5** `revisions` added to the
  `ForgottenRecordError` and `NotFound` rows of §3.1. **F6** P2.5 gains a note that a mode which
  removed the leaf's ancestor makes the comparison vacuous, and names the receipt (P3.5) as
  where removal is actually verified. **F7** grant granularity is open question 9. **F8** a
  `floor` row in §2 and a three-term `effective` rule in §5, so `residue`'s state appears in
  both the model and the arithmetic. **F9** a system declaring `residue` passes P2.5 unedited.
  F8 and F9 are spec-only by instruction: nothing in `systems/reference/` implements `residue`,
  so neither can be mistaken for a measured claim.
- **Two numbered checks.** `properties/test_p2_confidence.py::test_p2_8_effective_confidence_is_scope_invariant`
  (**P2.8**) reads `effective_confidence` for the same record from the owner scope and from a
  granted reader scope and requires the same float, which is the observable that makes I2.8
  falsifiable. `properties/test_p4_isolation.py::test_p4_6_grant_conveys_reading_only` (**P4.6**)
  is the former supplementary `grant-conveys-reading-only` test, promoted: a reader holding a
  grant attempts `revise` and `forget` and must get `ScopeError` from both, which is the one
  reachable scope error in §3.1. `properties/test_spec_coverage.py` asserts **26** ids parsed
  from the spec map one-to-one onto marked tests, and it passes.
- **`systems/reference/` — 798 lines before, 798 after.** Zero growth, because neither new check
  needed new behaviour: `effective_confidence` was already scope-independent by construction (it
  reads the store's arithmetic, and the scope only decides whether it answers) and `revise` and
  `forget` already raised `ScopeError` for a non-owner. The two checks are new *observations* of
  behaviour the reference already had, which is the outcome a good check has when the
  implementation was written from the same text.
- **A third contamination arm.** `scenarios/contamination/run.py` grew **74 added lines**, under
  the 80-line cap, so the arm abstraction held. `surfaced` sits between the two arms that
  existed: agents see effective confidence and weight selection by it, and nothing is blocked.
  `rounds` is a parameter defaulting to **60**, exposed as `amr contamination --rounds`.
  `scenarios/contamination/chart.py` now draws two panels of three bars with the value printed
  on each bar, still hand-written SVG, no plotting library, no timestamp.
- **`examples/external-adapter/`** — an installable `amr.systems` package: `pyproject.toml`
  (distribution `amr-adapter-example`, one entry point), `capabilities.py` (58 lines, one
  comment per declared field), `adapter.py` (**199 lines**, the twelve operations over one
  `dict`), `__init__.py` (`factory`), and a README that says which two methods are worth copying
  and why. It declares `tombstone` only, `revision: "none"` and `durability: "in-memory"`, so a
  first run shows real failures traceable to lines of the declaration.
- **`properties/test_external_adapter_example.py`** — 140 lines, three tests. It hand-writes the
  `dist-info` an install would have left, puts the example on `PYTHONPATH`, runs the whole suite
  against it in a subprocess with `SYSTEMS=amr-adapter-example`, and asserts the failing set is
  *exactly* what the declaration predicts — no more and no fewer. The subprocess sets
  `AMR_NESTED_RUN`, and the root `conftest.py` adds this file to `collect_ignore` when that
  variable is set, because a run that collects it starts another run, forever. Ignored rather
  than skipped: a skip is counted as a FAIL (`properties/runner.py`), and the inner run's own
  totals are what the outer test asserts on.
- **`docs/adding-a-system.md`** — 1,300 words, six sections: what you are implementing (all
  twelve operations with their error contracts), what you declare and what each field costs in
  matrix cells, the entry point, running the suite against only your system, reading your first
  results, and submitting them.
- **Release surface.** `README.md` (1,399 words) rewritten in the order the brief specified;
  `CONTRIBUTING.md` (two paths in, DCO sign-off, Apache 2.0, one paragraph on what will not be
  merged); `CHANGELOG.md` (one `0.1.0` entry, ten lines); `docs/RELEASE.md` (nine steps, and a
  closing section naming what cannot be closed from inside the repository);
  `.github/ISSUE_TEMPLATE/{spec-feedback.md,new-system.md}`; `.github/check_links.py`;
  `amr drift` as a seventh subcommand with `make drift`; and `make release-check`.
- **CI** gained three steps so that "green locally is green in CI" is true rather than
  aspirational: the former-name grep, `make drift`, and the link check.

## Test results

**97 tests: 96 PASS, 0 FAIL, 1 DIVERGENCE.** `make reproduce` exits 0, `missing_checks` is
empty, `test_spec_coverage.py` reports 26 checks mapped one-to-one onto marked tests, and
`amr demo` still renders in exactly 15 lines.

Declared by the reference, unchanged: forget modes cascade, erase, tombstone; default
`tombstone`; empty chain 1.0; revision `logged`, raising supported; scopes `native`;
cross-scope `opaque-ancestor`; durability `round-trip`.

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
| P2.5 | Forget weakest ancestor, re-read leaf | PASS | PASS | **DIVERGENCE** |
| P2.6 | Read revision history after a revise | PASS | PASS | PASS |
| P2.7 | Raise an ancestor above a descendant's declared value | PASS | PASS | PASS |
| P2.8 | Read `effective_confidence` from owner and from granted reader | PASS | PASS | PASS |
| P3.1 | Read a forgotten record | PASS | PASS | PASS |
| P3.2 | Forget twice | PASS | PASS | PASS |
| P3.3 | Forget a mid-chain record | PASS | PASS | PASS |
| P3.4 | Re-write identical content | PASS | PASS | PASS |
| P3.5 | Inspect receipt | PASS | PASS | PASS |
| P4.1 | Write in A, list in B | PASS | PASS | PASS |
| P4.2 | Grant, read, revoke, read | PASS | PASS | PASS |
| P4.3 | Cross-scope derivation, walk from B | PASS | PASS | PASS |
| P4.4 | Forget in A with descendants in B | PASS | PASS | PASS |
| P4.5 | Replay interleaved write schedules | PASS | PASS | PASS |
| P4.6 | Reader with a grant attempts `revise` and `forget` | PASS | PASS | PASS |

Beyond these, 13 supplementary checks and 6 meta checks, both counted in the totals.

**No regressed cell.** The committed run at `b6eea6c` had 72 cells; this one has 78. Compared
cell by cell: all 72 that existed before have the same outcome, none disappeared, and the six
new ones — P2.8 and P4.6 in each of the three modes — are PASS. The comparison was made
mechanically against `git show b6eea6c:results/2026-09-09/raw.json` rather than by reading two
tables, because reading two tables is how a regression survives.

The one DIVERGENCE is the same one: P2.5 under `erase`, `m003` rising 0.4 → 0.9 when its weakest
ancestor is forgotten, reported by the check as a disagreement with an open question rather than
scored.

## Contamination, three arms

Seed 7, 60 rounds, three roles, τ = 0.5, one belief declared 0.40 injected in round 1.

| arm | writes | reads | inherited the 0.40 belief | declared ≥ 0.9 while effective ≤ 0.5 | depth |
|---|---|---|---|---|---|
| ungated | 180 | 720 | 87 (48%) | 44 (24%) | 9 |
| surfaced | 180 | 720 | 9 (5%) | 8 (4%) | 3 |
| gated (τ = 0.5) | 180 | 720 | 0 (0%) | 0 (0%) | 0 |

All four sanity conditions hold: surfaced inheritance (5%) is strictly between gated (0%) and
ungated (48%); ungated inheritance is strictly positive; reads are identical at 720 in all three
arms, with zero abstentions everywhere, so the arms differ in policy and not in workload; and
`make determinism` reports the two runs byte-identical, `contamination.svg` included.

**Is 5% plausible?** It is the number I would defend, for three reasons. First, it is the right
shape: visibility is a soft policy, so it should reduce inheritance a lot without eliminating it,
and 48% → 5% with depth 9 → 3 is exactly that — the weak belief still gets cited occasionally,
but a chain built on it stops growing, because every derivative it touches is itself weak and
therefore also disfavoured. That compounding is where most of the reduction comes from, not from
the first-hop decision, and it is why the drop is nearly an order of magnitude rather than the
half you might guess from "prefer the stronger source". Second, it cannot be zero by
construction: selection weight is proportional to effective confidence, and 0.40 is a weight, not
a veto, so a run long enough will always cite it — 9 of 180 writes did. Third, the residual
inflation (8 writes, 4%) is the more interesting half of the number: those are writes that
inherited the weak belief and *still* declared ≥ 0.9, which is precisely the failure mode the
repository is about, and no amount of visibility removes it, because the agent that declares 0.9
is not lying about its own confidence — it is failing to propagate someone else's. The gated arm's
zeros are not evidence of anything: at τ = 0.5 the injected belief and every descendant are
bounded at 0.40 and cannot be cited, so the bar can only be zero. The chart caption and the
README say that in those words, because a bar that can only be zero looks like a result and is
not one.

## Adapter kit

The example adapter's matrix, as generated by the suite from the copy in `/tmp` renamed per its
own README (`my-store`, one mode column, exit code 1):

| Check | tombstone |
|---|---|
| P1.1 P1.2 P1.3 P1.4 P1.6 | PASS |
| **P1.5** — walk after store reopen | **FAIL** |
| **P1.7** — deserialise a store containing a cycle | **FAIL** |
| P2.1 P2.2 P2.3 P2.4 P2.5 P2.7 P2.8 | PASS |
| **P2.6** — read revision history after a revise | **FAIL** |
| P3.1 P3.2 P3.3 P3.4 P3.5 | PASS |
| P4.1 P4.2 P4.3 P4.4 P4.5 P4.6 | PASS |

| Property | tombstone |
|---|---|
| P1 — Provenance walk across writes | FAIL |
| P2 — Confidence cascading along the chain | FAIL |
| P3 — Forget operations | PASS |
| P4 — Isolation when agents share state | PASS |
| **P2.5 — Forget weakest ancestor, re-read leaf** | **PASS** |

45 tests: 40 PASS, 5 FAIL, 0 DIVERGENCE. Three numbered failures plus two suite-level ones —
`test_erasure_inflation_reproduces` and `test_orphaned_derivative_is_handled`, which need
`erase` and `cascade` and are therefore skipped, and a skip is a FAIL by entry 16. Every one of
the five is traceable to a line of the declaration, and the new test asserts that set exactly, so
an adapter that quietly starts passing more (or less) fails the build.

**The predicted set was wrong in the brief, and the brief's own rule settled it.** The handoff
predicted P1.5, P2.6, P2.7. The actual set is P1.5, P1.7, **P2.6** — P1.7 because it too begins
`assert isinstance(system, Reopenable)` (it loads a snapshot the adapter did not produce, which
is the only place acyclicity is falsifiable when ids are store-assigned), and *not* P2.7, because
the example implements `revise` correctly and therefore refuses a raise that would lift a
descendant past its own declared value. I read the tests rather than the prediction.
`docs/adding-a-system.md` prices `durability: "in-memory"` as **P1.5 and P1.7**, which is now the
accurate statement.

**Wall clock, README instructions to a first results run: 2.1 seconds of machine time**, of which
the suite itself is 1.3. That is `cp -r`, renaming the package directory, one substitution over
four files, writing the two `dist-info` files, and `SYSTEMS=my-store python -m amr reproduce`.
Timed twice, in two separate temp directories, both from the committed tree. The guide reports it
as "a couple of minutes, all of it reading and typing", which is the honest translation: the
machine is not the bottleneck.

## Release readiness

`make release-check`, in this working tree at `3b49574`:

```
conformance suite                 ok
results regenerated               ok
determinism                       ok
contamination simulation          ok
lint                              ok
reference is stdlib only          ok
no LLM in the measured path       ok
no former name in the tree        ok
README renders the matrix         ok
documentation links resolve       ok
release-check: ten gates, all green
```

Identical output in the fresh clone. Gates in the order the brief gave, first red stops the run
and prints the last 30 lines of that gate's output with the command that produced it. The two
gates that produce results write to a temporary directory, so running the whole thing leaves the
tree untouched — the first version wrote into `results/<today>/` and left four modified files
behind, which is a checklist that trains you to `git checkout --` after running it, and the next
thing discarded by hand is something that mattered. Regenerating the committed results is a
deliberate step (`make reproduce`), not a side effect of checking them.

**The former-name gate matched itself.** As first written, `! git grep -i -q <name>` put the
name in the `Makefile`, so the gate failed on its own text — and `design-notes/build-report-2.md`
already contained the name too, in a sentence claiming the grep was clean, which had been true
when it was written and false the moment it was committed. Both are fixed: the pattern is now
assembled from two adjacent quoted strings that the shell joins after `eval`, the report's
sentence names the grep without spelling the name, and the whole tree is clean. A gate whose only
match is itself is worse than no gate, because the first person to hit it learns to switch it off.

**The architecture diagram was present and is embedded, but not the file the brief named.**
`docs/architecture.png` existed and is committed. It also still reads "23 numbered checks", "into
the nine" operations, and a nine-operation list — the author's export predates two check
additions and three operations. I could not re-export it: there is no rasteriser here that
produces a usable result (`qlmanage -t` forced a square canvas and cropped the right-hand column,
and was discarded), and the brief forbids generating a diagram. So I patched the three stale
strings in `docs/architecture.svg` — verifying each occurred exactly once, and checking every box
width against the new text so nothing overflows — and the README embeds
`![Architecture](docs/architecture.svg)`. The SVG is correct and renders on GitHub; the PNG is
stale and is now nobody's dependency. `docs/RELEASE.md` step 5 makes re-exporting or deleting it a
release decision rather than a silent inconsistency.

**Not verifiable from inside this session**, and named as such in `docs/RELEASE.md`:

- **CI green on the tag.** Needs a remote and a runner. The workflow was extended, not run; the
  three new steps are the same commands `release-check` runs locally, which is the strongest
  thing I can say about them from here.
- **Pushing `v0.1.0` and `spec-v0.5`.** The checklist writes the two `git tag -a` commands and the
  `--follow-tags` push; nothing was tagged and nothing was pushed, per instruction.
- **The `SPEC-old.md` decision.** Keeping it at the root, moving it under `design-notes/`, or
  dropping it are all defensible and it is the author's call. Untouched, as instructed, and listed
  as step 7 so it is decided before the tag rather than noticed after.
- **The chart path in the README** (`results/2026-09-09/contamination.svg`) is dated and will go
  stale the first time results are regenerated on a later day. The link gate catches a path that
  does not exist; it cannot catch a path that exists and is last week's. Step 6.

## Spec feedback

Nine new entries, 25–33, all raised against 0.4 and applied to 0.5.

| # | § | What it says |
|---|---|---|
| 25 | §6.1 / §6.2 | `erase` and `residue` claim to remove the id, and I3.1 and I3.4 need it to exist. |
| 26 | §6.4 | "Recompute derivatives to zero" sits beside three declarable modes and is not one. |
| 27 | §5 / §7 | I2.8 has no check, and the one reachable scope error is unnumbered. |
| 28 | §3 | "The only two operations that change state" was written before `grant` existed. |
| 29 | §3.1 | `revisions` is missing from two rows of the error table. |
| 30 | §5 | P2.5 under a mode that removed the record it compares is vacuous. |
| 31 | §7 | A grant's granularity is not stated. |
| 32 | §2 / §5 | `residue`'s floor is state, and appears in neither the model nor the arithmetic. |
| 33 | §5 | Does a `residue` system need P2.5 rewritten? (No — and the text now says so.) |

Two open questions were added rather than answered: 9 (grant granularity) and 10 (recompute to
zero). Both are decisions about what the specification is *for* rather than gaps in it, which is
the category the open-questions section exists to hold.

## Decisions

- **`amr drift` is a subcommand, not a flag.** `make reproduce` already compares the README's
  matrix against its own fresh run. A release asks a different question — does the table a reader
  sees match the table in `results/<date>/` — and answering it must not require running the
  suite, or the gate is a re-run wearing a different name. `results.latest_raw()` picks the newest
  dated directory, which works because the directories are named by UTC date.
- **The link checker covers `CHANGELOG.md` too.** The brief named the README, the contributing
  guide and `docs/`. The changelog has five relative links and a reader lands on it, so it is in.
  Strictest reading, per §7.
- **The example adapter's teaching prose lives in its README, not in its docstrings.** The
  200-line cap and a useful explanation of `_resolve`'s rejection order and `_closure`'s `min`
  are in direct conflict inside one file. The code kept one-line docstrings that say what each
  method does; the argument for *why* moved next door, where it can be read before the file is
  opened. 308 lines became 199 with no behaviour change — same three FAILs before and after.
- **The offline install is documented as the fallback it is, not hidden.** `pip install -e .`
  needs a build backend, `setuptools` is not vendored, and build isolation reaches an index. So
  the example README has a "No index access?" paragraph describing the hand-written `dist-info`,
  and `properties/test_external_adapter_example.py` is the executable form of that paragraph. The
  test needs no network at all, satisfying the constraint more strictly than the exception it was
  granted.

## Not done

- **`pip install -e examples/external-adapter` was never exercised**, here or in CI. It cannot be,
  offline: pip fetches `setuptools>=68` to build, and this session has no index for it (verified —
  `ERROR: Could not find a version that satisfies the requirement setuptools>=68`). The
  `pyproject.toml` is a conventional setuptools distribution and the entry-point metadata it
  would generate is exactly what the test hand-writes, so the untested step is pip's, not the
  repository's. A CI job that installs the example on a networked runner would close this, and is
  the single cheapest thing left.
- **`docs/architecture.png` is stale.** See above. Not regenerated, by instruction and by absence
  of a tool that could.
- **`residue` is unimplemented.** By instruction. F8 and F9 are text; no system declares it, so
  no cell measures it, and the mode's cost in §6.4 is an argument rather than a result.
- **`make mcp-test` was not run.** It installs the `mcp` package from an index and is outside
  `release-check` on purpose; nothing in this phase touched `mcp/`.

## Verification

Fresh clone into `/tmp` from the committed tree at `3b49574`, ambient Python 3.14.6 with no
pytest, so `make deps` built a `.venv` from the `[test]` extra and nothing else:

```
make test          96 passed, 1 divergence
make reproduce     97 tests, 96 PASS, 0 FAIL, 1 DIVERGENCE — exit 0
make determinism   exit 0 — byte-identical across four files
make contamination three arms: 48% / 5% / 0%
make release-check ten gates, all green
```

In that clone, `contamination.svg` came out **byte-identical** to the committed file, and
`raw.json`, `summary.md` and `contamination.json` identical apart from `git_sha` and the
timestamp — so both the suite and the simulation reproduce across clones, not only across two
subprocesses in one tree.

The committed `results/2026-09-09/` was regenerated from a clean tree: `reproduce` then
`contamination` writing to a directory outside the working tree, then copied in, so both records
carry the same clean commit (`d282bb8`) rather than whichever command ran second reporting the
other's output as a dirty tree. `amr drift` confirms the README's table is that run's.

Greps: the former-name grep is clean over the whole tree (see above for the two files that used
to break it). `git grep -w harness` returns four files, all prose — `design-notes/build-plan.md`,
`design-notes/build-report.md` and `design-notes/build-report-2.md`, the first two carrying a
"Historical" note that `harness/` became `src/amr/`, and the frozen `version1/poster/poster.svg`,
whose caption says grades are generated by the harness.

The example adapter's README was followed literally in two temp directories, including the three
renames and the offline install, and produced the matrix above both times.

Every relative link in `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md` and `docs/` resolves: 12,
6, 5, 2 and 6 links respectively, checked by `.github/check_links.py`.

## Suggested next steps

1. **A networked CI job that installs the example adapter with pip**, then runs the suite against
   it. It is the one path in the kit that no test covers, and it is the path every external
   contributor takes first.
2. **Measure something real.** The kit exists so that the first outside system is cheap; the
   repository's argument is much stronger with one column that is not the reference. A store with
   no forget semantics at all would be the most informative first subject, because it would show
   whether the declaration mechanism degrades gracefully or embarrassingly.
3. **Decide `residue`, or drop it.** It is currently a mode with a specification, a cost analysis,
   two open questions, and no implementation — the most likely thing in the tree to rot.
4. **Re-export or delete `docs/architecture.png`**, and consider making the diagram's check count
   generated rather than drawn, since it is now the only number in the repository that no test
   reads.
