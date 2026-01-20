# Configuration Structure

This repository uses `modules/default.nix` as the shared module entrypoint, with
hosts layering host-specific overrides and feature bundles. When you need to
introduce a new capability, add it to the appropriate module and enable it via
the host or a bundle so ownership stays with that module.

## System Modules (`modules/`)

- **Core stack** – `modules/core.nix`, `modules/programs.nix`, `modules/networking.nix`,
  `modules/storage.nix`, etc. provide system-wide defaults.  They expect to be
  imported together from `flake/nixos.nix`, and each module owns its domain.
- **Services** – Each service lives in its own file under
  `modules/services/` (`asciinema.nix`, `polylogue.nix`, `sinex.nix`,
  `transmission.nix`). Service-specific state, users, tmpfiles, and advanced
  tuning stay beside the service definition. Hosts enable services by toggling
  `sinnix.services.*` (the service module set is imported via
  `modules/services/default.nix`). Former services (`qdrant.nix`,
  `sinevec.nix`) were consolidated into the unified Sinex service.
- **Secrets** – `modules/secrets.nix` renders every `.age` file and exposes two
  read-only helpers:
  - `config.sinnix.secrets.paths.NAME` – resolved runtime path for the secret.
  - `config.sinnix.secrets.exportScript` – shell snippet for selective export.
  Service modules reference `config.sinnix.secrets.paths` so secret usage is
  documented alongside the rest of the service configuration. Home modules
  receive the same mapping via `secretPaths` and should prefer it to literal
  `/run/agenix/...` paths.
- **Diagnostics** – `modules/diagnostics.nix` installs the core hardware tools
  plus the `perf-scan` wrapper; the heavier perf suite dependencies live inside
  the packaged `perf-scan` derivation instead of the global system profile.

## Host (`hosts/sinnix-prime`)

- Imports the required hardware overrides (`boot.nix`, `input.nix`, `display.nix`,
  `storage.nix`) and selects the services to activate.
- Direct overrides (e.g. toggling `services.sinex.enable`) belong here – the
  host remains the single point of control by virtue of the modules it chooses.

## Home-Manager Features (`modules/features/`)

- Feature modules live under `modules/features/` and are grouped by domain
  (`cli`, `desktop`, `dev`). `modules/bundles/` toggles cohesive sets of
  features for a host.
- Dev tooling that should not trigger system rebuilds lives under
  `modules/features/dev/`. Desktop UI config lives under
  `modules/features/desktop/`.

## Storage Responsibilities

- `modules/storage.nix` owns systemd services, mounts, and system-level packages
  required for Always-On sync (davfs2, rclone-backed remotes).  User-facing
  helpers (gocryptfs, mount scripts) live in
  `modules/features/desktop/storage.nix`.
- The module also relies on `config.sinnix.secrets.paths.davfs2-secrets` for the
  davfs2 credentials so the secret location is defined exactly once.

## Sinex Service

- `modules/services/sinex.nix` now fixes a handful of local defaults (state root
  under `/realm/data/indices/sinex`, desktop filesystem watch roots) and supports
  `sinnix.services.sinex.provisionDatabase` so the PostgreSQL setup can be
  kept ready without enabling the full service.
- The host still chooses when to enable the service; toggling it on prepares
  the working directories and exposes the CLI binaries exactly as the upstream
  module expects.

## Workflow Expectations

- Import a module where the behaviour logically belongs (host vs system vs user).
- Use `config.sinnix.secrets.paths` instead of hard-coding `/run/agenix/...`.
- When adding tooling, prefer the user profile unless the binary must be
  available before login; the shared modules install `perf-scan`, which bundles
  its own perf suite dependencies.
- Document new cross-cutting contracts (paths, data roots, service ownership)
  here to keep the topology obvious.
