"""``amr`` — the command line the Makefile calls. ``python -m amr`` is the same thing.

Six subcommands, and the Makefile is a convenience over them rather than the other way
round, so nothing in this repository can only be done by GNU make:

* ``test``          run the property suite, pytest's own output, nothing added
* ``reproduce``     run it and write ``results/<today>/{raw.json,summary.md}``
* ``determinism``   run ``reproduce`` twice and compare the bytes
* ``demo``          the reference through the suite, four blocks, no pytest output
* ``matrix``        render an existing ``raw.json`` as an SVG table
* ``contamination`` the three-role simulation, gated versus ungated

``reproduce`` exits non-zero if any check FAILed. A DIVERGENCE does not fail the command:
it is a reported disagreement with an open question in the specification, and a build that
went red on it would pressure whoever ran it to bury the finding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from amr import demo as demo_module
from amr import report, results
from amr.determinism import compare_two_runs
from amr.paths import repo_root, spec_path
from amr.runner import missing_checks, run_suite


def cmd_test(extra: list[str]) -> int:
    import pytest

    root = repo_root()
    return pytest.main([str(root / "properties"), "--rootdir", str(root), *extra])


def cmd_reproduce(out: Path | None, quiet: bool) -> int:
    root = repo_root()
    spec_file = spec_path(root)
    suite = run_suite(root, spec_path=spec_file)
    document = results.build_document(suite, root)
    directory = out or results.results_dir(root)
    raw_path = results.write(document, directory)
    summary_path = report.write(document, spec_file, directory)
    drift = report.readme_matrix_drift(
        document, report.read_spec(spec_file), root / "README.md"
    )

    if not quiet:
        print()
        print(summary_path.read_text(encoding="utf-8"), end="")
        print()
    counts = suite.counts()
    print(
        f"wrote {_display(raw_path, root)} and {_display(summary_path, root)} — "
        f"{counts['tests']} tests, {counts['PASS']} PASS, {counts['FAIL']} FAIL, "
        f"{counts['DIVERGENCE']} DIVERGENCE"
    )
    gaps = missing_checks(suite)
    for gap in gaps:
        print(
            f"missing: {gap.check} for {gap.system}/{gap.mode} — {gap.reason}",
            file=sys.stderr,
        )
    if drift:
        print(drift, file=sys.stderr)
    return 1 if suite.failed or gaps or drift else 0


def cmd_determinism() -> int:
    comparison = compare_two_runs(repo_root())
    stream = sys.stdout if comparison.identical else sys.stderr
    print(comparison.report(), file=stream)
    return 0 if comparison.identical else 1


def cmd_demo() -> int:
    print(demo_module.transcript(repo_root()), end="")
    return 0


def cmd_matrix(raw: Path, as_svg: bool, out: Path | None) -> int:
    if not as_svg:
        document = results.load(raw)
        spec = report.read_spec(spec_path())
        system = document["runs"][0]["system"]
        print("\n".join(report.poster_matrix(document, spec, system)))
        return 0
    print(demo_module.write_matrix_svg(raw, out))
    return 0


def cmd_contamination(seed: int, out: Path | None, quiet: bool) -> int:
    from scenarios.contamination import run as contamination

    root = repo_root()
    return contamination.main(root, seed=seed, out=out, quiet=quiet)


def _display(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amr", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("test", help="run the property suite (pytest arguments pass through)")

    run = commands.add_parser("reproduce", help="run the suite and write results")
    run.add_argument(
        "--out",
        type=Path,
        default=None,
        help="directory for raw.json and summary.md (default results/<today>/)",
    )
    run.add_argument(
        "--quiet", action="store_true", help="do not print the summary to stdout"
    )

    commands.add_parser(
        "determinism", help="run reproduce twice and compare the results byte for byte"
    )
    commands.add_parser("demo", help="the reference, its matrix, and its one divergence")

    matrix = commands.add_parser("matrix", help="render a results matrix from raw.json")
    matrix.add_argument("raw", type=Path, help="path to a results/<date>/raw.json")
    matrix.add_argument("--svg", action="store_true", help="write an SVG table")
    matrix.add_argument("--out", type=Path, default=None, help="output path for --svg")

    contamination = commands.add_parser(
        "contamination", help="the three-role contamination simulation"
    )
    contamination.add_argument("--seed", type=int, default=7)
    contamination.add_argument("--out", type=Path, default=None)
    contamination.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if argv and argv[0] == "test":
        return cmd_test(argv[1:])
    args = parser.parse_args(argv)
    if args.command == "reproduce":
        return cmd_reproduce(args.out, args.quiet)
    if args.command == "determinism":
        return cmd_determinism()
    if args.command == "demo":
        return cmd_demo()
    if args.command == "matrix":
        return cmd_matrix(args.raw, args.svg, args.out)
    return cmd_contamination(args.seed, args.out, args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
