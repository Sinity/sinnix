# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  pkgs,
  realmSnapshots,
  persistSnapshots,
  borgPersistSnapshotBind,
  borgRealmSnapshotBind,
  borgRepoPersistPath,
  borgRepoRealmPath,
  borgRepoRootSnapshotsPath,
  borgRepoPersist,
  borgRepoRealm,
  borgRepoRootSnapshots,
  borgPassphrasePath,
  outerRealmMountUnit,
  borgLockWaitSec,
  borgCacheDir,
  mkBackupJob,
  mkBorgCommonScript,
  mkSnapshotDrainScript,
  snapshotCoverage,
  persistExcludes,
  realmExcludes,
  persistNoncanonical,
  realmNoncanonical,
}:
[
  # ─── Borg Snapshot Drainers ───
  #
  # btrbk is the producer. Borg is the durability gate. Local snapshots are
  # never deleted by btrbk rotation; a snapshot leaves disk only after this
  # drain has verified its canonical contents in a UUID-bound Borg archive.
  #
  # Backups are scheduled bulk I/O and must stay below interactive work;
  # unthrottled they saturate /realm enough to visibly stall the desktop.
  #
  # Fresh drains run when a newer acquisition exists. Historical debt has a
  # separate daily window and one attempted transaction per volume per day.
  (mkBackupJob "borgbackup-job-persist" {
    description = "Drain /persist btrbk snapshots into Borg";
    unit = {
      after = [
        "persist.mount"
        outerRealmMountUnit
      ];
      requires = [
        "persist.mount"
        outerRealmMountUnit
      ];
    };
    serviceConfig = {
      # One wake processes at most one snapshot, then yields the shared lock.
      # A timeout leaves the current snapshot and remaining queue intact.
      TimeoutStartSec = "4h";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [
      borgbackup
      btrfs-progs
      coreutils
      findutils
      gnugrep
      util-linux
    ];
    script = mkSnapshotDrainScript {
      label = "persist";
      mode = "fresh";
      repo = borgRepoPersist;
      repoPath = borgRepoPersistPath;
      snapshotDir = persistSnapshots;
      snapshotGlob = "persist.*";
      bindTarget = borgPersistSnapshotBind;
      archivePrefix = "persist";
      replacementSuffix = "-coverage-v2";
      exclude = persistExcludes;
      noncanonical = persistNoncanonical;
    };
  })

  (mkBackupJob "borgbackup-job-realm" {
    description = "Drain /realm btrbk snapshots into Borg";
    unit = {
      after = [
        "realm.mount"
        outerRealmMountUnit
      ];
      requires = [
        "realm.mount"
        outerRealmMountUnit
      ];
    };
    serviceConfig = {
      # One wake processes at most one snapshot, then yields the shared lock.
      # A timeout leaves the current snapshot and remaining queue intact.
      TimeoutStartSec = "4h";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [
      borgbackup
      btrfs-progs
      coreutils
      findutils
      gnugrep
      util-linux
    ];
    script = mkSnapshotDrainScript {
      label = "realm";
      mode = "fresh";
      repo = borgRepoRealm;
      repoPath = borgRepoRealmPath;
      snapshotDir = realmSnapshots;
      snapshotGlob = "realm.*";
      bindTarget = borgRealmSnapshotBind;
      archivePrefix = "realm";
      replacementSuffix = "-coverage-v3";
      # A tag in an unknown realm subtree cannot waive canonical content.
      # The verifier only permits the exact noncanonical roots below.
      excludeByMarker = false;
      exclude = realmExcludes;
      noncanonical = realmNoncanonical;
    };
  })

  (mkBackupJob "borgbackup-debt-persist" {
    description = "Archive one historical /persist snapshot";
    unit = {
      after = [ "persist.mount" outerRealmMountUnit ];
      requires = [ "persist.mount" outerRealmMountUnit ];
    };
    serviceConfig = {
      TimeoutStartSec = "2h";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [ borgbackup btrfs-progs coreutils findutils gnugrep util-linux ];
    script = mkSnapshotDrainScript {
      label = "persist";
      mode = "debt";
      repo = borgRepoPersist;
      repoPath = borgRepoPersistPath;
      snapshotDir = persistSnapshots;
      snapshotGlob = "persist.*";
      bindTarget = borgPersistSnapshotBind;
      archivePrefix = "persist";
      replacementSuffix = "-coverage-v2";
      exclude = persistExcludes;
      noncanonical = persistNoncanonical;
    };
  })

  (mkBackupJob "borgbackup-debt-realm" {
    description = "Archive one historical /realm snapshot";
    unit = {
      after = [ "realm.mount" outerRealmMountUnit ];
      requires = [ "realm.mount" outerRealmMountUnit ];
    };
    serviceConfig = {
      TimeoutStartSec = "2h";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [ borgbackup btrfs-progs coreutils findutils gnugrep util-linux ];
    script = mkSnapshotDrainScript {
      label = "realm";
      mode = "debt";
      repo = borgRepoRealm;
      repoPath = borgRepoRealmPath;
      snapshotDir = realmSnapshots;
      snapshotGlob = "realm.*";
      bindTarget = borgRealmSnapshotBind;
      archivePrefix = "realm";
      replacementSuffix = "-coverage-v3";
      excludeByMarker = false;
      exclude = realmExcludes;
      noncanonical = realmNoncanonical;
    };
  })

  # One timer gives both fresh lanes an attempt in each cycle. systemctl start waits
  # for each oneshot's result; a persist failure must still start realm.
  # This unit never takes the Borg lock. The children own the archive gate.
  (mkBackupJob "borgbackup-drain-coordinator" {
    description = "Run persist and realm snapshot drains in sequence";
    unit.unitConfig.PropagatesStopTo = [
      "borgbackup-job-persist.service"
      "borgbackup-job-realm.service"
    ];
    serviceConfig = {
      TimeoutStartSec = "8h15m";
      TimeoutStopSec = "15s";
    };
    path = [ pkgs.systemd ];
    script = ''
      failed=0
      if ! systemctl start borgbackup-job-persist.service; then
        echo "Persist snapshot drain failed; continuing to realm" >&2
        failed=1
      fi
      if ! systemctl start borgbackup-job-realm.service; then
        echo "Realm snapshot drain failed" >&2
        failed=1
      fi
      exit "$failed"
    '';
    timer = {
      onCalendar = "*-*-* *:05,25,45:00";
      persistent = false;
    };
  })

  # The separate timer can be stopped during a final rebuild without stopping
  # fresh archival. A run ends before the next 06:00 acquisition even if both
  # child units hit their two-hour deadlines.
  (mkBackupJob "borgbackup-debt-coordinator" {
    description = "Run one daily historical snapshot transaction per volume";
    unit.unitConfig.PropagatesStopTo = [
      "borgbackup-debt-persist.service"
      "borgbackup-debt-realm.service"
    ];
    serviceConfig = {
      TimeoutStartSec = "4h15m";
      TimeoutStopSec = "15s";
    };
    path = [ pkgs.systemd ];
    script = ''
      failed=0
      if ! systemctl start borgbackup-debt-persist.service; then
        echo "Persist historical snapshot drain failed; continuing to realm" >&2
        failed=1
      fi
      if ! systemctl start borgbackup-debt-realm.service; then
        echo "Realm historical snapshot drain failed" >&2
        failed=1
      fi
      exit "$failed"
    '';
    timer = {
      onCalendar = "*-*-* 01:05:00";
      persistent = false;
    };
  })

  # Root snapshot archival: the initrd saves pre-wipe / states to
  # .snapshots/root.TIMESTAMP (btrfs subvolumes) on every boot. Archive them
  # to a dedicated borg repo so slow root-drain work never blocks the normal
  # /persist backup lock, then delete only after the archive exists.
  (mkBackupJob "borgbackup-root-snapshots" {
    description = "Archive ephemeral root snapshots to borg";
    unit = {
      after = [
        "persist.mount"
        outerRealmMountUnit
      ];
      requires = [ outerRealmMountUnit ];
    };
    serviceConfig = {
      TimeoutStartSec = "4h";
      TimeoutStopSec = "15s";
    };
    environment = {
      BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
      BORG_REPO = borgRepoRootSnapshots;
      BORG_CACHE_DIR = borgCacheDir;
    };
    timer = {
      onBootSec = "45min";
      onCalendar = "daily";
      persistent = true;
      randomizedDelaySec = 1800;
    };
    path = with pkgs; [
      btrfs-progs
      borgbackup
      coreutils
      findutils
      gnugrep
      util-linux
    ];
    script = ''
      set -euo pipefail
      shopt -s nullglob
      ${mkBorgCommonScript borgRepoRootSnapshots}
      acquire_borg_global_lock_or_skip "root snapshot Borg drain"
      recover_stale_borg_locks

      PERSIST_DEV="/dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02"
      TMP_ROOT=$(mktemp -d)
      cleanup() {
        if mountpoint -q "$TMP_ROOT"; then
          umount "$TMP_ROOT" || return
        fi
        rmdir "$TMP_ROOT"
      }
      trap cleanup EXIT

      mount -o subvol=/ "$PERSIST_DEV" "$TMP_ROOT"

      if [ ! -e "${borgRepoRootSnapshotsPath}/config" ]; then
        install -d -m 0700 -o root -g root "${borgRepoRootSnapshotsPath}"
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

      delete_archived_snapshot() {
        # Root snapshots use the same exact-coverage gate. Legacy archives
        # without UUID bindings, writable snapshots and ordinary directories
        # remain on disk; no fallback recursive deletion is safe here.
        ${snapshotCoverage} verify "$snap_dir" "$archive_name" "$snapshot_uuid" \
          ${
            pkgs.writeText "root-snapshot-coverage.json" (
              builtins.toJSON [
                "dev"
                "mnt"
                "neo-outer-realm"
                "nix"
                "outer-realm"
                "persist"
                "proc"
                "realm"
                "root/.cache"
                "run"
                "swap"
                "sys"
                "tmp"
                "var/cache"
              ]
            )
          } || return 1
        [ "$(${snapshotCoverage} identity "$snap_dir")" = "$snapshot_uuid" ] || return 1
        btrfs subvolume delete "$snap_dir"
      }

      backed_up=0
      failed=0
      for snap_dir in "$TMP_ROOT"/.snapshots/root.*; do
        [ -d "$snap_dir" ] || continue
        snap_name=$(basename "$snap_dir")
        archive_name="root-$snap_name"
        if ! snapshot_uuid="$(${snapshotCoverage} identity "$snap_dir")"; then
          failed=1
          continue
        fi

        if with_borg_lock borg list --short --glob-archives "$archive_name" "$BORG_REPO" | grep -Fxq "$archive_name"; then
          echo "Archive $archive_name already exists; verifying snapshot $snap_name"
          if delete_archived_snapshot; then
            backed_up=$((backed_up + 1))
          else
            failed=1
          fi
          continue
        fi

        if with_borg_lock borg create \
          --compression auto,zstd,1 \
          --comment "sinnix-snapshot-v1:$snapshot_uuid" \
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
          "::$archive_name" "$snap_dir/./"; then
          if delete_archived_snapshot; then
            backed_up=$((backed_up + 1))
          else
            failed=1
          fi
        else
          echo "borg create failed for $snap_name; subvolume kept on disk" >&2
          failed=1
        fi
      done

      # Compaction is batched by borgbackup-maintenance.service.
      exit "$failed"
    '';
  })

]
