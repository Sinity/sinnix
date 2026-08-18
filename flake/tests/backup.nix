# Provably fails when: the drain stops deleting snapshots it has proven into
# an archive (verified by removing the `btrfs subvolume delete` from
# mkSnapshotDrainScript), stops bind-mounting the snapshot it archives, or
# stops writing the freshness marker its capture lane watches.
#
# Borg backup drain-hook runtime checks — exercises the realm/persist
# btrbk-snapshot-drain shell logic (extracted from the systemd unit scripts)
# against mocked mount/borg/btrfs binaries.
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
            # Every backup job's freshness marker is watched by the sentinel
            # through its capture lane. The lane's path and the path actually
            # written have to be the same file, or the estate reports a backup
            # as fresh while nothing produces the marker (and the reverse: a
            # marker nobody watches). The writer is the unit's own script plus
            # the sources of the packaged scripts that unit invokes -- the
            # drill receipt, for one, is written by scripts/sinnix-borg-drill
            # rather than inline. Both sides come from the evaluated config,
            # so neither is a restated literal.
            assertion =
              let
                packagedScriptNames = builtins.attrNames (builtins.readDir ../../scripts);
                writerText =
                  name:
                  let
                    script = config.systemd.services.${name}.script or "";
                    invoked = lib.filter (scriptName: lib.hasInfix "/bin/${scriptName}" script) packagedScriptNames;
                  in
                  script
                  + lib.concatMapStrings (scriptName: builtins.readFile (../../scripts + "/${scriptName}")) invoked;
                jobs = lib.filterAttrs (
                  name: surface: lib.hasPrefix "borgbackup-" name && surface.captures != [ ]
                ) config.sinnix.runtime.surfaces;
              in
              jobs != { }
              && lib.all (
                name:
                let
                  written = writerText name;
                in
                lib.all (lane: lib.hasInfix lane.path written) jobs.${name}.captures
              ) (lib.attrNames jobs);
            message = "Every Borg job's capture lane must point at a path its unit -- or a packaged script that unit runs -- actually writes";
          }
          {
            # A liveness probe that cannot run is worse than none: the lane
            # reads healthy because nothing contradicts it.
            assertion = lib.all (
              surface:
              lib.all (
                lane:
                lane.livenessProbe == null
                || (lane.livenessProbe.command != "" && lane.livenessProbe.timeoutSeconds > 0)
              ) surface.captures
            ) (lib.attrValues config.sinnix.runtime.surfaces);
            message = "A capture lane's liveness probe must carry a real command and a bounded timeout";
          }
        ];
      };
      # `assertions` fed into evalTestSpec above are declared as NixOS module
      # assertions, but nothing in this test harness forces
      # `config.assertions` (no `system.build.toplevel` or
      # `lib.checkAssertions` consumer) -- confirmed empirically: a
      # deliberately false entry there built without error. Real `assert`
      # statements below, forced because `polylogueStateBorgScriptChecked`
      # is what actually gets used, are the enforcement mechanism for the
      # polylogue exclude-pattern checks instead.
      polylogueStateBorgScriptChecked =
        let
          script = backupRuntimeEval.config.systemd.services.borgbackup-job-polylogue-state.script;
        in
        assert lib.assertMsg (lib.hasInfix "--exclude realm/state/polylogue/source.db " script)
          "Polylogue state Borg job must exclude the qualified source.db path, not a bare filename (excludes match the FULL walked path -- see mkBorgExcludeArgs in modules/backup.nix)";
        assert lib.assertMsg (lib.hasInfix "--exclude realm/state/polylogue/source.db-wal " script)
          "Polylogue state Borg job must exclude source.db's WAL sidecar to avoid a torn copy";
        assert lib.assertMsg (!lib.hasInfix "embeddings.db.retired" script)
          "Polylogue state Borg job must not name retired database siblings in its exclude list -- they must stay covered by this direct-path job";
        script;
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
              from = "install -d -m 0755 -o root -g root";
              to = "install -d -m 0755";
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
              from = "install -d -m 0755 -o root -g root";
              to = "install -d -m 0755";
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
              from = "install -d -m 0755 -o root -g root";
              to = "install -d -m 0755";
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
              from = "install -d -m 0755 -o root -g root";
              to = "install -d -m 0755";
            }
            {
              from = "/var/lib/sinex/state/blob-repository";
              to = "$TMPDIR/live-cas";
            }
          ];

      polylogueStateBorgScript = rewriteBackupHook polylogueStateBorgScriptChecked [
        {
          from = "/outer-realm/backup/borg-polylogue-state-v1";
          to = "$TMPDIR/repos/borg-polylogue-state-v1";
        }
        {
          # Must precede the plain ".cache/borg" pattern below:
          # replaceStrings matches earlier list entries first at a given
          # position, and "borg" is itself a prefix of "borg-drain".
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
          from = "install -d -m 0755 -o root -g root";
          to = "install -d -m 0755";
        }
        {
          from = "/realm/state/polylogue";
          to = "$TMPDIR/live-polylogue";
        }
      ];

      sinexBeadsDrillScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.sinnix-borg-beads-drill.script
          [
            {
              from = "/outer-realm/backup/borg-realm-v2";
              to = "$TMPDIR/repos/borg-realm-v2";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "/realm/project/sinex";
              to = "$TMPDIR/sinex-source";
            }
            {
              from = "/realm/data";
              to = "$TMPDIR/realm-data";
            }
            {
              from = "${pkgs.git}/bin/git";
              to = "$TMPDIR/mock-bin/git";
            }
            {
              from = "${pkgs.dolt}/bin/dolt";
              to = "$TMPDIR/mock-bin/dolt";
            }
          ];

      backupBorgHookRuntime = mkRuntimeCheck system {
        name = "backup-borg-hook-runtime-check";
        nativeBuildInputs = [
          pkgs.bash
          pkgs.coreutils
          pkgs.findutils
          pkgs.gnugrep
          pkgs.jq
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
            "$TMPDIR/live-cas/objects/ab" \
            "$TMPDIR/live-polylogue/blob/objects/cd"
          printf 'production-shaped-cas-object\n' > "$TMPDIR/live-cas/objects/ab/cdef"
          printf 'production-shaped-blob-object\n' > "$TMPDIR/live-polylogue/blob/objects/cd/ef01"
          printf 'live sqlite content, excluded here on purpose\n' > "$TMPDIR/live-polylogue/source.db"

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
          cp -a "$source_path/." "$target_path/"
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
              archive_ref=""
              for arg in "$@"; do
                case "$arg" in
                  *::*) archive_ref="$arg"; break ;;
                esac
              done
              if [ -n "$archive_ref" ]; then
                repo="''${archive_ref%%::*}"
                archive="''${archive_ref##*::}"
                repo_path="''${repo#file://}"
                after_archive=0
                for arg in "$@"; do
                  if [ "$after_archive" -eq 0 ]; then
                    [ "$arg" = "$archive_ref" ] && after_archive=1
                    continue
                  fi
                  test -e "$repo_path/archives/$archive/$arg"
                  printf '%s\n' "$arg"
                done
              else
                repo="''${@: -1}"
                repo_path="''${repo#file://}"
                if [ -d "$repo_path/archives" ]; then
                  find "$repo_path/archives" -mindepth 1 -maxdepth 1 -type d -printf '%f\n'
                fi
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
              archive_ref="$1"
              archive="''${archive_ref##*::}"
              repo="''${archive_ref%%::*}"
              shift
              destination="$PWD"
              repo_path="''${repo#file://}"
              mkdir -p "$destination"
              if [ "$#" -eq 0 ]; then
                cp -a "$repo_path/archives/$archive/." "$destination/"
              else
                for archive_path in "$@"; do
                  test -e "$repo_path/archives/$archive/$archive_path"
                  mkdir -p "$(dirname "$destination/$archive_path")"
                  cp -a "$repo_path/archives/$archive/$archive_path" "$destination/$archive_path"
                done
              fi
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

          cat > "$TMPDIR/mock-bin/git" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          if [ "$1" = "-c" ]; then
            test "$2" = "safe.directory=$TMPDIR/sinex-source"
            shift 2
          fi
          test "$1" = "-C"
          test "$3" = "rev-parse"
          test "$4" = "HEAD"
          printf '%s\n' synthetic-source-git-head
          EOF

          cat > "$TMPDIR/mock-bin/dolt" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          printf '%s\n' '{"rows":[{"commit_hash":"synthetic-dolt-commit"}]}'
          EOF

          chmod +x \
            "$TMPDIR/mock-bin/mountpoint" \
            "$TMPDIR/mock-bin/mount" \
            "$TMPDIR/mock-bin/umount" \
            "$TMPDIR/mock-bin/borg" \
            "$TMPDIR/mock-bin/btrfs" \
            "$TMPDIR/mock-bin/pgrep" \
            "$TMPDIR/mock-bin/git" \
            "$TMPDIR/mock-bin/dolt"

          export PATH="$TMPDIR/mock-bin:$PATH"

          mkdir -p \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T010000" \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T011500/project/sinex/.beads/dolt/.dolt" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T010000" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T011500"
          printf '{"id":"synthetic-bead"}\n' > "$TMPDIR/realm-snapshots/realm.2026-04-02T011500/project/sinex/.beads/issues.jsonl"
          printf 'synthetic Dolt state\n' > "$TMPDIR/realm-snapshots/realm.2026-04-02T011500/project/sinex/.beads/dolt/.dolt/HEAD"

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

          cat > "$TMPDIR/run-sinex-beads-drill.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${sinexBeadsDrillScript}
          EOF

          cat > "$TMPDIR/run-polylogue-state-backup.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${polylogueStateBorgScript}
          EOF

          chmod +x \
            "$TMPDIR/run-realm-hook.sh" \
            "$TMPDIR/run-persist-hook.sh" \
            "$TMPDIR/run-missing-realm-hook.sh" \
            "$TMPDIR/run-sinex-blob-backup.sh" \
            "$TMPDIR/run-sinex-beads-drill.sh" \
            "$TMPDIR/run-polylogue-state-backup.sh"

          "$TMPDIR/run-realm-hook.sh"
          "$TMPDIR/run-persist-hook.sh"
          "$TMPDIR/run-sinex-blob-backup.sh"
          "$TMPDIR/run-sinex-beads-drill.sh"
          "$TMPDIR/run-polylogue-state-backup.sh"

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
          mkdir -p "$TMPDIR/restore"
          (
            cd "$TMPDIR/restore"
            borg extract "file://$TMPDIR/repos/borg-sinex-blobs-v1::$archive_name"
          )
          cmp "$TMPDIR/live-cas/objects/ab/cdef" "$TMPDIR/restore/objects/ab/cdef"
          grep -q "create .* $TMPDIR/live-cas" "$TMPDIR/logs/borg.log"
          ! grep -q "/realm/sinex/state/blob-repository" "$TMPDIR/logs/borg.log"
          polylogue_archive="$(borg list --short file://$TMPDIR/repos/borg-polylogue-state-v1)"
          case "$polylogue_archive" in polylogue-state-*) ;; *) exit 1 ;; esac
          mkdir -p "$TMPDIR/restore-polylogue"
          (
            cd "$TMPDIR/restore-polylogue"
            borg extract "file://$TMPDIR/repos/borg-polylogue-state-v1::$polylogue_archive"
          )
          cmp "$TMPDIR/live-polylogue/blob/objects/cd/ef01" "$TMPDIR/restore-polylogue/blob/objects/cd/ef01"
          test -f "$TMPDIR/state/borg-drain/polylogue-state.last-success"

          beads_drill_log="$(find "$TMPDIR/realm-data" -name borg_beads_drill.jsonl -print -quit)"
          test -n "$beads_drill_log"
          jq -e '
            .type == "sinex_beads_restore_drill" and
            .archive == "realm-realm.2026-04-02T011500" and
            .source_git_head == "synthetic-source-git-head" and
            .dolt_commit == "synthetic-dolt-commit" and
            .ok == true
          ' "$beads_drill_log" >/dev/null

          set +e
          "$TMPDIR/run-missing-realm-hook.sh" > "$TMPDIR/missing-realm.log" 2>&1
          missing_status=$?
          set -e

          test "$missing_status" -eq 0
          ! grep -q "borg create failed" "$TMPDIR/missing-realm.log"
        '';
      };

      # The freshness/liveness questions the retired borgbackup-status script
      # asked are now capture lanes and livenessProbes on the surfaces that
      # own the marker files (see modules/backup.nix). The claims about them
      # live in the eval spec's assertions above -- each lane must point at a
      # path its own unit writes, and each probe must be runnable. This
      # derivation forces that evaluation and publishes the lanes it checked.
      #
      # Provably fails when: a Borg job's marker path and its capture lane
      # drift apart, or a lane declares a probe with no command.
      borgHealthLanesJson = builtins.toJSON {
        inherit (backupRuntimeEval.config.sinnix.runtime.surfaces)
          borgbackup-job-persist
          borgbackup-job-realm
          borgbackup-job-sinex-blobs
          borgbackup-job-polylogue-state
          borgbackup-verify
          ;
        allSurfaceNames = builtins.attrNames backupRuntimeEval.config.sinnix.runtime.surfaces;
      };

      borgHealthLanesRuntime = pkgs.runCommand "backup-health-lanes-check" { } ''
        cat > "$out" <<'EOF_LANES'
        ${borgHealthLanesJson}
        EOF_LANES
      '';
    in
    {
      checks = {
        backup-borg-hook-runtime = backupBorgHookRuntime;
        backup-health-lanes-runtime = borgHealthLanesRuntime;
      };
    };
}
