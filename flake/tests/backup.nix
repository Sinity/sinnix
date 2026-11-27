# Backup checks. Evaluations assert the units, timers, surfaces and the
# policy file /etc/sinnix/backup.json; the sinnix-backup package's pytest
# suite runs every job against real Borg with mount, btrfs and systemctl
# faked, reading the policy file this fixture host evaluates.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  defaultBeadsPath = "state/tasks/sinex-next/.beads";
  protectedPathMatches = import ../../modules/lib/backup/protected-paths.nix {
    inherit lib;
    paths = [
      defaultBeadsPath
      "${defaultBeadsPath}/metadata.json"
      "${defaultBeadsPath}/config.yaml"
      "${defaultBeadsPath}/embeddeddolt/sxnext/.dolt"
      "library/model/control-vector"
    ];
  };
  backupJson =
    evaluated: builtins.fromJSON evaluated.config.environment.etc."sinnix/backup.json".text;
  # Every unit modules/lib/backup/units.nix declares.
  backupJobNames = [
    "btrbk"
    "borgbackup-job-persist"
    "borgbackup-job-realm"
    "borgbackup-job-genome"
    "borgbackup-drain-coordinator"
    "borgbackup-root-snapshots"
    "borgbackup-job-sinex-blobs"
    "polylogue-sqlite-backup"
    "borgbackup-job-polylogue-state"
    "borgbackup-job-persist-hourly"
    "borgbackup-job-live-small"
    "borgbackup-maintenance"
    "borgbackup-retention-plan"
    "borgbackup-capacity"
    "borgbackup-local-dumps"
    "borgbackup-verify"
    "borgbackup-coverage-audit-realm"
    "sinnix-borg-beads-check"
  ];
  packageDirectory = ../../pkgs/sinnix-backup/sinnix_backup;
  packageText = lib.concatMapStrings (name: builtins.readFile (packageDirectory + "/${name}")) (
    lib.filter (lib.hasSuffix ".py") (builtins.attrNames (builtins.readDir packageDirectory))
  );
in
assert lib.assertMsg (
  lib.all protectedPathMatches [
    "state"
    "state/tasks"
    "state/tasks/sinex-next"
    defaultBeadsPath
    "${defaultBeadsPath}/embeddeddolt"
    "${defaultBeadsPath}/embeddeddolt/sxnext/.dolt"
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
    { system, sinnixScriptRegistry, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        baseTestConfig
        evalTestSpec
        mountTmpfsRoots
        mkRuntimeCheck
        ;

      # evalTestSpec throws when any of these assertions fails, whenever the
      # evaluation is used.
      backupRuntimeEval = evalTestSpec system {
        name = "backup-borg-hook-runtime";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          ../../modules/services/sinex/bridge.nix
          (_: {
            networking.hostName = "backup-runtime";
            sinnix.backup.enable = true;
            sinnix.backup.genomeRoot = "/neo-outer-realm/content/genome";
            sinnix.services = {
              "machine-telemetry".enable = true;
              polylogue.enable = true;
              sinex.enable = true;
            };
            sinnix.services.sinex.retainedStores = [ "/var/lib/sinex/retained" ];
            services.sinex = {
              enable = true;
              storeDir = "/var/lib/sinex/daemon/store";
              nats.daemonPasswordFile = "/run/agenix/sinex-nats-daemon";
            };
            sinnix.services.polylogue.dataDir = "/tmp/sentinel-polylogue-root";
          })
        ];
        assertions =
          config:
          let
            backup = builtins.fromJSON config.environment.etc."sinnix/backup.json".text;
            services = config.systemd.services;
          in
          [
            {
              assertion =
                let
                  unit = config.systemd.services.machine-telemetry-seal;
                in
                !unit.restartIfChanged && unit.serviceConfig.TimeoutStartSec == "infinity";
              message = "Telemetry sealing must not restart on activation, and each sealed file's one structural check must run to completion.";
            }
            {
              assertion =
                backup.jobs.sinex_store_paths == config.sinnix.services.sinex.retainedStores
                &&
                  services.borgbackup-job-sinex-blobs.unitConfig.RequiresMountsFor
                  == config.sinnix.services.sinex.retainedStores;
              message = "The predecessor archive job must cover every retained Sinex store";
            }
            {
              assertion =
                config.services.sinex.backup.repo != config.services.sinex.backup.keysRepo
                && config.services.sinex.backup.startAt == [ ]
                &&
                  config.systemd.services.sinex-backup.unitConfig.PropagatesStopTo == [
                    "borgbackup-job-sinex.service"
                    "borgbackup-job-sinex-keys.service"
                  ]
                && builtins.elem "sinex-backup.service" backup.nightly.archive_units
                &&
                  backup.nightly.sinex_completion
                  == "${config.services.sinex.backup.artifactDir}/latest-complete.json"
                && lib.all (name: config.systemd.services.${name}.serviceConfig.Slice == "background.slice") [
                  "sinex-backup"
                  "borgbackup-job-sinex"
                  "borgbackup-job-sinex-keys"
                ];
              message = "The nightly sequence runs the paired Sinex backup in its declared background slice.";
            }
            {
              # Each backup unit runs one sinnix-backup command; the capacity
              # job runs its own packaged script.
              assertion = lib.all (
                name:
                let
                  service = services.${name};
                in
                service.script == ""
                && (
                  name == "borgbackup-capacity" || lib.hasInfix "/bin/sinnix-backup " service.serviceConfig.ExecStart
                )
              ) backupJobNames;
              message = "Every backup unit must run a sinnix-backup command from ExecStart, with no inline script";
            }
            {
              # A capture lane's path and the file its unit writes must be the
              # same, or the health sweep watches a file nothing writes. The
              # unit writes paths named in backup.json or its ExecStart, the
              # markers sinnix-backup names in the state directory, and files
              # of the packaged scripts it runs.
              assertion =
                let
                  # builtins.match (behind lib.hasInfix) overflows the stack on
                  # text this long; a literal split does not.
                  contains = needle: text: builtins.length (builtins.split (lib.escapeRegex needle) text) > 1;
                  backupText = config.environment.etc."sinnix/backup.json".text;
                  packagedScriptNames = builtins.attrNames (
                    lib.filterAttrs (_: type: type == "regular") (builtins.readDir ../../scripts)
                  );
                  writerText =
                    name:
                    let
                      execStart = services.${name}.serviceConfig.ExecStart or "";
                      runsBackup = contains "/bin/sinnix-backup " execStart;
                      invoked = lib.filter (
                        scriptName:
                        contains "/bin/${scriptName}" execStart || (runsBackup && contains "\"${scriptName}\"" packageText)
                      ) packagedScriptNames;
                    in
                    backupText
                    + execStart
                    + lib.concatMapStrings (scriptName: builtins.readFile (../../scripts + "/${scriptName}")) invoked;
                  stateMarker =
                    path:
                    let
                      base = baseNameOf path;
                      stem = builtins.head (lib.splitString "." base);
                      kind = lib.removePrefix "${stem}." base;
                    in
                    dirOf path == backup.state_directory
                    && (
                      contains base packageText
                      || ((backup.sources ? ${stem} || contains "\"${stem}\"" packageText) && contains kind packageText)
                    );
                  jobs = lib.filterAttrs (
                    name: surface: lib.hasPrefix "borgbackup-" name && surface.captures != [ ]
                  ) config.sinnix.runtime.units;
                in
                jobs != { }
                && lib.all (
                  name:
                  lib.all (lane: contains lane.path (writerText name) || stateMarker lane.path) jobs.${name}.captures
                ) (lib.attrNames jobs);
              message = "Every Borg job's capture lane must point at a path its unit -- or a packaged script that unit runs -- actually writes";
            }
            {
              assertion =
                lib.all (name: lib.hasInfix "export BORG_HOST_ID=" config.services.borgbackup.jobs.${name}.preHook)
                  [
                    "sinex"
                    "sinex-keys"
                  ];
              message = "Both upstream Sinex Borg jobs must use the stable local host identity";
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
      minimalBackupEval = evalTestSpec system {
        name = "backup-optional-producers";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          (_: {
            sinnix.machine.isDesktop = false;
            sinnix.backup.enable = true;
            sinnix.services.machine-telemetry.enable = false;
            sinnix.services.polylogue.enable = false;
          })
        ];
        assertions = _: [ ];
      };
      archiveOffEval = evalTestSpec system {
        name = "backup-archive-off";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          inputs.sinex.nixosModules.default
          ../../modules/services/sinex/bridge.nix
          (_: {
            sinnix.backup.enable = true;
            sinnix.backup.archive.enable = false;
            sinnix.backup.genomeRoot = "/neo-outer-realm/content/genome";
            sinnix.services = {
              "machine-telemetry".enable = true;
              polylogue.enable = true;
              sinex.enable = true;
            };
            sinnix.services.sinex.retainedStores = [ "/var/lib/sinex/retained" ];
            services.sinex = {
              enable = true;
              storeDir = "/var/lib/sinex/daemon/store";
              nats.daemonPasswordFile = "/run/agenix/sinex-nats-daemon";
            };
          })
        ];
        assertions = _: [ ];
      };
      telemetryOnlyEval = evalTestSpec system {
        name = "telemetry-without-backups";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          (_: {
            sinnix.machine.isDesktop = false;
            sinnix.backup.enable = false;
            sinnix.services.machine-telemetry.enable = true;
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

      services = backupRuntimeEval.config.systemd.services;
      timers = backupRuntimeEval.config.systemd.timers;
      backup = backupJson backupRuntimeEval;
      runsCommand =
        name: command:
        lib.hasSuffix "/bin/sinnix-backup ${command}" services.${name}.serviceConfig.ExecStart;

      backupBorgHookRuntime =
        assert lib.assertMsg (
          let
            inherit (backupRuntimeEval.config.sinnix) paths runtime;
            rebuild = lib.removePrefix "${paths.realmRoot}/" "${runtime.inventory.polylogue.archiveRoot}/index-rebuild";
            coverage = backup.sources.realm.coverage;
          in
          builtins.elem rebuild coverage.noncanonical
          && builtins.elem "run/borgbackup-snapshot-inputs/realm/${rebuild}" coverage.borg_excludes
        ) "Realm backups must omit Polylogue's rebuild work files";
        assert lib.assertMsg
          (
            let
              inherit (backup.jobs) polylogue;
            in
            polylogue.state_root == "/tmp/sentinel-polylogue-root"
            && lib.all (name: builtins.elem name polylogue.state_excludes) [
              "source.db"
              "source.db-wal"
              ".salvage-internals-20261008"
            ]
            && !(lib.any (lib.hasInfix "embeddings.db.retired") polylogue.state_excludes)
            && polylogue.hook_cut_directory == "/realm/state/cache/polylogue-backup-hooks"
            && runsCommand "borgbackup-job-polylogue-state" "polylogue-state"
            && !(timers ? borgbackup-job-polylogue-state)
            && services.borgbackup-job-polylogue-state.serviceConfig.TimeoutStartSec == "90min"
          )
          "Polylogue state excludes its live databases by name, keeps retired siblings covered, cuts hooks in its private storage, and keeps its deadline inside the nightly coordinator";
        assert lib.assertMsg
          (
            let
              verify = services.borgbackup-verify;
              checkScript = builtins.readFile ../../scripts/sinnix-borg-check;
              audit = services.borgbackup-coverage-audit-realm;
            in
            verify.description == "Borg repository integrity checks with bounded partial passes"
            && verify.serviceConfig.TimeoutStartSec == "4h30m"
            && timers.borgbackup-verify.timerConfig.OnCalendar == "Sun 13:00:00"
            && runsCommand "borgbackup-verify" "check-repositories"
            &&
              lib.take 3 backup.jobs.integrity.repositories == [
                {
                  repository = "persist";
                  seconds = 1800;
                }
                {
                  repository = "realm";
                  seconds = 7200;
                }
                {
                  repository = "sinex-blobs";
                  seconds = 1800;
                }
              ]
            && lib.hasInfix "MAX_DURATION=1800" checkScript
            && lib.hasInfix "VERIFY_DATA=0" checkScript
            && lib.hasInfix "file:///outer-realm/backup/borg-persist-v1" checkScript
            && lib.hasInfix "file:///outer-realm/backup/borg-realm-v2" checkScript
            && lib.hasInfix "borg check --repository-only --max-duration \"$MAX_DURATION\" \"$repo\"" checkScript
            && audit.serviceConfig.TimeoutStartSec == "2h"
            && !(timers ? borgbackup-coverage-audit-realm)
            && runsCommand "borgbackup-coverage-audit-realm" "audit-realm"
            && backup.jobs.audit.sample_bytes == 1073741824
            && backup.jobs.audit.sample_files == 128
          )
          "Weekly Borg verification must keep its CRC budgets and partial-check semantics while ending before the next archive window";
        assert lib.assertMsg (lib.all (name: services.${name}.serviceConfig.TimeoutStartSec == "4h") [
          "borgbackup-job-persist"
          "borgbackup-root-snapshots"
        ]) "Snapshot backlog drains must have a finite per-wake deadline";
        assert lib.assertMsg (
          services.borgbackup-drain-coordinator.serviceConfig.TimeoutStartSec == "80h15m"
          && services.borgbackup-job-realm.serviceConfig.TimeoutStartSec == "24h"
          &&
            services.borgbackup-drain-coordinator.unitConfig.PropagatesStopTo == [
              "machine-telemetry-sqlite-backup.service"
              "polylogue-sqlite-backup.service"
              "btrbk.service"
              "borgbackup-job-polylogue-state.service"
              "borgbackup-job-sinex-blobs.service"
              "borgbackup-job-realm.service"
              "borgbackup-job-genome.service"
              "borgbackup-job-persist.service"
              "sinex-backup.service"
              "borgbackup-root-snapshots.service"
              "borgbackup-maintenance.service"
              "borgbackup-coverage-audit-realm.service"
              "borgbackup-local-dumps.service"
            ]
          && lib.all (name: !(builtins.hasAttr name timers)) [
            "polylogue-sqlite-backup"
            "borgbackup-root-snapshots"
            "borgbackup-job-polylogue-state"
            "borgbackup-job-sinex-blobs"
            "borgbackup-maintenance"
            "borgbackup-local-dumps"
            "borgbackup-job-persist"
            "borgbackup-job-realm"
            "borgbackup-job-genome"
          ]
          && !timers.machine-telemetry-sqlite-backup.enable
          && !(backupRuntimeEval.config.sinnix.runtime.units ? machine-telemetry-sqlite-backup-timer)
          && !(backupRuntimeEval.config.sinnix.runtime.units ? polylogue-sqlite-backup-timer)
          # The coordinator stops only the resumable integrity check for drain work.
          && backup.nightly.verify_unit == "borgbackup-verify.service"
          && runsCommand "borgbackup-drain-coordinator" "nightly"
          && timers.borgbackup-drain-coordinator.timerConfig.OnCalendar == "*-*-* 03:05:00"
          && timers.borgbackup-drain-coordinator.timerConfig.OnBootSec == "45min"
          && timers.btrbk.timerConfig.OnCalendar == "*-*-* 00,06,12,18:00:00"
          && services.borgbackup-job-realm.serviceConfig.Slice == "borgdrain.slice"
          && services.borgbackup-job-realm.serviceConfig.MemoryHigh == "6G"
          && services.borgbackup-job-realm.serviceConfig.MemoryMax == "6G"
          && backupRuntimeEval.config.systemd.slices.borgdrain.sliceConfig.MemoryHigh == "6G"
          && services.borgbackup-job-realm.serviceConfig.MemorySwapMax == 0
          && services.borgbackup-job-persist.serviceConfig.Slice == "borgdrain.slice"
          && services.borgbackup-job-genome.serviceConfig.MemorySwapMax == 0
          &&
            lib.all
              (
                name:
                lib.any (lib.hasInfix "sinnix-backup-admission wait") services.${name}.serviceConfig.ExecStartPre
              )
              [
                "borgbackup-job-realm"
                "borgbackup-job-persist"
                "borgbackup-job-genome"
              ]
          && lib.hasInfix "sinnix-backup-admission yield" services.borgbackup-drain-admission.serviceConfig.ExecStart
          && timers.borgbackup-drain-admission.timerConfig.OnCalendar == "*:*:0/30"
          && timers.borgbackup-drain-admission.timerConfig.AccuracySec == "1s"
          && backupRuntimeEval.config.systemd.slices.borgdrain.sliceConfig.MemoryMax == "6G"
          && backupRuntimeEval.config.systemd.slices.borgdrain.sliceConfig.MemorySwapMax == 0
          &&
            lib.count (
              pattern: pattern == "run/borgbackup-snapshot-inputs/realm/state/cache"
            ) backup.sources.realm.coverage.borg_excludes == 1
        ) "Six-hour acquisition and bounded lossless archival must have separate schedules";
        assert lib.assertMsg (
          let
            children =
              minimalBackupEval.config.systemd.services.borgbackup-drain-coordinator.unitConfig.PropagatesStopTo;
          in
          lib.all (name: !(builtins.elem name children)) [
            "polylogue-sqlite-backup.service"
            "borgbackup-job-polylogue-state.service"
            "machine-telemetry-sqlite-backup.service"
            "borgbackup-job-sinex-blobs.service"
            "borgbackup-job-genome.service"
          ]
          && telemetryOnlyEval.config.systemd.timers.machine-telemetry-sqlite-backup.enable
          && telemetryOnlyEval.config.sinnix.runtime.units ? machine-telemetry-sqlite-backup-timer
        ) "Optional or disabled producer jobs must not become dangling coordinator calls";
        assert lib.assertMsg
          (
            let
              inherit (archiveOffEval) config;
              enabledTimers = lib.attrNames (lib.filterAttrs (_: timer: timer.enable) config.systemd.timers);
              borgSurfaces = lib.filterAttrs (
                name: _: lib.hasPrefix "borgbackup-" name || name == "sinnix-borg-beads-check"
              ) config.sinnix.runtime.units;
            in
            !(lib.any (
              name:
              name != "borgbackup-drain-admission"
              && (lib.hasInfix "borg" name || lib.hasPrefix "sinex-backup" name)
            ) enabledTimers)
            && config.systemd.timers.borgbackup-drain-admission.enable
            && config.systemd.timers.btrbk.timerConfig.OnCalendar == "*-*-* 00,06,12,18:00:00"
            && lib.all (name: config.systemd.services ? ${name}) backupJobNames
            && lib.all (surface: surface.captures == [ ]) (lib.attrValues borgSurfaces)
            && config.sinnix.runtime.units.btrbk.captures != [ ]
          )
          "With archive backups off, backup jobs stay defined with no archival timer or freshness lane; btrbk and drain admission keep their schedules";
        assert lib.assertMsg
          (
            let
              units = backupRuntimeEval.config.sinnix.runtime.units;
              probe = name: (builtins.head units.${name}.captures).livenessProbe.command;
              rules = backupRuntimeEval.config.systemd.tmpfiles.rules;
            in
            services.borgbackup-job-sinex-blobs.serviceConfig.TimeoutStartSec == "6h"
            && lib.hasSuffix "/bin/sinnix-backup freshness realm" (probe "borgbackup-job-realm")
            && lib.hasSuffix "/bin/sinnix-backup freshness persist" (probe "borgbackup-job-persist")
            && backup.jobs.freshness_seconds == 108000
            && lib.hasSuffix "/bin/sinnix-backup acquisition-freshness" (probe "borgbackup-job-genome")
            && lib.hasSuffix "/bin/sinnix-backup audit-status" (probe "borgbackup-coverage-audit-realm")
            && backup.jobs.genome.source == "/neo-outer-realm/content/genome"
            && backup.jobs.genome.max_observation_age_seconds == 64800
            && backup.jobs.genome.producer_unit == "btrbk.service"
            && runsCommand "btrbk" "take-snapshots"
            && builtins.elem "d /persist/root/.cache/borg-drain 0750 root users -" rules
            &&
              lib.all
                (
                  name:
                  builtins.elem "d /persist/root/.cache/borg-drain/${name}.latest-archived.by-snapshot 0750 root users -" rules
                )
                [
                  "realm"
                  "persist"
                  "genome"
                ]
            && builtins.elem "d /realm/state/cache/borg 0700 root root -" rules
          )
          "Operator probes must read receipts with nightly/change-aware budgets while credentials stay private";
        assert lib.assertMsg (
          let
            stores = (backupJson customAuthorityEval).jobs.beads.stores;
          in
          lib.any (store: store.path == "authority/sinex/.beads") stores
        ) "The Beads restore check must follow a configured task authority outside state/tasks";
        assert lib.assertMsg (
          let
            serviceSurfaces =
              evaluated:
              let
                index = builtins.fromJSON evaluated.config.environment.etc."sinnix/capability-index.json".text;
                service = builtins.head (
                  builtins.filter (row: row.kind == "service" && row.name == "machine-telemetry") index.rows
                );
              in
              map (surface: surface.name) service.surfaces;
            backupSurfaces = serviceSurfaces backupRuntimeEval;
            telemetrySurfaces = serviceSurfaces telemetryOnlyEval;
          in
          builtins.elem "machine-telemetry-sqlite-backup" backupSurfaces
          && !(builtins.elem "machine-telemetry-sqlite-backup-timer" backupSurfaces)
          && builtins.elem "machine-telemetry-sqlite-backup-timer" telemetrySurfaces
        ) "Capability index must export effective producer units and omit disabled standalone timers";
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
            ${pkgs.python3}/bin/python3 ${./backup_capacity.py} ${../../scripts/sinnix-backup-capacity}
            ${pkgs.python3}/bin/python3 ${./backup_native_restore_test.py} ${./backup_native_restore.py}
            ${pkgs.python3}/bin/python3 ${./borg-check-arguments.py} ${../../scripts/sinnix-borg-check}
          '';
        };

      # The freshness/liveness questions the retired borgbackup-status script
      # asked are capture lanes and livenessProbes on the surfaces that own
      # the marker files (see modules/backup.nix). The backupRuntimeEval
      # assertions check them -- each lane must point at a path its own unit
      # writes, and each probe must be runnable. This derivation forces that
      # evaluation and publishes the lanes it checked.
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
      # The evaluated policy file of the fixture host above. Package tests
      # relocate its absolute paths into a scratch tree, so they run against
      # the schema and values production reads.
      backupFixtureConfig =
        pkgs.writeText "backup-fixture-config.json"
          backupRuntimeEval.config.environment.etc."sinnix/backup.json".text;
      # pytest over the package's tests (all of them, or the files named).
      mkBackupSuite =
        name: testPaths:
        pkgs.runCommand name
          {
            nativeBuildInputs = [
              (pkgs.python3.withPackages (ps: [
                ps.pytest
                sinnixScriptRegistry.packageSet.sinnix-backup
              ]))
              pkgs.acl
              pkgs.bash
              pkgs.borgbackup
              pkgs.coreutils
              pkgs.util-linux
              sinnixScriptRegistry.packageSet.sinnix-borg-check
              sinnixScriptRegistry.packageSet.sinnix-borg-expire
              sinnixScriptRegistry.packageSet.sinnix-borg-prune-dumps
            ];
            SINNIX_BACKUP_FIXTURE_CONFIG = backupFixtureConfig;
            TZ = "UTC";
            passthru.fixtureConfig = backupFixtureConfig;
          }
          ''
            cp -r ${../../pkgs/sinnix-backup/tests} tests
            chmod -R u+w tests
            python3 -m pytest -q --durations=15 ${testPaths}
            touch "$out"
          '';
    in
    {
      checks = {
        backup-suite = mkBackupSuite "sinnix-backup-suite" "tests";
        backup-genome-files-cache =
          assert backup.sources.genome.files_cache_suffix == "genome";
          assert backup.sources.realm.files_cache_suffix == null;
          mkBackupSuite "backup-genome-files-cache-check" "tests/test_files_cache.py";
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
