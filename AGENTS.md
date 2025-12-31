# Repository Guidelines

## Project Structure & Module Organization

- `flake.nix` is the entrypoint; the `flake/` directory wires CLI apps, dev shells, and overlays.
- System modules live under `modules/` (e.g., `modules/core.nix`, `modules/services`). Import changes through the nearest `default.nix`.
- Home profile modules live under `modules/features/` (e.g., `modules/features/desktop`, `modules/features/dev`, `modules/features/cli`).
- Machine-specific overrides reside in `hosts/` (notably `hosts/sinnix-prime/`).
- Shared dotfiles live in `dots/`; reusable assets belong in `assets/`. Add repeatable scripts through `modules/programs.nix` or promote them to `flake/apps.nix` apps.

### Single-User Assumption

- The configuration is intentionally opinionated for a single human (`sinity`) across two machines. Do **not** spend effort making modules multi-user pluggable or adding enable/disable switches for hypothetical users. If a change must differ between hosts, wire it through the host directories instead.

### Services & Features

- Core audio, networking, and desktop plumbing are enabled in the shared modules; hosts only import the service modules they need (see `hosts/sinnix-prime`).

## Build, Test, and Development Commands

- `direnv allow` / `nix develop` – enter the dev shell with hooks and helper commands.
- `nix run .#format` – run `nixfmt-rfc-style` over all Nix sources.
- `nix run .#lint` – execute `deadnix` and ShellCheck (read-only).
- `nix run .#check` – run `nix flake check` plus parser validation.
- `sudo nix run .#test` – `nixos-rebuild test` for `sinnix-prime`; review streamed `nom` logs before switching.
- `sudo nix run .#switch` – apply the NixOS configuration after testing.
- `nix run .#update` – refresh flake inputs; commit the resulting `flake.lock` with related changes.

## Coding Style & Naming Conventions

- Nix: two-space indentation, kebab-case filenames, prefer `inherit (pkgs) foo bar`, and keep sources `nixfmt-rfc-style` formatted.
- Python: follow `pyproject.toml` (Black + Ruff, 88 columns, Python 3.11).
- Bash: begin with `#!/usr/bin/env bash`, enable `set -euo pipefail`, and satisfy ShellCheck; remove unused bindings with `deadnix`.

## Testing Guidelines

- Run `nix run .#check` before every PR or commit to catch evaluation regressions.
- For host tweaks, use `sudo nix run .#test` and inspect the streamed `nom` logs.
- Smoke-test user-facing scripts (e.g., `scripts/rawlog --help`) and record results in PR notes.
- Add ad-hoc NixOS tests when introducing new services or timers with higher risk.

## Commit & Pull Request Guidelines

- Commit subjects: ≤60 characters, imperative lowercase (e.g., `tighten dns routing`); squash fixups locally.
- Bodies touching services, secrets, or host modules should note context and verification commands run.
- Pull requests should link issues when available, list affected modules (e.g., `modules/ui.nix`, `modules/features/desktop/hyprland/default.nix`, `hosts/sinnix-prime/*`), and include logs or screenshots for UI-impacting changes.
