---
name: polylogue
description: "Query past AI sessions through Polylogue, or develop Polylogue itself: ingestion, provenance, queries, CLI, MCP, daemon behavior, and verification."
---

# Polylogue

Polylogue archives AI conversations and agent sessions. The installed
`polylogue` command uses the rewrite's live archive, shared with the daemon,
hooks, browser host and `mcp-polylogue`.

## Read history

1. Read the available MCP tool schemas or `polylogue --help` before choosing
   a command. `polylogue status --json` reports freshness and daemon state;
   an empty result alone does not establish absent history.
2. Use `polylogue 'repo:NAME since:7d'` for a query, `polylogue recall WORDS`
   to find earlier work, and `polylogue read ORIGIN:ID` to read a session.
   `polylogue brief --cwd PATH` gives the session-start context;
   `polylogue takeover ORIGIN:ID` gives context for continuing another session.
3. Retain returned IDs and cursors. Follow the next cursor to page through
   results or a budgeted read; read the complete relevant messages before
   making a claim about prior work. IDs are opaque and may contain colons.
4. MCP tools come from the same command table, including `query`, `read`,
   `recall`, `brief`, `takeover` and `status`. Use their exposed schemas for
   arguments. When ingestion is unavailable,
   [claude-sessions](../claude-sessions/SKILL.md) reads raw Claude transcripts.

## Develop Polylogue

Read the target checkout's `AGENTS.md`, `README.md`, `docs/architecture.md`
and `docs/development.md`. The main repository is
`/realm/project/polylogue/repo`. They own the current commands, crate
boundaries, archive schema and verification policy.

Use synthetic temporary archives. Run a checkout's binary explicitly with
its own archive when checking source changes; the ambient command is bound
to the operator's live archive. Builds and tests run through the checkout's
declared AgentCTL operations.

Sinnix owns installed commands, capture hooks, MCP launchers and the
`polylogue-live.service` user unit. A source edit requires a separately
authorized activation and verification of the installed executable and live
archive. Lynchpin reads its other owner-native sources independently; it has
no Polylogue archive or library dependency.
