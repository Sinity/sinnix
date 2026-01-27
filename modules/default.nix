{ ... }:
{
  imports = [
    ./audio.nix
    ./core.nix
    ./diagnostics.nix
    ./foundation.nix
    ./home-manager.nix
    ./logging.nix
    ./networking.nix
    ./nix-ld.nix
    ./performance.nix
    ./secrets.nix
    ./storage.nix
    ./ui.nix
    ./services/default.nix
    ./features/default.nix
    ./bundles/desktop.nix
    ./bundles/dev.nix
  ];
}
