## Top-Level Modules (Infrastructure)

Files at `modules/*.nix` represent **system-level cross-cutting concerns** that run before/beneath user features:

| Module | Purpose | Category |
|--------|---------|----------|
| foundation.nix | User identity, paths, projects, localization | Identity |
| core.nix | Nix config, caches, GC, security, firewall | Core System |
| networking.nix | Network config, DNS, hosts | Infrastructure |
| storage.nix | Filesystem mounts, drives, BTRFS | Infrastructure |
| performance.nix | CPU governor, I/O scheduler, OOM policy | Tuning |
| diagnostics.nix | System monitoring, metrics collection | Operations |
| log-hygiene.nix | Log cleanup, journal size limits | Operations |
| secrets.nix | Agenix secret integration | Security |
| home-manager.nix | Home Manager integration glue | Integration |
| default.nix | Auto-discovery aggregator (entry point) | Entry Point |

**Note**: `nix-ld` was moved to `features/system/` since it's user-facing (enabling binary compatibility).

**Rule**: If it affects **how the system operates** (not what users do on it), it's top-level.
