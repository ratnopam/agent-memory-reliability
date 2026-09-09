# Build plan — Phase 0

> Historical. `harness/` below became `src/amr/` in Phase 1.

Order is dependency order. Each step ends with a green test run and a commit.

## 1. `amr/protocol.py` (edit, additive only) + `amr/extensions.py` (new)

`protocol.py` gains only what a numbered conformance check cannot be written without:
`Origin` and `Record.origin` (SPEC §2.1), `write(..., origin=)`, `revisions(id, scope)`
(P2.6 says history is readable *after the fact*; the eight-operation set has no reader),
`UnresolvedSourceError` and `ForgottenRecordError` (I1.6 and "reject revise on a
tombstone" need distinguishable rejections), `ForgetReceipt.affected_scopes` (scope noted
per id). No renames, no removals, no restructuring.

`extensions.py` holds the two *optional* protocols the suite feature-detects, so the
SPEC §3 surface stays clean: `ScopeSharing` (grant / revoke / grants — I4.2 is untestable
without it) and `Reopenable` (`to_dict` + `reopen` — I1.5 round-trip).

## 2. `systems/reference/`

- `store.py` — `StoredRecord`, id allocation (`m1`, `m2`, … never reused), reverse child
  index, forgotten-id ledger, grants, `to_dict` / `from_dict` (every field, including
  tombstones, revisions, grants, the id counter).
- `confidence.py` — iterative memoized `effective()`, invalidation over `{id} ∪ descendants`,
  `min(∅) = 1.0`. Raises on an unresolvable source rather than skipping it.
- `scope.py` — visibility (native ∨ granted), grants, opaque-ancestor projection.
- `forget.py` — three modes, universal post-conditions, receipts with a delta per
  surviving descendant.
- `system.py` — `ReferenceSystem`, the façade implementing `MemorySystem`; `__init__.py`
  re-exports it and registers it.

## 3. `properties/`

`conftest.py`: `system` fixture parameterized over registry × declared modes, plus a
system-only parameterization for mode-independent supplementary tests; an autouse fixture
that stamps check id / system / mode / docstring into `user_properties` so the runner
never parses node ids; a `divergence` recorder; `pytest_report_teststatus` so DIVERGENCE
prints as its own status. No `xfail` anywhere.

One module per property, one test per spec check, marker `@pytest.mark.check("P2.5")`.
Supplementary tests carry `@pytest.mark.extra(...)`: the no-descendant control case,
ten fixed-seed random DAGs against `effective_confidence_reference`, and the taxonomy
reproductions. `test_spec_coverage.py` parses `version1/SPEC.md` and fails if any `| Pn.n`
row lacks exactly one marked test.

## 4. `harness/` runner side

`registry.py` (register / systems / discover via `pkgutil` over `systems`, `SYSTEMS`
filter) → `runner.py` (`pytest.main` in-process with a collecting plugin) →
`results.py` (schema `0.1`, environment capture, canonical JSON) → `report.py`
(per-system check × mode table, compact four-property poster matrix, P2.5 called out) →
`determinism.py` (two runs into temp dirs, timestamp stripped, byte compare).

## 5. `taxonomy/`

Four Markdown entries. Each reproduction lives in `taxonomy/repro/<name>.py` as a function
taking a `MemorySystem` and returning a result dict; the Markdown embeds the same file's
source path and `properties/test_taxonomy.py` imports and runs it. Docs cannot drift.

## 6. `mcp/`

`server.py`: nine tools (the eight operations + `memory_capabilities`, plus
`memory_revisions` since `revise` history is a conformance requirement) over one
`ReferenceSystem`, stdio. No `__init__.py` — a namespace directory does not shadow the
installed `mcp` package. `test_server.py` launches it as a subprocess over stdio and
checks the arithmetic; `importorskip` keeps it out of the way when `mcp` is absent.

## 7. Wrap-up

`Makefile` (test / reproduce / determinism / lint, auto-detects `.venv/bin/python`),
`.github/workflows/ci.yml` (3.11 + 3.12), `results/<date>/`, `results/README.md`,
`README.md`, `DECISIONS.md`, `design-notes/spec-feedback.md`, fresh-clone verification in
`/tmp`, `design-notes/build-report.md`.
