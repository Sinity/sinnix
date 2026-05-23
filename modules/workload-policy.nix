# Workload policy registry
#
# One source of truth for Sinnix resource classes, systemd slices, command
# wrappers, pressure backoff targets, and observability classification.
{ lib, config, ... }:
let
  policy = {
    schema = "sinnix-workload-policy-v1";

    classes = {
      interactive-agent.description = "Interactive AI agent shells and frontends";
      developer-build.description = "User-initiated builds, tests, and Nix work";
      background-maintenance.description = "Bulk maintenance that should yield to interaction";
      capture-runtime.description = "Long-running capture daemons";
      capture-substrate.description = "Databases and queues backing capture daemons";
      observability.description = "Monitoring needed during pressure incidents";
      system.description = "Ordinary system services without Sinnix-specific placement";
    };

    commandClasses = {
      agent = {
        resourceClass = "interactive-agent";
        slice = "agent.slice";
        nice = null;
        ioniceClass = null;
        ionicePriority = null;
        envDefaults = { };
      };
      build = {
        resourceClass = "developer-build";
        slice = "build.slice";
        nice = 5;
        ioniceClass = "best-effort";
        ionicePriority = 7;
        envDefaults = {
          CARGO_BUILD_JOBS = "4";
          CMAKE_BUILD_PARALLEL_LEVEL = "4";
          MAKEFLAGS = "-j4";
          NIX_BUILD_CORES = "4";
          SCCACHE_IDLE_TIMEOUT = "10";
        };
      };
      background = {
        resourceClass = "background-maintenance";
        slice = "background.slice";
        nice = 10;
        ioniceClass = "idle";
        ionicePriority = null;
        envDefaults = { };
      };
      nix-build = {
        resourceClass = "developer-build";
        slice = "nix-build.slice";
        nice = 10;
        ioniceClass = "idle";
        ionicePriority = null;
        envDefaults = { };
      };
    };

    slices = {
      system = {
        background = {
          CPUWeight = 10;
          IOWeight = 5;
          MemoryHigh = "4G";
          MemoryMax = "10G";
        };
        nix-build = {
          CPUWeight = 20;
          IOWeight = 10;
          MemoryHigh = "8G";
          MemoryMax = "16G";
        };
        system-critical = {
          CPUWeight = 200;
          IOWeight = 100;
          MemoryLow = "512M";
        };
      };
      user = {
        agent = {
          CPUWeight = 200;
          IOWeight = 100;
          MemoryLow = "1G";
          MemoryHigh = "12G";
        };
        background = {
          CPUWeight = 10;
          IOWeight = 5;
          MemoryHigh = "4G";
          MemoryMax = "10G";
        };
        build = {
          CPUWeight = 20;
          IOWeight = 10;
          MemoryHigh = "8G";
          MemoryMax = "16G";
        };
        nix-build = {
          CPUWeight = 20;
          IOWeight = 10;
          MemoryHigh = "8G";
          MemoryMax = "16G";
        };
      };
    };

    pressureBackoff = {
      systemUnits = [
        "nix-build.slice"
        "background.slice"
      ];
      userUnits = [
        "build.slice"
        "nix-build.slice"
        "background.slice"
      ];
      cpuWeight = 1;
      ioWeight = 1;
    };

    observedUnits = {
      system = [
        "below.service"
        "sinnix-pressure-watchdog.service"
        "sinex-runtime.target"
        "sinex-runtime.timer"
        "sinex-ingestd.service"
        "sinex-filesystem-1.service"
        "sinex-gateway.service"
        "nats.service"
        "postgresql.service"
        "nix-gc.service"
        "nix-optimise.service"
        "sinex-document-scan.service"
        "btrbk.service"
        "btrbk.timer"
        "borgbackup-job-realm.service"
        "borgbackup-job-persist.service"
        "borgbackup-check.service"
      ];
      user = [
        "polylogued.service"
        "polylogue-browser-capture.service"
      ];
    };

    observedSlices = {
      system = [
        "nix-build.slice"
        "background.slice"
        "system-critical.slice"
      ];
      user = [
        "agent.slice"
        "build.slice"
        "nix-build.slice"
        "background.slice"
      ];
    };

    unitClasses = {
      "below.service" = "observability";
      "sinnix-pressure-watchdog.service" = "observability";
      "btrbk.service" = "background-maintenance";
      "btrbk.timer" = "background-maintenance";
      "borgbackup-job-realm.service" = "background-maintenance";
      "borgbackup-job-persist.service" = "background-maintenance";
      "borgbackup-check.service" = "background-maintenance";
      "nix-gc.service" = "background-maintenance";
      "nix-optimise.service" = "background-maintenance";
      "polylogued.service" = "capture-runtime";
      "polylogue-browser-capture.service" = "capture-runtime";
      "sinex-runtime.target" = "capture-runtime";
      "sinex-runtime.timer" = "capture-runtime";
      "sinex-ingestd.service" = "capture-runtime";
      "sinex-filesystem-1.service" = "capture-runtime";
      "sinex-gateway.service" = "capture-runtime";
      "nats.service" = "capture-substrate";
      "postgresql.service" = "capture-substrate";
      "sinex-document-scan.service" = "background-maintenance";
    };
  };
in
{
  options.sinnix.workloadPolicy = lib.mkOption {
    type = lib.types.attrs;
    readOnly = true;
    default = policy;
    description = "Canonical Sinnix workload classes, slices, and observability policy.";
  };

  config.environment.etc."sinnix/workload-policy.json".text =
    builtins.toJSON config.sinnix.workloadPolicy;
}
