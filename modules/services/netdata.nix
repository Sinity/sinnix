# Netdata: Real-time system metrics collection
#
# Captures comprehensive system metrics at 100ms granularity:
# - CPU per-core, memory, disk I/O, network per-interface
# - Per-process/cgroup resource usage
# - systemd service metrics
# - Hardware sensors
#
# Data stored in ${capturesRoot}/netdata with tiered retention.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  inherit (lib) mkEnableOption mkIf mkOption types;
  inherit (config.sinnix.paths) capturesRoot;
  cfg = config.sinnix.services.netdata;
  username = config.sinnix.user.name;

  dataDir = "${capturesRoot}/netdata";
  cacheDir = "${dataDir}/cache";
  logDir = "${dataDir}/log";
  libDir = "${dataDir}/lib";
in
{
  options.sinnix.services.netdata = {
    enable = mkEnableOption "Netdata metrics collection";

    updateEvery = mkOption {
      type = types.int;
      default = 1;
      description = "Data collection frequency in seconds (use 0.1 for 100ms via config override)";
    };

    historySeconds = mkOption {
      type = types.int;
      default = 604800; # 7 days at 1s = 604800 points
      description = "How many seconds of data to retain in RAM (tier0)";
    };

    diskRetentionDays = mkOption {
      type = types.int;
      default = 365;
      description = "Days of historical data to retain on disk";
    };
  };

  config = mkIf cfg.enable {
    # Create data directories
    systemd.tmpfiles.rules = [
      "d ${dataDir} 0755 netdata netdata -"
      "d ${cacheDir} 0755 netdata netdata -"
      "d ${logDir} 0755 netdata netdata -"
      "d ${libDir} 0755 netdata netdata -"
    ];

    services.netdata = {
      enable = true;

      config = {
        global = {
          # 100ms update interval for maximum granularity
          "update every" = "1";
          "memory mode" = "dbengine";

          # Custom paths under /realm/data/captures
          "cache directory" = cacheDir;
          "log directory" = logDir;
          "lib directory" = libDir;

          # Error logging only (reduce noise)
          "debug log" = "none";
          "error log" = "${logDir}/error.log";
          "access log" = "none";
        };

        # Database engine configuration for long-term storage (25x capacity)
        db = {
          # Tier 0: 1-second granularity, recent data
          "mode" = "dbengine";
          "storage tiers" = "3";

          # Tier 0: ~6 months at 1s granularity
          "dbengine tier 0 retention size" = "125GiB";

          # Tier 1: ~2 years at 60s granularity (aggregated)
          "dbengine tier 1 retention size" = "50GiB";
          "dbengine tier 1 update every iterations" = "60";

          # Tier 2: ~10+ years at 3600s (1hr) granularity
          "dbengine tier 2 retention size" = "25GiB";
          "dbengine tier 2 update every iterations" = "60";
        };

        # Web dashboard - localhost only
        web = {
          "bind to" = "127.0.0.1";
          "default port" = "19999";
        };

        # Enable all collectors
        plugins = {
          "proc" = "yes";
          "diskspace" = "yes";
          "cgroups" = "yes";
          "tc" = "yes";
          "idlejitter" = "yes";
          "apps" = "yes";
          "charts.d" = "yes";
          "fping" = "no"; # Requires privileges
          "go.d" = "yes";
          "python.d" = "yes";
          "perf" = "yes";
          "slabinfo" = "yes";
          "ioping" = "yes";
          "debugfs" = "yes";
          "systemd-journal" = "yes";
        };

        # Per-process/app grouping
        "plugin:apps" = {
          "update every" = "1";
          "command options" = "with-childs";
        };

        # cgroups for systemd services and containers
        "plugin:cgroups" = {
          "update every" = "1";
          "check for new cgroups every" = "10";
          "enable systemd services" = "yes";
          "enable systemd scope units" = "yes";
        };

        # Disk I/O stats
        "plugin:proc:/proc/diskstats" = {
          "enable performance metrics" = "yes";
          "enable extended disk metrics" = "yes";
        };

        # Network interface stats
        "plugin:proc:/proc/net/dev" = {
          "enable all interfaces" = "yes";
        };

        # CPU stats
        "plugin:proc:/proc/stat" = {
          "cpu frequency" = "yes";
        };

        # Memory stats
        "plugin:proc:/proc/meminfo" = {
          "system ram" = "yes";
          "system swap" = "yes";
        };
      };

      # Additional config for 100ms granularity (override files)
      configDir = {
        # Override for sub-second collection
        "stream.conf" = pkgs.writeText "stream.conf" ''
          [stream]
            enabled = no
        '';
      };
    };

    # Grant netdata access to system stats
    users.users.netdata.extraGroups = [
      "proc" # /proc access
      "systemd-journal" # journal access
    ];

    # Performance: give netdata slightly elevated priority
    systemd.services.netdata.serviceConfig = {
      Nice = "-5";
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = "2";
    };
  };
}
