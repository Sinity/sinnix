{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.services;
in
{
  options.sinnix.services = {
    transmission.enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable the Transmission BitTorrent service.";
    };

    postgresql.enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable the PostgreSQL instance with TimescaleDB extensions.";
    };

    photoprism.enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable the Photoprism photo management service.";
    };

    qdrant.enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable the Qdrant vector database service.";
    };
  };

  config = lib.mkMerge [
    (lib.mkIf cfg.transmission.enable {
      services.transmission = {
        enable = true;
        openFirewall = false;
        settings = {
          script-torrent-done-enabled = false;
          ratio-limit-enabled = false;
          umask = 18;
          download-dir = "/outer-realm/inbox";
          incomplete-dir-enabled = false;
          rpc-enabled = true;
          rpc-bind-address = "127.0.0.1";
          rpc-port = 9091;
          rpc-authentication-required = false;
        };
      };
    })

    (lib.mkIf cfg.postgresql.enable {
      services.postgresql = {
        enable = true;
        package = pkgs.postgresql_16;
        extensions =
          let
            dbPkgs = pkgs.postgresql16Packages;
          in
          with dbPkgs;
          [
            timescaledb
          ]
          ++ lib.optional (dbPkgs ? pg_jsonschema) dbPkgs.pg_jsonschema
          ++ [
            pgx_ulid
            pgvector
          ];
        settings = {
          listen_addresses = "localhost";
          shared_preload_libraries = "timescaledb";
          max_connections = 200;
          shared_buffers = "256MB";
          effective_cache_size = "1GB";
          maintenance_work_mem = "256MB";
          checkpoint_completion_target = 0.9;
          wal_buffers = "16MB";
          default_statistics_target = 100;
          random_page_cost = 1.1;
          effective_io_concurrency = 200;
          max_prepared_transactions = 256;
          statement_timeout = "60s";
          lock_timeout = "30s";
          idle_in_transaction_session_timeout = "300s";
          log_statement = "mod";
          log_duration = true;
          log_min_duration_statement = "1000ms";
        };
        authentication = ''
          local   all             all                                     peer
          host    all             all             0.0.0.0/0               reject
          host    all             all             ::/0                    reject
        '';
        ensureDatabases = [ "sinex" ];
        ensureUsers = [
          {
            name = "sinex";
            ensureDBOwnership = true;
          }
        ];
      };
    })

    (lib.mkIf cfg.photoprism.enable {
      services.photoprism = {
        enable = true;
        originalsPath = "/realm/data/media/originals";
        importPath = "/realm/data/media/import";
        storagePath = "/realm/data/media/photoprism";
        passwordFile = "/run/agenix/photoprism-admin-password";
        settings = {
          PHOTOPRISM_ADMIN_USER = "sinity";
          PHOTOPRISM_SITE_CAPTION = "Realm Library";
          PHOTOPRISM_DISABLE_FACES = "false";
          PHOTOPRISM_DISABLE_CLASSIFICATION = "false";
        };
      };

      systemd.tmpfiles.rules = lib.mkBefore [
        "d /realm/data/media 0755 sinity users -"
        "d /realm/data/media/originals 2770 photoprism users -"
        "d /realm/data/media/import 2770 photoprism users -"
        "d /realm/data/media/photoprism 2770 photoprism photoprism -"
      ];

      users.groups.photoprism = { };
      users.users.photoprism = {
        isSystemUser = true;
        group = "photoprism";
        home = "/var/lib/photoprism";
        extraGroups = [ "users" ];
      };
    })

    (lib.mkIf cfg.qdrant.enable {
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
      ];

      users.groups.qdrant = { };
      users.users.qdrant = {
        isSystemUser = true;
        group = "qdrant";
        home = "/var/lib/qdrant";
      };
    })
  ];
}
