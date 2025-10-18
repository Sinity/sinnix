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
  ];

  services.sinex = {
    enable = false;
    targetUser = "sinity";
    directories = {
      state = "/realm/data/sinex";
      logs = "/realm/data/sinex/logs";
    };
    dlq.failureStoragePath = "/realm/data/sinex/failures";
    satellite.enable = false;
  };
}
