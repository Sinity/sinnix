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
    ./programs.nix
    ./secrets.nix
    ./storage.nix
    ./ui.nix
    ./users.nix
    ./services/default.nix
    ./features/default.nix
    ./bundles/desktop.nix
    ./bundles/dev.nix
  ];
}
