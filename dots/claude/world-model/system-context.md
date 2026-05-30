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

**Sinnix rebuild** (from `/realm/project/sinnix` after `direnv allow`):
```
nix flake check --no-build  # Fast pre-flight
test-vm                     # Test risky changes in QEMU VM first
switch                      # Apply to live system (nixos-rebuild switch)
nh os boot .                # Alternative: safer, sets boot default
```
