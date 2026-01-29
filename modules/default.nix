{ ... }:
{
  imports = [
    ./core.nix
    ./diagnostics.nix
    ./foundation.nix
    ./home-manager.nix
    ./log-hygiene.nix
    ./networking.nix
    ./nix-ld.nix
    ./performance.nix
    ./secrets.nix
    ./storage.nix
    ./services/default.nix
    ./features/default.nix
    ./bundles/desktop.nix
    ./bundles/dev.nix
  ];
}
