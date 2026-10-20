# machine-telemetry: canonical host sensor and pressure capture
#
# Sinnix owns capture mechanics; Lynchpin owns interpretation. This service
# writes active and sealed SQLite files under /realm/state/machine-telemetry,
# with the host manifest in the machine home. Lynchpin reads the declared
# source files and owns promotion into its substrate.
# Captures CPU RAPL package/core watts, thermal state, PSI, service placement,
# scheduler latency samples, and periodic network-link probes.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  inherit (config.sinnix.paths) realmRoot;
  hostName = config.networking.hostName;
  systemRevision = config.system.configurationRevision;
  dataRoot = config.sinnix.paths.machineRoot;
  dataDir = dataRoot;
  dbRoot = "${realmRoot}/state/machine-telemetry";
  dbPath = "${dbRoot}/telemetry.sqlite";
  # Lives on /realm, not /persist (worn MX500); still inside the /realm
  # btrbk→borg coverage.
  backupRoot = "/realm/state/db-dumps/machine-telemetry";
  backupSnapshotRoot = "${realmRoot}/state/machine-telemetry-backup-snapshots";
  # The daily backup copies only the active file, which weekly sealing keeps
  # small, and checks its header; sealed files get one full check each.
  backupTimeoutMinutes = 40;
  manifestPath = "${dataDir}/manifest.json";
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  machineTelemetry = scriptPkgs.machine-telemetry;
in
mkServiceModule {
  name = "machine-telemetry";
  defaultOnDesktop = true;
  description = "Canonical host machine telemetry capture for Lynchpin analysis";
  surface = {
    unit = "machine-telemetry.service";
    resourceClass = "critical";
    notifyOnFailure = true;
    operatorRestart = true;
    captures = [
      {
        name = "machine-telemetry";
        path = dataRoot;
        # The collector's sampling interval (SAMPLE_INTERVAL_SEC).
        cadenceSeconds = 10;
      }
    ];
  };
  extraOptions = {
    extraMonitoredCgroups = lib.mkOption {
      type = lib.types.listOf (
        lib.types.submodule {
          options = {
            label = lib.mkOption {
              type = lib.types.str;
              description = "Stable label for this cgroup memory sample.";
            };
            scope = lib.mkOption {
              type = lib.types.enum [
                "system"
                "user"
              ];
              description = "Whether the cgroup is under the system or user manager tree.";
            };
            path = lib.mkOption {
              type = lib.types.str;
              description = "Absolute cgroup-v2 path below /sys/fs/cgroup.";
            };
          };
        }
      );
      default = [ ];
      description = "Additional aggregate cgroups and slices sampled for memory-capacity/admission analysis.";
    };
  };
  configFn =
    {
      cfg,
      pkgs,
      config,
      lib,
      ...
    }:
    let
      surfaceUnitIdentities = map (
        surface: "${surface.manager}:${surface.unit}"
      ) config.sinnix.runtime.inventory.observedServices;
      unitArgs = lib.concatStringsSep "," (lib.unique surfaceUnitIdentities);
      userUid = "1000";
      userSliceRoot = "/user.slice/user-${userUid}.slice/user@${userUid}.service";
      # Slice names encode hierarchy: "agentctl-pytest.slice" is a child of
      # "agentctl.slice". Derive the pool paths from the declared slice
      # registry rather than keeping a second copy of the pool list here --
      # the pools whose MemoryHigh gates test parallelism were invisible for
      # exactly as long as that list was maintained by hand.
      userSliceCgroupPath =
        name:
        "${userSliceRoot}/${
          lib.concatStringsSep "/" (
            lib.imap1 (
              index: _: "${lib.concatStringsSep "-" (lib.take index (lib.splitString "-" name))}.slice"
            ) (lib.splitString "-" name)
          )
        }";
      agentctlPoolSliceNames = lib.filter (name: lib.hasPrefix "agentctl-" name) (
        lib.attrNames config.sinnix.runtime.inventory.slices.user
      );
      agentctlPoolCgroups = map (name: {
        label = "user.agentctl-pool-${lib.removePrefix "agentctl-" name}";
        scope = "user";
        path = userSliceCgroupPath name;
      }) agentctlPoolSliceNames;
      defaultMonitoredCgroups = [
        {
          label = "system.background";
          scope = "system";
          path = "/background.slice";
        }
        {
          label = "system.nix";
          scope = "system";
          path = "/nix.slice";
        }
        {
          label = "system.nix-build";
          scope = "system";
          path = "/nix.slice/nix-build.slice";
        }
        {
          label = "user.agent";
          scope = "user";
          path = "${userSliceRoot}/agent.slice";
        }
        {
          label = "user.agenttool";
          scope = "user";
          path = "${userSliceRoot}/agenttool.slice";
        }
        # Historical label: this samples the job plane ROOT (agentctl.slice),
        # not the agentctl-work.slice nested inside it. The name predates the
        # inner slice and is kept so the existing series stays comparable; the
        # per-pool children arrive below as user.agentctl-pool-<pool>.
        {
          label = "user.agentctl-work";
          scope = "user";
          path = "${userSliceRoot}/agentctl.slice";
        }
        {
          label = "user.background";
          scope = "user";
          path = "${userSliceRoot}/background.slice";
        }
        {
          label = "user.nix-build";
          scope = "user";
          path = "${userSliceRoot}/nix-build.slice";
        }
        {
          label = "user.backup";
          scope = "user";
          path = "${userSliceRoot}/backup.slice";
        }
        # The desktop-side slices the job plane's MemoryHigh is sized
        # against. Their MemoryLow reservations rest on a one-off 2026-09-02
        # reading; without a series there is no way to tell whether the
        # reservation is still the right size.
        {
          label = "user.app";
          scope = "user";
          path = "${userSliceRoot}/app.slice";
        }
        {
          label = "user.session";
          scope = "user";
          path = "${userSliceRoot}/session.slice";
        }
        {
          label = "user.desktop";
          scope = "user";
          path = "${userSliceRoot}/desktop.slice";
        }
        {
          label = "user.desktop-shell";
          scope = "user";
          path = "${userSliceRoot}/desktop.slice/desktop-shell.slice";
        }
      ]
      ++ agentctlPoolCgroups;
      cgroupSpecs = defaultMonitoredCgroups ++ cfg.extraMonitoredCgroups;
      cgroupArgs = lib.concatStringsSep "," (
        map (item: "${item.label}|${item.scope}|${item.path}") cgroupSpecs
      );
    in
    lib.mkMerge [
      # Weekly: seal the active file so it stays small, then archive and
      # structurally check each sealed file once. Sealed files never change,
      # so neither step repeats and neither needs a deadline.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "machine-telemetry-seal";
          description = "Seal the active telemetry file; archive and check sealed files once";
          surface = config.sinnix.runtime.units.machine-telemetry-seal;
        }
        {
          script = ''
            set -euo pipefail
            umask 077
            exec 9>>${lib.escapeShellArg "${dbRoot}/.maintenance.lock"}
            flock -n 9 || { echo "telemetry maintenance is already active" >&2; exit 75; }
            writer_was_active=0
            resume_writer() {
              if [ "$writer_was_active" -eq 1 ]; then
                writer_was_active=0
                systemctl start machine-telemetry.service
              fi
            }
            trap resume_writer EXIT
            trap 'exit 143' INT TERM
            if systemctl is-active --quiet machine-telemetry.service; then
              writer_was_active=1
              systemctl stop machine-telemetry.service
            fi
            machine-telemetry-segments seal --db ${lib.escapeShellArg dbPath}
            resume_writer
            flock -u 9
            machine-telemetry-segments archive --db ${lib.escapeShellArg dbPath} --output ${lib.escapeShellArg backupRoot}
            machine-telemetry-segments verify --db ${lib.escapeShellArg dbPath} --records ${lib.escapeShellArg "${backupRoot}/verified"}
            chown -R ${lib.escapeShellArg username}:users ${lib.escapeShellArg "${backupRoot}/verified"}
          '';
          path = [
            pkgs.coreutils
            pkgs.e2fsprogs
            pkgs.util-linux
            machineTelemetry
            scriptPkgs.sinnix-sqlite-backup
          ];
          # chattr +i on the sealed file needs root.
          user = "root";
          serviceConfig = {
            Group = "users";
            TimeoutStartSec = "infinity";
          };
          unit = {
            requires = [ "realm.mount" ];
            after = [ "realm.mount" ];
            unitConfig.RequiresMountsFor = [
              dbRoot
              backupRoot
            ];
            restartIfChanged = false;
          };
          timer = {
            onCalendar = "Sun *-*-* 04:30:00";
            randomizedDelaySec = "30min";
            persistent = true;
          };
        }
      )
      # Second unit pair (documented structural exception): the primary
      # surface above is machine-telemetry.service itself, so the sqlite
      # backup oneshot+timer gets a direct mkScheduledJob call rather than
      # mkServiceModule's single-unit `job` sugar.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "machine-telemetry-sqlite-backup";
          description = "Back up machine telemetry SQLite database";
          surface = config.sinnix.runtime.units.machine-telemetry-sqlite-backup;
        }
        {
          script = ''
            set -euo pipefail

            umask 077
            install -d -m 0700 -o ${lib.escapeShellArg username} -g users ${lib.escapeShellArg backupRoot}

            stamp="$(date -u +%Y%m%dT%H%M%SZ)"
            final=${lib.escapeShellArg backupRoot}/telemetry-"$stamp".sqlite.zst

            snapshot="${backupSnapshotRoot}/telemetry-$stamp-$INVOCATION_ID"
            snapshot_created=0
            writer_was_active=0
            resume_writer() {
              if [ "$writer_was_active" -eq 1 ]; then
                writer_was_active=0
                systemctl start machine-telemetry.service
              fi
            }
            cleanup() {
              resume_writer
              if [ "$snapshot_created" -eq 1 ]; then
                btrfs subvolume delete "$snapshot" >/dev/null
                snapshot_created=0
              fi
            }
            trap cleanup EXIT
            # A default-handled SIGTERM ends the shell without running its EXIT
            # trap, and every stamped snapshot has its own name, so the
            # subvolumes of every cancelled run would otherwise accumulate.
            trap 'cleanup; exit 143' INT TERM

            # The database is NOCOW, so cloning its file is not a reliable
            # constant-time operation. A read-only subvolume snapshot freezes
            # the checkpointed input; the helper then compresses it directly.
            exec 9>>${lib.escapeShellArg "${dbRoot}/.maintenance.lock"}
            flock -n 9 || { echo "telemetry maintenance is already active" >&2; exit 75; }
            machine-telemetry-segments check --db ${lib.escapeShellArg dbPath}
            if systemctl is-active --quiet machine-telemetry.service; then
              writer_was_active=1
              systemctl stop machine-telemetry.service
            fi
            sqlite3 ${lib.escapeShellArg dbPath} 'PRAGMA wal_checkpoint(TRUNCATE);'
            if [ -s ${lib.escapeShellArg "${dbPath}-wal"} ]; then
              echo "machine telemetry WAL remained after checkpoint" >&2
              exit 1
            fi
            btrfs subvolume snapshot -r ${lib.escapeShellArg dbRoot} "$snapshot"
            snapshot_created=1
            resume_writer
            flock -u 9
            sinnix-sqlite-backup \
              --immutable-source \
              --check-mode header \
              "$snapshot/telemetry.sqlite" "$final"
            chown ${lib.escapeShellArg username}:users "$final"

          '';
          path = [
            pkgs.coreutils
            pkgs.findutils
            pkgs.gawk
            pkgs.btrfs-progs
            pkgs.sqlite
            pkgs.util-linux
            machineTelemetry
            scriptPkgs.sinnix-sqlite-backup
          ];
          # Btrfs subvolume snapshots require CAP_SYS_ADMIN; the published
          # artifact is handed back to the operator below.
          user = "root";
          serviceConfig = {
            Group = "users";
            TimeoutStartSec = "${toString backupTimeoutMinutes}min";
          };
          unit = {
            after = [
              "realm.mount"
              "persist.mount"
            ];
            requires = [
              "realm.mount"
              "persist.mount"
            ];
            unitConfig.RequiresMountsFor = [
              dbRoot
              backupRoot
              backupSnapshotRoot
            ];
            restartIfChanged = false;
          };
          timer = {
            onCalendar = "*-*-* 03:42:00";
            randomizedDelaySec = "30min";
            persistent = false;
          };
        }
      )
      {
        systemd.tmpfiles.rules = [
          "d ${config.sinnix.paths.machinePaths.experiment} 0775 ${username} users -"
          "d ${dataDir}/legacy 0775 ${username} users -"
          # Adjust existing subvolumes without creating a plain directory before scaffold.
          "z ${dbRoot} 0700 ${username} users -"
          "d ${backupRoot} 0700 ${username} users -"
          "d ${backupSnapshotRoot} 0700 ${username} users -"
        ];

        systemd.services.machine-telemetry-db-scaffold = {
          description = "Create machine telemetry SQLite nodatacow subvolume";
          # Existing directories are repaired by tmpfiles without restarting capture.
          restartIfChanged = false;
          requiredBy = [ "machine-telemetry.service" ];
          before = [ "machine-telemetry.service" ];
          requires = [ "realm.mount" ];
          after = [ "realm.mount" ];
          path = [
            pkgs.btrfs-progs
            pkgs.coreutils
            pkgs.e2fsprogs
          ];
          serviceConfig.Type = "oneshot";
          script = ''
            install -d -m 0775 -o ${username} -g users ${dataRoot}
            if ! btrfs subvolume show ${lib.escapeShellArg dbRoot} >/dev/null 2>&1; then
              btrfs subvolume create ${lib.escapeShellArg dbRoot}
              chattr +C ${lib.escapeShellArg dbRoot} || true
            fi
            chown ${username}:users ${lib.escapeShellArg dbRoot}
            chmod 0700 ${lib.escapeShellArg dbRoot}
            chattr +C ${lib.escapeShellArg dbRoot} || true
          '';
        };

        # Append one JSONL line per NixOS generation activation, letting
        # Lynchpin join telemetry rows back to the sinnix revision that
        # produced them. Lives here rather than in the lynchpin module because
        # machine-telemetry owns the captures/machine namespace
        # unconditionally; lynchpin is an opt-in consumer.
        #
        # Failures degrade silently (|| true) because activation must succeed
        # even if /realm is unavailable (e.g. recovery boot).
        system.activationScripts.lynchpinGenerationLog = lib.stringAfter [ "var" ] ''
          LOG_FILE="${dataDir}/generations.jsonl"
          ${pkgs.coreutils}/bin/mkdir -p "$(${pkgs.coreutils}/bin/dirname "$LOG_FILE")" 2>/dev/null || true

          STORE_PATH="$(${pkgs.coreutils}/bin/readlink -f /run/current-system 2>/dev/null || echo unknown)"
          GENERATION="unknown"
          if [ -L /nix/var/nix/profiles/system ]; then
            GENERATION="$(${pkgs.coreutils}/bin/readlink /nix/var/nix/profiles/system | ${pkgs.gnused}/bin/sed -n 's/^system-\([0-9]\+\)-link$/\1/p')"
          fi
          ACTIVATED_AT="$(${pkgs.coreutils}/bin/date -u +%Y-%m-%dT%H:%M:%S+00:00)"

          ${pkgs.coreutils}/bin/printf '%s\n' "$(${pkgs.jq}/bin/jq -nc \
            --arg generation "''${GENERATION:-unknown}" \
            --arg activated_at "$ACTIVATED_AT" \
            --arg store_path "$STORE_PATH" \
            --arg sinnix_revision ${
              lib.escapeShellArg (if systemRevision == null then "unknown" else systemRevision)
            } \
            --arg nixos_label "${config.system.nixos.label}" \
            --arg host "${config.networking.hostName}" \
            '{generation: $generation, activated_at: $activated_at, store_path: $store_path, sinnix_revision: $sinnix_revision, nixos_label: $nixos_label, host: $host}')" \
            >> "$LOG_FILE" 2>/dev/null || true
        '';

        systemd.services.machine-telemetry = {
          description = "machine-telemetry - canonical host telemetry capture";
          wantedBy = [ "multi-user.target" ];
          after = [
            "local-fs.target"
            "lm_sensors.service"
          ];
          path = [
            pkgs.coreutils
            # pkgs.bind ships only the daemon; nslookup and dig live in the
            # split bind.dnsutils output. Without dnsutils the network probe's
            # nslookup exits 127 and every sample records
            # network.dns_probe_failed as though DNS were down.
            pkgs.bind
            pkgs.bind.dnsutils
            pkgs.curl
            pkgs.ethtool
            pkgs.iproute2
            pkgs.iputils
            pkgs.procps
            pkgs.systemd
            pkgs.util-linux
          ]
          ++ lib.optionals (config.sinnix.gpu.mode != "igpu") [
            pkgs.linuxPackages.nvidia_x11
          ];
          serviceConfig = {
            Type = "simple";
            # pynvml dlopen()s libnvidia-ml.so.1; NixOS exposes it at /run/opengl-driver/lib.
            Environment = lib.optionals (config.sinnix.gpu.mode != "igpu") [
              "LD_LIBRARY_PATH=/run/opengl-driver/lib"
            ];
            ExecStart = "${machineTelemetry}/bin/machine-telemetry --db ${dbPath} --manifest ${manifestPath} --host ${hostName} --cgroups ${cgroupArgs} --units ${unitArgs} --user-name ${username}";
            Restart = "on-failure";
            RestartSec = "5s";
          }
          // lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "machine-telemetry.service";
          };
        };

        sinnix.runtime.units = {
          machine-telemetry-sqlite-backup = {
            unit = "machine-telemetry-sqlite-backup.service";
            resourceClass = "backup";
            notifyOnFailure = true;
          };
          machine-telemetry-seal = {
            unit = "machine-telemetry-seal.service";
            resourceClass = "backup";
            notifyOnFailure = true;
          };
          machine-telemetry-seal-timer = {
            unit = "machine-telemetry-seal.timer";
          };
          machine-telemetry-sqlite-backup-timer = {
            unit = "machine-telemetry-sqlite-backup.timer";
          };
        };

      }
    ];
} args
