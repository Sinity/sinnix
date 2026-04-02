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
{ lib, ... }:
{
  options.sinnix.services.sinex = {
    enable = lib.mkEnableOption "Sinex service";
    prepareHost = lib.mkEnableOption ''
      Stage the Sinex host integration without starting the capture runtime
    '';
    provisionDatabase = lib.mkEnableOption ''
      Provision the Sinex PostgreSQL database and schema without starting Sinex services
    '';
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
      default = {
        unit = "sinex-ingestd.service";
        type = "service";
        restartable = true;
      };
      description = "Service health metadata consumed by introspection/sentinel.";
    };
  };
}
