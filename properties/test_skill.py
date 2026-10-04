"""The published skill is instructions nobody reads before they are followed.

``.claude/skills/conformance-run/SKILL.md`` tells an agent how to measure a system in this
repository. A stale command in a document is a typo somebody notices; a stale command in a
skill is an agent confidently running something that does not exist, or — worse — writing
where it was told not to. So every command the skill names is checked against the command
line and the Makefile that have to answer for it, and the sentences it must not contain are
checked too.

Nothing here runs the skill: an agent is a model and no measurement in this repository
involves one. This checks that what the skill says is true of the tree it ships in.
"""

from __future__ import annotations

import argparse
import re

import pytest

from amr.__main__ import build_parser
from amr.paths import repo_root

SKILL = repo_root() / ".claude" / "skills" / "conformance-run" / "SKILL.md"

#: ``amr demo``, ``python3 -m amr systems``: the word after the command, wherever it is
#: spelled. A subcommand that was renamed shows up here as a name the parser rejects.
SUBCOMMAND = re.compile(r"(?:^|\s|`)(?:python3? -m )?amr ([a-z-]+)")

MAKE_TARGET = re.compile(r"`make ([a-z-]+)")

#: The former name, assembled rather than written, so that this gate is not itself the
#: match: the tree is grepped for that name and a test containing it whole would fail the
#: grep it exists to support.
FORMER_NAME = "".join(("mem", "ledger"))

#: Claims the skill must not make — a score the suite does not compute, a schedule nothing
#: in this repository keeps — and the model clients that must not appear in a measured path.
FORBIDDEN = (
    FORMER_NAME,
    "conformance score",
    "overall score",
    "score of",
    "% of checks",
    "out of 26",
    "roadmap",
    "next quarter",
    "anthropic",
    "openai",
    "langchain",
)

#: Paths the skill is allowed to write. Anything else it tells somebody to write into is a
#: guardrail that was documented and then contradicted two sections later.
WRITABLE = (".amr-runs",)


def _frontmatter(text: str) -> dict[str, str]:
    """The YAML frontmatter, read without a YAML parser.

    The package has no runtime dependencies and this is not the place to acquire one. The
    frontmatter of a skill is flat ``key: value`` lines, so reading it is splitting on the
    first colon; anything else in there is a shape this function refuses rather than
    silently half-reads.
    """
    assert text.startswith("---\n"), "a skill begins with its frontmatter"
    _, _, rest = text.partition("---\n")
    block, marker, _ = rest.partition("\n---\n")
    assert marker, "the frontmatter is not closed"
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip():
            continue
        key, colon, value = line.partition(":")
        assert colon, f"not a key-value line: {line!r}"
        assert key == key.strip(), f"indented frontmatter is a nested shape: {line!r}"
        fields[key.strip()] = value.strip()
    return fields


@pytest.fixture(scope="module")
def text() -> str:
    assert SKILL.is_file(), f"{SKILL} is tracked and has to be here"
    return SKILL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(text: str) -> dict[str, str]:
    return _frontmatter(text)


def test_the_frontmatter_parses_and_names_its_directory(
    frontmatter: dict[str, str],
) -> None:
    """The name is the handle it is invoked by, and it is the directory's name."""
    assert frontmatter["name"] == SKILL.parent.name == "conformance-run"
    assert set(frontmatter) == {"name", "description"}, sorted(frontmatter)


def test_the_description_says_what_it_does_and_when_to_use_it(
    frontmatter: dict[str, str],
) -> None:
    """A description is how the skill gets chosen, so it carries both halves."""
    description = frontmatter["description"]
    assert 40 < len(description) < 600, len(description)
    assert "conformance" in description.lower()
    assert "use when" in description.lower(), "the trigger half is missing"


def test_every_subcommand_it_names_exists(text: str) -> None:
    """``amr`` grew from eight subcommands to nine once; it can grow again."""
    parser = build_parser()
    choices: set[str] = set()
    # argparse exposes no public accessor for its subcommands, and asking the parser is
    # still better than keeping a second list of nine names in this file.
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            choices |= set(action.choices)
    assert choices, "the parser exposed no subcommands, so this test proves nothing"

    named = set(SUBCOMMAND.findall(text))
    assert named, "the skill names no command at all"
    assert named <= choices, sorted(named - choices)


def test_every_make_target_it_names_exists(text: str) -> None:
    makefile = (repo_root() / "Makefile").read_text(encoding="utf-8")
    declared = set(re.findall(r"^([a-z-]+):", makefile, flags=re.MULTILINE))
    named = set(MAKE_TARGET.findall(text))
    assert named, "the skill names no make target at all"
    assert named <= declared, sorted(named - declared)


def test_every_link_resolves(text: str) -> None:
    """The same check the links gate makes, from inside the suite.

    Duplicated on purpose: the gate runs before a tag and this runs on every commit, and
    a skill that points at a renamed file is the one broken link nobody sees happen.
    """
    targets = [
        raw.split()[0]
        for raw in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
        if not raw.startswith(("http://", "https://", "mailto:", "#"))
    ]
    assert targets, "the skill links to nothing"
    missing = [
        target
        for target in targets
        if not (SKILL.parent / target.partition("#")[0]).resolve().exists()
    ]
    assert missing == [], missing


@pytest.mark.parametrize(
    "forbidden",
    # The first case carries its own id. A parametrised id is the runtime value, and it
    # travels into every results document the suite writes — where the gate that greps the
    # tree for the former name finds it and cannot tell a test parameter from a relapse.
    # This file is already careful to assemble the string rather than spell it; the id has
    # to be too.
    [pytest.param(FORMER_NAME, id="the-former-name"), *FORBIDDEN[1:]],
)
def test_it_does_not_say_what_it_must_not_say(
    text: str, forbidden: str, request: pytest.FixtureRequest
) -> None:
    """A score the suite does not compute is the easiest thing for a skill to invent."""
    assert forbidden not in text.lower(), forbidden
    # And this case's own name is publishable. The suite records one entry per test into
    # `raw.json`, a results document is committed, and the gate greps what is committed —
    # so a test id is as much a tracked string as a sentence of prose is.
    assert FORMER_NAME not in request.node.name, (
        "this test's id would carry the former name into every results document"
    )


def test_it_sends_every_run_to_the_scratch_directory(text: str) -> None:
    """The guardrail, read off the commands rather than off the prose promising it."""
    out_flags = re.findall(r"--out ([^\s`]+)", text)
    assert out_flags, "the skill runs the suite without saying where the output goes"
    for target in out_flags:
        assert target.startswith(WRITABLE), target
    assert "make results" not in text.replace("`make results`", ""), (
        "the producer target is named outside the sentence that says not to run it"
    )
    assert ".amr-runs" in (repo_root() / ".gitignore").read_text(encoding="utf-8"), (
        "the scratch directory the skill writes to is not git-ignored"
    )


def test_it_states_the_three_outcomes_and_no_score(text: str) -> None:
    """PASS, FAIL, DIVERGENCE, and the two things a reader gets wrong without being told."""
    for state in ("PASS", "FAIL", "DIVERGENCE"):
        assert state in text, state
    lowered = text.lower()
    assert "no score" in lowered, "the absence of a score is the thing to say out loud"
    assert "skipped check is a fail" in lowered, "a skip is a FAIL and must be stated"
    assert "no model is involved" in lowered, "the measurement has no model in it"
    assert "adding-a-system.md" in text, "somebody's own store needs the guide, not a scaffold"
