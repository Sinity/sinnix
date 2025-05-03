# Dotfiles

This directory contains configuration files (dotfiles) managed with GNU Stow.

## Available Packages

- **bat**: A cat clone with syntax highlighting
- **fzf**: Command-line fuzzy finder
- **git**: Git version control configuration
- **gtk**: GTK theme and cursor configuration
- **nvim**: Neovim text editor
- **ssh**: SSH client configuration (no keys)

## Structure

Each subdirectory represents a package/application with its configuration files. The directory structure inside each package mirrors the structure in your home directory.

Example:

```
dots/
├── nvim/
│   └── .config/
│       └── nvim/
│           ├── init.lua
│           └── ...
└── ...
```

## Usage

Use the `manage-dots.sh` script to deploy, remove, or collect dotfiles:

```bash
# Deploy all dotfiles
./manage-dots.sh deploy

# Deploy just Neovim config
./manage-dots.sh deploy nvim

# Remove Neovim config symlinks
./manage-dots.sh remove nvim

# Collect current Neovim config from your home directory
./manage-dots.sh collect nvim

# List available packages
./manage-dots.sh list
```

## Adding New Configurations

1. Create a new directory for your application:

   ```bash
   mkdir -p dots/app_name/.config/app_name
   ```

2. Copy configuration files, maintaining the same structure as in your home directory

   ```bash
   cp -r ~/.config/app_name/* dots/app_name/.config/app_name/
   ```

3. Update the `collect_package` function in `manage-dots.sh` to support your new package

4. Deploy using the script:

   ```bash
   ./manage-dots.sh deploy app_name
   ```

## Integration with NixOS Config

This dotfiles setup works alongside your NixOS configuration:

- **Static configs**: Managed through NixOS/home-manager
- **Frequently changed configs**: Managed as dotfiles with Stow
- **Sensitive configs**: Encrypted with agenix

When you want to switch from home-manager to dotfiles for a specific config, make sure to disable the home-manager module first to avoid conflicts.
