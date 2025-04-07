# Kitty Terminal Configuration

This directory contains the configuration files for the Kitty terminal emulator.

## Files

- `.config/kitty/kitty.conf` - Main configuration file
- `.config/kitty/themes/gruvbox_dark.conf` - Gruvbox Dark theme

## Installation

Use the `manage-dots.sh` script to deploy these dotfiles:

```bash
./manage-dots.sh deploy kitty
```

## Manual Installation

Alternatively, you can manually link these files:

```bash
mkdir -p ~/.config/kitty
ln -sf $(pwd)/.config/kitty/kitty.conf ~/.config/kitty/
ln -sf $(pwd)/.config/kitty/themes ~/.config/kitty/
```