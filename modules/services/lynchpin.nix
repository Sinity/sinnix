# Lynchpin substrate service
#
# Makes the lynchpin-mcp binary available on PATH and sets env vars for
# ergonomic CLI use. No persistent daemon — the MCP server is invoked on
# demand by AI agent runtimes via the stdio transport registered in
# mcp-registry.nix.
#
# A daily oneshot queues one bounded convergence operation. pueue owns the
# pool, logs and cancellation; the operation returns only after
# materialization, verification, and publication.
#
# Enable with:
#   sinnix.services.lynchpin.enable = true;
#   sinnix.services.lynchpin.materializationTimer.enable = true;
{
  mkServiceModule,
  lib,
  helpers,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "lynchpin";
  description = "lynchpin substrate + MCP server";
  extraOptions = {
    repoRoot = lib.mkOption {
      type = lib.types.str;
      default = "/realm/project/sinity-lynchpin";
      description = ''
        Absolute path to the lynchpin checkout. The materialization CLI is
        repo-rooted: it reads/writes `.lynchpin/` relative to this directory.
        Used as the service WorkingDirectory and to export
        LYNCHPIN_REPO_ROOT/LYNCHPIN_LOCAL_ROOT so the job does not depend on
        the process's inherited CWD.
      '';
    };

    materializationTimer = {
      enable = lib.mkEnableOption "daily substrate materialization timer";

      onCalendar = lib.mkOption {
        type = lib.types.str;
        default = "*-*-* 03:00:00";
        description = "systemd OnCalendar expression for substrate materialization (daily by default).";
      };

      randomizedDelaySec = lib.mkOption {
        type = lib.types.int;
        default = 3600;
        description = "Max randomized delay in seconds (spreads load).";
      };
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      machineTelemetryLakeRoot = "${config.sinnix.paths.dataRoot}/derived/machine-telemetry";
      localRoot = "${cfg.repoRoot}/.lynchpin";
      localHotDirs = [
        "cache"
        "enrich"
        "refresh"
      ];
      localHotDirArgs = lib.concatMapStringsSep " " (
        dir: lib.escapeShellArg "${localRoot}/${dir}"
      ) localHotDirs;
    in
    {
      environment.systemPackages = [
        scriptPkgs.lynchpin-cli
        scriptPkgs.lynchpin-python
      ];

      environment.variables = {
        LYNCHPIN_MCP_PROVIDED = "1";
      };

      systemd.services.lynchpin-local-attrs = {
        description = "Prepare Lynchpin local cache directories";
        wantedBy = [ "multi-user.target" ];
        path = [
          pkgs.coreutils
          pkgs.e2fsprogs
        ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          install -d -m 0775 -o sinity -g users ${lib.escapeShellArg localRoot}
          install -d -m 0775 -o sinity -g users ${lib.escapeShellArg machineTelemetryLakeRoot}
          for dir in ${localHotDirArgs}; do
            install -d -m 0775 -o sinity -g users "$dir"
            chattr +C "$dir" || true
          done
        '';
      };

      # Optional: run the daily convergence operation to completion.
      systemd.services.lynchpin-materialize = lib.mkIf cfg.materializationTimer.enable {
        description = "Materialize and publish Lynchpin substrate";
        onFailure = [ "sinnix-unit-failure-notify@%n.service" ];
        requires = [ "lynchpin-local-attrs.service" ];
        after = [ "lynchpin-local-attrs.service" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${scriptPkgs.agentctl}/bin/agentctl job start lynchpin converge --wait";
          User = "sinity";
          Group = "users";
          TimeoutStartSec = "4h";
        };
      };

      systemd.services.lynchpin-keylog-materialize = lib.mkIf cfg.materializationTimer.enable {
        description = "Refresh Lynchpin keylog analysis";
        onFailure = [ "sinnix-unit-failure-notify@%n.service" ];
        requires = [ "lynchpin-local-attrs.service" ];
        after = [ "lynchpin-local-attrs.service" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${scriptPkgs.agentctl}/bin/agentctl job start lynchpin refresh_keylog --wait";
          User = "sinity";
          Group = "users";
          TimeoutStartSec = "10min";
        };
      };

      # The webhistory lane belongs here, to the unit that actually fills it.
      # It used to be declared in capture-registry.nix against a
      # `sinnix-capture-webhistory` unit that does not exist, which is how a
      # lane could carry a 48h staleness budget with nothing on any schedule
      # able to keep it -- see sinnix-ksws. Registering the surface also puts
      # this daily job in front of the health sweep, which it was not.
      sinnix.runtime.surfaces.lynchpin-materialize = lib.mkIf cfg.materializationTimer.enable {
        unit = "lynchpin-materialize.service";
        resourceClass = "system";
        observe.enable = true;
        workload = {
          class = "sacrificial";
          rationale = "Bounded daily source convergence and complete substrate publication.";
        };
        captures = [
          {
            name = "webhistory";
            path = "${config.sinnix.paths.activityRoot}/webhistory";
            eventDriven = true;
            # Two days against a daily timer: one missed run is tolerable,
            # two is worth surfacing. The hard deadline is far longer --
            # Chrome drops visits after ~90 days -- so this is an early
            # warning, not the edge of data loss.
            staleAfterSeconds = 172800;
          }
        ];
      };

      systemd.timers.lynchpin-materialize = lib.mkIf cfg.materializationTimer.enable {
        description = "Daily lynchpin analysis materialization";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = cfg.materializationTimer.onCalendar;
          RandomizedDelaySec = toString cfg.materializationTimer.randomizedDelaySec;
          Persistent = true;
        };
      };

      systemd.timers.lynchpin-keylog-materialize = lib.mkIf cfg.materializationTimer.enable {
        description = "Quarter-hour Lynchpin keylog analysis refresh";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "*-*-* *:00/15:00";
          RandomizedDelaySec = "60s";
          Persistent = true;
        };
      };
    };
} args
