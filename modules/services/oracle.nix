# Oracle daily reverse-prompting digest.
#
# Wraps `scripts/oracle` in a systemd user-style oneshot + timer, disabled by
# default (target cost ~$0.10/run, ≤$5/month). The unit invokes the script
# directly out of the live sinnix checkout; no copy is made because the
# script's substrate paths are host-specific anyway.
#
# Enable with:
#   sinnix.services.oracle.enable = true;
#   sinnix.services.oracle.timer.enable = true;
{
  mkServiceModule,
  lib,
  pkgs,
  config,
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
  configFn = _: {
    sinnix.persistence.home.directories = [ ".local/share/oracle" ];
  };
  # Function form. The `timer` key stays statically present (its VALUE
  # carries `enable = cfg.timer.enable`, deferred through mkScheduledJob's
  # mkIf wrapping) rather than being conditionally omitted via
  # `lib.optionalAttrs cfg.timer.enable { timer = ...; }`: the latter forces
  # cfg.timer.enable to decide this module's OWN config SHAPE, which is a
  # genuine self-referential blackhole for a same-module option (see
  # modules/lib/scheduled-job.nix's `timer.enable` doc comment). The
  # rendered behaviour is identical to the previous
  # `lib.mkIf cfg.timer.enable { ... }` on the hand-rolled
  # systemd.user.timers.oracle: no timer unit at all when disabled.
  job =
    { cfg, pkgs, ... }:
    let
      oracleScript = "${config.sinnix.paths.projectRoot}/scripts/oracle";
    in
    {
      unitName = "oracle";
      manager = "user";
      description = "Oracle daily reverse-prompting digest";
      # outputDir is passed through, not merely declared. It used to be an
      # option with a type, a default and a description saying where
      # digests are written -- that nothing read, so setting it did
      # nothing. An option that silently ignores you is worse than no
      # option; the script has taken --output all along.
      execStart = "${pkgs.bash}/bin/bash -lc '${oracleScript} --output-dir ${lib.escapeShellArg cfg.outputDir}'";
      serviceConfig = {
        TimeoutStartSec = 600;
      };
      unit = {
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
      };
      timer = {
        enable = cfg.timer.enable;
        onCalendar = cfg.timer.onCalendar;
        randomizedDelaySec = cfg.timer.randomizedDelaySec;
        persistent = true;
        description = "Daily oracle digest";
      };
    };
} args
