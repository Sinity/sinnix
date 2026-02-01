## Bundles (Presets)

Convenience wrappers in `modules/bundles/`:

- **desktop.nix**: Enables all desktop features + audio + UI in one toggle
- **dev.nix**: Enables all development tools

**Rule**: Bundles only **enable other modules**, never add their own config.

Example:
```nix
# modules/bundles/desktop.nix
config = lib.mkIf cfg.enable {
  sinnix = {
    features.desktop.audio.enable = true;
    features.desktop.ui.enable = true;
    features.desktop.hyprland.enable = true;
    features.desktop.browser.enable = true;
    # ... etc
  };
};
```
