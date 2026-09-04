# machine-telemetry: canonical host sensor and pressure capture
#
# Sinnix owns capture mechanics; Lynchpin owns interpretation. This service
# writes a typed SQLite stream under /realm/data/machine/ that
# Lynchpin can promote into its substrate without scraping mixed-schema CSV.
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
  dataRoot = config.sinnix.paths.machineRoot;
  dataDir = dataRoot;
  legacyDbPath = "${dataDir}/telemetry.sqlite";
  dbRoot = "${realmRoot}/state/machine-telemetry";
  dbPath = "${dbRoot}/telemetry.sqlite";
  # Lives on /realm, not /persist (worn MX500); still inside the /realm
  # btrbk→borg coverage.
  backupRoot = "/realm/state/db-dumps/machine-telemetry";
  backupSnapshotRoot = "${realmRoot}/state/machine-telemetry-backup-snapshots";
  manifestPath = "${dataDir}/manifest.json";
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;

  machineTelemetry = pkgs.writeTextFile {
    name = "machine-telemetry";
    destination = "/bin/machine-telemetry";
    executable = true;
    text = ''
      #!${pkgs.python3.withPackages (p: [ p.nvidia-ml-py ])}/bin/python3
    ''
    + builtins.readFile ../../pkgs/machine-telemetry/collector.py;
  };
in
mkServiceModule {
  name = "machine-telemetry";
  description = "Canonical host machine telemetry capture for Lynchpin analysis";
  surface = {
    unit = "machine-telemetry.service";
    resourceClass = "observability";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "machine-telemetry";
        path = dataRoot;
        cadenceSeconds = config.sinnix.services."machine-telemetry".intervalSec or 10;
      }
    ];
  };
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.int;
      default = 10;
      description = "Machine telemetry sampling interval in seconds.";
    };
    serviceIntervalSec = lib.mkOption {
      type = lib.types.int;
      default = 10;
      description = "Systemd service-state sampling interval in seconds. Matches the heartbeat cadence so per-unit IO bytes are attributable at below-comparable resolution.";
    };
    networkIntervalSec = lib.mkOption {
      type = lib.types.int;
      default = 300;
      description = "Network-link sampling interval in seconds; 0 disables the integrated network probe.";
    };
    networkInterfaceName = lib.mkOption {
      type = lib.types.str;
      default = "enp4s0";
      description = "Network interface used for machine telemetry NIC counters.";
    };
    networkGateway = lib.mkOption {
      type = lib.types.str;
      default = "192.168.1.1";
      description = "Gateway address used by the integrated machine telemetry ping probe.";
    };
    bufferbloatIntervalSec = lib.mkOption {
      type = lib.types.ints.unsigned;
      default = 1800;
      description = "Minimum seconds between integrated 10 MB bufferbloat download probes. 0 disables the heavy probe.";
    };
    gpuIntervalSec = lib.mkOption {
      type = lib.types.numbers.nonnegative;
      default = 1.0;
      description = "Dedicated NVML-backed GPU sampler interval in seconds (power/temp/util/clocks). 0 disables the high-frequency sampler.";
    };
    processMemoryTop = lib.mkOption {
      type = lib.types.ints.unsigned;
      default = 50;
      description = "Number of top-PSS processes to persist in each process-memory sample.";
    };
    processMemoryIntervalSec = lib.mkOption {
      type = lib.types.numbers.nonnegative;
      default = 60.0;
      description = "Seconds between process smaps_rollup PSS/private memory samples. 0 disables process-memory sampling.";
    };
    killEventIntervalSec = lib.mkOption {
      type = lib.types.numbers.nonnegative;
      default = 30.0;
      description = "Seconds between journald scans for earlyoom/systemd-oomd/kernel OOM kill events. 0 disables kill-event capture.";
    };
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
      surfaceUnits = map (surface: surface.unit) config.sinnix.runtime.inventory.observedServices;
      unitArgs = lib.concatStringsSep "," (lib.unique surfaceUnits);
      userUid = "1000";
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
          path = "/user.slice/user-${userUid}.slice/user@${userUid}.service/agent.slice";
        }
        {
          label = "user.sinnixd-work";
          scope = "user";
          path = "/user.slice/user-${userUid}.slice/user@${userUid}.service/sinnixd.slice";
        }
        {
          label = "user.build";
          scope = "user";
          path = "/user.slice/user-${userUid}.slice/user@${userUid}.service/build.slice";
        }
        {
          label = "user.background";
          scope = "user";
          path = "/user.slice/user-${userUid}.slice/user@${userUid}.service/background.slice";
        }
        {
          label = "user.nix-build";
          scope = "user";
          path = "/user.slice/user-${userUid}.slice/user@${userUid}.service/nix-build.slice";
        }
        {
          label = "user.gpu-runtime";
          scope = "user";
          path = "/user.slice/user-${userUid}.slice/user@${userUid}.service/gpu-runtime.slice";
        }
        {
          label = "user.backup";
          scope = "user";
          path = "/user.slice/user-${userUid}.slice/user@${userUid}.service/backup.slice";
        }
      ];
      cgroupSpecs = defaultMonitoredCgroups ++ cfg.extraMonitoredCgroups;
      cgroupArgs = lib.concatStringsSep "," (
        map (item: "${item.label}|${item.scope}|${item.path}") cgroupSpecs
      );
    in
    lib.mkMerge [
      # Second unit pair (documented structural exception): the primary
      # surface above is machine-telemetry.service itself, so the sqlite
      # backup oneshot+timer gets a direct mkScheduledJob call rather than
      # mkServiceModule's single-unit `job` sugar.
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "machine-telemetry-sqlite-backup";
          description = "Back up machine telemetry SQLite database";
          surface = config.sinnix.runtime.surfaces.machine-telemetry-sqlite-backup;
        }
        {
          script = ''
            set -euo pipefail

            umask 077
            install -d -m 0700 -o ${lib.escapeShellArg username} -g users ${lib.escapeShellArg backupRoot}

            stamp="$(date -u +%Y%m%dT%H%M%SZ)"
            final=${lib.escapeShellArg backupRoot}/telemetry-"$stamp".sqlite.zst

            snapshot="${backupSnapshotRoot}/telemetry-$stamp"
            cleanup() {
              if [ -d "$snapshot" ]; then
                btrfs subvolume delete "$snapshot" >/dev/null
              fi
            }
            trap cleanup EXIT

            # The database is NOCOW, so cloning its file is not a reliable
            # constant-time operation. A read-only subvolume snapshot freezes
            # the checkpointed input; the helper then compresses it directly.
            sqlite3 ${lib.escapeShellArg dbPath} 'PRAGMA wal_checkpoint(TRUNCATE);'
            if [ -e ${lib.escapeShellArg "${dbPath}-wal"} ]; then
              echo "machine telemetry WAL remained after checkpoint" >&2
              exit 1
            fi
            btrfs subvolume snapshot -r ${lib.escapeShellArg dbRoot} "$snapshot"
            sinnix-sqlite-backup --immutable-source "$snapshot/telemetry.sqlite" "$final"
            chown ${lib.escapeShellArg username}:users "$final"

          '';
          path = [
            pkgs.coreutils
            pkgs.findutils
            pkgs.gawk
            pkgs.btrfs-progs
            pkgs.sqlite
            scriptPkgs.sinnix-sqlite-backup
          ];
          # Btrfs subvolume snapshots require CAP_SYS_ADMIN; the published
          # artifact is handed back to the operator below.
          user = "root";
          serviceConfig = {
            Group = "users";
            TimeoutStartSec = "30min";
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
          # Operator-owned like the rest of the lake, and group-writable so the
          # root daemons and operator producers that share this namespace can
          # both create files. It must NOT be root-owned under an
          # operator-owned parent: systemd-tmpfiles refuses such a directory
          # outright ("Detected unsafe path transition ... during
          # canonicalization"), which silently stops it managing this path at
          # all.
          "d ${dataRoot} 0775 ${username} users -"
          "d ${dataDir}/experiments 0775 ${username} users -"
          "d ${dataDir}/legacy 0775 ${username} users -"
          "d ${backupRoot} 0700 ${username} users -"
          "d ${backupSnapshotRoot} 0700 ${username} users -"
        ];

        systemd.services.machine-telemetry-db-scaffold = {
          description = "Create machine telemetry SQLite nodatacow subvolume";
          requiredBy = [ "machine-telemetry.service" ];
          before = [ "machine-telemetry.service" ];
          requires = [ "realm.mount" ];
          after = [ "realm.mount" ];
          path = [
            pkgs.btrfs-progs
            pkgs.coreutils
            pkgs.e2fsprogs
            pkgs.sqlite
          ];
          serviceConfig.Type = "oneshot";
          script = ''
            install -d -m 0755 -o root -g users ${dataRoot}
            if ! btrfs subvolume show ${lib.escapeShellArg dbRoot} >/dev/null 2>&1; then
              btrfs subvolume create ${lib.escapeShellArg dbRoot}
              chattr +C ${lib.escapeShellArg dbRoot} || true
            fi
            chown root:users ${lib.escapeShellArg dbRoot}
            chmod 0755 ${lib.escapeShellArg dbRoot}
            chattr +C ${lib.escapeShellArg dbRoot} || true

            if [ -L ${lib.escapeShellArg legacyDbPath} ]; then
              current="$(readlink ${lib.escapeShellArg legacyDbPath})"
              if [ "$current" != ${lib.escapeShellArg dbPath} ]; then
                echo "Refusing to replace unexpected machine telemetry DB symlink ${legacyDbPath} -> $current" >&2
                exit 1
              fi
            elif [ -e ${lib.escapeShellArg legacyDbPath} ]; then
              sqlite3 ${lib.escapeShellArg legacyDbPath} 'PRAGMA wal_checkpoint(TRUNCATE);'
              for sidecar in ${lib.escapeShellArg "${legacyDbPath}-wal"} ${lib.escapeShellArg "${legacyDbPath}-shm"}; do
                if [ -e "$sidecar" ]; then
                  echo "Refusing to migrate machine telemetry DB while SQLite sidecar exists: $sidecar" >&2
                  echo "Stop machine-telemetry and checkpoint/truncate WAL before running machine-telemetry-db-scaffold." >&2
                  exit 1
                fi
              done
              if [ -e ${lib.escapeShellArg dbPath} ]; then
                echo "Refusing to overwrite existing machine telemetry DB target ${dbPath}" >&2
                exit 1
              fi
              cp --reflink=never --preserve=mode,ownership,timestamps ${lib.escapeShellArg legacyDbPath} ${lib.escapeShellArg "${dbPath}.tmp"}
              mv ${lib.escapeShellArg "${dbPath}.tmp"} ${lib.escapeShellArg dbPath}
              rm ${lib.escapeShellArg legacyDbPath}
              ln -s ${lib.escapeShellArg dbPath} ${lib.escapeShellArg legacyDbPath}
            elif [ -e ${lib.escapeShellArg dbPath} ]; then
              ln -s ${lib.escapeShellArg dbPath} ${lib.escapeShellArg legacyDbPath}
            fi
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
            --arg sinnix_revision "${config.system.configurationRevision}" \
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
            ExecStart = "${machineTelemetry}/bin/machine-telemetry --db ${dbPath} --manifest ${manifestPath} --host ${hostName} --interval ${toString cfg.intervalSec} --service-interval ${toString cfg.serviceIntervalSec} --network-interval ${toString cfg.networkIntervalSec} --network-interface ${cfg.networkInterfaceName} --network-gateway ${cfg.networkGateway} --bufferbloat-interval ${toString cfg.bufferbloatIntervalSec} --gpu-interval ${toString cfg.gpuIntervalSec} --process-memory-top ${toString cfg.processMemoryTop} --process-memory-interval ${toString cfg.processMemoryIntervalSec} --kill-event-interval ${toString cfg.killEventIntervalSec} --cgroups ${cgroupArgs} --units ${unitArgs} --user-name ${username}";
            Restart = "on-failure";
            RestartSec = "5s";
          }
          // lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "machine-telemetry.service";
          };
        };

        sinnix.runtime.surfaces = {
          machine-telemetry-sqlite-backup = {
            unit = "machine-telemetry-sqlite-backup.service";
            resourceClass = "backup-maintenance";
            resources = {
              MemoryHigh = "2G";
              MemoryMax = "4G";
            };
            observe.enable = true;
          };
          machine-telemetry-sqlite-backup-timer = {
            unit = "machine-telemetry-sqlite-backup.timer";
            kind = "timer";
            resourceClass = "backup-maintenance";
          };
        };

      }
    ];
} args
