{ lib, pkgs, config, ... }:
let
  username = config.sinnix.user.name;
  inherit (config.sinnix.paths) dataRoot;
  qdrantDataDir = "${dataRoot}/qdrant";
in
{
  environment.etc."qdrant/config.yaml".text = ''
    log_level: "INFO"
    storage:
      storage_path: "${qdrantDataDir}/storage"
      snapshots_path: "${qdrantDataDir}/snapshots"
      on_disk_payload: true
    service:
      api:
        enabled: true
        bind_endpoint: "127.0.0.1:6333"
      grpc:
        enabled: true
        bind_endpoint: "127.0.0.1:6334"
    cluster:
      enabled: false
    telemetry:
      disabled: true
  '';

  users = {
    groups.qdrant.members = [ username ];

    users.qdrant = {
      isSystemUser = true;
      group = "qdrant";
      home = "/var/lib/qdrant";
    };
  };

  systemd = {
    services.qdrant = {
      description = "Qdrant vector search";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      serviceConfig = {
        Type = "simple";
        User = "qdrant";
        Group = "qdrant";
        ExecStart = "${pkgs.qdrant}/bin/qdrant --config-path /etc/qdrant/config.yaml";
        Restart = "on-failure";
        WorkingDirectory = qdrantDataDir;
        RuntimeDirectory = "qdrant";
        LimitNOFILE = 1048576;
        ReadWritePaths = [
          qdrantDataDir
          "${qdrantDataDir}/storage"
          "${qdrantDataDir}/snapshots"
        ];
      };
      unitConfig.RequiresMountsFor = [ qdrantDataDir ];
    };

    tmpfiles.rules = lib.mkBefore [
      "d ${qdrantDataDir} 0750 qdrant qdrant -"
      "d ${qdrantDataDir}/storage 0750 qdrant qdrant -"
      "d ${qdrantDataDir}/snapshots 0750 qdrant qdrant -"
      "z ${qdrantDataDir} 0750 qdrant qdrant - -"
      "z ${qdrantDataDir}/storage 0750 qdrant qdrant - -"
      "z ${qdrantDataDir}/snapshots 0750 qdrant qdrant - -"
    ];
  };
}
