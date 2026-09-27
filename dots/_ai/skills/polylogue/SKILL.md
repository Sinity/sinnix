---
name: polylogue
description: Query past AI sessions through Polylogue, or develop Polylogue itself — ingestion, storage tiers, lineage, CLI, MCP, daemon convergence, devtools verification.
---

# Polylogue

Polylogue archives AI sessions and serves them through a query-first CLI, an
MCP server, a Python API, and a daemon. Use it to reconstruct past work
instead of guessing. For development, the repository's `AGENTS.md` holds the
product invariants and `docs/atlas/` orients each area.

## Reading history

- Prefer the MCP operations: `status` before freshness-sensitive or
  completeness claims, `explain` when fields or grammar are uncertain,
  `query` to find sets, `read` or `get` for bounded context, `context` for a
  resume or prior-art packet (`context(intent="resume", repo_path=<abs>,
  cwd=<abs>)` after an interruption). Keep the returned refs and fetch full
  message text only when needed.
- On the CLI, signal query intent with `find`, a quoted expression, or field
  syntax, and filter by `origin`, not provider. `polylogued status` shows
  freshness when results look stale.
- When ingestion is unavailable, `claude-sessions` reads raw Claude
  transcripts.

## Developing

- Six SQLite tiers, split by durability: `source`, `user`, and `audit` are
  durable; `index` and `embeddings` rebuildable; `ops` disposable. Rebuildable
  state is never the authority for a durable mutation. Live writes go through
  the daemon's single writer; lineage is stored as a divergent tail and
  recomposed on read.
- Code edits can move the derived schema identity even without DDL. Check
  `devtools schema closure <file>` for anything you change and land closure
  changes before a rebuild starts.
- `devtools test <selector>` runs an explicit focused selection; keep exact
  selectors in a task's `verification_commands`. `devtools verify --quick`
  runs static checks only. `devtools verify` makes one bounded selection from
  a usable testmon graph and reports zero honestly; if the graph is unusable
  it refuses, and you run a focused selection instead. `devtools verify
  --all` runs the complete corpus only when scheduled or explicitly
  requested. Do not re-run a green or failed verification on the same
  revision to get a bigger selection. `devtools why` and the run receipt show
  what ran; an empty selection is not a pass.
- Product work lands through feature branches and squash-merged PRs.
