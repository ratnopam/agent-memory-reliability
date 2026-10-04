# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[semantic versioning](https://semver.org/spec/v2.0.0.html). The package version and the
specification version move independently: the specification carries its own version and its own
changelog at the top of [version2/SPEC.md](version2/SPEC.md), and
[version1/SPEC.md](version1/SPEC.md) is frozen.

## [Unreleased]

### Changed

- Specification draft 0.6. The fourth forget mode `residue` and its `floor` field are withdrawn:
  they were normative text no implementation could be held to, specified ahead of anyone building
  one. The idea survives as open question 8, rewritten to ask whether a forget could leave only a
  bound on its descendants, with no record and no explanation. Three feedback entries are applied:
  §3.1's `NotFound` row is renamed `NotFoundError` and required to be catchable as a `LookupError`;
  a sixth failure signal `StoreIntegrityError` names the snapshot whose edges dangle, which MUST be
  rejected rather than opened with the dangling edge dropped; and §8 states that `notes` is the one
  field a declaration may omit. No numbered check moved: twenty-six, as before, and all 78 matrix
  cells are unchanged.

## [0.1.0] — 2026-09-09

### Added

- The specification: four properties, twenty-six numbered falsifiable checks, twelve operations,
  three forget modes, and a declaration every system fills in ([version2/SPEC.md](version2/SPEC.md), draft v0.5).
- A conformance suite parameterised over every registered system × forget mode, reporting PASS,
  FAIL or DIVERGENCE, with no not-applicable state and a skipped test counted as a FAIL.
- A reference implementation over the standard library only, and `amr.protocol` as the whole of
  the coupling between a system and the suite.
- Discovery through the `amr.systems` entry-point group, so a new system adds columns without a
  file in this repository being edited.
- The erasure-inflation finding: forgetting an ancestor can raise a descendant's effective
  confidence, reported as a DIVERGENCE rather than scored.
- A taxonomy of failure modes, each with an executable reproduction whose source is asserted
  byte-identical to the snippet documenting it.
- A three-arm contamination simulation — ungated, surfaced, gated — over deterministic policies
  and a seeded PRNG, with a hand-written chart and no model in the loop.
- Byte-level determinism as a build gate: two runs of the same tree must agree exactly once the
  timestamp is stripped.
- `make release-check`: ten gates in one command — suite, results, determinism, simulation, lint,
  the standard-library gate, the model-import grep, the naming grep, README drift, and links.
- An external-adapter kit — [docs/adding-a-system.md](docs/adding-a-system.md) and
  [examples/external-adapter/](examples/external-adapter/) — with its failures predicted by its declaration.
