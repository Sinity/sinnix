# Configuration Structure

This repository is organised so that the active host (`sinnix-prime`) pulls
modules directly; there is no additional aggregation layer.  When you need to
introduce a new capability, import the module from the host (or user profile)
and keep ownership with that module.

## System Modules (`modules/`)

- **Core stack** – `modules/core.nix`, `modules/programs.nix`, `modules/networking.nix`,
  `modules/storage.nix`, etc. provide system-wide defaults.  They expect to be
  imported together from `flake/nixos.nix`, and each module owns its domain.
- **Services** – Each service lives in its own file under
  `modules/services/` (`photoprism.nix`, `qdrant.nix`, `sinevec.nix`,
  `sinex.nix`, `transmission.nix`).  Service-specific state, users, tmpfiles,
  and advanced tuning stay beside the service definition.  The host chooses
  which services to enable by importing the corresponding file.
- **Secrets** – `modules/secrets.nix` renders every `.age` file and exposes two
  read-only helpers:
  - `config.sinnix.secrets.paths.NAME` – resolved runtime path for the secret.
  - `config.sinnix.secrets.exportScript` – shell snippet for selective export.
  Service modules reference `config.sinnix.secrets.paths` so secret usage is
  documented alongside the rest of the service configuration. Home modules
  receive the same mapping via `secretPaths` and should prefer it to literal
  `/run/agenix/...` paths.
- **Diagnostics** – `modules/diagnostics.nix` keeps essential hardware tools
  installed by default and publishes `config.sinnix.optionalPackages` so you can
  see (and quickly re-enable) the trimmed “nice to have” suites without keeping
  them in the base closure.
- **Perf Shell** – `nix develop .#perf-tools` drops you into a shell with those
  optional diagnostics/perf suites on demand, so you can keep the system build
  lean and only bring the heavy tooling in when needed.

## Host (`hosts/sinnix-prime`)

- Imports the required hardware overrides (`boot.nix`, `input.nix`, `display.nix`,
  `storage.nix`) and selects the services to activate.
- Direct overrides (e.g. toggling `services.sinex.enable`) belong here – the
  host remains the single point of control by virtue of the modules it chooses.

## User Profiles (`user/`)

- `user/default.nix` brings together profile facets (`core`, `desktop`, `dev`,
  `media`, `networking`, `storage`).
- Dev tooling that should not trigger system rebuilds lives under `user/dev/`.
  The system modules only keep the operational minimum (e.g. CLI basics,
  perf-scan wrapper).

## Storage Responsibilities

- `modules/storage.nix` owns systemd services, mounts, and system-level packages
  required for Always-On sync (davfs2, OneDrive, rclone).  User-facing helpers
  (gocryptfs, mount scripts) remain in `user/storage.nix`.
- The module also relies on `config.sinnix.secrets.paths.davfs2-secrets` for the
  davfs2 credentials so the secret location is defined exactly once.

## Sinex Service

- `modules/services/sinex.nix` now simply fixes a handful of local defaults
  (data root under `/realm/data/sinex`, `database.autoSetup = true`, desktop
  filesystem watch roots). All of the heavy wiring continues to come from the
  upstream Sinex module.
- The host still chooses when to enable the service; toggling it on prepares
  the working directories and exposes the CLI binaries exactly as the upstream
  module expects.

## Workflow Expectations

- Import a module where the behaviour logically belongs (host vs system vs user).
- Use `config.sinnix.secrets.paths` instead of hard-coding `/run/agenix/...`.
- When adding tooling, prefer the user profile unless the binary must be
  available before login; perf-scan already encapsulates heavy diagnostics.
- Document new cross-cutting contracts (paths, data roots, service ownership)
  here to keep the topology obvious.
