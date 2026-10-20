---
name: polylogue
description: "Query past AI sessions through Polylogue, or develop Polylogue itself: ingestion, provenance, queries, CLI, MCP, daemon behavior, and verification."
---

# Polylogue

Polylogue archives AI conversations and agent sessions. Use it to reconstruct
past work from source evidence. Select instructions for the executable or
checkout you are actually using: the installed Python service and the Rust
rewrite can coexist, with different commands and archives.

## Read history

1. Inspect the available MCP tool descriptions or `polylogue --help` before
   choosing a command. `polylogue status` establishes freshness and service
   availability; an empty result alone does not establish absent history.
2. On the Python query-first CLI, use `polylogue find 'QUERY'` and
   `polylogue find 'QUERY' then read`. Filter source families with `origin`,
   not provider. Its MCP operations include `status`, `explain`, `query`,
   `read`, `get`, and `context`; use the exposed schemas for their arguments.
3. On the Rust CLI, use its current README and command help. Its query syntax,
   daemon entry point and context commands differ from Python. Run a checkout's
   built binary explicitly when checking the rewrite, rather than assuming the
   ambient `polylogue` command comes from that checkout.
4. Find a bounded set, retain returned references, and read the complete
   relevant messages before making a claim about prior work. When ingestion
   is unavailable, [claude-sessions](../claude-sessions/SKILL.md) reads raw
   Claude transcripts.

## Develop Polylogue

Read the target checkout's `AGENTS.md`, `README.md` and
`docs/development.md`. They own the current architecture and development
commands. The main repository at `/realm/project/polylogue/repo` is the Rust
rewrite; its README identifies whether it has replaced the deployed Python
version. Verify that boundary before using real archives or service commands.

For the Rust checkout:

- `crates/` and `xtask/` own implementation and developer checks. Follow the
  repository's crate boundaries and typed store interfaces; inspect the
  actual schema and archive layout instead of importing Python tier rules.
- Run focused tests while editing. The repository's fast check runs on push;
  full checks belong to integrated batches under its development policy.
  Read `docs/development.md` for current selectors and declared AgentCTL
  operations rather than applying Python `devtools` commands to Rust.
- Use synthetic test archives. Treat the rewrite's archive and the deployed
  archive as separate until a verified cutover establishes otherwise.
- Follow the checkout's delivery rules. A merge proves integration; report
  the checks that actually ran separately.

For an older Python checkout, read that checkout's own instructions and CLI
help. Its `devtools`, storage-tier and schema-closure procedures apply only
where that checkout still implements them.

A source edit does not switch the installed CLI, daemon, capture hooks or MCP
server. Deployment and data migration require their own authorized operation
and verification against the intended installed executable and archive.
