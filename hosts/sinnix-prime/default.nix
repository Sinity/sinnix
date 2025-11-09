{ ... }:
{
  imports = [
    ./boot.nix
    ./input.nix
    ./storage.nix
    ./display.nix
    ../../modules/services/transmission.nix
    ../../modules/services/photoprism.nix
    ../../modules/services/qdrant.nix
    ../../modules/services/sinevec.nix
    ../../modules/services/sinex.nix
  ];

  networking.hostName = "sinnix-prime";
  sinnix.machine.isDesktop = true;
}
