# An external adapter, entire

Copy this directory, rename three things, run the suite. That is the whole procedure, and
this package exists so that the claim can be checked rather than believed:
`properties/test_external_adapter_example.py` runs the conformance suite against this
adapter on every build.

It is a teaching artefact over a plain `dict`. It is not an adapter for any real product,
and it deliberately implements less than the reference does, so that a first run shows what
real failures look like instead of a clean sheet.

## What it declares, and what that costs

```
supported_forget_modes  ["tombstone"]   one column in the matrix instead of three
revision                "none"          P2.6 FAIL — revisions() returns nothing
durability              "in-memory"     P1.5, P1.7 FAIL — there is no snapshot to reopen
```

Three failures, from the declaration rather than from a bug. See
[capabilities.py](src/amr_adapter_example/capabilities.py) for the reasoning at each field
and [docs/adding-a-system.md](../../docs/adding-a-system.md) for what every other field
costs.

## The two methods worth copying

Everything else in [adapter.py](src/amr_adapter_example/adapter.py) is bookkeeping over a
dict. These two are where a real store gets it wrong.

**`_resolve`** fixes the order of the rejections [SPEC.md §3.1](../../version2/SPEC.md)
requires: absent first, as `LookupError`, and only then not-yours, as `ScopeError`. The
other order is an existence oracle — a reader who cannot see a record learns it exists by
being told they are not allowed to touch it — and P4.1 catches it. So "absent" here covers
both *no such id* and *another scope's id, which you are not entitled to know about*.

**`_closure`** is the transitive ancestor set, and every confidence number in the file is a
`min` over it. That is [SPEC.md §5](../../version2/SPEC.md) read literally rather than
recursively, and it gives the same answer, because `min` is associative and an ancestor
reached by several paths contributes once either way (P2.3). Nothing derived is stored, so
nothing can go stale — which is also why P2.5 passes: a tombstone keeps its confidence and
its edges, so it goes on bounding its descendants after it stops being readable.

## Copy it

```bash
cp -r examples/external-adapter ~/my-store-adapter
cd ~/my-store-adapter
```

Rename three things:

1. **The package.** `src/amr_adapter_example/` → `src/my_store/`, and the two imports
   inside it that name it.
2. **The distribution and the entry point,** in `pyproject.toml`: `project.name`, the
   `[project.entry-points."amr.systems"]` key (this is the name results are reported
   under), its value `my_store:factory`, and the two `[tool.setuptools]` lines.
3. **`SYSTEM_NAME`** in `capabilities.py`, to match the entry-point key.

Then replace the body of `adapter.py` with calls into your store, keeping the twelve method
signatures. `grep -n 'def ' src/my_store/adapter.py` is the checklist.

## Run the suite against it

```bash
python -m pip install -e path/to/agent-memory-reliability   # the suite
python -m pip install -e .                                 # your adapter
cd path/to/agent-memory-reliability
SYSTEMS=my-store python -m amr reproduce --out /tmp/my-first-run
```

`SYSTEMS` selects by the entry-point key, comma-separated; omit it to run every system the
process can see. `reproduce` exits non-zero while anything is FAIL, which on a first run it
will be. The matrix is in `/tmp/my-first-run/summary.md`.

**No index access?** `pip` builds this with `setuptools`, and if the machine cannot reach an
index to fetch it, put the package on `PYTHONPATH` and hand-write the two files an install
would have left behind — a `<name>-<version>.dist-info/` directory containing `METADATA`
and an `entry_points.txt` holding the `[amr.systems]` group. `importlib.metadata` reads it
by exactly the same code path, and
[properties/test_external_adapter_example.py](../../properties/test_external_adapter_example.py)
is the executable version of that paragraph.

## Files

| | |
| --- | --- |
| [pyproject.toml](pyproject.toml) | the distribution, and the one entry point that makes it discoverable |
| [src/amr_adapter_example/__init__.py](src/amr_adapter_example/__init__.py) | `factory`, the entry-point target |
| [src/amr_adapter_example/capabilities.py](src/amr_adapter_example/capabilities.py) | the SPEC.md 8 declaration, one comment per field |
| [src/amr_adapter_example/adapter.py](src/amr_adapter_example/adapter.py) | the twelve operations, under 200 lines |
