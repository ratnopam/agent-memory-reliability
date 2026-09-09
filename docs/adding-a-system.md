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
without its content. Raises `NotFound` for an invisible id and `ForgottenRecordError` for a
record that was removed rather than tombstoned.

**`effective_confidence(id, scope) -> float`** — `min(declared, min over ancestors)`, with
your declared convention for the empty chain. Same errors as `provenance`. The scope decides
whether it answers, never what it answers.

**`descendants(id, scope) -> set of id`** — everything derived from the record,
transitively, filtered to what the scope can see. Same errors as `provenance`.

**`revise(id, scope, new_declared, reason) -> receipt`** — changes the declared confidence
and nothing else. Lowering propagates; raising does not lift a descendant past its own
declared value. Raises `ForgottenRecordError` for a forgotten target, `ScopeError` when the
caller can see the record through a grant but does not own it, and `NotFound` otherwise.

**`revisions(id, scope) -> ordered receipts`** — the history, oldest first, carrying the
before value, the after value, and the reason. Raises `NotFound` and
`ForgottenRecordError` like the walk.

**`forget(id, scope, mode) -> receipt`** — applies one of the modes you declare. It is
idempotent: a second call succeeds, changes nothing, and names nothing. The receipt carries
the mode, every affected id, the confidence delta for every surviving descendant, and the
scope of each affected id. Raises `ScopeError` and `NotFound` like `revise`.

**`list_scope(scope) -> set of id`** — the records native to that scope, forgotten ones
excluded. A record readable through a grant is *not* listed: `list_scope` is not a
directory of another scope's contents.

**`grant(owner, reader)`**, **`revoke(owner, reader)`**, **`grants(owner)`** — the grant
table. A grant conveys reading only. `grants(owner)` returns the reader scopes, which is
the observable a revocation has to change.

**`capabilities()`** — the declaration below.

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

## 4. Running the suite against only your system

```bash
python -m pip install -e path/to/agent-memory-reliability
python -m pip install -e .
cd path/to/agent-memory-reliability
SYSTEMS=my-store python -m amr reproduce --out /tmp/my-first-run
```

Comma-separate to run more than one; omit `SYSTEMS` to run everything the process can see,
which is how the committed results are produced. A filtered run writes the same
`raw.json` and `summary.md`, and skips the README drift check, which is about the
reference's matrix rather than yours.

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
