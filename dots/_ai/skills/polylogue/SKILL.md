---
name: polylogue
description: "Query past AI sessions through Polylogue, or develop Polylogue itself: ingestion, provenance, queries, CLI, MCP, daemon behavior, and verification."
---

# Polylogue

Polylogue archives AI conversations and agent sessions. The installed
`polylogue` command uses the rewrite's live archive, shared with the daemon,
hooks, browser host and `mcp-polylogue`.

## Read history

1. The MCP server exposes `polylogue_read`, `polylogue_write` and
   `polylogue_act`. Use the installed tool schemas for operation names and
   arguments. For CLI syntax, use `polylogue --help` and `polylogue help read`.
2. Put the quoted selection first, then the verb and its options. Use
   `polylogue 'repo:NAME since:7d'` to list sessions, or
   `polylogue 'session:ORIGIN:ID' read --view dialogue` to read one session.
   Keep returned IDs intact, including colons.
3. Follow the returned continuation through the relevant messages before
   making a claim about prior work. Check `polylogue status --json` for
   freshness when a result is incomplete or empty. When the archive cannot
   serve Claude history, [claude-sessions](../claude-sessions/SKILL.md) reads
   the original transcripts.

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
