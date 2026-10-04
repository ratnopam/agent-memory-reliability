# Contributing

There are two ways in. Both are pull requests, and neither of them requires you to be right.

## 1. Results from a system

Run the suite against a memory system and submit what came out. Write an adapter over the
twelve operations, declare its capabilities, publish an `amr.systems` entry point, and open a
pull request adding `results/<date>-<system>/` with the `raw.json` and `summary.md` your run
produced, plus a short `README.md` in that directory naming the version you measured, how it
was configured, and anything a reader needs to get the same numbers. The adapter itself can
live in your own repository; a link is enough. [docs/adding-a-system.md](docs/adding-a-system.md)
is the guide and [examples/external-adapter/](examples/external-adapter/) is a working adapter
to copy.

Results with failures in them are the interesting case, not an embarrassment. A matrix with
FAILs and a declaration that explains them is worth more than a clean sheet nobody can
reproduce. If you believe a check is wrong rather than your system, say so — that is path 2,
and the two can be the same pull request.

## 2. Feedback on the specification

The specification is the artefact under test here as much as any implementation. If a check is
ambiguous, unfalsifiable, arguing for a behaviour it does not state, or missing a property that
matters, open an issue using the **specification feedback** template, or a pull request against
[version2/SPEC.md](version2/SPEC.md) — it is a draft and it moves. Every accepted piece of
feedback becomes a numbered entry in the project's feedback log with the reading that was taken
and why, and the changelog at the foot of [version2/SPEC.md](version2/SPEC.md) names each entry
against the version that absorbed it, so the next reader can see the argument rather than just
the outcome. A new numbered check has to come with the test that fails without it, because
a check nobody can run is a claim, and the point of this repository is that claims are checked.
[version1/SPEC.md](version1/SPEC.md) is frozen and does not move.

## Sign-off, not a CLA

There is no contributor licence agreement. Instead, certify the
[Developer Certificate of Origin](https://developercertificate.org/) by signing off every
commit:

```
git commit -s
```

That adds a `Signed-off-by:` line with the name and email in your git config, which is all the
DCO asks for. Contributions are under [Apache 2.0](LICENSE), the licence this repository is
released under, and you keep your copyright.

## What will not be merged

A check that special-cases a forget mode, because a check that branches on the mode is measuring
the mode rather than the property, and P2.5 in particular is one signed comparison for exactly
that reason. A dependency inside `systems/reference/`, which imports the standard library and
nothing else so that the reference cannot be accused of inheriting a vendor's behaviour —
`.github/check_stdlib_only.py` enforces it. Anything that puts a model in the measurement path:
no client, no API call, no "LLM as judge", not even behind an optional extra, because a verdict
that depends on a model is a verdict nobody can reproduce byte for byte, and `make determinism`
is what makes the results usable as evidence. Also, less philosophically: anything that makes
`make release-check` red.

## Before you open it

```
make release-check
```

Ten gates, one line each: the suite, the results, determinism, the simulation, lint, the
standard-library gate over the reference, the model-import grep, the naming grep, the README
matrix, and the documentation links. Green here is what CI checks too, so a red gate locally is
a red build later. If a gate is red for a reason you think is wrong, open the pull request
anyway and say which one — that is feedback, and it is path 2.
