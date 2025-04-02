# Git Configuration

This directory contains Git configuration files that are managed with GNU Stow.

## Structure

```
git/
├── .config/
│   └── git/
│       └── config  # Main Git configuration file
└── README.md
```

## Features

- User identity configuration
- Delta integration for improved diffs
- Custom aliases for common Git operations
- Sensible defaults for merging and diffing

## Notes

- SSH configuration for Git is still managed by home-manager
- GitHub CLI (gh) is installed via home-manager packages

## Deployment

Deploy this configuration with:

```bash
./dots/manage-dots.sh deploy git
```