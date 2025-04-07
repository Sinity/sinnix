# fzf Configuration

This directory contains configuration for fzf, a command-line fuzzy finder.

## Installation

Use the manage-dots.sh script to deploy this configuration:

```bash
./manage-dots.sh deploy fzf
```

## Configuration Files

- `fzf.conf`: Main configuration file with theme and behavior settings

To source this configuration, add the following to your shell config:

```bash
[ -f ~/.config/fzf.conf ] && source ~/.config/fzf.conf
```
