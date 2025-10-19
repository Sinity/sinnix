{ username, ... }:
let
  dataRoot = "/realm";
in
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
    targetUser = username;
    directories = {
      state = "${dataRoot}/data/sinex";
      logs = "${dataRoot}/data/sinex/logs";
    };
    dlq.failureStoragePath = "${dataRoot}/data/sinex/failures";
    satellite.enable = false;
  };
}
