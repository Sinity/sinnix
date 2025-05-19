# Development Guidelines for NixOS Config

## Commands

- `sudo nix run .#switch` - Apply NixOS configuration with nix-output-monitor
- `nix run .#update` - Update flake inputs only (requires switch to apply)
- `sudo nix run .#test` - Test configuration with nix-output-monitor
- `sudo nix run .#clean` - Clean up old generations
- `nix run .#format` - Format all Nix files
- `nix run .#check` - Validate configuration files (default command)
- `nix run .#lint` - Run statix linter
- `nix run .#agenix` - Run agenix commands for secret management

You can also use `nix run` without specifying an app to run the default check command.

Note: Commands that modify the system configuration (`switch`, `test`, `clean`) require root privileges and must be run with sudo.

## Module Structure

- **Core Modules**: System-level configuration in `module/core/`
- **Home Modules**: User-level configuration in `module/home/`

## Neovim Configuration

- Neovim config lives in `/nvim/` directory
- Symlinks created via home-manager in `module/home/neovim.nix`

## Secrets Management

- Uses `agenix` for secret management
  - Encryption rules in `.agenix.toml` (defines public keys and paths)
  - Runtime handling in `module/core/security.nix` (automatic discovery)
- Manage secrets with: `nix run .#agenix [options]`
  - Encrypt: `nix run .#agenix -- -e secret/new-secret.age`
  - Decrypt: `nix run .#agenix -- -d secret/existing-secret.age`

### Adding a New Secret

1. Create the encrypted file: `nix run .#agenix -- -e secret/new-secret.age`
2. Rebuild your system with `sudo nix run .#switch`

That's it! Secrets are automatically discovered from the `secret/` directory, and environment variables are created following the pattern: `dash-case-name.age` → `DASH_CASE_NAME`.

## Code Style

- **Formatting**: Use nixfmt-rfc-style for Nix files formatting
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
- Use `nix run .#test` to test configuration changes

## Consolidated Module Structure

- `system.nix`: Core system settings and packages
- `desktop-apps.nix`: GUI applications
- `media.nix`: Media players and utilities
- `development.nix`: Development tools and languages
- `system-utils.nix`: System utility programs

## Development Workflow

### Development Environment

A development shell with all necessary tools is available:

```bash
# Start the development shell manually
nix develop

# Alternatively, use direnv for automatic environment activation
# (requires direnv to be installed and hooked into your shell)
direnv allow
```

Using direnv automatically activates the same development environment as `nix develop` when you enter the directory, without having to manually enter the shell each time.

### Available Development Tools

- **nixfmt-rfc-style**: Format Nix files
- **statix**: Lint Nix files for common issues
- **deadnix**: Find and remove dead/unused Nix code
- **nixd**: Nix language server
- **pre-commit**: Run git hooks automatically
- **agenix**: Secret management
- **nix-output-monitor (nom)**: Better Nix build output visualization

### Git Hooks

Git hooks are automatically installed when using the development shell. They perform:

#### Pre-commit hooks

The project uses git-hooks.nix for Nix-based hook management, which provides:

- Nix code formatting with nixfmt-rfc-style
- Nix code linting with statix
- Dead/unused Nix code detection with deadnix
- Shell script checking with shellcheck

These hooks are installed automatically when you enter the development environment and run on each commit.

You can manually run the hooks with: `pre-commit run --all-files`

### Development Workflow

1. Make your changes
2. Format code with `nix run .#format`
3. Lint code with `nix run .#lint`
4. Validate with `nix run .#check`
5. Test locally with `sudo nix run .#test`
6. Switch to the new configuration with `sudo nix run .#switch`

