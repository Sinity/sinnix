---
name: polylogue-api
description: Use the system-wide Polylogue Python API through `polylogue-python` for import-driven archive access and scripting.
triggers:
  - "polylogue api"
  - "polylogue python"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
argument-hint: "<python-snippet|module>"
---

# Polylogue API

Use:

- `polylogue-python` for import-driven Polylogue API access
- `polylogue` for CLI operator flows
- `mcp-polylogue` for MCP-capable clients

Rules:

1. Prefer `polylogue-python` when the task is about library composition or scripted inspection.
2. Prefer `polylogue` for archive maintenance and ingest.
3. Prefer `mcp-polylogue` for reusable cross-client tool access.
4. Prefer the packaged wrappers from `PATH`; only enter the Polylogue repo when debugging packaging or developing Polylogue itself.
5. Do not assume a service/timer is keeping the archive fresh; run `polylogue run` explicitly when freshness matters.
6. For Lynchpin work, keep conversation semantics owned by Polylogue and build adapters on top of that API instead of re-encoding them from Markdown.
