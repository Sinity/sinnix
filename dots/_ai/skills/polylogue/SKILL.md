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
   a command; they describe the installed build. `polylogue status --json`
   reports freshness and daemon state; an empty result alone does not
   establish absent history.
2. Use `polylogue 'repo:NAME since:7d'` for a query, `polylogue recall WORDS`
   to find earlier work, and `polylogue read ORIGIN:ID` to read a session.
   `polylogue brief --cwd PATH` gives the session-start context;
   `polylogue takeover ORIGIN:ID` gives context for continuing another session.
3. Retain returned IDs and cursors. Follow the returned continuation to page
   through results or a long read; read the complete relevant messages before
   making a claim about prior work. IDs are opaque and may contain colons.
4. The installed MCP server exposes one tool per command (`query`, `read`,
   `recall`, `brief`, `takeover`, `status`, ...). Use their schemas for
   arguments. When ingestion is unavailable,
   [claude-sessions](../claude-sessions/SKILL.md) reads raw Claude transcripts.

The next deployed build changes this surface: reads take `session:ORIGIN:ID`,
pages continue by running the returned `next` call unchanged, `similar:`
replaces `near:`, and MCP has five tools (`polylogue_read`,
`polylogue_context`, `polylogue_note`, `polylogue_chat`, `polylogue_act`) that
take `{operation, arguments, request_id}`. Trust the schemas the server
reports over this paragraph.

## Develop Polylogue

Read the target checkout's `AGENTS.md`, `README.md`, `docs/architecture.md`
and `docs/README.md`, then the design page for the area. The main repository is
`/realm/project/polylogue/repo`. They own the current commands, crate
boundaries, archive schema and verification policy.

Use synthetic temporary archives. Run a checkout's binary explicitly with
its own archive when checking source changes; the ambient command is bound
to the operator's live archive. Builds and tests run through the checkout's
declared AgentCTL operations.

Sinnix owns installed commands, capture hooks, MCP launchers and the
`polylogue-live.service` user unit. A source edit changes nothing installed
until a Sinnix activation, which follows Sinnix `AGENTS.md`; then verify the
installed executable and live archive. Lynchpin reads its other owner-native sources independently; it has
no Polylogue archive or library dependency.
