{ ... }:
{
  imports = [
    ./core.nix
    ./desktop
    ./dev/default.nix
    ./media.nix
    ./networking.nix
    ./monero.nix
    ./storage.nix
    ./services
  ];
}
