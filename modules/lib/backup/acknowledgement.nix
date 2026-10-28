# Internal backup component. Public options and shared policy live in modules/backup.nix.
{
  coordinatorPolicies,
  lib,
  pkgs,
  config,
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
  genomeRoot,
  genomeSnapshots,
}:
let
  # Native units keep their own resource, proof and cancellation contracts.
  # A producer module that is disabled contributes no job to this sequence.
  configured = lib.filter (
    name: builtins.hasAttr name config.systemd.services && config.systemd.services.${name}.enable
  );
  dumpUnits = configured (
    lib.optional config.sinnix.services.machine-telemetry.enable "machine-telemetry-sqlite-backup"
    ++ lib.optional config.sinnix.services.polylogue.enable "polylogue-sqlite-backup"
  );
  archiveUnits = configured (
    # Daily direct-path coverage must not wait behind a multi-day historical
    # snapshot backlog. Native drain queues themselves remain lossless.
    lib.optional config.sinnix.services.polylogue.enable "borgbackup-job-polylogue-state"
    ++ [
      "borgbackup-job-sinex-blobs"
      "borgbackup-job-realm"
      "borgbackup-job-genome"
      "borgbackup-job-persist"
      "borgbackup-root-snapshots"
    ]
  );
  finalUnits = configured [
    "borgbackup-maintenance"
    "borgbackup-coverage-audit-realm"
    "borgbackup-local-dumps"
  ];
  acquisitionPolicy = builtins.hashString "sha256" (
    builtins.toJSON {
      dumps = map (name: config.systemd.services.${name}.script) dumpUnits;
      snapshots = config.environment.etc."btrbk/btrbk.conf".text;
    }
  );
  childUnits = dumpUnits ++ [ "btrbk" ] ++ archiveUnits ++ finalUnits;
  serviceNames = names: lib.escapeShellArgs (map (name: "${name}.service") names);
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

  # The coordinator owns the schedule, not the Borg lock. Waiting for a
  # native child while holding that child's lock would deadlock the sequence.
  (mkBackupJob "borgbackup-drain-coordinator" {
    description = "Run nightly dumps, snapshot archives and backup maintenance in sequence";
    unit.unitConfig.PropagatesStopTo = map (name: "${name}.service") childUnits;
    serviceConfig = {
      # Preserve child budgets, with room for dump/maintenance phases. The
      # coordinator also bounds children whose native start timeout is infinite.
      TimeoutStartSec = if genomeRoot == null then "56h15m" else "80h15m";
      TimeoutStopSec = "15s";
    };
    path = with pkgs; [
      gnused
      systemd
      btrfs-progs
      util-linux
      coreutils
    ];
    script = ''
      daily_fresh() {
        local epoch policy now
        now=$(date +%s)
        [ -f "$1" ] || return 1
        epoch=$(sed -n 's/^epoch=//p' "$1")
        policy=$(sed -n 's/^policy_sha256=//p' "$1")
        case "$epoch" in ""|*[!0-9]*) return 1 ;; esac
        [ "''${#epoch}" -le 10 ] || return 1
        epoch=$((10#$epoch))
        [ "$policy" = "$2" ] && [ "$now" -ge "$epoch" ] && [ $((now - epoch)) -lt 72000 ]
      }
      acquisition_marker=${lib.escapeShellArg "${borgDrainStateRoot}/coordinator.acquisition"}
      acquisition_due=1
      if daily_fresh "$acquisition_marker" ${lib.escapeShellArg acquisitionPolicy}; then
        acquisition_due=0
      fi
      failed=0
      run_step() {
        echo "backup_phase=coordinator unit=$1 status=starting"
        if systemctl start "$1"; then
          echo "backup_phase=coordinator unit=$1 status=finished"
        else
          echo "backup_phase=coordinator unit=$1 status=failed; continuing independent jobs" >&2
          failed=1
          return 1
        fi
      }
      if [ "$acquisition_due" -eq 1 ]; then
        dumps_failed=0
        for unit in ${serviceNames dumpUnits}; do
          if ! run_step "$unit"; then dumps_failed=1; fi
        done
        if [ "$dumps_failed" -eq 0 ]; then
          # Only a completed acquisition makes these dumps eligible for reuse
          # by the boot catch-up after an interrupted archive phase.
          if run_step btrbk.service; then
            install -d -m 0750 -o root -g users ${lib.escapeShellArg borgDrainStateRoot}
            temporary=$(mktemp "$acquisition_marker.XXXXXXXX")
            printf 'epoch=%s\npolicy_sha256=%s\n' "$(date +%s)" ${lib.escapeShellArg acquisitionPolicy} > "$temporary"
            chmod 0644 "$temporary"
            sync -f "$temporary"
            mv -f "$temporary" "$acquisition_marker"
            sync -f ${lib.escapeShellArg borgDrainStateRoot}
          fi
        else
          echo "backup_phase=coordinator unit=btrbk.service status=skipped reason=dump-failure" >&2
        fi
      else
        echo "backup_phase=coordinator acquisition=already-fresh"
      fi
      needs_archival() {
        local queued
        if ! queued="$(${snapshotCoverage} pending-hint -- "$@")"; then
          # Unavailable queue evidence needs the native child's validation.
          echo "Queue unavailable; requesting native drain validation" >&2
          return 0
        fi
        [ "$queued" = yes ]
      }
      if needs_archival ${lib.escapeShellArg realmSnapshots} 'realm.*' \
          ${lib.escapeShellArg "${borgDrainStateRoot}/realm.latest-archived"} || \
        needs_archival ${lib.escapeShellArg persistSnapshots} 'persist.*' \
          ${lib.escapeShellArg "${borgDrainStateRoot}/persist.latest-archived"} ${
            lib.optionalString (genomeRoot != null) ''
              || \
                      needs_archival ${lib.escapeShellArg genomeSnapshots} 'genome.*' \
                        ${lib.escapeShellArg "${borgDrainStateRoot}/genome.latest-archived"}''
          }; then
        systemctl stop borgbackup-verify.service
      fi
      for unit in ${serviceNames (archiveUnits ++ finalUnits)}; do
        daily_marker=""
        daily_policy=""
        case "$unit" in
          borgbackup-job-polylogue-state.service)
            daily_marker=${lib.escapeShellArg "${borgDrainStateRoot}/polylogue-state.last-success"}
            daily_policy=${lib.escapeShellArg coordinatorPolicies.polylogue} ;;
          borgbackup-job-sinex-blobs.service)
            daily_marker=${lib.escapeShellArg "${borgDrainStateRoot}/sinex-blobs.last-success"}
            daily_policy=${lib.escapeShellArg coordinatorPolicies.sinex} ;;
          borgbackup-local-dumps.service)
            daily_marker=${lib.escapeShellArg "${borgDrainStateRoot}/local-dumps.last-success"}
            daily_policy=${lib.escapeShellArg coordinatorPolicies.localDumps} ;;
        esac
        if [ -n "$daily_marker" ] && daily_fresh "$daily_marker" "$daily_policy"; then
          echo "backup_phase=coordinator unit=$unit status=skipped reason=already-fresh"
          continue
        fi
        run_step "$unit" || true
      done
      exit "$failed"
    '';
    timer = {
      # OnBootSec also resumes a night interrupted after the calendar fired.
      # The phase receipts make an additional missed-calendar wake cheap.
      onCalendar = "*-*-* 03:05:00";
      onBootSec = "45min";
      persistent = true;
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

        # Initrd names root cuts in UTC, without btrbk's numeric offset.
        cut="''${snap_name#root.}"
        snapshot_timestamp="$(date --date="''${cut:0:4}-''${cut:4:2}-''${cut:6:2} ''${cut:9:2}:''${cut:11:2}:''${cut:13:2} UTC" --utc +%Y-%m-%dT%H:%M:%S)"
        if with_borg_lock borg create \
          --timestamp "$snapshot_timestamp" \
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
