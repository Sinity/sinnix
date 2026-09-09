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
      machineTelemetryLakeRoot = "${config.sinnix.paths.machineRoot}/analysis";
      localRoot = "${cfg.repoRoot}/.lynchpin";
      localHotDirs = [
        "cache"
        "enrich"
        "refresh"
      ];
      localHotDirArgs = lib.concatMapStringsSep " " (
        dir: lib.escapeShellArg "${localRoot}/${dir}"
      ) localHotDirs;

      # Both units queue one bounded lynchpin operation and differ only in
      # operation name, deadline, cadence, and what they keep fresh. One table
      # so a unit cannot be scheduled without the surface that gives it failure
      # notification, resource placement, and a place in the health sweep.
      materializeJobs = {
        lynchpin-materialize = {
          description = "Materialize and publish Lynchpin substrate";
          operation = "converge";
          timeoutStartSec = "4h";
          rationale = "Bounded daily source convergence and complete substrate publication.";
          # The webhistory lane belongs to the unit that actually fills it. It
          # used to be declared in capture-registry.nix against a
          # `sinnix-capture-webhistory` unit that does not exist, which is how a
          # lane could carry a 48h staleness budget with nothing on any schedule
          # able to keep it -- see sinnix-ksws.
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
          timer = {
            description = "Daily lynchpin analysis materialization";
            inherit (cfg.materializationTimer) onCalendar;
            randomizedDelaySec = toString cfg.materializationTimer.randomizedDelaySec;
            persistent = true;
          };
        };
        lynchpin-keylog-materialize = {
          description = "Refresh Lynchpin keylog analysis";
          operation = "refresh_keylog";
          timeoutStartSec = "10min";
          rationale = "Quarter-hourly keylog analysis refresh over already-captured input.";
          timer = {
            description = "Quarter-hour Lynchpin keylog analysis refresh";
            onCalendar = "*-*-* *:00/15:00";
            randomizedDelaySec = "60s";
            persistent = true;
          };
        };
      };
    in
    lib.mkMerge [
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
      }

      (lib.mkIf cfg.materializationTimer.enable (
        lib.mkMerge (
          [
            {
              sinnix.runtime.surfaces = lib.mapAttrs (unitName: job: {
                unit = "${unitName}.service";
                resourceClass = "system";
                observe.enable = true;
                workload = {
                  class = "sacrificial";
                  inherit (job) rationale;
                };
                captures = job.captures or [ ];
              }) materializeJobs;
            }
          ]
          ++ lib.mapAttrsToList (
            unitName: job:
            lib.sinnix.mkScheduledJob
              {
                inherit config unitName;
                inherit (job) description;
                surface = config.sinnix.runtime.surfaces.${unitName};
              }
              {
                execStart = "${scriptPkgs.agentctl}/bin/agentctl job start lynchpin ${job.operation} --wait";
                user = "sinity";
                serviceConfig = {
                  Group = "users";
                  TimeoutStartSec = job.timeoutStartSec;
                };
                unit = {
                  requires = [ "lynchpin-local-attrs.service" ];
                  after = [ "lynchpin-local-attrs.service" ];
                };
                inherit (job) timer;
              }
          ) materializeJobs
        )
      ))
    ];
} args
