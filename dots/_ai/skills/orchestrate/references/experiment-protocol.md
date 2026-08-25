# Experiment protocol

Registry: `.agent/scratch/experiments.jsonl` in the active project repo
(polylogue during the reindex campaign). One JSON line per experiment or
verdict note. Deletion trigger: rows whose doctrine update landed are dead
weight — prune on consumption; the registry never becomes a database.

Every experiment row must name:
- **The decision it could change** (a doctrine line, a model default, a
  dispatch shape). No decision → not an experiment, don't register it.
- **A stopping rule** and an **expiry** (in merged packets or days).
  Blocked/expired experiments close as *inconclusive*, never linger.
- Its **status**: designed | running | complete | superseded | inconclusive.

Discipline (adopted 2026-08-25 after the Sol process critique):
- Prefer **piggybacking on product work** that would be dispatched anyway
  over dedicated experiment arms; dedicated arms need the decision to be
  worth their cost.
- Supporting infrastructure gets built only when it has independent product
  value (usage capture, event spool — yes; a bespoke experiment harness — no).
- Results are **directional engineering evidence**, not science: n=1 gets
  "replicate before doctrine change" stamped on it, and doctrine updates —
  a changed default in this skill or its references — are the only durable
  output. An experiment whose result never touches doctrine was wasted;
  say so in its closing row.

Standing measured results live where they're consumed: model/tier evidence
in `model-landscape-*.md`, lens yields in the grok skill's
`defect-lenses.md`, process smells in `worker-contract.md`.
