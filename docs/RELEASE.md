# Cutting a release

The order matters in one place only: the results have to be regenerated from the tree that gets
tagged, so the commit a reader checks out is the commit the numbers came from. That is step 2,
and step 8 confirms no later commit moved the code out from under it. Everything else can be done
in any order, and everything with a command next to it can be re-run.

Nothing here is automated on purpose. A release of this repository is a claim that the matrix in
the README is what the code produces, and the last person to check that should be a person.

## 1. `make release-check` is green

```
make release-check
```

Eleven gates, one line each, first red stops the run: the conformance suite, the results, byte
determinism, the contamination simulation, lint, the standard-library gate over
`systems/reference/`, the model-import grep, the former-name grep, the README's rendering of the
committed results, every relative link in `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md` and
`docs/`, and the architecture diagram's facts. If a gate is red, it is red for the release too —
there is no such thing as a known-red gate here.

Running it leaves the tree exactly as it was: every gate that produces results writes to a
temporary directory. Regenerating what is committed is step 2, on purpose — `make results` is the
only target that writes the record.

A twelfth gate exists and is not in this command. `.github/check_example_adapter.py` asserts that
a real `pip install -e examples/external-adapter` is discovered by its entry point and fails
exactly the five checks its declaration predicts; it needs an index, and `release-check`'s
contract is that it runs offline. It runs as the `examples` job in CI, which step 10 covers.

## 2. The results are regenerated from the tree being tagged

```
git status --porcelain          # empty, or the sha in raw.json will say -dirty
make results
git add results/ docs/contamination.svg && git commit -s -m "results: record the run from a clean tree at $(git rev-parse --short HEAD)"
```

`make results` is `reproduce` and then the simulation, in that order because the simulation upserts
a `## Contamination` section into the `summary.md` the first command writes. It is also the only
thing that refreshes `docs/contamination.svg`, the undated path the README embeds — everything
else, including every gate above, writes outside the tree. `raw.json` records
`environment.git_sha`; a `-dirty` suffix in a released results directory means the numbers came
from a tree nobody can check out, which is the one failure mode this step exists to prevent.

## 3. The README renders the results, figure for figure

```
make drift
```

Three comparisons against what is committed, running nothing. The first `| Property |` table in
`README.md` has to match the newest `results/<date>/raw.json` byte for byte; the contamination
table's five figures per arm — writes, inherited, inflated, depth — have to equal the newest
`contamination.json`, percentages included, because those numbers are typed by hand and no
generator writes them; and `docs/contamination.svg` has to be byte-identical to that run's chart,
since the README embeds the undated copy and a reader would otherwise see last month's bars beside
this month's numbers. `make reproduce` makes the first comparison against its own run; both should
pass.

## 4. The former name is gone

```
make release-check           # gate eight, "no former name in the tree"
```

The eighth gate greps the whole tree, tracked files only, case-insensitively, for the name this
work carried before it was renamed. It covers design notes and this file too, so a stray mention
in prose counts — which is why neither the gate nor this checklist writes the name out: the
pattern is assembled from two halves in the `Makefile`, because a gate whose own text is the only
match trains people to switch it off.

## 5. The diagram's picture is current

```
make release-check           # gate eleven, "the diagram's facts hold"
```

`README.md` embeds `docs/architecture.svg`. Its *facts* are now gated:
`.github/check_diagram.py` requires every source file the diagram names to exist, the check count
it prints to equal the count `properties/test_spec_coverage.py` parses out of the specification,
and the word "twelve" to appear only while `MemorySystem` declares twelve operations. What no gate
can read is the picture — boxes in the wrong place, an arrow that no longer describes the flow,
a label that is true of nothing. Look at it rendered, once, before the tag.

If `docs/architecture.png` is to be kept, re-export it from the SVG at release time or delete it;
a stale PNG that nobody notices is worse than no PNG, and nothing here can tell the difference.

## 6. The GIF, if it is being refreshed

`docs/demo.tape` is the script; rendering it needs `vhs`, which is not a dependency of anything
here. If the demo has changed, re-render and look at the result before committing it — a GIF is
accepted by eye or not at all. If it has not changed, there is nothing to do: the committed GIF
stays as it is.

## 7. `SPEC-old.md` — the author's call

`design-notes/SPEC-old.md` predates `version1/SPEC.md` and is referenced by neither. Keeping it,
leaving it where it is, or dropping it are all defensible; deciding is not a checklist item that
can be delegated, and the handoffs deliberately left it alone. It was moved out of the root under
`design-notes/` so that a first-time reader does not meet a superseded specification first, which
settles where it sits but not whether it should exist. Make that call before the tag rather than
after.

## 8. The results are the last thing regenerated

```
git diff --stat $(git rev-parse HEAD)   # nothing uncommitted
make results
git status --porcelain                  # empty, or step 2 ran before the last code change
```

Step 2 is the normal path; this step is the check that nothing slipped in behind it. Any commit
touching `src/`, `systems/`, `properties/`, or `scenarios/` after step 2 invalidates the record,
and a `results/` directory that disagrees with the code it was committed beside is the one defect
this whole file exists to prevent. If the second `git status` is not empty, re-commit the results
and start again at step 1 — the gates are cheap and a wrong matrix in a tagged release is not.

## 9. Tag, then push

```
git tag -a v0.1.0    -m "the conformance suite, the reference, and the erasure-inflation finding"
git tag -a spec-v0.6 -m "specification draft v0.6: 26 numbered checks"
git push origin main --follow-tags
```

Two tags, because the package version and the specification version move independently — a
specification draft can advance without a release, and a release can ship without the
specification moving. [CHANGELOG.md](../CHANGELOG.md) is the package's history; the changelog at
the top of [version2/SPEC.md](../version2/SPEC.md) is the specification's.

## 10. CI is green on the tag

Watch the run for the tagged commit, not for the branch: the `test` matrix covers Python 3.11
through 3.14, and a version-dependent failure is exactly the kind of thing a local `release-check`
on one interpreter cannot see. Each leg uploads its own `results/**` artefacts; if two legs
disagree, the determinism claim is wrong on some interpreter and the release should wait.

The `examples` job is the one that cannot be run locally at all: it installs
`examples/external-adapter` with real `pip` from a real index, and then asserts the adapter is
discovered by its entry point and fails exactly the checks its README claims. A green `test`
matrix with a red `examples` job means the documented extension path is broken even though
everything in the tree passes — which is precisely why that job exists off to the side.

## Not verifiable from inside the repository

Five things on this list cannot be closed by running anything here, and are named so that they
are not mistaken for gates: CI on the tag (step 10) needs a remote and a runner, and its
`examples` job needs a package index; pushing the tags (step 9) needs push rights; the GIF (step
6) is accepted by eye; the diagram's picture and any PNG re-export (step 5) are judgments about
an image; and the `SPEC-old.md` decision (step 7) is a judgment, not a check. Everything else in
this file is a command whose exit status is the answer.
