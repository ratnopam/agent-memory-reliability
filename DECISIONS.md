# Decisions

Choices made while building Phase 0 that a reader could reasonably have made differently.
Decisions forced by `version1/SPEC.md`, and ambiguities in it, are not here — those are in
[design-notes/spec-feedback.md](design-notes/spec-feedback.md).

## Dependencies

**pytest is the only dependency of the suite.** `requirements-dev.txt` pins
`pytest>=8.0,<10` and nothing else. `systems/reference/` imports the standard library and
`harness.protocol` only; `.github/check_stdlib_only.py` walks its ASTs in CI and fails the
build on anything else.

**The MCP server depends on the official `mcp` package, in a separate requirements file.**
`make test`, `make reproduce`, and `make determinism` pass without it installed. The
conformance suite never imports it, and `mcp/test_server.py` begins with an
`importorskip`.

**ruff is optional and never imported.** `make lint` uses ruff if present, pyflakes if not,
and `compileall` if neither. `ruff.toml` pins the rule selection so a contributor's ruff
agrees with CI rather than producing a different list. It is not in any requirements file.

**Nothing else.** No hypothesis (the random-DAG check uses `random.Random` with a
checked-in seed, so a failure is reproducible from the seed alone and CI needs no plugin).
No pytest-xdist (ordering would stop being deterministic). No coverage tooling.

## Harness

**One pytest session, grouped afterwards, rather than one session per matrix cell.** The
fixtures already parameterise every check over every `(system, forget_mode)` pair, so a
single session covers the matrix; the runner groups the reports by the system and mode that
`properties/conftest.py` stamps into `user_properties`. Running pytest once per cell would
re-collect the suite N times and, worse, would let `make test` and `make reproduce` disagree
about what ran.

**pytest, not a hand-rolled loop.** A loop that imported the test modules and called them
would need its own parameterisation, its own assertion introspection, and its own reporting,
and would then be a second implementation of the thing that decides whether a check passed.

**A skipped test is a FAIL.** See spec-feedback entry 16.

**DIVERGENCE is carried in `user_properties` and rendered by a report hook, not by
`xfail`.** An `xfail` is a claim about a test; a divergence is a claim about a
specification. A check records a divergence only after asserting that the system behaved
consistently with its own capability declaration — the receipt reported the inflation, and
the value equals the reference arithmetic over the shortened chain. Exit code stays 0.

**A divergence does not fail `make reproduce`; a failure does.** A build that went red on a
divergence would pressure whoever ran it to bury the finding, which is the opposite of the
point.

**`missing_checks` is a first-class field.** If the specification declares a numbered check
that no test reported, `make reproduce` exits non-zero. The harness treats its own silence
as a defect.

## Results and determinism

**Exactly one volatile field: `generated_at`.** Everything else in `raw.json` is a fact
about the code under test or the environment. No durations, no absolute paths, no iteration
orders. `make determinism` strips that field and compares the remaining bytes, so anything
nondeterministic added later breaks the build.

**Two subprocesses, not two calls in one process, and `PYTHONHASHSEED` is not pinned.** A
same-process repeat shares imported modules, memoised registries, and one hash seed —
exactly where a nondeterminism bug hides. Pinning the seed would hide set-iteration
dependence rather than surface it.

**`summary.md` is compared too**, with its generated-at line stripped. The requirement is
`raw.json`; the report is cheap to include and a nondeterministic report is just as bad on
a poster.

**The results directory is the UTC date**, matching `generated_at`. Two runs in one day
overwrite; the commit SHA in the file says which tree produced it.

**The git SHA carries a `-dirty` suffix** when the tree has uncommitted changes. A results
file that cannot be tied to a commit should say so on its face.

**`summary.md` reads check scenarios and property titles out of `SPEC.md`** instead of
restating them, so the report cannot describe a property differently from the specification.

**Property rows in the poster matrix aggregate pessimistically.** FAIL if any check failed,
DIVERGENCE if any diverged and none failed, PASS only if all passed. A property that is 4/5
PASS is not a PASS. The P2.5 row is printed separately because aggregation is exactly what
would hide it.

**One poster matrix per system.** With several systems registered, a single table would
have to either merge systems into one cell or grow a second header dimension; both are
worse to read at poster distance.

## Reference implementation

**Grants and store-reopen are optional protocols in `harness/extensions.py`, not additions
to the §3 operation set.** See spec-feedback entries 2 and 3.

**Ids are `m001`, `m002`, … allocated by the store.** Sequential and human-readable, so a
failing assertion names something a reader can find, and a serialised store diffs legibly.
The specification only requires opacity and no reuse.

**Confidence is computed lazily and memoised, with invalidation on write, revise, and
forget.** Open question 5 asks whether eager or lazy recomputation is observable; the
memoised value is invalidated for a record and all its descendants before anything reads it,
so it is not. The alternative — recomputing the whole graph on every read — would make the
random-DAG check quadratic for no gain in the property being tested.

**A forget receipt reports every surviving descendant, including unchanged ones.** See
spec-feedback entry 9.

**`revise` validates ownership and forgotten-ness before range-checking the value.** A
caller revising a forgotten record is told it is forgotten, not that 1.5 is out of range.

## Layout

**`conftest.py` at the repository root is the only packaging.** It puts the root on
`sys.path`. No `setup.py`, no `pyproject.toml`, no `pip install -e .` — a fresh clone runs
`make reproduce` with pytest and nothing else. `pyproject.toml` would also be the obvious
place for tool configuration, which is why `ruff.toml` is separate.

**`mcp/` has no `__init__.py`.** A regular package named `mcp` at the repository root would
shadow the installed one. A directory without `__init__.py` is only a namespace portion and
loses to an installed regular package, which is what makes the layout safe.

**The MCP server translates and decides nothing.** Errors are re-raised as tool errors with
a coded prefix (`cycle`, `unresolved_source`, `forgotten`, `scope`, `not_found`,
`invalid_argument`) so a client can branch without parsing English. Any behaviour worth
arguing about belongs in `systems/reference/`, where the conformance suite can see it.

**`make` targets run through `.venv` only when they have to.** If the ambient interpreter
already has pytest, nothing is installed and nothing is downloaded; otherwise a local
`.venv` is created, which also sidesteps a PEP 668 "externally managed" system Python.
Nothing is ever written outside the clone.

## Taxonomy

**Each entry embeds the verbatim source of a module the suite imports and runs**, and
`properties/test_taxonomy.py` asserts the embedded text is byte-identical to
`inspect.getsource` of that module and that the documented numbers are the numbers it
produces. Prose about a failure mode drifts; prose that fails a test does not.

**The taxonomy reproductions import `harness.protocol` only**, never
`systems.reference.*`, so they run against any registered system.
