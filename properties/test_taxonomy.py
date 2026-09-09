"""The taxonomy entries, executed.

Each entry in ``taxonomy/`` embeds the source of its reproduction module. These tests run
the reproduction and assert that the embedded source is byte-identical to the module that
ran, so a taxonomy entry cannot describe behaviour the code no longer has.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Callable

import pytest

from amr.protocol import ForgetMode, MemorySystem
from taxonomy.repro import (
    erasure_inflation,
    orphaned_derivative,
    silent_chain_truncation,
    undeclared_derivation,
)

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = ROOT / "taxonomy"

ENTRIES = {
    "erasure-inflation": erasure_inflation,
    "silent-chain-truncation": silent_chain_truncation,
    "orphaned-derivative": orphaned_derivative,
    "undeclared-derivation": undeclared_derivation,
}


def _fenced_python(text: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


@pytest.mark.parametrize("slug", sorted(ENTRIES))
def test_taxonomy_entry_embeds_its_reproduction(slug: str) -> None:
    """A taxonomy entry embeds the exact source of the module the suite runs."""
    entry = TAXONOMY / f"{slug}.md"
    assert entry.exists(), f"missing taxonomy entry {entry}"
    text = entry.read_text(encoding="utf-8")
    module = ENTRIES[slug]
    source = inspect.getsource(module)
    blocks = _fenced_python(text)
    assert source in blocks, (
        f"{entry.name} does not embed the current source of "
        f"{module.__name__}; the documentation has drifted from the code"
    )
    assert f"taxonomy/repro/{module.__name__.rsplit('.', 1)[1]}.py" in text
    for required in ("**Status:**", "**Caught by:**"):
        assert required in text, f"{entry.name} is missing {required}"


@pytest.mark.extra("taxonomy-erasure-inflation")
def test_erasure_inflation_reproduces(any_system: MemorySystem) -> None:
    """taxonomy/erasure-inflation.md: erase raises a survivor's confidence."""
    if ForgetMode.ERASE not in any_system.capabilities().supported_forget_modes:
        pytest.skip("system does not declare erase")
    result = erasure_inflation.reproduce(any_system)
    assert result["before"] == 0.4
    assert result["after"] == 0.9
    assert result["inflated"] is True
    assert result["chain_after"] == []
    assert result["receipt_reports_inflation"]


@pytest.mark.extra("taxonomy-silent-chain-truncation")
def test_silent_chain_truncation_is_handled(any_system: MemorySystem) -> None:
    """taxonomy/silent-chain-truncation.md: strict writes reject the truncation."""
    result = silent_chain_truncation.reproduce(any_system)
    assert result["rejected"] is True, "I1.6 requires the write to be rejected"
    assert result["truncated_chain_value"] == 0.9
    assert result["intact_chain_value"] == 0.4
    assert result["inflation_without_deletion"] is True
    assert result["persisted"] is True


@pytest.mark.extra("taxonomy-orphaned-derivative")
def test_orphaned_derivative_is_handled(
    make_any_system: Callable[..., MemorySystem]
) -> None:
    """taxonomy/orphaned-derivative.md: every mode leaves a defined derivative."""
    system = make_any_system()
    declared = system.capabilities().supported_forget_modes
    if not {ForgetMode.TOMBSTONE, ForgetMode.CASCADE, ForgetMode.ERASE} <= declared:
        pytest.skip("system does not declare all three modes")
    outcomes = orphaned_derivative.reproduce(system)

    assert outcomes["tombstone"]["survives"] is True
    assert outcomes["tombstone"]["dangling"] == []
    assert outcomes["cascade"]["survives"] is False
    assert outcomes["erase"]["survives"] is True
    assert outcomes["erase"]["dangling"] == []
    assert outcomes["erase"]["ancestors"] == []
    for mode in ("tombstone", "cascade", "erase"):
        assert outcomes[mode]["receipt_names_derivative"] is True, (
            "the receipt has to say what happened to the derivative"
        )


@pytest.mark.extra("taxonomy-undeclared-derivation")
def test_undeclared_derivation_is_out_of_scope(any_system: MemorySystem) -> None:
    """taxonomy/undeclared-derivation.md: no check at this boundary can catch it."""
    result = undeclared_derivation.reproduce(any_system)
    assert result["undeclared_effective"] == 0.95
    assert result["declared_effective"] == 0.2
    assert result["undeclared_ancestors"] == []
    assert result["indistinguishable_from_honest_root"] is True
