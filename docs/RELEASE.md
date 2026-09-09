# Cutting a release

The order matters in one place only: the results have to be regenerated from the tree that gets
tagged, so the commit a reader checks out is the commit the numbers came from. Everything else
can be done in any order, and everything with a command next to it can be re-run.

Nothing here is automated on purpose. A release of this repository is a claim that the matrix in
the README is what the code produces, and the last person to check that should be a person.

## 1. `make release-check` is green

```
make release-check
```

Ten gates, one line each, first red stops the run: the conformance suite, the results, byte
determinism, the contamination simulation, lint, the standard-library gate over
`systems/reference/`, the model-import grep, the former-name grep, the README matrix, and every
relative link in `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md` and `docs/`. If a gate is red, it
is red for the release too — there is no such thing as a known-red gate here.

Running it leaves the tree exactly as it was: the two gates that produce results write to a
temporary directory. Regenerating what is committed is step 2, on purpose.

## 2. The results are regenerated from the tree being tagged

```
git status --porcelain          # empty, or the sha in raw.json will say -dirty
make reproduce
make contamination
git add results/ && git commit -s -m "results: record the run from a clean tree at $(git rev-parse --short HEAD)"
```

`reproduce` first, then `contamination`: the simulation upserts a `## Contamination` section into
the `summary.md` the first command writes. `raw.json` records `environment.git_sha`; a `-dirty`
suffix in a released results directory means the numbers came from a tree nobody can check out,
which is the one failure mode this step exists to prevent.

## 3. The matrix in the README is the matrix in the results

```
make drift
```

This reads the newest committed `results/<date>/raw.json` and requires the first `| Property |`
table in `README.md` to match it byte for byte. It runs nothing, so it is the right check here:
the question is whether the table a reader sees is the table in `results/<date>/summary.md`, not
whether a fresh run agrees with itself. `make reproduce` makes the same comparison against its
own run; both should pass.

## 4. The former name is gone

```
make release-check           # gate eight, "no former name in the tree"
```

The eighth gate greps the whole tree, tracked files only, case-insensitively, for the name this
work carried before it was renamed. It covers design notes and this file too, so a stray mention
in prose counts — which is why neither the gate nor this checklist writes the name out: the
pattern is assembled from two halves in the `Makefile`, because a gate whose own text is the only
match trains people to switch it off.

## 5. The diagram is current

`README.md` embeds `docs/architecture.svg`. Compare the strings inside it against the release —
the check count, the number of operations, and the operation list drift silently, because no test
reads a diagram. If `docs/architecture.png` is to be kept, re-export it from the SVG at release
time or delete it; a stale PNG that nobody notices is worse than no PNG.

## 6. The chart path in the README is today's

`README.md` embeds `results/<date>/contamination.svg` at a dated path. Regenerating the results
into a new dated directory leaves that link pointing at the previous run. `make release-check`
catches the case where the file no longer exists (gate ten), but not the case where an older one
is still there, so read the path and confirm it is the directory step 2 wrote.

## 7. `SPEC-old.md` — the author's call

`SPEC-old.md` sits at the root, predates `version1/SPEC.md`, and is referenced by neither. Keeping
it, moving it under `design-notes/`, or dropping it are all defensible; deciding is not a checklist
item that can be delegated, and the handoffs deliberately left it alone. Make the decision before
the tag rather than after, because whichever way it goes it changes what a first-time reader finds
at the root.

## 8. Tag, then push

```
git tag -a v0.1.0    -m "the conformance suite, the reference, and the erasure-inflation finding"
git tag -a spec-v0.5 -m "specification draft v0.5: 26 numbered checks"
git push origin main --follow-tags
```

Two tags, because the package version and the specification version move independently — a
specification draft can advance without a release, and a release can ship without the
specification moving. [CHANGELOG.md](../CHANGELOG.md) is the package's history; the changelog at
the top of [version2/SPEC.md](../version2/SPEC.md) is the specification's.

## 9. CI is green on the tag

Watch the run for the tagged commit, not for the branch: the matrix covers Python 3.11 through
3.14, and a version-dependent failure is exactly the kind of thing a local `release-check` on one
interpreter cannot see. Each leg uploads its own `results/**` artefacts; if two legs disagree, the
determinism claim is wrong on some interpreter and the release should wait.

## Not verifiable from inside the repository

Three things on this list cannot be closed by running anything here, and are named so that they
are not mistaken for gates: CI on the tag (step 9) needs a remote and a runner; pushing the tags
(step 8) needs push rights; and the `SPEC-old.md` decision (step 7) is a judgment, not a check.
Everything else in this file is a command whose exit status is the answer.
