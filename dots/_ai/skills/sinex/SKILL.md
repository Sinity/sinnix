---
name: sinex
description: Work on Sinex capture, provenance, schemas, sources, automata, xtask, AgentCTL operations, database-backed verification, replay, deployment, or wipe-campaign decisions.
---

# Sinex

Sinex is the capture and provenance substrate. Read the repository
`CLAUDE.md`, `docs/architecture.md`, and `.agentctl/project.toml` for current
semantics and commands.

## Model

- Material events cite retained source material; derived events cite parent
  events. The database enforces exactly one provenance form.
- Event, acquisition, and processing times are distinct. Replay keeps event
  time but creates a new interpretation ID and processing time.
- Occurrence identity is stable source coordinates; event IDs identify one
  interpretation. Replay is intentionally non-idempotent.
- Schema evolution is declarative convergence through `sinex-schema apply`,
  not a migration chain.

Do not carry Polylogue's archive assumptions into Sinex. State is designed to
survive and fix forward through archive cascade and replay. A wipe is evidence
of a design failure unless the operator explicitly chooses it after direct
preservation checks.

## Commands

`xtask` is the only Cargo frontend. Use `xtask check`, `fix`, `test`, `build`,
`run`, `schema`, `history`, and `docs`; never invoke bare Cargo. Discover the
registered heavy routes with `agentctl project operations sinex`. Current core
operations include `check_default`, `build_default`, `fix_default`,
`test_default`, `run_core`, `run_all_automatons`, `run_all_sources`,
`vm_smoke`, and `vm_validate`.

Database-backed operations acquire the declared `dev_services` dependency.
Use the returned lease job ID as `SINEX_PRE_PUSH_AGENTCTL_LEASE_ID` when the
pre-push drift guard must use that workspace's PostgreSQL and NATS coordinates.
SQLx compiles against the live dev database; do not create an offline cache.

## Verification and deployment

Run the narrow semantic command while iterating, then one broad `xtask check
--full` or `xtask test --impact-mode=off --all` at the publishable boundary.
Product changes use a ready, squash-merged PR. The local gate is authoritative.

Production deployment is owned by Sinnix. Pin the Sinex revision and run the
Sinnix `switch` wrapper. Workstation activation does not restart `sinexd`;
restart it explicitly when immediate rollout is intended, then verify the
active binary, unit generation, and schema convergence.

Query the live wipe campaign through Beads (`bd show sinex-poma` and its
dependency graph) rather than copying status into instructions.
