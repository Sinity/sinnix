---
name: polylogue-archive-ops
description: >
  Operate Polylogue as the canonical chat-archive CLI and MCP surface. Use when
  ingesting, querying, or wiring Polylogue archives, especially when deciding
  between direct CLI workflows and the packaged `mcp-polylogue` server for
  Codex or Claude Code.
metadata:
  short-description: Polylogue archive CLI and MCP workflow
---

# Polylogue Archive Ops

Use this skill when the task touches archived AI-chat data.

## Surface Choice

1. Use `polylogue` CLI for local operator flows: ingest, inspect, archive maintenance.
2. Use `mcp-polylogue` when an MCP-capable client should query the archive through one canonical tool contract.
3. Do not duplicate Polylogue archive logic in ad hoc skills when the MCP already exposes it cleanly.

## Commands

```bash
polylogue --help
polylogue run
polylogue mcp
mcp-polylogue
```

## Rules

1. Prefer the packaged `polylogue` binary, not repo-local bootstrap commands.
2. Treat MCP as the portable query surface and skills as orchestration around it.
3. When configuring clients, use the `mcp-polylogue` wrapper rather than embedding provider-specific launch logic.
4. Keep archive state under the existing Sinnix-managed Polylogue directories; do not invent new state roots.
