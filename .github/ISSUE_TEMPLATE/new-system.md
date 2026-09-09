---
name: New system measured
about: Results from running the suite against a memory system
title: "results: "
labels: ["results"]
---

<!--
Failures are the interesting case. A matrix with FAILs and a declaration that explains them is
worth more than a clean sheet nobody can reproduce. docs/adding-a-system.md is the guide;
examples/external-adapter/ is an adapter to copy.
-->

**System.** Name, version, and how it was configured — in-memory, on disk, hosted, whatever
changes the answer.

**Declaration.** Paste the `capabilities` block from your `raw.json`, or the fields you set:

```
supported_forget_modes:
default_forget_mode:
empty_chain_convention:
revision:
revision_raise_supported:
scopes:
cross_scope_derivation:
durability:
```

**Matrix.** The property table from your `summary.md`, one column per forget mode.

**Every FAIL and DIVERGENCE.** For each one, the check id and one line on which it is:

- the *adapter* is incomplete — an operation you have not written yet;
- the *system* does not have the property, and cannot without a change upstream;
- the *check* is wrong. Then open a specification-feedback issue too, or say so here and both
  can be handled in one pull request.

**Reproducing.** What someone else has to install and run to get the same `raw.json`. If the
adapter is public, link it. If the system needs a network service, say so plainly — the suite
here calls no network and no model, and results that need one are still welcome as long as the
dependency is stated.

**Environment.** The `environment` block from your `raw.json` (Python version, platform, commit).
