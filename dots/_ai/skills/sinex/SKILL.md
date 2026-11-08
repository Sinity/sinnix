---
name: sinex
description: Work on Sinex capture, provenance, schemas, sources, automata, xtask, AgentCTL operations, database-backed verification, replay, deployment, or wipe-campaign decisions.
---

# Sinex

Sinex is the capture and provenance substrate. Read the repository
`AGENTS.md`, `docs/architecture.md`, and `.agentctl/project.toml` for current
semantics and commands.

## Model

- Material events cite retained source material; derived events cite parent
  events. The database enforces exactly one provenance form.
- Event, acquisition, and processing times are distinct. Replay keeps event
  time but creates a new interpretation ID and processing time.
- Occurrence identity is stable source coordinates; event IDs identify one
  interpretation. Replay is intentionally non-idempotent.
- Schema changes follow the repository `AGENTS.md`.

Do not carry Polylogue's archive assumptions into Sinex. State is designed to
survive and fix forward through archive cascade and replay. A wipe is evidence
of a design failure unless the operator explicitly chooses it after direct
preservation checks.

## Commands

`xtask` is the only Cargo frontend. Use `xtask check`, `fix`, `test`, `build`,
`run`, `schema`, `history`, and `docs`; never invoke bare Cargo. Discover the
registered heavy routes with `agentctl project operations sinex`.

Read the descriptor for each database-backed operation's service requirements.
An operation declaring `requires` owns those services inside its job unit.
Standalone commands need an explicit `dev_services` job; use its job ID for
cancellation. The checkout devshell owns PostgreSQL and NATS coordinates.
SQLx compiles against the live dev database; do not create an offline cache.

## Verification and deployment

Type-check and run focused tests while iterating, and the full check on the
head that lands (repository `AGENTS.md`).

Production deployment is owned by Sinnix. Pin the Sinex revision and run the
Sinnix `switch` wrapper. Workstation activation does not restart `sinexd`;
restart it explicitly when immediate rollout is intended, then verify the
active binary, unit generation, and schema convergence.
