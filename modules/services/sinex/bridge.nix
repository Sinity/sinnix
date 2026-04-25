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
      terminalSourceUnitIdForShell =
        shell:
        let
          normalized = lib.toLower shell;
        in
        if normalized == "atuin" then
          "terminal.atuin-history"
        else if normalized == "bash" then
          "terminal.bash-history"
        else if normalized == "zsh" then
          "terminal.zsh-history"
        else if normalized == "fish" then
          "terminal.fish-history"
        else
          "terminal.text-history";
      terminalSourceUnitServices = lib.unique (
        map (
          source:
          let
            explicitSourceUnit = source.sourceUnitId or null;
          in
          "sinex-source@${
            if explicitSourceUnit != null then explicitSourceUnit else terminalSourceUnitIdForShell source.shell
          }"
        ) (config.services.sinex.nodes.terminal.historySources or [ ])
      );
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
        ++ lib.optionals (runtimeEnabled && activationProfile.filesystem) [ "sinex-filesystem-1" ]
        ++ lib.optionals (runtimeEnabled && activationProfile.terminal) terminalSourceUnitServices
        ++ lib.optionals (runtimeEnabled && activationProfile.browser) [ "sinex-browser-1" ]
        ++ lib.optionals (runtimeEnabled && activationProfile.desktop) [ "sinex-desktop-1" ]
        ++ lib.optionals (runtimeEnabled && activationProfile.system) [ "sinex-system-1" ]
        ++ lib.optionals (runtimeEnabled && activationProfile.document) [ "sinex-document-scan" ]
        ++ lib.optionals (runtimeEnabled && activationProfile.automata) [
          "sinex-analytics-automaton"
          "sinex-session-detector"
        ]
        ++ lib.optionals (runtimeEnabled && activationProfile.canonicalizer) [ "sinex-canonicalizer" ]
        ++ lib.optionals (runtimeEnabled && activationProfile.healthAggregator) [
          "sinex-health-automaton"
        ]
      );
      delayedRuntimeUnits = map (name: "${name}.service") delayedRuntimeServices;
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
        systemd.services = lib.genAttrs delayedRuntimeServices (_: {
          wantedBy = lib.mkForce [ ];
        });
        systemd.targets.sinex-runtime = {
          description = "Start Sinex runtime after interactive boot";
          wants = delayedRuntimeUnits ++ [ "network-online.target" ];
          after = [
            "multi-user.target"
            "graphical.target"
            "network-online.target"
          ];
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
