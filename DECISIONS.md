# Decisions

Choices a reader could reasonably have made differently. Decisions forced by the
specification, and ambiguities in it, are not here — those are in
[design-notes/spec-feedback.md](design-notes/spec-feedback.md).

## Dependencies

**The package has no runtime dependencies.** `pyproject.toml` declares
`dependencies = []`. pytest is the runner rather than a runtime requirement, so it lives in
the `[test]` extra; `systems/reference/` imports the standard library and `amr.protocol`
only, and `.github/check_stdlib_only.py` walks its ASTs in CI and fails the build on
anything else.

**Extras, not requirements files.** `pip install -e ".[test]"` and `".[mcp]"` replaced
`requirements-dev.txt` and `requirements-mcp.txt`, which pinned the same versions a second
time in a second place. `make test`, `make reproduce`, and `make determinism` pass without
`mcp` installed; the conformance suite never imports it and `mcp/test_server.py` begins
with an `importorskip`.

**ruff is optional and never imported.** `make lint` uses ruff if present, pyflakes if not,
and `compileall` if neither. `ruff.toml` pins the rule selection so a contributor's ruff
agrees with CI rather than producing a different list. It is not in any requirements file.

**Nothing else.** No hypothesis (the random-DAG check uses `random.Random` with a
checked-in seed, so a failure is reproducible from the seed alone and CI needs no plugin).
No pytest-xdist (ordering would stop being deterministic). No coverage tooling.

## Running the suite

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
that no test reported, `make reproduce` exits non-zero. `amr` treats its own silence
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

**Grant administration is in the §3 operation set; reopening a store is not.** `grant`,
`revoke`, and `grants` are three of the twelve operations (spec-feedback entry 2, folded
into v0.4). `Reopenable` stays an optional protocol in `amr/extensions.py`, because closing
and reopening a store is a lifecycle concern rather than an operation on a record — but a
system that does not implement it fails P1.5 rather than being excused from it
(spec-feedback entry 3, as modified).

**`ScopeError` survives, narrowed to one case.** Entry 6 makes an invisible record
indistinguishable from a nonexistent one for every operation, which removes every scope
error the suite could previously observe: an operation on a record the caller cannot see
raises `NotFoundError`, exactly as an unassigned id would. The one case left is a caller
that *can* read a record through a grant and tries to `revise` or `forget` it. Collapsing
that into `NotFoundError` too would be wrong in the other direction — it would tell a caller
the record it just read does not exist — and a read grant conveying write access would make
`revoke` unable to undo anything. It leaks nothing, because it is only reachable once the
caller can already see the record. See spec-feedback entry 20 and SPEC.md 3.1.

**`NotFound` is a type, and it is a `LookupError`.** For three phases the reference raised a
bare `LookupError` for §3.1's `NotFound`, because the specification names that signal without
naming a type and the built-in was the smallest thing that worked. It was never written down
as a decision, which is how it survived: `amr.protocol` exported four error classes and the
fifth signal was a built-in nobody had chosen. `NotFoundError(LookupError)` now exists and is
raised by every mutation on an id the caller cannot see. Subclassing rather than replacing,
because the suite, the MCP server's error map, and the adapter documentation all already
caught `LookupError`, and an adapter that still raises the built-in conforms. `get` keeps
reporting `ReadOutcome.NOT_FOUND` and does not raise — that asymmetry is in the specification,
not in this code. See spec-feedback entry 34.

**`StoreIntegrityError` stays inside the reference.** A snapshot that opens with a dangling
edge — a live record citing an id the snapshot does not contain — has no §3.1 signal. The
reference raises its own exception for it, validating dangling edges before cycles so that a
snapshot with both faults names the missing id, which is the actionable one. The type is not
promoted into `amr.protocol`: §3.1 says five signals are normative, and adding a sixth to the
shared vocabulary ahead of the text would make this code the specification. P1.7 only requires
that opening a corrupt snapshot *fail* — the alternative, opening it with the edge dropped, is
`taxonomy/silent-chain-truncation.md` — so no matrix cell depends on which type comes out.
See spec-feedback entry 36.

**`Capabilities` has one optional field, and it is `notes`.** SPEC.md §8 requires every field
to be stated explicitly and says an omitted field is not a default, so the six dataclass
defaults that used to sit in `Capabilities` were the assumed values the section forbids, made
where nobody would look for them; omitting any of the ten §8 fields is now a `TypeError`.
`notes` is the exception and is kept: the reference's declaration is where "the `erase`
divergence is deliberate" is said in a machine-readable file, and the alternative to a field
§8 does not define is the same sentence in a commit message, which no result carries. The
strict reading — delete it — was implemented and reverted when it turned out `notes` is read
by `amr.results` as well as by the MCP server. `Capabilities.from_dict` is the reader for a
published declaration and rejects a missing or unknown key by name, because a checker that
tolerates an absent field is §8's failure one layer out. See spec-feedback entry 35.

**Grants are not exposed as MCP tools.** A client that can widen its own visibility is not
isolated by anything, so the server exposes the nine record operations and leaves grant
administration to whoever runs it.

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

**`src/` layout, and the import name is `amr` while the distribution is
`agent-memory-reliability`.** The long name is what a reader searching for the project will
type; the short one is what fifty test files import. `systems/` and `scenarios/` stay at the
root rather than moving under `src/amr/` because neither is part of the package a conformer
depends on: an adapter is a peer of the suite, not a module of it.

**An external package registers a system through the `amr.systems` entry-point group.** The
registry reads that group *and* imports the in-tree `systems/*/` packages, deduplicating by
name, with the entry point winning. Two sources rather than one because an adapter under
development should not have to be installed to be run, and a released one should not have to
be vendored here. `properties/test_registry.py` builds a throwaway distribution in a temp
directory to prove the second half of that claim.

**`properties/test_registry.py` hand-writes a `.dist-info` instead of calling `pip
install`.** pip's default build isolation fetches setuptools from the network, and no test
in this repository is allowed to touch the network. An `entry_points.txt` inside a
`.dist-info` on `sys.path` is exactly the artefact an install leaves behind, read by the
same `importlib.metadata` code path.

**The root `conftest.py` survives the packaging.** It puts the repository root and `src/` on
`sys.path`, so `pytest properties/` still works in a fresh clone with nothing installed but
pytest. `pip install -e .` is the supported path; this is the fallback that keeps the
one-command reproduce claim true.

**Tool configuration stays out of `pyproject.toml`.** `ruff.toml` is separate, and there is
no `[tool.pytest.ini_options]`: markers are registered in `properties/conftest.py`, next to
the fixtures that stamp them, and duplicating the list in a second file is how the two
disagree.

**The `amr` console script is the interface; the Makefile is a convenience over it.** Seven
subcommands (`test`, `reproduce`, `determinism`, `demo`, `contamination`, `matrix`,
`drift`), and `python -m amr` is the same thing. Nothing in this repository can only be done
by GNU make — including the drift gate, which is a subcommand rather than a shell line in
`release-check` so that a contributor can run it the same way CI does.

**`make results` is the only target that writes the committed record.** `make contamination`
and the two result-producing gates in `release-check` write into a temporary directory and
print; `make results` is `reproduce` plus the simulation into `results/<today>/`, and it is
the only thing that refreshes `docs/contamination.svg`. Running a check used to leave the
tree dirty, and a checklist step that does that gets `git checkout`ed away by hand — after
which the next thing discarded by hand is something that mattered.

**The diagram's facts are gated; its picture is not.** `docs/architecture.svg` was the only
document in the repository that nothing read, and it named a `scope.py` that this tree has
never contained — folded into `store.py` in Phase 2 and still on the diagram three phases
later. `.github/check_diagram.py` is the eleventh gate in `release-check`: every `*.py` the
diagram names has to exist in `git ls-files` by basename, its "N numbered checks" has to equal
what `properties/test_spec_coverage.py` parses out of the specification, and the count it
spells in "N operations" has to equal what `MemorySystem` declares. Both counts are checked in
both directions, and a *missing* phrase is a failure too: a gate whose subject can be deleted
is a gate that can be switched off by deleting its subject. Matched by basename because
the diagram writes `amr/protocol.py` where the tree writes `src/amr/protocol.py`, and a
drawing is not the place to track a directory layout. Layout, colour, and whether the arrows
point at the right boxes are not checked, and `docs/architecture.png` is not re-exported by
anything — a gate over an image's meaning is not available from text.

**Two size targets were missed, and the numbers are reported rather than met.**
`systems/reference/` is 799 lines against a ≤600 target (518 of them code) and
`scenarios/contamination/run.py` is 403 against a 200–300 one (253 code, inside the range).
Both overruns are docstrings and the constant tables that are the whole input to the
simulation, and the cuts available were all of the kind the handoffs forbid — "if a cut makes
a file harder to follow, don't make it". Logged here because the two build reports each
recorded the overrun of their own phase under "Not done", which is where a number goes to be
read once; a target this repository keeps deciding not to meet is a decision, not a defect
report. The constraints that are *not* negotiable held: the reference imports the standard
library only, and no numbered check was dropped to save a line.

**`mcp/` has no `__init__.py`.** A regular package named `mcp` at the repository root would
shadow the installed one. A directory without `__init__.py` is only a namespace portion and
loses to an installed regular package, which is what makes the layout safe.

**The example adapter's gate lives in CI, not in `release-check`.** `release-check` has to be
green in a fresh clone with no index access, and the only thing
`.github/check_example_adapter.py` adds over the in-tree test is a real
`pip install -e examples/external-adapter` — which needs the network for setuptools. So
`release-check` runs eleven gates and the twelfth, the one that proves the four commands
`docs/adding-a-system.md` promises a stranger, is a CI job. A gate that cannot run offline
does not belong in the command whose contract is that it runs offline.

**The MCP server's scope is the caller's word, and that is stated rather than defended.**
Every tool takes an optional `scope`; the server does not authenticate anyone, has no session
identity, and cannot tell two clients apart. Scope there is a namespace, not a boundary. The
alternative — inventing an identity for a reference server over one in-process store — would
be the server deciding something, which is the one thing it does not do. What it gained
instead is `--scope NAME` / `AMR_MCP_SCOPE`, which binds a connection to one scope: the
argument then defaults to that name and a call naming a different one is refused with the
`scope:` code rather than redirected, because a client told its write succeeded in a scope it
did not ask for has been lied to about where its memory is. `mcp/README.md` says in prose
what is and is not worth trusting; SPEC.md §7 isolation remains a property of the system under
test, which the suite calls directly.

**The MCP server translates and decides nothing.** Errors are re-raised as tool errors with
a coded prefix (`cycle`, `unresolved_source`, `forgotten`, `scope`, `not_found`,
`invalid_argument`) so a client can branch without parsing English. Any behaviour worth
arguing about belongs in `systems/reference/`, where the conformance suite can see it.

**`make` targets run through `.venv` only when they have to.** If the ambient interpreter
already has pytest, nothing is installed and nothing is downloaded; otherwise a local
`.venv` is created, which also sidesteps a PEP 668 "externally managed" system Python.
Nothing is ever written outside the clone.

## The contamination scenario

**The agents are policies over a seeded PRNG, not models.** Reproducibility is the whole
value of the number; a model in the loop would trade it for realism that a case study is the
right place for. Same seed, byte-identical JSON and SVG, checked by `make determinism`.

**Each role gets its own scope, with mutual read grants.** One shared scope would have made
the role labels decorative and would have skipped the grant machinery the scenario is
supposed to exercise. A colleague's memory is a foreign, opaque ancestor that still carries
its confidence, which is what the measurement rests on.

**The gate filters citation, not reading.** An agent still reads a memory below `tau` and
still counts the read; it may not build on it. Withholding the read as well would measure a
different and less interesting intervention, and `reads` stays identical across the two arms,
which makes it a usable control.

**The inflation metric reads the gate's own threshold.** "Declared ≥ 0.9 while effective ≤
`tau`" rather than a second hardcoded 0.5, so the two numbers cannot drift apart when `tau`
is changed. The declared floor stays a separate constant, because it means something else.

**Sixty rounds, and three arms rather than two.** Inheritance in the ungated arm rises and
then sits still — 5/18 writes at six rounds, 17/36 at twelve, 28/60 at twenty, 87/180 at
sixty, 138/270 at ninety — so the headline 48% is a plateau and not a number that any
particular run length flatters. The `surfaced` arm stays between 5% and 8% across the same
range and `gated` is flat at zero throughout, which is what makes the separation a finding
rather than an artefact of where the run was stopped. Sixty is where the depth figure stops
moving too (d9 at sixty and at ninety), and the third arm is why the length matters: with
only `ungated` and `gated`, the gated zero is true by construction and measures nothing.
`surfaced` — the agent sees effective confidence and nothing is withheld — is the arm with
a result in it, and 5% against 48% is the claim the chart is for.

**An agent occasionally cites an id it never read.** A tenth of writes attempt a hallucinated
citation, the strict write rejects the whole thing (I1.6), and the count is reported. It is
the one part of the simulation that measures the store rather than the policy.

## Taxonomy

**Each entry embeds the verbatim source of a module the suite imports and runs**, and
`properties/test_taxonomy.py` asserts the embedded text is byte-identical to
`inspect.getsource` of that module and that the documented numbers are the numbers it
produces. Prose about a failure mode drifts; prose that fails a test does not.

**The taxonomy reproductions import `amr.protocol` only**, never
`systems.reference.*`, so they run against any registered system.
