{ inputs, nixpkgs, self, username, host, ...}:
{
  imports = [
    ./bootloader.nix
    ./hardware.nix
    ./network.nix
    ./audio.nix
    ./security.nix
    ./services.nix
    ./system.nix
    ./storage.nix
    ./user.nix
    ./x.nix
    ./nginx.nix
  ];
}
