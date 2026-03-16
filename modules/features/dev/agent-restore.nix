{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "agentRestore"
  ];
  description = "Restore interrupted AI agent terminals after reboot";
  extraOptions = {
    autoRestore = lib.mkOption {
      type = lib.types.submodule {
        options = {
          enable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Automatically restore interrupted agent terminals when the graphical session starts.";
          };
          delaySeconds = lib.mkOption {
            type = lib.types.ints.unsigned;
            default = 4;
            description = "Seconds to wait after graphical session startup before checking for interrupted sessions.";
          };
          lookbackHours = lib.mkOption {
            type = lib.types.ints.positive;
            default = 72;
            description = "How far back to search the terminal capture ledger for interrupted sessions.";
          };
          maxSessions = lib.mkOption {
            type = lib.types.ints.positive;
            default = 8;
            description = "Maximum number of interrupted agent terminals to restore in one boot.";
          };
        };
      };
      default = { };
      description = "Automatic restore settings.";
    };
  };
  configFn =
    {
      config,
      cfg,
      user,
      ...
    }:
    let
      repoRoot = config.sinnix.paths.projectRoot;
      captureRoot = "${config.sinnix.paths.capturesRoot}/asciinema";
      graphicalTarget = "graphical-session.target";
      wrapper = ''
        #!/usr/bin/env bash
        set -euo pipefail
        exec ${pkgs.python3}/bin/python3 ${repoRoot}/scripts/sinnix-agent-session-restore "$@"
      '';
    in
    {
      home-manager.users.${user} =
        { lib, ... }:
        {
          home.file.".local/bin/sinnix-agent-session-restore" = {
            text = wrapper;
            executable = true;
          };

          systemd.user.services.sinnix-agent-session-restore = lib.mkIf cfg.autoRestore.enable (
            lib.sinnix.systemd.mkGraphicalUserService {
              description = "Restore interrupted agent terminals";
              target = graphicalTarget;
              serviceType = "oneshot";
              restart = "no";
              execStart =
                "${pkgs.python3}/bin/python3 ${repoRoot}/scripts/sinnix-agent-session-restore"
                + " --capture-root ${captureRoot}"
                + " --lookback-hours ${toString cfg.autoRestore.lookbackHours}"
                + " --max-sessions ${toString cfg.autoRestore.maxSessions}"
                + " restore"
                + " --auto"
                + " --settle-seconds ${toString cfg.autoRestore.delaySeconds}"
                + " --kitty-bin ${pkgs.kitty}/bin/kitty";
              unitExtra = {
                Requisite = [ graphicalTarget ];
              };
            }
          );
        };
    };
} args
