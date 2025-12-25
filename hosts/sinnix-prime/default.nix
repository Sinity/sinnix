{ ... }:
{
  imports = [
    ./boot.nix
    ./input.nix
    ./storage.nix
    ./display.nix
    ../../modules/services/transmission.nix
    ../../modules/services/qdrant.nix
    ../../modules/services/sinevec.nix
    ../../modules/services/asciinema.nix
    ../../modules/services/sinex.nix
    ../../modules/services/polylogue.nix
  ];

  networking.hostName = "sinnix-prime";
  sinnix.machine.isDesktop = true;

  services.polylogue-watch.enable = true;
}
