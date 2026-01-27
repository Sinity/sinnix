---
description: NixOS system management helpers for this sinnix configuration. Use for rebuilding, checking generations, finding packages, and debugging nix issues.
allowed-tools: Bash(nix:*), Bash(nixos-rebuild:*), Bash(systemctl:*), Bash(journalctl:*), Read, Glob, Grep
argument-hint: [rebuild|generations|search|diff|gc]
---

# NixOS Tools for Sinnix

Helpers for managing the sinnix NixOS configuration at `/realm/project/sinnix`.

## System Rebuild

```bash
# Test build (doesn't switch)
nixos-rebuild build --flake /realm/project/sinnix

# Switch to new config
sudo nixos-rebuild switch --flake /realm/project/sinnix

# Build but only switch on next boot
sudo nixos-rebuild boot --flake /realm/project/sinnix

# Show what would change (dry run)
nixos-rebuild dry-build --flake /realm/project/sinnix
```

## Generation Management

```bash
# List generations
sudo nix-env --list-generations -p /nix/var/nix/profiles/system

# Current generation
readlink /run/current-system

# Diff between generations
nix store diff-closures /nix/var/nix/profiles/system-{N-1}-link /nix/var/nix/profiles/system-{N}-link

# Rollback
sudo nixos-rebuild switch --rollback

# Delete old generations (keep last 5)
sudo nix-collect-garbage --delete-older-than 7d
```

## Package Search

```bash
# Search nixpkgs
nix search nixpkgs <package>

# Find package providing a file
nix-locate <filename>

# Show package info
nix eval nixpkgs#<package>.meta.description

# List installed packages (system)
nix path-info -rsSh /run/current-system | sort -k2 -h | tail -20

# Find which module enables a package
grep -r "packageName" /realm/project/sinnix/modules/
```

## Flake Operations

```bash
# Update all flake inputs
nix flake update /realm/project/sinnix

# Update single input
nix flake lock --update-input nixpkgs /realm/project/sinnix

# Show flake info
nix flake show /realm/project/sinnix

# Check flake
nix flake check /realm/project/sinnix
```

## Debugging

```bash
# Why is package in closure?
nix why-depends /run/current-system /nix/store/<hash>-<package>

# Build with verbose output
nixos-rebuild build --flake /realm/project/sinnix --show-trace

# Evaluate specific option
nix eval /realm/project/sinnix#nixosConfigurations.sinnix-prime.config.services.netdata.enable

# Check derivation
nix show-derivation /nix/store/<hash>.drv
```

## Service Management

```bash
# Restart service after config change
sudo systemctl restart <service>

# Check service status
systemctl status <service>

# View service logs
journalctl -u <service> -f

# List all sinnix services
systemctl list-units | grep -E "netdata|polylogue|sinex"
```

## Garbage Collection

```bash
# Show store size
du -sh /nix/store

# Optimize store (dedup)
nix store optimise

# Collect garbage (safe)
nix-collect-garbage

# Aggressive cleanup (careful!)
sudo nix-collect-garbage -d
```

## Sinnix-Specific

```bash
# Module structure
ls /realm/project/sinnix/modules/

# Find feature module
grep -r "description.*=" /realm/project/sinnix/modules/features/ | head -20

# Check enabled features (for sinnix-prime)
grep "enable = true" /realm/project/sinnix/hosts/sinnix-prime/*.nix

# Dotfiles location
ls /realm/project/sinnix/dots/
```

## Common Issues

### Build fails with hash mismatch
```bash
# Clear evaluation cache
rm -rf ~/.cache/nix/

# Rebuild
nixos-rebuild build --flake /realm/project/sinnix
```

### Service won't start
```bash
# Check logs
journalctl -u <service> -n 100 --no-pager

# Check config syntax
systemctl cat <service>

# Manual start for debugging
sudo /nix/store/...-<service>/bin/<binary>
```

### Out of disk space
```bash
# Check store size
df -h /nix/store

# Find largest packages
nix path-info -rsSh /run/current-system | sort -k2 -h | tail -30

# Cleanup
sudo nix-collect-garbage --delete-older-than 3d
```
