---
name: polylogue-archive-ops
description: Operate Polylogue through its packaged CLI and MCP wrapper, using the CLI for local archive workflows and `mcp-polylogue` for portable query access.
triggers:
  - "polylogue"
  - "chat archive"
  - "mcp polylogue"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
argument-hint: "<command> [args]"
---

# Polylogue Archive Ops

Use:

- `polylogue` for local ingest and archive maintenance
- `mcp-polylogue` for MCP-capable clients

Rules:

1. Prefer the packaged wrappers configured by Sinnix.
2. Use MCP when the goal is a reusable query/tool contract across clients.
3. Use the CLI when the goal is an operator workflow or archive maintenance step.
4. Do not recreate Polylogue archive semantics in bespoke scripts when the existing CLI or MCP surface already covers the task.
