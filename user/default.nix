{ ... }:
{
  imports = [
    ./core.nix
    ./desktop
    ./dev/default.nix
    ./media.nix
    ./networking.nix
    ./crypto.nix
    ./storage.nix
    ./services
  ];
}
