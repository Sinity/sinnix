# Script Catalog

All helper scripts live under `scripts/` and are referenced by Hyprland bindings,
Waybar widgets, or CLI aliases. Most are Bash with `set -euo pipefail`; longer
automations are in Python. The Hyprland module links the ones marked with `*`
into `~/.local/bin` automatically.

## Desktop + audio

- `audio-output-status`* – emits Waybar JSON for the active PipeWire sink,
  including icon/class heuristics.
- `toggle-audio-output`* – cycles between common sinks (speakers/bluetooth/etc.)
  and pokes Waybar via RTMIN+12.
- `mic-status`/`mic-toggle` – show and toggle microphone mute state
  (archived – functionality now in Waybar module).
- `kitty-hypr-nav`* – Hyprland focus helper used by arrow-key bindings.
- `kitty-grid`* – Python grid arranger that can spawn kitty panes through the
  `KITTY_LISTEN_ON` socket and tile them via `hyprctl`.
- `toggle-scratch`* – generic scratchpad spawner for Hyprland, reading configs
  under `~/.config/scratchpads`.

## Knowledgebase logging

- `rawlog`* – append a timestamped entry to `/realm/project/knowledgebase/logs.raw-log.md`.
- `rawlog-capture`/`rawlog-loop`* – gum-powered TUI logger that keeps the kitty
  scratchpad hot.
- `kb-capture`* – capture clipboard/text snippets into the knowledgebase.
- `combine-files`* – merge arbitrary files into a single Markdown/text artifact
  for ingestion (batch variant archived in `archive/scripts/`).

## MCP + data access

- `mcp-qdrant.py` – exposes Qdrant vector store to MCP-capable agents.
  `modules/features/dev/utilities.nix` ships thin wrappers (`mcp-<name>`) in
  `~/.local/bin`, including `mcp-context7`, `mcp-firecrawl`, and `mcp-playwright`
  for shared MCP wiring. Archived: `mcp-postgres.py`, `mcp-sqlite.py`.

## AI tooling

- `ai` – pick, show, or launch shared prompts/agents from `dots/ai` (supports
  `codex exec`, clipboard, or editor workflows).

## Developer tooling

- `perf-scan` – system diagnostics/benchmark runner with bundled dependencies.
- Archived: `audit-package-usage`, `pre-commit-check`, `setup-git-hooks` (moved
  to `archive/scripts/` – functionality superseded by devenv hooks).

## Misc

- `audio-output-status` and `toggle-audio-output` are used by Waybar modules and
  Hyprland keybindings (see `modules/features/desktop/waybar.nix`).

Scripts that manipulate Kitty or Hyprland rely on the remote control hints
described in `AGENTS.md` – in particular, they honour `KITTY_LISTEN_ON` so they
can be driven from Codex sessions without forking new windows unnecessarily.
