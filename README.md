# Sinnix

Sinnix is the NixOS and Home Manager configuration that runs a personal
workstation, a headless replica host, and an OpenWrt router. Host configuration,
desktop behavior, services, storage, recovery, monitoring, data capture, and
coding-agent tooling are versioned as one operating environment.

This is a personal system, not a generic NixOS framework. The repository shows
how one daily-use environment can remain reproducible while still accounting
for hardware-specific behavior, private state, heavy development workloads,
local data systems, and frequent operational changes.

[Project overview](https://sinity.github.io/sinnix/) | [Roadmap and operating record](https://sinity.github.io/sinnix/beads/)

## What the repository manages

| Area | Current scope |
|---|---|
| Workstation | Hyprland and Noctalia desktop, Home Manager configuration, GPU modes, audio, terminal capture, local AI services, development environments, and desktop applications |
| Services | typed service inventory, systemd resource classes, cgroup-aware command wrappers, monitoring, and common policy for user and system units |
| Local data | Sinex, Polylogue, Lynchpin, ActivityWatch, machine telemetry, shell history, and terminal recordings |
| Storage and recovery | impermanence, explicit persistence, Btrfs snapshots, Borg archives, restore drills, and separate treatment for durable, rebuildable, and bulk data |
| Agent tooling | shared instructions and skills, generated MCP profiles, browser and desktop control, local model backends, and a trusted repository gateway |
| Other hosts | a headless NixOS replica using the same module system and a router built from declarative OpenWrt configuration |

## Hosts

| Host | Role | Main responsibilities |
|---|---|---|
| `sinnix-prime` | interactive workstation and local service host | desktop, development, capture, analysis, local AI, storage, and backups |
| `sinnix-ethereal` | headless replica | cloud profile, declarative storage, Tailscale, and the replica Sinex role |
| `sinnix-gw` | OpenWrt router | generated UCI configuration, packages, deployment, and health checks |

## Repository structure

```text
flake.nix
  |-- flake/nixos.nix       host construction
  |      `-- hosts/{sinnix-prime,sinnix-ethereal}
  |             `-- modules/
  |                  |-- platform policy
  |                  |-- features/
  |                  |-- services/
  |                  `-- profiles/
  |-- flake/router.nix      sinnix-gw
  |-- flake/scripts.nix     packaged operational tools
  `-- flake/tests.nix       evaluation and runtime checks

dots/                      Home Manager out-of-store configuration
```

`modules/default.nix` imports the active module tree. The hierarchy is split by
purpose:

- features describe user-facing capabilities and are normally part of the
  workstation character;
- services describe long-running processes and are enabled deliberately;
- profiles define workstation and cloud posture;
- top-level modules own persistence, backups, networking, storage, and runtime
  policy;
- host files remain the final place where roles and settings are chosen.

Auto-discovery removes registration boilerplate. It does not hide which modules
a host enables.

## Main design choices

### Reproducible but machine-specific

The workstation configuration includes real hardware and workflow decisions:
NVIDIA and Intel GPU modes, an OLED-oriented Wayland setup, local capture
services, storage topology, media tools, and specific browser and terminal
workflows.

NixOS supplies a reproducible system closure. Home Manager out-of-store links
keep actively edited user configuration live without forcing a full rebuild for
every change.

### Resource policy belongs with the service

Services register in a shared runtime inventory with a resource class, manager,
unit name, observation policy, and capture role. That inventory drives:

- systemd slice placement and memory, CPU, and I/O defaults;
- `sinnix-scope` wrappers for builds, agents, and background work;
- `/etc/sinnix/runtime-inventory.json` for inspection;
- machine telemetry and `sinnix-observe` status output;
- evaluation checks for unknown or inconsistent service wiring.

Heavy builds are treated differently from interactive agents and capture
services. Rebuild commands share a lock and scheduling policy, so separate tools
cannot start competing system builds by accident.

### Each data system keeps its own authority

Sinnix deploys and connects the host-facing parts of several local data systems:

- **Sinex** captures and processes event streams.
- **Polylogue** archives AI conversations and coding-agent runs.
- **Lynchpin** joins sources and builds analysis products.
- **ActivityWatch**, machine telemetry, shell history, and terminal recording
  provide additional host context.

They do not share one database. Each project keeps its own storage, provenance,
and product rules. Sinnix owns service wiring, resource policy, paths, secrets,
and recovery contracts.

The repository contains deployment and capture configuration, not private data.
Raw captures, exports, notes, generated reports, and secrets live outside the
checkout.

### Recovery follows data type

The filesystem layout separates projects, canonical personal data, service
state, staging, temporary work, and media. Persistence is declared instead of
being an accidental consequence of a path.

Snapshots and Borg jobs cover durable data. Rebuildable or nested subvolumes use
explicit alternative handling. Restore drills exercise the recovery path rather
than assuming that an archive is usable.

## Working with the repository

Enter the development environment:

```bash
direnv allow
# or
nix develop
```

Common commands:

| Command | Purpose |
|---|---|
| `check` | run the curated default verification tier sequentially |
| `lint` | run static Nix and shell checks without modifying files |
| `format` | format supported source with treefmt |
| `switch` | build and activate the workstation through the shared lock and resource scope |
| `boot` | build and register the next boot generation without activating it |
| `test-system` | test activation without changing the boot default |
| `test-vm` | build the NixOS VM smoke test |

The wrappers are part of the operating policy. Direct `nh os switch` or
unscoped heavy commands bypass the resource and concurrency controls encoded in
the repository.

## Repository guide

| Path | Purpose |
|---|---|
| `flake.nix` | inputs and flake-parts composition |
| `flake/` | host construction, packages, overlays, checks, development commands, and deployment outputs |
| `hosts/` | host-specific roles and settings |
| `modules/` | platform modules plus feature, service, profile, and library trees |
| `dots/` | Home Manager configuration and shared agent tooling |
| `scripts/` | packaged operational tools with declared runtime dependencies |
| `pkgs/` | larger standalone packages maintained with the system |
| `docs/` | current subsystem, bootstrap, and incident documentation |

## Further reading

- [Agent gateway](docs/agent-gateway.md)
- [Agent environment reference](docs/agent-environment.md)
- [Infrastructure default audit](docs/config-default-audit-infrastructure.md)
- [Headless replica bootstrap](docs/ethereal-bootstrap.md)
- [Project overview](https://sinity.github.io/sinnix/)
- [Roadmap and operating record](https://sinity.github.io/sinnix/beads/)

Editing and publication rules live in [CLAUDE.md](CLAUDE.md). `AGENTS.md` is a
symlink to the same contract.

## Status

This repository describes and operates one real personal environment. It is
published as a complete example and as reusable source material, but consumers
should expect to adapt hardware, paths, secrets, services, and policy rather
than import it as a drop-in distribution.
