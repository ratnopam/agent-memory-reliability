"""The results document: schema 0.1, and the writer that produces it.

Two rules govern this file. Everything written is either a fact about the code under
test or a fact about the environment it ran in — never a duration, a path outside the
repository, or an iteration order that depends on a hash seed. And exactly one field
varies between two runs of the same tree: ``generated_at``. ``make determinism`` strips
that field and requires the remaining bytes to be identical, so anything nondeterministic
added here breaks the build, which is the intended pressure.

The schema is documented in results/README.md.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from amr.paths import SPEC_RELATIVE
from amr.protocol import Capabilities
from amr.runner import SuiteResult, missing_checks

SCHEMA_VERSION = "0.1"

#: Stripped before the byte comparison in ``make determinism``.
VOLATILE_FIELDS = ("generated_at",)

UNKNOWN = "unknown"

#: A published results directory is named by UTC date and nothing else. Anything else
#: under ``results/`` is somebody's side run and is not the matrix a reader is shown.
DATED = re.compile(r"\d{4}-\d{2}-\d{2}")


def git_sha(root: Path) -> str:
    """The commit the suite ran against, with a ``-dirty`` suffix if it was edited."""
    sha = _git(root, "rev-parse", "HEAD")
    if sha is None:
        return UNKNOWN
    status = _git(root, "status", "--porcelain")
    return f"{sha}-dirty" if status else sha


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):  # pragma: no cover - git absent
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def environment(root: Path) -> dict[str, str]:
    """Enough to tell two disagreeing runs apart, and nothing that varies within one."""
    version = sys.version_info
    return {
        "git_sha": git_sha(root),
        "platform": platform.system().lower(),
        "python_implementation": platform.python_implementation(),
        "python_version": f"{version.major}.{version.minor}.{version.micro}",
        "pytest_version": _pytest_version(),
    }


def _pytest_version() -> str:
    try:
        import pytest
    except ImportError:  # pragma: no cover - pytest is required to run the suite
        return UNKNOWN
    return str(getattr(pytest, "__version__", UNKNOWN))


def capabilities_as_dict(capabilities: Capabilities) -> dict[str, object]:
    """The full declaration, SPEC.md 8, with sets sorted so bytes are stable."""
    return {
        "system": capabilities.system,
        "version": capabilities.version,
        "supported_forget_modes": sorted(
            mode.value for mode in capabilities.supported_forget_modes
        ),
        "default_forget_mode": capabilities.default_forget_mode.value,
        "empty_chain_convention": capabilities.empty_chain_convention,
        "revision": capabilities.revision,
        "revision_raise_supported": capabilities.revision_raise_supported,
        "scopes": capabilities.scopes,
        "cross_scope_derivation": capabilities.cross_scope_derivation,
        "durability": capabilities.durability,
        "notes": list(capabilities.notes),
    }


def build_document(result: SuiteResult, root: Path, timestamp: str | None = None) -> dict:
    """The whole results document, ready to serialise."""
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": timestamp or utc_now(),
        "environment": environment(root),
        "spec": {
            "path": SPEC_RELATIVE.as_posix(),
            "checks": list(result.check_ids),
        },
        "totals": result.counts(),
        "runs": [
            {
                "system": run.system,
                "system_version": run.version,
                "forget_mode": run.mode.value,
                "capabilities": capabilities_as_dict(run.capabilities),
                "checks": [check.as_dict() for check in run.checks],
                "supplementary": [extra.as_dict() for extra in run.extras],
            }
            for run in result.runs
        ],
        "suite_checks": [check.as_dict() for check in result.suite_checks],
        "missing_checks": [
            {
                "system": gap.system,
                "forget_mode": gap.mode,
                "check": gap.check,
                "reason": gap.reason,
            }
            for gap in missing_checks(result)
        ],
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def serialise(document: dict) -> str:
    """Canonical JSON: sorted keys, fixed separators, trailing newline."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def strip_volatile(document: dict) -> dict:
    """The document as ``make determinism`` compares it."""
    return {key: value for key, value in document.items() if key not in VOLATILE_FIELDS}


def results_dir(root: Path, day: str | None = None) -> Path:
    return root / "results" / (day or datetime.now(timezone.utc).strftime("%Y-%m-%d"))


def extras_dir(root: Path, day: str | None = None) -> Path:
    """Where a run that includes the extras goes: ``results/extras/<date>/``.

    Under its own directory rather than into the dated ones, because the published
    matrix is the default run and a reader comparing two trees must not have to work out
    which systems were in which file. ``latest_raw`` ignores this path on purpose.
    """
    return root / "results" / "extras" / (
        day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )


def latest_raw(root: Path) -> Path:
    """The newest committed ``results/<date>/raw.json``.

    Directories are named by UTC date, so sorting them is sorting them by time — but only
    the dated ones. ``results/`` also holds runs that are not the published matrix, and a
    directory whose name sorts after a date (``results/extras/``) would otherwise become
    "the newest results" and silently decide what ``amr drift`` compares the README with.
    A drift gate that can be redirected by a directory name is not a gate.
    """
    candidates = sorted(
        path
        for path in (root / "results").glob("*/raw.json")
        if DATED.fullmatch(path.parent.name)
    )
    if not candidates:
        raise FileNotFoundError(f"no results/<date>/raw.json under {root / 'results'}")
    return candidates[-1]


def latest_extras(root: Path) -> Path | None:
    """The newest ``results/extras/<date>/raw.json``, or ``None`` if there is none.

    ``None`` rather than an exception, because an extras run is optional in a way the
    published matrix is not: a checkout where nobody installed an optional dependency has
    nothing to compare and is not thereby broken. ``latest_raw`` raises for the opposite
    reason — a tree with no published matrix cannot answer the question the README asks.
    """
    candidates = sorted(
        path
        for path in (root / "results" / "extras").glob("*/raw.json")
        if DATED.fullmatch(path.parent.name)
    )
    return candidates[-1] if candidates else None


def latest_contamination(root: Path) -> Path:
    """The newest committed ``results/<date>/contamination.json``.

    Separate from ``latest_raw`` because the two are written by two commands and a tree
    can legitimately hold a dated directory with only one of them in it. ``amr drift``
    reads this to check the figures the README types out by hand.
    """
    candidates = sorted(
        path
        for path in (root / "results").glob("*/contamination.json")
        if DATED.fullmatch(path.parent.name)
    )
    if not candidates:
        raise FileNotFoundError(
            f"no results/<date>/contamination.json under {root / 'results'}"
        )
    return candidates[-1]


def load_contamination(path: Path) -> dict:
    """A scenario record, with enough checked that a wrong file is not read as figures."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("scenario") != "contamination":
        raise ValueError(f"{path} declares scenario {document.get('scenario')!r}")
    return document


def write(document: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "raw.json"
    path.write_text(serialise(document), encoding="utf-8")
    return path


def load(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    schema = document.get("schema")
    if schema != SCHEMA_VERSION:
        raise ValueError(
            f"{path} declares schema {schema!r}; amr reads {SCHEMA_VERSION!r}"
        )
    return document
