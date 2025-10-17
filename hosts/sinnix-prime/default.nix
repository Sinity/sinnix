{
  imports = [
    ./boot.nix
    ./hardware.nix
    ./storage.nix
    ./display.nix
    ../../modules/services/transmission.nix
    ../../modules/services/postgresql.nix
    ../../modules/services/photoprism.nix
    ../../modules/services/qdrant.nix
    ../../modules/services/sinevec.nix
  ];

}
