# SSH Configuration

This directory contains SSH configuration managed by GNU Stow.

## Structure

- `.ssh/config` - SSH client configuration
  - Uses GitHub-specific key at `~/.ssh/id_ed25519_github`
  - Default key at `~/.ssh/id_ed25519` for other hosts

## Integration with Agenix

The actual SSH private keys are managed by Agenix and deployed to:

- `/home/sinity/.ssh/id_ed25519` - Default SSH key

See `modules/core/secrets.nix` for the key deployment configuration.

