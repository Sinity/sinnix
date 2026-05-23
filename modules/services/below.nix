# below: Time-traveling resource monitor for Linux
#
# Records system state continuously for post-mortem debugging.
# Use `below replay` to investigate what happened at any point in time.
#
# Data stored in /var/log/below (default).
# Retention is indefinite: at 1 s with dict-compress (chunk-32, ~8.8× over plain
# zstd) this is ~720 MB/day = ~260 GB/year. Without dict-compress: ~6.5 GB/day.
# Export via: below dump -O json/csv. Excluded from Borg in modules/backup.nix.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
in
mkServiceModule {
  name = "below";
  description = "below time-traveling resource monitor";
  health = {
    unit = "below.service";
    type = "service";
    restartable = true;
  };
  extraOptions = {
    collectIntervalSec = lib.mkOption {
      type = lib.types.int;
      default = 1;
      description = "Collection interval in seconds.";
    };
  };
  configFn =
    {
      cfg,
      config,
      pkgs,
      ...
    }:
    {
      environment.systemPackages = [
        pkgs.below
        scriptPkgs.sinnix-observe
      ];

      # /var/log/below/store is the below data directory. Create it via tmpfiles
      # so below.service can start even if the /persist bind-mount hasn't activated
      # yet (e.g. first boot without @blank). When impermanence is active, the
      # bind-mount overlays this and persists the data across reboots.
      systemd.tmpfiles.rules = [
        "d /var/log/below 0755 root root -"
        "d /var/log/below/store 0755 root root -"
        "d /var/log/below/home 0755 root root -"
        "d /var/log/below/cache 0755 root root -"
        "d /var/log/below/state 0755 root root -"
      ];

      systemd.services.below = {
        description = "below - Time traveling resource monitor";
        wantedBy = [ "multi-user.target" ];
        after = [ "local-fs.target" ];

        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.below}/bin/below record --collect-io-stat --compress --dict-compress-chunk-size 32 --interval-s ${toString cfg.collectIntervalSec}";
          Restart = "on-failure";
          RestartSec = "5s";
          # below is the recorder that remains useful under contention, so it
          # runs in the protected observability tier instead of default
          # system.slice placement.
          Slice = "system-critical.slice";
          Nice = -5;
          IOSchedulingClass = "best-effort";
          IOSchedulingPriority = 0;
        };
      };

    };
} args
