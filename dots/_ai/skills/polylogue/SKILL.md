---
name: polylogue
description: Work with Polylogue archives through the packaged CLI, Python API, and MCP wrapper. Use when you need archive freshness, conversation/session queries, provider or action filtering, durable product inspection, readiness checks, or stable downstream archive-product bundles.
metadata:
  short-description: Polylogue archive and products workflow
---

# Polylogue

Use the packaged wrappers from `PATH`:

- `polylogue` for ingest, refresh, search, archive maintenance, and product inspection
- `polylogue-python` for scripted inspection over the public library surface
- `mcp-polylogue` when the goal is a reusable archive tool contract across agents or clients

## Interface Choice

1. Use `polylogue` for operator-facing work: refresh, search, list, audit, product status, or product export.
2. Use `polylogue-python` when you need scripted analysis, filter composition, or direct access to durable products.
3. Use `mcp-polylogue` when the archive should be exposed as a portable service boundary rather than a repo-local script.

## Core Rules

1. Prefer the packaged wrappers configured by Sinnix over ad hoc repo-local entrypoints.
2. When freshness matters, run an explicit refresh. Use `polylogue run all` for end-to-end updates or `polylogue run materialize` when raw archive content is already current and only derived products need rebuilding.
3. Check `polylogue products status` before trusting product coverage or freshness.
4. Prefer durable products over re-deriving semantics from raw transcripts when a product already exists for the question at hand.
5. Use `polylogue products export` when a downstream consumer needs a stable, generic archive-product bundle.
6. Keep provider, tag, path, action, and tool filters in the query layer instead of post-filtering exported markdown or JSON by hand.
7. If you are debugging Polylogue itself, work in `/realm/project/polylogue`. Otherwise stay at the packaged boundary.

## Common Commands

```bash
# Refresh the full archive pipeline
polylogue run all

# Refresh derived read models only
polylogue run materialize

# Check whether products are materially ready to use
polylogue products status

# Inspect durable products directly
polylogue products profiles --limit 10
polylogue products phases --limit 10
polylogue products threads --limit 10
polylogue products work-events --limit 10
polylogue products day-summaries --limit 10
polylogue products week-summaries --limit 10

# Query-first archive search with archive-native filters
polylogue --provider claude-ai --since "last week" stats --by provider
polylogue "duckdb scaffold" --provider claude-code --format json --list --limit 20

# Export a stable downstream bundle when another system should consume products
polylogue products export --help
```

## Python API

```python
from polylogue import Polylogue
from polylogue.archive_products import (
    DaySessionSummaryProductQuery,
    SessionPhaseProductQuery,
    SessionProfileProductQuery,
)
import asyncio


async def main() -> None:
    async with Polylogue() as archive:
        status = await archive.get_session_product_status()
        print(status)

        profiles = await archive.list_session_profile_products(
            SessionProfileProductQuery(
                provider="claude-code",
                session_date_since="2026-03-01",
                session_date_until="2026-03-31",
                limit=25,
            )
        )
        phases = await archive.list_session_phase_products(
            SessionPhaseProductQuery(provider="claude-code", kind="execution", limit=25)
        )
        days = await archive.list_day_session_summary_products(
            DaySessionSummaryProductQuery(provider="claude-code", since="2026-03-01")
        )

        print(len(profiles), len(phases), len(days))


asyncio.run(main())
```

## Notes

- Durable products include profiles, phases, work events, threads, day summaries, week summaries, provider analytics, and archive debt/readiness surfaces.
- `SessionWorkEventProduct` and `SessionPhaseProduct` expose timestamped timeline rows and are usually the right substrate for session chronology.
- `SessionProfileProduct` exposes stable session semantics such as `canonical_session_date`, `engaged_minutes`, `repo_names`, and `repo_paths`.
- The CLI is query-first, but durable products are the preferred surface for downstream consumers that need stable semantics instead of transcript spelunking.
