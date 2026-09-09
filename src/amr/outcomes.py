"""The three result states, and the rule for when a failure is a divergence.

SPEC.md 9 reports PASS, FAIL, and DIVERGENCE. DIVERGENCE is not "a failure we decided
to forgive": it is reserved for behaviour the specification deliberately leaves open
(SPEC.md 6.4) in a system whose capability declaration says it behaves that way.

``xfail`` is deliberately not used. An xfail is a claim about a test; a divergence is a
claim about a specification. The suite has to keep them apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from amr.protocol import Capabilities, ForgetMode

#: Key under which a divergence is stamped into a pytest report's user properties.
DIVERGENCE_PROPERTY = "amr-divergence"


class CheckOutcome(str, Enum):
    """See SPEC.md 9."""

    PASS = "PASS"
    FAIL = "FAIL"
    DIVERGENCE = "DIVERGENCE"


@dataclass(frozen=True)
class DivergenceRecord:
    """One sanctioned divergence, as reported by a check."""

    check: str
    spec_ref: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"check": self.check, "spec_ref": self.spec_ref, "detail": self.detail}


def erasure_inflation_is_declared(
    capabilities: Capabilities, mode: ForgetMode
) -> bool:
    """True when SPEC.md 6.4 sanctions inflation for this system in this mode.

    Three things have to hold. The run is under ``erase``; the system declared
    ``erase`` as a supported mode, so the behaviour is chosen rather than accidental;
    and the system declared an empty-chain convention above zero, which is the
    arithmetic that produces the inflation. A system that declared
    ``empty_chain_convention: 0.0`` and still inflated would be inconsistent with its
    own declaration, and that is a FAIL.
    """
    return (
        mode is ForgetMode.ERASE
        and ForgetMode.ERASE in capabilities.supported_forget_modes
        and capabilities.empty_chain_convention > 0.0
    )
