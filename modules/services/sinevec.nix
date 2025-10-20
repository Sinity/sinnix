{ inputs, lib, pkgs, ... }:
let
  dataRoot = "/realm/data";
  sinevecDataDir = "${dataRoot}/sinevec";
  sinevecStateDir = "${sinevecDataDir}/state";
  sinevecLogDir = "${sinevecDataDir}/logs";
  sinevecPkg = inputs.sinevec.packages.${pkgs.system}.sinevec;
  sinevecUser = "sinevec";
  sinevecGroup = "sinevec";
  username = "sinity";
in
{
  environment.systemPackages = [ sinevecPkg ];

  users.groups.${sinevecGroup} = {
    members = [ username ];
  };

  users.users.${sinevecUser} = {
    isSystemUser = true;
    group = sinevecGroup;
    description = "Service user for Sinevec contextual embeddings";
    home = sinevecDataDir;
    createHome = false;
    extraGroups = [ ];
  };

  systemd.services.sinevec = {
    description = "Sinevec contextual embeddings API";
    after = lib.mkAfter [ "qdrant.service" ];
    wants = [ "qdrant.service" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "simple";
      User = sinevecUser;
      Group = sinevecGroup;
      ExecStart = "${sinevecPkg}/bin/sinevec serve";
      Restart = "on-failure";
      RestartSec = 5;
      WorkingDirectory = sinevecDataDir;
      Environment = "PYTHONUNBUFFERED=1";
      CacheDirectory = "sinevec";
      LogsDirectory = "sinevec";
      ReadWritePaths = [
        sinevecDataDir
        sinevecStateDir
        sinevecLogDir
      ];
      RuntimeDirectory = "sinevec";
    };
    environment = {
      SINEVEC_DATA_ROOT = dataRoot;
      SINEVEC_STATE_DIR = sinevecStateDir;
      SINEVEC_LOG_DIR = sinevecLogDir;
      QDRANT_HOST = "127.0.0.1";
      QDRANT_HTTP_PORT = "6333";
      QDRANT_GRPC_PORT = "6334";
      QDRANT_USE_HTTPS = "0";
    };
  };

  systemd.tmpfiles.rules = [
    "d ${sinevecDataDir} 0750 ${sinevecUser} ${sinevecGroup} -"
    "d ${sinevecStateDir} 0750 ${sinevecUser} ${sinevecGroup} -"
    "d ${sinevecLogDir} 0750 ${sinevecUser} ${sinevecGroup} -"
  ];
}
