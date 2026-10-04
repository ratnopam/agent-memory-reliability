"""What counts as "the results" when something else is also under ``results/``.

``amr drift`` asks whether the README still renders the committed matrix, and it finds
that matrix by taking the newest ``results/<date>/raw.json``. An extras run writes a
matrix too, under ``results/extras/<date>/``, and ``extras`` sorts after every date — so
the naive glob would make somebody's side run the thing the gate compares the README with.
A gate that can be redirected by a directory name is not a gate, which is why the decoy
below is a test and not a comment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amr.results import extras_dir, latest_contamination, latest_extras, latest_raw

DAYS = ("2026-01-01", "2026-02-02")


def _write(directory: Path, name: str, document: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    return path


def test_the_newest_dated_directory_wins(tmp_path: Path) -> None:
    """The control: dates sort by name, so the newest name is the newest run."""
    for day in DAYS:
        _write(tmp_path / "results" / day, "raw.json", {"day": day})
    assert latest_raw(tmp_path).parent.name == DAYS[-1]


def test_an_extras_run_does_not_become_the_published_matrix(tmp_path: Path) -> None:
    """The decoy. ``results/extras/`` holds a real raw.json and must still be ignored."""
    published = _write(tmp_path / "results" / DAYS[0], "raw.json", {"published": True})
    _write(extras_dir(tmp_path, DAYS[-1]), "raw.json", {"published": False})
    # Written where an extras run writes it, and also one level up, because a glob of
    # ``*/raw.json`` would catch either shape if it only sorted.
    _write(tmp_path / "results" / "extras", "raw.json", {"published": False})

    assert latest_raw(tmp_path) == published
    assert json.loads(latest_raw(tmp_path).read_text(encoding="utf-8"))["published"]


def test_a_working_directory_under_results_is_ignored_too(tmp_path: Path) -> None:
    """Dated and nothing else: a scratch directory is not a release."""
    published = _write(tmp_path / "results" / DAYS[0], "raw.json", {"published": True})
    for decoy in ("latest", "tmp-run", f"{DAYS[-1]}-retry", "zzz"):
        _write(tmp_path / "results" / decoy, "raw.json", {"published": False})
    assert latest_raw(tmp_path) == published


def test_the_contamination_record_is_filtered_the_same_way(tmp_path: Path) -> None:
    """Two files, two commands, one rule about which directories are published."""
    published = _write(
        tmp_path / "results" / DAYS[0], "contamination.json", {"published": True}
    )
    _write(extras_dir(tmp_path, DAYS[-1]), "contamination.json", {"published": False})
    assert latest_contamination(tmp_path) == published


def test_an_empty_results_tree_says_so(tmp_path: Path) -> None:
    """Filtering everything out has to read as "nothing published", not as a crash."""
    _write(extras_dir(tmp_path, DAYS[-1]), "raw.json", {"published": False})
    with pytest.raises(FileNotFoundError, match="results"):
        latest_raw(tmp_path)
    with pytest.raises(FileNotFoundError, match="contamination"):
        latest_contamination(tmp_path)


def test_extras_runs_are_dated_inside_their_own_directory(tmp_path: Path) -> None:
    """``results/extras/<date>/``: the date is still there, one level further down."""
    directory = extras_dir(tmp_path, DAYS[0])
    assert directory == tmp_path / "results" / "extras" / DAYS[0]
    assert extras_dir(tmp_path).parent == tmp_path / "results" / "extras"
    assert extras_dir(tmp_path).name.count("-") == 2, "the default is today's date"


def test_the_newest_extras_run_is_found_and_an_absent_one_is_not_an_error(
    tmp_path: Path,
) -> None:
    """``None`` and not an exception, and the same date filter one level down.

    An extras run needs an optional dependency, so a checkout can legitimately have none
    and still be a working checkout — unlike a tree with no published matrix, which
    ``latest_raw`` refuses. The filter is still a filter: a scratch directory beside the
    dated ones must not become the thing ``amr drift`` compares the README with.
    """
    assert latest_extras(tmp_path) is None, "nothing published is not a crash"

    newest = _write(extras_dir(tmp_path, DAYS[-1]), "raw.json", {"wanted": True})
    _write(extras_dir(tmp_path, DAYS[0]), "raw.json", {"wanted": False})
    for decoy in ("latest", "tmp-run", f"{DAYS[-1]}-retry"):
        _write(tmp_path / "results" / "extras" / decoy, "raw.json", {"wanted": False})
    assert latest_extras(tmp_path) == newest

    # And it is not confused by the published matrix: the two live in two trees, which is
    # the whole reason extras_dir exists.
    _write(tmp_path / "results" / "2026-12-31", "raw.json", {"wanted": False})
    assert latest_extras(tmp_path) == newest
