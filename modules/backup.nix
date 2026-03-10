# Comprehensive Unified Backup Strategy
#
# 1. btrbk: Local snapshots for instant rollbacks (block-level, zero I/O overhead)
# 2. Borg: Off-disk incremental backups (file-level, with exclusions, deduplicated)
#
# Drive           Label            Mount            Purpose
# ────────────────────────────────────────────────────────────────────────────
# /dev/nvme0n1p3  SSD_4TB          /realm           Source: projects, data
# /dev/sdc2       root_btrfs       /persist         Source: system & home state
# /dev/sdc1       outer-realm      /outer-realm     Target: Borg & btrbk archives
# Note: / is ephemeral — not snapshotted by btrbk (initrd saves pre-wipe states)
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
  persistSnapshots = "/persist/.snapshot";
  neoSnapshots = "${neoOuterRealm}/.snapshot";
  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  borgPersistSnapshotBind = "${borgSnapshotBindRoot}/persist";
  borgRealmSnapshotBind = "${borgSnapshotBindRoot}/realm";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoPersist = "file://${borgRepoPersistPath}";
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

    volume /persist
      snapshot_dir   .snapshot
      subvolume .
        snapshot_preserve       14d 52w

    # / is ephemeral (wiped and recreated each boot by initrd rollback script).
    # Pre-wipe states are saved by initrd to .snapshots/root.TIMESTAMP.
    # btrbk snapshotting / would be pointless — it resets every boot.

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
      # 1. Persistent state (/persist snapshots) - runs as root
      #    Replaced the old borg-var-v2 job. /persist now contains all system
      #    and home state that was previously split between @var and /realm/home.
      persist = commonBorgOptions // {
        paths = [
          # Borg treats symlink roots as symlinks, not traversed directories.
          # Bind-mount the newest snapshot to a stable path and archive that path.
          "${borgPersistSnapshotBind}/./"
        ];
        exclude = [
          # Large game library — relocate to /realm/data/libraries/ eventually
          "/persist/home/sinity/.local/share/Steam"
          # Ephemeral junk
          "/persist/var/lib/systemd/coredump"
          "/persist/home/sinity/.config/google-chrome/Default/Cache"
          "/persist/home/sinity/.config/google-chrome/Default/Code Cache"
          "/persist/home/sinity/.config/google-chrome/Default/Service Worker"
        ];
        repo = borgRepoPersist;
        readWritePaths = [
          borgSnapshotBindRoot
          borgRepoRoot
        ];
        preHook = mkBindMountedSnapshotHook {
          label = "persist";
          snapshotDir = persistSnapshots;
          snapshotGlob = "persist.*";
          bindTarget = borgPersistSnapshotBind;
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
    systemd.services.borgbackup-job-persist.serviceConfig = {
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
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPersistPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRealmPath}
    '';

    # Ensure directories exist
    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${realmSnapshots} 0750 root users -"
      "d ${persistSnapshots} 0750 root users -"
      "d ${neoSnapshots} 0750 root users -"
      "d ${borgSnapshotBindRoot} 0700 root root -"
      "d ${borgPersistSnapshotBind} 0700 root root -"
      "d ${borgRealmSnapshotBind} 0700 root root -"
      "d ${borgRepoRoot} 0750 root users -"
    ];

    # systemd services for btrbk
    # Depends on all snapshotted volumes being mounted. neo-outer-realm is an
    # HDD (slow spin-up) with nofail — without this, btrbk races the mount on boot.
    systemd.services.btrbk = {
      description = "btrbk btrfs snapshot";
      after = [ "neo-outer-realm.mount" "persist.mount" "realm.mount" ];
      wants = [ "neo-outer-realm.mount" ];
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
