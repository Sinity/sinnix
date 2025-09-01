# Services
# System services and daemons

{ pkgs, ... }:
{
  config = {
    services = {
      transmission = {
        enable = true;
        settings = {
          script-torrent-done-enabled = false;
          ratio-limit-enabled = false;
          umask = 18; # 002
          download-dir = "/outer-realm/inbox";
          incomplete-dir-enabled = false;
          rpc-port = 9091;
        };
      };

      ollama = {
        enable = false;
        acceleration = "cuda";
      };

      postgresql = {
        enable = true;
        package = pkgs.postgresql_16;

        # Install required extensions
        extensions = with pkgs.postgresql16Packages; [
          timescaledb
          pg_jsonschema # From Sinex overlay
          pgx_ulid
          pgvector
        ];

        # Configure PostgreSQL
        settings = {
          # Required for TimescaleDB
          shared_preload_libraries = "timescaledb";

          # Performance settings optimized for Sinex
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

          # Timeouts
          statement_timeout = "60s";
          lock_timeout = "30s";
          idle_in_transaction_session_timeout = "300s";

          # Logging
          log_statement = "mod";
          log_duration = true;
          log_min_duration_statement = "1000ms";
        };

        # Create database and user
        ensureDatabases = [ "sinex" ];
        ensureUsers = [
          {
            name = "sinex";
            ensureDBOwnership = true;
          }
        ];
      };
      # Temporarily disabled due to module conflicts
      # sinex = {
      # enable = true;
      # targetUser = "sinity";
      #   preset = "normal";
      #   blobStorage.repositoryPath = /realm/annex;
      #   blobStorage.healthCheck.wantedSize = null;
      #   unifiedCollector.logLevel = "debug";
      #   unifiedCollector.sources.kittyScrollback.captureOnCommand = true;
      #   unifiedCollector.sources.asciinema.autoRecord = true;
      #   unifiedCollector.sources.filesystem.watchPaths = [
      #     "/realm"
      #     "/home/sinity"
      #   ];
      #   # unifiedCollector.sources.filesystem.excludePatterns = [ ];
      # };
    };

    # User-level services
    home-manager.users.sinity = {
      # ActivityWatch - automatic time tracking
      services.activitywatch = {
        enable = true;
        package = pkgs.aw-server-rust;

        watchers = {
          awatcher = {
            package = pkgs.awatcher;
            settings = {
              idle-timeout-seconds = 60;
              poll-time-idle-seconds = 1;
              poll-time-window-seconds = 1;
            };
          };
        };
      };

      # User systemd services
      systemd.user = {
        services = {
          # Ensure ActivityWatch awatcher starts with graphical session
          activitywatch-watcher-awatcher =
            let
              target = "graphical-session.target";
            in
            {
              Unit = {
                After = [ target ];
                Requisite = [ target ];
                PartOf = [ target ];
              };
              Install = {
                WantedBy = [ target ];
              };
            };
        };
      };

      # ActivityWatch watchers packages
      home.packages = with pkgs; [
        aw-watcher-window-wayland
        aw-watcher-afk
      ];
    };
  };
}
