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
    deploymentRole = lib.mkOption {
      type = lib.types.enum [
        "workstation"
        "workstation-thin"
        "replica"
      ];
      default = "workstation";
      description = ''
        Deployment topology for this host's sinex installation.

        - <literal>workstation</literal>: current behavior. PostgreSQL, NATS
          and the full sinexd runtime are all local. This is the only role
          sinnix-prime should use; changing the default would alter prime's
          behavior.

        - <literal>workstation-thin</literal>: PostgreSQL and NATS are
          disabled locally; sinexd ingest reads <literal>DATABASE_URL</literal>
          and <literal>NATS_URL</literal> from
          <literal>/run/agenix/sinex-remote-db</literal> (typically pointing
          at a tailscale-reachable replica host).

        - <literal>replica</literal>: PostgreSQL and NATS run locally to
          back remote workstation-thin nodes; the local sinexd capture
          runtime is disabled (only the collector/receiver path stays live).
      '';
    };
    filesystem.watchPaths = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [
        "/srv/sinex/watch"
        "/var/lib/sinex/downloads"
      ];
      description = ''
        Host-owned filesystem roots passed through to upstream
        <literal>services.sinex.sources.filesystem.watchPaths</literal>.

        The module default is empty so reusable Sinnix service wiring does not
        bake in a personal filesystem topology. Hosts should set this
        explicitly in their host configuration.
      '';
    };
  };
}
