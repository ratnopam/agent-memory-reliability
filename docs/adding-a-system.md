# Adding a system

You do not need a patch to this repository to be measured by it. Write an adapter over your
store, declare an `amr.systems` entry point, run one command, and the results come out in
the same shape as the reference's.

The worked example is [examples/external-adapter/](../examples/external-adapter/): a
complete adapter over a `dict`, under 200 lines, that fails three checks on purpose. Copy
it and read this next to it. The normative text is [version2/SPEC.md](../version2/SPEC.md);
where the two disagree, the specification wins.

## 1. What you are implementing

Twelve operations ([SPEC.md §3](../version2/SPEC.md)). None of them may consult a language
model, and none may return a value that depends on who is asking except where a scope makes
a record invisible.

**`write(content, declared_confidence, sources, scope) -> id`** — stores a record and its
edges. Sources are checked before anything is persisted: an id that does not resolve for
the writing scope raises `UnresolvedSourceError` and stores nothing, and an id belonging to
a forgotten record — a tombstone included — raises `ForgottenRecordError`. If your store
lets a caller supply ids, edges that would close a cycle raise `CycleError`.

**`get(id, scope) -> record | NotFound | Forgotten`** — the only operation that reports
absence as a value rather than an error, and it has to distinguish *forgotten* from *never
existed*. Collapsing the two is the single most common way to fail P3.1.

**`provenance(id, scope) -> ancestor subgraph`** — the transitive ancestor closure, each
ancestor once, every id it names resolvable inside the subgraph it returns. A tombstoned
ancestor appears marked; an ancestor in another scope appears with its confidence and
without its content. Raises `NotFoundError` for an invisible id and `ForgottenRecordError`
for a record that was removed rather than tombstoned.

**`effective_confidence(id, scope) -> float`** — `min(declared, min over ancestors)`, with
your declared convention for the empty chain. Same errors as `provenance`. The scope decides
whether it answers, never what it answers.

**`descendants(id, scope) -> set of id`** — everything derived from the record,
transitively, filtered to what the scope can see. Same errors as `provenance`.

**`revise(id, scope, new_declared, reason) -> receipt`** — changes the declared confidence
and nothing else. Lowering propagates; raising does not lift a descendant past its own
declared value. Raises `ForgottenRecordError` for a forgotten target, `ScopeError` when the
caller can see the record through a grant but does not own it, and `NotFoundError`
otherwise.

**`revisions(id, scope) -> ordered receipts`** — the history, oldest first, carrying the
before value, the after value, and the reason. Raises `NotFoundError` and
`ForgottenRecordError` like the walk.

**`forget(id, scope, mode) -> receipt`** — applies one of the modes you declare. It is
idempotent: a second call succeeds, changes nothing, and names nothing. The receipt carries
the mode, every affected id, the confidence delta for every surviving descendant, and the
scope of each affected id. Raises `ScopeError` and `NotFoundError` like `revise`.

**`list_scope(scope) -> set of id`** — the records native to that scope, forgotten ones
excluded. A record readable through a grant is *not* listed: `list_scope` is not a
directory of another scope's contents.

**`grant(owner, reader)`**, **`revoke(owner, reader)`**, **`grants(owner)`** — the grant
table. A grant conveys reading only. `grants(owner)` returns the reader scopes, which is
the observable a revocation has to change.

**`capabilities()`** — the declaration below.

### The errors, by name

[SPEC.md §3.1](../version2/SPEC.md) names the signals; these are the types `amr.protocol`
exports for them, and what the suite catches. An adapter may subclass them or raise its
own, as long as the name it raises is catchable as the one in the right-hand column.

| Signal (§3.1) | Type | Raised when |
| --- | --- | --- |
| `UnresolvedSource` | `UnresolvedSourceError` | A write cites an id that does not resolve for the writing scope. Nothing is persisted. |
| `Cycle` | `CycleError` | An edge would make a record its own ancestor. Reachable only where ids are caller-supplied — a write, or a snapshot being opened. |
| `ForgottenRecord` | `ForgottenRecordError` | The target of a mutation, or an id cited by a write, belongs to a forgotten record — a tombstone included. |
| `NotFoundError` | `NotFoundError` (a `LookupError`) | No record with that id is visible to the calling scope. One answer for "no such id" and for "another scope's id": telling them apart is an existence oracle (§7). `get` reports this as its `NOT_FOUND` outcome and does not raise. |
| `Scope` | `ScopeError` | The caller can *read* the record through a grant but may not do what it asked — mutate a record it does not own. Distinct from `NotFoundError`, which says nothing about whether the record exists. |
| `StoreIntegrityError` | `StoreIntegrityError` | A snapshot being opened has a *dangling* edge: a live record cites an id the snapshot does not contain. Raised by the reference's store, and the sixth signal §3.1 names. |

`NotFoundError` subclasses `LookupError`, so an adapter that raises the bare built-in still
conforms. The named type is what lets a caller say *which* lookup failed.

A corrupt snapshot has two shapes and both must be rejected. A dangling edge raises
`StoreIntegrityError`, a cyclic one raises `CycleError`, and where a snapshot is both the
dangling edge is reported first, because it names a specific missing id. The suite requires
that opening such a snapshot *fails* rather than silently truncating the chain (P1.7) —
truncation inflates every effective confidence below the break, which is the finding this
repository exists to measure. If you implement `Reopenable`, raise whatever your store
raises for corruption, as long as it is not nothing.

## 2. What you declare, and what it costs

Every field of [SPEC.md §8](../version2/SPEC.md) is explicit; absence is not a default. A
declaration is not a disclaimer — it changes which cells the suite can hold you to, and
each of these has a price:

| Field | If you declare less |
| --- | --- |
| `supported_forget_modes` | One column per mode. Naming fewer modes gives you a narrower matrix, not a cleaner one. |
| `default_forget_mode` | Must be one of the modes you named. |
| `empty_chain_convention` | The value P2 arithmetic is checked against. If it is not 1.0, say so; the suite uses what you declare. |
| `revision: "none"` | **P2.6 FAIL.** A history no caller can read is indistinguishable from no history. |
| `revision_raise_supported: false` | P2.7 requires you to *refuse* a raise rather than silently accept it. |
| `scopes` | The P4 checks run either way. There is no declaration that removes them. |
| `cross_scope_derivation` | How a foreign ancestor appears in a walk (P4.3). |
| `durability: "in-memory"` | **P1.5 and P1.7 FAIL** unless you implement the optional `Reopenable` protocol (`to_dict`, `load`, `reopen`). P1.7 loads a snapshot the adapter did not produce, which is the only place acyclicity is falsifiable when ids are store-assigned. |
| `notes` | Free text. Read by humans, not by the suite. |

There is no *not applicable*. A check you cannot satisfy is a FAIL, and a skipped test is
counted as one — including the two taxonomy reproductions that need `cascade` and `erase`,
which report FAIL for a system that declares only `tombstone`. That is deliberate: a suite
that reports "not applicable" for a property is the failure mode this repository exists to
avoid.

## 3. The entry point

One declaration in your `pyproject.toml`:

```toml
[project.entry-points."amr.systems"]
my-store = "my_store:factory"
```

The key is the name results are reported under and the name `SYSTEMS=` selects by. The
value is `module:attribute`, where the attribute is a callable that returns your system,
accepting `default_forget_mode` or nothing. Nothing in this repository names your package,
and nothing in your package imports the registry.

### If your store only stores

Most stores are key-value or document stores: they hold what you put in them and compute
nothing. Implementing the twelve operations over one means writing confidence arithmetic,
scope visibility and forget semantics yourself, which is a second implementation of the
specification and the one with the bugs in it.

[systems/persistent/](../systems/persistent/) is the other route. `WriteThrough` composes
the reference implementation and persists every mutation through four methods — `put`,
`get`, `delete`, `items` — so what gets measured is your storage with the reference's
semantics on top:

```python
from systems.persistent import WriteThrough

def factory(default_forget_mode=None):
    return WriteThrough(MyBackend(...), default_forget_mode, name="my-store")
```

`systems/persistent/sqlite.py` is a complete backend in under eighty lines and
`backend.py` is the interface with its one hazard written out: `items` must yield every
item. A store whose listing is paged will answer the first page and stop, and a loader that
takes a prefix for the whole rebuilds a *shorter* graph than it stored — intact chains,
self-consistent records, and every effective confidence along the truncation higher than
it should be. That is erasure inflation arriving through the loader instead of through a
forget, and it is what the fault injection in
[properties/test_persistent_system.py](../properties/test_persistent_system.py) exists to
catch.

The wrapper declares `durability` from the backend, so a backend that puts state in a file
says `durable` and one that puts it in a dictionary says `round-trip`. Nothing else in the
declaration changes, because nothing else about the system changed.

[systems/langgraph_store/](../systems/langgraph_store/) is both routes over one real
third-party store, side by side: `store_alone.py` is the store mapped straight onto the
protocol, where every computed operation raises and the twenty-five resulting FAILs are the
measurement of what you would have to write; `layered.py` is the same store as four methods
behind `WriteThrough`, which passes everything. If you want to know what your store is
missing before you decide how much to build, measure it the first way first. The FAILs are
not an insult to the store — they are the specification's questions, asked of something that
was built to answer different ones.

## 4. Running the suite against only your system

```bash
python -m pip install -e path/to/agent-memory-reliability
python -m pip install -e .
cd path/to/agent-memory-reliability
SYSTEMS=my-store python -m amr reproduce --out /tmp/my-first-run
```

Comma-separate to run more than one. A filtered run writes the same `raw.json` and
`summary.md`, and skips the README drift check, which is about the reference's matrix
rather than yours.

Omitting `SYSTEMS` runs the **default** systems, which is how the committed results are
produced. A system registered as an extra — anything with an optional dependency, and
every adapter in this repository that is not the reference — is measured only when you
name it or set `AMR_EXTRAS=1`. `python -m amr systems` prints what this interpreter can
run and which of the two each one is; `make extras` runs everything installed and writes
`results/extras/<date>/`, which is deliberately not where the published matrix lives.

It is quick. Copying the example, renaming the three things, and getting a first matrix out
measured **2.1 seconds** of machine time end to end, the suite itself being 1.3 of them — so
the honest estimate is a couple of minutes, all of it reading and typing. If `pip` cannot
reach an index to fetch its build backend, use the `PYTHONPATH` and hand-written
`dist-info` route in
[examples/external-adapter/README.md](../examples/external-adapter/README.md); the numbers
above were measured that way, offline.

## 5. Reading your first results

`summary.md` has one row per numbered check and one column per declared mode. Three states:

**PASS.** The check held.

**FAIL.** It did not, or the test did not run. Read `## Failures`, which gives one line per
failure naming the check and what went wrong.

**DIVERGENCE.** Behaviour the specification deliberately leaves open, in a system whose
declaration says it behaves that way — today, that is only erasure inflation under
`erase` ([SPEC.md §6.4](../version2/SPEC.md)). It is reported, not scored, and it does not
fail `reproduce`. You cannot reach it by declaring something inconvenient: the check also
requires that your receipt reported the inflation and that the inflated number is exactly
your declared arithmetic over the shortened chain.

The poster matrix at the bottom aggregates pessimistically — a property is PASS only if all
of its checks are.

## 6. Submitting results

Open a pull request adding `results/<date>-<system>/` with the `raw.json` and `summary.md`
your run produced, and a short `README.md` in that directory saying which version of your
store it was, how it was configured, and anything a reader needs to reproduce it. Your
adapter can live in your own repository; a link is enough. See
[CONTRIBUTING.md](../CONTRIBUTING.md) for the sign-off and for what will not be merged.

Results that show failures are welcome, and are the interesting case. A matrix with FAILs
in it and a declaration that explains them is worth more than a clean sheet nobody can
reproduce.
