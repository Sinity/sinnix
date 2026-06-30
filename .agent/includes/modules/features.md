## Features (User-Facing)

Organized by domain under `modules/features/`:

### CLI (`features/cli/`)

- **core.nix**: Core CLI environment (git, taskwarrior, gnupg)
- **aichat.nix**: Terminal AI chat client wired to the local Ollama hub
- **image-tools.nix**: Image/media CLI utilities
- **polylogue.nix**: Polylogue CLI integration
- **task-tracking.nix**: Taskwarrior/Timewarrior integration
- **yt-polisher.nix**: YouTube media workflow helpers

### System (`features/system/`)

- **nix-ld.nix**: Dynamic linker for running unpatched binaries (AppImages, proprietary software)

### Desktop (`features/desktop/`)

- **activitywatch.nix**: Activity tracking daemon + web UI
- **audio.nix**: PipeWire, audio devices, routing (moved from top-level)
- **audio-capture.nix**: Local audio segmentation/transcription capture controls
- **agent-verify-timer.nix**: Periodic health check for configured coding-agent surfaces
- **base.nix**: Core desktop services (clipboard + applets; launcher/notifications/OSD are Noctalia's)
- **browser.nix**: Qutebrowser config, userscripts, profiles
- **common-apps.nix**: GUI utilities (file manager, image viewer, etc.)
- **gaming.nix**: Steam, game launchers
- **hyprland-animations.nix**: Optional Hyprland animation policy
- **hyprland/**: Window manager config (bindings, rules, idle/DPMS — lock UI is Noctalia)
- **noctalia.nix**: Noctalia Wayland shell — bar, launcher, notifications, lock, OSD, wallpaper, and live Material-You color authority; plugins (polkit-agent, screen-recorder, nvibrant, model-usage, keybind-cheatsheet, timer, display-settings, linux-wallpaperengine)
- **media.nix**: mpv, audio/video tools, codecs
- **mime.nix**: File associations, default applications
- **reboot-notifier.nix**: Systemd reboot notifications
- **storage.nix**: File managers, disk usage tools (distinct from top-level storage.nix which handles mounts)
- **terminal.nix**: Terminal emulators (foot, kitty)
- **theming.nix**: Stylix integration, GTK/Qt themes
- **ui.nix**: Fonts, cursor themes, Wayland base environment (moved from top-level)

### Dev (`features/dev/`)

- **agent-tools.nix**: AI coding agent CLIs (claude-code, codex, gemini), shared skills, MCP config rendering. All three use FHS environments with self-bootstrapping npm install — they auto-update outside the Nix store.
- **editors.nix**: VS Code, Zed (with subFeatures for each)
- **git.nix**: Git config, delta, aliases
- **interp-lab.nix**: Interactive notebook/interpreter lab tooling
- **languages.nix**: Language toolchains (Python, Rust, Node, etc.)
- **mcp-servers.nix**: Model Context Protocol server configs (Serena, Codebase Memory, Polylogue, Context7, GitHub, Lynchpin, and opt-in browser automation)
- **shell.nix**: Unified shell environment with subFeatures:
  - `zsh`: Zsh + oh-my-zsh + syntax highlighting
  - `prompt`: Starship + Atuin + Zoxide + FZF
  - `utilities`: CLI tools (bat, eza, fd, ripgrep) + config linking
  - `tmux`: Terminal multiplexer
- **workbench.nix**: General development workbench applications and helpers

**Rule**: If users **directly interact** with it, it's a feature.

### Composite Module Pattern: Hyprland

The hyprland module (`features/desktop/hyprland/`) does NOT use `mkFeatureModule` due to:

- Complex internal structure (5 sub-files)
- Sub-files need parent's let-bindings
- System + HM config tightly coupled

Reserve this pattern for WM-level complexity only. Most features should use `mkFeatureModule`.
