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
  realmSnapshots = "${realmRoot}/.btrfs/snapshot";
  persistSnapshots = "/persist/.btrfs/snapshot";
  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  borgPersistSnapshotBind = "${borgSnapshotBindRoot}/persist";
  borgRealmSnapshotBind = "${borgSnapshotBindRoot}/realm";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoPersist = "file://${borgRepoPersistPath}";
  borgRepoRealm = "file://${borgRepoRealmPath}";
  borgPassphrasePath = config.sinnix.secrets.paths."borg-passphrase";
  realmDevice = "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea";
  persistDevice = "/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02";
  outerRealmDevice = "/dev/disk/by-uuid/250683a9-c13f-4546-a29b-a743f3babb43";
  borgBandwidth = "80M";
  btrbkBandwidth = "100M";
  borgMemoryHigh = "8G";
  borgMemoryMax = "20G";
  mkBandwidthCaps = rate: devices: map (device: "${device} ${rate}") devices;

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
    persistentTimer = false;
    prune.keep = {
      within = "2d";
      daily = 14;
      weekly = 8;
      monthly = 6;
    };
    # / is ephemeral; persist the chunk cache so backups are truly incremental
    # (without it, borg re-reads + re-chunks every file on every run).
    environment.BORG_CACHE_DIR = "/persist/root/.cache/borg";
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
    # btrbk covers the intra-day window that borg doesn't: fine-grained rollback
    # for recent work. Borg runs daily overnight; once a day is borged, the
    # fine-grained snapshots for that day have little value.
    #
    # Retention: btrbk fills the gaps between overnight borg runs.
    # Keep all 30-min snapshots for 6h (the "oops I just broke it" window),
    # then hourly for 24h (covers two borg cycles as buffer), then drop.
    # Beyond 24h, borg has it covered with better dedup and off-disk safety.

    volume ${realmRoot}
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   6h
        snapshot_preserve       24h

    volume /persist
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   6h
        snapshot_preserve       24h

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
        startAt = "*-*-* 02:17:00"; # overnight, offset from btrbk :12/:42 marks
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
          "/persist/home/sinity/.config/chrome-ws/Default/Service Worker"
          "/persist/home/sinity/.config/chrome-ws/Default/GPUCache"
          "/persist/home/sinity/.config/chrome-ws/*Cache*"
          "/persist/home/sinity/.config/chrome-ws/*cache*"
        ];
        repo = borgRepoPersist;
        readWritePaths = [
          borgSnapshotBindRoot
          borgRepoRoot
          "/persist/root/.cache/borg"
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
        startAt = "*-*-* 03:17:00"; # overnight, offset from btrbk :12/:42 marks
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
          "/persist/root/.cache/borg"
        ];
        preHook = mkBindMountedSnapshotHook {
          label = "realm";
          snapshotDir = realmSnapshots;
          snapshotGlob = "realm.*";
          bindTarget = borgRealmSnapshotBind;
        };
      };
    };

    # Performance tuning for Borg. Nice/CPUWeight do not protect the desktop
    # from NVMe/HDD stalls, and IOSchedulingClass=idle is ineffective on the
    # active schedulers. Use hard cgroup I/O caps and do not run missed backup
    # timers immediately after boot.
    systemd.services.borgbackup-job-persist.serviceConfig = {
      Nice = 19;
      CPUWeight = 1;
      IOWeight = 1;
      MemoryHigh = borgMemoryHigh;
      MemoryMax = borgMemoryMax;
      IOReadBandwidthMax = mkBandwidthCaps borgBandwidth [ persistDevice ];
      IOWriteBandwidthMax = mkBandwidthCaps borgBandwidth [
        persistDevice
        outerRealmDevice
      ];
    };
    systemd.services.borgbackup-job-realm.serviceConfig = {
      Nice = 19;
      CPUWeight = 1;
      IOWeight = 1;
      MemoryHigh = borgMemoryHigh;
      MemoryMax = borgMemoryMax;
      IOReadBandwidthMax = mkBandwidthCaps borgBandwidth [
        realmDevice
        persistDevice
      ];
      IOWriteBandwidthMax = mkBandwidthCaps borgBandwidth [
        persistDevice
        outerRealmDevice
      ];
    };

    # Weekly integrity check — verify repo metadata, detect bit rot on the HDD.
    # Runs repository-only (fast, ~minutes) not --verify-data (reads all chunks, hours).
    systemd.services.borgbackup-check = {
      description = "Borg backup integrity check";
      serviceConfig = {
        Type = "oneshot";
        Nice = 19;
        CPUWeight = 1;
        IOWeight = 1;
        IOReadBandwidthMax = mkBandwidthCaps borgBandwidth [
          persistDevice
          outerRealmDevice
        ];
        IOWriteBandwidthMax = mkBandwidthCaps borgBandwidth [
          persistDevice
          outerRealmDevice
        ];
      };
      environment.BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
      script = ''
        ${pkgs.borgbackup}/bin/borg check --repository-only ${borgRepoPersist}
        ${pkgs.borgbackup}/bin/borg check --repository-only ${borgRepoRealm}
      '';
    };
    systemd.timers.borgbackup-check = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "Sun 06:17:00";
        Persistent = false;
      };
    };

    system.activationScripts.borgRepositoryDirectories.text = ''
      ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g users ${borgRepoRoot}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPersistPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRealmPath}
    '';

    # Ensure directories exist
    # Borg chunk cache must survive reboots. / is ephemeral, so the default
    # ~/.cache/borg is lost on every boot, forcing a full re-read + re-chunk
    # of every file (616GB read for 2.4GB written — a 256:1 waste).
    # Persist it under /persist so backups are truly incremental.
    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${realmSnapshots} 0750 root users -"
      "d ${persistSnapshots} 0750 root users -"
      "d ${borgSnapshotBindRoot} 0700 root root -"
      "d ${borgPersistSnapshotBind} 0700 root root -"
      "d ${borgRealmSnapshotBind} 0700 root root -"
      "d ${borgRepoRoot} 0750 root users -"
      "d /persist/root/.cache/borg 0700 root root -"
    ];

    # systemd services for btrbk
    # Depends on all snapshotted volumes being mounted. neo-outer-realm is an
    # HDD (slow spin-up) with nofail — without this, btrbk races the mount on boot.
    systemd.services.btrbk = {
      description = "btrbk btrfs snapshot";
      after = [
        "persist.mount"
        "realm.mount"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.btrbk}/bin/btrbk run --quiet";
        Nice = 19;
        IOSchedulingClass = "idle";
        IOWeight = 1;
        IOReadBandwidthMax = mkBandwidthCaps btrbkBandwidth [
          realmDevice
          persistDevice
        ];
        IOWriteBandwidthMax = mkBandwidthCaps btrbkBandwidth [
          realmDevice
          persistDevice
        ];
      };
    };

    systemd.timers.btrbk = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* *:12/30:00";
        Persistent = false;
      };
    };

  };
}
