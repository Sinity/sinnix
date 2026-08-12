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
          (_: {
            networking.hostName = "backup-runtime";
          })
        ];
        assertions = _config: [ ];
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
            "$TMPDIR/realm-empty"

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
          case "$1" in
            init)
              repo="''${@: -1}"
              repo_path="''${repo#file://}"
              mkdir -p "$repo_path"
              touch "$repo_path/config"
              ;;
            list)
              exit 2
              ;;
            create)
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

          chmod +x \
            "$TMPDIR/run-realm-hook.sh" \
            "$TMPDIR/run-persist-hook.sh" \
            "$TMPDIR/run-missing-realm-hook.sh"

          "$TMPDIR/run-realm-hook.sh"
          "$TMPDIR/run-persist-hook.sh"

          grep -q "$TMPDIR/realm-snapshots/realm.2026-04-02T011500 => $TMPDIR/bind/realm" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/persist-snapshots/persist.2026-04-02T011500 => $TMPDIR/bind/persist" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/bind/realm" "$TMPDIR/logs/umount.log"
          grep -q "$TMPDIR/bind/persist" "$TMPDIR/logs/umount.log"
          grep -q "create .*::realm-realm.2026-04-02T011500" "$TMPDIR/logs/borg.log"
          grep -q "create .*::persist-persist.2026-04-02T011500" "$TMPDIR/logs/borg.log"
          grep -q "subvolume delete $TMPDIR/realm-snapshots/realm.2026-04-02T010000" "$TMPDIR/logs/btrfs.log"
          grep -q "subvolume delete $TMPDIR/persist-snapshots/persist.2026-04-02T010000" "$TMPDIR/logs/btrfs.log"

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
