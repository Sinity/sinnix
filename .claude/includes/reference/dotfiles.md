## Dotfiles Management

Dotfiles in `dots/` directory:

- **Mechanism**: Home Manager out-of-store symlinks (`mkOutOfStoreSymlink`)
- **Benefit**: Edits propagate instantly without rebuild
- **Key paths**:
  - `dots/claude/` → `~/.config/claude` (Claude Code config)
  - `dots/codex/` → `~/.config/codex` (Codex CLI config)
  - `dots/nvim/` → `~/.config/nvim` (Neovim LazyVim)
  - `dots/vscode/User/` → VS Code settings
  - `dots/qutebrowser/` → Qutebrowser config + userscripts
  - `dots/hyprland/` → Hyprland config (some declarative in modules)
