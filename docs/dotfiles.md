# Dotfile Coverage

This repository keeps all user-editable configuration under `dots/` and links
them into `$HOME` with Home Manager out-of-store symlinks (`dotsRepoPath` +
`mkOutOfStoreSymlink`). Editing a file in `dots/` takes effect immediately – no
flake rebuild is needed because the symlinks point directly into the checkout.

## Managed dot directories

| Dot dir        | Primary consumer(s)                              | Notes |
|----------------|--------------------------------------------------|-------|
| `audacity/`    | `user/desktop/apps.nix` (`xdg.configFile`)       | UI settings for the audio editor |
| `claude/`      | `user/dev/core.nix` (`linkNeovimConfig`)         | Shared with `.claude` and CLAUDE CLI |
| `codex/`       | `user/dev/tools.nix` (`.codex/config.toml`)      | Codex CLI / MCP client config |
| `gemini/`      | `user/dev/tools.nix` (`.gemini/settings.json`)   | Gemini CLI defaults |
| `Kvantum/`     | `user/desktop/apps.nix` (Qt style)               | Kvantum theme synchronized with Stylix |
| `marimo/`      | `user/dev/tools.nix` (`marimo/marimo.toml`)      | MCP-enabled Marimo notebooks |
| `nvim/`        | `user/dev/core.nix` (linked to `.config/nvim`)   | Neovim configuration |
| `opencode/`    | `user/dev/tools.nix` (`opencode/opencode.json`)  | OpenCode client |
| `qt5ct/`, `qt6ct/` | `user/desktop/apps.nix` (`xdg.configFile`)   | Qt control centre themes |
| `qutebrowser/` | `user/desktop/qutebrowser.nix` (config + scripts)| Config, userstyles, userscripts |
| `ripgrep-all/` | `user/dev/tools.nix`                             | Search tool defaults |
| `sqlitebrowser/` | `user/dev/tools.nix`                           | DB Browser GUI settings |
| `transmission/`| `user/desktop/apps.nix`                          | GTK client preferences |
| `vscode/`      | `user/dev/vscode.nix` (settings/keybindings/MCP) | VS Code profile |
| `yazi/`        | `user/desktop/apps.nix` (keymap/opener)          | File manager bindings |
| `zed/`         | `user/dev/zed.nix` (settings/keymap)             | Zed editor profile |

All of these modules use out-of-store symlinks, so edits in `dots/` propagate
instantly. Apart from the dotfiles above, Neovim and Claude also get linked in
`user/dev/core.nix`, and qutebrowser’s userscripts are sourced completely from
`dots/qutebrowser`.

## Configs intentionally kept in Nix

Some UI stacks stay in modules because they depend on Stylix values, systemd
units, or generated scripts:

- Hyprland: declarative bindings/rules in `user/desktop/hyprland*.nix`.
- Waybar: templated CSS/JSON tied to system packages in `user/desktop/waybar.nix`.
- Fnott/Clipse/Tofi: configured alongside services inside `user/desktop/apps.nix`.

These can move to `dots/` later, but keeping them in Nix lets us share colors
and automatically restart the right daemons on changes.
