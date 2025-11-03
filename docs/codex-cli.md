# Codex CLI MCP configuration

Codex' CLI config lives under `dots/codex/config.toml`. Home Manager now links
this file to `~/.codex/config.toml`, so updates to the dotfile are picked up on
the next `home-manager switch`. If you prefer to experiment ad-hoc, copy the
rendered file elsewhere first so you can diff and merge changes back.

## Deploying the config

The managed link is created automatically, but if you ever need to repair it:

```
ln -sfv /realm/sinnix/dots/codex/config.toml ~/.codex/config.toml
```

The template contains:

- `model = "gpt-5-codex"` and `model_reasoning_effort = "high"`
- The shared trusted project list
- MCP servers aligned with VS Code: GitHub (expects `GITHUB_TOKEN`), a local
  PostgreSQL bridge (no auth required, talks to the socket at
  `/run/postgresql`), Playwright, Context7, Firecrawl (with
  `FIRECRAWL_API_KEY` forwarded), plus a local Qdrant server executed via the
  `~/.local/bin/mcp-qdrant` wrapper.
- `features.rmcp_client = true` for hosted MCP OAuth flows

The shell profile now sources the agenix export snippet automatically; use the
`load-secrets` alias any time you want to refresh the values mid-session.

## Verifying the wiring

1. `codex mcp list` — all entries should show `Status   enabled`.
2. For hosted MCPs (`github` and other OAuth-backed remotes) run
   `codex mcp login <name>` to finish authentication.
3. Launch Codex and confirm the servers appear in the CLI's tool picker. Try
   `codex mcp call postgres-local list-tables` and
   `codex mcp call qdrant list-collections` to verify connectivity.
