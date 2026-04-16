## Common Workflows

### Rebuild System

```bash
cd /realm/project/sinnix
direnv allow                    # Activate devshell
check                          # Validate config
sudo nix run .#switch          # Apply changes
```

### Add New Feature

```bash
# 1. Create module
vim modules/features/desktop/new-feature.nix

# 2. Import in default.nix
vim modules/features/desktop/default.nix  # Add to imports

# 3. Enable in host or bundle
vim hosts/sinnix-prime/default.nix        # Add sinnix.features.desktop.new-feature.enable

# 4. Test
check && sudo nix run .#test

# 5. Update CLAUDE.md
vim CLAUDE.md  # Add to feature list
```

### Add New Package Overlay

```bash
# 1. Create overlay file
vim flake/overlay/package/my-package.nix

# 2. Add to overlay list
vim flake/overlay/package/default.nix  # Add to mkOverlay list

# 3. Test
nix build .#nixosConfigurations.sinnix-prime.config.system.build.toplevel
```

### Add New Script

```bash
# 1. Create script
vim scripts/my-script
chmod +x scripts/my-script

# 2. Add package wrapper
vim flake/packages.nix  # Add writeShellApplication entry

# 3. Test
nix run .#my-script
```
