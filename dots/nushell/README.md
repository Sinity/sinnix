# Nushell Configuration

This directory contains configuration files for [Nushell](https://www.nushell.sh/), a modern shell designed to handle structured data.

## Contents

- **config.nu**: Main configuration with aliases, custom functions, and hooks
- **env.nu**: Environment variables and basic shell settings
- **zoxide.nu, starship.nu, atuin.nu**: modules for respective utilities

## Features

- Customized prompt with terminal title updating
- Quality-of-life aliases for common commands
- NixOS-specific command shortcuts
- Integration with external tools:
  - atuin (shell history)
  - starship (prompt)
  - zoxide (directory navigation)

## Usage

This configuration is managed with GNU Stow. Deploy using:

```bash
./manage-dots.sh deploy nushell
```

## Integration

Modules zoxide.nu, starship.nu, atuin.nu were generated with the following commands:

```nushell
zoxide init nushell | save -f ~/.config/nushell/zoxide.nu
starship init nu | save -f starship.nu
atuin init nu | save -f atuin.nu
```

## NixOS Integration Notes

- Some integrations like zoxide or starship are configured via home-manager
