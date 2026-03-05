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
