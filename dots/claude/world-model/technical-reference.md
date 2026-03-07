## Cross-Project Tooling

### Codex CLI

- **Config**: `dots/codex/config.toml`, shared skills in `dots/agent-skills`
- **MCP Servers**: GitHub, Context7 (singleton HTTP), Firecrawl
- **Context7**: Documentation discovery via `resolve-library-id` and `query-docs`

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
