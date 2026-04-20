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
      mkScopedSinexPackage =
        sinexPkgs:
        pkgs.symlinkJoin {
          name = "sinex-runtime-${sinexEnvironment}";
          paths = lib.unique (
            lib.optionals databasePrepared [ sinexPkgs.xtask ]
            ++ lib.optionals runtimeEnabled [
              sinexPkgs.sinex-ingestd
              sinexPkgs.sinex-gateway
              sinexPkgs.sinex-node-sdk
            ]
            ++ lib.optionals (runtimeEnabled && activationProfile.filesystem) [ sinexPkgs.sinex-fs-ingestor ]
            ++ lib.optionals (runtimeEnabled && activationProfile.terminal) [
              sinexPkgs.sinex-terminal-ingestor
            ]
            ++ lib.optionals (runtimeEnabled && activationProfile.browser) [ sinexPkgs.sinex-browser-ingestor ]
            ++ lib.optionals (runtimeEnabled && activationProfile.desktop) [ sinexPkgs.sinex-desktop-ingestor ]
            ++ lib.optionals (runtimeEnabled && activationProfile.system) [ sinexPkgs.sinex-system-ingestor ]
            ++ lib.optionals (runtimeEnabled && activationProfile.document) [ sinexPkgs.sinex-document-ingestor ]
            ++ lib.optionals (runtimeEnabled && activationProfile.automata) [
              sinexPkgs.sinex-analytics-automaton
              sinexPkgs.sinex-session-detector
            ]
            ++ lib.optionals (runtimeEnabled && activationProfile.canonicalizer) [
              sinexPkgs.sinex-terminal-command-canonicalizer
            ]
            ++ lib.optionals (runtimeEnabled && activationProfile.healthAggregator) [
              sinexPkgs.sinex-health-automaton
            ]
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
            dlq.enable = lib.mkDefault false;
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
          services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexctl;
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
            storeDir = "/var/lib/nats/jetstream";
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
            dlq.enable = runtimeEnabled;
          };

          lifecycle = {
            preflight.enable = runtimeEnabled;
            maintenance = {
              enable = runtimeEnabled;
              tasks.dlq = lib.mkForce false;
            };
            updates.enable = runtimeEnabled;
          };

          nodes = {
            enable = runtimeEnabled;

            filesystem = {
              enable = runtimeEnabled && activationProfile.filesystem;
              watchPaths = [ realmRoot ];
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

      (lib.mkIf (
        cfg.provisionDatabase
        && databasePasswordFile != null
        && config.services.sinex.database.localAuth != "trust"
      ) {
        # Delay postgresql-setup until agenix has materialized the password file.
        systemd.services.postgresql-setup.unitConfig.ConditionPathIsReadable = [
          databasePasswordFile
        ];
      })

    ]
  );
}
