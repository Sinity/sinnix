## Cross-Project Tooling

### AI Agent Configs

- **Claude**: `dots/claude/` — CLAUDE.md read natively; other agents get flat renders via `render-agents` on HM activation and on `dots/claude/` file changes (systemd path unit).
- **Codex**: `dots/codex/config.toml`, skills overlay at `dots/codex/skills/` (`.system/` holds Codex-only system skills).
- **MCP Servers**: Polylogue/Context7/GitHub are the default coding-agent substrate. Browser automation MCPs are opt-in/manual so ordinary agent sessions do not multiply heavyweight browser-control daemons. Registry source of truth: `modules/features/dev/mcp-servers.nix`.
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
