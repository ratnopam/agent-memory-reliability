"""``python -m harness`` — the entry point both Makefile targets go through.

``reproduce`` runs the suite, writes ``results/<today>/{raw.json,summary.md}``, prints the
summary, and exits non-zero if any check FAILed. A DIVERGENCE does not fail the command:
it is a reported disagreement with an open question in the specification, and a build that
went red on it would pressure whoever ran it to bury the finding.

``determinism`` runs ``reproduce`` twice into temporary directories and compares the bytes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness import report, results
from harness.determinism import compare_two_runs
from harness.runner import missing_checks, run_suite

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "version1" / "SPEC.md"


def reproduce(out: Path | None, quiet: bool) -> int:
    suite = run_suite(ROOT, spec_path=SPEC_PATH)
    document = results.build_document(suite, ROOT)
    directory = out or results.results_dir(ROOT)
    raw_path = results.write(document, directory)
    summary_path = report.write(document, SPEC_PATH, directory)

    drift = report.readme_matrix_drift(
        document, report.read_spec(SPEC_PATH), ROOT / "README.md"
    )

    if not quiet:
        print()
        print(summary_path.read_text(encoding="utf-8"), end="")
        print()
    counts = suite.counts()
    print(
        f"wrote {_display(raw_path)} and {_display(summary_path)} — "
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


def determinism() -> int:
    comparison = compare_two_runs(ROOT)
    stream = sys.stdout if comparison.identical else sys.stderr
    print(comparison.report(), file=stream)
    return 0 if comparison.identical else 1


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

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

    args = parser.parse_args(argv)
    if args.command == "reproduce":
        return reproduce(args.out, args.quiet)
    return determinism()


if __name__ == "__main__":
    raise SystemExit(main())
