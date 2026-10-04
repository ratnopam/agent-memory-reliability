"""``amr`` — the command line the Makefile calls. ``python -m amr`` is the same thing.

Nine subcommands, and the Makefile is a convenience over them rather than the other way
round, so nothing in this repository can only be done by GNU make:

* ``test``          run the property suite, pytest's own output, nothing added
* ``reproduce``     run it and write ``results/<today>/{raw.json,summary.md}``
* ``determinism``   run ``reproduce`` and ``contamination`` twice, compare the bytes
* ``demo``          the reference through the suite, four blocks, no pytest output
* ``matrix``        render an existing ``raw.json`` as an SVG table
* ``contamination`` the three-role simulation, three arms
* ``drift``         the README's matrix, figures and chart against committed results
* ``replay``        re-execute a recorded tool-call trace and compare every result
* ``systems``       what is registered: default or extra, and in what modes

``reproduce`` exits non-zero if any check FAILed. A DIVERGENCE does not fail the command:
it is a reported disagreement with an open question in the specification, and a build that
went red on it would pressure whoever ran it to bury the finding.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from amr import demo as demo_module
from amr import registry, report, results
from amr.determinism import compare_two_runs
from amr.paths import repo_root, spec_path
from amr.runner import missing_checks, run_suite


def cmd_test(extra: list[str]) -> int:
    import pytest

    root = repo_root()
    return pytest.main([str(root / "properties"), "--rootdir", str(root), *extra])


def cmd_reproduce(out: Path | None, quiet: bool, extras: bool = False) -> int:
    root = repo_root()
    spec_file = spec_path(root)
    if extras:
        # Set before the suite runs, because the registry reads it when it is asked for
        # systems. The default output directory moves with it: an extras run is not the
        # published matrix and must not be written where the published matrix lives.
        os.environ["AMR_EXTRAS"] = "1"
    suite = run_suite(root, spec_path=spec_file)
    document = results.build_document(suite, root)
    if out is not None:
        directory = out
    elif extras or registry.extras_requested():
        directory = results.extras_dir(root)
    else:
        directory = results.results_dir(root)
    raw_path = results.write(document, directory)
    summary_path = report.write(document, spec_file, directory)
    # The README renders the reference's matrix. A run filtered with SYSTEMS, or one
    # carrying the extras, is not the document that table is about, so it is not evidence
    # of drift either way.
    drift = (
        None
        if registry.selected_names() or registry.extras_requested()
        else report.readme_matrix_drift(
            document, report.read_spec(spec_file), root / "README.md"
        )
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


def cmd_drift(raw: Path | None) -> int:
    """The same check ``reproduce`` makes, over what is committed rather than a fresh run.

    ``make release-check`` wants each gate to be its own line, and a release is made from
    the tree as it stands: the question here is whether the table a reader sees in the
    README is the table in ``results/<date>/``, not whether today's run agrees with itself.

    Four things the README asserts and nothing generates: the conformance matrix, the
    contamination figures, the chart, and the two-system comparison from an extras run.
    All four are reported together rather than one per run, because a reader fixing one
    wants to know about the others.

    The comparison is the one that may have nothing to compare: an extras run needs an
    optional dependency, so ``latest_extras`` answers ``None`` in a checkout without one
    and the check passes unless the README renders a table anyway.
    """
    root = repo_root()
    readme = root / "README.md"
    path = raw or results.latest_raw(root)
    document = results.load(path)
    spec = report.read_spec(spec_path(root))
    contamination_path = results.latest_contamination(root)
    contamination = results.load_contamination(contamination_path)
    extras_path = results.latest_extras(root)
    drifts = [
        report.readme_matrix_drift(document, spec, readme),
        report.readme_contamination_drift(contamination, readme),
        report.embedded_chart_drift(root, contamination_path.with_name("contamination.svg")),
        report.readme_pair_drift(
            None if extras_path is None else results.load(extras_path), spec, readme
        ),
    ]
    found = [drift for drift in drifts if drift]
    if found:
        print("\n".join(found), file=sys.stderr)
        return 1
    compared = (
        "no extras run to compare"
        if extras_path is None
        else f"the comparison in {_display(extras_path, root)}"
    )
    print(
        f"README.md renders the matrix in {_display(path, root)}, the figures in "
        f"{_display(contamination_path, root)}, that run's chart, and {compared}"
    )
    return 0


def cmd_systems() -> int:
    """The inventory, including the rows a default run leaves out.

    Printed rather than filtered through ``SYSTEMS``, because the question this answers
    is what could be run, and a reader who has to guess a name guesses wrong. A system
    whose optional dependency is absent is listed too, with what to install, because
    "not here" and "not supported" are different answers.
    """
    rows = []
    for registration in registry.registered():
        missing = registration.missing
        if missing:
            modes = f"needs {', '.join(missing)}"
            if registration.extra:
                modes += f' — pip install -e ".[{registration.extra}]"'
        else:
            modes = ", ".join(
                mode.value for mode in registry.modes_for(registration)
            )
        rows.append((registration.name, registration.source, registration.kind, modes))
    if not rows:
        print("no systems registered", file=sys.stderr)
        return 1
    width = max(len(name) for name, _, _, _ in rows)
    source_width = max(len(source) for _, source, _, _ in rows)
    for name, source, kind, modes in rows:
        print(f"{name:<{width}}  {source:<{source_width}}  {kind:<7}  {modes}")
    return 0


def cmd_replay(traces: list[Path], system: str) -> int:
    """Re-run recorded tool calls and report any value that came back different.

    Non-zero on the first disagreement across every trace, not the first trace that
    disagrees: a reader fixing one difference wants to see the others.
    """
    from amr import replay as replay_module

    runs = replay_module.replay_all(traces, system)
    for run in runs:
        print(run.report(), file=sys.stdout if run.identical else sys.stderr)
    return 0 if all(run.identical for run in runs) else 1


def cmd_contamination(seed: int, out: Path | None, quiet: bool, rounds: int | None) -> int:
    from scenarios.contamination import run as contamination

    root = repo_root()
    # The scenario owns the default, so --help does not have to import the scenario.
    extra = {} if rounds is None else {"rounds": rounds}
    return contamination.main(root, seed=seed, out=out, quiet=quiet, **extra)


def _display(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


USAGE = """the conformance suite for agent memory reliability.

  amr test            run the property suite; pytest's arguments pass through
  amr reproduce       run it and write results/<today>/{raw.json,summary.md}
  amr determinism     run reproduce and contamination twice, compare the bytes
  amr demo            the reference, its matrix, its one divergence: fifteen lines
  amr matrix          render an existing raw.json as an SVG table
  amr contamination   the three-role simulation: ungated, surfaced, gated
  amr drift           does README.md render the committed matrix, figures and chart?
  amr replay          re-execute a recorded tool-call trace; non-zero if a value moved
  amr systems         what is registered: name, source, default or extra, forget modes

A run with nothing set measures the default systems. SYSTEMS=a,b measures exactly those,
default or not; AMR_EXTRAS=1 adds every extra whose dependencies are installed, which is
what `amr reproduce --extras` does. An extras run writes results/extras/<today>/, because
the published matrix is the default run and adding an adapter must not be able to move it.

reproduce exits non-zero if any check FAILed. A DIVERGENCE does not: it is a reported
disagreement with an open question in the specification, and a build that went red on it
would pressure whoever ran it to bury the finding.
"""


def build_parser() -> argparse.ArgumentParser:
    # The module docstring is prose and argparse would reflow it into one paragraph. The
    # command line is the interface, so its help is written for a terminal, not derived.
    parser = argparse.ArgumentParser(
        prog="amr",
        description=USAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
    run.add_argument(
        "--extras",
        action="store_true",
        help="add every installed extra and write results/extras/<today>/ instead",
    )

    commands.add_parser(
        "determinism",
        help="run reproduce and contamination twice and compare the bytes",
    )
    commands.add_parser("demo", help="the reference, its matrix, and its one divergence")

    matrix = commands.add_parser("matrix", help="render a results matrix from raw.json")
    matrix.add_argument("raw", type=Path, help="path to a results/<date>/raw.json")
    matrix.add_argument("--svg", action="store_true", help="write an SVG table")
    matrix.add_argument("--out", type=Path, default=None, help="output path for --svg")

    contamination = commands.add_parser(
        "contamination", help="the three-role contamination simulation"
    )
    contamination.add_argument(
        "--seed", type=int, default=7, help="the PRNG seed; the whole of the input"
    )
    contamination.add_argument(
        "--out",
        type=Path,
        default=None,
        help="directory for contamination.json and the chart (default results/<today>/)",
    )
    contamination.add_argument(
        "--rounds",
        type=int,
        default=None,
        help="rounds per arm (default 60); lower it to shorten a run, not to change a finding",
    )
    contamination.add_argument(
        "--quiet", action="store_true", help="do not print the table to stdout"
    )

    drift = commands.add_parser(
        "drift",
        help="check README.md against the committed matrix, figures and chart",
    )
    drift.add_argument(
        "raw",
        type=Path,
        nargs="?",
        default=None,
        help="a results/<date>/raw.json (default: the newest one committed)",
    )

    commands.add_parser(
        "systems", help="list the registered systems, default and extra"
    )

    replay = commands.add_parser(
        "replay",
        help="re-execute a recorded tool-call trace and compare every result",
    )
    replay.add_argument(
        "traces", type=Path, nargs="+", help="one or more trace files (JSON lines)"
    )
    replay.add_argument(
        "--system",
        default="reference",
        help="the registered system to replay against (default: reference)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    try:
        # Resolved before anything runs. Otherwise a mistyped SYSTEMS surfaces as a
        # conftest import error with the real message buried under pytest's frames.
        registry.systems()
        if argv and argv[0] == "test":
            return cmd_test(argv[1:])
        return _dispatch(parser.parse_args(argv))
    except (LookupError, ImportError) as error:
        # Naming a system that is not registered, or one whose optional dependency is
        # not installed. Both carry the inventory and what to install; a traceback would
        # bury that under frames nobody who typed a name needs to read.
        print(f"amr: {error}", file=sys.stderr)
        print("amr: `amr systems` lists what this interpreter can run", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "reproduce":
        return cmd_reproduce(args.out, args.quiet, args.extras)
    if args.command == "determinism":
        return cmd_determinism()
    if args.command == "demo":
        return cmd_demo()
    if args.command == "matrix":
        return cmd_matrix(args.raw, args.svg, args.out)
    if args.command == "drift":
        return cmd_drift(args.raw)
    if args.command == "replay":
        return cmd_replay(args.traces, args.system)
    if args.command == "systems":
        return cmd_systems()
    return cmd_contamination(args.seed, args.out, args.quiet, args.rounds)


if __name__ == "__main__":
    raise SystemExit(main())
