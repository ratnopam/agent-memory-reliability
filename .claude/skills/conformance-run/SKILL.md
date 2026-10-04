---
name: conformance-run
description: Run the agent memory reliability conformance suite against a memory system in this repository and explain the resulting matrix. Use when someone asks to measure, test or check a memory store against the specification, asks what a PASS, FAIL or DIVERGENCE in the matrix means, or asks whether their own store would conform.
---

# Running the conformance suite

The suite measures four reliability properties of a memory store — provenance, confidence,
forget, isolation — as 26 numbered checks in each declared forget mode. Every result is
produced by running code. **No model is involved in any measurement, and no result here is
an opinion of yours.** Say so when you report: the numbers come from the suite, and anyone
can reproduce them byte for byte.

## 1. Check the preconditions

```bash
python3 --version          # 3.11 or newer
python3 -c "import amr"    # the package must be importable
```

If the import fails, install the package in the repository root:

```bash
python3 -m pip install -e ".[test]"
```

If `pip` cannot reach an index, the repository also works from a checkout with nothing but
`pytest` installed — the root `conftest.py` puts `amr` on the path. Run `python3 -m pytest
properties/` in that case and read the matrix from the run in step 3.

## 2. Find out what there is to measure

```bash
python3 -m amr systems
```

One line per system: name, where it came from, whether it is a **default** or an **extra**,
and the forget modes it declares. An extra is measured only when it is named; if its
optional dependency is missing, the line says what to install instead of a mode list.

If the person did not say which system they meant, ask, and list what that command printed.
Do not pick for them — `reference` is the implementation this repository ships to
demonstrate the specification, and measuring it is not the same question as measuring
theirs.

## 3. Run it

Into a scratch directory, never into `results/`:

```bash
mkdir -p .amr-runs
SYSTEMS=reference python3 -m amr reproduce --out .amr-runs/reference
```

Substitute the system's name: `SYSTEMS=your-system python3 -m amr reproduce --out
.amr-runs/your-system`. Comma-separate to measure more than one in one run.

`.amr-runs/` is git-ignored and is the only place this skill writes. `results/` holds the
published record, produced deliberately by the repository's author with `make results`;
regenerating it is not part of running the suite and would make a committed file disagree
with its own provenance.

The command writes `raw.json` and `summary.md` into the directory and prints the summary.
It exits non-zero if any check FAILed. A DIVERGENCE does not fail it.

## 4. Read the matrix out loud

`summary.md` has one row per numbered check and one column per declared forget mode. Show
the person that table, then explain it. Three states, and **no score** — there is no
percentage, no grade, and no total to report:

**PASS** — the check ran and the system produced the outcome the specification requires.

**FAIL** — it did not, *or the check did not run at all*. A skipped check is a FAIL on
purpose: a system is not excused from a check by declaring something inconvenient, and
there is no not-applicable state in this suite.

**DIVERGENCE** — the specification deliberately leaves the behaviour open, and the system
behaved the way its declaration says it does. It is reported, not scored. Today the only
one is erasure inflation under `erase`: with the weakest ancestor gone, the weakest-link
walk over the shortened chain returns a *higher* number than before, and the system's
receipt says so ([version2/SPEC.md](../../../version2/SPEC.md) §6.4).

### For each FAIL, do this before saying anything about it

1. Find the check's row in [version2/SPEC.md](../../../version2/SPEC.md) §4–§7 by its
   number, and say what the row requires. Quote the required outcome.
2. Read `## Failures` in `summary.md`, which gives one line per failure naming what went
   wrong.
3. Name the capability field in §8 that the failure follows from. Most FAILs are a
   declaration being honest: `durability: "in-memory"` with no reopen support cannot
   survive the checks that reopen the store, and `revision: "none"` cannot survive the
   ones that revise a record.

**A FAIL means "this system does not provide this", not "this system is broken."** Most
stores were not built to answer these questions at all. Report the shape of the column,
not a verdict on the software.

## 5. Offer what else is there

- `python3 -m amr demo` — the reference's declaration, its matrix and its one divergence,
  in fifteen lines. The fastest way to see what the suite is claiming.
- `python3 -m amr replay examples/traces/scripted-demo.jsonl` — re-executes a recorded
  session and compares every value. Non-zero if anything moved.
- `make extras` — every installed extra as well as the defaults, written to
  `results/extras/<date>/`. Offer this only if the person asked for the extras; it writes
  inside the tree.

If they want their *own* store measured, point them at
[docs/adding-a-system.md](../../../docs/adding-a-system.md) and stop. Do not scaffold an
adapter, do not write a `capabilities()` for them, and do not guess at their declaration:
the declaration is the thing being measured, and one you invented would make the matrix
meaningless. [systems/persistent/](../../../systems/persistent/) is the route for a store
that only stores — it wraps the reference's semantics around a four-method backend.

## Guardrails

- **Never modify a tracked file.** Not the suite, not a system, not a document. If a check
  FAILs, that is the measurement.
- **Never edit the specification.** `version2/SPEC.md` and `version1/SPEC.md` are read-only
  here. A specification edited to match an implementation measures nothing. Disagreements
  with the text go to `design-notes/spec-feedback.md` as a numbered entry, by its author.
- **Never regenerate `results/`.** Write under `.amr-runs/` and nowhere else.
- **Never present a number you did not run.** If a command was not run, say it was not run.
