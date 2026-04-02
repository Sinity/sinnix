# Sinex System Service
#
# ─── STATE LAYOUT ─────────────────────────────────────────────────────────────
#
#   System service state: /var/lib/sinex/.local/state/sinex/
#     Runs as the sinex system user. Persisted via modules/persistence.nix
#     when impermanence is enabled (/var/lib/sinex bind-mounted from /persist).
#
#   Development state: /realm/project/sinex/.sinex/state/ (workspace-local)
#     xtask (sinex dev runner) defaults to SINEX_STATE_DIR which points at
#     the workspace-local path. Home dirs (~/.local/state/sinex, ~/.config/sinex,
#     ~/.config/xtask, ~/.local/share/nats etc.) were accumulated from past
#     SINEX_STATE_DIR overrides and have been purged. Do not re-accumulate there.
#
#   Future: system service state may move to /realm/data/sinex/ or similar
#     once the realm topology is finalized. SINEX_STATE_DIR will control this.
#
# ─── ENABLED WHEN ─────────────────────────────────────────────────────────────
#
#   sinnix.services.sinex.enable = true   (currently disabled — service is not
#   yet deployed; sinex is in active development at /realm/project/sinex)
#
{
  config,
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
  targetUserHome = lib.attrByPath [ "users" "users" targetUserName "home" ] "/home/${targetUserName}" config;
  targetUserUid = lib.attrByPath [ "users" "users" targetUserName "uid" ] null config;
  databaseHost = "127.0.0.1";
  databasePort = 5432;
  databaseUser = "sinex";
  databaseName = "sinex_${sinexEnvironment}";
  databasePasswordFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-local-db" ] null config;
  gatewayAdminTokenFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-gateway-admin-token" ] null config;
  natsCaCertFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-ca" ] null config;
  natsClientCertFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-client-cert" ] null config;
  natsClientKeyFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-client-key" ] null config;
  natsTokenFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-token" ] null config;
  natsCredsFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-client-creds" ] null config;
  natsNkeySeedFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-client-nkey" ] null config;
  databaseUrl = "postgresql://${databaseUser}@${databaseHost}:${toString databasePort}/${databaseName}";
in
{
  options.sinnix.services.sinex = {
    enable = lib.mkEnableOption "Sinex service";
    prepareHost = lib.mkEnableOption "Apply host prerequisites for Sinex without enabling the service";
    provisionDatabase = lib.mkEnableOption "Provision the Sinex PostgreSQL database without running services";
    activationProfile = lib.mkOption {
      type = lib.types.enum [
        "foundation"
        "capture"
        "full"
      ];
      default = "foundation";
      description = ''
        High-level deployment profile used to map the upstream
        <literal>services.sinex</literal> node toggles. <literal>foundation</literal>
        enables only core services plus filesystem/system collectors,
        <literal>capture</literal> adds terminal capture and baseline automata,
        and <literal>full</literal> enables the workstation-facing desktop path.
      '';
    };
    environment = lib.mkOption {
      type = lib.types.str;
      default = "prod";
      apply = lib.toLower;
      description = ''
        Environment name used for both the Sinex NATS namespace and the
        default runtime database name.
      '';
    };
    health = lib.mkOption {
      type = lib.types.nullOr (
        lib.types.submodule {
          options = {
            unit = lib.mkOption {
              type = lib.types.str;
            };
            type = lib.mkOption {
              type = lib.types.enum [
                "service"
                "timer"
                "user"
              ];
            };
            restartable = lib.mkOption {
              type = lib.types.bool;
            };
          };
        }
      );
      default = null;
      description = "Service health metadata consumed by introspection/sentinel.";
    };
  };

  # Only configure if sinex module is available from the flake input
  config = lib.mkIf (config.services ? sinex) (
    let
      activationProfile = {
        foundation = {
          filesystem = true;
          terminal = false;
          desktop = false;
          system = true;
          automata = false;
          canonicalizer = false;
          healthAggregator = false;
          kitty = false;
        };
        capture = {
          filesystem = true;
          terminal = true;
          desktop = false;
          system = true;
          automata = true;
          canonicalizer = true;
          healthAggregator = true;
          kitty = true;
        };
        full = {
          filesystem = true;
          terminal = true;
          desktop = true;
          system = true;
          automata = true;
          canonicalizer = true;
          healthAggregator = true;
          kitty = true;
        };
      }.${cfg.activationProfile};
      terminalHistorySources = [
        {
          path = "${targetUserHome}/.bash_history";
          shell = "bash";
        }
        {
          path = "${targetUserHome}/.zsh_history";
          shell = "zsh";
        }
        {
          path = "${targetUserHome}/.local/share/atuin/history.db";
          shell = "atuin";
        }
        {
          path = "${targetUserHome}/.local/share/fish/fish_history";
          shell = "fish";
        }
      ];
      activitywatchDbPath = "${targetUserHome}/.local/share/activitywatch/aw-server-rust/sqlite.db";
      desktopRuntimeDir =
        if targetUserUid == null then null else "/run/user/${toString targetUserUid}";
      preparedManagedUnits =
        lib.optionals cfg.provisionDatabase [ "sinex-schema-apply.service" ];
      deploymentDescriptor = builtins.toJSON {
        version = 1;
        source = "sinnix.services.sinex.prepared";
        mode = if cfg.enable then "enabled" else "prepared";
        managed_units = preparedManagedUnits;
        target = {
          user = targetUserName;
          uid = targetUserUid;
          home = targetUserHome;
        };
        filesystem = {
          enabled = activationProfile.filesystem;
          instances = 1;
        };
        terminal = {
          enabled = activationProfile.terminal;
          instances = 1;
          kitty_enabled = activationProfile.kitty;
          history_sources = terminalHistorySources;
        };
        desktop = {
          enabled = activationProfile.desktop;
          instances = 1;
          clipboard_enabled = true;
          activitywatch_db_path = activitywatchDbPath;
          runtime_dir = desktopRuntimeDir;
          wayland_display = null;
          hyprland_instance_signature = null;
          hyprland_event_socket = null;
          hyprland_command_socket = null;
        };
        system = {
          enabled = activationProfile.system;
          instances = 1;
        };
        automata = {
          enabled = activationProfile.automata;
        };
        expectations = {
          schema_apply = cfg.provisionDatabase || cfg.enable;
          nats_streams = cfg.enable;
          gateway_ready = cfg.enable;
        };
        secrets = {
          database_password_file = databasePasswordFile;
          gateway_admin_token_file = gatewayAdminTokenFile;
          nats_ca_cert_file = natsCaCertFile;
          nats_client_cert_file = natsClientCertFile;
          nats_client_key_file = natsClientKeyFile;
          nats_token_file = natsTokenFile;
          nats_creds_file = natsCredsFile;
          nats_nkey_seed_file = natsNkeySeedFile;
        };
      };
    in
    lib.mkMerge [
      # Keep the imported upstream module genuinely inert while Sinnix is only
      # preparing the host. Several upstream submodules default to "on" and
      # would otherwise create secrets, blob maintenance units, or tmpfiles even
      # with the master switch still off.
      (lib.mkIf (!(cfg.enable || cfg.provisionDatabase)) {
        services.sinex = {
          cliPackage = lib.mkDefault null;
          secrets.enableAgenix = lib.mkDefault false;
          core.enable = lib.mkDefault false;
          nodes.enable = lib.mkDefault false;
          nats.enable = lib.mkDefault false;
          nats.autoSetup = lib.mkDefault false;
          observability.enable = lib.mkDefault false;
          storage = {
            dlq.enable = lib.mkDefault false;
            blob.enable = lib.mkDefault false;
          };
          lifecycle = {
            preflight.enable = lib.mkDefault false;
            maintenance.enable = lib.mkDefault false;
            updates.enable = lib.mkDefault false;
          };
        };
      })

      # Package defaults — applied whenever sinex is referenced at all
      (lib.mkIf (cfg.prepareHost || cfg.enable || cfg.provisionDatabase) (
        let
          sinexPkgs = mkSinexPkgs pkgs;
        in
        {
          services.sinex.package = lib.mkDefault sinexPkgs.sinex;
          services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexctl;
        }
      ))

      # Target-user wiring is deployment intent, not a live-enable concern.
      # Keep the observed workstation user known during dark-host preparation
      # so agenix and other target-user-aware defaults can resolve against the
      # real account before any capture units are enabled.
      (lib.mkIf (cfg.prepareHost || cfg.enable || cfg.provisionDatabase) {
        services.sinex.users.target = targetUserName;
      })

      (lib.mkIf ((cfg.prepareHost || cfg.provisionDatabase) && !cfg.enable) {
        environment.etc."sinex/deployment-readiness.json".text = deploymentDescriptor;
      })

      (lib.mkIf (cfg.prepareHost || cfg.enable || cfg.provisionDatabase) {
        sinex.secrets.paths = lib.mkForce (
          lib.mapAttrs (_: path: toString path) (
            lib.filterAttrs (
              name: _:
              lib.hasPrefix "sinex-" name || lib.hasPrefix "nats-" name
            ) config.sinnix.secrets.paths
          )
        );

        services.sinex = {
          enable = cfg.enable;

          secrets = {
            enableAgenix = false;
            gatewayAdminTokenFile = lib.mkDefault gatewayAdminTokenFile;
          };
          nats = {
            environment = sinexEnvironment;
            enable = cfg.enable;
          };

          # Align service state root with XDG-style default for the sinex service user.
          stateRoot = "/var/lib/sinex/.local/state/sinex";
          logLevel = "info";

          database = {
            enable = cfg.provisionDatabase || cfg.enable;
            autoSetup = cfg.provisionDatabase || cfg.enable;
            host = databaseHost;
            port = databasePort;
            name = databaseName;
            user = databaseUser;
            passwordFile = databasePasswordFile;
          };

          core = {
            enable = true;
            gateway = {
              enable = true;
              autoGenerateTls = true;
            };
          };

          storage = {
            blob.enable = true;
            dlq.enable = true;
          };

          lifecycle = {
            preflight.enable = true;
            maintenance.enable = true;
          };

          nodes = {
            enable = true;
            defaults.instances = 1;

            # The captured user's home is private (`0700`) on sinnix-prime, so
            # the system `sinex` account cannot observe it honestly. Watch the
            # realm workspace only until a readable target path is configured.
            filesystem = {
              enable = activationProfile.filesystem;
              instances = 1;
              watchPaths = [
                realmRoot
              ];
            };

            terminal = {
              enable = activationProfile.terminal;
              instances = 1;
              historySources = terminalHistorySources;
            };

            desktop = {
              enable = activationProfile.desktop;
              instances = 1;
              clipboard.enable = true;
              history.activitywatchDbPath = activitywatchDbPath;
              session.runtimeDir = desktopRuntimeDir;
            };

            system = {
              enable = activationProfile.system;
              instances = 1;
            };

            automata = {
              enable = activationProfile.automata;
              canonicalizer.enable = activationProfile.canonicalizer;
              healthAggregator.enable = activationProfile.healthAggregator;
            };
          };

          observability = {
            enable = true;
            monitoring = {
              # Keep the host story truthful until gateway/node readiness and
              # dataflow health are good enough to treat dashboards as signal.
              enable = false;
              prometheus.enable = false;
              grafana = {
                enable = false;
              };
              exporters = {
                node = false;
                postgres = false;
                nats = false;
              };
            };
          };

          shell.kitty = {
            enable = activationProfile.kitty;
            autoConfigure = activationProfile.kitty;
          };
        };
      })

      # Database provisioning only (no running services)
      (lib.mkIf cfg.provisionDatabase {
        assertions = [
          {
            assertion = databasePasswordFile != null;
            message = "sinnix.services.sinex requires the sinex-local-db agenix secret";
          }
        ];
      })

      # Keep the database-only path honest: create the env-namespaced DB and
      # apply the declarative schema even while the full Sinex service remains off.
      (lib.mkIf (cfg.provisionDatabase && !cfg.enable) (
        let
          sinexPkgs = mkSinexPkgs pkgs;
          schemaBootstrapScript = pkgs.writeShellScript "sinnix-sinex-schema-bootstrap" ''
            set -euo pipefail

            database_url=${lib.escapeShellArg databaseUrl}
            echo "$(date): applying Sinex schema to ${databaseName}"
            ${sinexPkgs.sinex}/bin/xtask infra schema-apply --database-url "$database_url"
          '';
        in
        {
          systemd.services.sinex-schema-apply = {
            description = "Apply Sinex declarative schema";
            wantedBy = [ "multi-user.target" ];
            wants = [ "network-online.target" ];
            after = [
              "network-online.target"
              "postgresql.service"
              "postgresql-setup.service"
            ];
            requires = [
              "postgresql.service"
              "postgresql-setup.service"
            ];
            serviceConfig = {
              Type = "oneshot";
              User = databaseUser;
              Group = databaseUser;
              ExecStart = schemaBootstrapScript;
              TimeoutStartSec = "10min";
              RemainAfterExit = true;
            };
          };
        }
      ))

    ]
  );
}
