# NixOS Configuration

A declarative, modular NixOS system configuration using flake-parts and devenv.

## Quick Start

```bash
# Enter development environment
cd /realm/project/sinnix
direnv allow   # Or: nix develop

# Validate configuration
check

# Apply configuration
switch
```

## Structure

- `flake.nix` – Dependency declarations and flake-part wiring
- `flake/` – Flake components (`nixos.nix`, `dev-shell.nix`, `apps.nix`, `tests.nix`, overlays/packages)
- `modules/` – NixOS modules by taxonomy:
  - top-level `modules/*.nix` = infrastructure/platform
  - `modules/features/` = user-facing capabilities (cli/desktop/dev/system)
  - `modules/services/` = long-running daemons/timers
  - `modules/bundles/` = composition-only presets
  - `modules/lib/` = reusable helpers/factories
- `hosts/` – Host-specific overrides (e.g. `hosts/sinnix-prime`)
- `dots/` – Declarative dotfiles linked via Home Manager

Encrypted secrets (agenix) live outside this checkout, not under a repo path.

Hosts import shared modules and selectively enable bundles/features/services.

## Core Commands

**Development Environment:**

- `check` - Validate configuration
- `format` - Format Nix code
- `switch` - Apply configuration changes (requires sudo)
- `test-system` - Build and test activation without switching

**Direct Nix Commands:**

- `check --no-build` - Run the curated default check tier through the devshell-safe sequential wrapper
- `nix fmt` - Format code via treefmt
- `nix flake update` - Update flake inputs

**Flake App Commands:**

- `nix run .#lint` - Check code quality
- `test-system` - Test without applying
- `switch` - Apply configuration
- `clean` - Clean old generations
- `nix run .#agenix` - Manage secrets

## Features

- Modular system with flake-parts
- Development environment with devenv.sh
- Automated code quality (pre-commit hooks)
- Secret management with agenix
- Comprehensive home-manager configuration
- Sinex module uses the `sinex` input directly; set `sinnix.services.sinex.*` to provision Postgres without enabling services

## Desktop Workflow Highlights

- **Hyprland + qutebrowser**: Hyprland groups replace browser tabs; each qutebrowser page spawns a native window bound to the active workspace layout.
- **Noctalia shell**: Noctalia owns the bar, launcher, notifications, lock screen, OSD, wallpaper, and live Material-You palette.
- **mpv-centered media**: `open-in-mpv`/`yt-related` userscripts offload streaming and SponsorBlock/RYD logic to mpv with bundled scripts.
- **Dual editors**: VS Code and Zed both default to plain zsh terminals and hide internal tab bars so Hyprland groups and kitty layouts stay consistent.
- **Automation hooks**: qutebrowser config ships ActivityWatch heartbeats, tab dedupe/cap logic, and research capture scripts; borg backups run daily via user timers.

## Design Philosophy

- Explicit over implicit: Modules are explicitly imported
- Modularity: Each component has a single responsibility
- Composability: System built from independent, focused modules
- Structure: Consistent organization and conventions

## Documentation

- `CLAUDE.md` – canonical agent instruction file (flat; `AGENTS.md` is a symlink to it)
