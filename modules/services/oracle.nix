# Oracle daily reverse-prompting digest.
#
# Wraps `scripts/oracle` in a systemd user-style oneshot + timer. Disabled by
# default — enable manually once cost calibration is in (target ~$0.10/run,
# ≤$5/month). The unit invokes the script directly out of the live sinnix
# checkout; no copy is made because the script's substrate paths are
# host-specific anyway.
#
# Enable with:
#   sinnix.services.oracle.enable = true;
#   sinnix.services.oracle.timer.enable = true;
#
# Not yet wired into flake.nix — that's a separate decision once the MVP has
# logged a few days of useful output.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "oracle";
  description = "oracle daily reverse-prompting digest";
  extraOptions = {
    timer = {
      enable = lib.mkEnableOption "daily oracle digest timer";

      onCalendar = lib.mkOption {
        type = lib.types.str;
        default = "*-*-* 07:00:00";
        description = "systemd OnCalendar expression for the daily digest run.";
      };

      randomizedDelaySec = lib.mkOption {
        type = lib.types.int;
        default = 600;
        description = "Max randomized delay in seconds.";
      };
    };

    outputDir = lib.mkOption {
      type = lib.types.str;
      default = "%h/.local/share/oracle";
      description = "Directory where YYYY-MM-DD.md digests are written.";
    };
  };
  configFn =
    { cfg, pkgs, ... }:
    let
      oracleScript = "/realm/project/sinnix/scripts/oracle";
    in
    {
      sinnix.persistence.home.directories = [ ".local/share/oracle" ];

      systemd.user.services.oracle = {
        description = "Oracle daily reverse-prompting digest";
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${pkgs.bash}/bin/bash -lc '${oracleScript}'";
          TimeoutStartSec = 600;
        };
      };

      systemd.user.timers.oracle = lib.mkIf cfg.timer.enable {
        description = "Daily oracle digest";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = cfg.timer.onCalendar;
          RandomizedDelaySec = toString cfg.timer.randomizedDelaySec;
          Persistent = true;
        };
      };
    };
} args
