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
  borgDrainStateRoot = "/persist/root/.cache/borg-drain";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoRootSnapshotsPath = "${borgRepoRoot}/borg-root-snapshots-v1";
  btrfsImageRoot = "${borgRepoRoot}/btrfs-images";
  borgRepoPersist = "file://${borgRepoPersistPath}";
  borgRepoRealm = "file://${borgRepoRealmPath}";
  borgRepoRootSnapshots = "file://${borgRepoRootSnapshotsPath}";
  borgPassphrasePath = config.sinnix.secrets.paths."borg-passphrase";
  outerRealmMountUnit = "outer\\x2drealm.mount";
  borgLockWaitSec = 60;
  backupServiceConfig =
    unit:
    lib.sinnix.mkRuntimeServiceConfig {
      runtimeInventory = config.sinnix.runtime.inventory;
      inherit unit;
    };

  mkBorgExcludeArgs =
    exclude: lib.concatMapStringsSep " " (pattern: "--exclude ${lib.escapeShellArg pattern}") exclude;

  borgRetentionArgs = [
    "--keep-within"
    "7d"
    "--keep-daily"
    "60"
    "--keep-weekly"
    "26"
    "--keep-monthly"
    "24"
    "--keep-yearly"
    "5"
  ];

  mkBorgRetentionArgs = lib.concatMapStringsSep " " lib.escapeShellArg borgRetentionArgs;

  mkSnapshotDrainScript =
    {
      label,
      repo,
      repoPath,
      snapshotDir,
      snapshotGlob,
      bindTarget,
      archivePrefix,
      minIntervalSec,
      exclude,
    }:
    ''
      set -euo pipefail
      shopt -s nullglob

      export BORG_REPO=${lib.escapeShellArg repo}
      export BORG_PASSCOMMAND=${lib.escapeShellArg "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}"}
      export BORG_CACHE_DIR=/persist/root/.cache/borg

      install -d -m 0700 -o root -g root ${lib.escapeShellArg repoPath}
      install -d -m 0700 -o root -g root ${lib.escapeShellArg bindTarget}
      install -d -m 0700 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}

      if [ ! -e ${lib.escapeShellArg "${repoPath}/config"} ]; then
        borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

      stamp=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.stamp"}
      now="$(date +%s)"
      if [ -e "$stamp" ]; then
        last="$(stat -c %Y "$stamp")"
        age=$((now - last))
        if [ "$age" -lt ${toString minIntervalSec} ]; then
          echo "Last ${label} Borg drain was $age seconds ago; keeping snapshots queued for coalescing"
          exit 0
        fi
      fi

      cleanup_snapshot_bind_mount() {
        if mountpoint -q ${lib.escapeShellArg bindTarget}; then
          umount ${lib.escapeShellArg bindTarget}
        fi
      }
      trap cleanup_snapshot_bind_mount EXIT

      snapshot="$(
        find ${lib.escapeShellArg snapshotDir} -maxdepth 1 -mindepth 1 -type d -name ${lib.escapeShellArg snapshotGlob} -printf '%f\n' \
          | sort \
          | tail -n 1
      )"

      if [ -z "$snapshot" ]; then
        exit 0
      fi

      snapshot_path=${lib.escapeShellArg snapshotDir}/"$snapshot"
      archive_name=${lib.escapeShellArg archivePrefix}-"$snapshot"

      if borg info "::$archive_name" >/dev/null 2>&1; then
        echo "Archive $archive_name already exists"
      else

        cleanup_snapshot_bind_mount || true
        mount --bind "$snapshot_path" ${lib.escapeShellArg bindTarget}

        if borg create \
          --compression auto,zstd,1 \
          --lock-wait ${toString borgLockWaitSec} \
          ${mkBorgExcludeArgs exclude} \
          "::$archive_name" ${lib.escapeShellArg "${bindTarget}/./"}; then
          cleanup_snapshot_bind_mount
        else
          echo "borg create failed for ${label} snapshot $snapshot; subvolume kept on disk" >&2
          exit 1
        fi
      fi

      find ${lib.escapeShellArg snapshotDir} -maxdepth 1 -mindepth 1 -type d -name ${lib.escapeShellArg snapshotGlob} -printf '%f\n' \
        | sort \
        | while IFS= read -r queued_snapshot; do
          if [[ "$queued_snapshot" > "$snapshot" ]]; then
            continue
          fi
          echo "Deleting ${label} snapshot $queued_snapshot covered by $archive_name"
          btrfs subvolume delete ${lib.escapeShellArg snapshotDir}/"$queued_snapshot"
        done

      # Retention pruning and compaction are deliberately batched in
      # borgbackup-maintenance.service. Running compaction on every path wake
      # would turn "continuous" backups into repeated HDD churn.
      touch "$stamp"
    '';

  persistExcludes = [
    # Archive-relative patterns: paths start from the /persist snapshot root.
    "home/sinity/.local/share/Steam"
    "home/sinity/.cache/huggingface"
    "home/sinity/.cache/spotify"
    "root/.cache/borg"
    "home/sinity/.config/chrome-ws/Default/Service Worker"
    "home/sinity/.config/chrome-ws/Default/GPUCache"
    "home/sinity/.config/chrome-ws/*Cache*"
    "home/sinity/.config/chrome-ws/*cache*"
    # User caches are regenerable and currently large enough to dominate
    # backup churn if included.
    "home/sinity/.cache"
    "var/lib/systemd/coredump"
    # Sinex runtime state is backed up through structured service tooling.
    "var/lib/sinex"
  ];

  realmExcludes = [
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
    # Regenerable local capture products.
    "**/data/captures/polylogue"
    "**/data/captures/syslog"
    "**/data/captures/machine/below"
  ];

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

    # ─── Snapshot handoff queue ───
    # btrbk creates point-in-time local snapshots; Borg is responsible for
    # durable retention. The systemd btrbk service runs with
    # --preserve-snapshots, so snapshots are deleted only by Borg drain jobs
    # after the matching archive exists.

    volume ${realmRoot}
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   all

    volume /persist
      snapshot_dir   .btrfs/snapshot
      subvolume .
        snapshot_preserve_min   all

    # / is ephemeral (wiped and recreated each boot by initrd rollback script).
    # Pre-wipe states are saved to .snapshots/root.TIMESTAMP and archived by
    # a separate borg job (borgbackup-root-snapshots) that picks them up,
    # backs them up, and deletes the subvolume.

  '';

in
{
  config = {
    sinnix.runtime.surfaces = {
      btrbk = {
        unit = "btrbk.service";
        resourceClass = "backup-maintenance";
      };
      btrbk-timer = {
        unit = "btrbk.timer";
        kind = "timer";
        resourceClass = "backup-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
      };
      borgbackup-job-persist = {
        unit = "borgbackup-job-persist.service";
        resourceClass = "backup-maintenance";
      };
      borgbackup-job-realm = {
        unit = "borgbackup-job-realm.service";
        resourceClass = "backup-maintenance";
      };
      borgbackup-check = {
        unit = "borgbackup-check.service";
        resourceClass = "backup-maintenance";
      };
      borgbackup-maintenance = {
        unit = "borgbackup-maintenance.service";
        resourceClass = "backup-maintenance";
      };
      btrfs-metadata-image-backup = {
        unit = "btrfs-metadata-image-backup.service";
        resourceClass = "backup-maintenance";
      };
      borgbackup-root-snapshots = {
        unit = "borgbackup-root-snapshots.service";
        resourceClass = "backup-maintenance";
      };
      sinnix-borg-drill = {
        unit = "sinnix-borg-drill.service";
        resourceClass = "backup-maintenance";
        captures = [
          {
            name = "borg-drill";
            path = "${config.sinnix.paths.capturesRoot}/machine/borg_drill.jsonl";
            eventDriven = true;
          }
        ];
      };
    };

    environment.systemPackages = [
      pkgs.btrbk
      pkgs.borgbackup
    ];

    # btrbk configuration
    environment.etc."btrbk/btrbk.conf".text = btrbkConfig;

    # ─── Borg Snapshot Drainers ───
    #
    # btrbk is the producer. Borg is the durability gate. Local snapshots are
    # never deleted by btrbk rotation; a snapshot leaves disk only after this
    # drain has either found or created the matching Borg archive.

    # Backups are scheduled bulk I/O. Keep them below interactive work: the
    # post-restore backup and metadata capture saturated /realm enough to make
    # the desktop visibly stall even though the machine was otherwise healthy.
    systemd.services.borgbackup-job-persist = {
      description = "Drain /persist btrbk snapshots into Borg";
      restartIfChanged = false;
      after = [
        "persist.mount"
        outerRealmMountUnit
      ];
      requires = [
        "persist.mount"
        outerRealmMountUnit
      ];
      serviceConfig = (backupServiceConfig "borgbackup-job-persist.service") // {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      };
      path = with pkgs; [
        borgbackup
        btrfs-progs
        coreutils
        findutils
        util-linux
      ];
      script = mkSnapshotDrainScript {
        label = "persist";
        repo = borgRepoPersist;
        repoPath = borgRepoPersistPath;
        snapshotDir = persistSnapshots;
        snapshotGlob = "persist.*";
        bindTarget = borgPersistSnapshotBind;
        archivePrefix = "persist";
        minIntervalSec = 3600;
        exclude = persistExcludes;
      };
    };
    systemd.services.borgbackup-job-realm = {
      description = "Drain /realm btrbk snapshots into Borg";
      restartIfChanged = false;
      after = [
        "realm.mount"
        outerRealmMountUnit
      ];
      requires = [
        "realm.mount"
        outerRealmMountUnit
      ];
      serviceConfig = (backupServiceConfig "borgbackup-job-realm.service") // {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      };
      path = with pkgs; [
        borgbackup
        btrfs-progs
        coreutils
        findutils
        util-linux
      ];
      script = mkSnapshotDrainScript {
        label = "realm";
        repo = borgRepoRealm;
        repoPath = borgRepoRealmPath;
        snapshotDir = realmSnapshots;
        snapshotGlob = "realm.*";
        bindTarget = borgRealmSnapshotBind;
        archivePrefix = "realm";
        minIntervalSec = 3600;
        exclude = realmExcludes;
      };
    };

    systemd.paths.borgbackup-job-persist = {
      wantedBy = [ "multi-user.target" ];
      pathConfig = {
        PathChanged = persistSnapshots;
        Unit = "borgbackup-job-persist.service";
      };
    };
    systemd.paths.borgbackup-job-realm = {
      wantedBy = [ "multi-user.target" ];
      pathConfig = {
        PathChanged = realmSnapshots;
        Unit = "borgbackup-job-realm.service";
      };
    };

    systemd.timers.borgbackup-job-persist = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* *:20:00";
        Persistent = false;
      };
    };
    systemd.timers.borgbackup-job-realm = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* *:35:00";
        Persistent = false;
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
      // backupServiceConfig "borgbackup-check.service";
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

    systemd.services.borgbackup-maintenance = {
      description = "Prune and compact Borg backup repositories";
      restartIfChanged = false;
      after = [
        outerRealmMountUnit
      ];
      requires = [
        outerRealmMountUnit
      ];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      }
      // backupServiceConfig "borgbackup-maintenance.service";
      environment.BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
      environment.BORG_CACHE_DIR = "/persist/root/.cache/borg";
      path = with pkgs; [
        borgbackup
        coreutils
      ];
      script = ''
        set -euo pipefail

        maintain_repo() {
          repo="$1"
          if [ ! -e "''${repo#file://}/config" ]; then
            echo "Skipping uninitialized repo $repo"
            return
          fi

          borg prune --lock-wait ${toString borgLockWaitSec} ${mkBorgRetentionArgs} "$repo"
          borg compact --lock-wait ${toString borgLockWaitSec} "$repo"
        }

        maintain_repo ${lib.escapeShellArg borgRepoPersist}
        maintain_repo ${lib.escapeShellArg borgRepoRealm}
        maintain_repo ${lib.escapeShellArg borgRepoRootSnapshots}
      '';
    };
    systemd.timers.borgbackup-maintenance = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* 04:50:00";
        Persistent = false;
        RandomizedDelaySec = "45min";
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
        outerRealmMountUnit
      ];
      requires = [
        "persist.mount"
        "realm.mount"
        outerRealmMountUnit
      ];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      }
      // backupServiceConfig "btrfs-metadata-image-backup.service";
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
        OnCalendar = "Sun 00:12:00";
        Persistent = false;
        RandomizedDelaySec = "2h";
      };
    };

    system.activationScripts.borgRepositoryDirectories.text = ''
      ${pkgs.coreutils}/bin/install -d -m 0750 -o root -g users ${borgRepoRoot}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoPersistPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRealmPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoRootSnapshotsPath}
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
      "d ${borgRepoRootSnapshotsPath} 0700 root root -"
      "d ${btrfsImageRoot} 0700 root root -"
      "d /persist/root/.cache/borg 0700 root root -"
      "d ${borgDrainStateRoot} 0700 root root -"
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
        ExecStart = "${pkgs.btrbk}/bin/btrbk --quiet --preserve-snapshots run";
        TimeoutStopSec = "15s";
      }
      // backupServiceConfig "btrbk.service";
    };

    systemd.timers.btrbk = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* *:00/15:00";
        Persistent = false;
      };
    };

    # Root snapshot archival: the initrd saves pre-wipe / states to
    # .snapshots/root.TIMESTAMP (btrfs subvolumes) on every boot. Archive them
    # to a dedicated borg repo so slow root-drain work never blocks the normal
    # /persist backup lock, then delete only after the archive exists.
    systemd.services.borgbackup-root-snapshots = {
      description = "Archive ephemeral root snapshots to borg";
      restartIfChanged = false;
      after = [
        "persist.mount"
        outerRealmMountUnit
      ];
      requires = [ outerRealmMountUnit ];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      }
      // backupServiceConfig "borgbackup-root-snapshots.service";
      environment.BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
      environment.BORG_REPO = borgRepoRootSnapshots;
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

        if [ ! -e "${borgRepoRootSnapshotsPath}/config" ]; then
          install -d -m 0700 -o root -g root "${borgRepoRootSnapshotsPath}"
          borg init --encryption repokey-blake2 "$BORG_REPO"
        fi

        delete_archived_snapshot() {
          snap_dir="$1"
          if btrfs subvolume show "$snap_dir" >/dev/null 2>&1; then
            btrfs subvolume delete "$snap_dir"
          else
            rm -rf --one-file-system "$snap_dir"
          fi
        }

        backed_up=0
        for snap_dir in "$TMP_ROOT"/.snapshots/root.*; do
          [ -d "$snap_dir" ] || continue
          snap_name=$(basename "$snap_dir")
          archive_name="root-$snap_name"

          if borg info "::$archive_name" >/dev/null 2>&1; then
            echo "Archive $archive_name already exists; deleting archived snapshot $snap_name"
            delete_archived_snapshot "$snap_dir"
            backed_up=$((backed_up + 1))
            continue
          fi

          if borg create \
            --compression auto,zstd,1 \
            --lock-wait ${toString borgLockWaitSec} \
            --exclude "$snap_dir/dev" \
            --exclude "$snap_dir/home/*/.cache" \
            --exclude "$snap_dir/mnt" \
            --exclude "$snap_dir/neo-outer-realm" \
            --exclude "$snap_dir/nix" \
            --exclude "$snap_dir/outer-realm" \
            --exclude "$snap_dir/persist" \
            --exclude "$snap_dir/proc" \
            --exclude "$snap_dir/realm" \
            --exclude "$snap_dir/root/.cache" \
            --exclude "$snap_dir/run" \
            --exclude "$snap_dir/swap" \
            --exclude "$snap_dir/sys" \
            --exclude "$snap_dir/tmp" \
            --exclude "$snap_dir/var/cache" \
            "::$archive_name" "$snap_dir"; then
            delete_archived_snapshot "$snap_dir"
            backed_up=$((backed_up + 1))
          else
            echo "borg create failed for $snap_name; subvolume kept on disk" >&2
          fi
        done

        # Retention pruning and compaction are batched by
        # borgbackup-maintenance.service.
      '';
    };

    systemd.timers.borgbackup-root-snapshots = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "45min";
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = 1800;
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
    # /realm/data/captures/machine/borg_drill.jsonl so lynchpin and
    # operator reports can chart pass/fail history from the canonical capture.
    systemd.services.sinnix-borg-drill = {
      description = "Borg random-archive deep-verify drill";
      # Detach from nixos-rebuild switch: this is a multi-hour oneshot;
      # switch-to-configuration must not block waiting for it to finish
      # when the unit hash changes or the Persistent=true timer wants to
      # catch up. The timer schedules invocations on its own cadence.
      restartIfChanged = false;
      reloadIfChanged = false;
      stopIfChanged = false;
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
        # `borg check --verify-data` on a multi-GB archive can take
        # tens of minutes on HDDs; allow up to 12 hours total across repos.
        TimeoutStartSec = "12h";
      }
      // backupServiceConfig "sinnix-borg-drill.service";
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
