# Repository Guidelines

## Project Structure & Module Organization
- `flake.nix` is the entrypoint; the `flake/` directory wires CLI apps, dev shells, and overlays.
- Domain modules live under `module/` (e.g., `module/interface`, `module/automation`). Import changes through the nearest `default.nix`.
- Machine-specific overrides reside in `host/` (notably `host/sinnix-prime/`).
- Shared dotfiles live in `dots/`; reusable assets belong in `module/asset/`. Add repeatable scripts to `module/automation/script.nix` or promote them to `flake/apps.nix` apps.

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
- Smoke-test user-facing scripts (e.g., `nix run .#apps.rawlog -- --help`) and record results in PR notes.
- Add ad-hoc NixOS tests when introducing new services or timers with higher risk.

## Commit & Pull Request Guidelines
- Commit subjects: ≤60 characters, imperative lowercase (e.g., `tighten dns routing`); squash fixups locally.
- Bodies touching services, secrets, or host modules should note context and verification commands run.
- Pull requests should link issues when available, list affected modules (e.g., `module/interface/hyprland.nix`, `host/sinnix-prime/*`), and include logs or screenshots for UI-impacting changes.
