---
name: polylogue
description: Query or develop Polylogue session archives, ingestion, storage tiers, lineage, CLI, MCP, daemon convergence, devtools verification, or historical work reconstruction.
---

# Polylogue

Polylogue archives AI sessions and exposes them through a query-first CLI, MCP,
Python API, and daemon. Use it for past-session reconstruction instead of
guessing. Read the repository `CLAUDE.md` for product invariants, and the
area sheets under `docs/atlas/` (storage, daemon, mcp — code-verified
anchors) before exploring an area; report an ATLAS-DELTA in your summary if
reality disagrees with a sheet.

## Reading history

Prefer the MCP `query`, `read`, `get`, `explain`, `context`, and `status`
operations. Query with refs and fetch full message text only when needed.
Use `context(intent="resume", repo_path=<abs>, cwd=<abs>)` to reconstruct work
after interruption. If ingestion is unavailable, use the `claude-sessions`
raw-JSONL stopgap.

The CLI is query-first. Signal intent with `find`, a quoted expression, or
field syntax, and filter public surfaces by `origin`, not provider. Confirm
freshness with `polylogued status` when results look stale.

## Development

Durability separates the six SQLite tiers: source, user, and audit are durable;
index and embeddings are rebuildable; ops is disposable. Never use rebuildable
state as authority for durable mutation. Preserve lineage composition and the
single-writer daemon route.

`devtools` is the repository verification surface:

```text
devtools test <selector>
devtools verify --quick
devtools verify
devtools verify --all
devtools why
devtools render all --check
```

`devtools verify` selects from and updates the checkout's corpus testmon
graph. A usable local graph survives newer primary files; a compatible seed
replaces an absent, unusable, or environment-incompatible copy when it would
select better. Without a usable seed, verification records a full seed run.
Package or interpreter changes can also require full execution. `devtools
why` and the run receipt explain the actual selection; graph usability alone
does not establish corpus coverage.

`devtools test <selector>` traces a run-local scratch graph, preserving the
corpus graph. Keep exact selectors in `verification_commands`; the generic
focused operation is `verify_quick`, which runs static checks only. The
candidate's hosted `verify` check runs affected verification; only `--all`
proves the corpus, at the master boundary. Read command, selection counts and
outcomes before claiming test coverage. Use existing receipt references;
do not infer success from a process exit or an empty selection.

Product work uses feature branches and squash-merged PRs. Generic lane,
job, and task lifecycle belongs to `agentctl` and the shared runtime skills, not
the contributor-facing project contract.
