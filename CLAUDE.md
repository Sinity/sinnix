# Development Guidelines for NixOS Config

## Commands

- `nix-switch` - Apply NixOS configuration (alias for `nh os switch`)
- `nix-update` - Update and apply configuration (alias for `nh os switch --update`)
- `nix-test` - Test configuration (alias for `nh os test`)
- `nix-clean` - Clean up old generations (alias for `nh clean all --keep 5`)

## Module Structure

- **Core Modules**: System-level configuration in `modules/core/`
- **Home Modules**: User-level configuration in `modules/home/`

## Neovim Configuration

- Neovim config lives in `/nvim/` directory
- Symlinks created via home-manager in `modules/home/neovim.nix`

## Secrets Management

- Uses `agenix` for secret management in `secrets/` directory
- Can handle both system and user-level secrets
- See `modules/core/secrets.nix` for integration

## Code Style

- **Formatting**: Use Alejandra for Nix files formatting
- **Indentation**: 2 spaces (no tabs)
- **Line Length**: Max 110 characters for Nix files
- **Header Comments**: Start each module file with a clear description comment
- **Section Comments**: Use section comments to group related settings
- **Imports**: Group by purpose, system imports first, then custom modules
- **Naming**: Use camelCase for variables/options, kebab-case for files
- **Organization**: Keep related configurations in appropriate module files

## Module Design

- **Consolidation**: Group related functionality in focused modules
- **Documentation**: Include comments explaining non-obvious configurations
- **Sectioning**: Use comment headers to organize related configurations
- **Explicit Names**: Use descriptive names for options and files

## Types

- Use proper Nix types where applicable
- Ensure modules have proper option declarations and types

## Error Handling

- Validate inputs with assertions where appropriate
- Use `lib.mkIf` for conditional configurations

## NixOS-Specific Notes

- Use `/bin/sh` for script shebangs
- Prefer `fd` over `find` when possible
- Use `nh os test` to test configuration changes

## Consolidated Module Structure

- `system.nix`: Core system settings and packages
- `desktop-apps.nix`: GUI applications
- `media.nix`: Media players and utilities
- `development.nix`: Development tools and languages
- `system-utils.nix`: System utility programs

## Advanced Configuration Notes

- `internal/` contains some advanced configuration files, created by you, which for now I've reverted. These are for future reference. They may be out-of-sync/out-of-date with the repo proper.

