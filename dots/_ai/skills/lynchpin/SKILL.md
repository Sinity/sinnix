---
name: lynchpin
description: Query or develop Lynchpin evidence sources, materialization, DuckDB substrate generations, graphs, analyses, Chisel reports, Polylogue boundaries, and MCP evidence products.
---

# Lynchpin

Lynchpin joins heterogeneous evidence into canonical products, a coherent
DuckDB read model, graphs, analyses, and reports. Missing coverage is not zero
activity, association is not causation, and generated narrative is not source
evidence.

## Querying

Use the MCP readiness and table/schema tools before analytical claims. Keep one
`refresh_id` per coherent query and cite product, timeframe, denominator,
method, and degraded coverage. The MCP is read-only except for explicitly
documented maintenance actions, which are dry-run first.

## Materialization

Materialization uses a typed product catalog and convergence planner. Declared
AgentCTL operations preview the plan, execute individual product nodes,
promote a complete substrate generation, or run the convergence sequence.
Discover the exact operation names and requirements with
`agentctl project operations lynchpin`, then run the declared route. Do not
copy an operation name from this skill into a command without checking the
descriptor first.

Promotion is atomic and generation-coherent. Full promotion rebuilds all
history; incremental promotion uses current canonical products and freshness
logic. Chisel builds the configured cross-project report portfolio.

## Boundaries

AI-session ingestion and interpretation belong to Polylogue. Lynchpin does not
read its archives, products or live status. Git and Chisel may inspect its source
repository like any registered project.

Lint, type checks, and tests run as Lynchpin's declared operations
(`agentctl job start lynchpin lint` or `check`), never inside an agent's own
process; `agentctl project operations lynchpin` lists the rest. Commit verified work directly
to `master` unless an active workflow says to hold, and keep generated private
products, databases, receipts, and captures out of Git.
