# Base Operational Rules

## Completion and Safety

- Work is not done until things compile, are committed, and docs are current. Update memory when facts change.
- Do not "fix" issues by disabling or removing features.
- Never remove files that cannot be recovered via version control. Do not use `git restore` on entire folders.
- Comments must describe the current behavior. Avoid meta commentary about your changes.
- When modifying code or configuration, overwrite instead of creating; prune obsolete bits.
- Save full compilation output to `compilation.log` when compiling.

## Workflow Preferences

- Prefer `fd` over `find` and `rg` over `grep`.
- Prefer singular folder names.

## Nix

- OS is NixOS.
- Scripts use `#!/usr/bin/env bash`.
- Nix flake builds only see tracked files; commit SQLX cache files.
- Avoid `nix develop --command` unless needed; enter the shell first.

## Communication

- No gratuitous flattery or sycophancy.
