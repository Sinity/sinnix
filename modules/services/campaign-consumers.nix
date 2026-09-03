# Daily read-only artifacts derived from the event spool and job records.
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
in
mkServiceModule {
  name = "campaign-consumers";
  description = "Daily campaign trajectory and result-gap reports";
  extraOptions = {
    eventSpool = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/agentctl/events.jsonl";
    };
    jobsStateDir = lib.mkOption {
      type = lib.types.str;
      # `%S` is the user manager's state directory, which is where sinnixd
      # stores its job records (the event spool has a separate shared path).
      default = "%S/sinnixd";
    };
    outputDir = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/campaign-consumers";
    };
    onCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*-*-* 01:30:00";
    };
  };
  configFn =
    { cfg, ... }:
    lib.mkMerge [
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-campaign-trajectory";
          description = "Daily campaign trajectory snapshot";
        }
        {
          manager = "user";
          resourceClass = "background-maintenance";
          execStart = "${scriptPkgs.sinnix-campaign-trajectory}/bin/sinnix-campaign-trajectory --event-spool ${lib.escapeShellArg cfg.eventSpool} --output ${lib.escapeShellArg "${cfg.outputDir}/trajectory.json"} --state ${lib.escapeShellArg "${cfg.outputDir}/trajectory.state.json"}";
          serviceConfig = {
            TimeoutStartSec = "2min";
            ReadWritePaths = [
              cfg.outputDir
              (builtins.dirOf cfg.eventSpool)
            ];
          };
          timer = {
            onCalendar = cfg.onCalendar;
            persistent = true;
            description = "Daily campaign trajectory snapshot";
          };
        }
      )
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-result-gap-digest";
          description = "Daily empty result-artifact digest";
        }
        {
          manager = "user";
          resourceClass = "background-maintenance";
          execStart = "${scriptPkgs.sinnix-result-gap-digest}/bin/sinnix-result-gap-digest --jobs-state-dir ${lib.escapeShellArg cfg.jobsStateDir} --event-spool ${lib.escapeShellArg cfg.eventSpool} --output ${lib.escapeShellArg "${cfg.outputDir}/result-gaps.jsonl"} --state ${lib.escapeShellArg "${cfg.outputDir}/result-gaps.state.json"}";
          serviceConfig = {
            TimeoutStartSec = "2min";
            ReadWritePaths = [
              cfg.outputDir
              (builtins.dirOf cfg.eventSpool)
            ];
          };
          timer = {
            onCalendar = cfg.onCalendar;
            persistent = true;
            description = "Daily terminal result-gap digest";
          };
        }
      )
      {
        systemd.tmpfiles.rules = [
          "d ${cfg.outputDir} 0750 ${userName} users -"
        ];
      }
    ];
} args
