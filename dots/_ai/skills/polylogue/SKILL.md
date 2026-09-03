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

Plain verification uses a compatible testmon graph or refuses. Lanes run
selected verification from the seed inherited off the main checkout — false
negatives there are accepted; only `--all` proves the full corpus, at
merge/master boundaries. Per-PR CI runs the quick gate, so local verification
is still required. Do not scrape `.cache/verify` as an inter-project
contract; publish stable evidence through an explicit export surface.

Product work uses feature branches and squash-merged PRs. Generic lane,
job, and task lifecycle belongs to `agentctl` and the shared runtime skills, not
the contributor-facing project contract.
