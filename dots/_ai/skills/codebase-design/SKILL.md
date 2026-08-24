---
name: codebase-design
description: Design or restructure modules, interfaces, seams, and adapters; assess module depth; or decide whether apparently unused code should be completed or removed.
---

# Codebase design

Design **deep modules**: much behavior behind a small interface at a clean
seam, testable through that interface. Use these terms exactly; consistent
language is the point.

## Glossary

- **Module**: anything with an interface and an implementation — function,
  class, package, tier-spanning slice. Scale-agnostic.
- **Interface**: everything a caller must know to use it correctly —
  signature, invariants, ordering, error modes, configuration, performance.
- **Depth**: leverage at the interface — behavior exercised per unit of
  interface learned. Deep = small interface, large behavior.
- **Seam**: where behavior can be altered without editing in place; the
  location of the interface. Placing the seam is its own decision.
- **Adapter**: the concrete thing satisfying an interface at a seam — a role,
  not a substance.
- **Leverage** (callers) and **locality** (maintainers): what depth buys —
  one implementation paying back across N call sites; change and bugs
  concentrating in one place.

## Principles

- Depth is a property of the interface, not the implementation. Internal
  seams (private, for the module's own tests) are fine and invisible.
- **The interface is the test surface.** Wanting to test past it means the
  module is the wrong shape.
- **One adapter is a hypothetical seam; two adapters is a real one.** Do not
  introduce a seam nothing varies across — this is the estate's
  no-compat-pre-adoption rule in module form.
- **The deletion test** (for shape, not for license — see below): imagine
  deleting the module. Complexity vanishing = it was a pass-through;
  complexity reappearing across N callers = it earned its keep.
- **Prove the rules bite**: any boundary you mechanize (layering manifest,
  import lint, dependency rule) gets a red twin — a deliberate violation
  observed to fail — before you trust it. The polylogue layering ratchet
  (baseline-exempt, growth-blocking) is the estate pattern for retrofitting
  a boundary onto an existing violation population.

## Deletion needs consent, not just a failed deletion test

The deletion test judges a module's *shape*. Whether code should be REMOVED
is a different question with its own doctrine, learned expensively (four
recorded wrong deletions from grep-level reasoning):

- **Unfinished is not obsolete.** Wired-but-unused parsers, dead-looking
  functions with tests, built-ahead packages (`sinex/`,
  `material_protocol/`) are what half-done work looks like. Deletion needs
  positive evidence of abandonment: a shipped replacement, a recorded
  decision, or explicit operator retirement. Check git history, beads, and
  design docs for intent before choosing removal over completion.
- **Reachability is checked mechanically, not by grep.** Import edges alone
  under-report (registries, lazy commands, `python -m` entries, re-exports);
  use the oracle-integrity reachability machinery where it exists.
- **Durable-tier structures require operator consent** and a
  copy-forward/migration design — write-only durable state is not
  automatically deletable.
- **Declarations die with their implementations.** A deletion tranche that
  removes a module must remove its CommandSpec, hook registration, config
  key, and doc line in the same change — the estate's recorded breakage
  class is exactly the dangling declaration.
- Fan-in before judging: a 415-line module imported by 126 files is small
  only in LOC. "Small says nothing about blast radius."

## Designing for testability

Accept dependencies, don't create them; return results over side effects;
small surfaces need fewer tests. Tests and callers cross the same seam.
Pre-agree the seams under test before writing tests — testing effort lands
on critical paths, not every edge (and see [[review-land]] for the
tautological-test smell: an assertion that recomputes its expectation the
way the code does proves nothing).

## Exploring alternatives

For a consequential interface, design it twice: spawn parallel subagents to
draft the interface radically differently, then compare on depth, locality,
and seam placement. Cheap relative to living with the wrong shape; matches
the estate's judge-panel orchestration pattern.

## Rejected framings

- Depth as implementation/interface line ratio (rewards padding).
- "Interface" as just the type signature.
- "Boundary" (overloaded); say seam or interface.
- Deletion-test-as-license (see consent doctrine above).
