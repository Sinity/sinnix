# Comprehensive Unified Backup Strategy
#
# 1. btrbk: Local snapshots for instant rollbacks (block-level, zero I/O overhead)
# 2. Borg: Off-disk incremental backups (file-level, with exclusions, deduplicated)
#
# Drive           Label            Mount            Purpose
# ────────────────────────────────────────────────────────────────────────────
# /dev/nvme0n1p3  SSD_4TB          /realm           Source: projects, data
# /dev/sdb2       root_btrfs       /persist         Source: system & home state
# /dev/sda1       outer-realm      /outer-realm     Target: Borg & btrbk archives
# Note: / is ephemeral — not snapshotted by btrbk (initrd saves pre-wipe states)
{
  pkgs,
  lib,
  config,
  helpers,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot;
  borgRepoRoot = "${config.sinnix.paths.outerRealm}/backup";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  # Snapshot directories
  realmSnapshots = "${realmRoot}/.btrfs/snapshot";
  persistSnapshots = "/persist/.btrfs/snapshot";
  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  borgPersistSnapshotBind = "${borgSnapshotBindRoot}/persist";
  borgRealmSnapshotBind = "${borgSnapshotBindRoot}/realm";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  btrfsImageRoot = "${borgRepoRoot}/btrfs-images";
  borgRepoPersist = "file://${borgRepoPersistPath}";
  borgRepoRealm = "file://${borgRepoRealmPath}";
  borgPassphrasePath = config.sinnix.secrets.paths."borg-passphrase";
  backgroundBackupServiceConfig = {
    Nice = 10;
    CPUSchedulingPolicy = "idle";
    IOSchedulingClass = "idle";
    CPUWeight = 20;
    IOWeight = 20;
  };

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

  # ── shared borg-job constructor ──────────────────────────────────────
  # Wraps mkBindMountedSnapshotHook + commonBorgOptions + the shared
  # readWritePaths list around per-job policy (paths, excludes, repo,
  # startAt, snapshot args). Each new borg job becomes a single attrset.
  mkBorgJob =
    {
      name,
      startAt,
      repo,
      paths,
      exclude,
      snapshotDir,
      snapshotGlob,
      bindTarget,
      archiveBaseName ? null,
    }:
    commonBorgOptions
    // (lib.optionalAttrs (archiveBaseName != null) { inherit archiveBaseName; })
    // {
      inherit
        startAt
        paths
        exclude
        repo
        ;
      readWritePaths = [
        borgSnapshotBindRoot
        borgRepoRoot
        "/persist/root/.cache/borg"
      ];
      preHook = mkBindMountedSnapshotHook {
        label = name;
        inherit snapshotDir snapshotGlob bindTarget;
      };
    };

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
    # appendFailedSuffix + rename-on-success pattern is fragile: borgWrapper
    # never suppresses warnings (-z check is always false), so `borg create`
    # exiting with code 1 kills the script before the rename runs, leaving
    # every archive permanently named .failed.
    appendFailedSuffix = false;
    # Prevent lock-timeout failures: if a prior job crashed and left the lock,
    # give the next run a generous window to acquire it (HDD spin-up,
    # slow borg operations, etc. can all delay lock release).
    extraCreateArgs = [
      "--lock-wait"
      "7200"
    ];
  };

  btrbkConfig = ''
    # === Global settings ===
    timestamp_format        long-iso
    snapshot_create          onchange
    incremental             yes
    preserve_day_of_week    monday
    snapshot_preserve_min   latest
    ssh_identity            /etc/ssh/ssh_host_ed25519_key
    transaction_log         /var/log/btrbk.log
    lockfile                /var/lock/btrbk.lock

    # ─── Tier-1: fine-grained local rollback (btrbk) ───
    # Borg runs every 4h (:20). btrbk keeps ~9 snapshots per volume with
    # declining density: all 15-min for 30min, then thins to hourly out to 6h
    # (2h of overlap with the previous borg run as safety buffer).

    volume ${realmRoot}
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   30m
        snapshot_preserve       6h

    volume /persist
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   30m
        snapshot_preserve       6h

    # / is ephemeral (wiped and recreated each boot by initrd rollback script).
    # Pre-wipe states are saved to .snapshots/root.TIMESTAMP and archived by
    # a separate borg job (borgbackup-root-snapshots) that picks them up,
    # backs them up, and deletes the subvolume.

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
      persist = mkBorgJob {
        name = "persist";
        repo = borgRepoPersist;
        snapshotDir = persistSnapshots;
        snapshotGlob = "persist.*";
        bindTarget = borgPersistSnapshotBind;
        # Every 4h at :20 (5 min after btrbk :15, so latest snapshot is always ready)
        startAt = [ "*-*-* 02,06,10,14,18,22:20:00" ];
        paths = [
          # Borg treats symlink roots as symlinks, not traversed directories.
          # Bind-mount the newest snapshot to a stable path and archive that path.
          "${borgPersistSnapshotBind}/./"
        ];
        exclude = [
          # Archive-relative patterns: bind mount is at
          # /run/borgbackup-snapshot-inputs/persist/, so paths start from
          # the /persist snapshot root. /persist prefix never matches.
          # Game library — large, rebuilt from Steam
          "home/sinity/.local/share/Steam"
          # AI model caches — ephemeral, rebuildable
          "home/sinity/.cache/huggingface"
          # Streaming cache — ephemeral
          "home/sinity/.cache/spotify"
          # Borg's own cache — backing up the backup tool's cache is waste
          "root/.cache/borg"
          # Chromium browser caches
          "home/sinity/.config/chrome-ws/Default/Service Worker"
          "home/sinity/.config/chrome-ws/Default/GPUCache"
          "home/sinity/.config/chrome-ws/*Cache*"
          "home/sinity/.config/chrome-ws/*cache*"
          # Polylogue DB belongs in realm, not persist (32 GB wasted per backup)
          "home/sinity/.local/share/polylogue/polylogue.db"
          # below resource monitor: indefinite retention ~260 GB/year at 1 s,
          # post-mortem only — recover from live host, not backup.
          "var/log/below"
          # User caches — all regenerable; collectively ~30 GB on this host.
          # Specific entries (huggingface, spotify, chrome-ws) above stay as
          # documentation; the catch-all picks up sccache (11 G), sinex client
          # cache (6 G), media-preview-cache, uv, google-chrome, ms-playwright,
          # and anything else future tools drop here.
          "home/sinity/.cache"
          # System coredumps
          "var/lib/systemd/coredump"
          # Sinex service runtime state (Postgres data, NATS JetStream, CAS
          # blob-repository, per-source-worker state). Has its own snapshot
          # tooling — `sinexctl admin snapshot` (PR #1287) — and the
          # underlying data is either content-addressed (CAS, restorable
          # only by re-ingestion), transient (NATS event queue), or
          # operationally large (50+ GB pg data dir). Including in borg
          # would multiply repo size by ~150 GB per backup with little
          # recovery value: pg_basebackup / pg_dump dumps are the right
          # tool for the structured data, the source materials are
          # replayable from their original sources.
          "var/lib/sinex"
        ];
      };

      # 2. User Data (/realm snapshots) - runs as root so the bind mount can be created
      realm = mkBorgJob {
        name = "realm";
        repo = borgRepoRealm;
        snapshotDir = realmSnapshots;
        snapshotGlob = "realm.*";
        bindTarget = borgRealmSnapshotBind;
        # Pin hostname explicitly; the eval-time hostname can resolve to the
        # build sandbox default ("machine") instead of the real hostname.
        archiveBaseName = "sinnix-prime-realm";
        # Every 4h at :20, offset 1h from persist to avoid lock contention
        startAt = [ "*-*-* 03,07,11,15,19,23:20:00" ];
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
          # Polylogue archive (~123 GB) — regenerable from ~/.claude/projects/
          # and ~/.codex/sessions/ via `polylogue run acquire parse materialize`.
          "**/data/captures/polylogue"
          # Syslog exports (~21 GB) — derived from journald, which retains the
          # source on the same disk. Re-exportable if needed.
          "**/data/captures/syslog"
        ];
      };
    };

    # Backups are scheduled bulk I/O. Keep them below interactive work: the
    # post-restore backup and metadata capture saturated /realm enough to make
    # the desktop visibly stall even though the machine was otherwise healthy.
    systemd.services.borgbackup-job-persist = {
      restartIfChanged = false;
      serviceConfig = backgroundBackupServiceConfig // {
        TimeoutStopSec = "15s";
      };
    };
    systemd.services.borgbackup-job-realm = {
      restartIfChanged = false;
      serviceConfig = backgroundBackupServiceConfig // {
        TimeoutStopSec = "15s";
      };
    };

    # Weekly integrity check — verify repo metadata and detect bit rot on the HDD.
    systemd.services.borgbackup-check = {
      description = "Borg backup integrity check";
      restartIfChanged = false;
      serviceConfig = {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      }
      // backgroundBackupServiceConfig;
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

    # Borg is file-level recovery. Keep compact Btrfs metadata images off the
    # source filesystems so a future tree/chunk/extent repair has native
    # metadata evidence instead of only a file archive.
    systemd.services.btrfs-metadata-image-backup = {
      description = "Capture Btrfs metadata images for realm and persist";
      restartIfChanged = false;
      after = [
        "persist.mount"
        "realm.mount"
        "outer\\x2drealm.mount"
      ];
      requires = [
        "persist.mount"
        "realm.mount"
        "outer\\x2drealm.mount"
      ];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      }
      // backgroundBackupServiceConfig;
      path = with pkgs; [
        btrfs-progs
        coreutils
        findutils
      ];
      script = ''
        set -euo pipefail

        stamp="$(date -u +%Y%m%dT%H%M%SZ)"
        install -d -m 0700 -o root -g root "${btrfsImageRoot}"

        capture_image() {
          label="$1"
          device="$2"
          out="${btrfsImageRoot}/$label-$stamp.btrfs-image"
          tmp="$out.tmp"

          rm -f "$tmp"
          btrfs-image -c 9 "$device" "$tmp"
          chmod 0600 "$tmp"
          mv "$tmp" "$out"
        }

        capture_image realm /dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a
        capture_image persist /dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02

        find "${btrfsImageRoot}" -type f -name '*.btrfs-image' -mtime +30 -delete
      '';
    };
    systemd.timers.btrfs-metadata-image-backup = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = false;
        RandomizedDelaySec = "30min";
      };
    };

    system.activationScripts.borgRepositoryDirectories.text = ''
      ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g users ${borgRepoRoot}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPersistPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRealmPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${btrfsImageRoot}
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
      "d ${btrfsImageRoot} 0700 root root -"
      "d /persist/root/.cache/borg 0700 root root -"
    ];

    # systemd services for btrbk
    # Depends on all snapshotted volumes being mounted. neo-outer-realm is an
    # HDD (slow spin-up) with nofail — without this, btrbk races the mount on boot.
    systemd.services.btrbk = {
      description = "btrbk btrfs snapshot";
      restartIfChanged = false;
      after = [
        "persist.mount"
        "realm.mount"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.btrbk}/bin/btrbk run --quiet";
        TimeoutStopSec = "15s";
      }
      // backgroundBackupServiceConfig;
    };

    systemd.timers.btrbk = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* *:00/15:00";
        Persistent = false;
      };
    };

    # Root snapshot archival: the initrd saves pre-wipe / states to
    # .snapshots/root.TIMESTAMP (btrfs subvolumes) on every boot. They
    # accumulate indefinitely because they're invisible to btrbk (which
    # manages .btrfs/snapshot/) and borg (which sees only btrbk snapshots).
    # This job mounts the btrfs root, backs each root snapshot up to the
    # persist borg repo, and deletes the subvolume on success.
    systemd.services.borgbackup-root-snapshots = {
      description = "Archive ephemeral root snapshots to borg";
      restartIfChanged = false;
      after = [
        "persist.mount"
        "borgbackup-job-persist.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      }
      // backgroundBackupServiceConfig;
      environment.BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
      environment.BORG_REPO = borgRepoPersist;
      environment.BORG_CACHE_DIR = "/persist/root/.cache/borg";
      path = with pkgs; [
        btrfs-progs
        borgbackup
        coreutils
        util-linux
      ];
      script = ''
        PERSIST_DEV="/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02"
        TMP_ROOT=$(mktemp -d)
        cleanup() {
          umount "$TMP_ROOT" 2>/dev/null || true
          rm -rf "$TMP_ROOT"
        }
        trap cleanup EXIT

        mount -o subvol=/ "$PERSIST_DEV" "$TMP_ROOT"

        backed_up=0
        for snap_dir in "$TMP_ROOT"/.snapshots/root.*; do
          [ -d "$snap_dir" ] || continue
          snap_name=$(basename "$snap_dir")
          archive_name="root-$snap_name"

          borg create \
            --compression auto,zstd,3 \
            --lock-wait 7200 \
            "::$archive_name" "$snap_dir"

          if [ $? -eq 0 ]; then
            btrfs subvolume delete "$snap_dir"
            backed_up=$((backed_up + 1))
          else
            echo "borg create failed for $snap_name — subvolume kept on disk" >&2
          fi
        done

        if [ $backed_up -gt 0 ]; then
          borg compact --lock-wait 7200
        fi
      '';
    };

    systemd.timers.borgbackup-root-snapshots = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "5min";
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = 300;
      };
    };

    # Weekly random-archive deep-verify drill.
    #
    # The existing `services.borgbackup.jobs.*.doCheck` runs
    # `borg check --repository-only` which validates the chunk graph
    # without re-reading chunk data — fast, but cannot detect chunk-store
    # bit rot. The drill picks one random archive per repo (within the
    # last 30 days, to bound runtime + keep the verification fresh) and
    # runs `borg check --verify-data --first 1 -P <archive>` against it,
    # appending a JSONL record to
    # /realm/data/captures/machine/borg_drill.jsonl so lynchpin can
    # chart pass/fail history. Sentinel will surface failures via its
    # existing systemd-unit health checks.
    systemd.services.sinnix-borg-drill = {
      description = "Borg random-archive deep-verify drill";
      after = [
        "network.target"
      ];
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_CACHE_DIR = "/persist/root/.cache/borg";
      };
      path = with pkgs; [
        borgbackup
        coreutils
        jq
        util-linux
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${scriptPkgs.sinnix-borg-drill}/bin/sinnix-borg-drill";
        # Borg's chunk verification is CPU+IO heavy; keep it from
        # contending with interactive work and the periodic borg create.
        Nice = 10;
        CPUSchedulingPolicy = "idle";
        IOSchedulingClass = "idle";
        IOWeight = 20;
        # `borg check --verify-data` on a multi-GB archive can take
        # tens of minutes on HDDs; allow up to 12 hours total across repos.
        TimeoutStartSec = "12h";
      };
    };

    systemd.timers.sinnix-borg-drill = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        # Weekly, offset from `borgbackup-check.timer` (Sun 06:17) so the
        # two heavy borg jobs do not contend for the HDD.
        OnCalendar = "Wed 04:00:00";
        Persistent = true;
        RandomizedDelaySec = 1800;
      };
    };

  };
}
