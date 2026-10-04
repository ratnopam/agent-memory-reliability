"""The write-through system: the whole suite, a real restart, and the paging hazard.

Three claims, each checked the way it would actually fail.

*It conforms.* Not asserted from this process, where the fixtures could be holding it up,
but by running the whole suite against it in a subprocess and reading the matrix —
``properties/test_external_adapter_example.py`` does the same thing for the external
example and says more about why. Zero FAIL, and the one divergence the reference has
under ``erase`` and no other.

*It is durable.* ``durable`` in SPEC.md 8 claims state survives a process restart, and
``reopen()`` inside one process cannot show that: the dict is still in memory either way.
So a subprocess writes a chain to a database file and exits, and this process opens the
file and compares the provenance walk byte for byte.

*It reloads completely.* The backend pages, so a reload that stopped at the first page
would rebuild a shorter graph than it stored — and a shorter graph is not visibly broken.
Every chain is intact, every record is self-consistent, and every effective confidence
below the break is *higher* than it should be. That is erasure inflation arriving through
the loader. The last test truncates a reload deliberately to prove the check can see it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from amr.paths import repo_root
from amr.protocol import ForgetMode, ReadOutcome, UnresolvedSourceError
from properties.support import canonical_chain
from systems.persistent import SQLITE_NAME, SQLiteBackend, sqlite_factory
from systems.persistent.backend import MemoryBackend
from systems.persistent.sqlite import PAGE
from systems.persistent.writethrough import RECORD_PREFIX, WriteThrough

#: More than ``sqlite.PAGE``, by enough that an off-by-one page boundary is not what is
#: being measured. A chain this long is also the thing a truncated reload shortens.
CHAIN = 30

WRITER = """\
import json, sys
from systems.persistent import sqlite_factory

memory = sqlite_factory(path=sys.argv[1])
previous = None
ids = []
for step in range({chain}):
    previous = memory.write(
        f"link {{step}}", 0.9 if step else 0.4, sources=[] if previous is None else [previous]
    )
    ids.append(previous)
print(json.dumps({{"ids": ids, "effective": memory.effective_confidence(ids[-1])}}))
"""


def _run(source: str, *arguments: str) -> dict:
    """A short program in a subprocess that is gone before this process looks."""
    root = repo_root()
    completed = subprocess.run(
        [sys.executable, "-c", source, *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(root / "src"), str(root)]),
        },
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


# ------------------------------------------------------------------- the whole suite


@pytest.fixture(scope="module")
def document(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """``SYSTEMS=sqlite amr reproduce``, out of process, as a reader would run it."""
    root = repo_root()
    out = tmp_path_factory.mktemp("sqlite-run") / "out"
    completed = subprocess.run(
        [sys.executable, "-m", "amr", "reproduce", "--out", str(out), "--quiet"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(root / "src"), str(root)]),
            "SYSTEMS": SQLITE_NAME,
            # Keeps the inner run from collecting this file and starting a third. The
            # conftest at the root says what it does with this.
            "AMR_NESTED_RUN": "1",
        },
    )
    raw = out / "raw.json"
    assert raw.is_file(), completed.stdout + completed.stderr
    # Green, unlike the external example's run: reproduce exits red while anything is
    # FAIL, and a wrapper that only adds storage has nothing to fail.
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(raw.read_text(encoding="utf-8"))


@pytest.mark.extra("persistent-suite-has-no-failures")
def test_the_sqlite_system_passes_every_check_in_every_mode(document: dict) -> None:
    """A wrapper that changed any answer would show up here as a cell, not a stack trace."""
    assert [run["system"] for run in document["runs"]] == [SQLITE_NAME] * 3, document[
        "runs"
    ]
    outcomes = {
        (run["forget_mode"], check["check"]): check["outcome"]
        for run in document["runs"]
        for check in run["checks"]
    }
    failed = [cell for cell, outcome in outcomes.items() if outcome == "FAIL"]
    assert failed == [], failed
    diverged = sorted(cell for cell, outcome in outcomes.items() if outcome == "DIVERGENCE")
    assert diverged == [("erase", "P2.5")], diverged
    assert not document["missing_checks"], document["missing_checks"]
    assert [
        check["name"] for check in document["suite_checks"] if check["outcome"] == "FAIL"
    ] == []


@pytest.mark.extra("persistent-declares-durable")
def test_it_declares_durable_and_the_reference_still_declares_round_trip(
    document: dict,
) -> None:
    """The one field the wrapper changes, and the reference it did not change."""
    declaration = document["runs"][0]["capabilities"]
    assert declaration["durability"] == "durable"
    assert declaration["system"] == SQLITE_NAME
    assert sorted(declaration["supported_forget_modes"]) == [
        "cascade",
        "erase",
        "tombstone",
    ]
    from systems.reference import ReferenceSystem

    assert ReferenceSystem().capabilities().durability == "round-trip"


# --------------------------------------------------------------------- the restart


@pytest.mark.extra("persistent-survives-a-process-restart")
def test_a_chain_written_by_a_dead_process_walks_identically(tmp_path: Path) -> None:
    """The claim ``durable`` makes, checked across a process boundary."""
    database = tmp_path / "store.sqlite3"
    written = _run(WRITER.format(chain=CHAIN), str(database))
    assert len(written["ids"]) == CHAIN
    assert database.is_file(), "nothing was persisted"

    reopened = sqlite_factory(path=database)
    leaf = written["ids"][-1]

    chain = reopened.provenance(leaf)
    assert len(chain.nodes) == CHAIN, "the reload stopped short of the whole graph"
    assert reopened.effective_confidence(leaf) == written["effective"]
    assert reopened.get(leaf).outcome is ReadOutcome.OK
    assert sorted(reopened.list_scope()) == sorted(written["ids"])

    # The walk the dead process would have produced, byte for byte: the same rendering
    # P1.5 compares, over a restart P1.5 cannot perform.
    expected = _run(
        "import json, sys\n"
        "from properties.support import canonical_chain\n"
        "from systems.persistent import sqlite_factory\n"
        "memory = sqlite_factory(path=sys.argv[1])\n"
        "print(json.dumps(canonical_chain(memory.provenance(sys.argv[2]))))",
        str(database),
        leaf,
    )
    assert canonical_chain(chain) == expected


@pytest.mark.extra("persistent-reopen-changes-nothing")
def test_reopening_leaves_every_answer_where_it_was(tmp_path: Path) -> None:
    """Reopen is only useful if it is a no-op on everything observable.

    Checked as the whole stored state rather than one walk: the items on disk before and
    after have to be equal, and so does every read the suite's own P1.5 compares.
    """
    database = tmp_path / "store.sqlite3"
    memory = sqlite_factory(default_forget_mode=ForgetMode.ERASE, path=database)
    root = memory.write("root", 0.9)
    middle = memory.write("middle", 0.4, sources=[root])
    leaf = memory.write("leaf", 0.95, sources=[middle])
    memory.revise(root, 0.8, "sharpened")
    memory.grant("default", "reader")

    before = dict(SQLiteBackend(database).items())
    reopened = memory.reopen()
    after = dict(SQLiteBackend(database).items())

    assert after == before, "a reopen wrote something"
    assert reopened.to_dict() == memory.to_dict()
    assert canonical_chain(reopened.provenance(leaf)) == canonical_chain(
        memory.provenance(leaf)
    )
    assert reopened.effective_confidence(leaf) == memory.effective_confidence(leaf)
    assert reopened.revisions(root) == memory.revisions(root)
    assert reopened.grants("default") == frozenset({"reader"})
    assert reopened.capabilities().default_forget_mode is ForgetMode.ERASE


# ------------------------------------------------------------------ the item layout


@pytest.mark.extra("persistent-stores-one-item-per-record")
def test_each_record_is_its_own_item_and_a_forget_removes_it(tmp_path: Path) -> None:
    """One blob would make "the store holds records" a sentence about a string."""
    database = tmp_path / "store.sqlite3"
    memory = sqlite_factory(default_forget_mode=ForgetMode.ERASE, path=database)
    root = memory.write("root", 0.9)
    leaf = memory.write("leaf", 0.4, sources=[root])

    backend = SQLiteBackend(database)
    items = dict(backend.items())
    records = {key for key in items if key.startswith(RECORD_PREFIX)}
    assert records == {f"{RECORD_PREFIX}{root}", f"{RECORD_PREFIX}{leaf}"}
    assert items[f"{RECORD_PREFIX}{leaf}"]["sources"] == [root]
    assert sorted(key for key in items if not key.startswith(RECORD_PREFIX)) == [
        "meta/counter",
        "meta/envelope",
        "meta/forgotten",
        "meta/grants",
        "meta/scopes",
    ]

    memory.forget(root)
    items = dict(SQLiteBackend(database).items())
    assert f"{RECORD_PREFIX}{root}" not in items, "erase left the item behind"
    assert items["meta/forgotten"]["forgotten"] == [
        {"id": root, "mode": "erase", "scope": "default"}
    ]
    # The counter is the reason an id is never reused, and it outlives the record.
    assert items["meta/counter"]["counter"] == 2


@pytest.mark.extra("persistent-detached-load")
def test_loading_a_foreign_snapshot_does_not_touch_the_live_store(
    tmp_path: Path,
) -> None:
    """A snapshot from outside is something to validate, not something to adopt."""
    database = tmp_path / "store.sqlite3"
    memory = sqlite_factory(path=database)
    kept = memory.write("kept", 0.9)

    elsewhere = WriteThrough(MemoryBackend())
    foreign = elsewhere.write("somebody else's record", 0.5)

    before = dict(SQLiteBackend(database).items())
    loaded = memory.load(elsewhere.to_dict())
    after = dict(SQLiteBackend(database).items())

    assert sorted(loaded.list_scope()) == [foreign]
    assert sorted(memory.list_scope()) == [kept], "the live store changed"
    assert after == before, "loading a foreign snapshot wrote to the database"
    assert loaded.capabilities().durability == "round-trip", (
        "a detached copy declares where it actually lives"
    )


# ------------------------------------------------------- the paging fault injection


class _TruncatedBackend(SQLiteBackend):
    """A backend whose ``items`` answers the first page and stops.

    The bug being guarded against, written down: the single most likely way to use a paged
    store wrongly. Its first page is five metadata items and three records, because ``m``
    sorts before ``r`` — so it loses the *end* of the chain, where losing the start would
    have been rejected outright by the snapshot reader.
    """

    def items(self):
        first = []
        for entry in super().items():
            if len(first) >= PAGE:
                break
            first.append(entry)
        return iter(first)


def _written_chain(database: Path) -> list[str]:
    """``CHAIN`` records, each deriving from the last, in a database on disk."""
    memory = sqlite_factory(path=database)
    previous = None
    ids = []
    for step in range(CHAIN):
        previous = memory.write(
            f"link {step}",
            0.9 if step else 0.4,
            sources=[] if previous is None else [previous],
        )
        ids.append(previous)
    assert memory.effective_confidence(ids[-1]) == 0.4, "the floor is the root's 0.4"
    return ids


def _assert_the_whole_graph_came_back(backend: SQLiteBackend, ids: list[str]) -> None:
    """The completeness claim ``items`` makes, as one assertion, used twice below."""
    system = WriteThrough(backend, name=SQLITE_NAME)
    assert sorted(system.list_scope()) == sorted(ids), "not every record was reloaded"
    assert len(system.provenance(ids[-1]).nodes) == CHAIN, "the chain came back shorter"
    # The number a truncated chain inflates: with the 0.4 root missing, a leaf of 0.9
    # sources would read 0.9 and look perfectly well-founded.
    assert system.effective_confidence(ids[-1]) == 0.4


@pytest.mark.extra("persistent-reload-pages-through-everything")
def test_a_reload_pages_through_more_records_than_one_page(tmp_path: Path) -> None:
    """``CHAIN`` records against ``PAGE`` rows: a one-page loader cannot pass this."""
    database = tmp_path / "store.sqlite3"
    ids = _written_chain(database)
    assert CHAIN > PAGE, "the paging is not being exercised"
    _assert_the_whole_graph_came_back(SQLiteBackend(database), ids)


@pytest.mark.extra("persistent-truncated-reload-is-caught")
def test_a_reload_that_stops_at_the_first_page_is_caught(tmp_path: Path) -> None:
    """The fault injection that makes the test above load-bearing.

    Without this, "a reload pages through everything" would pass against a backend that
    returned one page, and the suite would be asserting that nothing is wrong by never
    looking. Either the snapshot reader refuses the prefix, or the prefix opens short —
    and short is what must not be silent.
    """
    database = tmp_path / "store.sqlite3"
    ids = _written_chain(database)

    with pytest.raises((AssertionError, UnresolvedSourceError)):
        _assert_the_whole_graph_came_back(_TruncatedBackend(database), ids)

    # Restored: the same check, the real backend, green. A fault injection that left the
    # tree red would be indistinguishable from a broken wrapper.
    _assert_the_whole_graph_came_back(SQLiteBackend(database), ids)
