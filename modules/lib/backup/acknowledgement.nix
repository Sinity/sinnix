# Internal backup component. Public options and shared policy live in modules/backup.nix.
{ context }:
with context;
[
  # ─── Borg Snapshot Drainers ───
  #
  # btrbk is the producer. Borg is the durability gate. Local snapshots are
  # never deleted by btrbk rotation; a snapshot leaves disk only after this
  # drain has either found or created the matching Borg archive.
  #
  # Backups are scheduled bulk I/O and must stay below interactive work;
  # unthrottled they saturate /realm enough to visibly stall the desktop.
  #
  # The drain timers are RETRY granularity, not work cadence: how often a
  # drain actually copies anything is set by borgDrainMinIntervalSec (4h),
  # and a wake inside that window exits after one stat without touching the
  # Borg lock. What the timer period buys is recovery margin. A drain that
  # loses the global lock race skips outright and waits for its next wake,
  # while the health budget (borgArchiveMaxAgeSec / borgSnapshotQueueMaxAgeSec,
  # 6h) starts counting from the last SUCCESS -- so the 4h floor leaves only
  # ~2h of slack. At the old hourly period two consecutive lock races spent
  # most of it and a third breached the budget; at 20 minutes, six retries
  # fit in the same slack. Both stay off btrbk's :00/:30 wakes and off each
  # other so the two drains never race for the lock they now rarely take.
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
    serviceConfig.TimeoutStopSec = "15s";
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
      repo = borgRepoPersist;
      repoPath = borgRepoPersistPath;
      snapshotDir = persistSnapshots;
      snapshotGlob = "persist.*";
      bindTarget = borgPersistSnapshotBind;
      archivePrefix = "persist";
      minIntervalSec = borgDrainMinIntervalSec;
      exclude = persistExcludes;
    };
    timer = {
      onCalendar = "*-*-* *:05,25,45:00";
      persistent = false;
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
    serviceConfig.TimeoutStopSec = "15s";
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
      repo = borgRepoRealm;
      repoPath = borgRepoRealmPath;
      snapshotDir = realmSnapshots;
      snapshotGlob = "realm.*";
      bindTarget = borgRealmSnapshotBind;
      archivePrefix = "realm";
      minIntervalSec = borgDrainMinIntervalSec;
      exclude = realmExcludes;
    };
    timer = {
      onCalendar = "*-*-* *:15,35,55:00";
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
    serviceConfig.TimeoutStopSec = "15s";
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
      ${mkBorgCommonScript borgRepoRootSnapshots}
      acquire_borg_global_lock_or_skip "root snapshot Borg drain"
      recover_stale_borg_locks

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
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
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

        if with_borg_lock borg list --short --glob-archives "$archive_name" "$BORG_REPO" | grep -Fxq "$archive_name"; then
          echo "Archive $archive_name already exists; deleting archived snapshot $snap_name"
          delete_archived_snapshot "$snap_dir"
          backed_up=$((backed_up + 1))
          continue
        fi

        if with_borg_lock borg create \
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

      # Compaction is batched by borgbackup-maintenance.service.
    '';
  })

]
