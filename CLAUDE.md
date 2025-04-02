# Development Guidelines for NixOS Config

## Commands
- `nix-switch` - Apply NixOS configuration (alias for `nh os switch`)
- `nix-update` - Update and apply configuration (alias for `nh os switch --update`)
- `nix-test` - Test configuration (alias for `nh os test`)
- `nix-clean` - Clean up old generations (alias for `nh clean all --keep 5`)

## Dotfiles Management
- Dotfiles in `dots/` directory, managed with GNU Stow
- Structure: `dots/<app>/.config/<app>/` → `~/.config/<app>/`
- Use `./dots/manage-dots.sh` script to deploy/remove/collect configs
- Currently manages: nvim

## Secrets Management
- Uses `agenix` for secret management in `secrets/` directory
- Can handle both system and user-level secrets

## Code Style
- **Formatting**: Use Alejandra for Nix files formatting
- **Indentation**: 2 spaces (no tabs)
- **Line Length**: Max 110 characters for Nix files
- **Imports**: Group by purpose, system imports first, then custom modules
- **Naming**: Use camelCase for variables/options, kebab-case for files
- **Documentation**: Comment non-obvious configurations with explanation
- **Organization**: Keep related configurations in appropriate module files

## Types
- Use proper Nix types where applicable
- Ensure modules have proper option declarations and types

## Error Handling
- Validate inputs with assertions where appropriate
- Use `lib.mkIf` for conditional configurations

## NixOS-Specific Notes
- Use `/bin/sh` for script shebangs
- Prefer `fd` over `find` when possible
- Some configs moving from home-manager to dotfiles

## Quality Checks
- Always verify syntax before committing: `sh -n` for shell, `nix-instantiate` for nix
- Test commands with small examples before full implementation
- Verify paths and permissions when manipulating files