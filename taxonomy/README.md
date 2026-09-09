# Failure mode taxonomy

A failure mode is a way a memory chain can produce a number, or a state, that a reader
would be wrong to trust. Each entry here is one such way.

Entries are not bugs in any particular system. Two of the four are properties of the
arithmetic itself, one is a design choice with a defensible cost, and one is outside what
this layer can see at all. Naming them is the point: an unnamed failure mode gets
rediscovered.

## What an entry contains

- **Name and description.** One paragraph. What goes wrong, and why it is not obvious.
- **Reproduction.** A Python snippet, embedded verbatim from `taxonomy/repro/<name>.py`.
  `properties/test_taxonomy.py` imports that module, runs it against every registered
  system, and asserts that the code embedded here is byte-identical to the code that ran.
  An entry cannot drift from the behaviour it describes.
- **Caught by.** The conformance check that detects it, or an explicit statement that no
  check can.
- **Status.** One of:
  - `open` — reproducible, unresolved, and reported rather than scored. The
    specification deliberately leaves the tension open.
  - `handled` — a property in the specification rules it out, and a check enforces that.
  - `out-of-scope` — real, but not observable at this operation boundary. Saying so is
    more useful than pretending otherwise.

## Entries

| Entry | Status | Caught by |
|---|---|---|
| [erasure-inflation](erasure-inflation.md) | `open` | P2.5 under `erase`, reported as DIVERGENCE |
| [silent-chain-truncation](silent-chain-truncation.md) | `handled` | P1.6 (strict writes) |
| [orphaned-derivative](orphaned-derivative.md) | `handled` | P3.3, P3.5 (defined modes and receipts) |
| [undeclared-derivation](undeclared-derivation.md) | `out-of-scope` | nothing — see the entry |

## Adding an entry

1. Write `taxonomy/repro/<slug>.py` with a `reproduce(system) -> dict` function that uses
   `harness.protocol` only and names any forget mode explicitly.
2. Write `taxonomy/<slug>.md` with the sections above, embedding the module source in a
   `python` fenced block.
3. Register the module in `ENTRIES` in `properties/test_taxonomy.py` and assert the
   numbers the entry claims.
