# Real Borg fixtures exercise exact canonical coverage and rendered snapshot
# drain scripts. Only mount/btrfs are mocked; no production data is touched.
# Unique older bytes, same-name changes, restart, archive collision, and
# unclassified exclusions must all pass through the deletion gate.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  defaultBeadsPath = "state/tasks/sinex/.beads";
  protectedPathMatches = import ../../modules/lib/backup/protected-paths.nix {
    inherit lib;
    paths = [
      defaultBeadsPath
      "${defaultBeadsPath}/metadata.json"
      "${defaultBeadsPath}/config.yaml"
      "${defaultBeadsPath}/dolt/sinex/.dolt"
      "library/model/control-vector"
    ];
  };
in
assert lib.assertMsg (
  lib.all protectedPathMatches [
    "state"
    "state/tasks"
    "state/tasks/sinex"
    defaultBeadsPath
    "${defaultBeadsPath}/dolt"
    "${defaultBeadsPath}/dolt/sinex/.dolt"
    "${defaultBeadsPath}/metadata.json"
    "state/**"
  ]
  && lib.all protectedPathMatches [
    "library"
    "library/model"
    "library/model/control-vector"
    "library/model/**"
  ]
  && !protectedPathMatches "library/model/ollama"
  && !protectedPathMatches "project/sinex/.beads"
) "Realm exclusions must reject the canonical Sinex task store and every ancestor";
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
      customAuthorityEval = evalTestSpec system {
        name = "backup-custom-sinex-task-authority";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          (_: {
            networking.hostName = "backup-custom-authority";
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
            sinnix.projects.entries.sinex.taskAuthority = {
              workspace = "/realm/authority/sinex/.beads";
              database = "/realm/authority/sinex/.beads/dolt";
            };
          })
        ];
        assertions = _: [ ];
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
          timer = backupRuntimeEval.config.systemd.timers.borgbackup-job-polylogue-state.timerConfig;
          root = "tmp/sentinel-polylogue-root";
        in
        assert lib.assertMsg (lib.hasInfix "--exclude ${root}/source.db " script)
          "Polylogue state Borg job must exclude the configured source.db path, not a bare filename";
        assert lib.assertMsg (lib.hasInfix "--exclude ${root}/source.db-wal " script)
          "Polylogue state Borg job must exclude source.db's WAL sidecar to avoid a torn copy";
        assert lib.assertMsg (lib.hasInfix "--exclude ${root}/.salvage-internals-20261008 " script)
          "Polylogue state Borg job must leave the inert campaign salvage directory unread";
        assert lib.assertMsg (!lib.hasInfix "embeddings.db.retired" script)
          "Polylogue state Borg job must not name retired database siblings in its exclude list -- they must stay covered by this direct-path job";
        assert lib.assertMsg (lib.hasInfix "/tmp/sentinel-polylogue-root/hooks/**" script)
          "Polylogue state Borg job must omit only the live hook input by its physical source path";
        assert lib.assertMsg (lib.hasInfix "seal-polylogue-hooks.py" script)
          "Polylogue state Borg job must seal hook carriers before archiving them";
        assert lib.assertMsg (lib.hasInfix "state/cache/polylogue-backup-hooks" script)
          "Polylogue state Borg job must use its stable private hooks cache";
        assert lib.assertMsg (lib.hasInfix "install -d -m 0700 -o root -g root" script)
          "Polylogue state hook cache must be private to root";
        assert lib.assertMsg (
          timer.OnCalendar == "*-*-* 04:15:00"
          && timer.RandomizedDelaySec == "5min"
          && !(timer.Persistent or false)
          &&
            backupRuntimeEval.config.systemd.services.borgbackup-job-polylogue-state.serviceConfig.TimeoutStartSec
            == "90min"
        ) "Polylogue state Borg job must run outside the 06:05 drain window without late catch-up";
        script;
      rewriteBackupHook =
        hook: replacements:
        builtins.replaceStrings (map (replacement: replacement.from) replacements) (map (
          replacement: replacement.to
        ) replacements) hook;
      coordinatorScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-drain-coordinator.script
          [
            {
              from = "${pkgs.python3}/bin/python3 ${../../modules/lib/backup/snapshot-coverage.py} fresh-window";
              to = "true";
            }
            {
              from = "systemctl start";
              to = "$TMPDIR/mock-bin/systemctl start";
            }
          ];
      realmBorgDrainScriptFor =
        name:
        rewriteBackupHook backupRuntimeEval.config.systemd.services.${name}.script [
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
      realmBorgDrainScript = realmBorgDrainScriptFor "borgbackup-job-realm";
      persistBorgDrainScriptFor =
        name:
        rewriteBackupHook backupRuntimeEval.config.systemd.services.${name}.script [
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
      persistBorgDrainScript = persistBorgDrainScriptFor "borgbackup-job-persist";
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
          from = "/realm/state/cache/polylogue-backup-hooks";
          to = "$TMPDIR/realm-data/state/cache/polylogue-backup-hooks";
        }
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
          from = "--exclude '/tmp/sentinel-polylogue-root/hooks/**'";
          to = "--exclude \"$TMPDIR/live-polylogue/hooks/**\"";
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
        assert lib.assertMsg
          (lib.hasInfix "authority/sinex/.beads" customAuthorityEval.config.systemd.services.sinnix-borg-beads-drill.script)
          "The Beads drill must follow a configured Sinex task authority outside state/tasks";
        rewriteBackupHook backupRuntimeEval.config.systemd.services.sinnix-borg-beads-drill.script [
          {
            from = "/outer-realm/backup/borg-realm-v2";
            to = "$TMPDIR/repos/borg-realm-v2";
          }
          {
            from = "/run/lock/sinnix-borg.lock";
            to = "$TMPDIR/state/sinnix-borg.lock";
          }
          {
            from = "/realm";
            to = "$TMPDIR/realm-data";
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
        assert lib.assertMsg
          (
            let
              verify = backupRuntimeEval.config.systemd.services.borgbackup-verify;
              timer = backupRuntimeEval.config.systemd.timers.borgbackup-verify;
              script = verify.script;
              drillScript = builtins.readFile ../../scripts/sinnix-borg-drill;
              audit = backupRuntimeEval.config.systemd.services.borgbackup-coverage-audit-realm;
              auditTimer = backupRuntimeEval.config.systemd.timers.borgbackup-coverage-audit-realm;
            in
            verify.description == "Borg repository integrity checks with bounded partial passes"
            && verify.serviceConfig.TimeoutStartSec == "4h30m"
            && timer.timerConfig.OnCalendar == "Sun 13:00:00"
            && lib.hasInfix "--max-duration 1800 file:///outer-realm/backup/borg-persist-v1" script
            && lib.hasInfix "--max-duration 7200 file:///outer-realm/backup/borg-realm-v2" script
            && lib.hasInfix "--max-duration 1800 file:///outer-realm/backup/borg-sinex-blobs-v1" script
            && lib.hasInfix "/bin/sinnix-borg-drill\n" script
            && lib.hasInfix "MAX_DURATION=1800" drillScript
            && lib.hasInfix "VERIFY_DATA=0" drillScript
            && lib.hasInfix "file:///outer-realm/backup/borg-persist-v1" drillScript
            && lib.hasInfix "file:///outer-realm/backup/borg-realm-v2" drillScript
            && lib.hasInfix "borg check --repository-only --max-duration \"$MAX_DURATION\" \"$repo\"" drillScript
            && audit.serviceConfig.TimeoutStartSec == "5h"
            && auditTimer.timerConfig.OnCalendar == "*-*-* *:35:00"
            && lib.hasInfix "status=deferred reason=borg-lock-contention remains_due=true" audit.script
          )
          "Weekly Borg verification must keep its CRC budgets and drill semantics while ending before the next archive window";
        assert lib.assertMsg (lib.all
          (name: backupRuntimeEval.config.systemd.services.${name}.serviceConfig.TimeoutStartSec == "4h")
          [
            "borgbackup-job-realm"
            "borgbackup-job-persist"
            "borgbackup-root-snapshots"
          ]
        ) "Snapshot backlog drains must have a finite per-wake deadline";
        assert lib.assertMsg (
          backupRuntimeEval.config.systemd.services.borgbackup-drain-coordinator.serviceConfig.TimeoutStartSec
          == "8h15m"
          &&
            backupRuntimeEval.config.systemd.services.borgbackup-drain-coordinator.unitConfig.PropagatesStopTo
            == [
              "borgbackup-job-persist.service"
              "borgbackup-job-realm.service"
            ]
          && !(builtins.hasAttr "borgbackup-job-persist" backupRuntimeEval.config.systemd.timers)
          && !(builtins.hasAttr "borgbackup-job-realm" backupRuntimeEval.config.systemd.timers)
          && builtins.hasAttr "borgbackup-drain-coordinator" backupRuntimeEval.config.systemd.timers
          &&
            backupRuntimeEval.config.systemd.timers.borgbackup-drain-coordinator.timerConfig.OnCalendar
            == "*-*-* 00,06,12,18:05,25:00"
          && backupRuntimeEval.config.systemd.timers.btrbk.timerConfig.OnCalendar == "*-*-* 00,06,12,18:00:00"
          &&
            backupRuntimeEval.config.systemd.services.borgbackup-job-realm.serviceConfig.Slice
            == "borgdrain.slice"
          && backupRuntimeEval.config.systemd.services.borgbackup-job-realm.serviceConfig.MemoryHigh == "4G"
          && backupRuntimeEval.config.systemd.services.borgbackup-job-realm.serviceConfig.MemoryMax == "6G"
          && backupRuntimeEval.config.systemd.slices.borgdrain.sliceConfig.MemoryHigh == "6G"
          && backupRuntimeEval.config.systemd.slices.borgdrain.sliceConfig.MemoryMax == "8G"
          &&
            builtins.length (
              builtins.filter (line: lib.hasInfix "$TMPDIR/bind/realm/state/cache" line) (
                lib.splitString "\n" realmBorgDrainScript
              )
            ) == 1
        ) "Six-hour acquisition and bounded newest-only archival must have separate schedules";
        mkRuntimeCheck system {
          name = "backup-borg-hook-runtime-check";
          nativeBuildInputs = [
            pkgs.acl
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
                    coordinator = coordinatorScript;
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
      polylogueHookSealRuntime =
        pkgs.runCommand "backup-polylogue-hook-seal-check"
          {
            nativeBuildInputs = [ pkgs.python3 ];
          }
          ''
            missing_state="$TMPDIR/state-root"
            missing_source="$missing_state/hooks"
            missing_stage="$TMPDIR/missing-sealed/realm/state/polylogue/hooks"
            mkdir -p "$missing_state" "$missing_stage"
            printf 'stale-cache' > "$missing_stage/previous.ndjson"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$missing_source" "$missing_stage"
            test -d "$missing_stage"
            test -z "$(find "$missing_stage" -mindepth 1 -print -quit)"
            if ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/unavailable-state/hooks" "$TMPDIR/unavailable-sealed/hooks"; then
              echo 'unavailable Polylogue state root unexpectedly succeeded' >&2
              exit 1
            fi
            mkdir -p "$TMPDIR/source/hooks/carriers/codex/2026-09-27"
            printf '%s\n' '{"event":"captured"}' > "$TMPDIR/source/hooks/carriers/codex/2026-09-27/4242.ndjson"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            before_inode=$(stat -c %i "$TMPDIR/sealed/realm/state/polylogue/hooks/carriers/codex/2026-09-27/4242.ndjson")
            cmp "$TMPDIR/source/hooks/carriers/codex/2026-09-27/4242.ndjson" \
              "$TMPDIR/sealed/realm/state/polylogue/hooks/carriers/codex/2026-09-27/4242.ndjson"
            printf '%s\n' '{"event":"appended-after-seal"}' \
              >> "$TMPDIR/source/hooks/carriers/codex/2026-09-27/4242.ndjson"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            after_inode=$(stat -c %i "$TMPDIR/sealed/realm/state/polylogue/hooks/carriers/codex/2026-09-27/4242.ndjson")
            test "$before_inode" != "$after_inode"
            printf '%s\n' '{"event":"new-carrier"}' \
              > "$TMPDIR/source/hooks/carriers/codex/2026-09-27/4343.ndjson"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            cmp "$TMPDIR/source/hooks/carriers/codex/2026-09-27/4343.ndjson" \
              "$TMPDIR/sealed/realm/state/polylogue/hooks/carriers/codex/2026-09-27/4343.ndjson"
            before_inode=$(stat -c %i "$TMPDIR/sealed/realm/state/polylogue/hooks/carriers/codex/2026-09-27/4343.ndjson")
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            test "$before_inode" = "$(stat -c %i "$TMPDIR/sealed/realm/state/polylogue/hooks/carriers/codex/2026-09-27/4343.ndjson")"
            printf 'outside' > "$TMPDIR/outside"
            ln -s "$TMPDIR/outside" "$TMPDIR/source/hooks/transition"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            rm "$TMPDIR/source/hooks/transition"
            mkdir "$TMPDIR/source/hooks/transition"
            printf 'inside' > "$TMPDIR/source/hooks/transition/child"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            test -d "$TMPDIR/sealed/realm/state/polylogue/hooks/transition"
            test "$(cat "$TMPDIR/outside")" = outside
            rm "$TMPDIR/source/hooks/transition/child"
            rmdir "$TMPDIR/source/hooks/transition"
            printf 'replacement' > "$TMPDIR/source/hooks/transition"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            test -f "$TMPDIR/sealed/realm/state/polylogue/hooks/transition"
            rm "$TMPDIR/source/hooks/transition"
            mkdir "$TMPDIR/source/hooks/transition"
            ln -s "$TMPDIR/outside" "$TMPDIR/source/hooks/transition/link"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            rm -r "$TMPDIR/source/hooks/transition"
            ln -s "$TMPDIR/outside" "$TMPDIR/source/hooks/transition"
            ${pkgs.python3}/bin/python3 ${../../modules/lib/backup/seal-polylogue-hooks.py} \
              "$TMPDIR/source/hooks" "$TMPDIR/sealed/realm/state/polylogue/hooks"
            test -L "$TMPDIR/sealed/realm/state/polylogue/hooks/transition"
            ${pkgs.python3}/bin/python3 - ${../../modules/lib/backup/seal-polylogue-hooks.py} <<'PY'
            import importlib.util
            import os
            import tempfile
            from pathlib import Path
            import sys

            spec = importlib.util.spec_from_file_location("hook_sealer", sys.argv[1])
            sealer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sealer)
            root = Path(tempfile.mkdtemp())
            source = root / "source"
            source.mkdir()
            outside = root / "outside"
            outside.write_text("outside")
            original = source / "event"
            original.write_text("inside")
            record = sealer._file_record(os.stat(original, follow_symlinks=False))
            original.unlink()
            original.symlink_to(outside)
            try:
                sealer._clone_file(source, "event", root / "sealed-event", record)
                raise AssertionError("final symlink replacement was followed")
            except OSError:
                pass
            assert outside.read_text() == "outside"

            nested = source / "nested"
            nested.mkdir()
            (nested / "event").write_text("inside nested")
            nested_record = sealer._file_record(
                os.stat(nested / "event", follow_symlinks=False)
            )
            outside_directory = root / "outside-directory"
            outside_directory.mkdir()
            (outside_directory / "event").write_text("outside nested")
            nested.rename(source / "held-directory")
            nested.symlink_to(outside_directory, target_is_directory=True)
            try:
                sealer._clone_file(source, "nested/event", root / "sealed-nested", nested_record)
                raise AssertionError("intermediate symlink replacement was followed")
            except OSError:
                pass
            assert (outside_directory / "event").read_text() == "outside nested"
            manifest = sealer._manifest(source)
            assert manifest["nested"]["kind"] == "symlink"
            assert "nested/event" not in manifest
            os.utime(source / "held-directory", ns=(1, 2))
            assert sealer._manifest(source) == sealer._manifest(source)

            retry_source = root / "retry-source"
            retry_source.mkdir()
            (retry_source / "a-stable").write_text("stable")
            (retry_source / "z-changing").write_text("first")
            retry_destination = root / "retry-sealed"
            real_clone = sealer._clone_file
            calls = []

            def clone_then_change(source, relative, destination, expected):
                calls.append(relative)
                real_clone(source, relative, destination, expected)
                if calls == ["a-stable"]:
                    (source / "z-changing").write_text("second")

            sealer._clone_file = clone_then_change
            sys.argv = ["seal", str(retry_source), str(retry_destination)]
            assert sealer.main() == 0
            assert calls.count("a-stable") == 1
            assert calls.count("z-changing") == 2
            assert (retry_destination / "a-stable").read_text() == "stable"
            assert (retry_destination / "z-changing").read_text() == "second"
            saved_manifest = retry_destination.with_name(retry_destination.name + ".manifest.json")
            import json
            assert json.loads(saved_manifest.read_text()) == sealer._manifest(retry_source)

            resume_source = root / "resume-source"
            resume_source.mkdir()
            (resume_source / "a-stable").write_text("stable across interruption")
            (resume_source / "z-blocked").write_text("finish later")
            resume_destination = root / "resume-sealed"
            calls = []

            def interrupt_after_stable(source, relative, destination, expected):
                calls.append(relative)
                if relative == "z-blocked":
                    raise OSError("synthetic interruption")
                real_clone(source, relative, destination, expected)

            sealer._clone_file = interrupt_after_stable
            sys.argv = ["seal", str(resume_source), str(resume_destination)]
            assert sealer.main() == 1
            resume_manifest = resume_destination.with_name(
                resume_destination.name + ".manifest.json"
            )
            assert not resume_manifest.exists()
            assert calls.count("a-stable") == 1
            try:
                os.getxattr(resume_destination / "a-stable", sealer.SOURCE_RECORD_XATTR)
                checkpoint_supported = True
            except OSError as error:
                assert error.errno == sealer.errno.EOPNOTSUPP
                checkpoint_supported = False
            calls.clear()

            def trace_clone(source, relative, destination, expected):
                calls.append(relative)
                real_clone(source, relative, destination, expected)

            sealer._clone_file = trace_clone
            assert sealer.main() == 0
            assert calls == (["z-blocked"] if checkpoint_supported else ["a-stable", "z-blocked"])
            assert json.loads(resume_manifest.read_text()) == sealer._manifest(resume_source)
            for item in resume_source.iterdir():
                assert (resume_destination / item.name).read_bytes() == item.read_bytes()

            # Invalid checkpoints and changed sources must be recloned.
            if checkpoint_supported:
                os.setxattr(resume_destination / "a-stable", sealer.SOURCE_RECORD_XATTR, b"invalid")
            (resume_source / "z-blocked").write_text("source changed")
            resume_manifest.unlink()
            calls.clear()
            assert sealer.main() == 0
            assert calls == ["a-stable", "z-blocked"]
            for item in resume_source.iterdir():
                assert (resume_destination / item.name).read_bytes() == item.read_bytes()

            # A failed file barrier must not publish a reusable clone or manifest.
            barrier_source = root / "barrier-source"
            barrier_source.mkdir()
            (barrier_source / "event").write_text("durable event")
            barrier_destination = root / "barrier-sealed"
            real_fsync = os.fsync
            import stat

            def reject_file_barrier(fd):
                if stat.S_ISREG(os.fstat(fd).st_mode):
                    raise OSError(sealer.errno.EIO, "synthetic durability failure")
                real_fsync(fd)

            sealer._clone_file = real_clone
            os.fsync = reject_file_barrier
            sys.argv = ["seal", str(barrier_source), str(barrier_destination)]
            assert sealer.main() == 1
            assert not (barrier_destination / "event").exists()
            assert not barrier_destination.with_name(barrier_destination.name + ".manifest.json").exists()
            os.fsync = real_fsync
            assert sealer.main() == 0
            assert (barrier_destination / "event").read_bytes() == (barrier_source / "event").read_bytes()

            manifest_probe = root / "manifest-probe.json"
            barriers = []

            def record_manifest_barriers(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode):
                    assert manifest_probe.exists()
                    barriers.append("directory")
                else:
                    assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o600
                    barriers.append("file")
                real_fsync(fd)

            os.fsync = record_manifest_barriers
            sealer._write_manifest(manifest_probe, {"verified": {"kind": "file"}})
            os.fsync = real_fsync
            assert barriers == ["file", "directory"]
            PY
            cmp "$TMPDIR/sealed/realm/state/polylogue/hooks/carriers/codex/2026-09-27/4242.ndjson" \
              <(printf '%s\n' '{"event":"captured"}' '{"event":"appended-after-seal"}')
            touch "$out"
          '';
      metadataImageRuntime =
        let
          unit = backupRuntimeEval.config.systemd.services.btrfs-metadata-image-backup;
          script =
            builtins.replaceStrings
              [ "/outer-realm/backup/btrfs-images" "sleep \"$delay\"" "install -d -m 0700 -o root -g root" ]
              [ "$TMPDIR/images" "sleep 0" "install -d -m 0700" ]
              unit.script;
        in
        assert lib.assertMsg (
          unit.serviceConfig.TimeoutStartSec == "85min"
          && unit.serviceConfig.MemoryHigh == "3G"
          && unit.serviceConfig.MemoryMax == "5G"
          && unit.serviceConfig.MemorySwapMax == 0
          && unit.serviceConfig.Slice == "borgdrain.slice"
          && lib.hasInfix "deadline=$(( $(date +%s) + 40 * 60 ))" script
          && lib.hasInfix "timeout --signal=TERM --kill-after=15s" script
        ) "Metadata image capture must bound each label and memory pressure";
        pkgs.runCommand "backup-metadata-image-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
            ];
          }
          ''
            mkdir -p "$TMPDIR/mock-bin" "$TMPDIR/images"
            cat > "$TMPDIR/mock-bin/btrfs-image" <<'EOF_IMAGE'
            #!${pkgs.bash}/bin/bash
            set -eu
            device="$5"
            output="$6"
            printf '%s\n' "$device" >> "$IMAGE_CALLS"
            if [ -f "$FAIL_PERSIST" ] && [[ "$device" == *f4782d9f* ]]; then
              if [ -f "$HANG_PERSIST" ]; then sleep 10; fi
              exit 1
            fi
            printf 'image for %s\n' "$device" > "$output"
            truncate -s 70M "$output"
            EOF_IMAGE
            chmod +x "$TMPDIR/mock-bin/btrfs-image"
            export PATH="$TMPDIR/mock-bin:$PATH"
            export IMAGE_CALLS="$TMPDIR/calls" FAIL_PERSIST="$TMPDIR/fail-persist" HANG_PERSIST="$TMPDIR/hang-persist"
            bash ${pkgs.writeText "metadata-image-script" script} > "$TMPDIR/success.log" 2>&1
            test "$(find "$TMPDIR/images" -name '*.btrfs-image' | wc -l)" -eq 2
            grep -q 'persist captured' "$TMPDIR/success.log"
            grep -q 'realm captured' "$TMPDIR/success.log"
            test "$(wc -l < "$IMAGE_CALLS")" -eq 2
            persist_image=$(find "$TMPDIR/images" -name 'persist-*.btrfs-image' -print -quit)
            previous_size=$(stat -c %s "$persist_image")
            previous_header=$(head -c 64 "$persist_image")
            touch "$FAIL_PERSIST"
            if bash ${pkgs.writeText "metadata-image-script" script} > "$TMPDIR/failure.log" 2>&1; then
              echo 'persist failure unexpectedly succeeded' >&2
              exit 1
            fi
            grep -q 'persist failed after 3 attempts' "$TMPDIR/failure.log"
            grep -q 'realm captured' "$TMPDIR/failure.log"
            test "$(stat -c %s "$persist_image")" -eq "$previous_size"
            test "$(head -c 64 "$persist_image")" = "$previous_header"
            test "$(wc -l < "$IMAGE_CALLS")" -eq 6
            touch "$HANG_PERSIST"
            if bash ${
              pkgs.writeText "metadata-image-timeout-script" (
                builtins.replaceStrings [ "40 * 60" ] [ "2" ] script
              )
            } > "$TMPDIR/timeout.log" 2>&1; then
              echo 'timed-out persist capture unexpectedly succeeded' >&2
              exit 1
            fi
            grep -q 'persist attempt 1 exited 124' "$TMPDIR/timeout.log"
            grep -q 'realm captured' "$TMPDIR/timeout.log"
            test "$(stat -c %s "$persist_image")" -eq "$previous_size"
            test "$(head -c 64 "$persist_image")" = "$previous_header"
            touch "$out"
          '';
    in
    {
      checks = {
        backup-borg-hook-runtime = backupBorgHookRuntime;
        backup-health-lanes-runtime = borgHealthLanesRuntime;
        backup-polylogue-hook-seal = polylogueHookSealRuntime;
        backup-metadata-image-runtime = metadataImageRuntime;
        backup-headless-default =
          assert headlessBackupUnits == [ ];
          pkgs.runCommand "backup-headless-default-check" { } ''
            touch "$out"
          '';
      };
    };
}
