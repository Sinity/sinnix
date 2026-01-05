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
- `mic-status`/`mic-toggle` – show and toggle microphone mute state.
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
- `combine-files` & `combine-files-batch.sh` – merge arbitrary files into a
  single Markdown/text artifact for ingestion.

## MCP + data access

- `mcp-postgres.py`, `mcp-qdrant.py`, `mcp-sqlite.py` – expose local datasources
  to MCP-capable agents (Codex, Claude Desktop, etc.). `modules/features/dev/utilities.nix`
  ships thin wrappers (`mcp-<name>`) in `~/.local/bin`.

## Developer tooling

- `audit-package-usage` – inspects shell history, desktop files, and units to
  flag unused packages vs. configured ones.
- `perf-scan` – system diagnostics/benchmark runner with bundled dependencies.
- `pre-commit-check` – runs `nix flake check`, warns about tmpfiles/services,
  and ensures staged `.nix` files are tracked.
- `setup-git-hooks` – installs repo-specific pre-commit hooks.

## Misc

- `audio-output-status`, `mic-status`, etc. are used by Waybar modules (see
  `modules/features/desktop/waybar.nix`).
- `toggle-audio-output` and `mic-toggle` are bound via Hyprland keybindings.

Scripts that manipulate Kitty or Hyprland rely on the remote control hints
described in `AGENTS.md` – in particular, they honour `KITTY_LISTEN_ON` so they
can be driven from Codex sessions without forking new windows unnecessarily.
