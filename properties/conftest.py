"""Fixtures and the DIVERGENCE outcome.

The ``system`` fixture is parameterised over every ``(registered system, declared forget
mode)`` pair, so a test function runs once per cell of the results matrix and each run
gets a fresh instance. ``any_system`` is the same thing without the mode dimension, for
supplementary checks whose answer cannot depend on a forget mode.

DIVERGENCE is a third outcome, not a forgiven failure and not an ``xfail``. A check that
meets a spec-sanctioned divergence calls ``divergence.record(...)``; that stamps the
report and pytest is told to display it as its own status. The runner reads the same
stamp, so ``make test`` and ``make reproduce`` agree on every cell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

import pytest

from amr import registry
from amr.outcomes import DIVERGENCE_PROPERTY, DivergenceRecord
from amr.protocol import Capabilities, ForgetMode, MemorySystem

CHECK_PROPERTY = "amr-check"
EXTRA_PROPERTY = "amr-extra"
SYSTEM_PROPERTY = "amr-system"
MODE_PROPERTY = "amr-mode"
DOC_PROPERTY = "amr-doc"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "check(id): the numbered SPEC.md conformance check this test is"
    )
    config.addinivalue_line(
        "markers", "extra(name): a supplementary check, not numbered in SPEC.md"
    )


# --------------------------------------------------------------------- systems


@dataclass(frozen=True)
class SystemConfig:
    """One cell of the results matrix: a system and a forget mode."""

    name: str
    mode: ForgetMode
    build: Callable[[], MemorySystem]

    def __str__(self) -> str:
        return f"{self.name}-{self.mode.value}"


def _configs() -> tuple[SystemConfig, ...]:
    configs: list[SystemConfig] = []
    for registration in registry.systems():
        for mode in registry.modes_for(registration):
            configs.append(
                SystemConfig(
                    name=registration.name,
                    mode=mode,
                    build=lambda r=registration, m=mode: r.build(m),
                )
            )
    return tuple(configs)


CONFIGS = _configs()
REGISTRATIONS = registry.systems()


@pytest.fixture(params=CONFIGS, ids=[str(config) for config in CONFIGS])
def system_config(request: pytest.FixtureRequest) -> SystemConfig:
    return request.param


@pytest.fixture
def make_system(system_config: SystemConfig) -> Callable[[], MemorySystem]:
    """A factory, for checks that need more than one instance (P4.5)."""
    return system_config.build


@pytest.fixture
def system(make_system: Callable[[], MemorySystem]) -> MemorySystem:
    return make_system()


@pytest.fixture
def mode(system_config: SystemConfig) -> ForgetMode:
    return system_config.mode


@pytest.fixture
def capabilities(system: MemorySystem) -> Capabilities:
    return system.capabilities()


@pytest.fixture(
    params=REGISTRATIONS, ids=[registration.name for registration in REGISTRATIONS]
)
def registration(request: pytest.FixtureRequest) -> registry.Registration:
    return request.param


@pytest.fixture
def make_any_system(
    registration: registry.Registration,
) -> Callable[..., MemorySystem]:
    return registration.build


@pytest.fixture
def any_system(make_any_system: Callable[..., MemorySystem]) -> MemorySystem:
    return make_any_system()


# ------------------------------------------------------------------ divergence


class DivergenceRecorder:
    """Records a sanctioned divergence on the running test."""

    def __init__(self, node: pytest.Item) -> None:
        self._node = node

    def record(self, check: str, spec_ref: str, detail: str) -> None:
        record = DivergenceRecord(check=check, spec_ref=spec_ref, detail=detail)
        self._node.user_properties.append(
            (DIVERGENCE_PROPERTY, json.dumps(record.as_dict(), sort_keys=True))
        )


@pytest.fixture
def divergence(request: pytest.FixtureRequest) -> DivergenceRecorder:
    return DivergenceRecorder(request.node)


@pytest.fixture(autouse=True)
def _stamp_metadata(request: pytest.FixtureRequest) -> None:
    """Stamp check id, system, mode, and spec row onto the report.

    The runner reads these instead of parsing node ids, so renaming a test cannot
    silently move a cell in the matrix.
    """
    node = request.node
    check = node.get_closest_marker("check")
    if check is not None:
        node.user_properties.append((CHECK_PROPERTY, check.args[0]))
    extra = node.get_closest_marker("extra")
    if extra is not None:
        node.user_properties.append((EXTRA_PROPERTY, extra.args[0]))
    doc = (getattr(node, "function", None).__doc__ or "").strip()
    node.user_properties.append(
        (DOC_PROPERTY, doc.splitlines()[0].strip() if doc else "")
    )
    callspec = getattr(node, "callspec", None)
    params = callspec.params if callspec is not None else {}
    config = params.get("system_config")
    if config is not None:
        node.user_properties.append((SYSTEM_PROPERTY, config.name))
        node.user_properties.append((MODE_PROPERTY, config.mode.value))
    elif params.get("registration") is not None:
        node.user_properties.append((SYSTEM_PROPERTY, params["registration"].name))


def pytest_report_teststatus(
    report: pytest.TestReport, config: pytest.Config
) -> tuple[str, str, tuple[str, dict[str, bool]]] | None:
    if report.when != "call" or not report.passed:
        return None
    for key, _ in report.user_properties:
        if key == DIVERGENCE_PROPERTY:
            return "divergence", "D", ("DIVERGENCE", {"yellow": True})
    return None
