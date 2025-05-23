_: {
  imports = [
    # ./network.nix # Moved to communication domain
    ./security.nix
    # ./services.nix # Migrated to automation domain
    ./system.nix
    ./user.nix
    # ./nix-ld.nix # Moved to development domain
    # ../service/nginx.nix # Moved to communication domain
  ];
}
