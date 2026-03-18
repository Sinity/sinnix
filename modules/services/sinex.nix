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
  sinexPkgs = inputs.sinex.packages.${pkgs.stdenv.hostPlatform.system};
in
{
  options.sinnix.services.sinex = {
    enable = lib.mkEnableOption "Sinex service";
    provisionDatabase = lib.mkEnableOption "Provision the Sinex PostgreSQL database without running services";
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
      (lib.mkIf (cfg.enable || cfg.provisionDatabase) {
        services.sinex.package = lib.mkDefault sinexPkgs.sinex;
        services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexctl;
      })

      # Database provisioning only (no running services)
      (lib.mkIf cfg.provisionDatabase {
        services.sinex.database = {
          enable = true;
          autoSetup = true;
          host = "127.0.0.1";
          name = "sinex";
          user = "sinex";
          passwordFile = config.sinex.secrets.paths."sinex-local-db";
        };
      })

      # Full service configuration
      (lib.mkIf cfg.enable {
        services.sinex = {
          enable = true;

          secrets.enableAgenix = true;
          nats.environment = "prod";

          # Align service state root with XDG-style default for the sinex service user.
          stateRoot = "/var/lib/sinex/.local/state/sinex";
          logLevel = "info";

          users.target = config.sinnix.user.name;

          database = {
            autoSetup = true;
            host = "127.0.0.1";
            name = "sinex";
            user = "sinex";
            passwordFile = config.sinex.secrets.paths."sinex-local-db";
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

            # watchPaths defaults to ["/home/${users.target}"] automatically;
            # extend with the realm workspace as well.
            filesystem = {
              enable = true;
              watchPaths = [
                "/home/${config.sinnix.user.name}"
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
              enable = true;
              prometheus = {
                listen = "127.0.0.1";
                port = 9090;
                retention = "30d";
                exporters = {
                  node = true;
                  postgres = true;
                };
              };
              grafana = {
                enable = true;
                port = 3000;
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
