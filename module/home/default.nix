{
  ...
}:
{
  imports = [
    # Core configuration
    ../shell # Shell environment configuration
    ../desktop # Desktop environment configuration
    ./git.nix
    ./ssh.nix
    ./neovim.nix # Manual symlink-based neovim config

    # Consolidated modules (new organization)
    ./system.nix # System utilities and tools
    ./media.nix # Media applications and players
    ./development.nix # Development tools and languages
    ./desktop-apps.nix # Desktop applications
    ./packages.nix # misc packages

    # Specialized modules
    ./activity_watch.nix # Self-inflicted telemetry
    ./hydrus.nix # Hydrus with custom setup
    ./scripts/scripts.nix # Personal scripts
    ./xdg-mimes.nix # XDG config (possibly unnecessary)

    # Currently disabled modules
    # ./enhanced-imv.nix # Image viewer with support of common formats
    # ./asbl-no-moar.nix # Wayland gamma poke for ASBL mitigation
  ];
}
