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
  inherit (config.sinnix.paths) capturesRoot;
  hostName = config.networking.hostName;
  dataRoot = "${capturesRoot}/machine";
  dataDir = dataRoot;
  dbPath = "${dataDir}/telemetry.sqlite";
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
    in
    {
      systemd.tmpfiles.rules = [
        "d ${dataRoot} 0755 root users -"
        "d ${dataDir}/boot 0750 root users -"
        "d ${dataDir}/experiments 0775 root users -"
        "d ${dataDir}/legacy 0775 root users -"
      ];

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
          ExecStart = "${machineTelemetry}/bin/machine-telemetry --db ${dbPath} --manifest ${manifestPath} --host ${hostName} --interval ${toString cfg.intervalSec} --service-interval ${toString cfg.serviceIntervalSec} --network-interval ${toString cfg.networkIntervalSec} --network-interface ${cfg.networkInterfaceName} --network-gateway ${cfg.networkGateway} --bufferbloat-interval ${toString cfg.bufferbloatIntervalSec} --gpu-interval ${toString cfg.gpuIntervalSec} --units ${unitArgs} --user-name ${username}";
          Restart = "on-failure";
          RestartSec = "5s";
        }
        // lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "machine-telemetry.service";
        };
      };
    };
} args
