# Dotfile Coverage

This repository keeps all user-editable configuration under `dots/` and links
them into `$HOME` with Home Manager out-of-store symlinks (`dotsRepoPath` +
`mkOutOfStoreSymlink`). Editing a file in `dots/` takes effect immediately – no
flake rebuild is needed because the symlinks point directly into the checkout.

## Managed dot directories

| Dot dir        | Primary consumer(s)                              | Notes |
|----------------|--------------------------------------------------|-------|
| `audacity/`    | `modules/features/desktop/common-apps.nix` (`xdg.configFile`) | UI settings for the audio editor |
| `claude/`      | `modules/features/dev/core/base.nix` (`linkClaudeConfig`)             | Shared with `.claude` and CLAUDE CLI |
| `codex/`       | `modules/features/dev/utilities.nix` (`.codex/config.toml`, `.codex/skills`) | Codex CLI config + skills |
| `gemini/`      | `modules/features/dev/utilities.nix` (`.gemini/settings.json`)         | Gemini CLI defaults |
| `Kvantum/`     | `modules/features/desktop/common-apps.nix` (Qt style)          | Kvantum theme synchronized with Stylix |
| `marimo/`      | `modules/features/dev/utilities.nix` (`marimo/marimo.toml`)            | MCP-enabled Marimo notebooks |
| `nvim/`        | `modules/features/dev/core/base.nix` (linked to `.config/nvim`)        | Neovim configuration |
| `opencode/`    | `modules/features/dev/utilities.nix` (`opencode/opencode.json`)        | OpenCode client |
| `qt5ct/`, `qt6ct/` | `modules/features/desktop/common-apps.nix` (`xdg.configFile`) | Qt control centre themes |
| `qutebrowser/` | `modules/features/desktop/browser.nix` (config + scripts)      | Config, userstyles, userscripts |
| `ripgrep-all/` | `modules/features/dev/utilities.nix`                                   | Search tool defaults |
| `sqlitebrowser/` | `modules/features/dev/utilities.nix`                                 | DB Browser GUI settings |
| `transmission/`| `modules/features/desktop/common-apps.nix`                     | GTK client preferences |
| `vscode/`      | `modules/features/dev/vscode.nix` (settings/keybindings/MCP)           | VS Code profile |
| `yazi/`        | `modules/features/desktop/common-apps.nix` (keymap/opener)     | File manager bindings |
| `zed/`         | `modules/features/dev/zed.nix` (settings/keymap)                       | Zed editor profile |

All of these modules use out-of-store symlinks, so edits in `dots/` propagate
instantly. Apart from the dotfiles above, Neovim and Claude also get linked in
`modules/features/dev/core/base.nix`, and qutebrowser’s userscripts are sourced
completely from `dots/qutebrowser`.

## Configs intentionally kept in Nix

Some UI stacks stay in modules because they depend on Stylix values, systemd
units, or generated scripts:

- Hyprland: declarative bindings/rules in `modules/features/desktop/hyprland/*`.
- Waybar: templated CSS/JSON tied to system packages in `modules/features/desktop/waybar.nix`.
- Fnott/Clipse/Tofi: configured alongside services inside `modules/features/desktop/fnott.nix`,
  `modules/features/desktop/clipse.nix`, and `modules/features/desktop/tofi.nix`.

These can move to `dots/` later, but keeping them in Nix lets us share colors
and automatically restart the right daemons on changes.
