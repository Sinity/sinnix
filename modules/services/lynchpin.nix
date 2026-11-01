# Lynchpin substrate service
#
# Makes the lynchpin-mcp binary available on PATH and sets env vars for
# ergonomic CLI use.
# No persistent daemon — the MCP server is invoked on
# demand by AI agent runtimes via the stdio transport registered in
# mcp-registry.nix.
#
# A daily oneshot queues the bounded browser-history capture. pueue owns the
# pool, logs and cancellation. Other Lynchpin products refresh on read.
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
      default = "/realm/project/sinity-lynchpin/repo";
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
      # One stable host path for the two entry points agents and the dev shell
      # call, independent of which store paths the packages occupy.
      hostRuntime = pkgs.runCommand "lynchpin-host-runtime" { } ''
        mkdir -p "$out/bin"
        ln -s ${scriptPkgs.lynchpin-python}/bin/lynchpin-python "$out/bin/lynchpin-python"
        ln -s ${scriptPkgs.lynchpin-cli}/bin/lynchpin-mcp "$out/bin/lynchpin-mcp"
      '';
      localHotDirs = [
        "cache"
        "enrich"
        "refresh"
      ];
      localHotDirArgs = lib.concatMapStringsSep " " (
        dir: lib.escapeShellArg "${localRoot}/${dir}"
      ) localHotDirs;

      # Each unit queues one bounded lynchpin operation. One table so a unit
      # cannot be scheduled without the surface that gives it failure
      # notification, resource placement, and a place in the health sweep.
      # The keylog refresh timer is gone: its product is a cache every reader
      # rebuilds on request (`agentctl job start lynchpin refresh_keylog`).
      materializeJobs = {
        lynchpin-materialize = {
          # Only the browser-history capture still has a scheduled consumer;
          # every other Lynchpin product refreshes when a reader asks for it.
          # `converge` stays a declared on-demand operation.
          description = "Capture recent browser history for Lynchpin";
          operation = "capture_webhistory";
          # Covers the queue wait plus the operation's own 30 min budget.
          timeoutStartSec = "1h";
          rationale = "Daily bounded browser-history capture before Chrome expires visits.";
          # The webhistory lane belongs to the unit that actually fills it. It
          # used to be declared in capture-registry.nix against a
          # `sinnix-capture-webhistory` unit that does not exist, which is how a
          # lane could carry a 48h staleness budget with nothing on any schedule
          # able to keep it -- see sinnix-ksws.
          captures = [
            {
              name = "webhistory";
              path = "${config.sinnix.paths.capturePaths.webhistory}";
              eventDriven = true;
              # Two days against a daily timer: one missed run is tolerable,
              # two is worth surfacing. The hard deadline is far longer --
              # Chrome drops visits after ~90 days -- so this is an early
              # warning, not the edge of data loss.
              staleAfterSeconds = 172800;
            }
          ];
          timer = {
            description = "Daily Lynchpin browser-history capture";
            inherit (cfg.materializationTimer) onCalendar;
            randomizedDelaySec = toString cfg.materializationTimer.randomizedDelaySec;
            persistent = true;
          };
        };
      };
    in
    lib.mkMerge [
      {
        system.build.lynchpinRuntime = hostRuntime;
        environment.systemPackages = [ hostRuntime ];

        environment.variables.LYNCHPIN_MCP_PROVIDED = "1";

        systemd.tmpfiles.rules = [
          "d ${config.sinnix.paths.capturePaths.webhistory} 0700 ${config.sinnix.user.name} users -"
          "d ${config.sinnix.paths.stateRoot}/lynchpin 0700 ${config.sinnix.user.name} ${config.sinnix.user.name} -"
        ];

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
            install -d -m 0700 -o sinity -g users ${lib.escapeShellArg localRoot}
            install -d -m 0775 -o sinity -g users ${lib.escapeShellArg machineTelemetryLakeRoot}
            for dir in ${localHotDirArgs}; do
              install -d -m 0700 -o sinity -g users "$dir"
              chattr +C "$dir" || true
            done
          '';
        };
      }

      (lib.mkIf cfg.materializationTimer.enable (
        lib.mkMerge (
          [
            {
              sinnix.runtime.units = lib.mapAttrs (unitName: job: {
                unit = "${unitName}.service";
                resourceClass = "ordinary";
                notifyOnFailure = true;
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
                surface = config.sinnix.runtime.units.${unitName};
              }
              {
                execStart = "${scriptPkgs.agentctl}/bin/agentctl job start --if-idle lynchpin ${job.operation} --wait";
                user = "sinity";
                serviceConfig = {
                  ExecCondition = "${scriptPkgs.sinnix-fs}/bin/sinnix-fs maintain admission --volume ${config.sinnix.paths.realmRoot}";
                  Group = "users";
                  TimeoutStartSec = job.timeoutStartSec;
                };
                unit = {
                  requires = [ "lynchpin-local-attrs.service" ];
                  after = [ "lynchpin-local-attrs.service" ];
                  # The timer runs these; an activation that started one waited
                  # for its queued AgentCTL job behind the build pools (a 42 min
                  # switch on 2026-11-01).
                  restartIfChanged = false;
                };
                inherit (job) timer;
              }
          ) materializeJobs
        )
      ))
    ];
} args
