# Sinnix

Sinnix is the live NixOS and Home Manager configuration for a personal
workstation, a headless replica host, and an OpenWrt router. It treats the
machines as one operating environment: host configuration, desktop behavior,
service topology, storage and recovery policy, observability, data capture,
and coding-agent tooling are versioned together.

This is a personal system rather than a reusable NixOS framework. The value of
the repository is in the complete design: it shows how a daily-driver machine
can remain reproducible while still accommodating local state, heavy developer
workloads, private data, hardware-specific behavior, and continuously evolving
automation.

## The system at a glance

| Surface | What Sinnix provides |
| --- | --- |
| Workstation | Hyprland/Noctalia desktop, Home Manager dotfiles, GPU modes, audio and terminal capture, local AI services, development environments, and interactive applications. |
| Runtime control | Typed service inventory, systemd resource classes, cgroup-aware command wrappers, pressure containment, and a single observable contract for user and system services. |
| Evidence capture | Sinex, Polylogue, machine telemetry, ActivityWatch, terminal recordings, and Lynchpin materialization are composed as cooperating services rather than ad-hoc shell processes. |
| State and recovery | Impermanence, explicit persistence declarations, Btrfs snapshots, Borg archives, restore drills, and separate policies for durable state, regenerable data, and bulk media. |
| Agent environment | Shared Claude/Codex/Gemini instructions and skills, generated MCP profiles, isolated browser/desktop control, local model backends, and a trusted repository gateway. |
| Other hosts | A headless NixOS replica shares the module system; the router is generated and deployed from a declarative OpenWrt configuration. |

## Architecture

```text
flake.nix
  ├─ flake/nixos.nix ── host construction ── hosts/{sinnix-prime,sinnix-ethereal}
  │                                           │
  │                                           └─ modules/
  │                                              ├─ platform policy
  │                                              ├─ features/
  │                                              ├─ services/
  │                                              └─ profiles/
  ├─ flake/router.nix ─────────────────────── hosts/sinnix-gw
  ├─ flake/scripts.nix ── discovered tools ─ scripts/
  └─ flake/tests.nix ──── evaluated contracts and runtime checks

dots/ ── Home Manager out-of-store links ── live user configuration
```

`modules/default.nix` recursively imports the active module tree. Module
factories give the hierarchy a consistent contract:

- features describe user-facing capabilities and are part of the default host
  character unless a host opts out;
- services describe long-running daemons and are enabled deliberately;
- profiles define workstation or cloud posture;
- top-level modules own platform concerns such as persistence, backups,
  networking, storage, and runtime governance.

Host files remain the final composition boundary. Auto-discovery removes
registration boilerplate; it does not hide which capabilities a machine uses.

## What this achieves

### A workstation that can rebuild without becoming generic

The desktop configuration deliberately includes machine-specific choices:
NVIDIA/Intel GPU modes, an OLED-oriented Wayland stack, local capture services,
storage topology, media tools, and particular editor/browser workflows. NixOS
still provides a reproducible system closure, while Home Manager's out-of-store
links keep actively edited dotfiles live without requiring a rebuild for every
change.

### Resource policy as part of service design

Services register themselves in a shared runtime inventory with a resource
class, manager, unit name, observation policy, and capture role. The resulting
inventory drives:

- systemd slice placement and memory/CPU/IO defaults;
- `sinnix-scope` wrappers for builds, agents, and background work;
- `/etc/sinnix/runtime-inventory.json` for runtime inspection;
- machine telemetry and `sinnix-observe` status views;
- evaluation-time checks that reject unknown or inconsistent service wiring.

Heavy builds are contained as disposable work; interactive agents and capture
services receive different protection. The rebuild commands also share a lock
and scheduling policy so two well-meaning tools cannot launch competing system
builds.

### Local data systems with explicit ownership

Sinnix runs the host-facing parts of a broader local evidence system:

- **Sinex** captures and transports event streams.
- **Polylogue** archives and derives structure from AI sessions.
- **Lynchpin** materializes cross-source evidence and analysis products.
- **Machine telemetry**, ActivityWatch, shell, and terminal capture preserve
  the host context those systems need.

The repository owns deployment and capture wiring, not the private datasets.
Raw captures, exports, personal notes, generated analyses, and secret payloads
live outside the checkout.

### Recovery policy that distinguishes data classes

The filesystem layout separates projects, canonical personal data, service
state, staging, throwaway work, and media. Persistence is declared rather than
accidental. Snapshot and Borg jobs cover durable data; nested or regenerable
subvolumes have explicit alternative handling; restore drills exercise the
recovery path rather than assuming archives are usable.

## Hosts

| Host | Role | Composition |
| --- | --- | --- |
| `sinnix-prime` | Interactive workstation and local service host | Workstation profile, desktop features, capture/analysis services, local AI, storage and backup policy. |
| `sinnix-ethereal` | Headless replica | Cloud profile, declarative storage, Tailscale connectivity, and the replica Sinex role. |
| `sinnix-gw` | OpenWrt router | Generated UCI configuration, package installation, deployment, and health checks. |

## Repository guide

| Path | Purpose |
| --- | --- |
| `flake.nix` | Inputs and flake-parts composition. |
| `flake/` | Host construction, package/overlay wiring, checks, development commands, and router/deployment outputs. |
| `hosts/` | The small host-specific layer that chooses roles and settings. |
| `modules/` | Platform modules plus feature, service, profile, and library subtrees. |
| `dots/` | Home Manager-managed configuration and shared agent tooling. |
| `scripts/` | Automatically packaged operational tools with declared runtime dependencies. |
| `pkgs/` | Larger standalone packages maintained with the system. |
| `docs/` | Current subsystem, bootstrap, and incident documentation. |

## Working with the repository

Enter the development environment:

```bash
direnv allow
# or
nix develop
```

Use the commands provided by the shell:

| Command | Purpose |
| --- | --- |
| `check` | Run the curated default verification tier sequentially. |
| `lint` | Run static Nix and shell checks without modifying files. |
| `format` | Format supported source through treefmt. |
| `switch` | Build and activate the workstation configuration through the shared lock and resource scope. |
| `boot` | Build and register the next boot generation without activating it. |
| `test-system` | Test activation without changing the boot default. |
| `test-vm` | Build the NixOS VM smoke surface. |

The wrappers are part of the architecture: direct `nh os switch` or unscoped
heavy commands bypass the containment and concurrency policy encoded here.

## Further reading

- [`docs/agent-gateway.md`](docs/agent-gateway.md) — trusted repository and
  command gateway for coding agents.
- [`docs/ethereal-bootstrap.md`](docs/ethereal-bootstrap.md) — first install
  and steady-state deployment of the headless host.

Editing and publication rules live in [`CLAUDE.md`](CLAUDE.md);
[`AGENTS.md`](AGENTS.md) is a symlink to the same contract.
