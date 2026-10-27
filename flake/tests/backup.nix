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
            sinnix.backup.genomeRoot = "/neo-outer-realm/content/genome";
            sinnix.services = {
              "machine-telemetry".enable = true;
              polylogue.enable = true;
            };
            services.sinex = {
              enable = true;
              storeDir = "/var/lib/sinex/daemon/store";
              nats.daemonPasswordFile = "/run/agenix/sinex-nats-daemon";
            };
            sinnix.services.polylogue.dataDir = "/tmp/sentinel-polylogue-root";
          })
        ];
        assertions = config: [
          {
            assertion =
              let
                unit = config.systemd.services.machine-telemetry-seal;
              in
              !unit.restartIfChanged && unit.serviceConfig.TimeoutStartSec == "infinity";
            message = "Telemetry sealing must not restart on activation, and each sealed file's one structural check must run to completion.";
          }
          {
            assertion = lib.hasInfix config.services.sinex.storeDir config.systemd.services.borgbackup-job-sinex-blobs.script;
            message = "The sinex-blobs Borg job must archive the evaluated content store";
          }
          {
            # Every backup job's freshness marker is watched by the sentinel
            # through its capture lane. The lane's path and the path actually
            # written have to be the same file, or the health sweep reports a backup
            # as fresh while nothing produces the marker (and the reverse: a
            # marker nobody watches). The writer is the unit's own script plus
            # the sources of the packaged scripts that unit invokes -- the
            # check receipt, for one, is written by scripts/sinnix-borg-check
            # rather than inline. Both sides come from the evaluated config,
            # so neither is a restated literal.
            assertion =
              let
                packagedScriptNames = builtins.attrNames (builtins.readDir ../../scripts);
                writerText =
                  name:
                  let
                    service = config.systemd.services.${name};
                    script = (service.script or "") + (service.serviceConfig.ExecStart or "");
                    invoked = lib.filter (scriptName: lib.hasInfix "/bin/${scriptName}" script) packagedScriptNames;
                  in
                  script
                  + lib.concatMapStrings (scriptName: builtins.readFile (../../scripts + "/${scriptName}")) invoked;
                jobs = lib.filterAttrs (
                  name: surface: lib.hasPrefix "borgbackup-" name && surface.captures != [ ]
                ) config.sinnix.runtime.units;
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
            ) (lib.attrValues config.sinnix.runtime.units);
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
            };
            services.sinex = {
              enable = true;
              storeDir = "/var/lib/sinex/daemon/store";
              nats.daemonPasswordFile = "/run/agenix/sinex-nats-daemon";
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
        assert lib.assertMsg
          (
            lib.hasInfix "with_borg_lock" script
            && lib.hasInfix "cut-polylogue-hooks.py" script
            && lib.hasInfix "-- borg create" script
          )
          "Polylogue state must hold its verified native cut through Borg completion under the repository lock";
        assert lib.assertMsg (lib.hasInfix "state/cache/polylogue-backup-hooks" script)
          "Polylogue state Borg job must use its stable private cut storage";
        assert lib.assertMsg (lib.hasInfix "install -d -m 0700 -o root -g root" script)
          "Polylogue state cut storage must be private to root";
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
              from = "/neo-outer-realm/.btrfs/genome-snapshots";
              to = "$TMPDIR/genome-snapshots";
            }
            {
              from = "/realm/.btrfs/snapshot";
              to = "$TMPDIR/realm-snapshots";
            }
            {
              from = "/persist/.btrfs/snapshot";
              to = "$TMPDIR/persist-snapshots";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/state/borg-drain";
            }
            {
              from = "systemctl stop";
              to = "$TMPDIR/mock-bin/systemctl stop";
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
      genomeBorgDrainScript = rewriteBackupHook (realmBorgDrainScriptFor "borgbackup-job-genome") [
        {
          from = "/neo-outer-realm/.btrfs/genome-snapshots";
          to = "$TMPDIR/genome-snapshots";
        }
        {
          from = "/run/borgbackup-snapshot-inputs/genome";
          to = "$TMPDIR/bind/genome";
        }
        {
          from = "run/borgbackup-snapshot-inputs/genome";
          to = "$TMPDIR/bind/genome";
        }
      ];
      localDumpsScript = rewriteBackupHook (realmBorgDrainScriptFor "borgbackup-local-dumps") [
        {
          from = "/realm/state/db-dumps";
          to = "$TMPDIR/live-dumps";
        }
      ];
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
              from = "/var/lib/sinex/daemon/store";
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

      sinexBeadsCheckScript =
        assert lib.assertMsg
          (lib.hasInfix "authority/sinex/.beads" customAuthorityEval.config.systemd.services.sinnix-borg-beads-check.script)
          "The Beads restore check must follow a configured Sinex task authority outside state/tasks";
        rewriteBackupHook backupRuntimeEval.config.systemd.services.sinnix-borg-beads-check.script [
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
              checkScript = builtins.readFile ../../scripts/sinnix-borg-check;
              audit = backupRuntimeEval.config.systemd.services.borgbackup-coverage-audit-realm;
              auditTimer = backupRuntimeEval.config.systemd.timers.borgbackup-coverage-audit-realm;
            in
            verify.description == "Borg repository integrity checks with bounded partial passes"
            && verify.serviceConfig.TimeoutStartSec == "4h30m"
            && timer.timerConfig.OnCalendar == "Sun 13:00:00"
            && lib.hasInfix "--max-duration 1800 file:///outer-realm/backup/borg-persist-v1" script
            && lib.hasInfix "--max-duration 7200 file:///outer-realm/backup/borg-realm-v2" script
            && lib.hasInfix "--max-duration 1800 file:///outer-realm/backup/borg-sinex-blobs-v1" script
            && lib.hasInfix "/bin/sinnix-borg-check\n" script
            && lib.hasInfix "MAX_DURATION=1800" checkScript
            && lib.hasInfix "VERIFY_DATA=0" checkScript
            && lib.hasInfix "file:///outer-realm/backup/borg-persist-v1" checkScript
            && lib.hasInfix "file:///outer-realm/backup/borg-realm-v2" checkScript
            && lib.hasInfix "borg check --repository-only --max-duration \"$MAX_DURATION\" \"$repo\"" checkScript
            && audit.serviceConfig.TimeoutStartSec == "2h"
            && auditTimer.timerConfig.OnCalendar == "*-*-* *:35:00"
            && lib.hasInfix "status=deferred reason=borg-lock-contention remains_due=true" audit.script
            && lib.hasInfix "flock -n -s 8" audit.script
            && lib.hasInfix "exec 9>&-" audit.script
            && lib.hasInfix "--mode sampled --sample-bytes 1073741824 --sample-files 128" audit.script
            && lib.hasInfix "flock -n -x 8" realmBorgDrainScript
          )
          "Weekly Borg verification must keep its CRC budgets and partial-check semantics while ending before the next archive window";
        assert lib.assertMsg (lib.all
          (name: backupRuntimeEval.config.systemd.services.${name}.serviceConfig.TimeoutStartSec == "4h")
          [
            "borgbackup-job-persist"
            "borgbackup-root-snapshots"
          ]
        ) "Snapshot backlog drains must have a finite per-wake deadline";
        assert lib.assertMsg (
          backupRuntimeEval.config.systemd.services.borgbackup-drain-coordinator.serviceConfig.TimeoutStartSec
          == "52h15m"
          &&
            backupRuntimeEval.config.systemd.services.borgbackup-job-realm.serviceConfig.TimeoutStartSec
            == "24h"
          &&
            backupRuntimeEval.config.systemd.services.borgbackup-drain-coordinator.unitConfig.PropagatesStopTo
            == [
              "borgbackup-job-persist.service"
              "borgbackup-job-realm.service"
              "borgbackup-job-genome.service"
            ]
          && !(lib.hasInfix "stop borgbackup-verify.service borgbackup-coverage-audit-realm.service" backupRuntimeEval.config.systemd.services.borgbackup-drain-coordinator.script)
          && !(builtins.hasAttr "borgbackup-job-persist" backupRuntimeEval.config.systemd.timers)
          && !(builtins.hasAttr "borgbackup-job-realm" backupRuntimeEval.config.systemd.timers)
          && !(builtins.hasAttr "borgbackup-job-genome" backupRuntimeEval.config.systemd.timers)
          && builtins.hasAttr "borgbackup-drain-coordinator" backupRuntimeEval.config.systemd.timers
          &&
            backupRuntimeEval.config.systemd.timers.borgbackup-drain-coordinator.timerConfig.OnCalendar
            == "*-*-* 03:05,03:25:00"
          && backupRuntimeEval.config.systemd.timers.btrbk.timerConfig.OnCalendar == "*-*-* 00,06,12,18:00:00"
          &&
            backupRuntimeEval.config.systemd.services.borgbackup-job-realm.serviceConfig.Slice
            == "borgdrain.slice"
          && backupRuntimeEval.config.systemd.services.borgbackup-job-realm.serviceConfig.MemoryHigh == "6G"
          && backupRuntimeEval.config.systemd.services.borgbackup-job-realm.serviceConfig.MemoryMax == "6G"
          && backupRuntimeEval.config.systemd.slices.borgdrain.sliceConfig.MemoryHigh == "6G"
          && backupRuntimeEval.config.systemd.slices.borgdrain.sliceConfig.MemoryMax == "8G"
          &&
            builtins.length (
              builtins.filter (line: lib.hasInfix "$TMPDIR/bind/realm/state/cache" line) (
                lib.splitString "\n" realmBorgDrainScript
              )
            ) == 1
        ) "Six-hour acquisition and bounded lossless archival must have separate schedules";
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
            ${pkgs.python3}/bin/python3 ${./backup_retention.py} ${pkgs.writeText "backup-maintenance-fixture.sh" deadHolderLockScript}
            ${pkgs.python3}/bin/python3 ${./backup_capacity.py} ${../../scripts/sinnix-backup-capacity}
            ${pkgs.python3}/bin/python3 ${./backup_native_restore_test.py} ${./backup_native_restore.py}
            ${pkgs.python3}/bin/python3 ${./borg-check-arguments.py} ${../../scripts/sinnix-borg-check}
            ${pkgs.python3}/bin/python3 ${./backup_snapshot_coverage.py} \
              --verifier ${../../modules/lib/backup/snapshot-coverage.py} \
              --scripts ${
                pkgs.writeText "backup-fixture-scripts.json" (
                  builtins.toJSON {
                    realm = realmBorgDrainScript;
                    genome = genomeBorgDrainScript;
                    localDumps = localDumpsScript;
                    persist = persistBorgDrainScript;
                    coordinator = coordinatorScript;
                    missing = missingRealmBorgDrainScript;
                    sinex = sinexBlobBorgScript;
                    polylogue = polylogueStateBorgScript;
                    beads = sinexBeadsCheckScript;
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
        inherit (backupRuntimeEval.config.sinnix.runtime.units)
          borgbackup-job-persist
          borgbackup-job-realm
          borgbackup-job-sinex-blobs
          borgbackup-job-polylogue-state
          borgbackup-verify
          ;
        allSurfaceNames = builtins.attrNames backupRuntimeEval.config.sinnix.runtime.units;
      };

      borgHealthLanesRuntime = pkgs.runCommand "backup-health-lanes-check" { } ''
        cat > "$out" <<'EOF_LANES'
        ${borgHealthLanesJson}
        EOF_LANES
      '';
      polylogueHookCutRuntime =
        pkgs.runCommand "backup-polylogue-hook-cut-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.borgbackup
            ];
          }
          ''
            python3 ${./polylogue-hook-cut.py} ${../../modules/lib/backup/cut-polylogue-hooks.py}
            touch "$out"
          '';
    in
    {
      checks = {
        backup-borg-hook-runtime = backupBorgHookRuntime;
        backup-health-lanes-runtime = borgHealthLanesRuntime;
        backup-polylogue-hook-cut = polylogueHookCutRuntime;
        backup-headless-default =
          assert headlessBackupUnits == [ ];
          pkgs.runCommand "backup-headless-default-check" { } ''
            touch "$out"
          '';
      };
    };
}
