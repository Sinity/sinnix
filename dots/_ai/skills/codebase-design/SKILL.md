---
name: codebase-design
description: Design or restructure modules, interfaces, seams, and adapters; judge module depth; or decide whether apparently unused code should be completed or deleted.
---

# Codebase design

Aim for deep modules: much behavior behind a small interface, placed at a
clean seam and tested through that interface. Use the terms below exactly;
shared vocabulary is the point.

## Terms

- **Module**: anything with an interface and an implementation, at any scale:
  a function, a class, a package, a slice across tiers.
- **Interface**: everything a caller must know to use it correctly:
  signature, invariants, ordering, error modes, configuration, cost.
- **Depth**: behavior gained per unit of interface learned. Deep means a small
  interface over a lot of behavior. It is a property of the interface, not of
  line counts.
- **Seam**: where behavior can change without editing in place; where the
  interface sits. Placing it is its own decision.
- **Adapter**: whatever satisfies an interface at a seam.

## Principles

- The interface is the test surface. Wanting to test past it means the module
  has the wrong shape.
- One adapter is a hypothetical seam; two make it real. Do not add a seam
  nothing varies across.
- Deletion test for shape: imagine removing the module. If its complexity
  vanishes, it was a pass-through; if the complexity reappears across its
  callers, it earns its place.
- Accept dependencies rather than creating them, return results rather than
  causing side effects, and agree on the seams under test before writing
  tests.
- A boundary you mechanize (a layering manifest, an import rule) gets a
  deliberate violation that you watch fail before you trust it. A ratchet
  (existing violations baselined, growth blocked) retrofits a boundary onto
  existing code.
- Judge blast radius by fan-in, not size: a short module imported everywhere
  is not small.
- For a consequential interface, draft it twice, radically differently (in
  parallel agents if available), and compare depth, locality, and seam
  placement before committing.

## Removing code

Whether code should be deleted is a separate question from its shape.

- Unfinished is not obsolete. Wired-but-unused code, tested functions with no
  callers yet, and built-ahead packages are what half-done work looks like.
  Deletion needs positive evidence: a shipped replacement, a recorded
  decision, or explicit authorization. Check history, tasks, and design docs
  for intent first.
- Establish reachability mechanically. Import edges miss registries, lazy
  commands, string-dispatched handlers, entry points, and re-exports; use the
  repository's reachability tooling where it exists.
- A deletion removes its declarations in the same change: command specs, hook
  registrations, config keys, docs, generated surfaces.
- Durable stored structures need the repository's migration regime and,
  where it requires one, operator consent.
