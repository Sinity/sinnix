# Codex CLI MCP configuration

Codex' CLI config lives under `dots/codex/config.toml`, and skills are checked
into `dots/codex/skills`. Home Manager links both to `~/.codex`, so updates to
the dotfiles are picked up on the next `home-manager switch`. If you prefer to
experiment ad-hoc, copy the rendered files elsewhere first so you can diff and
merge changes back.

## Deploying the config

The managed link is created automatically, but if you ever need to repair it:

```
ln -sfv /realm/sinnix/dots/codex/config.toml ~/.codex/config.toml
ln -sfn /realm/sinnix/dots/codex/skills ~/.codex/skills
```

The template contains:

- `model = "gpt-5-codex"` and `model_reasoning_effort = "high"`
- The shared trusted project list
- `dots/codex/skills` linked into `~/.codex/skills`
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

## Context7 workflow

The Context7 MCP server exposes two tools:

- `resolve-library-id` – maps human names to Context7 IDs such as `/vercel/next.js`
- `get-library-docs` – fetches focused documentation for a given ID

Both read credentials from `CONTEXT7_API_KEY`, which is exported automatically by
the agenix secrets profile. To discover a project and grab its docs:

```
codex mcp call context7 resolve-library-id --arg libraryName="nextjs"
codex mcp call context7 get-library-docs \
  --arg context7CompatibleLibraryID="/vercel/next.js" \
  --arg topic="routing"
```

The resolve step accepts any fuzzy library name and returns a list of IDs. Pass
whichever `/org/repo` slug you need into `get-library-docs` (optionally with a
`topic` or `tokens` override) and Codex will load the docs directly into the
conversation—no separate CLI wrapper required.
