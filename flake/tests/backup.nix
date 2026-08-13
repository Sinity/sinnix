# Borg backup drain-hook runtime checks — exercises the realm/persist
# btrbk-snapshot-drain shell logic (extracted from the systemd unit scripts)
# against mocked mount/borg/btrfs binaries.
#
# Split out of the former flake/tests-runtime.nix monolith (sinnix-7bu).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        baseTestConfig
        evalTestSpec
        mountTmpfsRoots
        mkRuntimeCheck
        ;

      backupRuntimeEval = evalTestSpec system {
        name = "backup-borg-hook-runtime";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          (_: {
            networking.hostName = "backup-runtime";
            services.sinex = {
              stateRoot = "/var/lib/sinex/state";
              storage.blob.repositoryPath = "/var/lib/sinex/state/blob-repository";
            };
          })
        ];
        assertions = config: [
          {
            assertion = lib.hasInfix config.services.sinex.storage.blob.repositoryPath config.systemd.services.borgbackup-job-sinex-blobs.script;
            message = "Sinex blob Borg job must use the evaluated CAS repository path";
          }
          {
            assertion =
              !lib.hasInfix "/realm/sinex/state/blob-repository" config.systemd.services.borgbackup-job-sinex-blobs.script;
            message = "Sinex blob Borg job must not retain the retired CAS source path";
          }
        ];
      };
      rewriteBackupHook =
        hook: replacements:
        builtins.replaceStrings (map (replacement: replacement.from) replacements) (map (
          replacement: replacement.to
        ) replacements) hook;
      realmBorgDrainScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-realm.script
          [
            {
              from = "/outer-realm/backup/borg-realm-v2";
              to = "$TMPDIR/repos/borg-realm-v2";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/state/borg-drain";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/state/borg-cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "install -d -m 0700 -o root -g root";
              to = "install -d -m 0700";
            }
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/realm/.btrfs/snapshot";
              to = "$TMPDIR/realm-snapshots";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/realm";
              to = "$TMPDIR/bind/realm";
            }
          ];
      persistBorgDrainScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-persist.script
          [
            {
              from = "/outer-realm/backup/borg-persist-v1";
              to = "$TMPDIR/repos/borg-persist-v1";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/state/borg-drain";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/state/borg-cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "install -d -m 0700 -o root -g root";
              to = "install -d -m 0700";
            }
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/persist/.btrfs/snapshot";
              to = "$TMPDIR/persist-snapshots";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/persist";
              to = "$TMPDIR/bind/persist";
            }
          ];
      missingRealmBorgDrainScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-realm.script
          [
            {
              from = "/outer-realm/backup/borg-realm-v2";
              to = "$TMPDIR/repos/borg-realm-v2";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/state/borg-drain";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/state/borg-cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "install -d -m 0700 -o root -g root";
              to = "install -d -m 0700";
            }
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/realm/.btrfs/snapshot";
              to = "$TMPDIR/realm-empty";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/realm";
              to = "$TMPDIR/bind/realm-empty";
            }
          ];

      sinexBlobBorgScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-sinex-blobs.script
          [
            {
              from = "/outer-realm/backup/borg-sinex-blobs-v1";
              to = "$TMPDIR/repos/borg-sinex-blobs-v1";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/state/borg-cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "install -d -m 0700 -o root -g root";
              to = "install -d -m 0700";
            }
            {
              from = "/var/lib/sinex/state/blob-repository";
              to = "$TMPDIR/live-cas";
            }
          ];

      backupBorgHookRuntime = mkRuntimeCheck system {
        name = "backup-borg-hook-runtime-check";
        nativeBuildInputs = [
          pkgs.bash
          pkgs.coreutils
          pkgs.findutils
          pkgs.gnugrep
          pkgs.util-linux
        ];
        script = ''
          mkdir -p \
            "$TMPDIR/mock-bin" \
            "$TMPDIR/logs" \
            "$TMPDIR/bind" \
            "$TMPDIR/repos" \
            "$TMPDIR/state" \
            "$TMPDIR/state/borg-cache" \
            "$TMPDIR/realm-snapshots" \
            "$TMPDIR/persist-snapshots" \
            "$TMPDIR/realm-empty" \
            "$TMPDIR/live-cas/objects/ab"
          printf 'production-shaped-cas-object\n' > "$TMPDIR/live-cas/objects/ab/cdef"

          cat > "$TMPDIR/mock-bin/mountpoint" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          path="''${@: -1}"
          if [ -e "$path/.mounted" ]; then
            exit 0
          fi
          exit 1
          EOF

          cat > "$TMPDIR/mock-bin/mount" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          source_path="''${@: -2:1}"
          target_path="''${@: -1}"
          mkdir -p "$target_path"
          touch "$target_path/.mounted"
          printf '%s => %s\n' "$source_path" "$target_path" >> "$TMPDIR/logs/mount.log"
          EOF

          cat > "$TMPDIR/mock-bin/umount" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          target_path="$1"
          rm -f "$target_path/.mounted"
          printf '%s\n' "$target_path" >> "$TMPDIR/logs/umount.log"
          EOF

          cat > "$TMPDIR/mock-bin/borg" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          printf '%s\n' "$*" >> "$TMPDIR/logs/borg.log"
          command="$1"
          shift
          case "$command" in
            init)
              repo="''${@: -1}"
              repo_path="''${repo#file://}"
              mkdir -p "$repo_path"
              touch "$repo_path/config"
              ;;
            list)
              repo="''${@: -1}"
              repo_path="''${repo#file://}"
              if [ -d "$repo_path/archives" ]; then
                find "$repo_path/archives" -mindepth 1 -maxdepth 1 -type d -printf '%f\n'
              fi
              ;;
            create)
              archive=""
              for arg in "$@"; do
                case "$arg" in
                  ::*) archive="''${arg#::}" ;;
                esac
              done
              source_path="''${@: -1}"
              repo="''${BORG_REPO:?BORG_REPO must be set}"
              repo_path="''${repo#file://}"
              test -n "$archive"
              test -d "$source_path"
              mkdir -p "$repo_path/archives/$archive"
              cp -a "$source_path/." "$repo_path/archives/$archive/"
              ;;
            extract)
              repo="$1"
              archive="$2"
              shift 2
              test "$1" = "--destination"
              destination="$2"
              repo_path="''${repo#file://}"
              archive="''${archive#::}"
              mkdir -p "$destination"
              cp -a "$repo_path/archives/$archive/." "$destination/"
              ;;
            break-lock)
              ;;
            *)
              echo "unexpected borg command: $*" >&2
              exit 64
              ;;
          esac
          EOF

          cat > "$TMPDIR/mock-bin/btrfs" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          printf '%s\n' "$*" >> "$TMPDIR/logs/btrfs.log"
          if [ "$1" = subvolume ] && [ "$2" = delete ]; then
            rm -rf "$3"
            exit 0
          fi
          echo "unexpected btrfs command: $*" >&2
          exit 64
          EOF

          cat > "$TMPDIR/mock-bin/pgrep" <<'EOF'
          #!${pkgs.bash}/bin/bash
          exit 1
          EOF

          chmod +x \
            "$TMPDIR/mock-bin/mountpoint" \
            "$TMPDIR/mock-bin/mount" \
            "$TMPDIR/mock-bin/umount" \
            "$TMPDIR/mock-bin/borg" \
            "$TMPDIR/mock-bin/btrfs" \
            "$TMPDIR/mock-bin/pgrep"

          export PATH="$TMPDIR/mock-bin:$PATH"

          mkdir -p \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T010000" \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T011500" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T010000" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T011500"

          cat > "$TMPDIR/run-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${realmBorgDrainScript}
          EOF

          cat > "$TMPDIR/run-persist-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${persistBorgDrainScript}
          EOF

          cat > "$TMPDIR/run-missing-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${missingRealmBorgDrainScript}
          EOF

          cat > "$TMPDIR/run-sinex-blob-backup.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${sinexBlobBorgScript}
          EOF

          chmod +x \
            "$TMPDIR/run-realm-hook.sh" \
            "$TMPDIR/run-persist-hook.sh" \
            "$TMPDIR/run-missing-realm-hook.sh" \
            "$TMPDIR/run-sinex-blob-backup.sh"

          "$TMPDIR/run-realm-hook.sh"
          "$TMPDIR/run-persist-hook.sh"
          "$TMPDIR/run-sinex-blob-backup.sh"

          grep -q "$TMPDIR/realm-snapshots/realm.2026-04-02T011500 => $TMPDIR/bind/realm" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/persist-snapshots/persist.2026-04-02T011500 => $TMPDIR/bind/persist" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/bind/realm" "$TMPDIR/logs/umount.log"
          grep -q "$TMPDIR/bind/persist" "$TMPDIR/logs/umount.log"
          grep -q "create .*::realm-realm.2026-04-02T011500" "$TMPDIR/logs/borg.log"
          grep -q "create .*::persist-persist.2026-04-02T011500" "$TMPDIR/logs/borg.log"
          grep -q "subvolume delete $TMPDIR/realm-snapshots/realm.2026-04-02T010000" "$TMPDIR/logs/btrfs.log"
          grep -q "subvolume delete $TMPDIR/persist-snapshots/persist.2026-04-02T010000" "$TMPDIR/logs/btrfs.log"
          archive_name="$(borg list --short file://$TMPDIR/repos/borg-sinex-blobs-v1)"
          case "$archive_name" in sinex-blobs-*) ;; *) exit 1 ;; esac
          borg extract "file://$TMPDIR/repos/borg-sinex-blobs-v1" "::$archive_name" --destination "$TMPDIR/restore"
          cmp "$TMPDIR/live-cas/objects/ab/cdef" "$TMPDIR/restore/objects/ab/cdef"
          grep -q "create .* $TMPDIR/live-cas" "$TMPDIR/logs/borg.log"
          ! grep -q "/realm/sinex/state/blob-repository" "$TMPDIR/logs/borg.log"

          set +e
          "$TMPDIR/run-missing-realm-hook.sh" > "$TMPDIR/missing-realm.log" 2>&1
          missing_status=$?
          set -e

          test "$missing_status" -eq 0
          ! grep -q "borg create failed" "$TMPDIR/missing-realm.log"
        '';
      };

      borgStatusRuntime = mkRuntimeCheck system {
        name = "backup-status-integrity-state-runtime-check";
        nativeBuildInputs = [
          pkgs.bash
          pkgs.coreutils
          pkgs.findutils
          pkgs.gnugrep
          pkgs.jq
        ];
        script =
          let
            statusScript = backupRuntimeEval.config.systemd.services.borgbackup-status.script;
            rewrite =
              builtins.replaceStrings
                [
                  "/realm/data/captures/machine/borg_status.jsonl"
                  "/realm/data/captures/machine"
                  "/persist/root/.cache/borg-drain/integrity-check.json"
                  "/persist/root/.cache/borg-drain/integrity-status-state.json"
                  "/persist/root/.cache/borg-drain"
                  "/persist/.btrfs/snapshot"
                  "/realm/.btrfs/snapshot"
                ]
                [
                  "/build/status.jsonl"
                  "/build"
                  "/build/state/integrity-check.json"
                  "/build/state/integrity-status-state.json"
                  "/build/state"
                  "/build/persist-snapshots"
                  "/build/realm-snapshots"
                ]
                statusScript;
          in
          ''
            mkdir -p "$TMPDIR/state" "$TMPDIR/persist-snapshots" "$TMPDIR/realm-snapshots"
            now="$(date +%s)"
            old=$((now - 100000))
            printf 'epoch=%s\n' "$old" > "$TMPDIR/state/persist.last-success"
            printf 'epoch=%s\n' "$old" > "$TMPDIR/state/realm.last-success"
            mkdir -p "$TMPDIR/persist-snapshots/persist.$(date -d "@$old" +%Y%m%dT%H%M%S+0000)"
            mkdir -p "$TMPDIR/realm-snapshots/realm.$(date -d "@$old" +%Y%m%dT%H%M%S+0000)"

            cat > "$TMPDIR/state/integrity-check.json" <<EOF
            {"operation_kind":"integrity_check","run_id":"run-1","expected_jobs":["persist"],"start_epoch":$((now - 60)),"deadline_epoch":$((now + 3600)),"state":"running"}
            EOF
            cat > "$TMPDIR/run-status.sh" <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail
            ${rewrite}
            EOF
            chmod +x "$TMPDIR/run-status.sh"

            set +e
            "$TMPDIR/run-status.sh"
            first_status=$?
            set -e
            test "$first_status" -ne 0
            jq -e 'select(.type == "archive_freshness" and .label == "persist" and .state == "maintenance" and .ok == true and .run_id == "run-1")' "$TMPDIR/status.jsonl" >/dev/null
            jq -e 'select(.type == "archive_freshness" and .label == "realm" and .state == "red" and .ok == false)' "$TMPDIR/status.jsonl" >/dev/null
            test "$(jq -c 'select(.type == "notification_transition" and .label == "persist")' "$TMPDIR/status.jsonl" | wc -l)" -eq 1

            set +e
            "$TMPDIR/run-status.sh"
            second_status=$?
            set -e
            test "$second_status" -ne 0
            test "$(jq -c 'select(.type == "notification_transition" and .label == "persist")' "$TMPDIR/status.jsonl" | wc -l)" -eq 1

            jq '.deadline_epoch = (now - 1)' "$TMPDIR/state/integrity-check.json" > "$TMPDIR/state/expired.json"
            mv "$TMPDIR/state/expired.json" "$TMPDIR/state/integrity-check.json"
            set +e
            "$TMPDIR/run-status.sh"
            expired_status=$?
            set -e
            test "$expired_status" -ne 0
            jq -e 'select(.type == "archive_freshness" and .label == "persist" and .state == "red" and .message == "integrity check receipt is expired")' "$TMPDIR/status.jsonl" >/dev/null

            jq '.state = "failed"' "$TMPDIR/state/integrity-check.json" > "$TMPDIR/state/failed.json"
            mv "$TMPDIR/state/failed.json" "$TMPDIR/state/integrity-check.json"
            set +e
            "$TMPDIR/run-status.sh"
            failed_status=$?
            set -e
            test "$failed_status" -ne 0
            jq -e 'select(.type == "archive_freshness" and .label == "persist" and .state == "red" and .message == "integrity check receipt is failed")' "$TMPDIR/status.jsonl" >/dev/null

            rm "$TMPDIR/state/integrity-check.json"
            set +e
            "$TMPDIR/run-status.sh"
            missing_status=$?
            set -e
            test "$missing_status" -ne 0
            jq -e 'select(.type == "archive_freshness" and .label == "persist" and .state == "red" and .message == "integrity check receipt is missing")' "$TMPDIR/status.jsonl" >/dev/null

            now="$(date +%s)"
            printf 'epoch=%s\n' "$((now - 30))" > "$TMPDIR/state/persist.last-success"
            printf 'epoch=%s\n' "$((now - 30))" > "$TMPDIR/state/realm.last-success"
            rm -rf "$TMPDIR/persist-snapshots" "$TMPDIR/realm-snapshots"
            mkdir -p "$TMPDIR/persist-snapshots" "$TMPDIR/realm-snapshots"
            mkdir -p "$TMPDIR/persist-snapshots/persist.$(date +%Y%m%dT%H%M%S+0000)"
            mkdir -p "$TMPDIR/realm-snapshots/realm.$(date +%Y%m%dT%H%M%S+0000)"
            cat > "$TMPDIR/state/integrity-check.json" <<EOF
            {"operation_kind":"integrity_check","run_id":"run-2","expected_jobs":["persist"],"start_epoch":$((now - 3600)),"deadline_epoch":$((now - 1800)),"state":"completed"}
            EOF
            set +e
            "$TMPDIR/run-status.sh"
            completed_status=$?
            set -e
            test "$completed_status" -eq 0
            jq -e 'select(.type == "archive_freshness" and .label == "persist" and .state == "healthy" and .ok == true)' "$TMPDIR/status.jsonl" >/dev/null
          '';
      };
    in
    {
      checks = {
        backup-borg-hook-runtime = backupBorgHookRuntime;
        backup-status-integrity-state-runtime = borgStatusRuntime;
      };
    };
}
