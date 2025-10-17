{ inputs, lib, pkgs, ... }:
let
  dataRoot = "/realm/data";
  sinevecDataDir = "${dataRoot}/sinevec";
  sinevecStateDir = "${sinevecDataDir}/state";
  sinevecLogDir = "/var/log/sinevec";
  sinevecPkg = inputs.sinevec.packages.${pkgs.system}.sinevec;
in
{
  environment.systemPackages = [ sinevecPkg ];

  systemd.services.sinevec = {
    description = "Sinevec contextual embeddings API";
    after = lib.mkAfter [ "qdrant.service" ];
    wants = [ "qdrant.service" ];
    serviceConfig = {
      Type = "simple";
      User = "sinity";
      Group = "users";
      ExecStart = "${sinevecPkg}/bin/sinevec serve";
      Restart = "on-failure";
      RestartSec = 5;
      WorkingDirectory = sinevecDataDir;
      Environment = "PYTHONUNBUFFERED=1";
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
    "d ${dataRoot}/raindrop 0750 sinity users -"
    "d ${dataRoot}/chatlog 0750 sinity users -"
    "d ${sinevecDataDir} 0750 sinity users -"
    "d ${sinevecStateDir} 0750 sinity users -"
    "d ${sinevecLogDir} 0750 sinity users -"
  ];
}
