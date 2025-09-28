# Repository Guidelines

## Project Structure & Module Organization
- `flake.nix` is the entrypoint; `flake/` contains CLI apps, the dev shell, and overlay wiring that glue the system together.
- Keep domain modules within `module/` and import them through the nearest `default.nix`; machine-specific overrides belong in `host/sinnix-prime/`.
- Shared dotfiles stay in `dots/`, reusable assets in `module/asset/`, and repeatable tasks should become `flake/apps.nix` apps before landing in `scripts/`.

## Build, Test, and Development Commands
- `direnv allow` or `nix develop` loads the devenv shell (see `flake/dev-shell.nix`) with hooks and helper scripts.
- `check` runs `nix flake check` plus parser validation; run it before committing or opening a PR.
- `nix run .#format` applies `nixfmt-rfc-style`, while `nix run .#lint` runs `deadnix` and ShellCheck without modifying sources.
- `sudo nix run .#test` performs `nixos-rebuild test` for `sinnix-prime`; only follow with `sudo nix run .#switch` after reviewing the output.
- `nix run .#update` refreshes flake inputs; commit the resulting `flake.lock` alongside related code.

## Coding Style & Naming Conventions
- Nix files use two-space indentation, kebab-case names (e.g. `interface/system.nix`), and must pass `nixfmt-rfc-style`.
- Remove unused bindings with `deadnix` and prefer explicit `inherit (pkgs) foo bar` over blanket imports.
- Python utilities follow the `pyproject.toml` rules (Black, Ruff, 88-character lines on Python 3.11).
- Bash helpers start with `#!/usr/bin/env bash`, enable `set -euo pipefail`, and satisfy `shellcheck`.

## Testing Guidelines
- Always run `check`; it guards against evaluation regressions and syntax errors.
- Exercise host-level tweaks with `sudo nix run .#test` and inspect the streamed `nom` logs before switching.
- Smoke-test updated dotfiles or scripts (e.g. `scripts/rawlog --help`) and record the result in the pull request notes.
- Add ad-hoc nixos tests when introducing critical services or timers, even though extra coverage tooling is optional.

## Commit & Pull Request Guidelines
- Mirror existing history: ≤60-character, imperative, lowercase subjects (`tighten dns routing`), with fixups squashed locally.
- Document context plus the verification commands you ran in commit bodies when touching services, secrets, or host modules.
- Pull requests should link issues when available, list affected modules (`module/interface/hyprland.nix`, `host/sinnix-prime/*`), and include UI screenshots or logs when relevant.

## Secrets & Configuration Tips
- Manage encrypted secrets in `secrets/` via agenix; edit with `nix run .#agenix -- -e secrets/<name>.age` and never commit plaintext.
- Reference new secrets from the owning module, update `secrets.nix`, and keep environment-specific values in host modules rather than shared logic.
