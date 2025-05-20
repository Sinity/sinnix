{
  inputs,
  nixpkgs,
  self,
  username,
  host,
  ...
}:
{
  imports = [
    # Host-specific modules have been moved to host/desktop/
    # ./bootloader.nix
    # ./hardware.nix
    # ./audio.nix
    # ./storage.nix
    # ./x.nix

    # Core modules that remain
    ./network.nix
    ./security.nix
    ./services.nix
    ./system.nix
    ./user.nix
    ./nginx.nix
    ./nix-ld.nix
  ];
}
