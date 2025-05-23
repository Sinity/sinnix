{
  ...
}:
{
  imports = [
    # Core configuration
    ./environment.nix # Shell environment configuration
    ./desktop # Desktop environment configuration (moved to interface domain)
    # ./ssh.nix # Moved to communication domain
    # ./git.nix # Moved to development domain
    # ./neovim.nix # Moved to development domain
    ./kitty.nix # Terminal emulator configuration (moved to interface domain)

    # Consolidated modules (new organization)
    ./system.nix # System utilities and tools
    # ./media.nix # Migrated to media domain
    # ./development.nix # Moved to development domain
    ./desktop-apps.nix # Desktop applications
    ./packages.nix # misc packages

    # Specialized modules
    # ./activity_watch.nix # Migrated to automation domain
    ./hydrus.nix # Hydrus with custom setup
    # ./scripts/scripts.nix # Migrated to automation domain
    ./xdg-mimes.nix # XDG config (moved to interface domain)

    # Currently disabled modules
    # ./enhanced-imv.nix # Image viewer with support of common formats
    # ./asbl-no-moar.nix # Migrated to automation domain
  ];
}
