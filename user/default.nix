{ ... }:
{
  imports = [
    ./core.nix
    ./desktop
    ./dev/default.nix
    ./media.nix
    ./networking.nix
    ./storage.nix
  ];
}
