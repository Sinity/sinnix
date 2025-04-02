# Zsh Configuration

This directory contains Zsh configuration files managed with GNU Stow.

## Structure

```
zsh/
├── .zshrc        # Main Zsh configuration
├── .zshenv       # Environment variables for all shells
└── .config/
    └── zsh/      # Additional Zsh configuration files
```

## Features

- Oh-My-Zsh integration
- Custom aliases for common commands
- FZF integration with fd for better file finding
- Terminal title customization
- Vi-mode keybindings

## Dependencies

The following tools are installed via home-manager:
- zoxide (better directory navigation)
- eza (better ls)
- bat (better cat)
- fd (better find)
- fzf (fuzzy finder)

## Deployment

Deploy this configuration with:

```bash
./dots/manage-dots.sh deploy zsh
```