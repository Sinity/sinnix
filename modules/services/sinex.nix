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
  databaseHost = "127.0.0.1";
  databasePort = 5432;
  databaseUser = "sinex";
  databaseName = "sinex_${sinexEnvironment}";
  databasePasswordFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-local-db" ] null config;
  databaseUrl = "postgresql://${databaseUser}@${databaseHost}:${toString databasePort}/${databaseName}";
in
{
  options.sinnix.services.sinex = {
    enable = lib.mkEnableOption "Sinex service";
    provisionDatabase = lib.mkEnableOption "Provision the Sinex PostgreSQL database without running services";
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
    lib.mkMerge [
      # Keep the imported upstream module from pulling pkgs.sinexctl into the
      # system closure when Sinnix is not actually enabling Sinex yet.
      (lib.mkIf (!(cfg.enable || cfg.provisionDatabase)) {
        services.sinex.cliPackage = lib.mkDefault null;
      })

      # Package defaults — applied whenever sinex is referenced at all
      (lib.mkIf (cfg.enable || cfg.provisionDatabase) (
        let
          sinexPkgs = mkSinexPkgs pkgs;
        in
        {
          services.sinex.package = lib.mkDefault sinexPkgs.sinex;
          services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexctl;
        }
      ))

      # Database provisioning only (no running services)
      (lib.mkIf cfg.provisionDatabase {
        assertions = [
          {
            assertion = databasePasswordFile != null;
            message = "sinnix.services.sinex requires the sinex-local-db agenix secret";
          }
        ];
        services.sinex.secrets.enableAgenix = true;
        services.sinex.nats.environment = sinexEnvironment;
        services.sinex.database = {
          enable = true;
          autoSetup = true;
          host = databaseHost;
          port = databasePort;
          name = databaseName;
          user = databaseUser;
          passwordFile = databasePasswordFile;
        };
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

      # Full service configuration
      (lib.mkIf cfg.enable {
        assertions = [
          {
            assertion = databasePasswordFile != null;
            message = "sinnix.services.sinex requires the sinex-local-db agenix secret";
          }
        ];
        services.sinex = {
          enable = true;

          secrets.enableAgenix = true;
          nats.environment = sinexEnvironment;

          # Align service state root with XDG-style default for the sinex service user.
          stateRoot = "/var/lib/sinex/.local/state/sinex";
          logLevel = "info";

          users.target = config.sinnix.user.name;

          database = {
            autoSetup = true;
            host = databaseHost;
            port = databasePort;
            name = databaseName;
            user = databaseUser;
            passwordFile = databasePasswordFile;
          };

          core = {
            enable = true;
            gateway.autoGenerateTls = true;
          };

          nats.enable = true;

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

            # The captured user's home is private (`0700`) on sinnix-prime, so
            # the system `sinex` account cannot observe it honestly. Watch the
            # realm workspace only until a readable target path is configured.
            filesystem = {
              enable = true;
              watchPaths = [
                realmRoot
              ];
            };

            terminal.enable = true;

            desktop = {
              enable = true;
              clipboard.enable = true;
            };

            system.enable = true;

            automata = {
              enable = true;
              canonicalizer.enable = true;
              healthAggregator.enable = true;
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
            enable = true;
            autoConfigure = true;
          };
        };
      })
    ]
  );
}
