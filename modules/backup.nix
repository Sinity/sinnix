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
  inherit (config.sinnix.paths) realmRoot;
  borgRepoRoot = "${config.sinnix.paths.outerRealm}/backup";

  # Snapshot directories
  realmSnapshots = "${realmRoot}/.snapshot";
  persistSnapshots = "/persist/.snapshot";
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
    # Schedule-based retention does nothing unless snapshot_preserve_min stops
    # defaulting to "all". Keep a single latest snapshot by default.
    snapshot_preserve_min   latest
    ssh_identity            /etc/ssh/ssh_host_ed25519_key
    transaction_log         /var/log/btrbk.log
    lockfile                /var/lock/btrbk.lock

    # ─── SNAPSHOTS ONLY (Borg handles all off-disk transfers) ───
    # Keep every 15-minute snapshot for 4h, then thin to hourly for 3d,
    # daily for 14d, and weekly for 8w.

    volume ${realmRoot}
      snapshot_dir   .snapshot
      subvolume .
        snapshot_preserve_min   4h
        snapshot_preserve       72h 14d 8w

    volume /persist
      snapshot_dir   .snapshot
      subvolume .
        snapshot_preserve_min   4h
        snapshot_preserve       72h 14d 8w

    # / is ephemeral (wiped and recreated each boot by initrd rollback script).
    # Pre-wipe states are saved by initrd to .snapshots/root.TIMESTAMP.
    # btrbk snapshotting / would be pointless — it resets every boot.

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
          "**/inbox/monero"
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
      requires = [ "sinnix-realm-sinex-target-subvolume.service" ];
      after = [ "persist.mount" "realm.mount" "sinnix-realm-sinex-target-subvolume.service" ];
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

    systemd.services.sinnix-realm-sinex-target-subvolume = {
      description = "Ensure /realm/project/sinex/.sinex/target is a dedicated Btrfs subvolume";
      after = [ "realm.mount" ];
      requires = [ "realm.mount" ];
      before = [ "btrbk.service" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig.Type = "oneshot";
      script = ''
        set -euo pipefail

        target_parent="/realm/project/sinex/.sinex"
        target_path="$target_parent/target"

        ${pkgs.coreutils}/bin/mkdir -p "$target_parent"

        if ${pkgs.btrfs-progs}/bin/btrfs subvolume show "$target_path" >/dev/null 2>&1; then
          exit 0
        fi

        if ${pkgs.coreutils}/bin/test -e "$target_path" && ! ${pkgs.coreutils}/bin/test -d "$target_path"; then
          echo "$target_path exists but is not a directory" >&2
          exit 1
        fi

        if ${pkgs.coreutils}/bin/test -d "$target_path"; then
          if ${pkgs.findutils}/bin/find "$target_path" -mindepth 1 -print -quit | ${pkgs.gnugrep}/bin/grep -q .; then
            echo "$target_path already exists as a non-empty directory; refusing to replace it automatically" >&2
            exit 1
          fi
          ${pkgs.coreutils}/bin/rmdir "$target_path"
        fi

        ${pkgs.btrfs-progs}/bin/btrfs subvolume create "$target_path"
      '';
    };
  };
}
