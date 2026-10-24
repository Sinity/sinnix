# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  lib,
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
  borgDrainStateRoot,
  mkBackupJob,
  mkBorgCommonScript,
  mkSnapshotDrainScript,
  snapshotCoverage,
  persistExcludes,
  realmExcludes,
  persistNoncanonical,
  realmNoncanonical,
  username,
}:
let
  # Root snapshot paths left out of the archive. One list feeds both the
  # `borg create` excludes and the coverage check, so an excluded root can
  # never be reported as missing canonical content: when `home/*/.cache` was
  # excluded but absent from the check, every snapshot since 2026-09-13 was
  # retained and the job failed nightly.
  rootSnapshotExcludes = [
    "dev"
    "home/${username}/.cache"
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
  ];
in
[
  # ─── Borg Snapshot Drainers ───
  #
  # btrbk is the producer. Borg is the durability gate. Local snapshots are
  # never deleted by btrbk rotation. Each released snapshot needs its own
  # accepted archive; the newest acknowledged local source stays for audits.
  #
  # Backups are scheduled bulk I/O and must stay below interactive work;
  # unthrottled they saturate /realm enough to visibly stall the desktop.
  #
  # Each wake captures a finite queue, newest first, then historical states.
  # A snapshot leaves disk only under its own durable acknowledgement.
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
      # A timeout preserves unacknowledged history; later wakes reuse durable
      # per-snapshot proofs and finish the remaining finite queue.
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
      # A multi-terabyte backfill runs under idle I/O and bandwidth caps.
      # Each snapshot in the admitted queue requires its own accepted proof.
      TimeoutStartSec = "24h";
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
      repo = borgRepoRealm;
      repoPath = borgRepoRealmPath;
      snapshotDir = realmSnapshots;
      snapshotGlob = "realm.*";
      bindTarget = borgRealmSnapshotBind;
      archivePrefix = "realm";
      replacementSuffix = "-coverage-v3";
      # A tag in an unknown realm subtree cannot waive canonical content.
      # The verifier only permits the exact noncanonical roots below.
      exclude = realmExcludes;
      noncanonical = realmNoncanonical;
    };
  })

  # One timer gives both fresh lanes an attempt in each cycle. Archive /realm
  # first so a long /persist full verification cannot delay its space-critical
  # snapshot drain. A realm failure must still start persist.
  # This unit never takes the Borg lock. The children own the archive gate.
  (mkBackupJob "borgbackup-drain-coordinator" {
    description = "Run realm and persist snapshot drains in sequence";
    unit.unitConfig.PropagatesStopTo = [
      "borgbackup-job-persist.service"
      "borgbackup-job-realm.service"
    ];
    serviceConfig = {
      # Cover the Realm and persist budgets plus coordination overhead.
      TimeoutStartSec = "28h15m";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [
      systemd
      btrfs-progs
      util-linux
      coreutils
    ];
    script = ''
      # The timer owns retry cadence; explicit native drains can run anytime.
      # Partial repository checks can resume at a later window. Independent
      # full comparisons retain their lock and snapshot until they finish;
      # lock-busy drains keep snapshots queued without acknowledging them.
      needs_archival() {
        local queued
        if ! queued="$(${snapshotCoverage} queue -- "$@")"; then
          # Unavailable queue evidence needs the native child's validation.
          echo "Queue unavailable; requesting native drain validation" >&2
          return 0
        fi
        [ -n "$queued" ]
      }
      if needs_archival ${lib.escapeShellArg realmSnapshots} 'realm.*' \
          ${lib.escapeShellArg "${borgDrainStateRoot}/realm.latest-archived"} realm '-coverage-v3' || \
        needs_archival ${lib.escapeShellArg persistSnapshots} 'persist.*' \
          ${lib.escapeShellArg "${borgDrainStateRoot}/persist.latest-archived"} persist '-coverage-v2'; then
        systemctl stop borgbackup-verify.service
      fi
      failed=0
      if ! systemctl start borgbackup-job-realm.service; then
        echo "Realm snapshot drain failed; continuing to persist" >&2
        failed=1
      fi
      if ! systemctl start borgbackup-job-persist.service; then
        echo "Persist snapshot drain failed" >&2
        failed=1
      fi
      exit "$failed"
    '';
    timer = {
      onCalendar = "*-*-* *:05,25:00";
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
          ${pkgs.writeText "root-snapshot-coverage.json" (builtins.toJSON rootSnapshotExcludes)} || return 1
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
          ${lib.concatMapStringsSep " " (path: "--exclude \"$snap_dir/${path}\"") rootSnapshotExcludes} \
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
