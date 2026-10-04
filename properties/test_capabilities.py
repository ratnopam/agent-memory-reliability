"""The capability declaration has no implicit defaults, and reads back from JSON.

SPEC.md 8: "A declaration ... MUST state every field in this section explicitly. An
omitted field is not a default: a checker that cannot read a field MUST report the
declaration as invalid rather than assume a value for it."

That sentence constrains this repository twice. ``Capabilities`` is the in-process
declaration every adapter returns, so a dataclass default there is the assumed value the
section forbids, made where nobody looks. ``Capabilities.from_dict`` is the reader for a
declaration that arrives as JSON — somebody else's published ``raw.json`` — and a reader
that tolerates a missing key is the same failure a layer further out.

These are checks on the suite's own surfaces rather than on a system's behaviour, so they
carry no check id and no ``extra`` marker, the same way ``test_spec_coverage.py`` does.
"""

from __future__ import annotations

import pytest

from amr.protocol import Capabilities, ForgetMode, MemorySystem
from amr.results import capabilities_as_dict

#: A complete declaration, written out field by field. Deliberately not built from the
#: reference's: the point is that every key has to be present, so the fixture that tests
#: absence cannot itself depend on a default.
COMPLETE: dict[str, object] = {
    "system": "declaration-under-test",
    "version": "0.0.1",
    "supported_forget_modes": frozenset({ForgetMode.TOMBSTONE}),
    "default_forget_mode": ForgetMode.TOMBSTONE,
    "empty_chain_convention": 1.0,
    "revision": "logged",
    "revision_raise_supported": True,
    "scopes": "native",
    "cross_scope_derivation": "opaque-ancestor",
    "durability": "in-memory",
}

#: The six fields that carried a dataclass default before SPEC.md 8 was read strictly.
#: ``system``, ``version``, and the two forget-mode fields never had one.
FORMERLY_DEFAULTED = (
    "empty_chain_convention",
    "revision",
    "revision_raise_supported",
    "scopes",
    "cross_scope_derivation",
    "durability",
)


def test_the_complete_declaration_names_every_spec_field() -> None:
    """The fixture above is the §8 key set exactly, so the omission test is exhaustive."""
    assert set(COMPLETE) == set(Capabilities.SPEC_FIELDS)
    assert set(FORMERLY_DEFAULTED) <= set(Capabilities.SPEC_FIELDS)


@pytest.mark.parametrize("omitted", FORMERLY_DEFAULTED)
def test_omitting_a_declared_field_is_a_construction_error(omitted: str) -> None:
    """An omitted field is not a default (SPEC.md 8): it does not construct at all."""
    incomplete = {key: value for key, value in COMPLETE.items() if key != omitted}
    with pytest.raises(TypeError) as raised:
        Capabilities(**incomplete)  # type: ignore[arg-type]
    assert omitted in str(raised.value), (
        f"omitting {omitted} must fail in a way that names it; got {raised.value}"
    )


def test_a_complete_declaration_constructs() -> None:
    """The control. Without this, the test above passes for the wrong reason."""
    declaration = Capabilities(**COMPLETE)  # type: ignore[arg-type]
    assert declaration.notes == (), "notes is the one optional field, and defaults empty"


def test_from_dict_round_trips_a_declaration(any_system: MemorySystem) -> None:
    """Every registered system's declaration survives the JSON shape and back."""
    declared = any_system.capabilities()
    assert Capabilities.from_dict(capabilities_as_dict(declared)) == declared


@pytest.mark.parametrize("missing", Capabilities.SPEC_FIELDS)
def test_from_dict_requires_every_spec_field(missing: str) -> None:
    """A checker that cannot read a field reports the declaration invalid (SPEC.md 8)."""
    mapping = {key: value for key, value in _serialisable().items() if key != missing}
    with pytest.raises(ValueError, match=missing):
        Capabilities.from_dict(mapping)


def test_from_dict_rejects_an_unknown_field_by_name() -> None:
    """A typo in a published declaration is an error, not a field nobody reads."""
    mapping = {**_serialisable(), "empty_chian_convention": 0.0}
    with pytest.raises(ValueError, match="empty_chian_convention"):
        Capabilities.from_dict(mapping)


def test_from_dict_accepts_notes_and_nothing_else_optional() -> None:
    """``notes`` is outside SPEC.md 8, so it is the one key that may be absent."""
    with_notes = Capabilities.from_dict({**_serialisable(), "notes": ["a remark"]})
    assert with_notes.notes == ("a remark",)
    assert Capabilities.from_dict(_serialisable()).notes == ()


def _serialisable() -> dict[str, object]:
    """``COMPLETE`` as canonical JSON would carry it: sorted strings, not Python enums."""
    return capabilities_as_dict(Capabilities(**COMPLETE))  # type: ignore[arg-type]
