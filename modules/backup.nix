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
  realmSnapshots = "${realmRoot}/.snapshot";
  rootSnapshots = "/.snapshot";
  varSnapshots = "/var/.snapshot";
  neoSnapshots = "${neoOuterRealm}/.snapshot";

  # Borg Configuration
  borgRepoSystem = "${config.sinnix.paths.outerRealm}/backup/borg-var";
  borgRepoRealm = "${config.sinnix.paths.outerRealm}/backup/borg-realm";

  commonBorgOptions = {
    encryption.mode = "none";
    compression = "auto,zstd,3";
    startAt = "daily";
    persistentTimer = true;
    environment = {
      BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK = "yes";
    };
    prune.keep = {
      daily = 14;
      weekly = 8;
      monthly = 6;
    };
  };

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
      snapshot_dir   .snapshot
      subvolume .
        snapshot_preserve       14d 52w

    volume /var
      snapshot_dir   .snapshot
      subvolume .
        snapshot_preserve       14d 52w

    volume /
      snapshot_dir   .snapshot
      subvolume .
        snapshot_preserve       30d 52w

    volume ${neoOuterRealm}
      snapshot_dir   .snapshot
      snapshot_create always
      subvolume .
        snapshot_preserve       30d 52w
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
      var = commonBorgOptions // {
        paths = [
          # Backup the latest snapshot to ensure data consistency
          # Use trailing slash to force traversal into the symlinked dir
          "/var/.snapshot/var.latest/"
        ];
        exclude = [
          "/var/tmp"
          "/var/cache"
          "/var/lib/systemd/coredump"
        ];
        repo = borgRepoSystem;
        # Allow creating the .latest symlink in the snapshot dir
        readWritePaths = [ "/var/.snapshot" ];
        # Hook to symlink the latest snapshot before backup
        preHook = ''
          latest="$(
            ${pkgs.findutils}/bin/find /var/.snapshot -maxdepth 1 -mindepth 1 -type d -name 'var.*' -printf '%f\n' \
              | ${pkgs.coreutils}/bin/sort | ${pkgs.coreutils}/bin/tail -n 1
          )"
          if [ -n "$latest" ]; then
            ${pkgs.coreutils}/bin/ln -sfn "/var/.snapshot/$latest" /var/.snapshot/var.latest
          fi
        '';
      };

      # 2. User Data (/realm snapshots) - runs as sinity
      realm = commonBorgOptions // {
        user = username;
        group = "users";
        paths = [
          # Backup the latest snapshot to ensure data consistency
          # Use trailing slash to force traversal into the symlinked dir
          "${realmRoot}/.snapshot/realm.latest/"
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
          "/realm/data/runtime"
        ];
        repo = borgRepoRealm;
        # Allow creating the .latest symlink in the snapshot dir
        readWritePaths = [ "${realmRoot}/.snapshot" ];
        # Hook to symlink the latest snapshot before backup
        preHook = ''
          latest="$(
            ${pkgs.findutils}/bin/find ${realmRoot}/.snapshot -maxdepth 1 -mindepth 1 -type d -name 'realm.*' -printf '%f\n' \
              | ${pkgs.coreutils}/bin/sort | ${pkgs.coreutils}/bin/tail -n 1
          )"
          if [ -n "$latest" ]; then
            ${pkgs.coreutils}/bin/ln -sfn "${realmRoot}/.snapshot/$latest" ${realmRoot}/.snapshot/realm.latest
          fi
        '';
      };
    };

    # Performance tuning for Borg
    systemd.services.borgbackup-job-var.serviceConfig = {
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
      "d ${config.sinnix.paths.outerRealm}/backup 0750 root users -"
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
        OnCalendar = "*-*-* *:00/15:00";
        Persistent = true;
      };
    };
  };
}
