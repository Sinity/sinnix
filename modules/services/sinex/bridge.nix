# Sinex upstream bridge
#
# This module carries the heavy integration with the upstream `services.sinex`
# option tree. Keep it opt-in so the generic sinnix module graph does not pay
# for Sinex evaluation when the host does not import the upstream module.
{
  config,
  options,
  pkgs,
  lib,
  inputs,
  ...
}:
let
  cfg = config.sinnix.services.sinex;
  inherit (config.sinnix.paths) realmRoot;
  mkSinexPkgs = pkgs': inputs.sinex.packages.${pkgs'.stdenv.hostPlatform.system};
  sinexEnvironment = lib.toLower cfg.environment;
  targetUserName = config.sinnix.user.name;
  targetUserHome = "/home/${targetUserName}";
  databaseHost = "127.0.0.1";
  databasePort = 5432;
  databaseUser = "sinex";
  databaseName = "sinex_${sinexEnvironment}";
  databasePasswordFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-local-db" ] null config;
  hostPrepared = cfg.prepareHost || cfg.enable || cfg.provisionDatabase;
  runtimeEnabled = cfg.enable;
  databasePrepared = cfg.provisionDatabase || cfg.enable;
  sinexRuntimeStartDelay = "90s";
in
{
  config = lib.mkIf (options.services ? sinex) (
    let
      activationProfile =
        {
          foundation = {
            filesystem = true;
            terminal = false;
            browser = false;
            desktop = false;
            system = true;
            document = false;
            automata = false;
            canonicalizer = false;
            healthAggregator = false;
            kitty = false;
          };
          capture = {
            filesystem = true;
            terminal = true;
            browser = true;
            desktop = false;
            system = true;
            document = true;
            automata = true;
            canonicalizer = true;
            healthAggregator = true;
            kitty = true;
          };
          full = {
            filesystem = true;
            terminal = true;
            browser = true;
            desktop = true;
            system = true;
            document = true;
            automata = true;
            canonicalizer = true;
            healthAggregator = true;
            kitty = true;
          };
        }
        .${cfg.activationProfile};
      filesystemWatchPaths = [
        "${realmRoot}/project"
        "${realmRoot}/inbox/download"
        "${realmRoot}/inbox/polylogue_scratch"
      ];
      generatedNodeServices = lib.optionals runtimeEnabled (config.sinex._generatedUnits or [ ]);
      documentScanEnabled =
        runtimeEnabled
        && lib.attrByPath [ "services" "sinex" "nodes" "document" "enable" ] false config;
      kittyAutoConfigureEnabled =
        runtimeEnabled
        && lib.attrByPath [ "services" "sinex" "shell" "kitty" "enable" ] false config
        && lib.attrByPath [ "services" "sinex" "shell" "kitty" "autoConfigure" ] false config;
      delayedRuntimeServices = lib.unique (
        lib.optionals databasePrepared [
          "postgresql"
          "postgresql-setup"
          "sinex-schema-apply"
        ]
        ++ lib.optionals runtimeEnabled [
          "nats"
          "sinex-nats-bootstrap"
          "sinex-blob-init"
          "sinex-preflight"
          "sinex-tls-init"
          "sinex-ingestd"
          "sinex-gateway"
        ]
        ++ generatedNodeServices
        ++ lib.optionals documentScanEnabled [ "sinex-document-scan" ]
        ++ lib.optionals kittyAutoConfigureEnabled [ "sinex-kitty-setup" ]
      );
      delayedRuntimeTargets = lib.optionals databasePrepared [ "postgresql" ];
      delayedRuntimeUnits =
        map (name: "${name}.service") delayedRuntimeServices
        ++ map (name: "${name}.target") delayedRuntimeTargets;
      mkScopedSinexPackage =
        sinexPkgs:
        pkgs.symlinkJoin {
          name = "sinex-runtime-${sinexEnvironment}";
          paths = lib.unique (
            lib.optionals runtimeEnabled [
              # Use the upstream aggregate runtime so Nix builds Sinex once for
              # deployment. Selecting per-node packages here reintroduces one
              # SQLx/Postgres build derivation per service.
              sinexPkgs.sinex
            ]
            ++ lib.optionals (!runtimeEnabled && databasePrepared) [ sinexPkgs.xtask ]
          );
        };
    in
    lib.mkMerge [
      (lib.mkIf (!runtimeEnabled) {
        services.sinex = {
          secrets.enableAgenix = lib.mkDefault false;
          core.enable = lib.mkDefault false;
          nodes.enable = lib.mkDefault false;
          nats.enable = lib.mkDefault false;
          nats.autoSetup = lib.mkDefault false;
          observability.enable = lib.mkDefault false;
          shell.kitty.enable = lib.mkDefault false;
          storage = {
            blob = {
              enable = lib.mkDefault false;
              autoInit = lib.mkDefault false;
            };
          };
          lifecycle = {
            preflight.enable = lib.mkDefault false;
            maintenance.enable = lib.mkDefault false;
            updates.enable = lib.mkDefault false;
          };
        };
      })

      (lib.mkIf hostPrepared (
        let
          sinexPkgs = mkSinexPkgs pkgs;
        in
        {
          services.sinex.package = lib.mkDefault (mkScopedSinexPackage sinexPkgs);
          services.sinex.cliPackage = lib.mkDefault (
            if runtimeEnabled then sinexPkgs.sinex else sinexPkgs.sinexctl
          );
          services.sinex.users.target = targetUserName;
          sinex.secrets.paths = lib.mkForce (
            lib.mapAttrs (_: path: toString path) (
              lib.filterAttrs (
                name: _: lib.hasPrefix "sinex-" name || lib.hasPrefix "nats-" name
              ) config.sinnix.secrets.paths
            )
          );

          users.users.sinex = {
            home = lib.mkForce "/var/lib/sinex";
            createHome = lib.mkForce true;
            extraGroups = lib.optionals (cfg.provisionDatabase || cfg.enable) [ "postgres" ];
          };
        }
      ))

      (lib.mkIf hostPrepared {
        services.sinex = {
          enable = runtimeEnabled;

          secrets = {
            enableAgenix = false;
          };
          nats = {
            environment = sinexEnvironment;
            enable = runtimeEnabled;
            autoSetup = runtimeEnabled;
            dataDir = "/var/lib/nats";
            # JetStream on the dedicated NVMe cache partition so its
            # sustained write load (message store + index compaction) does
            # not compete with system and interactive I/O on the root volume.
            storeDir = "/cache/nats/jetstream";
          };

          stateRoot = "/var/lib/sinex/.local/state/sinex";

          database = {
            enable = databasePrepared;
            autoSetup = databasePrepared;
            host = databaseHost;
            port = databasePort;
            name = databaseName;
            user = databaseUser;
          };

          core = {
            enable = runtimeEnabled;
            gateway = {
              enable = runtimeEnabled;
              autoGenerateTls = true;
            };
          };

          storage = {
            blob = {
              enable = runtimeEnabled;
              autoInit = runtimeEnabled;
            };
          };

          lifecycle = {
            preflight.enable = runtimeEnabled;
            maintenance.enable = runtimeEnabled;
            updates.enable = runtimeEnabled;
          };

          nodes = {
            enable = runtimeEnabled;

            filesystem = {
              enable = runtimeEnabled && activationProfile.filesystem;
              watchPaths = filesystemWatchPaths;
            };

            terminal = {
              enable = runtimeEnabled && activationProfile.terminal;
              historySources = [
                {
                  path = "${targetUserHome}/.local/share/atuin/history.db";
                  shell = "atuin";
                }
              ];
            };

            browser = {
              enable = runtimeEnabled && activationProfile.browser;
            };

            desktop = {
              enable = runtimeEnabled && activationProfile.desktop;
              clipboard.enable = false;
            };

            system = {
              enable = runtimeEnabled && activationProfile.system;
            };

            document = {
              enable = runtimeEnabled && activationProfile.document;
            };

            automata = {
              enable = runtimeEnabled && activationProfile.automata;
              canonicalizer.enable = runtimeEnabled && activationProfile.canonicalizer;
              healthAggregator.enable = runtimeEnabled && activationProfile.healthAggregator;
            };
          };

          observability = {
            enable = runtimeEnabled;
            monitoring = {
              enable = false;
              prometheus.enable = false;
              grafana.enable = false;
              exporters = {
                node = false;
                postgres = false;
                nats = false;
              };
            };
          };

          shell.kitty = {
            enable = runtimeEnabled && activationProfile.kitty;
            autoConfigure = runtimeEnabled && activationProfile.kitty;
          };
        };
      })

      (lib.mkIf runtimeEnabled {
        # Sinex is a capture runtime, not a boot prerequisite for the desktop.
        # Start the stack shortly after boot through an explicit target so
        # PostgreSQL/schema apply/NATS/node startup cannot hold graphical.target.
        # Strip both direct services and the postgresql.target install surface;
        # otherwise local PostgreSQL still leaks into multi-user.target.
        systemd.services = lib.genAttrs delayedRuntimeServices (_: {
          wantedBy = lib.mkForce [ ];
        }) // {
          # Cap NATS memory so JetStream cannot push the system into swap.
          # Peak observed: 3.4 GB with 484 MB swapped — the 1 GB cap keeps
          # it in RAM and lets earlyoom prefer-kill it before the desktop
          # feels pressure. IOWeight=10 ensures its sustained writes don't
          # compete fairly with interactive I/O.
          nats.serviceConfig = {
            MemoryMax = "1G";
            IOWeight = 10;
          };

          # Restrict PostgreSQL from consuming all system memory and I/O bandwidth,
          # preventing page-cache thrashing and system lockups on heavy analytical queries.
          postgresql.serviceConfig = {
            MemoryHigh = "8G";
            IOWeight = 10;
          };
        };
        systemd.targets =
          lib.genAttrs delayedRuntimeTargets (_: {
            wantedBy = lib.mkForce [ ];
          })
          // {
            sinex-runtime = {
              description = "Start Sinex runtime after interactive boot";
              wants = delayedRuntimeUnits ++ [ "network-online.target" ];
              after = [
                "multi-user.target"
                "graphical.target"
                "network-online.target"
              ];
            };
          };
        systemd.timers.sinex-runtime = {
          description = "Delay Sinex runtime startup until after boot";
          wantedBy = [ "timers.target" ];
          timerConfig = {
            OnBootSec = sinexRuntimeStartDelay;
            AccuracySec = "15s";
            Unit = "sinex-runtime.target";
          };
        };

        # NATS JetStream lives on the /cache NVMe partition. Ensure the
        # directory exists before the service starts so the auto-setup
        # bootstrap doesn't race with fs init.
        systemd.tmpfiles.rules = [
          "d /cache/nats 0750 nats nats -"
        ];
      })

      (lib.mkIf
        (
          cfg.provisionDatabase
          && databasePasswordFile != null
          && config.services.sinex.database.localAuth != "trust"
        )
        {
          # Delay postgresql-setup until agenix has materialized the password file.
          systemd.services.postgresql-setup.unitConfig.ConditionPathIsReadable = [
            databasePasswordFile
          ];
        }
      )

    ]
  );
}
