{
  config,
  lib,
  pkgs,
  inputs,
  ...
}:
let
  username = config.sinnix.user.name;
  defaultStateDir = "${config.sinnix.paths.dataRoot}/sinex";
  defaultLogsDir = "${defaultStateDir}/logs";
  defaultBlobRepo = "${defaultStateDir}/blob-repository";
  defaultDlqDir = "${defaultStateDir}/failures";
  sinexDotsDir = "${inputs.self}/dots/sinex";
  cfg = config.services.sinex;
  collectorConfigFile = pkgs.writeText "sinex-collector-placeholder.toml" ''
    # This file is managed by NixOS (modules/services/sinex.nix).
    # Sinex loads configuration through nixos_config.rs; this placeholder ensures
    # the expected configuration path exists for diagnostics.
  '';
in
{
  config = lib.mkMerge [
    {
      services.sinex = {
        enable = lib.mkDefault false;
        targetUser = lib.mkDefault username;
        logLevel = lib.mkDefault "info";

        directories = {
          state = lib.mkDefault defaultStateDir;
          logs = lib.mkDefault defaultLogsDir;
        };

        dlq = {
          enable = lib.mkDefault true;
          failureStoragePath = lib.mkDefault defaultDlqDir;
          maxRetries = lib.mkDefault 12;
          retryDelaySecs = lib.mkDefault 120;
          cleanup = {
            enable = lib.mkDefault true;
            maxAge = lib.mkDefault "45d";
            maxFiles = lib.mkDefault 50000;
          };
        };

        blobStorage = {
          enable = lib.mkDefault true;
          autoInit = lib.mkDefault true;
          repositoryPath = lib.mkDefault defaultBlobRepo;
          numCopies = lib.mkDefault 2;
          maintenance = {
            enableAutoGc = lib.mkDefault true;
            gcSchedule = lib.mkDefault "hourly";
            enablePeriodicFsck = lib.mkDefault true;
            fsckSchedule = lib.mkDefault "daily";
          };
          healthCheck = {
            enable = lib.mkDefault true;
            interval = lib.mkDefault 900;
            diskUsageWarning = lib.mkDefault 0.7;
            wantedSize = lib.mkDefault "750G";
          };
        };

        database = {
          package = lib.mkDefault pkgs.postgresql_16;
          listenAddress = lib.mkDefault "127.0.0.1";
          host = lib.mkDefault "127.0.0.1";
          port = lib.mkDefault 5432;
          name = lib.mkDefault "sinex";
          user = lib.mkDefault "sinex";
          monotonicUlids = lib.mkDefault true;
          connectionPool = {
            maxConnections = lib.mkDefault 64;
            minConnections = lib.mkDefault 4;
            idleTimeout = lib.mkDefault 600;
            connectionTimeout = lib.mkDefault 30;
          };
          healthCheck = {
            enable = lib.mkDefault true;
            interval = lib.mkDefault 60;
            timeout = lib.mkDefault 15;
          };
        };

        eventSources = {
          filesystem = {
            enable = lib.mkDefault true;
            watchPaths = lib.mkDefault [
              config.sinnix.paths.realmRoot
            ];
            excludePatterns = lib.mkDefault [
              "**/.git/**"
              "**/.cache/**"
              "**/node_modules/**"
              "**/tmp/**"
            ];
          };

          clipboard = {
            enable = lib.mkDefault true;
            monitorClipboard = lib.mkDefault true;
            monitorPrimary = lib.mkDefault true;
            monitorSecondary = lib.mkDefault false;
            enableHistory = lib.mkDefault true;
            hashFileContent = lib.mkDefault true;
            maxPreviewLength = lib.mkDefault 1024;
            maxContentSize = lib.mkDefault 1048576;
            pollInterval = lib.mkDefault 750;
          };

          dbus = {
            enable = lib.mkDefault true;
            monitorSystem = lib.mkDefault true;
            monitorSession = lib.mkDefault true;
            extractNotifications = lib.mkDefault true;
            extractHardware = lib.mkDefault true;
            extractNetwork = lib.mkDefault true;
            extractPower = lib.mkDefault true;
            extractMounts = lib.mkDefault true;
            extractMedia = lib.mkDefault true;
          };

          kitty = {
            enable = lib.mkDefault true;
            autoConfigureShellIntegration = lib.mkDefault true;
            autoModifyUserConfig = lib.mkDefault false;
            enableCommandCompletion = lib.mkDefault true;
            pollInterval = lib.mkDefault 2;
            scrollbackSafetyNetInterval = lib.mkDefault 900;
            maxScrollbackLines = lib.mkDefault 20000;
            userConfigPath = lib.mkDefault "${sinexDotsDir}/kitty-ingestor.toml";
          };

          kittyScrollback = {
            enable = lib.mkDefault true;
            pollInterval = lib.mkDefault 5;
            captureInterval = lib.mkDefault 30;
            maxScrollbackLines = lib.mkDefault 40000;
            socketPath = lib.mkDefault "/run/user/%i/kitty";
          };

          shellHistory = {
            enable = lib.mkDefault true;
            bashPath = lib.mkDefault "/home/${username}/.bash_history";
            zshPath = lib.mkDefault "/home/${username}/.local/state/zsh/history";
          };

          asciinema = {
            enable = lib.mkDefault true;
            autoRecord = lib.mkDefault true;
            autoAnnex = lib.mkDefault true;
            path = lib.mkDefault "/home/${username}/.local/share/asciinema";
          };

          atuin = {
            enable = lib.mkDefault true;
            databasePath = lib.mkDefault "/home/${username}/.local/share/atuin/history.db";
            pollInterval = lib.mkDefault 30;
          };
        };

        monitoring = {
          enable = lib.mkDefault true;
          logging = {
            level = lib.mkDefault "debug";
            structured = lib.mkDefault true;
            retention = {
              maxAge = lib.mkDefault "30d";
              maxFiles = lib.mkDefault 200;
              maxSize = lib.mkDefault "5G";
            };
            performance = {
              enable = lib.mkDefault true;
              slowQueryThreshold = lib.mkDefault 200;
              traceRequests = lib.mkDefault true;
            };
          };
          alerting = {
            enable = lib.mkDefault true;
            healthAlerts = {
              serviceDown = {
                enable = lib.mkDefault true;
                threshold = lib.mkDefault "2m";
              };
              databaseConnections = {
                enable = lib.mkDefault true;
                maxConnectionsPercent = lib.mkDefault 0.75;
              };
              highErrorRate = {
                enable = lib.mkDefault true;
                threshold = lib.mkDefault 0.03;
              };
            };
            resourceAlerts = {
              highCpuUsage = {
                enable = lib.mkDefault true;
                threshold = lib.mkDefault 0.7;
              };
              highMemoryUsage = {
                enable = lib.mkDefault true;
                threshold = lib.mkDefault 0.85;
              };
              diskSpaceUsage = {
                enable = lib.mkDefault true;
                threshold = lib.mkDefault 0.8;
              };
            };
          };
          prometheus = {
            enable = lib.mkDefault true;
            scrapeInterval = lib.mkDefault "15s";
            metricsPrefix = lib.mkDefault "sinex";
          };
          observabilityStack = {
            enable = lib.mkDefault true;
            listenAddress = lib.mkDefault "127.0.0.1";
            grafanaPort = lib.mkDefault 30900;
            prometheusPort = lib.mkDefault 30901;
            retentionTime = lib.mkDefault "30d";
          };
          dashboards = {
            enable = lib.mkDefault true;
            grafana.enable = lib.mkDefault true;
          };
        };

        resources = {
          gateway.cpuQuota = lib.mkDefault "400%";
          gateway.memoryMax = lib.mkDefault "12G";
          ingestd.cpuQuota = lib.mkDefault "600%";
          ingestd.memoryMax = lib.mkDefault "24G";
          defaultSatellite.cpuQuota = lib.mkDefault "200%";
          defaultSatellite.memoryMax = lib.mkDefault "8G";
        };

        services.enhancementMode = lib.mkDefault "full";

        preflightVerification = {
          enable = lib.mkDefault true;
          failureAction = lib.mkDefault "abort";
          recordResults = lib.mkDefault true;
          requiredUnits = lib.mkDefault [
            "postgresql.service"
            "qdrant.service"
          ];
          notifications = {
            enable = lib.mkDefault true;
            onFailure = lib.mkDefault true;
            onSuccess = lib.mkDefault false;
          };
          timeout = lib.mkDefault 900;
        };

        update = {
          enable = lib.mkDefault true;
          gracePeriod = lib.mkDefault 300;
          rollbackOnFailure = lib.mkDefault true;
          preserveData = lib.mkDefault true;
        };

        security = {
          level = lib.mkDefault "strict";
          allowFileSystemAccess = lib.mkDefault true;
          allowSocketAccess = lib.mkDefault true;
          audit = {
            enable = lib.mkDefault true;
            logLevel = lib.mkDefault "info";
            retentionDays = lib.mkDefault 60;
          };
        };
      };
    }

    (lib.mkIf cfg.enable {
      systemd.tmpfiles.rules = [
        "d ${cfg.directories.state} 0755 ${cfg.database.user} ${cfg.database.user} -"
        "d ${cfg.directories.logs} 0755 ${cfg.database.user} ${cfg.database.user} -"
      ]
      ++ lib.optionals (cfg.dlq.enable or false) [
        "d ${cfg.dlq.failureStoragePath} 0755 ${cfg.database.user} ${cfg.database.user} -"
      ]
      ++ lib.optionals (cfg.blobStorage.enable or false) [
        "d ${cfg.blobStorage.repositoryPath} 0755 ${cfg.database.user} ${cfg.database.user} -"
      ];

      environment.systemPackages = lib.mkAfter (
        lib.optional (cfg ? cliPackage && cfg.cliPackage != null) cfg.cliPackage
      );

      environment.etc."sinex/collector.toml".source = collectorConfigFile;
    })
  ];
}
