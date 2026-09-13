# Real Borg fixtures exercise exact canonical coverage and rendered snapshot
# drain scripts. Only mount/btrfs are mocked; no production data is touched.
# Unique older bytes, same-name changes, restart, archive collision, and
# unclassified exclusions must all pass through the deletion gate.
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
            sinnix.backup.enable = true;
            sinnix.services = {
              "machine-telemetry".enable = true;
              polylogue.enable = true;
              sinex.prepareHost = true;
            };
            services.sinex = {
              stateRoot = "/var/lib/sinex/state";
              storage.blob.repositoryPath = "/var/lib/sinex/state/blob-repository";
            };
            sinnix.services.polylogue.dataDir = "/tmp/sentinel-polylogue-root";
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
            # written have to be the same file, or the health sweep reports a backup
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
            assertion =
              let
                script = config.systemd.services.borgbackup-job-machine-telemetry-dumps.script;
                service = config.systemd.services.borgbackup-job-machine-telemetry-dumps.serviceConfig;
                timer = config.systemd.timers.borgbackup-job-machine-telemetry-dumps;
              in
              service.TimeoutStartSec == "12h"
              && service.TimeoutStopSec == "15s"
              && timer.timerConfig.OnCalendar == "*-*-* 06:15:00"
              && timer.timerConfig.RandomizedDelaySec == "30min"
              && timer.timerConfig.Persistent
              && lib.hasInfix "/realm/state/db-dumps/machine-telemetry/./" script
              && lib.hasInfix "borg extract --stdout" script
              && lib.hasInfix "zstd -t" script
              && lib.hasInfix "machine-telemetry-dumps.last-success" script;
            message = "Machine telemetry dump Borg coverage must retain its finite bounds and schedule while archiving, restore-checking, and publishing its freshness marker";
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
      headlessBackupEval = evalTestSpec system {
        name = "backup-headless-default";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          ({ ... }: {
            networking.hostName = "backup-headless";
            sinnix.machine.isDesktop = false;
            services.sinex.storage.blob.repositoryPath = "/var/lib/sinex/state/blob-repository";
          })
        ];
        assertions = _: [ ];
      };
      headlessBackupUnits =
        builtins.filter (name: lib.hasInfix "borg" name || lib.hasInfix "btrbk" name)
          (
            builtins.attrNames headlessBackupEval.config.systemd.services
            ++ builtins.attrNames headlessBackupEval.config.systemd.timers
          );
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
          root = "tmp/sentinel-polylogue-root";
        in
        assert lib.assertMsg (lib.hasInfix "--exclude ${root}/source.db " script)
          "Polylogue state Borg job must exclude the configured source.db path, not a bare filename";
        assert lib.assertMsg (lib.hasInfix "--exclude ${root}/source.db-wal " script)
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
            {
              # mkBorgExcludeArgs qualifies every non-`**` pattern with the
              # source root minus its leading separator, which is what borg
              # matches against. Rewrite that spelling too, or the exclude
              # patterns name a path the test tree does not have and every
              # path-based exclusion silently matches nothing.
              from = "run/borgbackup-snapshot-inputs/realm";
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
            {
              from = "run/borgbackup-snapshot-inputs/persist";
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
          from = "/tmp/sentinel-polylogue-root";
          to = "$TMPDIR/live-polylogue";
        }
        {
          from = "tmp/sentinel-polylogue-root";
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
              from = "/realm";
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

      # The stale-lock guard, driven through the drain job's own call site.
      # The snapshot directory stays empty, so the drain reaches the guard and
      # then has nothing left to archive.
      liveHolderLockScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-realm.script
          [
            {
              from = "/outer-realm/backup/borg-realm-v2";
              to = "$TMPDIR/live-holder/repo";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/live-holder/drain-state";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/live-holder/cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/live-holder/global.lock";
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
              to = "$TMPDIR/live-holder/snapshots";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/realm";
              to = "$TMPDIR/live-holder/bind";
            }
          ];

      # The same guard through the maintenance job's call site, which passes
      # the repository as an argument. Only the realm repository is created,
      # so the other four are skipped as uninitialized.
      deadHolderLockScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-maintenance.script
          [
            {
              from = "/outer-realm/backup";
              to = "$TMPDIR/dead-holder/repos";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/dead-holder/cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/dead-holder/global.lock";
            }
          ];

      backupBorgHookRuntime =
        assert lib.assertMsg (lib.all
          (name: backupRuntimeEval.config.systemd.services.${name}.serviceConfig.TimeoutStartSec == "4h")
          [
            "borgbackup-job-realm"
            "borgbackup-job-persist"
            "borgbackup-root-snapshots"
          ]
        ) "Snapshot backlog drains must have a finite per-wake deadline";
        mkRuntimeCheck system {
          name = "backup-borg-hook-runtime-check";
          nativeBuildInputs = [
            pkgs.bash
            pkgs.borgbackup
            pkgs.coreutils
            pkgs.findutils
            pkgs.gnugrep
            pkgs.python3
            pkgs.jq
            pkgs.util-linux
          ];
          script = ''
            ${pkgs.python3}/bin/python3 ${./backup_snapshot_coverage.py} \
              --verifier ${../../modules/lib/backup/snapshot-coverage.py} \
              --scripts ${
                pkgs.writeText "backup-fixture-scripts.json" (
                  builtins.toJSON {
                    realm = realmBorgDrainScript;
                    persist = persistBorgDrainScript;
                    missing = missingRealmBorgDrainScript;
                    sinex = sinexBlobBorgScript;
                    polylogue = polylogueStateBorgScript;
                    beads = sinexBeadsDrillScript;
                    liveLock = liveHolderLockScript;
                    deadLock = deadHolderLockScript;
                  }
                )
              }
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
          borgbackup-job-machine-telemetry-dumps
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
        backup-headless-default =
          assert headlessBackupUnits == [ ];
          pkgs.runCommand "backup-headless-default-check" { } ''
            touch "$out"
          '';
      };
    };
}
