## System Context

### Hardware

- **Host**: `sinnix-prime` (desktop workstation)
- **CPU**: Intel i7-13700K (16 cores, 24 threads)
- **OS**: NixOS 26.05 (Yarara) - unstable channel

### NixOS Environment

```
# NEVER use nix profile commands - all packages via modules
# Use nix shell/nix develop for temporary tools

direnv allow           # Activate project devshell
nix develop            # Enter flake devshell manually
nix build .#<output>   # Build specific flake output
```

**Sinnix rebuild** — ALWAYS use the devshell commands (they wrap `nh` with idle CPU/IO scheduling):

```
# From inside the devshell (direnv allow or nix develop):
check --no-build            # Fast pre-flight; curated, sequential, eval-cache disabled
test-vm                     # Test risky changes in QEMU VM first
switch                      # Apply to live system (resource-scoped nh os switch)
boot                        # Safer alternative: set boot default without immediate activation

# From outside the devshell (e.g. Claude Code, non-devshell shell):
cd /realm/project/sinnix && nix develop --command switch
# NEVER: nix shell nixpkgs#nh --command nh os switch ...
# NEVER: nh os switch ... (bypasses idle-scheduling wrapper)
```

> **Why this matters**: `nix.daemonCPUSchedPolicy=idle` is set, but that only affects
> the scheduler priority — it does NOT cap memory. Without the nix-build.slice placement
> (added 2026-06-09), the daemon ran unconstrained in system.slice and Rust builds could
> consume all 32 GB of RAM, thrashing the system and making video unplayable even though
> CPU cycles were yielded correctly. Always use `switch`/`boot` devshell commands or
> `nix develop --command switch` — these ensure proper resource context.
