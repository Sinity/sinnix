---
name: lynchpin
description: Query the Lynchpin substrate via MCP — 28 tools over DuckDB. Evidence graph, velocity, correlations, closure chains, overlap edges, PR reviews, kind audit, refactor detection, durability, anomalies, calendar.
---

# Lynchpin substrate skill

Use `mcp-lynchpin` to query Lynchpin's deterministic evidence substrate
(DuckDB-backed, 28 MCP tools, 6/6 sources healthy, trustworthy=true).

## Substrate-First Principle (CRITICAL)

**Before making claims about "what happened" in any project**, query the
substrate first. `substrate_readiness_report` tells you if the substrate is
trustworthy. `velocity_narrative` gives the high-level story. Then drill into
specific tools for evidence. Never guess — every claim needs a substrate query
backing it.

## Quick orientation

- **What's the state?** → `substrate_readiness_report` (one-stop health)
- **What shipped?** → `velocity_narrative` (auto-summary text)
- **How fast?** → `velocity_series` (daily + rolling avg + cumulative)
- **Symbol-level?** → `symbol_velocity` (added/modified/renamed per day)
- **What survived?** → `work_package_durability` (symbol survival at HEAD)
- **Anomalies?** → `source_anomalies` (commits without AI, AI without commits, focus without git)
- **PR quality?** → `frontier_slo` (merge time P50/P75, friction signals)
- **Refactors?** → `refactor_candidates` (renamed symbols, similarity matches)
- **Hotspots?** → `file_hotspots` (most-changed files/directories)
- **When?** → `temporal_rhythm` (time-of-day × day-of-week patterns)
- **Cross-project?** → `project_relationship_graph` (shared edges between projects)
- **AI attribution?** → `ai_attribution_backfill` (commit→AI matching, dry-run first)
- **Kind quality?** → `kind_audit` (polylogue-vs-lynchpin agreement rates)
- **Confidence?** → `substrate_confidence_matrix` + `evidence_confidence`
- **Compare snapshots?** → `context_pack_diff` (cross-refresh deltas)
- **Gaps?** → `substrate_gap_draft` (tracker-issue draft for unhealthy sources)
- **Calendar?** → `calendar_events` (returns [] until upstream ingestion)

This MCP is **read-only** for queries. `ai_attribution_backfill` is the one
write tool — always use `dry_run=True` first. For running the full current-state
pipeline use `python -m lynchpin.scripts.current_state`.

## When to use this skill

- "What did I ship last week / month?" — `project_day_correlations` over the window; each row carries git, AI-session, focus, shell, and GitHub dimensions side by side.
- "Which commits did this AI session touch?" — `file_overlap_edges` or `symbol_overlap_edges` filtered by `we_refresh_id`.
- "Are there open issues with no closure chain?" — `closure_chain_walks` with `min_chain_depth=0`.
- "PR review friction signals across the codebase" — `pr_review_rows(only_with_friction=true)` from the M.7 topology.
- "What evidence do I have for project X on date Y?" — `load_evidence_graph_summary` + `query_substrate` on `evidence_nodes` filtered by project/date.
- Ad-hoc analysis — `query_substrate(sql)` for any read-only SELECT over the substrate schema.

## Available tools

```
query_substrate(sql, parameters?, max_rows?=1000)
  Direct SELECT against the DuckDB substrate. DDL and DML are rejected.
  Use list_substrate_tables() first if schema is uncertain.

list_substrate_tables()
  Returns table names and column definitions. Start here for ad-hoc queries.

list_evidence_graph_builds(start?, end?, mode?)
  What graph builds are materialized — refresh_id, generated_at, node/edge
  counts. Use to check freshness before querying graph products.

load_evidence_graph_summary(refresh_id? | start?+end?)
  Node and edge counts broken down by kind. Useful for understanding graph
  coverage before running targeted queries.

project_day_correlations(start, end, projects?, include_github_context?)
  Per-project per-day rows preserving source dimensions: commit_count,
  churn, ai_session_count, ai_messages, focus_minutes, shell_commands,
  github_issues_opened, github_prs_merged, and more. Does NOT collapse
  these into a single velocity scalar — inspect each column.

closure_chain_walks(start?, end?, projects?, min_chain_depth?, max_depth?)
  Recursive github_issue → PR → commit traversal. Returns chain rows with
  depth, commit shas, and closure timestamps. min_chain_depth=0 surfaces
  orphaned issues with no downstream closure evidence.

file_overlap_edges(we_refresh_id?, start?, end?, projects?, min_overlap?)
  AI work-event ↔ git commit join on shared file paths. Identifies which
  coding-agent sessions correspond to which commits based on file-level
  co-occurrence within a temporal window.

symbol_overlap_edges(we_refresh_id?, start?, end?, projects?, min_overlap?)
  Same as file_overlap_edges but joined on symbol (function/class) names
  extracted from diffs. Higher precision, lower recall than file overlap.

pr_review_rows(start?, end?, projects?, only_with_friction?)
  M.7 PR-review thread topology. Friction signals: review_round_count > 1,
  change_requested flag, long review-to-merge lag. Use only_with_friction=true
  to filter to PRs that had re-review cycles.
```

## Substrate freshness

The substrate is populated by the refresh DAG (`python -m lynchpin.analysis refresh`
or Arc 2.6 incremental). Check `list_evidence_graph_builds()` — `generated_at`
is the freshness signal. A stale substrate (>1 day old) may not reflect recent
commits or AI sessions.

## Query patterns

```sql
-- Active projects this week by git + AI session evidence
SELECT project, SUM(commit_count) AS commits, SUM(ai_session_count) AS ai_sessions
FROM project_day_correlations
WHERE day >= current_date - INTERVAL 7 DAYS
GROUP BY project ORDER BY commits DESC;

-- Open issues with no closure chain (orphaned)
SELECT issue_id, title, opened_at
FROM closure_chain_walks
WHERE min_chain_depth = 0 AND closed_at IS NULL;

-- File overlap: which sessions touched lynchpin/composite?
SELECT we_refresh_id, session_start, file_path, commit_sha
FROM file_overlap_edges
WHERE file_path LIKE '%lynchpin/composite%'
ORDER BY session_start DESC LIMIT 20;
```

## When NOT to use this skill

- Authoring new analysis or running the full current-state pipeline — use the CLI directly.
- Polylogue archive queries (conversation search, session profiles, cost rollups) — use `mcp-polylogue` instead.
- Editing Lynchpin source code — this MCP is read-only.
- If `list_evidence_graph_builds()` returns no builds, the substrate is empty; run the refresh DAG first.
