---
name: polylogue-api
description: >
  Use the system-wide Polylogue Python API through `polylogue-python` for
  import-driven archive access, scripting, and MCP/server composition when a
  direct library surface is preferable to CLI-only workflows.
metadata:
  short-description: Polylogue Python API workflows
---

# Polylogue API

Use this skill when the task needs Polylogue as an importable Python library
rather than only its CLI or MCP wrapper.

## Canonical Surface

- System-wide API interpreter: `polylogue-python`
- Python imports from `polylogue.*`
- CLI and MCP remain available, but are secondary when the task is about
  library composition or scripting

## Rules

1. Prefer `polylogue-python -c ...` or `polylogue-python -m ...` when the task
   is API-oriented.
2. Prefer `polylogue` CLI for archive maintenance and ingest workflows.
3. Prefer `mcp-polylogue` when the goal is a reusable cross-client MCP
   contract.
4. Do not duplicate archive semantics in ad hoc scripts when the existing
   library, CLI, or MCP surface already covers them.
5. Prefer the packaged wrappers from `PATH`; do not jump into the Polylogue
   repo unless you are debugging packaging or developing Polylogue itself.
6. Do not assume a service/timer is keeping the archive fresh; run `polylogue
   run` explicitly when freshness matters.
7. For Lynchpin work, keep conversation semantics owned by Polylogue and build
   adapters on top of that API instead of re-encoding them from Markdown.

## Common Invocations

```bash
polylogue-python -c "import polylogue; print(polylogue.__file__)"
polylogue-python -c "from polylogue.services import build_runtime_services; print(build_runtime_services())"
polylogue-python -c "from polylogue.mcp.server import build_server; print(build_server())"
polylogue --help
polylogue mcp
mcp-polylogue
```

## Workflow Guidance

- Use the API when you need to compose Polylogue services inside Python.
- Use the CLI when you need operator flows such as ingest, query, reset, site,
  or run stages.
- Use MCP when another agent/client should consume one stable tool contract
  instead of embedding Polylogue logic locally.
- Use the packaged wrappers because they are hardened against repo-local Python
  environment leakage.
