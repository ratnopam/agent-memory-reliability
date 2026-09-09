"""What this adapter tells the suite about itself. SPEC.md 8.

Every field is stated. Absence is not a default here: a declaration that leaves something
out is a declaration the suite cannot check you against, and the specification says so.

This one is deliberately weaker than the reference's, in three ways, and each one is
visible in the results:

* ``supported_forget_modes`` names one mode, so the matrix has one column instead of
  three. The two mode-dependent taxonomy reproductions are reported as failures for the
  same reason: the suite has no "not applicable" state (see docs/adding-a-system.md).
* ``revision`` is ``none``, so ``revisions`` returns nothing and **P2.6 fails**.
* ``durability`` is ``in-memory`` and the adapter does not implement ``Reopenable``, so
  **P1.5 and P1.7 fail** — the first because provenance cannot be shown to survive a
  restart, the second because a snapshot is the only place a cycle can be introduced from
  outside when ids are store-assigned.

Three real failures, from a declaration rather than from a bug. That is the point of the
example: this is what an honest partial implementation looks like on the first run.
"""

from __future__ import annotations

from amr.protocol import Capabilities, ForgetMode

#: Rename this and the entry point in pyproject.toml together. The suite reports results
#: under this name, and ``SYSTEMS=`` selects by it.
SYSTEM_NAME = "amr-adapter-example"
SYSTEM_VERSION = "0.1.0"

#: One mode. Adding ``cascade`` or ``erase`` here without implementing it turns a missing
#: column into a failing one, which is the honest direction for that mistake to break in.
MODES = frozenset({ForgetMode.TOMBSTONE})

#: min over an empty ancestor chain (SPEC.md 5). Never reachable in a tombstone-only
#: store, because a tombstone keeps its chain position — declared anyway, because the
#: suite compares this adapter's arithmetic against the value it published.
EMPTY_CHAIN = 1.0

NOTES = (
    "A teaching example over a plain dict. Not a product, and not an adapter for one.",
    "revise works and is not recorded: the declaration says revision=none, so P2.6 fails.",
    "No snapshot, so P1.5 and P1.7 fail rather than being skipped.",
)

DECLARATION = Capabilities(
    system=SYSTEM_NAME,
    version=SYSTEM_VERSION,
    supported_forget_modes=MODES,
    default_forget_mode=ForgetMode.TOMBSTONE,
    empty_chain_convention=EMPTY_CHAIN,
    revision="none",
    revision_raise_supported=True,
    scopes="native",
    cross_scope_derivation="opaque-ancestor",
    durability="in-memory",
    notes=NOTES,
)
