{ ... }:
{
  imports = [
    ./core.nix
    ./desktop
    ./bitcoin.nix
    ./dev/default.nix
    ./media.nix
    ./networking.nix
    ./monero.nix
    ./storage.nix
    ./services
  ];
}
