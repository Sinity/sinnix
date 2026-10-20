# Sinnix

Sinnix is the NixOS and Home Manager configuration for a personal workstation,
a headless replica, and an OpenWrt router. It versions desktop behavior,
services, storage, recovery, capture, and coding-agent tools together.
Hardware, paths, secrets, and policy are specific to this environment; adapt
these sources before using them elsewhere.

## Hosts and capabilities

| Host              | Role                                                                                   |
| ----------------- | -------------------------------------------------------------------------------------- |
| `sinnix-prime`    | Hyprland and Noctalia desktop, development, capture, local AI, storage, and backups    |
| `sinnix-ethereal` | Headless NixOS replica with declarative storage, Tailscale, and the replica Sinex role |
| `sinnix-gw`       | OpenWrt router with generated UCI configuration, deployment, and health checks         |

The workstation includes NVIDIA and Intel GPU modes, audio and media tools,
terminal recording, and browser and desktop control. Home Manager out-of-store
links make user configuration edits available without a rebuild.

Sinnix deploys the host-facing parts of **Sinex** (event capture and processing),
**Polylogue** (AI conversation archives), and **Lynchpin** (cross-source analysis).
ActivityWatch, telemetry, shell history, and terminal recording supply additional
host context. Each data project owns its databases, provenance, and product
rules. Sinnix owns their service wiring, resources, paths, secrets, and recovery.
Private captures, reports, notes, and secrets remain outside the checkout.

## Repository map

| Path        | Purpose                                                                                     |
| ----------- | ------------------------------------------------------------------------------------------- |
| `flake.nix` | Inputs and flake-parts composition                                                          |
| `flake/`    | Host construction, packages, overlays, checks, development commands, and router outputs     |
| `hosts/`    | Host roles, hardware, and settings                                                          |
| `modules/`  | Platform policy, default-on features, default-off services, profiles, and factories         |
| `dots/`     | Home Manager configuration, shared agent instructions and skills, client settings and hooks |
| `scripts/`  | Small packaged tools with declared runtime dependencies                                     |
| `pkgs/`     | Larger packages and test suites for scripts                                                 |
| `docs/`     | Subsystem behavior and bootstrap guides                                                     |

`modules/default.nix` discovers the module tree. Host files choose enabled
roles and settings; profiles supply workstation and cloud defaults.

## Runtime and recovery

Services register their manager, unit, resource class, observation policy, and
capture role in a shared inventory. It drives systemd slice placement,
resource defaults, telemetry, and `/etc/sinnix/runtime-inventory.json`.
`sinnix-observe` inspects live state; evaluation checks reject inconsistent
service wiring. Named AgentCTL operations schedule heavy and recurring work.
Rebuild commands share a lock to prevent competing system builds.

Login sessions and the user manager put temporary work on NVMe at
`TMPDIR=/realm/tmp/work`; `/tmp` is a small tmpfs and remains the default for
system services. `sinnix-tmp-sweep` removes unused `nix-shell.*` and
`nix-develop-*` directories every fifteen minutes.

The filesystem separates projects, personal data, service state, staging,
temporary work, and media. Persistence is declared. Stores and captures are
classified by recovery needs:

- canonical data is preserved indefinitely;
- derived data names its inputs;
- caches are ephemeral;
- exact copies name their source and backup responsibility.

Evaluation rejects contradictory or dangling declarations. Btrfs snapshots and
Borg archives cover durable data; nested or rebuildable subvolumes declare
alternative handling. Restore drills exercise recovery. Agent CLI recovery uses
the versioned, hash-checked tarballs in `flake/data/agent-cli-sources.nix`.

## Development

Enter the environment with `nix develop`, or `direnv allow` after reviewing the
checkout's `.envrc`.

| Command       | Purpose                                                        |
| ------------- | -------------------------------------------------------------- |
| `check`       | Run the curated default verification tier sequentially         |
| `lint`        | Check Nix and shell sources without modifying them             |
| `format`      | Format supported sources with treefmt                          |
| `switch`      | Build and activate through the shared lock and resource policy |
| `boot`        | Register the next boot generation without activating it        |
| `test-system` | Test activation without changing the boot default              |
| `test-vm`     | Build the NixOS VM smoke test                                  |

Run heavy or scheduled work as a declared operation; list them with
`agentctl project operations sinnix`. Package test suites are separate checks
in `flake/tests/pkg-suites.nix`, so editing a test does not rebuild its package.
Editing, publication, verification, and activation rules live in
[AGENTS.md](AGENTS.md).

## Subsystem guides

- [Agent operations](docs/agentctl.md) and [gateway](docs/agent-gateway.md)
- [Generated agent environment reference](docs/agent-environment.md)
- [Local AI activation](docs/local-ai-activation.md)
- [Headless replica bootstrap](docs/ethereal-bootstrap.md)
- [Other subsystem documentation](docs/)
