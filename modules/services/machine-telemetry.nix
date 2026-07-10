# machine-telemetry: canonical host sensor and pressure capture
#
# Sinnix owns capture mechanics; Lynchpin owns interpretation. This service
# writes a typed SQLite stream under /realm/data/captures/machine/ that
# Lynchpin can promote into its substrate without scraping mixed-schema CSV.
# Captures CPU RAPL package/core watts, thermal state, PSI, service placement,
# scheduler latency samples, and periodic network-link probes.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  ...
}@args:
let
  inherit (config.sinnix.paths) capturesRoot realmRoot;
  hostName = config.networking.hostName;
  dataRoot = "${capturesRoot}/machine";
  dataDir = dataRoot;
  legacyDbPath = "${dataDir}/telemetry.sqlite";
  dbRoot = "${realmRoot}/db/machine-telemetry";
  dbPath = "${dbRoot}/telemetry.sqlite";
  # 2026-07-10: moved off /persist (worn MX500) to /realm; still inside the
  # /realm btrbk→borg coverage.
  backupRoot = "/realm/backup/machine-telemetry";
  manifestPath = "${dataDir}/manifest.json";
  username = config.sinnix.user.name;

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
    {
      systemd.tmpfiles.rules = [
        "d ${realmRoot}/db 0755 root root -"
        "d ${dataRoot} 0755 root users -"
        "d ${dataDir}/boot 0750 root users -"
        "d ${dataDir}/experiments 0775 root users -"
        "d ${dataDir}/legacy 0775 root users -"
        "d ${backupRoot} 0700 ${username} users -"
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
          install -d -m 0755 -o root -g root ${realmRoot}/db
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

      # Activation hook: append one JSONL line per NixOS generation
      # activation to ${dataDir}/generations.jsonl. Lynchpin reads this
      # to join telemetry rows back to the sinnix configuration revision
      # that produced them — answers "what changed at generation N?"
      # without git archaeology. Lives here (not in the lynchpin module)
      # because machine-telemetry owns the captures/machine namespace
      # unconditionally; lynchpin is an opt-in consumer.
      #
      # Append-only. Failures degrade silently (|| true) because the
      # activation must succeed even if /realm is unavailable
      # (e.g. recovery boot).
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
          # pkgs.bind ships only the daemon (named, rndc, etc.); nslookup +
          # dig live in the split bind.dnsutils output. Without dnsutils on
          # PATH the network probe's `nslookup example.com` invocation
          # returns exit 127, the collector records gap_codes_json carrying
          # network.dns_probe_failed on every sample, and the substrate row
          # looks like DNS is down (gap-summary surfaced this at 100% share
          # on 2026-05-18). Keep both for ad-hoc operator debug paths.
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
          observe.enable = true;
        };
        machine-telemetry-sqlite-backup-timer = {
          unit = "machine-telemetry-sqlite-backup.timer";
          kind = "timer";
          resourceClass = "backup-maintenance";
        };
      };

      systemd.services.machine-telemetry-sqlite-backup = {
        description = "Back up machine telemetry SQLite database";
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
        ];
        restartIfChanged = false;
        serviceConfig =
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "machine-telemetry-sqlite-backup.service";
          })
          // {
            Type = "oneshot";
            User = username;
            Group = "users";
            TimeoutStartSec = "30min";
            MemoryHigh = "2G";
            MemoryMax = "4G";
          };
        path = [
          pkgs.coreutils
          pkgs.findutils
          pkgs.gawk
          pkgs.sqlite
          pkgs.zstd
        ];
        script = ''
          set -euo pipefail

          umask 077
          install -d -m 0700 -o ${lib.escapeShellArg username} -g users ${lib.escapeShellArg backupRoot}

          stamp="$(date -u +%Y%m%dT%H%M%SZ)"
          raw_tmp=${lib.escapeShellArg backupRoot}/telemetry-"$stamp".sqlite.tmp
          zst_tmp="$raw_tmp.zst.tmp"
          final=${lib.escapeShellArg backupRoot}/telemetry-"$stamp".sqlite.zst

          cleanup() {
            rm -f "$raw_tmp" "$zst_tmp"
          }
          trap cleanup EXIT

          sqlite3 ${lib.escapeShellArg dbPath} ".backup '$raw_tmp'"
          chmod 0600 "$raw_tmp"
          zstd -T1 -q -f "$raw_tmp" -o "$zst_tmp"
          chmod 0600 "$zst_tmp"
          mv -f "$zst_tmp" "$final"
          rm -f "$raw_tmp"
          trap - EXIT

          find ${lib.escapeShellArg backupRoot} \
            -maxdepth 1 \
            -type f \
            -name 'telemetry-*.sqlite.zst' \
            -printf '%T@ %p\n' \
            | sort -rn \
            | awk 'NR > 7 { print substr($0, index($0, $2)) }' \
            | xargs -r rm -f
        '';
      };

      systemd.timers.machine-telemetry-sqlite-backup = {
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnCalendar = "*-*-* 03:42:00";
          RandomizedDelaySec = "30min";
          Persistent = false;
        };
      };
    };
} args
