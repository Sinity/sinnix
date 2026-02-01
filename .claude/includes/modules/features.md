## Features (User-Facing)

Organized by domain under `modules/features/`:

### CLI (`features/cli/`)
- **core.nix**: Core CLI environment (git, taskwarrior, gnupg)
- **task-tracking.nix**: Taskwarrior/Timewarrior integration

### System (`features/system/`)
- **nix-ld.nix**: Dynamic linker for running unpatched binaries (AppImages, proprietary software)

### Desktop (`features/desktop/`)
- **activitywatch.nix**: Activity tracking daemon + web UI
- **audio.nix**: PipeWire, audio devices, routing (moved from top-level)
- **base.nix**: Core desktop services (clipboard, notifications, launcher)
- **browser.nix**: Qutebrowser config, userscripts, profiles
- **common-apps.nix**: GUI utilities (file manager, image viewer, etc.)
- **crypto.nix**: Cryptocurrency tools (Monero)
- **gaming.nix**: Steam, game launchers
- **hyprland/**: Window manager config (bindings, rules, lock screen)
- **media.nix**: mpv, audio/video tools, codecs
- **mime.nix**: File associations, default applications
- **reboot-notifier.nix**: Systemd reboot notifications
- **storage.nix**: File managers, disk usage tools (distinct from top-level storage.nix which handles mounts)
- **terminal.nix**: Terminal emulators (foot, kitty)
- **theming.nix**: Stylix integration, GTK/Qt themes
- **ui.nix**: Fonts, cursor themes, Wayland base environment (moved from top-level)
- **waybar.nix**: Status bar configuration

### Dev (`features/dev/`)
- **editors.nix**: VS Code, Zed (with subFeatures for each)
- **git.nix**: Git config, delta, aliases
- **languages.nix**: Language toolchains (Python, Rust, Node, etc.)
- **mcp-servers.nix**: Model Context Protocol server configs
- **shell.nix**: Unified shell environment with subFeatures:
  - `zsh`: Zsh + oh-my-zsh + syntax highlighting
  - `prompt`: Starship + Atuin + Zoxide + FZF
  - `utilities`: CLI tools (bat, eza, fd, ripgrep) + config linking
  - `tmux`: Terminal multiplexer

**Rule**: If users **directly interact** with it, it's a feature.
