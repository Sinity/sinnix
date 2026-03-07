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
  borgRepoRoot = "${config.sinnix.paths.outerRealm}/backup";

  # Snapshot directories
  realmSnapshots = "${realmRoot}/.snapshot";
  rootSnapshots = "/.snapshot";
  varSnapshots = "/var/.snapshot";
  neoSnapshots = "${neoOuterRealm}/.snapshot";
  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  borgVarSnapshotBind = "${borgSnapshotBindRoot}/var";
  borgRealmSnapshotBind = "${borgSnapshotBindRoot}/realm";

  # Borg Configuration
  borgRepoSystemPath = "${borgRepoRoot}/borg-var-v2";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoSystem = "file://${borgRepoSystemPath}";
  borgRepoRealm = "file://${borgRepoRealmPath}";
  borgPassphrasePath = config.sinnix.secrets.paths."borg-passphrase";

  mkBindMountedSnapshotHook =
    {
      label,
      snapshotDir,
      snapshotGlob,
      bindTarget,
    }:
    ''
      cleanup_${label}_snapshot_bind_mount() {
        if ${pkgs.util-linux}/bin/mountpoint -q "${bindTarget}"; then
          ${pkgs.util-linux}/bin/umount "${bindTarget}"
        fi
      }

      trap cleanup_${label}_snapshot_bind_mount EXIT

      latest_snapshot="$(
        ${pkgs.findutils}/bin/find ${snapshotDir} -maxdepth 1 -mindepth 1 -type d -name '${snapshotGlob}' -printf '%f\n' \
          | ${pkgs.coreutils}/bin/sort | ${pkgs.coreutils}/bin/tail -n 1
      )"

      if [ -z "$latest_snapshot" ]; then
        echo "No ${label} snapshot found in ${snapshotDir}" >&2
        exit 1
      fi

      ${pkgs.coreutils}/bin/mkdir -p "${bindTarget}"
      cleanup_${label}_snapshot_bind_mount || true
      ${pkgs.util-linux}/bin/mount --bind "${snapshotDir}/$latest_snapshot" "${bindTarget}"
    '';

  commonBorgOptions = {
    encryption = {
      mode = "repokey-blake2";
      passCommand = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
    };
    compression = "auto,zstd,3";
    startAt = "daily";
    persistentTimer = true;
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
          # Borg treats symlink roots as symlinks, not traversed directories.
          # Bind-mount the newest snapshot to a stable path and archive that path.
          "${borgVarSnapshotBind}/./"
        ];
        exclude = [
          "/var/tmp"
          "/var/cache"
          "/var/lib/systemd/coredump"
        ];
        repo = borgRepoSystem;
        readWritePaths = [
          borgSnapshotBindRoot
          borgRepoRoot
        ];
        preHook = mkBindMountedSnapshotHook {
          label = "var";
          snapshotDir = varSnapshots;
          snapshotGlob = "var.*";
          bindTarget = borgVarSnapshotBind;
        };
      };

      # 2. User Data (/realm snapshots) - runs as root so the bind mount can be created
      realm = commonBorgOptions // {
        paths = [
          "${borgRealmSnapshotBind}/./"
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
        ];
        repo = borgRepoRealm;
        readWritePaths = [
          borgSnapshotBindRoot
          borgRepoRoot
        ];
        preHook = mkBindMountedSnapshotHook {
          label = "realm";
          snapshotDir = realmSnapshots;
          snapshotGlob = "realm.*";
          bindTarget = borgRealmSnapshotBind;
        };
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

    system.activationScripts.borgRepositoryDirectories.text = ''
      ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g users ${borgRepoRoot}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoSystemPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRealmPath}
    '';

    # Ensure directories exist
    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${realmSnapshots} 0750 root users -"
      "d ${rootSnapshots} 0750 root users -"
      "d ${varSnapshots} 0750 root users -"
      "d ${neoSnapshots} 0750 root users -"
      "d ${borgSnapshotBindRoot} 0700 root root -"
      "d ${borgVarSnapshotBind} 0700 root root -"
      "d ${borgRealmSnapshotBind} 0700 root root -"
      "d ${borgRepoRoot} 0750 root users -"
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
