## Dotfiles Management

Dotfiles in `dots/` directory:

- **Mechanism**: Home Manager out-of-store symlinks (`mkOutOfStoreSymlink`)
- **Benefit**: Edits propagate instantly without rebuild
- **Helper**: Use `mkDotsFile` or `mkDotsFileFor config` for consistent linking

### Key Paths

| Directory      | Target                  | Purpose                         |
| -------------- | ----------------------- | ------------------------------- |
| `claude/`      | `~/.config/claude`      | Claude Code config              |
| `codex/`       | `~/.config/codex`       | Codex CLI config                |
| `gemini/`      | `~/.config/gemini`      | Gemini CLI config               |
| `nvim/`        | `~/.config/nvim`        | Neovim LazyVim                  |
| `vscode/User/` | VS Code settings        | Settings, keybindings, snippets |
| `zed/`         | `~/.config/zed`         | Zed editor config               |
| `qutebrowser/` | `~/.config/qutebrowser` | Browser config + userscripts    |
| `zsh/`         | Various                 | Zsh aliases, functions          |
| `tmux/`        | `~/.config/tmux`        | Terminal multiplexer            |
| `yazi/`        | `~/.config/yazi`        | File manager                    |
| `taskwarrior/` | `~/.config/task`        | Task management                 |
| `timewarrior/` | `~/.config/timewarrior` | Time tracking                   |

### Application Configs (less frequently edited)

`audacity/`, `Kvantum/`, `marimo/`, `opencode/`, `qt5ct/`, `qt6ct/`, `ripgrep-all/`, `serena/`, `sqlitebrowser/`, `transmission/`
