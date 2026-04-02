## Dotfiles Management

Dotfiles in `dots/` directory:

- **Mechanism**: Home Manager out-of-store symlinks (`mkOutOfStoreSymlink`)
- **Benefit**: Edits propagate instantly without rebuild
- **Helper**: Use `mkDotsFileFor config` for consistent linking

### Key Paths

| Directory      | Target                  | Purpose                                   |
| -------------- | ----------------------- | ----------------------------------------- |
| `claude/`      | `~/.config/claude`      | Claude Code config                        |
| `codex/`       | `~/.codex`              | Codex CLI config + skills + global AGENTS |
| `gemini/`      | `~/.config/gemini`      | Gemini CLI config                         |
| `nvim/`        | `~/.config/nvim`        | Neovim LazyVim                            |
| `vscode/User/` | VS Code settings        | Settings, keybindings, snippets           |
| `zed/`         | `~/.config/zed`         | Zed editor config                         |
| `qutebrowser/` | `~/.config/qutebrowser` | Browser config + userscripts              |
| `zsh/`         | Various                 | Zsh aliases, functions                    |
| `tmux/`        | `~/.config/tmux`        | Terminal multiplexer                      |
| `yazi/`        | `~/.config/yazi`        | File manager                              |
| `taskwarrior/` | `~/.config/task`        | Task management                           |
| `timewarrior/` | `~/.config/timewarrior` | Time tracking                             |

### Application Configs (less frequently edited)

`audacity/`, `Kvantum/`, `marimo/`, `opencode/`, `qt5ct/`, `qt6ct/`, `ripgrep-all/`, `serena/`, `sqlitebrowser/`, `transmission/`

### Codex AGENTS Include Handling

- Codex does not expand `@path` includes in `AGENTS.md` natively.
- Canonical source is `CLAUDE.md`; `scripts/render-agents` renders `CLAUDE.md` (with recursive transclusions) into generated `AGENTS.md`.
- `~/.local/bin/codex` wrapper auto-runs this renderer on launch for the working tree (`$PWD`/`--cd`) and parent dirs that contain `CLAUDE.md`.
- Shared skill sources live in `dots/_ai/skills/`.
- `dots/codex/skills/` and `dots/claude/skills/` are agent-facing overlay trees, mostly symlinks into `dots/_ai/skills/`; Codex-only system skills remain in `dots/codex/skills/.system/`.
- Gemini user skills live at `~/.gemini/skills`, linked directly to `dots/_ai/skills/`.
- Forge user skills live at `~/forge/skills`, linked directly to `dots/_ai/skills/`.
- `scripts/normalize-agent-projects /realm/project` performs one-shot normalization across repos (promotes/creates `CLAUDE.md`, regenerates `AGENTS.md`, removes legacy overrides, updates `.gitignore`).
- `scripts/verify-agent-topology /realm/project` is the read-only topology/sync verifier used for audits and CI checks.
- Global always-on Codex guidance is `~/.codex/AGENTS.md`, rendered from `~/.config/claude/CLAUDE.md` during activation and before Codex launch.
