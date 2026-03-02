# Comprehensive Unified Backup Strategy
#
# 1. btrbk: Local snapshots for instant rollbacks (block-level, zero I/O overhead)
# 2. Borg: Off-disk incremental backups (file-level, with exclusions, deduplicated)
#
# Drive           Label            Mount            Purpose
# ────────────────────────────────────────────────────────────────────────────
# /dev/nvme0n1p3  SSD_4TB          /realm           Source: projects, home, data
# /dev/sda2       root_btrfs       /                Source: System & /var
# /dev/sdc1       outer-realm      /outer-realm     Target: Borg & btrbk archives
{
  pkgs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot neoOuterRealm;
  username = config.sinnix.user.name;

  # Snapshot directories
  realmSnapshots = "${realmRoot}/.snapshots";
  rootSnapshots = "/.snapshots";
  varSnapshots = "/var/.snapshots";
  neoSnapshots = "${neoOuterRealm}/.snapshots";

  # Borg Configuration
  borgRepoSystem = "${config.sinnix.paths.outerRealm}/backups/borg-system";
  borgRepoRealm = "${config.sinnix.paths.outerRealm}/backups/borg-realm";

  btrbkConfig = ''
    # === Global settings ===
    timestamp_format        long-iso
    snapshot_create          onchange
    incremental             yes
    preserve_day_of_week    monday
    ssh_identity            /etc/ssh/ssh_host_ed25519_key
    transaction_log         /var/log/btrbk.log
    lockfile                /var/lock/btrbk.lock

    # ─── SNAPSHOTS ONLY (Borg handles all off-disk transfers) ───
    
    volume ${realmRoot}
      snapshot_dir   ${realmSnapshots}
      subvolume .
        snapshot_preserve       48h 14d 8w

    volume /var
      snapshot_dir   ${varSnapshots}
      subvolume .
        snapshot_preserve       48h 14d 8w

    volume /
      snapshot_dir   ${rootSnapshots}
      subvolume .
        snapshot_preserve       7d 4w

    volume ${neoOuterRealm}
      snapshot_dir   ${neoSnapshots}
      snapshot_create always
      subvolume .
        snapshot_preserve       7d 4w
  '';

in
{
  config = {
    environment.systemPackages = [
      pkgs.btrbk
      pkgs.borgbackup
    ];

    # btrbk configuration
    environment.etc."btrbk/btrbk.conf".text = btrbkConfig;

    # ─── Borg Backup Jobs ───
    services.borgbackup.jobs = {
      # 1. System State (/var snapshots) - runs as root
      system = {
        paths = [
          # Backup the latest snapshot to ensure data consistency
          "${varSnapshots}/var.latest"
        ];
        exclude = [
          "/var/tmp"
          "/var/cache"
          "/var/lib/systemd/coredump"
        ];
        repo = borgRepoSystem;
        encryption.mode = "none";
        compression = "zstd,1";
        startAt = "daily";
        persistentTimer = true;
        prune.keep = {
          daily = 14;
          weekly = 8;
          monthly = 6;
        };
        # Hook to symlink the latest snapshot before backup
        preHook = ''
          latest=$(ls -td ${varSnapshots}/var.* | grep -v 'var.latest' | head -n 1 || true)
          if [ -n "$latest" ]; then
            ln -sfn "$latest" ${varSnapshots}/var.latest
          fi
        '';
      };

      # 2. User Data (/realm snapshots) - runs as sinity
      realm = {
        user = username;
        group = "users";
        paths = [
          # Backup the latest snapshot to ensure data consistency
          "${realmSnapshots}/realm.latest"
        ];
        exclude = [
          "**/node_modules"
          "**/target"
          "**/.venv"
          "**/.direnv"
          "**/.ruff_cache"
          "**/.pytest_cache"
          "**/.cache"
          "**/build"
          "**/dist"
          "**/*.pyc"
          "**/.Trash-1000"
          "/realm/data/indices"
        ];
        repo = borgRepoRealm;
        encryption.mode = "none";
        compression = "zstd,1";
        startAt = "daily";
        persistentTimer = true;
        prune.keep = {
          daily = 14;
          weekly = 8;
          monthly = 6;
        };
        # Hook to symlink the latest snapshot before backup
        preHook = ''
          latest=$(ls -td ${realmSnapshots}/realm.* | grep -v 'realm.latest' | head -n 1 || true)
          if [ -n "$latest" ]; then
            ln -sfn "$latest" ${realmSnapshots}/realm.latest
          fi
        '';
      };
    };

    # Performance tuning for Borg
    systemd.services.borgbackup-job-system.serviceConfig = {
      Nice = 19;
      IOSchedulingClass = "idle";
      IOSchedulingPriority = 7;
    };
    systemd.services.borgbackup-job-realm.serviceConfig = {
      Nice = 19;
      IOSchedulingClass = "idle";
      IOSchedulingPriority = 7;
    };

    # Ensure directories exist
    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${realmSnapshots} 0750 root users -"
      "d ${rootSnapshots} 0750 root users -"
      "d ${varSnapshots} 0750 root users -"
      "d ${neoSnapshots} 0750 root users -"
      "d ${config.sinnix.paths.outerRealm}/backups 0750 root users -"
      "d ${borgRepoSystem} 0700 root root -"
      "d ${borgRepoRealm} 0750 ${username} users -"
    ];

    # systemd services for btrbk
    systemd.services.btrbk = {
      description = "btrbk btrfs snapshot";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.btrbk}/bin/btrbk run --quiet";
        Nice = 19;
        IOSchedulingClass = "idle";
      };
    };

    systemd.timers.btrbk = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "hourly";
        Persistent = true;
      };
    };
  };
}
