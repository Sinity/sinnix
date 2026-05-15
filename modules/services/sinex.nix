# Sinex System Service
#
# ─── STATE LAYOUT ─────────────────────────────────────────────────────────────
#
#   System service state: /var/lib/sinex/state/
#     Runs as the sinex system user on the /realm NVMe data volume. PostgreSQL
#     production data lives beside it under /var/lib/sinex/postgresql.
#
#   Development state: /realm/project/sinex/.sinex/state/ (workspace-local)
#     xtask (sinex dev runner) defaults to SINEX_STATE_DIR which points at
#     the workspace-local path. Home dirs (~/.local/state/sinex, ~/.config/sinex,
#     ~/.config/xtask, ~/.local/share/nats etc.) were accumulated from past
#     SINEX_STATE_DIR overrides and have been purged. Do not re-accumulate there.
#
# ─── ENABLED WHEN ─────────────────────────────────────────────────────────────
#
#   sinnix.services.sinex.enable = true
#     The host bridge is live. `prepareHost` and `provisionDatabase` stage
#     partial activation without starting the full runtime.
#
{ config, lib, ... }:
{
  options.sinnix.services.sinex = {
    enable = lib.mkEnableOption "Sinex service";
    autoStart = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Install the delayed runtime timer that starts Sinex automatically after
        boot. Disable this when the host should keep Sinex available for
        manual operation without letting NATS/ingest start during interactive
        login.
      '';
    };
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
        restartable = false;
      };
      description = "Service health metadata consumed by introspection/sentinel.";
    };
  };

  config = lib.mkIf (config.sinnix.services.sinex.enable && !config.sinnix.services.sinex.autoStart) {
    # why mkForce: when the host opts out of auto-start, sentinel must
    # not include sinex in the auto-derived health-policy (otherwise it
    # resurrects manually-stopped runtime services). The default health
    # value above is set unconditionally; override it to null here.
    sinnix.services.sinex.health = lib.mkForce null;
  };
}
