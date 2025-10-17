{
  imports = [
    ./boot.nix
    ./input.nix
    ./storage.nix
    ./display.nix
    ../../modules/services/postgresql.nix
    ../../modules/services/transmission.nix
    ../../modules/services/photoprism.nix
    ../../modules/services/qdrant.nix
    ../../modules/services/sinevec.nix
  ];

  services.sinex = {
    enable = false;
    targetUser = "sinity";
    database.additionalUsers = [
      {
        name = "sinity";
        ensureClauses = {
          login = true;
          createdb = true;
        };
      }
    ];
  };
}
