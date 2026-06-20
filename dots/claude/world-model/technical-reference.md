## Cross-Project Tooling

### AI Agent Configs

- **Claude**: `dots/claude/` — CLAUDE.md read natively; other agents get flat renders via `render-agents` on HM activation and on `dots/claude/` file changes (systemd path unit).
- **Codex**: `dots/codex/config.toml`, skills overlay at `dots/codex/skills/` (`.system/` holds Codex-only system skills).
- **MCP Servers**: Serena, Codebase Memory, Polylogue, Context7, GitHub, Lynchpin, live Chrome DevTools, private Chrome DevTools, and visible private Chrome DevTools are the default coding-agent substrate. Registry source of truth: `flake/data/mcp-registry.nix`; Nix/HM wiring lives in `modules/features/dev/mcp-servers.nix`.
- **Browser/Desktop/Terminal Control**: "your browser" means an agent-private Chrome via `chrome-devtools-private` or `chrome-devtools-private-visible`; "my browser" means the user's live Chrome profile via `chrome-devtools` on `127.0.0.1:9222`; "desktop/window/screen" means Hyprland/screenshot helpers; "terminal" means Kitty remote control. Stable helper commands are `sinnix-chrome-control`, `sinnix-hypr-control`, `sinnix-keyboard-control`, `sinnix-kitty-control`, `sinnix-screenshot-control`, and `sinnix-agent-control-status`; load the `desktop-control-plane` skill for detailed recipes.
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
