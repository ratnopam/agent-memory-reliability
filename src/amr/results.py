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
