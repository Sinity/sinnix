# Model-free campaign reactor.  Each tick it reads every managed workspace into
# facts and dispatches the one action they imply; it keeps only dispatch
# markers and an error log.
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
      rationale = "Typed campaign lane dispatcher owned by sinnixd.";
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
      description = "Reactor dispatch markers and rotating error log.";
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
      default = 4;
      description = "Minimum active lanes an automatic refill keeps in flight.";
    };
    refillWidthTarget = lib.mkOption {
      type = lib.types.ints.positive;
      default = 6;
      description = "Maximum active lanes targeted by automatic refill.";
    };
    refillSpacingSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 300;
      description = "Minimum spacing used by automatic refill dispatches.";
    };
    refillProjects = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "polylogue" ];
      description = "Projects automatic refill may dispatch into; board and event consumption stay estate-wide.";
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
          # systemd's user-manager namespace setup needs every component of a
          # ReadWritePaths bind source to exist before it starts the unit.  Do
          # not rely on tmpfiles implicitly creating the root-owned parent:
          # provision both levels with the service's ownership explicitly.
          "d ${builtins.dirOf cfg.stateDir} 0750 ${userName} users -"
          "d ${cfg.stateDir} 0750 ${userName} users -"
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
              ExecStart = "${scriptPkgs.sinnixd}/bin/sinnixd-reactor --event-spool ${lib.escapeShellArg cfg.eventSpool} --board ${lib.escapeShellArg cfg.boardPath} --state-dir ${lib.escapeShellArg cfg.stateDir} --jobs-state-dir %S/sinnixd/jobs --interval-seconds ${toString cfg.intervalSeconds} --min-active-lanes ${toString cfg.minActiveLanes} --refill-width-target ${toString cfg.refillWidthTarget} --refill-spacing-seconds ${toString cfg.refillSpacingSeconds} ${
                lib.concatMapStringsSep " " (name: "--refill-project ${lib.escapeShellArg name}") cfg.refillProjects
              } ${projectRootArgs}";
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
    ];
} args
