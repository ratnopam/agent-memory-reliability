"""The two-system comparison the README carries, and the gate that keeps it honest.

``amr drift`` already asks whether the README still renders the published matrix. The
comparison table is the same kind of claim about a different run: two adapters over one
store, one of them failing almost everything on purpose, and a reader who is being told
what the gap between them is. A table typed out by hand beside a run nobody diffs it
against is the most expensive thing in this repository to get wrong, because it is the
part a reader believes without checking.

So the rendering is generated and the README is compared with it. What is tested here is
the comparison itself: that it finds the table, that it finds the two systems by reading
the table's own header rather than by knowing an adapter's name, and that each way of
being wrong — a changed cell, a missing table, a missing run, a system that is not in the
document — is reported rather than passed over or raised as a traceback.

None of this needs an optional dependency. The documents below are written by hand for
that reason: a gate that could only be tested where an extra is installed is a gate that
is untested wherever it matters.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amr import report, results
from amr.paths import repo_root, spec_path

BARE = "store-alone"
LAYERED = "with-the-layer"
CHECKS = ("P1.1", "P1.2", "P2.5")


def _run(system: str, mode: str, outcomes: dict[str, str]) -> dict:
    return {
        "system": system,
        "forget_mode": mode,
        "checks": [
            {"check": check, "outcome": outcome} for check, outcome in outcomes.items()
        ],
    }


def _document(
    bare_modes: tuple[str, ...] = ("tombstone",),
    layered_modes: tuple[str, ...] = ("tombstone", "cascade"),
    bare: dict[str, str] | None = None,
) -> dict:
    """Two systems over three checks: the shape of the real document, three rows deep."""
    failing = bare or {"P1.1": "FAIL", "P1.2": "FAIL", "P2.5": "PASS"}
    passing = dict.fromkeys(CHECKS, "PASS")
    return {
        "spec": {"checks": list(CHECKS)},
        "runs": [
            *[_run(BARE, mode, failing) for mode in bare_modes],
            *[_run(LAYERED, mode, passing) for mode in layered_modes],
        ],
    }


@pytest.fixture(scope="module")
def spec() -> report.SpecText:
    return report.read_spec(spec_path(repo_root()))


def _readme(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "README.md"
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text("# a page\n\nsome prose\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------------------ rendering


def test_the_table_is_one_row_per_check_with_a_column_per_system(
    spec: report.SpecText,
) -> None:
    """The columns are the two systems, named by the document and not by this file."""
    lines = report.pair_table(_document(), spec, BARE, LAYERED)
    assert lines[0] == f"| Check | Scenario | {BARE} | {LAYERED} |"
    assert lines[0].startswith(report.PAIR_HEADER)
    assert lines[1] == "|---|---|---|---|"
    assert len(lines) == len(CHECKS) + 2

    cells = [line.strip("|").split("|") for line in lines[2:]]
    assert [cell[0].strip() for cell in cells] == list(CHECKS)
    assert [cell[2].strip() for cell in cells] == ["FAIL", "FAIL", "PASS"]
    assert [cell[3].strip() for cell in cells] == ["PASS"] * len(CHECKS)
    # The scenario comes from the specification, so the row says what was measured and
    # not only how it came out.
    assert cells[0][1].strip() == spec.scenario("P1.1")


def test_the_mode_is_one_both_systems_declare(spec: report.SpecText) -> None:
    """A one-mode column beside a three-mode column, compared at the mode they share.

    Otherwise the table would carry two differences at once — between the adapters and
    between the forget modes — and a reader could not tell which one a cell was about.
    """
    document = _document(bare_modes=("erase",), layered_modes=("tombstone", "erase"))
    assert report.pair_table(document, spec, BARE, LAYERED)[2].endswith("| FAIL | PASS |")

    with pytest.raises(ValueError, match="no forget mode in common"):
        report.pair_table(
            _document(bare_modes=("erase",), layered_modes=("tombstone",)),
            spec,
            BARE,
            LAYERED,
        )
    with pytest.raises(ValueError, match="cascade"):
        report.pair_table(_document(), spec, BARE, LAYERED, mode="cascade")


def test_a_system_that_is_not_in_the_document_is_named(spec: report.SpecText) -> None:
    """The likeliest mistake: a run filtered to one system, rendered as a pair."""
    with pytest.raises(ValueError, match="'nobody'"):
        report.pair_table(_document(), spec, "nobody", LAYERED)


# ---------------------------------------------------------------------- the gate


def test_a_readme_that_renders_the_run_agrees(tmp_path: Path, spec: report.SpecText) -> None:
    """The control. Without it every test below passes for the wrong reason."""
    document = _document()
    readme = _readme(tmp_path, report.pair_table(document, spec, BARE, LAYERED))
    assert report.readme_pair_drift(document, spec, readme) is None


def test_a_cell_the_run_does_not_produce_is_reported(
    tmp_path: Path, spec: report.SpecText
) -> None:
    """The drift that matters: a FAIL quietly written up as a PASS."""
    document = _document()
    lines = report.pair_table(document, spec, BARE, LAYERED)
    flattered = [line.replace("| FAIL | PASS |", "| PASS | PASS |") for line in lines]
    assert flattered != lines, "the injection changed nothing"

    drift = report.readme_pair_drift(document, spec, _readme(tmp_path, flattered))
    assert drift is not None
    assert "P1.1" in drift and "FAIL" in drift

    # Restored: the generated table, green. A detector that reported everything would be
    # as useless as one that reported nothing.
    assert report.readme_pair_drift(document, spec, _readme(tmp_path, lines)) is None


def test_the_two_systems_are_read_off_the_table(
    tmp_path: Path, spec: report.SpecText
) -> None:
    """Which pair the table is about is the table's business, not ``amr``'s.

    Nothing under ``src/amr`` knows the name of an optional adapter, and it should not
    have to: the committed table declares what it compares and the run supplies the
    outcomes. The cost is that a header naming a system nobody measured has to be an
    ordinary report rather than a traceback out of the gate.
    """
    document = _document()
    lines = report.pair_table(document, spec, BARE, LAYERED)
    renamed = [lines[0].replace(BARE, "somebody-else"), *lines[1:]]

    drift = report.readme_pair_drift(document, spec, _readme(tmp_path, renamed))
    assert drift is not None
    assert "somebody-else" in drift
    assert "no runs in this results document" in drift


def test_a_table_with_the_wrong_number_of_columns_is_reported(
    tmp_path: Path, spec: report.SpecText
) -> None:
    """Four columns, because a third system in the header is a different table."""
    document = _document()
    lines = report.pair_table(document, spec, BARE, LAYERED)
    widened = [lines[0] + " and-a-third |", *lines[1:]]
    drift = report.readme_pair_drift(document, spec, _readme(tmp_path, widened))
    assert drift is not None and "four columns" in drift


def test_a_missing_table_and_a_missing_run_are_different_reports(
    tmp_path: Path, spec: report.SpecText
) -> None:
    """Both directions, and the one case that is neither: a tree with nothing to compare.

    A checkout without the optional dependency has no extras run and, if it also carries
    no table, nothing to be wrong about — so the gate passes. It must not pass when the
    README makes a claim there is no run to support, which is the shape this would take
    after somebody deleted a results directory.
    """
    document = _document()
    bare_page = _readme(tmp_path / "bare", ["no table here"])
    with_table = _readme(
        tmp_path / "full", report.pair_table(document, spec, BARE, LAYERED)
    )

    assert report.readme_pair_drift(None, spec, bare_page) is None
    assert report.readme_pair_drift(document, spec, bare_page) is not None

    unsupported = report.readme_pair_drift(None, spec, with_table)
    assert unsupported is not None
    assert "make extras" in unsupported, "the report says how to produce the run"

    assert report.readme_pair_drift(document, spec, tmp_path / "absent.md") is not None


# -------------------------------------------------------------- against the real tree


def test_this_repository_renders_its_own_comparison(spec: report.SpecText) -> None:
    """The gate, over the committed tree, from inside the suite.

    ``make release-check`` runs ``amr drift``, which makes this same comparison. Here too,
    because a reader of the README is not running the gate, and a test that fails in a
    pull request is read sooner than one that fails at a tag.
    """
    root = repo_root()
    extras = results.latest_extras(root)
    document = None if extras is None else results.load(extras)
    assert report.readme_pair_drift(document, spec, root / "README.md") is None
