# Model-free campaign reactor.  It consumes the daemon event spool, owns the
# externalized campaign board, and performs only typed mechanical reactions.
# Harvester/reviewer and strategist wakes remain outside this service.
{
  mkServiceModule,
  config,
  helpers,
  lib,
  pkgs,
  ...
}@args:
let
  userName = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  projectRootArgs = lib.concatMapStringsSep " " (
    project: "--project-root ${lib.escapeShellArg "${project.name}=${project.value.path}"}"
  ) (lib.attrsToList config.sinnix.projects.entries);
  plannerOutput = "/realm/tmp/work/dispatch-plan.json";
in
mkServiceModule {
  name = "campaign-reactor";
  description = "Sinnix model-free campaign event reactor";
  surface = {
    unit = "sinnixd-reactor.service";
    manager = "user";
    resourceClass = "background-maintenance";
    observe = {
      enable = true;
      restartable = true;
    };
    workload = {
      class = "protected";
      rationale = "Typed campaign state and keeper event publisher owned by sinnixd.";
      processMatchers = [ "sinnixd-reactor" ];
    };
  };
  extraOptions = {
    eventSpool = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/agentctl/events.jsonl";
      apply =
        path:
        if lib.hasPrefix "/" path then
          path
        else
          throw "sinnix.services.campaign-reactor.eventSpool must be absolute";
      description = "Append-only sinnixd event spool consumed by the reactor.";
    };
    boardPath = lib.mkOption {
      type = lib.types.str;
      default = "/realm/tmp/work/campaign-board.json";
      apply =
        path:
        if lib.hasPrefix "/" path then
          path
        else
          throw "sinnix.services.campaign-reactor.boardPath must be absolute";
      description = "Versioned JSON campaign board maintained by the reactor.";
    };
    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/sinnixd/reactor";
      apply =
        path:
        if lib.hasPrefix "/" path then
          path
        else
          throw "sinnix.services.campaign-reactor.stateDir must be absolute";
      description = "Durable reactor cursor and backoff state.";
    };
    intervalSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 10;
      description = "Seconds between bounded event-spool drains.";
    };
    minActiveLanes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 3;
      description = "Keeper threshold for an under-filled active campaign wave.";
    };
    keeperBackoffSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 600;
      description = "Initial delay between repeated keeper events for one action.";
    };
    prAgeThresholdSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 3600;
      description = "Age after which an open pull request receives a needs-merge keeper event.";
    };
    refillWidthTarget = lib.mkOption {
      type = lib.types.ints.positive;
      default = 3;
      description = "Maximum active lanes targeted by automatic bead-close refill.";
    };
    refillSpacingSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 10;
      description = "Minimum spacing used by automatic refill dispatches.";
    };
  };
  configFn =
    { cfg, ... }:
    let
      boardDirectory = builtins.dirOf cfg.boardPath;
      spoolDirectory = builtins.dirOf cfg.eventSpool;
    in
    lib.mkMerge [
      {
        assertions = [
          {
            assertion = config.sinnix.services.sinnixd.enable;
            message = "sinnix.services.campaign-reactor requires sinnix.services.sinnixd.enable";
          }
        ];
        environment.systemPackages = [
          scriptPkgs.sinnixd
          scriptPkgs.beads
        ];
        systemd.tmpfiles.rules = [
          "d ${cfg.stateDir} 0700 ${userName} users -"
          "d ${boardDirectory} 0755 ${userName} users -"
          "d ${spoolDirectory} 0700 ${userName} users -"
        ];
        home-manager.users.${userName}.systemd.user.services.sinnixd-reactor = {
          Unit = {
            Description = "Sinnix model-free campaign event reactor";
            After = [ "sinnixd.service" ];
            Requires = [ "sinnixd.service" ];
          };
          Service =
            (lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnixd-reactor.service";
            })
            // {
              Type = "simple";
              ExecStart = "${scriptPkgs.sinnixd}/bin/sinnixd-reactor --event-spool ${lib.escapeShellArg cfg.eventSpool} --board ${lib.escapeShellArg cfg.boardPath} --state-dir ${lib.escapeShellArg cfg.stateDir} --jobs-state-dir %S/sinnixd/jobs --interval-seconds ${toString cfg.intervalSeconds} --min-active-lanes ${toString cfg.minActiveLanes} --keeper-backoff-seconds ${toString cfg.keeperBackoffSeconds} --pr-age-threshold-seconds ${toString cfg.prAgeThresholdSeconds} --refill-width-target ${toString cfg.refillWidthTarget} --refill-spacing-seconds ${toString cfg.refillSpacingSeconds} ${projectRootArgs}";
              Restart = "on-failure";
              RestartSec = "5s";
              NoNewPrivileges = true;
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              ReadWritePaths = [
                cfg.stateDir
                boardDirectory
                spoolDirectory
                config.sinnix.services.sinnixd.taskStateRoot
              ]
              ++ map (project: project.value.path) (lib.attrsToList config.sinnix.projects.entries);
              UMask = "0077";
            };
          Install.WantedBy = [ "default.target" ];
        };
      }
      # The planner is a scheduled, read-only snapshot producer.  It emits the
      # artifact consumed by refill; launching remains the campaign runner's
      # typed admission path.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnixd-campaign-planner";
          description = "Sinnix campaign dispatch-plan snapshot";
        }
        {
          manager = "user";
          resourceClass = "background-maintenance";
          execStart = "${scriptPkgs.sinnixd}/bin/sinnixd-planner --output ${lib.escapeShellArg plannerOutput} ${projectRootArgs}";
          serviceConfig = {
            ReadWritePaths = [ (builtins.dirOf plannerOutput) ];
          };
          timer = {
            intervalSec = 900;
            persistent = true;
            description = "Periodic campaign frontier planning";
          };
        }
      )
    ];
} args
