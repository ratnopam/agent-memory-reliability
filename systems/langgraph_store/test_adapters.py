"""Both adapters, measured: the gap a document store leaves, and the same store with it filled.

Two columns over one store. ``langgraph-store`` is the store's own five operations with
nothing computed over them; ``langgraph-layered`` is that store underneath
``systems/persistent/writethrough.py``. The pair is the measurement, and these tests are
what makes it one rather than two anecdotes:

*The failing set is a set, not a count.* Twenty-five of the twenty-six numbered checks FAIL
for the store alone, and ``WHY_IT_FAILS`` below names each one and the operation it wanted.
Asserting the set means a store that quietly grew an answer — or quietly lost the one it
has — changes a test rather than a number in a report nobody diffs.

*A FAIL is "not provided", not "defective".* The store answers everything it was built to
answer: the three checks of storage that it does provide pass, the one isolation check a
namespace gives for free passes, and every other failure arrives as ``NotProvided`` naming
itself. A store that returned an empty walk or a default confidence instead would have
scored better while being far worse.

*The layer closes the whole gap.* The layered column passes every check in every declared
mode, with the reference's single ``erase`` divergence and nothing else.

*And it reloads completely.* The store pages, and its listing answers ten items by default.
A loader that calls it once rebuilds a shorter graph than it stored, which is not visibly
broken — so there is a reload over thirty records, and a deliberately one-page loader next
to it to prove the reload test can tell the difference.

This file lives beside the code it measures rather than in ``properties/``, and the reason
is mechanical: it needs the ``langgraph`` extra, a missing extra is a skip, and a skip in
``properties/`` is counted as a FAIL (src/amr/runner.py). Here it is a file ``make test``
never collects and ``make extras-test`` always names.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Iterator

import pytest

pytest.importorskip(
    "langgraph.store.base",
    reason='the langgraph extra is not installed: pip install -e ".[langgraph]"',
)

from langgraph.store.memory import InMemoryStore

from amr.extensions import Reopenable
from amr.paths import repo_root
from amr.protocol import ForgetMode, ReadOutcome, UnresolvedSourceError
from properties.support import canonical_chain
from systems.langgraph_store import (
    LAYERED_NAME,
    STORE_NAME,
    layered_factory,
    store_factory,
)
from systems.langgraph_store.layered import META_PREFIX, StoreBackend
from systems.langgraph_store.naming import (
    META,
    PAGE,
    RECORDS,
    every_item,
    every_namespace,
)
from systems.langgraph_store.store_alone import NOTES, NotProvided
from systems.persistent.backend import Item
from systems.persistent.writethrough import RECORD_PREFIX, WriteThrough

#: Long enough that no single page holds it, by a wide margin: more than ``naming.PAGE``,
#: and more than the ten items the store's own ``search`` answers when nobody asks for a
#: limit. The brief asks for at least twenty-five, and the number has to clear the larger
#: of the two page sizes to be measuring anything.
CHAIN = 30

#: The two causes that are not a missing computed operation. Both are things the store has
#: no opinion about rather than things it refuses: a write that does not resolve its
#: sources cannot reject an unresolvable one, and a system that does not declare itself
#: reopenable is not asked to reopen.
DECLARATION = "the Reopenable declaration"
RESOLUTION = "source resolution at write time"

#: Every check the store alone fails, what it needed, and why in one line. Written out
#: rather than derived from the run: a table generated from whatever the run produced would
#: agree with the run no matter what the run said, and the gap between a document store and
#: this specification is the thing a reader came here to read.
#:
#: Each value is ``(what it needed, why the store does not have it)``. Where the first
#: element is an operation name, the measured failure detail has to be that operation's
#: ``NotProvided`` message — asserted below, one check at a time.
WHY_IT_FAILS: dict[str, tuple[str, str]] = {
    "P1.1": (
        RESOLUTION,
        (
            "a write stores the source ids it is handed. With nothing resolving them, an id "
            "that cannot have been assigned yet is stored instead of rejected, so the cycle "
            "the check tries to close is accepted."
        ),
    ),
    "P1.2": (
        "provenance",
        (
            "the walk is a graph traversal over stored edges, and traversal is the first "
            "thing a document store does not do: it hands back the document it was given."
        ),
    ),
    "P1.3": (
        "provenance",
        (
            "a diamond needs the shared ancestor returned once, which is a traversal with a "
            "visited set. Same missing operation, and the de-duplication is downstream of it."
        ),
    ),
    "P1.4": (
        "forget",
        (
            "nothing is forgotten, so there is no post-forget walk to inspect. A delete would "
            "have removed the document and left the edges citing it dangling."
        ),
    ),
    "P1.5": (
        DECLARATION,
        (
            "a byte-identical walk after a reopen presupposes a walk and a reopen. The store "
            "is not a Reopenable: it has no snapshot of its own to round-trip."
        ),
    ),
    "P1.6": (
        RESOLUTION,
        (
            "the same missing resolution as P1.1, from the other direction: an id that will "
            "never resolve is stored as happily as one that would."
        ),
    ),
    "P1.7": (
        DECLARATION,
        (
            "refusing a cycle on load requires a load. There is no snapshot format here to "
            "refuse, which is not the same as accepting a bad one."
        ),
    ),
    "P2.1": (
        "effective_confidence",
        (
            "the weakest-link bound is computed over a chain. The store holds the declared "
            "value it was given and has no second number to offer."
        ),
    ),
    "P2.2": (
        "effective_confidence",
        (
            "a revision that moves a descendant needs both a revise and a bound, and this "
            "check reads the bound."
        ),
    ),
    "P2.3": (
        "effective_confidence",
        (
            "bounding a sink once rather than squaring it is arithmetic over a traversal, so "
            "it fails one layer below where the check looks."
        ),
    ),
    "P2.4": (
        "effective_confidence",
        (
            "even the trivial case fails. A root's effective confidence equals its declared "
            "one, and the store still cannot answer, because it answers no such question."
        ),
    ),
    "P2.5": (
        "effective_confidence",
        (
            "the erasure-inflation check reads the bound before and after a forget. Both "
            "halves are missing, and the bound is the one the check calls first."
        ),
    ),
    "P2.6": (
        "revise",
        (
            "a revision history is a log the store was never asked to keep. Overwriting the "
            "document with a new confidence would have lost the prior value silently."
        ),
    ),
    "P2.7": (
        "effective_confidence",
        (
            "raising an ancestor must leave a descendant's own declared ceiling in place, "
            "which is again a statement about a computed number."
        ),
    ),
    "P2.8": (
        "grant",
        (
            "the check reads one number from two scopes and compares them. There is no grant "
            "to make the second read legitimate, so it fails before the comparison."
        ),
    ),
    "P3.1": (
        "forget",
        (
            "`Forgotten` distinct from `NotFound` is a state a store that only deletes cannot "
            "represent: a deleted key and a key that never existed read the same."
        ),
    ),
    "P3.2": (
        "forget",
        "idempotence needs a first call that did something. Nothing here does.",
    ),
    "P3.3": (
        "forget",
        (
            "handling descendants per the declared mode is the whole of P3, and the mode is "
            "declared (tombstone) precisely so this column can be measured rather than "
            "skipped."
        ),
    ),
    "P3.4": (
        "forget",
        (
            "a re-write does get a new id — ids are the one thing allocated here — but the "
            "check asks it to inherit no descendants of the forgotten original."
        ),
    ),
    "P3.5": (
        "forget",
        (
            "a receipt is the record of what a forget did, and is the clearest case of a "
            "value that would have to be invented to pass."
        ),
    ),
    "P4.2": (
        "grant",
        (
            "grant, read, revoke, read: there is no grant table, so visibility is permanently "
            "the namespace boundary and never temporarily wider."
        ),
    ),
    "P4.3": (
        "grant",
        (
            "withholding content while keeping an ancestor id visible is a per-field "
            "visibility rule over a traversal. Neither exists."
        ),
    ),
    "P4.4": (
        "grant",
        (
            "applying a mode across a scope boundary needs the forget and the boundary "
            "crossing; the grant is the call the check makes first."
        ),
    ),
    "P4.5": (
        "grant",
        (
            "the interleaving is set up through a second scope, so the missing grant is what "
            "stops it before any concurrency is exercised."
        ),
    ),
    "P4.6": (
        "grant",
        (
            "a reader refused a revise is the check that most wants a FAIL to mean something: "
            "there is no reader to refuse, not a reader who was wrongly allowed through."
        ),
    ),
}

#: The one numbered check the store alone passes, and it is not an accident: a scope is a
#: namespace here, so "write in A, list in B" is answered by the store's own addressing.
PROVIDED = ("P4.1",)


# --------------------------------------------------------------------- the two columns


def _measure(system: str, out) -> dict:
    """``SYSTEMS=<system> amr reproduce``, out of process, as a reader would run it.

    Out of process for the reason ``properties/test_external_adapter_example.py`` gives:
    an adapter measured through this session's fixtures is measured by something that
    could be holding it up. The exit code is not asserted here — one of these two columns
    is supposed to be red, and which one is the measurement.
    """
    root = repo_root()
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
            "SYSTEMS": system,
            # The suite only collects properties/, so this file is never in the inner run.
            # Set anyway, because the flag means "a run is already in progress" and the
            # next file to rely on it should not have to discover that it was unset here.
            "AMR_NESTED_RUN": "1",
        },
    )
    raw = out / "raw.json"
    assert raw.is_file(), completed.stdout + completed.stderr
    document = json.loads(raw.read_text(encoding="utf-8"))
    assert document["runs"], completed.stdout + completed.stderr
    return document


def _cells(document: dict) -> dict[tuple[str, str], str]:
    return {
        (run["forget_mode"], check["check"]): check["outcome"]
        for run in document["runs"]
        for check in run["checks"]
    }


@pytest.fixture(scope="module")
def alone(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """The store on its own, one declared mode, twenty-six cells."""
    return _measure(STORE_NAME, tmp_path_factory.mktemp("store-alone") / "out")


@pytest.fixture(scope="module")
def layered(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """The same store with the layer, three declared modes, seventy-eight cells."""
    return _measure(LAYERED_NAME, tmp_path_factory.mktemp("layered") / "out")


# ------------------------------------------------------------------ the store alone


def test_the_store_alone_fails_exactly_the_checks_nobody_wrote_an_answer_for(
    alone: dict,
) -> None:
    """The failing set, asserted as a set.

    A count would move for the wrong reasons in both directions: a store that started
    inventing an answer would look like progress, and a check renamed would look like a
    regression. The set says which questions a document store does not answer.
    """
    assert [run["forget_mode"] for run in alone["runs"]] == ["tombstone"], (
        "the store declares one forget mode, so it is measured in one"
    )
    cells = _cells(alone)
    assert len(cells) == 26, "every numbered check is measured, including the ones that fail"

    failed = sorted(check for (_, check), outcome in cells.items() if outcome == "FAIL")
    passed = sorted(check for (_, check), outcome in cells.items() if outcome == "PASS")
    assert failed == sorted(WHY_IT_FAILS), (
        "the measured failing set is not the explained one. Add or remove the row in "
        "WHY_IT_FAILS; a failing check with no explanation is a number nobody can read."
    )
    assert passed == sorted(PROVIDED)
    # No cell went unmeasured and none diverged: a divergence is a different answer, and
    # this column has no answers to differ with.
    assert alone["missing_checks"] == [], alone["missing_checks"]
    assert [outcome for outcome in cells.values() if outcome == "DIVERGENCE"] == []


@pytest.mark.parametrize("check", sorted(WHY_IT_FAILS))
def test_every_failing_check_names_the_operation_it_wanted(check: str, alone: dict) -> None:
    """Each FAIL tied to its cause, one check at a time.

    The explanation in ``WHY_IT_FAILS`` is prose and prose cannot be checked. What can be
    is the *cause*: a check explained by a missing operation has to have failed inside
    that operation's refusal, and not somewhere else that happened to be red too.
    """
    cause, why = WHY_IT_FAILS[check]
    assert why.strip(), f"{check} has no explanation"
    detail = next(
        entry["detail"]
        for run in alone["runs"]
        for entry in run["checks"]
        if entry["check"] == check
    )
    if cause == DECLARATION:
        assert "Reopenable" in detail, detail
    elif cause == RESOLUTION:
        assert "DID NOT RAISE" in detail, detail
    else:
        assert f"{cause} is not provided by this store" in detail, detail


def test_a_fail_here_means_not_provided_and_the_store_proves_it() -> None:
    """The claim the failing column rests on, checked rather than asserted in a docstring.

    Two halves. Every refusal is a refusal — a named exception that says so, not a wrong
    answer — and everything the store *was* built to do, it does. A store that returned an
    empty provenance walk and a default confidence of 1.0 would have passed several of the
    checks above while being the exact failure this repository exists to catch.
    """
    system = store_factory()
    assert isinstance(NotProvided("x"), NotImplementedError)
    assert "not provided by this store" in str(NotProvided("provenance"))
    assert "does not provide" in NOTES[0], (
        "the declaration has to say it too: the notes travel with the run, and the matrix "
        "is read by somebody who never opens this file"
    )

    root = system.write("root", 0.9, scope="demo")
    leaf = system.write("leaf", 0.4, sources=[root], scope="demo")
    assert system.get(leaf, scope="demo").record.sources == frozenset({root})
    assert system.get(leaf, scope="demo").record.declared_confidence == 0.4
    assert sorted(system.list_scope(scope="demo")) == sorted([root, leaf])
    assert system.get("m999", scope="demo").outcome is ReadOutcome.NOT_FOUND

    for operation in (
        lambda: system.provenance(leaf, scope="demo"),
        lambda: system.effective_confidence(leaf, scope="demo"),
        lambda: system.descendants(root, scope="demo"),
        lambda: system.revise(root, 0.2, "because", scope="demo"),
        lambda: system.revisions(root, scope="demo"),
        lambda: system.forget(root, scope="demo"),
        lambda: system.grant("demo", "reader"),
        lambda: system.revoke("demo", "reader"),
        lambda: system.grants("demo"),
    ):
        with pytest.raises(NotProvided):
            operation()
    assert not isinstance(system, Reopenable), "it does not claim a reopen it cannot do"


def test_the_one_check_it_passes_is_the_one_the_addressing_answers() -> None:
    """P4.1, directly: a scope is a namespace, so isolation is the store's own boundary.

    Worth its own test because it is the only numbered row that is not about the layer.
    Addressing is a design decision inside the adapter — a scope could have been a field
    to filter on, and then this row would have failed too, for the reason every
    filter-based isolation fails: somebody forgets the filter.
    """
    store = InMemoryStore()
    system = store_factory(store=store)
    hidden = system.write("employee on leave", 0.9, scope="hr")

    # It is the namespace doing the hiding, not a filter: the record is addressable under
    # hr and there is nowhere else to address it from. Asserted before the reads below,
    # because a read is how a namespace comes to exist in the store's own listing.
    assert every_namespace(store, RECORDS) == [(*RECORDS, "hr")]

    assert system.get(hidden, scope="ops").outcome is ReadOutcome.NOT_FOUND
    assert system.list_scope(scope="ops") == frozenset()
    assert system.get(hidden, scope="hr").outcome is ReadOutcome.OK


def test_it_declares_every_field_and_the_listing_pages() -> None:
    """The declaration, and the one computed thing in the file: its own listing.

    ``list_scope`` has to page. The store answers ten items when nobody passes a limit,
    and a scope with more than ten records in it would otherwise report a smaller scope
    than it holds — which is the paging hazard in its smallest form.
    """
    declared = store_factory().capabilities()
    assert declared.system == STORE_NAME
    assert declared.supported_forget_modes == frozenset({ForgetMode.TOMBSTONE})
    assert declared.durability == "in-memory"
    assert declared.scopes == "native"
    assert declared.revision == "none"
    assert declared.revision_raise_supported is False
    assert declared.cross_scope_derivation == "rejected"
    assert declared.empty_chain_convention == 1.0

    system = store_factory()
    written = {system.write(f"item {step}", 0.9) for step in range(CHAIN)}
    assert len(written) == CHAIN, "ids are unique"
    assert system.list_scope() == frozenset(written), "the listing stopped at a page"


# --------------------------------------------------------------------- with the layer


def test_the_layered_system_passes_every_check_in_every_declared_mode(
    layered: dict,
) -> None:
    """Seventy-eight cells, no FAIL, and the reference's one divergence.

    This is the half of the pair that makes the other half readable. The same store, the
    same five operations underneath, and the whole specification answered — so the failing
    column measures a missing layer and not a deficient store.
    """
    assert [run["forget_mode"] for run in layered["runs"]] == [
        "tombstone",
        "cascade",
        "erase",
    ], [run["forget_mode"] for run in layered["runs"]]
    assert [run["system"] for run in layered["runs"]] == [LAYERED_NAME] * 3

    cells = _cells(layered)
    assert len(cells) == 78
    failed = sorted(cell for cell, outcome in cells.items() if outcome == "FAIL")
    assert failed == [], failed
    diverged = sorted(cell for cell, outcome in cells.items() if outcome == "DIVERGENCE")
    assert diverged == [("erase", "P2.5")], diverged
    assert layered["missing_checks"] == [], layered["missing_checks"]
    assert [
        check["name"] for check in layered["suite_checks"] if check["outcome"] == "FAIL"
    ] == []


def test_the_layer_changes_the_storage_and_nothing_else(layered: dict) -> None:
    """What the declaration says about a store that is in memory and reopenable."""
    declared = layered["runs"][0]["capabilities"]
    assert declared["system"] == LAYERED_NAME
    assert declared["durability"] == "round-trip", (
        "an in-memory store survives a reopen and not a process, which is what "
        "round-trip means. A store backed by a database would declare durable here, "
        "which is why the backend takes the value rather than hard-coding one."
    )
    assert sorted(declared["supported_forget_modes"]) == ["cascade", "erase", "tombstone"]
    assert declared["revision"] == "logged"
    # The two columns agree here, and the agreement is the point: both scope natively,
    # because in both of them a scope is a namespace in the same store.
    assert declared["scopes"] == "native"
    assert store_factory().capabilities().scopes == declared["scopes"]


def test_a_scope_is_a_namespace_and_the_bookkeeping_is_somewhere_else() -> None:
    """The mapping, read off the store rather than off the module docstring claiming it.

    A reader who opens this store should see one namespace per scope holding records and
    nothing else. If the wrapper's counter and grant table lived in a scope's namespace,
    every listing of that scope would have to know which keys to skip.
    """
    store = InMemoryStore()
    system = layered_factory(store=store)
    mine = system.write("a runbook entry", 0.9, scope="ops")
    theirs = system.write("someone else's note", 0.4, scope="hr")
    system.grant("ops", "hr")

    assert sorted(every_namespace(store, RECORDS)) == [
        (*RECORDS, "hr"),
        (*RECORDS, "ops"),
    ]
    assert [key for key, _ in every_item(store, (*RECORDS, "ops"))] == [mine]
    assert [key for key, _ in every_item(store, (*RECORDS, "hr"))] == [theirs]
    assert sorted(key for key, _ in every_item(store, META)) == [
        "counter",
        "envelope",
        "forgotten",
        "grants",
        "scopes",
    ]
    # The grant is bookkeeping and lives with the bookkeeping, not in either scope.
    assert store.get(META, "grants").value["grants"] == [["ops", "hr"]]
    assert store.get(META, "counter").value["counter"] == 2


class _RecordsEveryPut(InMemoryStore):
    """A store that remembers how each ``put`` asked to be indexed.

    The ``index=False`` claim is the one in this directory that cannot be checked by
    looking at the result: an indexed put and an unindexed one store the same value, and
    the difference is an embedding computed over a memory's content. So it is checked at
    the call.
    """

    def __init__(self) -> None:
        super().__init__()
        self.indexing: list[object] = []

    def put(self, namespace, key, value, index=None, **rest) -> None:  # type: ignore[override]
        self.indexing.append(index)
        super().put(namespace, key, value, index=index, **rest)


def test_every_value_is_readable_json_and_nothing_is_indexed() -> None:
    """Two claims about what is in the store, and one about what is not.

    Readable, because a store holding one opaque blob per system is a store nobody can
    audit — and auditing a memory's provenance by looking at it is half of what this
    specification is for. Unindexed, because an embedding model in the measured path is a
    model in the measured path, whatever it is embedding.
    """
    store = _RecordsEveryPut()
    system = layered_factory(store=store)
    root = system.write("incident report", 0.9, scope="ops")
    leaf = system.write("agent summary", 0.95, sources=[root], scope="ops")
    system.revise(root, 0.2, "retracted", scope="ops")
    system.forget(leaf, scope="ops", mode=ForgetMode.TOMBSTONE)

    assert store.indexing, "nothing was stored"
    assert set(store.indexing) == {False}, (
        f"a put asked for an index: {sorted(set(map(str, store.indexing)))}"
    )

    value = store.get((*RECORDS, "ops"), root).value
    assert value["content"] == "incident report"
    assert value["declared_confidence"] == 0.2
    assert value["id"] == root
    assert json.loads(json.dumps(value)) == dict(value), "the value is not plain JSON"
    # Readable means readable without this repository: every key a reader would need is
    # spelled out, and the revision log travels inside the record it belongs to.
    assert {"id", "content", "declared_confidence", "sources", "scope"} <= set(value)


# ----------------------------------------------------------- the reload, and the fault


def _written_chain(store: object) -> list[str]:
    """``CHAIN`` records, each deriving from the last, with the weak link at the root."""
    system = layered_factory(store=store)
    previous = None
    ids = []
    for step in range(CHAIN):
        previous = system.write(
            f"link {step}",
            0.9 if step else 0.4,
            sources=[] if previous is None else [previous],
        )
        ids.append(previous)
    assert system.effective_confidence(ids[-1]) == 0.4, "the floor is the root's 0.4"
    return ids


def _assert_the_whole_graph_came_back(backend: StoreBackend, ids: list[str]) -> str:
    """The completeness claim ``items`` makes, as one assertion, used three times below."""
    system = WriteThrough(backend, name=LAYERED_NAME)
    assert sorted(system.list_scope()) == sorted(ids), "not every record was reloaded"
    assert len(system.provenance(ids[-1]).nodes) == CHAIN, "the chain came back shorter"
    # The number a truncated chain inflates: with the 0.4 root missing, a leaf whose
    # sources all declared 0.9 reads 0.9 and looks perfectly well-founded.
    assert system.effective_confidence(ids[-1]) == 0.4
    return canonical_chain(system.provenance(ids[-1]))


def test_a_reload_from_the_store_walks_the_whole_graph_identically() -> None:
    """Thirty records back out of a paged store, and the same walk they went in as.

    Compared as the rendered chain rather than as a count, because a reload can be the
    right length and the wrong shape: an edge dropped on the way out leaves thirty records
    and a different graph. This is the rendering P1.5 compares, over a reopen P1.5 does not
    reach — a cold open from the store with none of the writer's state in memory.
    """
    store = InMemoryStore()
    ids = _written_chain(store)
    assert CHAIN > PAGE, "the paging is not being exercised"

    live = layered_factory(store=store)
    walked = live.provenance(ids[-1])
    expected = canonical_chain(walked)
    assert len(walked.nodes) == CHAIN, "the writer's own walk is short"

    reloaded = _assert_the_whole_graph_came_back(StoreBackend(store), ids)
    assert reloaded == expected, "the reload rebuilt a different graph"

    # And the metadata came back with it: an id is never reused, which is a promise about
    # the counter surviving the reload and not about the records.
    fresh = WriteThrough(StoreBackend(store), name=LAYERED_NAME)
    assert fresh.write("after the reload", 0.9) not in ids


class _OnePageBackend(StoreBackend):
    """The bug, written down: one ``search`` per namespace and no limit.

    Not a contrived failure. It is the shortest correct-looking way to list a namespace,
    it is what the store's own documentation shows, and the store answers ten items and
    says nothing about the eleventh. ``naming.every_item`` exists to not be this.
    """

    def items(self) -> Iterator[tuple[str, Item]]:
        for namespace in [META, *every_namespace(self._store, RECORDS)]:
            for item in self._store.search(namespace):
                yield self._flat(namespace, item.key), dict(item.value)


def test_a_reload_that_takes_the_first_page_is_caught() -> None:
    """The fault injection that makes the reload test above load-bearing.

    Without it, "the reload walks the whole graph" would pass against a loader that
    returned one page, and the suite would be asserting that nothing is wrong by never
    looking. Two outcomes are accepted because which one arrives depends on where the
    page boundary falls: a prefix of the chain opens short, and any other subset cites a
    source that did not come back and the snapshot reader refuses it outright. Short is
    the dangerous one, and short is what the record count catches.
    """
    store = InMemoryStore()
    ids = _written_chain(store)

    truncated = dict(_OnePageBackend(store).items())
    records = [key for key in truncated if key.startswith(RECORD_PREFIX)]
    assert len(records) < CHAIN, (
        "the injected loader returned everything, so it is not injecting anything. The "
        "store's default page size grew past this test's chain length."
    )
    assert len([key for key in truncated if key.startswith(META_PREFIX)]) == 5

    with pytest.raises((AssertionError, UnresolvedSourceError)):
        _assert_the_whole_graph_came_back(_OnePageBackend(store), ids)

    # Restored: the same assertion, the real backend, green. A fault injection that left
    # the tree red would be indistinguishable from a broken adapter.
    _assert_the_whole_graph_came_back(StoreBackend(store), ids)
