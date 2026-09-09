# Results

`make reproduce` writes two files into `results/<YYYY-MM-DD>/`:

- `raw.json` — the machine-readable record. Schema below.
- `summary.md` — the human-readable tables, generated from `raw.json` alone.

`make contamination` writes two more into the same directory, and appends its table to
`summary.md`:

- `contamination.json` — the simulation's parameters, seed, and both arms' metrics.
- `contamination.svg` — the two-bar chart, hand-written, no plotting library.

The date is UTC, matching `generated_at`. A directory is one day's results, overwritten if
`amr reproduce` runs twice in a day; the commit SHA inside tells you which tree produced it.

The committed records are produced in a fresh clone with `--out` pointed outside the working
tree, then copied in. Writing into the clone would make the second of the two commands see
the first one's output and stamp `-dirty`, and two records of the same tree disagreeing about
which tree it was is worse than the extra step.

## Determinism

Exactly one field in `raw.json` may differ between two runs of the same tree:
`generated_at`. `make determinism` runs `reproduce` and `contamination` twice in separate
subprocesses, strips that field, and requires the remaining bytes to be identical.
`PYTHONHASHSEED` is not pinned, so anything that depends on set or dict iteration order fails
there. The contamination files carry no timestamp at all and are compared verbatim.

Everything else in the document is either a fact about the code under test or a fact about
the environment. Durations, absolute paths, and iteration orders are deliberately absent.

## Schema 0.1

```
schema            "0.1". A reader that does not recognise the value must refuse the file.
generated_at      UTC ISO 8601, seconds resolution. The only volatile field.
environment
  git_sha         The commit, with "-dirty" appended if the tree had uncommitted changes.
                  Untracked files count. Note that rerunning `reproduce` in place rewrites
                  the committed files in this directory, so a second run in the same day
                  reports the tree as dirty. The committed record is always from a clean
                  tree; see above for how.
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
                  Non-empty is a suite defect, and `make reproduce` exits non-zero.
```

## contamination.json

```
scenario          "contamination".
schema            "0.1".
system            The registered system the simulation ran against.
forget_mode       The mode the store was configured with. Nothing is forgotten during the
                  run; the mode is recorded because it is part of the configuration.
seed              The PRNG seed. `amr contamination --seed N` is the whole of the input.
environment       As above. No generated_at: there is nothing volatile to strip.
parameters        Roles, rounds, tau, the confidence distribution and its weights, the
                  citation sizes, the hallucinated-citation rate, and both injected beliefs.
arms
  ungated         The agent sees declared confidence only and may cite anything it reads.
  gated           A source whose *effective* confidence is below tau may be read, not cited.
    denominator   Derived writes measured. The two injected roots are not counted.
    inherited_count, inherited_fraction
                  Writes whose provenance walk reaches the injected 0.40 belief.
    inflated_count, inflated_fraction
                  Writes declared at or above 0.9 whose effective confidence is at or
                  below tau. The declared-versus-effective gap.
    max_chain_depth
                  Longest path beneath the 0.40 belief. The belief itself is depth 0.
    totals        rounds, writes, reads, strict_write_rejections, abstentions.
```

## Outcomes

`PASS` and `FAIL` are ordinary. `DIVERGENCE` is narrower than it looks: it is only used for
behaviour the specification deliberately leaves open (SPEC.md 6.4) in a system whose
capability declaration says it behaves that way. A divergence does not fail
`make reproduce`; a build that went red on it would pressure whoever ran it to bury the
finding. A `FAIL` — including a skipped test, which counts as a failure —
does fail it.
