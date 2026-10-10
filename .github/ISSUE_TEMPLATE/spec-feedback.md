---
name: Specification feedback
about: A check is ambiguous, unfalsifiable, wrong, or missing
title: "spec: "
labels: ["specification"]
---

<!--
The specification is a draft and is under test as much as any implementation. Accepted
feedback becomes a numbered entry in the project's feedback log with the reading that was
taken and why, and the changelog at the foot of version2/SPEC.md names it. Fill in what you
can; a partial report is better than none.
-->

**Which text.** Section or check number in `version2/SPEC.md`, and the version at the top of
that file.

**What it says, quoted.**

**The problem.** One of:

- *ambiguous* — two readings, both defensible, and they require different behaviour. Give both.
- *unfalsifiable* — no observation through the twelve operations could show a system violating it.
- *wrong* — it mandates behaviour that is unimplementable, or that contradicts another check.
- *missing* — a property in scope that no numbered check covers. Say what a violating system
  would do that the suite currently reports as PASS.

**A system that shows it.** If you hit this while measuring something real, name the system and
the mode, and paste the relevant rows of your `summary.md`. Not required.

**What you would have it say.** A proposed wording, however rough. If you are proposing a new
numbered check, note that it has to come with a test that fails without it — a check nobody can
run is a claim, and the point of the repository is that claims are checked.

**Anything the check should not do.** In particular: does your reading require branching on the
forget mode? A check that special-cases a mode measures the mode rather than the property, and
will not be merged, so a reading that avoids the branch is worth more.
