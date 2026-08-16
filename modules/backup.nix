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
  options,
  helpers,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot;
  # Sinex publishes this path into every generated runtime/maintenance unit as
  # SINEX_CONTENT_STORE_PATH. Borg must consume the same evaluated topology,
  # rather than reconstructing a backing-subvolume path that can drift after a
  # storage move.
  sinexBlobRepositoryPath = lib.optionalString (
    options.services ? sinex
  ) config.services.sinex.storage.blob.repositoryPath;
  borgRepoRoot = "${config.sinnix.paths.outerRealm}/backup";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  # Snapshot directories
  realmSnapshots = "${realmRoot}/.btrfs/snapshot";
  persistSnapshots = "/persist/.btrfs/snapshot";
  borgSnapshotBindRoot = "/run/borgbackup-snapshot-inputs";
  borgPersistSnapshotBind = "${borgSnapshotBindRoot}/persist";
  borgRealmSnapshotBind = "${borgSnapshotBindRoot}/realm";
  borgDrainStateRoot = "/persist/root/.cache/borg-drain";
  borgIntegrityReceipt = "${borgDrainStateRoot}/integrity-check.json";
  borgIntegrityTransitionState = "${borgDrainStateRoot}/integrity-status-state.json";

  # Borg Configuration
  borgRepoPersistPath = "${borgRepoRoot}/borg-persist-v1";
  borgRepoRealmPath = "${borgRepoRoot}/borg-realm-v2";
  borgRepoRootSnapshotsPath = "${borgRepoRoot}/borg-root-snapshots-v1";
  borgRepoSinexBlobsPath = "${borgRepoRoot}/borg-sinex-blobs-v1";
  btrfsImageRoot = "${borgRepoRoot}/btrfs-images";
  borgRepoPersist = "file://${borgRepoPersistPath}";
  borgRepoRealm = "file://${borgRepoRealmPath}";
  borgRepoRootSnapshots = "file://${borgRepoRootSnapshotsPath}";
  borgRepoSinexBlobs = "file://${borgRepoSinexBlobsPath}";
  borgPassphrasePath = config.sinnix.secrets.paths."borg-passphrase";
  outerRealmMountUnit = "outer\\x2drealm.mount";
  borgLockWaitSec = 60;
  borgCacheDir = "/persist/root/.cache/borg";
  borgStaleLockMinutes = 120;
  borgGlobalLock = "/run/lock/sinnix-borg.lock";
  borgStatusLog = "${config.sinnix.paths.capturesRoot}/machine/borg_status.jsonl";
  sinexProjectPath = "${realmRoot}/project/sinex";
  sinexBeadsDoltArchivePath = "project/sinex/.beads/dolt";
  sinexBeadsIssuesArchivePath = "project/sinex/.beads/issues.jsonl";
  sinexBeadsDrillLog = "${config.sinnix.paths.capturesRoot}/machine/borg_beads_drill.jsonl";
  sinexBeadsArchivePaths = [
    sinexBeadsDoltArchivePath
    sinexBeadsIssuesArchivePath
  ];
  borgArchiveMaxAgeSec = 6 * 60 * 60;
  borgSnapshotQueueMaxAgeSec = 6 * 60 * 60;
  borgDrainMinIntervalSec = 4 * 60 * 60;
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

  mkBorgCommonScript = repo: repoPath: ''
    export BORG_REPO=${lib.escapeShellArg repo}
    export BORG_PASSCOMMAND=${lib.escapeShellArg "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}"}
    export BORG_CACHE_DIR=${lib.escapeShellArg borgCacheDir}

    with_borg_lock() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        "$@"
      else
        flock ${lib.escapeShellArg borgGlobalLock} "$@"
      fi
    }

    acquire_borg_global_lock_or_skip() {
      if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
        return
      fi
      reason="$1"
      exec 9>${lib.escapeShellArg borgGlobalLock}
      if ! flock -n 9; then
        echo "Another Borg operation is active; skipping $reason and keeping work queued"
        exit 0
      fi
      export SINNIX_BORG_GLOBAL_LOCK_HELD=1
    }

    recover_stale_borg_locks() {
      if [ ! -e ${lib.escapeShellArg "${repoPath}/config"} ]; then
        return
      fi

      stale_lock="$(
        find ${lib.escapeShellArg repoPath} \
          -maxdepth 2 -type d -name lock.exclusive \
          -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null || true
      )"
      if [ -z "$stale_lock" ]; then
        if ! find ${lib.escapeShellArg borgCacheDir} \
          -maxdepth 2 -type d -name lock.exclusive \
          -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null | grep -q .; then
          return
        fi
        stale_lock="stale Borg cache lock"
      fi

      if pgrep -x borg >/dev/null 2>&1; then
        echo "Stale-looking Borg lock remains for ${repo}, but a Borg process is alive; refusing break-lock" >&2
        return
      fi

      echo "Breaking stale Borg lock for ${repo}: $stale_lock" >&2
      with_borg_lock borg break-lock ${lib.escapeShellArg repo}
    }
  '';

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

      ${mkBorgCommonScript repo repoPath}

      install -d -m 0700 -o root -g root ${lib.escapeShellArg borgDrainStateRoot}

      # The coalescing gate runs FIRST, before the global Borg lock. A wake
      # inside the min-interval window has no work to do, so it must cost a
      # single stat -- not a lock acquisition that contends with whatever real
      # Borg operation is running. This is what makes a frequent retry timer
      # free: see the drain timers for why the retry granularity matters.
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

      acquire_borg_global_lock_or_skip "${label} Borg drain"

      cleanup_snapshot_bind_mount() {
        if mountpoint -q ${lib.escapeShellArg bindTarget}; then
          umount ${lib.escapeShellArg bindTarget}
        fi
      }
      cleanup_snapshot_bind_mount || true

      install -d -m 0700 -o root -g root ${lib.escapeShellArg repoPath}
      install -d -m 0700 -o root -g root ${lib.escapeShellArg bindTarget}

      recover_stale_borg_locks

      if [ ! -e ${lib.escapeShellArg "${repoPath}/config"} ]; then
        with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
      fi

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

      if with_borg_lock borg list --short --glob-archives "$archive_name" "$BORG_REPO" | grep -Fxq "$archive_name"; then
        echo "Archive $archive_name already exists"
      else

        cleanup_snapshot_bind_mount || true
        mount --bind "$snapshot_path" ${lib.escapeShellArg bindTarget}

        if with_borg_lock borg create \
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
      marker=${lib.escapeShellArg "${borgDrainStateRoot}/${label}.last-success"}
      {
        printf 'archive=%s\n' "$archive_name"
        printf 'snapshot=%s\n' "$snapshot"
        printf 'epoch=%s\n' "$(date +%s)"
      } > "$marker.tmp"
      mv "$marker.tmp" "$marker"
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
    # Pure regenerable caches and logs, multi-GB each.
    "home/sinity/.npm/_cacache"
    "home/sinity/.local/share/nvim/mason"
    "home/sinity/.local/share/hyprland/logs"
    "var/lib/systemd/coredump"
    # Sinex runtime state is backed up through structured service tooling.
    "var/lib/sinex"
  ];

  realmExcludes = [
    # Re-acquirable media: Steam and model weights re-download, and stashbox
    # regenerable members carry their own provenance. Precious-small media
    # (books, videos, substack, edu, music-audio-features, web-content)
    # deliberately stays in coverage.
    "media/Steam"
    "media/model"
    "media/stashbox/models"
    "media/stashbox/generated"
    "media/stashbox/analysis-cache"
    "media/stashbox/gpu-venv"
    # Top-level regenerable-cache root (sinex cargo/dev caches via the
    # /var/cache/sinex bind, nix-build) — pure churn, never backup material.
    "cache"
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

  # Borg excludes are glob patterns relative to /realm. Test both an item and
  # its ancestors: excluding .beads or project/sinex excludes its children
  # even when the protected item itself does not match the pattern directly.
  borgGlobToRegex =
    pattern:
    let
      globStarPlaceholder = "__SINNIX_BORG_GLOBSTAR__";
      withGlobStarPlaceholder = lib.replaceStrings [ "**" ] [ globStarPlaceholder ] pattern;
      escaped =
        lib.replaceStrings
          [
            "\\"
            "."
            "+"
            "("
            ")"
            "["
            "]"
            "{"
            "}"
            "^"
            "$"
            "|"
          ]
          [
            "\\\\"
            "\\."
            "\\+"
            "\\("
            "\\)"
            "\\["
            "\\]"
            "\\{"
            "\\}"
            "\\^"
            "\\$"
            "\\|"
          ]
          withGlobStarPlaceholder;
      withSingleStar = lib.replaceStrings [ "*" ] [ "[^/]*" ] escaped;
      withQuestion = lib.replaceStrings [ "?" ] [ "[^/]" ] withSingleStar;
    in
    "^${lib.replaceStrings [ globStarPlaceholder ] [ ".*" ] withQuestion}$";
  protectedPathAndAncestors =
    path:
    let
      parts = lib.splitString "/" path;
    in
    lib.genList (index: lib.concatStringsSep "/" (lib.take (index + 1) parts)) (builtins.length parts);
  realmExcludeMatchesProtectedPath =
    exclude:
    lib.any (
      path:
      lib.any (candidate: builtins.match (borgGlobToRegex exclude) candidate != null) (
        protectedPathAndAncestors path
      )
    ) sinexBeadsArchivePaths;

  mkSinexBeadsDrillScript = ''
    set -euo pipefail

    archive_paths=(
      ${lib.escapeShellArg sinexBeadsDoltArchivePath}
      ${lib.escapeShellArg sinexBeadsIssuesArchivePath}
    )

    exec 9>${lib.escapeShellArg borgGlobalLock}
    if ! flock -n 9; then
      echo "another Borg operation is active; skipping Beads restore drill" >&2
      exit 0
    fi

    mapfile -t archives < <(borg list --short --glob-archives 'realm-*' ${lib.escapeShellArg borgRepoRealm} | sort)
    if [ "''${#archives[@]}" -eq 0 ]; then
      echo "no realm Borg archive is available for the Sinex Beads restore drill" >&2
      exit 1
    fi
    archive="''${archives[$(( ''${#archives[@]} - 1 ))]}"

    for archive_path in "''${archive_paths[@]}"; do
      borg list --short "${borgRepoRealm}::''${archive}" "$archive_path" | grep -Fxq "$archive_path"
    done

    restore_root="$(mktemp -d)"
    cleanup() {
      rm -rf "$restore_root"
    }
    trap cleanup EXIT

    (
      cd "$restore_root"
      borg extract "${borgRepoRealm}::''${archive}" "''${archive_paths[@]}"
    )

    issues_path="$restore_root/${sinexBeadsIssuesArchivePath}"
    dolt_path="$restore_root/${sinexBeadsDoltArchivePath}"
    test -s "$issues_path"
    jq -e -s 'length > 0' "$issues_path" >/dev/null
    test -d "$dolt_path/.dolt"

    source_git_head="$(${pkgs.git}/bin/git -c safe.directory=${lib.escapeShellArg sinexProjectPath} -C ${lib.escapeShellArg sinexProjectPath} rev-parse HEAD)"
    dolt_commit="$(${pkgs.dolt}/bin/dolt --data-dir "$dolt_path" --use-db sinex sql \
      -q 'SELECT commit_hash FROM dolt_log LIMIT 1' -r json \
      | jq -er '.rows[0].commit_hash // empty')"

    install -d -m 0755 ${lib.escapeShellArg (builtins.dirOf sinexBeadsDrillLog)}
    jq -nc \
      --arg type sinex_beads_restore_drill \
      --arg archive "$archive" \
      --arg source_git_head "$source_git_head" \
      --arg dolt_commit "$dolt_commit" \
      --arg issues_jsonl_sha256 "$(sha256sum "$issues_path" | cut -d ' ' -f 1)" \
      --arg ts "$(date -Iseconds)" \
      '{ts:$ts,type:$type,archive:$archive,source_git_head:$source_git_head,dolt_commit:$dolt_commit,issues_jsonl_sha256:$issues_jsonl_sha256,ok:true}' \
      | tee -a ${lib.escapeShellArg sinexBeadsDrillLog}
  '';

  mkBorgStatusScript = ''
    set -euo pipefail

    install -d -m 0755 ${lib.escapeShellArg (builtins.dirOf borgStatusLog)}
    now="$(date +%s)"
    status=0

    json_escape() {
      jq -Rsa .
    }

    integrity_state() {
      if [ ! -s ${lib.escapeShellArg borgIntegrityReceipt} ]; then
        printf '%s\n' missing
        return
      fi

      if ! jq -e '
        (.operation_kind == "integrity_check") and
        (.run_id | type == "string" and length > 0) and
        (.expected_jobs | type == "array") and
        (.start_epoch | type == "number") and
        (.deadline_epoch | type == "number") and
        (.state | type == "string")
      ' ${lib.escapeShellArg borgIntegrityReceipt} >/dev/null 2>&1; then
        printf '%s\n' missing
        return
      fi

      jq -r --argjson now "$now" '
        if .state == "running" and $now <= .deadline_epoch then "maintenance"
        elif .state == "running" then "expired"
        elif .state == "completed" then "completed"
        elif .state == "failed" then "failed"
        else "missing"
        end
      ' ${lib.escapeShellArg borgIntegrityReceipt}
    }

    integrity_covers() {
      label="$1"
      jq -e --arg label "$label" '.expected_jobs | index($label) != null' \
        ${lib.escapeShellArg borgIntegrityReceipt} >/dev/null 2>&1
    }

    record_transition() {
      label="$1"
      state="$2"
      run_id="$3"
      deadline="$4"
      previous=""
      if [ -s ${lib.escapeShellArg borgIntegrityTransitionState} ]; then
        previous="$(jq -r --arg label "$label" '.[$label] // empty' ${lib.escapeShellArg borgIntegrityTransitionState})"
      fi
      if [ "$previous" = "$state" ]; then
        return
      fi
      install -d -m 0700 ${lib.escapeShellArg borgDrainStateRoot}
      jq -cn \
        --arg type notification_transition \
        --arg label "$label" \
        --arg state "$state" \
        --arg run_id "$run_id" \
        --argjson deadline "$deadline" \
        --arg ts "$(date -Iseconds)" \
        '{ts:$ts,type:$type,label:$label,state:$state,run_id:$run_id,deadline_epoch:$deadline}' \
        >> ${lib.escapeShellArg borgStatusLog}
      tmp=${lib.escapeShellArg borgIntegrityTransitionState}.tmp
      # Branch on the file existing, not on jq failing. Falling back to a
      # single-entry object is right on first run and destructive on a corrupt
      # one -- it would drop every other label's transition state and then mv
      # that over the original. A parse failure is reported and the file left
      # alone instead.
      if [ -s ${lib.escapeShellArg borgIntegrityTransitionState} ]; then
        if ! jq --arg label "$label" --arg state "$state" '.[$label] = $state' \
          ${lib.escapeShellArg borgIntegrityTransitionState} > "$tmp"; then
          rm -f "$tmp"
          echo "borgbackup-status: integrity transition state is unreadable; leaving it intact and not recording $label=$state" >&2
          return 0
        fi
      else
        jq -cn --arg label "$label" --arg state "$state" '{($label):$state}' > "$tmp"
      fi
      if [ -s "$tmp" ]; then
        mv "$tmp" ${lib.escapeShellArg borgIntegrityTransitionState}
      fi
    }

    latest_archive_epoch() {
      label="$1"
      marker=${lib.escapeShellArg borgDrainStateRoot}/"$label.last-success"
      stamp=${lib.escapeShellArg borgDrainStateRoot}/"$label.stamp"

      if [ -s "$marker" ]; then
        sed -n 's/^epoch=//p' "$marker" | tail -n 1
      elif [ -e "$stamp" ]; then
        stat -c %Y "$stamp"
      fi
    }

    oldest_snapshot_epoch() {
      dir="$1"
      glob="$2"
      find "$dir" -maxdepth 1 -mindepth 1 -type d -name "$glob" -printf "%f\n" \
        | sort \
        | head -n 1 \
        | sed -E 's/^[^.]+\.([0-9]{8})T([0-9]{6})([+-][0-9]{4})$/\1 \2 \3/' \
        | while read -r day time tz; do
            [ -n "''${day:-}" ] || continue
            date -d "''${day:0:4}-''${day:4:2}-''${day:6:2} ''${time:0:2}:''${time:2:2}:''${time:4:2} $tz" +%s
          done
    }

    check_archive() {
      label="$1"
      latest_status=0
      latest="$(latest_archive_epoch "$label")" || latest_status=$?
      if [ -z "$latest" ]; then
        age=-1
        ok=false
        if [ "$latest_status" -eq 0 ]; then
          message="no successful Borg drain marker found"
        else
          message="Borg drain marker unreadable"
        fi
        status=1
      else
        age=$((now - latest))
        integrity="$(integrity_state)"
        run_id=""
        deadline=0
        if [ -s ${lib.escapeShellArg borgIntegrityReceipt} ]; then
          run_id="$(jq -r '.run_id // empty' ${lib.escapeShellArg borgIntegrityReceipt})"
          deadline="$(jq -r '.deadline_epoch // 0' ${lib.escapeShellArg borgIntegrityReceipt})"
        fi
        if [ "$integrity" = maintenance ] && integrity_covers "$label"; then
          ok=true
          state=maintenance
          message="integrity check in planned maintenance"
        elif [ "$integrity" = failed ] || [ "$integrity" = expired ] || [ "$integrity" = missing ]; then
          ok=false
          state=red
          message="integrity check receipt is $integrity"
          status=1
        elif [ "$age" -le ${toString borgArchiveMaxAgeSec} ]; then
          ok=true
          state=healthy
          message="archive fresh"
        else
          ok=false
          state=red
          message="latest archive too old"
          status=1
        fi

        record_transition "$label" "$state" "$run_id" "$deadline"
      fi

      jq -cn \
        --arg type archive_freshness \
        --arg label "$label" \
        --arg message "$message" \
        --argjson ok "$ok" \
        --argjson age "$age" \
        --argjson max_age ${toString borgArchiveMaxAgeSec} \
        --arg state "''${state:-red}" \
        --arg run_id "''${run_id:-}" \
        --argjson deadline_epoch "''${deadline:-0}" \
        --arg ts "$(date -Iseconds)" \
        '{ts:$ts,type:$type,label:$label,ok:$ok,state:$state,run_id:$run_id,deadline_epoch:$deadline_epoch,age_sec:$age,max_age_sec:$max_age,message:$message}' \
        >> ${lib.escapeShellArg borgStatusLog}

      # Say it out loud too. This unit exits 1 by design when it finds a red
      # condition, but it used to record the reason only in the JSONL, so the
      # journal showed a bare "status=1/FAILURE" with no line explaining it --
      # the one place an operator looks first.
      if [ "$ok" = false ]; then
        echo "borgbackup-status: $label is ''${state:-red}: $message (age ''${age}s, budget ${toString borgArchiveMaxAgeSec}s)" >&2
      fi
    }

    check_queue() {
      label="$1"
      dir="$2"
      glob="$3"
      count="$(find "$dir" -maxdepth 1 -mindepth 1 -type d -name "$glob" | wc -l)"
      oldest="$(oldest_snapshot_epoch "$dir" "$glob" || true)"

      # An empty `oldest` means one of two very different things, and reporting
      # both as age=0 made every probe failure read as a fresh queue. With
      # snapshots present, failing to date the oldest is a broken probe (dir
      # unreadable, naming convention changed, date rejected) and must not
      # claim health.
      probe_failed=0
      age=0
      if [ -z "$oldest" ] && [ "$count" -gt 0 ]; then
        probe_failed=1
      elif [ -n "$oldest" ]; then
        age=$((now - oldest))
      fi

      if [ "$probe_failed" -eq 1 ]; then
        ok=false
        state=unknown
        message="snapshot queue present but its age could not be determined"
        status=1
      elif [ "$age" -le ${toString borgSnapshotQueueMaxAgeSec} ]; then
        ok=true
        state=healthy
        message="snapshot queue fresh"
      else
        ok=false
        state=red
        message="snapshot queue too old"
        status=1
      fi

      jq -cn \
        --arg type snapshot_queue \
        --arg label "$label" \
        --arg message "$message" \
        --argjson ok "$ok" \
        --argjson count "$count" \
        --argjson age "$age" \
        --argjson max_age ${toString borgSnapshotQueueMaxAgeSec} \
        --arg state "$state" \
        --arg ts "$(date -Iseconds)" \
        '{ts:$ts,type:$type,label:$label,ok:$ok,state:$state,count:$count,oldest_age_sec:$age,max_age_sec:$max_age,message:$message}' \
        >> ${lib.escapeShellArg borgStatusLog}
    }

    check_archive persist
    check_archive realm
    check_queue persist ${lib.escapeShellArg persistSnapshots} 'persist.*'
    check_queue realm ${lib.escapeShellArg realmSnapshots} 'realm.*'

    exit "$status"
  '';

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
        observe = {
          enable = true;
          restartable = false;
        };
      };
      borgbackup-job-realm = {
        unit = "borgbackup-job-realm.service";
        resourceClass = "backup-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
      };
      borgbackup-job-sinex-blobs = {
        unit = "borgbackup-job-sinex-blobs.service";
        resourceClass = "backup-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
      };
      borgbackup-check = {
        unit = "borgbackup-check.service";
        resourceClass = "backup-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
      };
      borgbackup-maintenance = {
        unit = "borgbackup-maintenance.service";
        resourceClass = "backup-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
      };
      borgbackup-status = {
        unit = "borgbackup-status.service";
        resourceClass = "backup-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
        captures = [
          {
            name = "borg-status";
            path = borgStatusLog;
            eventDriven = true;
            # borgbackup-status.timer runs hourly (3600s); budget 3x cadence
            # so one missed/delayed run doesn't false-positive.
            staleAfterSeconds = 10800;
          }
        ];
      };
      borgbackup-status-timer = {
        unit = "borgbackup-status.timer";
        kind = "timer";
        resourceClass = "backup-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
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
            # sinnix-borg-drill.timer runs weekly (604800s); budget 3x
            # cadence so one missed/delayed run doesn't false-positive.
            staleAfterSeconds = 1814400;
          }
        ];
      };
      sinnix-borg-beads-drill = {
        unit = "sinnix-borg-beads-drill.service";
        resourceClass = "backup-maintenance";
        captures = [
          {
            name = "borg-beads-drill";
            path = sinexBeadsDrillLog;
            eventDriven = true;
            staleAfterSeconds = 1814400;
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

    # Backups are scheduled bulk I/O and must stay below interactive work;
    # unthrottled they saturate /realm enough to visibly stall the desktop.
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
        gnugrep
        procps
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
        gnugrep
        procps
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
    };

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
    systemd.timers.borgbackup-job-persist = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* *:05,25,45:00";
        Persistent = false;
      };
    };
    systemd.timers.borgbackup-job-realm = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* *:15,35,55:00";
        Persistent = false;
      };
    };

    # ─── Sinex blob-repository Borg job ───
    # A CAS lives outside the /realm snapshot stream, so Borg reads the live
    # evaluated content-store path. Immutable objects make this safe without a
    # snapshot; `RequiresMountsFor` keeps the source mount authoritative.
    systemd.services.borgbackup-job-sinex-blobs = lib.mkIf (sinexBlobRepositoryPath != "") {
      description = "Back up sinex blob repository into Borg";
      restartIfChanged = false;
      after = [
        outerRealmMountUnit
      ];
      requires = [
        outerRealmMountUnit
      ];
      unitConfig.RequiresMountsFor = [ sinexBlobRepositoryPath ];
      serviceConfig = (backupServiceConfig "borgbackup-job-sinex-blobs.service") // {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      };
      path = with pkgs; [
        borgbackup
        coreutils
        gnugrep
        procps
        util-linux
      ];
      script = ''
        set -euo pipefail
        ${mkBorgCommonScript borgRepoSinexBlobs borgRepoSinexBlobsPath}

        install -d -m 0700 -o root -g root ${lib.escapeShellArg borgRepoSinexBlobsPath}
        recover_stale_borg_locks

        if [ ! -e ${lib.escapeShellArg "${borgRepoSinexBlobsPath}/config"} ]; then
          with_borg_lock borg init --encryption repokey-blake2 "$BORG_REPO"
        fi

        archive_name="sinex-blobs-$(date -u +%Y%m%dT%H%M%SZ)"
        with_borg_lock borg create \
          --compression auto,zstd,1 \
          --lock-wait ${toString borgLockWaitSec} \
          "::$archive_name" \
          ${lib.escapeShellArg sinexBlobRepositoryPath}
        echo "sinex blob backup complete: $archive_name"
      '';
    };

    systemd.timers.borgbackup-job-sinex-blobs = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* 05:40:00";
        RandomizedDelaySec = "10min";
        Persistent = true;
      };
    };

    assertions =
      lib.optional (sinexBlobRepositoryPath != "") {
        assertion = lib.hasInfix sinexBlobRepositoryPath config.systemd.services.borgbackup-job-sinex-blobs.script;
        message = "Sinex CAS Borg backup must archive services.sinex.storage.blob.repositoryPath";
      }
      ++ [
        {
          assertion = lib.all (exclude: !realmExcludeMatchesProtectedPath exclude) realmExcludes;
          message = "The /realm Borg backup must not exclude Sinex .beads/dolt or .beads/issues.jsonl";
        }
      ];

    # Failure surfacing for the two borg verification/integrity units
    # (sinnix-borg-drill, borgbackup-check): a restore drill or repo check
    # that fails silently is worse than none. Appends a `service_failure`
    # event to the existing borgStatusLog JSONL (same file/consumer path as
    # the archive_freshness/snapshot_queue events above) and best-effort
    # desktop-notifies the active graphical session.
    systemd.services."sinnix-service-failure-notify@" = {
      description = "Record + surface a failed backup-verification unit (%i)";
      serviceConfig.Type = "oneshot";
      path = [
        pkgs.coreutils
        pkgs.jq
        pkgs.systemd
        pkgs.sudo
        pkgs.libnotify
      ];
      script = ''
        set -euo pipefail
        unit="%I"
        result="$(systemctl show "$unit" -p Result --value 2>/dev/null || echo unknown)"
        install -d -m 0755 ${lib.escapeShellArg (builtins.dirOf borgStatusLog)}
        jq -cn \
          --arg type service_failure \
          --arg unit "$unit" \
          --arg result "$result" \
          --arg ts "$(date -Iseconds)" \
          '{ts:$ts,type:$type,unit:$unit,result:$result,ok:false,message:"unit entered failed state"}' \
          >> ${lib.escapeShellArg borgStatusLog}

        user_uid="$(id -u ${lib.escapeShellArg config.sinnix.user.name} 2>/dev/null || true)"
        if [ -n "$user_uid" ] && [ -S "/run/user/$user_uid/bus" ]; then
          sudo -u ${lib.escapeShellArg config.sinnix.user.name} \
            DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$user_uid/bus" \
            notify-send --urgency=critical "Backup verification failed" "$unit: $result" \
            || true
        fi
      '';
    };

    # Weekly integrity check — verify repo metadata and detect bit rot on the HDD.
    systemd.services.borgbackup-check = {
      description = "Borg backup integrity check";
      restartIfChanged = false;
      onFailure = [ "sinnix-service-failure-notify@%n.service" ];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStopSec = "15s";
      }
      // backupServiceConfig "borgbackup-check.service";
      environment.BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
      environment.BORG_CACHE_DIR = borgCacheDir;
      path = with pkgs; [
        borgbackup
        coreutils
        findutils
        gnugrep
        jq
        procps
        util-linux
      ];
      script = ''
        set -euo pipefail

        ${mkBorgCommonScript borgRepoPersist borgRepoPersistPath}
        acquire_borg_global_lock_or_skip "Borg repository check"
        run_id="''${INVOCATION_ID:-borg-check-$(date +%s)}"
        write_integrity_receipt() {
          state="$1"
          install -d -m 0700 ${lib.escapeShellArg borgDrainStateRoot}
          jq -cn \
            --arg operation_kind integrity_check \
            --arg run_id "$run_id" \
            --argjson expected_jobs '["persist","realm"]' \
            --argjson start_epoch "$start_epoch" \
            --argjson deadline_epoch "$deadline_epoch" \
            --arg state "$state" \
            --arg ts "$(date -Iseconds)" \
            '{operation_kind:$operation_kind,run_id:$run_id,expected_jobs:$expected_jobs,start_epoch:$start_epoch,deadline_epoch:$deadline_epoch,state:$state,updated_at:$ts}' \
            > ${lib.escapeShellArg borgIntegrityReceipt}.tmp
          mv ${lib.escapeShellArg borgIntegrityReceipt}.tmp ${lib.escapeShellArg borgIntegrityReceipt}
        }
        start_epoch="$(date +%s)"
        deadline_epoch=$((start_epoch + 3 * 3600))
        finish_integrity_receipt() {
          rc="$?"
          if [ "$rc" -eq 0 ]; then
            write_integrity_receipt completed
          else
            write_integrity_receipt failed
          fi
          exit "$rc"
        }
        # Armed BEFORE the first receipt write: when jq was missing from this
        # unit's path, the "running" write died with 127 before the trap
        # existed, so no receipt was written at all -- not even a failed one.
        # borgbackup-status then reported "integrity check receipt is
        # missing" and went red for two weeks while the backups themselves
        # were fine.
        trap finish_integrity_receipt EXIT
        write_integrity_receipt running
        recover_stale_borg_locks
        ${mkBorgCommonScript borgRepoRealm borgRepoRealmPath}
        recover_stale_borg_locks

        # --max-duration makes the repository check INCREMENTAL: each run
        # verifies segments for at most the budget and records progress in
        # the repo, so successive weekly runs cycle through the full
        # repository without ever monopolizing the repo lock for a whole day
        # and starving the hourly drains.
        ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 1800 ${borgRepoPersist}
        ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 7200 ${borgRepoRealm}
        ${pkgs.borgbackup}/bin/borg check --repository-only --max-duration 1800 ${borgRepoSinexBlobs}
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
      environment.BORG_CACHE_DIR = borgCacheDir;
      path = with pkgs; [
        borgbackup
        coreutils
        findutils
        gnugrep
        procps
        util-linux
      ];
      script = ''
        set -euo pipefail

        export BORG_CACHE_DIR=${lib.escapeShellArg borgCacheDir}

        with_borg_lock() {
          if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
            "$@"
          else
            flock ${lib.escapeShellArg borgGlobalLock} "$@"
          fi
        }

        acquire_borg_global_lock_or_skip() {
          if [ "''${SINNIX_BORG_GLOBAL_LOCK_HELD:-0}" = 1 ]; then
            return
          fi
          reason="$1"
          exec 9>${lib.escapeShellArg borgGlobalLock}
          if ! flock -n 9; then
            echo "Another Borg operation is active; skipping $reason"
            exit 0
          fi
          export SINNIX_BORG_GLOBAL_LOCK_HELD=1
        }

        recover_stale_borg_locks() {
          repo="$1"
          repo_path="''${repo#file://}"

          stale_lock="$(
            find "$repo_path" \
              -maxdepth 2 -type d -name lock.exclusive \
              -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null || true
          )"
          if [ -z "$stale_lock" ]; then
            if ! find ${lib.escapeShellArg borgCacheDir} \
              -maxdepth 2 -type d -name lock.exclusive \
              -mmin +${toString borgStaleLockMinutes} -print -quit 2>/dev/null | grep -q .; then
              return
            fi
            stale_lock="stale Borg cache lock"
          fi

          if pgrep -x borg >/dev/null 2>&1; then
            echo "Stale-looking Borg lock remains for $repo, but a Borg process is alive; refusing break-lock" >&2
            return
          fi

          echo "Breaking stale Borg lock for $repo: $stale_lock" >&2
          with_borg_lock borg break-lock "$repo"
        }

        maintain_repo() {
          repo="$1"
          if [ ! -e "''${repo#file://}/config" ]; then
            echo "Skipping uninitialized repo $repo"
            return
          fi

          acquire_borg_global_lock_or_skip "Borg maintenance"
          recover_stale_borg_locks "$repo"
          with_borg_lock borg prune --lock-wait ${toString borgLockWaitSec} ${mkBorgRetentionArgs} "$repo"
          with_borg_lock borg compact --lock-wait ${toString borgLockWaitSec} "$repo"
        }

        maintain_repo ${lib.escapeShellArg borgRepoPersist}
        maintain_repo ${lib.escapeShellArg borgRepoRealm}
        maintain_repo ${lib.escapeShellArg borgRepoSinexBlobs}
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

    systemd.services.borgbackup-status = {
      description = "Check Borg backup freshness and snapshot queue age";
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
        TimeoutStartSec = "30s";
      }
      // backupServiceConfig "borgbackup-status.service";
      path = with pkgs; [
        borgbackup
        coreutils
        findutils
        gnugrep
        jq
        util-linux
      ];
      script = mkBorgStatusScript;
    };
    systemd.timers.borgbackup-status = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "hourly";
        Persistent = true;
        RandomizedDelaySec = "10min";
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
        jq
      ];
      script = ''
        set -euo pipefail

        stamp="$(date -u +%Y%m%dT%H%M%SZ)"
        install -d -m 0700 -o root -g root "${btrfsImageRoot}"

        # btrfs-image writes to "$out.tmp" and renames only on success, and
        # the 30-day prune below matches finished images only, so a dead run
        # leaves multi-GB orphans indefinitely.
        find "${btrfsImageRoot}" -type f -name '*.btrfs-image.tmp' -mtime +1 -delete

        record_status() {
          jq -cn \
            --arg ts "$(date -Iseconds)" \
            --arg type btrfs_metadata_image \
            --arg label "$1" \
            --arg state "$2" \
            --argjson attempts "$3" \
            --arg message "$4" \
            '{ts:$ts,type:$type,label:$label,ok:($state == "healthy"),state:$state,attempts:$attempts,message:$message}' \
            >> ${lib.escapeShellArg borgStatusLog}
        }

        # btrfs-image walks a MOUNTED, actively-written filesystem: there is
        # no consistent-view mode for one, and a tree block whose generation
        # advances between the parent-pointer read and the child read aborts
        # the walk with "parent transid verify failed" / "child eb corrupted".
        # That is a race against concurrent writes, not on-disk damage (the
        # device error counters stay at zero throughout), so it is worth
        # retrying rather than failing the run -- a quieter moment succeeds.
        capture_image() {
          label="$1"
          device="$2"
          out="${btrfsImageRoot}/$label-$stamp.btrfs-image"
          tmp="$out.tmp"
          attempt=1

          while [ "$attempt" -le 3 ]; do
            rm -f "$tmp"
            if btrfs-image -c 9 "$device" "$tmp"; then
              chmod 0600 "$tmp"
              mv "$tmp" "$out"
              record_status "$label" healthy "$attempt" "metadata image captured"
              return 0
            fi
            echo "btrfs-metadata-image-backup: $label attempt $attempt failed (live-filesystem race or real error)" >&2
            attempt=$((attempt + 1))
            sleep 60
          done

          rm -f "$tmp"
          record_status "$label" red 3 "metadata image failed three times; check btrfs device stats for real corruption"
          echo "btrfs-metadata-image-backup: $label failed after 3 attempts" >&2
          return 1
        }

        # Per-label accounting: a combined exit code hides which target is
        # actually broken.
        rc=0
        capture_image realm /dev/disk/by-uuid/43701cf7-7880-4e0c-9725-b6e12d91898a || rc=1
        capture_image persist /dev/disk/by-uuid/f4782d9f-aabe-408e-b18b-2f2baa9e9a02 || rc=1

        find "${btrfsImageRoot}" -type f -name '*.btrfs-image' -mtime +30 -delete
        exit "$rc"
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
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${borgRepoSinexBlobsPath}
      ${pkgs.coreutils}/bin/install -d -m 0700 -o root -g root ${btrfsImageRoot}
    '';

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
      "d ${borgCacheDir} 0700 root root -"
      "d ${borgDrainStateRoot} 0700 root root -"
      "f ${borgGlobalLock} 0600 root root -"
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
        OnCalendar = "*-*-* *:00/30:00";
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
      environment.BORG_CACHE_DIR = borgCacheDir;
      path = with pkgs; [
        btrfs-progs
        borgbackup
        coreutils
        findutils
        gnugrep
        procps
        util-linux
      ];
      script = ''
        ${mkBorgCommonScript borgRepoRootSnapshots borgRepoRootSnapshotsPath}
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

    # Weekly bounded Borg verification drill.
    #
    # Full `borg check --verify-data` archive drills have proven able to run for
    # most of a day on the local HDD. The scheduled drill instead uses Borg's
    # resumable `--repository-only --max-duration` mode so integrity checking
    # progresses without monopolizing the host. Full archive-data verification
    # remains available as an explicit manual `sinnix-borg-drill --verify-data`
    # command.
    systemd.services.sinnix-borg-drill = {
      description = "Borg bounded verification drill";
      # Detach from nixos-rebuild switch: this is a multi-hour oneshot;
      # switch-to-configuration must not block waiting for it to finish
      # when the unit hash changes or the Persistent=true timer wants to
      # catch up. The timer schedules invocations on its own cadence.
      restartIfChanged = false;
      reloadIfChanged = false;
      stopIfChanged = false;
      onFailure = [ "sinnix-service-failure-notify@%n.service" ];
      after = [
        "network.target"
      ];
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_CACHE_DIR = borgCacheDir;
        SINNIX_BORG_GLOBAL_LOCK = borgGlobalLock;
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

    # The realm archive is the production authority for Sinex's checkout,
    # including the mutable Beads Dolt directory and tracked JSONL export.
    # This drill lists both exact paths, extracts them into an ephemeral
    # directory, validates their formats, and records archive/source commits.
    systemd.services.sinnix-borg-beads-drill = {
      description = "Restore drill for Sinex Beads Dolt and issues JSONL";
      restartIfChanged = false;
      reloadIfChanged = false;
      stopIfChanged = false;
      onFailure = [ "sinnix-service-failure-notify@%n.service" ];
      after = [ outerRealmMountUnit ];
      requires = [ outerRealmMountUnit ];
      environment = {
        BORG_PASSCOMMAND = "${pkgs.coreutils}/bin/cat ${borgPassphrasePath}";
        BORG_CACHE_DIR = borgCacheDir;
      };
      path = with pkgs; [
        borgbackup
        coreutils
        dolt
        git
        gnugrep
        jq
        util-linux
      ];
      serviceConfig = {
        Type = "oneshot";
        PrivateTmp = true;
        TimeoutStartSec = "30min";
      }
      // backupServiceConfig "sinnix-borg-beads-drill.service";
      script = mkSinexBeadsDrillScript;
    };

    systemd.timers.sinnix-borg-beads-drill = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        # Follow the regular realm archive and stay clear of the repository
        # integrity drill on Wednesday.
        OnCalendar = "Thu 05:00:00";
        Persistent = true;
      };
    };

  };
}
