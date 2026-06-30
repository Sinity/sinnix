## Top-Level Modules (Infrastructure)

Files at `modules/*.nix` represent **system-level cross-cutting concerns** that run before/beneath user features:

| Module             | Purpose                                      | Category       |
| ------------------ | -------------------------------------------- | -------------- |
| foundation.nix     | User identity, paths, projects, localization | Identity       |
| build-policy.nix   | Nix daemon, caches, build scratch, GC        | Build Policy   |
| core.nix           | Platform defaults, security, firewall        | Core System    |
| networking.nix     | Network config, DNS, hosts                   | Infrastructure |
| storage.nix        | Filesystem mounts, drives, BTRFS             | Infrastructure |
| backup.nix         | Btrbk/Borg backup and restore-drill pipeline | Infrastructure |
| persistence.nix    | Impermanence and persisted state mapping     | Infrastructure |
| performance.nix    | CPU governor, I/O scheduler, OOM policy      | Tuning         |
| gpu.nix            | Host GPU mode selection and driver policy    | Hardware       |
| runtime.nix        | Runtime inventory, resource classes, slices  | Operations     |
| diagnostics.nix    | System monitoring, metrics collection        | Operations     |
| dotfiles-sweep.nix | Cross-feature dotfile metadata application   | Operations     |
| introspection.nix  | Generated config dump                        | Operations     |
| log-hygiene.nix    | Log cleanup, journal size limits             | Operations     |
| secrets.nix        | Agenix secret integration                    | Security       |
| home-manager.nix   | Home Manager integration glue                | Integration    |
| default.nix        | Auto-discovery aggregator (entry point)      | Entry Point    |

**Note**: `nix-ld` was moved to `features/system/` since it's user-facing (enabling binary compatibility).

**Rule**: If it affects **how the system operates** (not what users do on it), it's top-level.
