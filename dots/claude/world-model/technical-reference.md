## Cross-Project Tooling

### AI Agent Configs

- **Claude**: `dots/claude/` — CLAUDE.md read natively; other agents get flat renders via `render-agents` on HM activation and on `dots/claude/` file changes (systemd path unit).
- **Codex**: `dots/codex/config.toml`, skills overlay at `dots/codex/skills/` (`.system/` holds Codex-only system skills).
- **MCP Servers**: The registry source of truth is `flake/data/mcp-registry.nix`; Nix/HM wiring lives in `modules/features/dev/mcp-servers.nix`. Plain `claude`/`codex` use the full non-browser profile: GitHub, Context7, Polylogue, Lynchpin, Serena, and Codebase Memory. `claude-lean`/`codex-lean` keep GitHub, Context7, and Polylogue only. `claude-browser`/`codex-browser` add the Chrome DevTools MCP tier as an explicit superset.
- **Browser/Desktop/Terminal Control**: "your browser" means `sinnix-chrome-control --target private` unless the user explicitly asks for the real browser; "my browser" means `sinnix-chrome-control --target live` against the user's Chrome profile on `127.0.0.1:9222`; "desktop/window/screen" means Hyprland/screenshot helpers; "terminal" means Kitty remote control. Stable helper commands are `sinnix-chrome-control`, `sinnix-hypr-control`, `sinnix-keyboard-control`, `sinnix-kitty-control`, `sinnix-screenshot-control`, and `sinnix-agent-status`; load the `desktop-control-plane` skill for detailed recipes. Use browser MCPs only via the explicit browser agent profile when shell CDP primitives are insufficient.
- **Control vs Evidence**: DevTools/Hyprland/Kitty helpers are the live action plane. Polylogue is AI transcript/session recall, Lynchpin is cross-source analysis over chats/git/ActivityWatch/shell/health/telemetry, and Sinnix observability (`/etc/sinnix/runtime-inventory.json`, `sinnix-observe`, `/realm/data/captures/**`) is raw host/runtime evidence.
- **Context7**: Documentation discovery via `resolve-library-id` and `query-docs`.

### Desktop Environment

- **WM**: Hyprland (Wayland compositor)
- **Browser**: qutebrowser (keyboard-driven)
- **Terminal**: foot/kitty
- **Launcher**: tofi

### Dotfile Pattern

All dotfiles in `dots/` use Home Manager out-of-store symlinks (`mkOutOfStoreSymlink`). Edits propagate instantly without rebuild.

---

**Project-specific details** (module structure, patterns, workflows) are in each project's CLAUDE.md:

- sinnix → `/realm/project/sinnix/CLAUDE.md`
- sinex → `/realm/project/sinex/CLAUDE.md`
- lynchpin → see project docs
