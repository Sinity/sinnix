{ lib, pkgs, ... }:
{
  environment.etc."qdrant/config.yaml".text = ''
    log_level: "INFO"
    storage:
      storage_path: "/realm/data/qdrant/storage"
      snapshots_path: "/realm/data/qdrant/snapshots"
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

  systemd.services.qdrant = {
    description = "Qdrant vector search";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" ];
    serviceConfig = {
      Type = "simple";
      User = "qdrant";
      Group = "qdrant";
      ExecStart = "${pkgs.qdrant}/bin/qdrant --config-path /etc/qdrant/config.yaml";
      Restart = "on-failure";
      WorkingDirectory = "/realm/data/qdrant";
      RuntimeDirectory = "qdrant";
      LimitNOFILE = 1048576;
      ReadWritePaths = [
        "/realm/data/qdrant"
        "/realm/data/qdrant/storage"
        "/realm/data/qdrant/snapshots"
      ];
    };
  };

  systemd.tmpfiles.rules = lib.mkBefore [
    "d /realm/data/model 0750 sinity users -"
    "d /realm/data/qdrant 0750 qdrant qdrant -"
    "d /realm/data/qdrant/storage 0750 qdrant qdrant -"
    "d /realm/data/qdrant/snapshots 0750 qdrant qdrant -"
    "z /realm/data/qdrant 0750 qdrant qdrant - -"
    "z /realm/data/qdrant/storage 0750 qdrant qdrant - -"
    "z /realm/data/qdrant/snapshots 0750 qdrant qdrant - -"
  ];

  users.groups.qdrant = { };

  users.users.qdrant = {
    isSystemUser = true;
    group = "qdrant";
    home = "/var/lib/qdrant";
  };
}
