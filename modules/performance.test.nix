{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
  inputs,
  ...
}:
{
  name = "core-performance-policy";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "performance-policy-test";
        sinnix.machine.isDesktop = true;
        sinnix.features.cli.core.enable = true;
      }
    )
  ];
  assertions =
    config:
    let
      nixSettings = config.nix.settings;
      scopeScript = builtins.readFile (inputs.self + "/scripts/sinnix-scope");
      commandRegistry = builtins.readFile (inputs.self + "/flake/command-registry.nix");
      devShell = builtins.readFile (inputs.self + "/flake/dev-shell.nix");
      nixSafeScript = builtins.readFile (inputs.self + "/scripts/nix-safe");
      coreModule = builtins.readFile (inputs.self + "/modules/core.nix");
      performanceModule = builtins.readFile (inputs.self + "/modules/performance.nix");
      persistenceModule = builtins.readFile (inputs.self + "/modules/persistence.nix");
      cliCoreModule = builtins.readFile (inputs.self + "/modules/features/cli/core.nix");
      direnvrc = builtins.readFile (inputs.self + "/scripts/sinnix-direnvrc");
      rootCacheService = config.systemd.services.sinnix-root-cache-attrs;
      runtimeInventory = config.sinnix.runtime.inventory;
      runtimeInventoryJson =
        builtins.fromJSON
          config.environment.etc."sinnix/runtime-inventory.json".text;
      earlyoomAvoid = builtins.elemAt config.services.earlyoom.extraArgs 3;
      earlyoomPrefer = builtins.elemAt config.services.earlyoom.extraArgs 1;
      panicCaptureExec = config.systemd.services.panic-log-capture.serviceConfig.ExecStart;
      cpuPowerLimitExec = config.systemd.services.sinnix-cpu-power-limits.serviceConfig.ExecStart;
      noLocalSlice =
        name:
        !(builtins.hasAttr name config.systemd.slices)
        || (config.systemd.slices.${name}.sliceConfig or { }) == { };
      noUserSlice =
        name:
        !(builtins.hasAttr name config.systemd.user.slices)
        || (config.systemd.user.slices.${name}.sliceConfig or { }) == { };
      systemBackground = config.systemd.slices.background.sliceConfig;
      nixBuild = config.systemd.slices."nix-build".sliceConfig;
      systemCritical = config.systemd.slices."system-critical".sliceConfig;
      userAgent = config.systemd.user.slices.agent.sliceConfig;
      userBackground = config.systemd.user.slices.background.sliceConfig;
      userBuild = config.systemd.user.slices.build.sliceConfig;
      userNixBuild = config.systemd.user.slices."nix-build".sliceConfig;
    in
    [
      {
        assertion = !config.zramSwap.enable;
        message = "zram is intentionally disabled (2026-06-07); keep anon resident via low swappiness + cache reclaim, with a tiny disk swap as OOM cushion only";
      }
      {
        assertion = config.systemd.oomd.enable && config.services.earlyoom.enable;
        message = "systemd-oomd must provide slice-local pressure kills while earlyoom handles global emergencies";
      }
      {
        assertion =
          config.boot.kernel.sysctl."vm.dirty_background_bytes" == 64 * 1024 * 1024
          && config.boot.kernel.sysctl."vm.dirty_bytes" == 256 * 1024 * 1024;
        message = "desktop dirty writeback must stay byte-bounded for NVMe/Btrfs latency";
      }
      {
        assertion =
          config.boot.kernel.sysctl."kernel.hung_task_panic" == 0
          && config.boot.kernel.sysctl."kernel.hung_task_timeout_secs" == 120
          && config.boot.kernel.sysctl."kernel.panic" == 60
          && config.boot.kernel.sysctl."kernel.oops_all_cpu_backtrace" == 1
          && builtins.elem "ramoops" config.boot.kernelModules
          && builtins.elem "ramoops.dump_oops=1" config.boot.kernelParams;
        message = "desktop crash diagnostics must not auto-reboot on ordinary hung-task reports";
      }
      {
        assertion =
          lib.hasInfix "Hyprland" earlyoomAvoid
          && lib.hasInfix "below" earlyoomAvoid
          && lib.hasInfix "chrome" earlyoomAvoid
          && lib.hasInfix "firefox" earlyoomAvoid
          && lib.hasInfix "cargo" earlyoomPrefer
          && lib.hasInfix "nix-daemon" earlyoomPrefer
          && !(lib.hasInfix "chrome" earlyoomPrefer)
          && !(lib.hasInfix "firefox" earlyoomPrefer)
          && config.services.earlyoom.freeMemThreshold == 15
          && config.services.earlyoom.freeSwapThreshold == 90;
        message = "earlyoom must fire before disk-swap residency collapses interactivity";
      }
      {
        assertion =
          !(config.systemd.services ? sinnix-iocost-init)
          && !(config.systemd.services ? sinnix-swap-drain)
          && !(config.systemd.timers ? sinnix-swap-drain);
        message = "The retired io.cost and swap-drain services must not be installed";
      }
      {
        assertion =
          lib.hasInfix "/bin/panic-log-capture" panicCaptureExec
          && !(lib.hasInfix "panic-log-capture.sh" panicCaptureExec);
        message = "panic-log-capture must execute a packaged binary, not a non-executable store file";
      }
      {
        assertion =
          lib.hasInfix "/bin/sinnix-apply-cpu-power-limits" cpuPowerLimitExec
          && config.systemd.services.sinnix-cpu-power-limits.wantedBy == [ "multi-user.target" ];
        message = "desktop must apply conservative CPU package power limits at boot";
      }
      {
        assertion =
          !(config.systemd.services ? browser-oom-protect)
          && !(lib.hasInfix "oom_score_adj" performanceModule)
          && !(lib.hasInfix "pgrep -x" performanceModule);
        message = "desktop must not install the retired browser OOM score daemon";
      }
      {
        assertion =
          noLocalSlice "nix"
          && noLocalSlice "sinnix"
          && noLocalSlice "sinnix-maintenance"
          && noUserSlice "app"
          && noUserSlice "session";
        message = "Sinnix must not resurrect retired whole-session or maintenance slice policy";
      }
      {
        assertion =
          systemBackground.CPUWeight == 3
          && systemBackground.IOWeight == 1
          && systemBackground.MemoryHigh == "2G"
          && systemBackground.MemoryMax == "4G"
          && systemBackground.ManagedOOMMemoryPressure == "kill"
          && systemBackground.ManagedOOMMemoryPressureLimit == "25%"
          && nixBuild.CPUWeight == 5
          && nixBuild.IOWeight == 2
          && nixBuild.MemoryHigh == "10G"
          && nixBuild.MemoryMax == "18G"
          && nixBuild.ManagedOOMMemoryPressure == "kill"
          && nixBuild.ManagedOOMMemoryPressureLimit == "30%"
          && systemCritical.CPUWeight == 400
          && systemCritical.IOWeight == 300
          && systemCritical.MemoryLow == "2G"
          && userBackground.CPUWeight == 3
          && userBackground.IOWeight == 1
          && userBackground.MemoryMax == "4G"
          && userBackground.ManagedOOMMemoryPressure == "kill"
          && userBackground.ManagedOOMMemoryPressureLimit == "25%"
          && userBuild.CPUWeight == 5
          && userBuild.IOWeight == 2
          && userBuild.MemoryHigh == "3G"
          && userBuild.MemoryMax == "8G"
          && userBuild.ManagedOOMMemoryPressure == "kill"
          && userBuild.ManagedOOMMemoryPressureLimit == "30%"
          && userNixBuild.CPUWeight == 5
          && userNixBuild.IOWeight == 2
          && userNixBuild.MemoryHigh == "3G"
          && userNixBuild.MemoryMax == "8G"
          && userNixBuild.ManagedOOMMemoryPressure == "kill"
          && userNixBuild.ManagedOOMMemoryPressureLimit == "30%"
          && userAgent.CPUWeight == 400
          && userAgent.IOWeight == 300
          && userAgent.MemoryLow == "3G";
        message = "background/build/agent slices must keep measured resource budgets and pressure backpressure";
      }
      {
        assertion =
          !(config.systemd.user.services ? sinnix-thaw-interactive-scopes)
          && !(config.systemd.user.timers ? sinnix-thaw-interactive-scopes)
          && !(lib.hasInfix "FreezerState" performanceModule)
          && !(lib.hasInfix "systemctl --user thaw" performanceModule);
        message = "desktop must not install automatic frozen-scope repair jobs";
      }
      {
        assertion =
          nixSettings.max-jobs == 2
          && nixSettings.cores == 2
          && nixSettings.http-connections == 16
          && nixSettings.max-substitution-jobs == 8
          && nixSettings.keep-going == false
          && !(nixSettings ? use-cgroups)
          && !(builtins.elem "cgroups" nixSettings.experimental-features)
          &&
            nixSettings.experimental-features == [
              "nix-command"
              "flakes"
              "fetch-tree"
            ]
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-2" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_CORES:-2" commandRegistry
          && lib.hasInfix "SINNIX_REBUILD_MAX_JOBS:-2" devShell
          && lib.hasInfix "SINNIX_REBUILD_CORES:-2" devShell
          && lib.hasInfix "NIX_SAFE_MAX_JOBS:-2" nixSafeScript
          && lib.hasInfix "NIX_SAFE_CORES:-2" nixSafeScript;
        message = "Nix concurrency and substitution fan-out must stay bounded without enabling Nix cgroups";
      }
      {
        assertion =
          lib.hasInfix "usage: sinnix-scope <class> -- <command> [args...]" scopeScript
          && lib.hasInfix "SINNIX_RUNTIME_INVENTORY_FILE" scopeScript
          && lib.hasInfix "/etc/sinnix/runtime-inventory.json" scopeScript
          && lib.hasInfix "/run/current-system/etc/sinnix/runtime-inventory.json" scopeScript
          && lib.hasInfix "jq -er" scopeScript
          && lib.hasInfix ".commandClasses[$class] != null" scopeScript
          && lib.hasInfix ".environmentAllowList[]?" scopeScript
          && lib.hasInfix "systemd-run" scopeScript
          && lib.hasInfix "agent.slice" scopeScript
          && lib.hasInfix "build.slice" scopeScript
          && lib.hasInfix "background.slice" scopeScript
          && lib.hasInfix "nix-build.slice" scopeScript
          && lib.hasInfix ".commandClasses[$class].envDefaults" scopeScript
          && lib.hasInfix "ionice -c 2 -n" scopeScript
          && lib.hasInfix "nice -n \"$nice_level\"" scopeScript
          && lib.hasInfix "ionice -c 3" scopeScript
          && lib.hasInfix "--unit=\"$unit\"" scopeScript
          && lib.hasInfix "--user" scopeScript;
        message = "sinnix-scope must place heavy work in explicit resource slices and scheduler classes";
      }
      {
        assertion =
          runtimeInventory.schema == "sinnix-runtime-inventory-v1"
          && runtimeInventoryJson.schema == runtimeInventory.schema
          && runtimeInventory.commandClasses.build.slice == "build.slice"
          && runtimeInventory.commandClasses.build.envDefaults.MAKEFLAGS == "-j3"
          && runtimeInventory.commandClasses.build.envDefaults.CARGO_INCREMENTAL == "0"
          && runtimeInventory.commandClasses.agent.resourceClass == "interactive-agent"
          && runtimeInventory.classes.observability.serviceConfig.Slice == "system-critical.slice"
          && runtimeInventory.classes.interactive-access.serviceConfig.Slice == "system-critical.slice"
          && runtimeInventory.classes.backup-maintenance.serviceConfig.CPUWeight == 20
          && runtimeInventory.classes.capture-runtime.serviceConfig.MemoryMax == "8G"
          && builtins.elem "SINEX_DEV_CACHE_ROOT" runtimeInventory.environmentAllowList
          && runtimeInventory.surfaces.sshd.resourceClass == "interactive-access"
          && runtimeInventory.surfaces.nix-gc.resourceClass == "background-maintenance";
        message = "runtime policy registry must be the single source for command classes and declared surfaces";
      }
      {
        assertion =
          builtins.any (rule: lib.hasInfix "/var/cache/nix-build" rule) config.systemd.tmpfiles.rules
          && builtins.any (rule: lib.hasInfix "/var/cache/sinex" rule) config.systemd.tmpfiles.rules
          && lib.hasInfix "build-dir = /var/cache/nix-build" config.nix.extraOptions
          && rootCacheService.before == [ "nix-daemon.service" ]
          && rootCacheService.serviceConfig.Type == "oneshot"
          && lib.hasInfix "chattr +C" rootCacheService.script
          && builtins.elem "sinnix-root-cache-attrs.service" config.systemd.services.nix-daemon.requires
          && !(lib.hasInfix "/var/cache/nix-build" coreModule)
          && lib.hasInfix "Eval/fetcher cache stays under ~/.cache/nix" persistenceModule;
        message = "Nix scratch must use prepared root cache, not /realm or the failed /cache NVMe";
      }
      {
        assertion =
          !(lib.hasInfix "default_sinex_cache=" scopeScript)
          && !(lib.hasInfix "SINEX_DEV_ROOT" scopeScript)
          && lib.hasInfix "builtins.readFile ../../../scripts/sinnix-direnvrc" cliCoreModule
          && lib.hasInfix "_sinnix_setup_sinex_dev_cache" direnvrc
          && lib.hasInfix "/var/cache/sinex/$sinex_user/$sinex_hash" direnvrc
          && lib.hasInfix "export SINEX_DEV_CACHE_ROOT=\"$sinex_cache_base\"" direnvrc
          && !(lib.hasInfix "CARGO_INCREMENTAL" direnvrc)
          && lib.hasInfix "export CARGO_TARGET_DIR=\"$SINEX_DEV_CACHE_ROOT/target\"" direnvrc
          && lib.hasInfix "export SINEX_DEV_STATE_DIR=\"$sinex_cache_base/dev-state\"" direnvrc
          && lib.hasInfix "export SINEX_STATE_DIR=\"$project_root/.sinex/state\"" direnvrc
          && lib.hasInfix "export DATABASE_URL=\"postgresql:///sinex_dev?host=$SINEX_DEV_STATE_DIR/run\"" direnvrc;
        message = "Sinex dev cache relocation belongs to project direnv setup, not generic sinnix-scope";
      }
      {
        assertion =
          lib.hasInfix "systemd-oomd provides slice-local pressure backpressure" performanceModule
          && !(lib.hasInfix "while this host is being retuned" performanceModule);
        message = "OOM policy notes must be present-tense rather than retuning history";
      }
    ];
}
