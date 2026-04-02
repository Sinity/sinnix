---
name: polylogue
description: Work with Polylogue archives through the packaged CLI, Python API, and MCP wrapper. Use when you need archive freshness, conversation/session queries, provider filtering, scripted inspection, or reusable cross-client access to archived AI chats.
metadata:
  short-description: Unified Polylogue archive workflow
---

# Polylogue

Use the packaged wrappers from `PATH`:

- `polylogue` for ingest, maintenance, and quick archive queries
- `polylogue-python` for import-driven scripting
- `mcp-polylogue` for reusable agent/client access

## Interface Choice

1. Use `polylogue` when the task is operator-facing: ingest, refresh, list, search, or audit.
2. Use `polylogue-python` when the task is scripted inspection or library composition.
3. Use `mcp-polylogue` when the goal is a portable tool contract across agents or clients.

## Core Rules

1. Prefer the packaged wrappers configured by Sinnix over ad hoc repo-local entrypoints.
2. Do not assume a timer or background service has refreshed the archive; run an explicit refresh when freshness matters.
3. Do not reimplement transcript/session parsing when Polylogue already exposes the semantics through CLI, Python, or MCP.
4. Keep provider, tag, and action filters in the query layer instead of post-filtering raw markdown exports.

## Common Commands

```bash
# Refresh the archive explicitly
polylogue run

# List recent Codex sessions as JSON
polylogue --provider codex --format json --list --limit 50

# Search archived sessions by text
polylogue "duckdb scaffold" --provider claude-code --format json --list --limit 20
```

```python
from polylogue.facade import Polylogue
import asyncio

async def main() -> None:
    archive = Polylogue()
    try:
        sessions = await archive.list_conversations(provider="codex", limit=20)
        for session in sessions[:5]:
            print(session.id, session.title)
    finally:
        await archive.close()

asyncio.run(main())
```

## Notes

- `polylogue` is the canonical archive surface; the skill is only a routing guide for when to use which interface.
- If you are debugging Polylogue itself, work in `/realm/project/polylogue`. Otherwise stay at the packaged boundary.
