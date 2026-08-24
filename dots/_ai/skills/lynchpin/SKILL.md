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

Current materialization is procedural. The AgentCTL operations wrap the
existing CLI; the planned typed DAG and per-node executor are not current
architecture. Discover the exact descriptor with `agentctl project operations
lynchpin`. The registered routes are:

```text
agentctl job start lynchpin check
agentctl job start lynchpin materialize_plan
agentctl job start lynchpin promote_incremental
agentctl job start lynchpin promote_full
agentctl job start lynchpin chisel
```

Promotion is atomic and generation-coherent. Full promotion rebuilds all
history; incremental promotion uses current canonical products and freshness
logic. Chisel builds the configured cross-project report portfolio.

## Boundaries

Polylogue owns AI-session ingestion and archive-native inference. Lynchpin owns
cross-source promotion and analysis over stable products. Never scrape
Polylogue's disposable `.cache/verify` receipts; consume a declared export or
mark that source unavailable.

Short checks run in the Nix devshell (`just lint`, `just typecheck`, `pytest`,
`just check`). Heavy standard work uses AgentCTL. Commit verified work directly
to `master` unless an active workflow says to hold, and keep generated private
products, databases, receipts, and captures out of Git.
