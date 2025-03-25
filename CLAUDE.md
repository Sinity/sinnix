# Development Guidelines for NixOS Config

## Commands
- `nix-switch` - Apply NixOS configuration (alias for `nh os switch`)
- `nix-update` - Update and apply configuration (alias for `nh os switch --update`)
- `nix-test` - Test configuration (alias for `nh os test`)
- `nix-clean` - Clean up old generations (alias for `nh clean all --keep 5`)

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