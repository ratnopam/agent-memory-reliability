# Results

`make reproduce` writes two files into `results/<YYYY-MM-DD>/`:

- `raw.json` — the machine-readable record. Schema below.
- `summary.md` — the human-readable tables, generated from `raw.json` alone.

The date is UTC, matching `generated_at`. A directory is one day's results, overwritten if
the harness runs twice in a day; the commit SHA inside tells you which tree produced it.

## Determinism

Exactly one field in `raw.json` may differ between two runs of the same tree:
`generated_at`. `make determinism` runs `reproduce` twice in separate subprocesses, strips
that field, and requires the remaining bytes to be identical. `PYTHONHASHSEED` is not
pinned, so anything that depends on set or dict iteration order fails there.

Everything else in the document is either a fact about the code under test or a fact about
the environment. Durations, absolute paths, and iteration orders are deliberately absent.

## Schema 0.1

```
schema            "0.1". A reader that does not recognise the value must refuse the file.
generated_at      UTC ISO 8601, seconds resolution. The only volatile field.
environment
  git_sha         The commit, with "-dirty" appended if the tree had uncommitted changes.
  platform        "darwin", "linux", ...
  python_implementation, python_version
  pytest_version
spec
  path            The specification the check ids were read from.
  checks          Every numbered check id the specification declares, in document order.
totals            tests, PASS, FAIL, DIVERGENCE. Counts every executed test.
runs[]            One entry per (system, forget_mode). This is a column of the matrix.
  system, system_version
  forget_mode     "tombstone" | "cascade" | "erase"
  capabilities    The full declaration, SPEC.md 8, with sets sorted.
  checks[]        The numbered checks, in specification order.
    check         "P2.5"
    name, nodeid  The test that produced the outcome.
    outcome       "PASS" | "FAIL" | "DIVERGENCE"
    detail        One line: what diverged, what failed, or what the check asserts.
    divergences[] Present only when outcome is DIVERGENCE.
      check, spec_ref, detail
  supplementary[] Checks that are not numbered in the specification but do depend on the
                  forget mode. Same shape, with "extra" instead of "check".
suite_checks[]    Executed tests that belong to no (system, forget_mode) cell: checks
                  whose answer cannot depend on a forget mode, and meta checks over the
                  specification and the taxonomy.
missing_checks[]  Numbered checks the specification declares that a run did not report.
                  Non-empty is a harness failure, and `make reproduce` exits non-zero.
```

## Outcomes

`PASS` and `FAIL` are ordinary. `DIVERGENCE` is narrower than it looks: it is only used for
behaviour the specification deliberately leaves open (SPEC.md 6.4) in a system whose
capability declaration says it behaves that way. A divergence does not fail
`make reproduce`; a build that went red on it would pressure whoever ran it to bury the
finding. A `FAIL` — including a skipped test, which the harness counts as a failure —
does fail it.
