# below: Time-traveling resource monitor for Linux
#
# Records system state continuously for post-mortem debugging.
# Use `below replay` to investigate what happened at any point in time.
#
# Data stored in /var/log/below (default).
# Storage: ~10-20 MB/day at 1s interval with zstd (~10x).
# No retention limit = accumulate indefinitely (~4-8 GB/year at 1s).
# Export via: below dump -O json/csv
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
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
    { cfg, pkgs, ... }:
    {
      environment.systemPackages = [ pkgs.below ];

      # /var/log/below/store is the below data directory. Create it via tmpfiles
      # so below.service can start even if the /persist bind-mount hasn't activated
      # yet (e.g. first boot without @blank). When impermanence is active, the
      # bind-mount overlays this and persists the data across reboots.
      systemd.tmpfiles.rules = [
        "d /var/log/below 0755 root root -"
        "d /var/log/below/store 0755 root root -"
      ];

      systemd.services.below = {
        description = "below - Time traveling resource monitor";
        wantedBy = [ "multi-user.target" ];
        after = [ "local-fs.target" ];

        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.below}/bin/below record --collect-io-stat --compress --interval-s ${toString cfg.collectIntervalSec}";
          Restart = "on-failure";
          RestartSec = "5s";
        };
      };
    };
} args
